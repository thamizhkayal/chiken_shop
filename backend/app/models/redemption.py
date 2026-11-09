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


class RedemptionStatus(str, Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    FULFILLED = "FULFILLED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class RedemptionRequest(Base):
    __tablename__ = "redemption_requests"
    __table_args__ = (
        CheckConstraint("points >= 100", name="ck_redemption_requests_minimum_points"),
        CheckConstraint(
            "fulfilled_grams IS NULL OR (fulfilled_grams > 0 AND fulfilled_grams <= points)",
            name="ck_redemption_requests_fulfilled_grams",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RESERVED', 'FULFILLED', 'EXPIRED', 'CANCELLED')",
            name="ck_redemption_requests_status",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="uq_redemption_requests_user_idempotency"),
        Index("ix_redemption_requests_user_created", "user_id", "created_at"),
        Index("ix_redemption_requests_status_expiry", "status", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RedemptionStatus.RESERVED.value)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fulfilled_grams: Mapped[int | None] = mapped_column(Integer)
    fulfilled_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tokens: Mapped[list["RedemptionQrToken"]] = relationship(
        back_populates="redemption", cascade="all, delete-orphan"
    )


class RedemptionQrToken(Base):
    __tablename__ = "redemption_qr_tokens"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    redemption_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("redemption_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    redemption: Mapped[RedemptionRequest] = relationship(back_populates="tokens")
