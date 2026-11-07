from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.models.identity import User
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.auth import LoginRequest, MessageResponse, RegisterRequest, UserResponse
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
        "path": "/",
    }
    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.access_token_minutes * 60,
        **common,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.refresh_token_days * 86400,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/", domain=settings.cookie_domain, secure=settings.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie("refresh_token", path="/", domain=settings.cookie_domain, secure=settings.cookie_secure, httponly=True, samesite="lax")


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role.name,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    del request
    try:
        user, access, refresh = auth_service.register(db, payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _set_auth_cookies(response, access, refresh)
    return _user_response(user)


@router.post("/login", response_model=UserResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> UserResponse:
    del request
    try:
        user, access, refresh = auth_service.login(db, payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _set_auth_cookies(response, access, refresh)
    return _user_response(user)


@router.post("/refresh", response_model=UserResponse)
@limiter.limit("10/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    try:
        user, access, rotated_refresh = auth_service.rotate_refresh_token(db, raw_token)
    except AuthError as exc:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _set_auth_cookies(response, access, rotated_refresh)
    return _user_response(user)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    auth_service.revoke_refresh_token(db, request.cookies.get("refresh_token"))
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out")
