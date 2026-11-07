from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.wallet import WalletTransaction, WalletTransactionType
from app.repositories import wallet_repository


class WalletError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class WalletSummary:
    balance_points: int
    raw_chicken_grams: int
    minimum_redemption_points: int = 100


def get_summary(db: Session, user_id: UUID) -> WalletSummary:
    wallet = wallet_repository.get_wallet_for_user(db, user_id)
    if wallet is None:
        raise WalletError(404, "Wallet not found")
    return WalletSummary(
        balance_points=wallet.balance_points,
        raw_chicken_grams=wallet.balance_points,
    )


def reconcile_balance(db: Session, user_id: UUID) -> bool:
    wallet = wallet_repository.get_wallet_for_user(db, user_id)
    if wallet is None:
        raise WalletError(404, "Wallet not found")
    return wallet.balance_points == wallet_repository.get_ledger_balance(db, wallet.id)


def list_transactions(
    db: Session, user_id: UUID, *, limit: int, offset: int
) -> list[WalletTransaction]:
    return wallet_repository.list_transactions(db, user_id, limit=limit, offset=offset)


def award_daily_login_point(
    db: Session,
    user_id: UUID,
    *,
    occurred_at: datetime | None = None,
) -> bool:
    event_time = occurred_at or datetime.now(timezone.utc)
    if event_time.tzinfo is None:
        raise WalletError(422, "Login event time must include a timezone")
    business_day = event_time.astimezone(ZoneInfo(settings.business_timezone)).date()
    reference_id = f"{user_id}:{business_day.isoformat()}"

    wallet = wallet_repository.get_wallet_for_user(db, user_id, lock=True)
    if wallet is None:
        raise WalletError(404, "Wallet not found")
    existing = db.scalar(
        select(WalletTransaction.id).where(
            WalletTransaction.transaction_type == WalletTransactionType.DAILY_LOGIN_REWARD.value,
            WalletTransaction.reference_id == reference_id,
        )
    )
    if existing is not None:
        return False

    ledger_balance = wallet_repository.get_ledger_balance(db, wallet.id)
    if wallet.balance_points != ledger_balance:
        raise WalletError(409, "Wallet balance does not match its transaction ledger")

    wallet.balance_points += 1
    db.add(
        WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            transaction_type=WalletTransactionType.DAILY_LOGIN_REWARD.value,
            points_delta=1,
            description="Daily login reward",
            reference_id=reference_id,
        )
    )
    return True


def record_transaction(
    db: Session,
    *,
    user_id: UUID,
    transaction_type: WalletTransactionType,
    points_delta: int,
    description: str,
    reference_id: str | None = None,
) -> WalletTransaction:
    try:
        kind = WalletTransactionType(transaction_type)
    except (TypeError, ValueError) as exc:
        raise WalletError(422, "Unsupported wallet transaction type") from exc

    if not isinstance(points_delta, int) or isinstance(points_delta, bool):
        raise WalletError(422, "Points must be an integer")
    if not isinstance(description, str) or not description.strip() or len(description) > 240:
        raise WalletError(422, "A description of at most 240 characters is required")
    if reference_id is not None and (not reference_id.strip() or len(reference_id) > 128):
        raise WalletError(422, "Reference ID must contain 1 to 128 characters")
    if not _has_valid_delta(kind, points_delta):
        raise WalletError(422, "Point changes do not match the transaction type")
    if kind is WalletTransactionType.REDEMPTION_RESERVATION and points_delta > -100:
        raise WalletError(422, "A redemption must reserve at least 100 points")

    wallet = wallet_repository.get_wallet_for_user(db, user_id, lock=True)
    if wallet is None:
        raise WalletError(404, "Wallet not found")
    ledger_balance = wallet_repository.get_ledger_balance(db, wallet.id)
    if wallet.balance_points != ledger_balance:
        raise WalletError(409, "Wallet balance does not match its transaction ledger")

    new_balance = wallet.balance_points + points_delta
    if new_balance < 0:
        raise WalletError(409, "Insufficient points")

    wallet.balance_points = new_balance
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user_id,
        transaction_type=kind.value,
        points_delta=points_delta,
        description=description.strip(),
        reference_id=reference_id,
    )
    db.add(transaction)
    try:
        db.commit()
        db.refresh(transaction)
    except IntegrityError as exc:
        db.rollback()
        raise WalletError(409, "A transaction with this reference already exists") from exc
    return transaction


def _has_valid_delta(transaction_type: WalletTransactionType, points_delta: int) -> bool:
    if transaction_type in {
        WalletTransactionType.DAILY_LOGIN_REWARD,
        WalletTransactionType.SPIN_REWARD,
        WalletTransactionType.PUZZLE_REWARD,
        WalletTransactionType.REDEMPTION_CANCELLATION,
    }:
        return points_delta > 0
    if transaction_type in {WalletTransactionType.REDEMPTION_RESERVATION, WalletTransactionType.EXPIRY}:
        return points_delta < 0
    if transaction_type is WalletTransactionType.REDEMPTION_COMPLETION:
        return points_delta == 0
    return points_delta != 0
