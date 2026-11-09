from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.identity import User
from app.schemas.redemption import (
    StaffRedemptionFulfillRequest,
    StaffRedemptionFulfillResponse,
    StaffRedemptionVerifyRequest,
    StaffRedemptionVerifyResponse,
)
from app.services import redemption_service
from app.services.redemption_service import RedemptionError

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/health")
def staff_health(_: User = Depends(require_roles("staff", "admin"))):
    return {"status": "ok"}


@router.post("/redemptions/verify", response_model=StaffRedemptionVerifyResponse)
@limiter.limit("20/minute")
def verify_redemption(
    request: Request,
    payload: StaffRedemptionVerifyRequest,
    staff_user: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
) -> StaffRedemptionVerifyResponse:
    del request
    try:
        result = redemption_service.verify_staff_token(
            db, payload.token, staff_user_id=staff_user.id
        )
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    redemption = result.redemption
    return StaffRedemptionVerifyResponse(
        redemption_id=redemption.id,
        customer_name=result.customer_name,
        points_reserved=redemption.points,
        maximum_grams=redemption.points,
        status=redemption.status,
        expires_at=redemption.expires_at,
    )


@router.post("/redemptions/fulfill", response_model=StaffRedemptionFulfillResponse)
@limiter.limit("10/minute")
def fulfill_redemption(
    request: Request,
    payload: StaffRedemptionFulfillRequest,
    staff_user: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
) -> StaffRedemptionFulfillResponse:
    del request
    try:
        result = redemption_service.fulfill_redemption(
            db, staff_user.id, payload.token, grams=payload.grams
        )
    except RedemptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    redemption = result.redemption
    return StaffRedemptionFulfillResponse(
        redemption_id=redemption.id,
        status=redemption.status,
        fulfilled_grams=redemption.fulfilled_grams or 0,
        refunded_points=result.refunded_points,
        fulfilled_at=redemption.fulfilled_at,
    )
