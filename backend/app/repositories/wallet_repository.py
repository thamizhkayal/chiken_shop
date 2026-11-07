from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wallet import Wallet, WalletTransaction


def get_wallet_for_user(db: Session, user_id: UUID, *, lock: bool = False) -> Wallet | None:
    statement = select(Wallet).where(Wallet.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_ledger_balance(db: Session, wallet_id: UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.points_delta), 0)).where(
            WalletTransaction.wallet_id == wallet_id
        )
    )


def list_transactions(db: Session, user_id: UUID, *, limit: int, offset: int) -> list[WalletTransaction]:
    return list(
        db.scalars(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
