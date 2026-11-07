"""Add configurable spin rewards and daily puzzles."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_daily_activities"
down_revision: Union[str, None] = "0003_daily_login_reward"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spin_configurations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("puzzle_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("daily_activity_cap", sa.Integer(), server_default="20", nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("daily_activity_cap >= 1", name="ck_spin_configurations_daily_cap_positive"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "spin_reward_options",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("configuration_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("probability_basis_points", sa.Integer(), nullable=False),
        sa.CheckConstraint("points >= 0", name="ck_spin_reward_options_points_non_negative"),
        sa.CheckConstraint(
            "probability_basis_points > 0 AND probability_basis_points <= 10000",
            name="ck_spin_reward_options_probability",
        ),
        sa.ForeignKeyConstraint(["configuration_id"], ["spin_configurations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("configuration_id", "points", name="uq_spin_reward_options_reward"),
    )
    op.create_index("ix_spin_reward_options_configuration_id", "spin_reward_options", ["configuration_id"])

    op.create_table(
        "spin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column("probability_basis_points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("reward_points >= 0", name="ck_spin_sessions_reward_non_negative"),
        sa.CheckConstraint("probability_basis_points > 0", name="ck_spin_sessions_probability_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "business_date", name="uq_spin_sessions_user_business_date"),
    )
    op.create_index("ix_spin_sessions_user_id", "spin_sessions", ["user_id"])

    op.create_table(
        "puzzle_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column("answer_hash", sa.String(length=64), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("reward_points > 0", name="ck_puzzle_questions_reward_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_date", name="uq_puzzle_questions_business_date"),
    )

    op.create_table(
        "puzzle_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("points_awarded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("points_awarded >= 0", name="ck_puzzle_attempts_award_non_negative"),
        sa.ForeignKeyConstraint(["question_id"], ["puzzle_questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "user_id", name="uq_puzzle_attempts_question_user"),
    )
    op.create_index("ix_puzzle_attempts_question_id", "puzzle_attempts", ["question_id"])
    op.create_index("ix_puzzle_attempts_user_id", "puzzle_attempts", ["user_id"])

    op.create_table(
        "daily_activity_limits",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("points_earned", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("points_earned >= 0", name="ck_daily_activity_limits_points_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "business_date"),
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])

    configuration = sa.table(
        "spin_configurations",
        sa.column("id", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("puzzle_enabled", sa.Boolean()),
        sa.column("daily_activity_cap", sa.Integer()),
    )
    reward_options = sa.table(
        "spin_reward_options",
        sa.column("configuration_id", sa.Integer()),
        sa.column("points", sa.Integer()),
        sa.column("probability_basis_points", sa.Integer()),
    )
    bind = op.get_bind()
    bind.execute(
        configuration.insert().values(
            id=1,
            enabled=True,
            puzzle_enabled=True,
            daily_activity_cap=20,
        )
    )
    bind.execute(
        reward_options.insert(),
        [
            {"configuration_id": 1, "points": 1, "probability_basis_points": 5000},
            {"configuration_id": 1, "points": 2, "probability_basis_points": 3000},
            {"configuration_id": 1, "points": 5, "probability_basis_points": 1500},
            {"configuration_id": 1, "points": 10, "probability_basis_points": 500},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_table("daily_activity_limits")
    op.drop_index("ix_puzzle_attempts_user_id", table_name="puzzle_attempts")
    op.drop_index("ix_puzzle_attempts_question_id", table_name="puzzle_attempts")
    op.drop_table("puzzle_attempts")
    op.drop_table("puzzle_questions")
    op.drop_index("ix_spin_sessions_user_id", table_name="spin_sessions")
    op.drop_table("spin_sessions")
    op.drop_index("ix_spin_reward_options_configuration_id", table_name="spin_reward_options")
    op.drop_table("spin_reward_options")
    op.drop_table("spin_configurations")
