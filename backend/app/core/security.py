from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(*, user_id: UUID, token_type: str, expires_delta: timedelta, jti: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    token = jwt.encode(
        {"sub": str(user_id), "type": token_type, "jti": jti, "iat": now, "exp": expires_at},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    claims = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat", "jti", "type"]},
    )
    if claims.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return claims
