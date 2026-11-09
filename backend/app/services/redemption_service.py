import hashlib
import hmac
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import qrcode
from qrcode.image.svg import SvgPathImage
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activities import AdminAuditLog
from app.models.identity import User
from app.models.redemption import RedemptionQrToken, RedemptionRequest, RedemptionStatus
from app.models.wallet import Wallet, WalletTransaction, WalletTransactionType

MINIMUM_REDEMPTION_POINTS = 100


class RedemptionError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class StaffRedemption:
    redemption: RedemptionRequest
    customer_name: str


@dataclass(frozen=True)
class FulfillmentResult:
    redemption: RedemptionRequest
    refunded_points: int


def create_redemption(
    db: Session,
    user_id: UUID,
    *,
    points: int,
    idempotency_key: str,
    now: datetime | None = None,
) -> tuple[RedemptionRequest, str]:
    created_at = _utc_now(now)
    existing = db.scalar(
        select(RedemptionRequest).where(
            RedemptionRequest.user_id == user_id,
            RedemptionRequest.idempotency_key == idempotency_key,
        ).with_for_update()
    )
    if existing is not None:
        if existing.points != points:
            raise RedemptionError(409, "This idempotency key was already used for a different amount")
        if existing.status != RedemptionStatus.RESERVED.value:
            raise RedemptionError(409, "This idempotency key has already been used")
        if _is_expired(existing.expires_at, created_at):
            _expire_redemption(db, existing, created_at)
            db.commit()
            raise RedemptionError(410, "This redemption QR code has expired")
        return existing, _issue_qr_token(db, existing)

    if points < MINIMUM_REDEMPTION_POINTS:
        raise RedemptionError(422, "A redemption must be at least 100 points")

    _expire_due_reservations(db, user_id, created_at)
    wallet = _get_verified_wallet(db, user_id, lock=True)
    existing = db.scalar(
        select(RedemptionRequest).where(
            RedemptionRequest.user_id == user_id,
            RedemptionRequest.idempotency_key == idempotency_key,
        ).with_for_update()
    )
    if existing is not None:
        if existing.points != points:
            raise RedemptionError(409, "This idempotency key was already used for a different amount")
        if existing.status != RedemptionStatus.RESERVED.value:
            raise RedemptionError(409, "This idempotency key has already been used")
        if _is_expired(existing.expires_at, created_at):
            _expire_redemption(db, existing, created_at)
            db.commit()
            raise RedemptionError(410, "This redemption QR code has expired")
        return existing, _issue_qr_token(db, existing)
    if wallet.balance_points < points:
        raise RedemptionError(409, "Insufficient points")

    redemption = RedemptionRequest(
        user_id=user_id,
        points=points,
        status=RedemptionStatus.RESERVED.value,
        idempotency_key=idempotency_key,
        expires_at=created_at + timedelta(minutes=settings.redemption_qr_ttl_minutes),
    )
    try:
        db.add(redemption)
        db.flush()
        wallet.balance_points -= points
        db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                user_id=user_id,
                transaction_type=WalletTransactionType.REDEMPTION_RESERVATION.value,
                points_delta=-points,
                description=f"Reserved {points} grams of raw chicken",
                reference_id=str(redemption.id),
            )
        )
        qr_record, qr_svg = _new_qr_record(redemption)
        db.add(qr_record)
        db.commit()
        db.refresh(redemption)
        return redemption, qr_svg
    except IntegrityError as exc:
        db.rollback()
        raise RedemptionError(409, "This redemption request could not be reserved") from exc


def list_customer_redemptions(
    db: Session,
    user_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    now: datetime | None = None,
) -> list[RedemptionRequest]:
    current_time = _utc_now(now)
    pending = list(
        db.scalars(
            select(RedemptionRequest)
            .where(
                RedemptionRequest.user_id == user_id,
                RedemptionRequest.status == RedemptionStatus.RESERVED.value,
                RedemptionRequest.expires_at <= current_time,
            )
            .with_for_update()
        )
    )
    for redemption in pending:
        _expire_redemption(db, redemption, current_time)
    if pending:
        db.commit()
    return list(
        db.scalars(
            select(RedemptionRequest)
            .where(RedemptionRequest.user_id == user_id)
            .order_by(RedemptionRequest.created_at.desc(), RedemptionRequest.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def refresh_qr(
    db: Session,
    user_id: UUID,
    redemption_id: UUID,
    *,
    now: datetime | None = None,
) -> tuple[RedemptionRequest, str]:
    current_time = _utc_now(now)
    redemption = _get_redemption(db, redemption_id, lock=True)
    if redemption.user_id != user_id:
        raise RedemptionError(404, "Redemption not found")
    if redemption.status != RedemptionStatus.RESERVED.value:
        raise RedemptionError(409, "This redemption is not active")
    if _is_expired(redemption.expires_at, current_time):
        _expire_redemption(db, redemption, current_time)
        db.commit()
        raise RedemptionError(410, "This redemption QR code has expired")
    return redemption, _issue_qr_token(db, redemption, rotate=True)


def cancel_redemption(
    db: Session,
    user_id: UUID,
    redemption_id: UUID,
    *,
    now: datetime | None = None,
) -> tuple[RedemptionRequest, int]:
    current_time = _utc_now(now)
    redemption = _get_redemption(db, redemption_id, lock=True)
    if redemption.user_id != user_id:
        raise RedemptionError(404, "Redemption not found")
    if redemption.status != RedemptionStatus.RESERVED.value:
        raise RedemptionError(409, "Only an active redemption can be cancelled")
    if _is_expired(redemption.expires_at, current_time):
        _expire_redemption(db, redemption, current_time)
        db.commit()
        return redemption, redemption.points
    refunded = _refund_reservation(
        db, redemption, RedemptionStatus.CANCELLED, current_time, actor_user_id=user_id
    )
    db.commit()
    db.refresh(redemption)
    return redemption, refunded


def verify_staff_token(
    db: Session,
    token: str,
    *,
    staff_user_id: UUID,
    now: datetime | None = None,
) -> StaffRedemption:
    current_time = _utc_now(now)
    qr_token = _find_token(db, token)
    if qr_token is None:
        raise RedemptionError(404, "Redemption QR code is invalid")
    redemption = _get_redemption(db, qr_token.redemption_id, lock=True)
    qr_token = _get_token_for_redemption(db, redemption.id, token, lock=True)
    if qr_token is None or qr_token.used_at is not None or qr_token.revoked_at is not None:
        raise RedemptionError(409, "Redemption QR code has already been used or replaced")
    if redemption.status != RedemptionStatus.RESERVED.value:
        raise RedemptionError(409, "This redemption is no longer active")
    if _is_expired(redemption.expires_at, current_time) or _is_expired(qr_token.expires_at, current_time):
        _expire_redemption(db, redemption, current_time)
        db.commit()
        raise RedemptionError(410, "This redemption QR code has expired")
    customer = db.get(User, redemption.user_id)
    if customer is None:
        raise RedemptionError(404, "Customer not found")
    db.add(
        AdminAuditLog(
            actor_user_id=staff_user_id,
            action="redemption_qr_verified",
            entity_type="redemption",
            entity_id=str(redemption.id),
            before_data={"status": RedemptionStatus.RESERVED.value},
            after_data={"status": RedemptionStatus.RESERVED.value, "points_reserved": redemption.points},
        )
    )
    db.commit()
    return StaffRedemption(redemption=redemption, customer_name=customer.full_name)


def fulfill_redemption(
    db: Session,
    staff_user_id: UUID,
    token: str,
    *,
    grams: int,
    now: datetime | None = None,
) -> FulfillmentResult:
    current_time = _utc_now(now)
    qr_token = _find_token(db, token)
    if qr_token is None:
        raise RedemptionError(404, "Redemption QR code is invalid")
    redemption = _get_redemption(db, qr_token.redemption_id, lock=True)
    qr_token = _get_token_for_redemption(db, redemption.id, token, lock=True)
    if qr_token is None or qr_token.used_at is not None or qr_token.revoked_at is not None:
        raise RedemptionError(409, "Redemption QR code has already been used or replaced")
    if redemption.status != RedemptionStatus.RESERVED.value:
        raise RedemptionError(409, "This redemption is no longer active")
    if _is_expired(redemption.expires_at, current_time) or _is_expired(qr_token.expires_at, current_time):
        _expire_redemption(db, redemption, current_time)
        db.commit()
        raise RedemptionError(410, "This redemption QR code has expired")
    if grams > redemption.points:
        raise RedemptionError(422, "Fulfilled chicken weight cannot exceed the reserved amount")

    wallet = _get_verified_wallet(db, redemption.user_id, lock=True)
    refunded = redemption.points - grams
    redemption.status = RedemptionStatus.FULFILLED.value
    redemption.fulfilled_grams = grams
    redemption.fulfilled_by_user_id = staff_user_id
    redemption.fulfilled_at = current_time
    qr_token.used_at = current_time
    db.add(
        WalletTransaction(
            wallet_id=wallet.id,
            user_id=redemption.user_id,
            transaction_type=WalletTransactionType.REDEMPTION_COMPLETION.value,
            points_delta=0,
            description=f"Fulfilled {grams} grams of raw chicken",
            reference_id=str(redemption.id),
        )
    )
    if refunded:
        wallet.balance_points += refunded
        db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                user_id=redemption.user_id,
                transaction_type=WalletTransactionType.REDEMPTION_CANCELLATION.value,
                points_delta=refunded,
                description=f"Refunded {refunded} unused redemption points",
                reference_id=f"{redemption.id}:partial-refund",
            )
        )
    db.add(
        AdminAuditLog(
            actor_user_id=staff_user_id,
            action="redemption_fulfilled",
            entity_type="redemption",
            entity_id=str(redemption.id),
            before_data={"status": RedemptionStatus.RESERVED.value, "points": redemption.points},
            after_data={
                "status": RedemptionStatus.FULFILLED.value,
                "fulfilled_grams": grams,
                "refunded_points": refunded,
            },
        )
    )
    db.commit()
    db.refresh(redemption)
    return FulfillmentResult(redemption=redemption, refunded_points=refunded)


def _get_verified_wallet(db: Session, user_id: UUID, *, lock: bool) -> Wallet:
    statement = select(Wallet).where(Wallet.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    wallet = db.scalar(statement)
    if wallet is None:
        raise RedemptionError(404, "Wallet not found")
    ledger_balance = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.points_delta), 0)).where(
            WalletTransaction.wallet_id == wallet.id
        )
    )
    if wallet.balance_points != ledger_balance:
        raise RedemptionError(409, "Wallet balance does not match its transaction ledger")
    return wallet


def _get_redemption(db: Session, redemption_id: UUID, *, lock: bool) -> RedemptionRequest:
    statement = select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    if lock:
        statement = statement.with_for_update()
    redemption = db.scalar(statement)
    if redemption is None:
        raise RedemptionError(404, "Redemption not found")
    return redemption


def _find_token(db: Session, token: str) -> RedemptionQrToken | None:
    return db.scalar(
        select(RedemptionQrToken).where(RedemptionQrToken.token_hash == _hash_token(token))
    )


def _get_token_for_redemption(
    db: Session,
    redemption_id: UUID,
    token: str,
    *,
    lock: bool,
) -> RedemptionQrToken | None:
    statement = select(RedemptionQrToken).where(
        RedemptionQrToken.redemption_id == redemption_id,
        RedemptionQrToken.token_hash == _hash_token(token),
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def _issue_qr_token(
    db: Session,
    redemption: RedemptionRequest,
    *,
    rotate: bool = False,
) -> str:
    existing_tokens = list(
        db.scalars(
            select(RedemptionQrToken).where(
                RedemptionQrToken.redemption_id == redemption.id,
                RedemptionQrToken.revoked_at.is_(None),
                RedemptionQrToken.used_at.is_(None),
            ).with_for_update()
        )
    )
    if existing_tokens and not rotate:
        token = _derive_token(redemption.id, existing_tokens[0].id)
        return _render_qr(token)
    current_time = datetime.now(timezone.utc)
    for existing in existing_tokens:
        existing.revoked_at = current_time
    qr_record, qr_svg = _new_qr_record(redemption)
    db.add(qr_record)
    db.commit()
    return qr_svg


def _new_qr_record(redemption: RedemptionRequest) -> tuple[RedemptionQrToken, str]:
    token_id = uuid4()
    token = _derive_token(redemption.id, token_id)
    return (
        RedemptionQrToken(
            id=token_id,
            redemption_id=redemption.id,
            token_hash=_hash_token(token),
            expires_at=redemption.expires_at,
        ),
        _render_qr(token),
    )


def _derive_token(redemption_id: UUID, token_id: UUID) -> str:
    secret = settings.redemption_qr_secret_key or settings.jwt_secret_key
    return hmac.new(
        secret.get_secret_value().encode("utf-8"),
        f"redemption:{redemption_id}:{token_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _render_qr(token: str) -> str:
    qr = qrcode.make(token, image_factory=SvgPathImage, box_size=6, border=4)
    output = io.BytesIO()
    qr.save(output)
    return output.getvalue().decode("utf-8")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _refund_reservation(
    db: Session,
    redemption: RedemptionRequest,
    status: RedemptionStatus,
    current_time: datetime,
    *,
    actor_user_id: UUID | None = None,
) -> int:
    wallet = _get_verified_wallet(db, redemption.user_id, lock=True)
    wallet.balance_points += redemption.points
    redemption.status = status.value
    redemption.cancelled_at = current_time
    db.execute(
        RedemptionQrToken.__table__.update()
        .where(
            RedemptionQrToken.redemption_id == redemption.id,
            RedemptionQrToken.revoked_at.is_(None),
        )
        .values(revoked_at=current_time)
    )
    db.add(
        WalletTransaction(
            wallet_id=wallet.id,
            user_id=redemption.user_id,
            transaction_type=WalletTransactionType.REDEMPTION_CANCELLATION.value,
            points_delta=redemption.points,
            description=(
                "Refunded expired redemption reservation"
                if status is RedemptionStatus.EXPIRED
                else "Refunded cancelled redemption reservation"
            ),
            reference_id=f"{redemption.id}:refund",
        )
    )
    db.add(
        AdminAuditLog(
            actor_user_id=actor_user_id,
            action=f"redemption_{status.value.lower()}",
            entity_type="redemption",
            entity_id=str(redemption.id),
            before_data={"status": RedemptionStatus.RESERVED.value},
            after_data={"status": status.value, "refunded_points": redemption.points},
        )
    )
    db.flush()
    return redemption.points


def _expire_redemption(db: Session, redemption: RedemptionRequest, current_time: datetime) -> None:
    if redemption.status != RedemptionStatus.RESERVED.value:
        return
    if _is_expired(redemption.expires_at, current_time):
        _refund_reservation(db, redemption, RedemptionStatus.EXPIRED, current_time)


def _expire_due_reservations(db: Session, user_id: UUID, current_time: datetime) -> None:
    due = list(
        db.scalars(
            select(RedemptionRequest)
            .where(
                RedemptionRequest.user_id == user_id,
                RedemptionRequest.status == RedemptionStatus.RESERVED.value,
                RedemptionRequest.expires_at <= current_time,
            )
            .with_for_update()
        )
    )
    for redemption in due:
        _expire_redemption(db, redemption, current_time)
    if due:
        db.commit()


def _utc_now(now: datetime | None) -> datetime:
    event_time = now or datetime.now(timezone.utc)
    if event_time.tzinfo is None:
        raise RedemptionError(422, "Redemption time must include a timezone")
    return event_time.astimezone(timezone.utc)


def _is_expired(expires_at: datetime, current_time: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= current_time
