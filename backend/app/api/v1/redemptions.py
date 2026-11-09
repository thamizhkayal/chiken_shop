from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.identity import User
from app.models.redemption import RedemptionRequest
from app.schemas.redemption import (
    RedemptionCancelResponse,
    RedemptionCreateRequest,
    RedemptionCreatedResponse,
    RedemptionQrResponse,
    RedemptionResponse,
)
from app.services import redemption_service
from app.services.redemption_service import RedemptionError

router = APIRouter(prefix="/redemptions", tags=["redemptions"])


@router.post("", response_model=RedemptionCreatedResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_redemption(
    request: Request,
    payload: RedemptionCreateRequest,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> RedemptionCreatedResponse:
    del request
    try:
        redemption, qr_svg = redemption_service.create_redemption(
            db, user.id, points=payload.points, idempotency_key=idempotency_key
        )
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _created_response(redemption, qr_svg)


@router.get("", response_model=list[RedemptionResponse])
def list_redemptions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> list[RedemptionResponse]:
    try:
        records = redemption_service.list_customer_redemptions(
            db, user.id, limit=limit, offset=offset
        )
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return [_response(record) for record in records]


@router.post("/{redemption_id}/qr", response_model=RedemptionQrResponse)
@limiter.limit("5/minute")
def refresh_redemption_qr(
    request: Request,
    redemption_id: UUID,
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> RedemptionQrResponse:
    del request
    try:
        redemption, qr_svg = redemption_service.refresh_qr(db, user.id, redemption_id)
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RedemptionQrResponse(
        redemption_id=redemption.id,
        expires_at=redemption.expires_at,
        qr_svg=qr_svg,
    )


@router.post("/{redemption_id}/cancel", response_model=RedemptionCancelResponse)
@limiter.limit("5/minute")
def cancel_redemption(
    request: Request,
    redemption_id: UUID,
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> RedemptionCancelResponse:
    del request
    try:
        redemption, refunded_points = redemption_service.cancel_redemption(db, user.id, redemption_id)
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RedemptionCancelResponse(
        **_response(redemption).model_dump(),
        refunded_points=refunded_points,
    )


def _response(redemption: RedemptionRequest) -> RedemptionResponse:
    return RedemptionResponse(
        id=redemption.id,
        points=redemption.points,
        raw_chicken_grams=redemption.points,
        status=redemption.status,
        expires_at=redemption.expires_at,
        fulfilled_grams=redemption.fulfilled_grams,
        fulfilled_at=redemption.fulfilled_at,
        created_at=redemption.created_at,
    )


def _created_response(
    redemption: RedemptionRequest,
    qr_svg: str,
) -> RedemptionCreatedResponse:
    return RedemptionCreatedResponse(
        **_response(redemption).model_dump(),
        qr_svg=qr_svg,
    )
