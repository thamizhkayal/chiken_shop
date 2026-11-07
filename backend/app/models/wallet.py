from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WalletTransactionType(str, Enum):
    DAILY_LOGIN_REWARD = "daily_login_reward"
    SPIN_REWARD = "spin_reward"
    PUZZLE_REWARD = "puzzle_reward"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    REDEMPTION_RESERVATION = "redemption_reservation"
    REDEMPTION_COMPLETION = "redemption_completion"
    REDEMPTION_CANCELLATION = "redemption_cancellation"
    EXPIRY = "expiry"


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance_points >= 0", name="ck_wallets_non_negative_balance"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    balance_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="wallet")
    transactions: Mapped[list["WalletTransaction"]] = relationship(back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN "
            "('daily_login_reward', 'spin_reward', 'puzzle_reward', 'admin_adjustment', 'redemption_reservation', "
            "'redemption_completion', 'redemption_cancellation', 'expiry')",
            name="ck_wallet_transactions_type",
        ),
        CheckConstraint(
            "points_delta != 0 OR transaction_type = 'redemption_completion'",
            name="ck_wallet_transactions_nonzero_delta",
        ),
        UniqueConstraint("transaction_type", "reference_id", name="uq_wallet_transactions_reference"),
        Index("ix_wallet_transactions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    wallet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    points_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    wallet: Mapped[Wallet] = relationship(back_populates="transactions")
    user: Mapped["User"] = relationship(back_populates="wallet_transactions")
