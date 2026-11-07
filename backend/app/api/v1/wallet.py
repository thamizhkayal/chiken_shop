from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.identity import User
from app.schemas.wallet import WalletSummaryResponse, WalletTransactionResponse
from app.services import wallet_service
from app.services.wallet_service import WalletError

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletSummaryResponse)
def get_wallet(
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> WalletSummaryResponse:
    try:
        summary = wallet_service.get_summary(db, user.id)
    except WalletError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return WalletSummaryResponse(
        balance_points=summary.balance_points,
        raw_chicken_grams=summary.raw_chicken_grams,
        minimum_redemption_points=summary.minimum_redemption_points,
    )


@router.get("/transactions", response_model=list[WalletTransactionResponse])
def get_wallet_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> list[WalletTransactionResponse]:
    return [
        WalletTransactionResponse.model_validate(transaction)
        for transaction in wallet_service.list_transactions(db, user.id, limit=limit, offset=offset)
    ]
