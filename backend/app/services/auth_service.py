import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models.identity import RefreshSession, User
from app.models.wallet import Wallet
from app.repositories import user_repository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.wallet_service import WalletError, award_daily_login_point


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code: int = status_code
        self.detail: str = detail
        super().__init__(detail)


def _issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access, _ = create_token(
        user_id=user.id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_minutes),
        jti=secrets.token_urlsafe(24),
    )
    refresh_jti = secrets.token_urlsafe(32)
    refresh, refresh_expiry = create_token(
        user_id=user.id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_days),
        jti=refresh_jti,
    )
    db.add(RefreshSession(jti=refresh_jti, user_id=user.id, expires_at=refresh_expiry))
    return access, refresh


def register(db: Session, payload: RegisterRequest) -> tuple[User, str, str]:
    role = user_repository.get_role(db, "customer")
    if role is None:
        raise AuthError(503, "Customer role is not initialized; run database migrations")

    user = User(
        role_id=role.id,
        email=str(payload.email).lower() if payload.email is not None else None,
        phone=payload.phone,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        db.add(Wallet(user_id=user.id))
        access, refresh = _issue_tokens(db, user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise AuthError(409, "An account with that email or mobile number already exists") from exc
    return user, access, refresh


def login(db: Session, payload: LoginRequest) -> tuple[User, str, str]:
    user = user_repository.find_by_contact(db, payload.identifier)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthError(401, "Invalid email/mobile number or password")
    if not user.is_active:
        raise AuthError(403, "This account is disabled")
    if user.role.name == "customer":
        try:
            award_daily_login_point(db, user.id)
        except WalletError as exc:
            raise AuthError(exc.status_code, exc.detail) from exc
    access, refresh = _issue_tokens(db, user)
    db.commit()
    return user, access, refresh


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str, str]:
    try:
        claims = decode_token(raw_token, "refresh")
        user_id = UUID(str(claims["sub"]))
        old_jti = str(claims["jti"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise AuthError(401, "Invalid or expired refresh token") from exc

    old_session = db.scalar(
        select(RefreshSession)
        .where(RefreshSession.jti == old_jti)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if (
        old_session is None
        or old_session.user_id != user_id
        or old_session.revoked_at is not None
        or old_session.expires_at.replace(tzinfo=timezone.utc) <= now
    ):
        raise AuthError(401, "Refresh token has expired or was already used")

    user = user_repository.find_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthError(401, "Account is unavailable")

    old_session.revoked_at = now
    access, refresh = _issue_tokens(db, user)
    db.flush()
    new_jti = str(decode_token(refresh, "refresh")["jti"])
    old_session.replaced_by_jti = new_jti
    db.commit()
    return user, access, refresh


def revoke_refresh_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    try:
        claims = decode_token(raw_token, "refresh")
        jti = str(claims["jti"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        return

    session = db.scalar(select(RefreshSession).where(RefreshSession.jti == jti).with_for_update())
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def authenticate_access_token(db: Session, token: str) -> User:
    try:
        claims = decode_token(token, "access")
        user_id = UUID(str(claims["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise AuthError(401, "Invalid or expired access token") from exc
    user = user_repository.find_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthError(401, "Account is unavailable")
    return user
