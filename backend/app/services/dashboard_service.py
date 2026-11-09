from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import Role, User
from app.models.redemption import RedemptionRequest, RedemptionStatus
from app.models.wallet import Wallet, WalletTransaction, WalletTransactionType


@dataclass(frozen=True)
class AdminDashboard:
    business_date: date
    total_customers: int
    daily_active_customers: int
    total_points_issued: int
    outstanding_points: int
    total_points_redeemed: int
    total_chicken_grams_redeemed: int
    pending_redemptions: int
    completed_redemptions: int
    expired_redemptions: int
    cancelled_redemptions: int


@dataclass(frozen=True)
class StaffRedemption:
    redemption_id: UUID
    customer_name: str
    points_reserved: int
    status: str
    fulfilled_grams: int | None
    created_at: datetime
    fulfilled_at: datetime | None


@dataclass(frozen=True)
class StaffDashboard:
    business_date: date
    pending_redemptions: int
    fulfilled_today: int
    chicken_grams_fulfilled_today: int
    recent_redemptions: list[StaffRedemption]


def _business_day_bounds() -> tuple[date, datetime, datetime]:
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(ZoneInfo(settings.business_timezone))
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo)
    local_end = local_start + timedelta(days=1)
    return local_now.date(), local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def get_admin_dashboard(db: Session) -> AdminDashboard:
    business_day, start, end = _business_day_bounds()
    customer_role_id = db.scalar(select(Role.id).where(Role.name == "customer"))
    total_customers = (
        db.scalar(select(func.count(User.id)).where(User.role_id == customer_role_id)) or 0
        if customer_role_id is not None
        else 0
    )
    active_customer_ids = select(WalletTransaction.user_id).where(
        WalletTransaction.created_at >= start,
        WalletTransaction.created_at < end,
    ).distinct()
    daily_active_customers = db.scalar(
        select(func.count()).select_from(active_customer_ids.subquery())
    ) or 0
    total_points_issued = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.points_delta), 0)).where(
            WalletTransaction.points_delta > 0,
            WalletTransaction.transaction_type.in_(
                [
                    WalletTransactionType.DAILY_LOGIN_REWARD.value,
                    WalletTransactionType.SPIN_REWARD.value,
                    WalletTransactionType.PUZZLE_REWARD.value,
                    WalletTransactionType.ADMIN_ADJUSTMENT.value,
                ]
            ),
        )
    ) or 0
    outstanding_points = db.scalar(select(func.coalesce(func.sum(Wallet.balance_points), 0))) or 0
    redeemed_grams = db.scalar(
        select(func.coalesce(func.sum(RedemptionRequest.fulfilled_grams), 0)).where(
            RedemptionRequest.status == RedemptionStatus.FULFILLED.value
        )
    ) or 0
    status_counts = dict(
        db.execute(
            select(RedemptionRequest.status, func.count(RedemptionRequest.id)).group_by(
                RedemptionRequest.status
            )
        ).all()
    )
    return AdminDashboard(
        business_date=business_day,
        total_customers=total_customers,
        daily_active_customers=daily_active_customers,
        total_points_issued=total_points_issued,
        outstanding_points=outstanding_points,
        total_points_redeemed=redeemed_grams,
        total_chicken_grams_redeemed=redeemed_grams,
        pending_redemptions=status_counts.get(RedemptionStatus.RESERVED.value, 0)
        + status_counts.get(RedemptionStatus.PENDING.value, 0),
        completed_redemptions=status_counts.get(RedemptionStatus.FULFILLED.value, 0),
        expired_redemptions=status_counts.get(RedemptionStatus.EXPIRED.value, 0),
        cancelled_redemptions=status_counts.get(RedemptionStatus.CANCELLED.value, 0),
    )


def get_staff_dashboard(db: Session, *, recent_limit: int = 8) -> StaffDashboard:
    business_day, start, end = _business_day_bounds()
    pending_redemptions = db.scalar(
        select(func.count(RedemptionRequest.id)).where(
            RedemptionRequest.status.in_(
                [RedemptionStatus.PENDING.value, RedemptionStatus.RESERVED.value]
            )
        )
    ) or 0
    fulfilled_today = db.scalar(
        select(func.count(RedemptionRequest.id)).where(
            RedemptionRequest.status == RedemptionStatus.FULFILLED.value,
            RedemptionRequest.fulfilled_at >= start,
            RedemptionRequest.fulfilled_at < end,
        )
    ) or 0
    grams_today = db.scalar(
        select(func.coalesce(func.sum(RedemptionRequest.fulfilled_grams), 0)).where(
            RedemptionRequest.status == RedemptionStatus.FULFILLED.value,
            RedemptionRequest.fulfilled_at >= start,
            RedemptionRequest.fulfilled_at < end,
        )
    ) or 0
    recent_redemptions = [
        StaffRedemption(
            redemption_id=redemption.id,
            customer_name=customer.full_name,
            points_reserved=redemption.points,
            status=redemption.status,
            fulfilled_grams=redemption.fulfilled_grams,
            created_at=redemption.created_at,
            fulfilled_at=redemption.fulfilled_at,
        )
        for redemption, customer in db.execute(
            select(RedemptionRequest, User)
            .join(User, User.id == RedemptionRequest.user_id)
            .order_by(RedemptionRequest.created_at.desc(), RedemptionRequest.id.desc())
            .limit(recent_limit)
        ).all()
    ]
    return StaffDashboard(
        business_date=business_day,
        pending_redemptions=pending_redemptions,
        fulfilled_today=fulfilled_today,
        chicken_grams_fulfilled_today=grams_today,
        recent_redemptions=recent_redemptions,
    )
