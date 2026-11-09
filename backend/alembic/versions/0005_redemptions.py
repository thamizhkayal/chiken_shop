"""Add point reservations, redemption QR tokens, and fulfillment records."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_redemptions"
down_revision: Union[str, None] = "0004_daily_activities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "redemption_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fulfilled_grams", sa.Integer(), nullable=True),
        sa.Column("fulfilled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("points >= 100", name="ck_redemption_requests_minimum_points"),
        sa.CheckConstraint(
            "fulfilled_grams IS NULL OR (fulfilled_grams > 0 AND fulfilled_grams <= points)",
            name="ck_redemption_requests_fulfilled_grams",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RESERVED', 'FULFILLED', 'EXPIRED', 'CANCELLED')",
            name="ck_redemption_requests_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fulfilled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_redemption_requests_user_idempotency"),
    )
    op.create_index("ix_redemption_requests_user_id", "redemption_requests", ["user_id"])
    op.create_index("ix_redemption_requests_expires_at", "redemption_requests", ["expires_at"])
    op.create_index("ix_redemption_requests_user_created", "redemption_requests", ["user_id", "created_at"])
    op.create_index("ix_redemption_requests_status_expiry", "redemption_requests", ["status", "expires_at"])

    op.create_table(
        "redemption_qr_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("redemption_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["redemption_id"], ["redemption_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_redemption_qr_tokens_redemption_id", "redemption_qr_tokens", ["redemption_id"])
    op.create_index("ix_redemption_qr_tokens_expires_at", "redemption_qr_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_redemption_qr_tokens_expires_at", table_name="redemption_qr_tokens")
    op.drop_index("ix_redemption_qr_tokens_redemption_id", table_name="redemption_qr_tokens")
    op.drop_table("redemption_qr_tokens")
    op.drop_index("ix_redemption_requests_status_expiry", table_name="redemption_requests")
    op.drop_index("ix_redemption_requests_user_created", table_name="redemption_requests")
    op.drop_index("ix_redemption_requests_expires_at", table_name="redemption_requests")
    op.drop_index("ix_redemption_requests_user_id", table_name="redemption_requests")
    op.drop_table("redemption_requests")
