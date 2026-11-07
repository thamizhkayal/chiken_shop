"""Add wallets and immutable transaction ledger."""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0002_wallet_ledger"
down_revision: Union[str, None] = "0001_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRANSACTION_TYPES = (
    "spin_reward",
    "puzzle_reward",
    "admin_adjustment",
    "redemption_reservation",
    "redemption_completion",
    "redemption_cancellation",
    "expiry",
)


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("balance_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance_points >= 0", name="ck_wallets_non_negative_balance"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    bind = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Uuid()))
    wallets = sa.table(
        "wallets",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("balance_points", sa.Integer()),
    )
    for (user_id,) in bind.execute(sa.select(users.c.id)):
        bind.execute(
            wallets.insert().values(id=uuid4(), user_id=user_id, balance_points=0)
        )

    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN (" + ", ".join(f"'{value}'" for value in TRANSACTION_TYPES) + ")",
            name="ck_wallet_transactions_type",
        ),
        sa.CheckConstraint(
            "points_delta != 0 OR transaction_type = 'redemption_completion'",
            name="ck_wallet_transactions_nonzero_delta",
        ),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_type", "reference_id", name="uq_wallet_transactions_reference"),
    )
    op.create_index("ix_wallet_transactions_wallet_id", "wallet_transactions", ["wallet_id"])
    op.create_index("ix_wallet_transactions_user_id", "wallet_transactions", ["user_id"])
    op.create_index(
        "ix_wallet_transactions_user_created",
        "wallet_transactions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_transactions_user_created", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_user_id", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_wallet_id", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")
    op.drop_table("wallets")
