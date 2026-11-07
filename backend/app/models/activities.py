from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SpinConfiguration(Base):
    __tablename__ = "spin_configurations"
    __table_args__ = (
        CheckConstraint("daily_activity_cap >= 1", name="ck_spin_configurations_daily_cap_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    puzzle_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    daily_activity_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    rewards: Mapped[list["SpinRewardOption"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )


class SpinRewardOption(Base):
    __tablename__ = "spin_reward_options"
    __table_args__ = (
        CheckConstraint("points >= 0", name="ck_spin_reward_options_points_non_negative"),
        CheckConstraint(
            "probability_basis_points > 0 AND probability_basis_points <= 10000",
            name="ck_spin_reward_options_probability",
        ),
        UniqueConstraint("configuration_id", "points", name="uq_spin_reward_options_reward"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        ForeignKey("spin_configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    probability_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[SpinConfiguration] = relationship(back_populates="rewards")


class SpinSession(Base):
    __tablename__ = "spin_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "business_date", name="uq_spin_sessions_user_business_date"),
        CheckConstraint("reward_points >= 0", name="ck_spin_sessions_reward_non_negative"),
        CheckConstraint("probability_basis_points > 0", name="ck_spin_sessions_probability_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    probability_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PuzzleQuestion(Base):
    __tablename__ = "puzzle_questions"
    __table_args__ = (
        CheckConstraint("reward_points > 0", name="ck_puzzle_questions_reward_positive"),
        UniqueConstraint("business_date", name="uq_puzzle_questions_business_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attempts: Mapped[list["PuzzleAttempt"]] = relationship(back_populates="question")


class PuzzleAttempt(Base):
    __tablename__ = "puzzle_attempts"
    __table_args__ = (
        CheckConstraint("points_awarded >= 0", name="ck_puzzle_attempts_award_non_negative"),
        UniqueConstraint("question_id", "user_id", name="uq_puzzle_attempts_question_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("puzzle_questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question: Mapped[PuzzleQuestion] = relationship(back_populates="attempts")


class DailyActivityLimit(Base):
    __tablename__ = "daily_activity_limits"
    __table_args__ = (
        CheckConstraint("points_earned >= 0", name="ck_daily_activity_limits_points_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
