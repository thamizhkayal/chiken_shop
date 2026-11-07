"""Allow daily login rewards in the wallet ledger."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_daily_login_reward"
down_revision: Union[str, None] = "0002_wallet_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRANSACTION_TYPES = (
    "daily_login_reward",
    "spin_reward",
    "puzzle_reward",
    "admin_adjustment",
    "redemption_reservation",
    "redemption_completion",
    "redemption_cancellation",
    "expiry",
)

PREVIOUS_TRANSACTION_TYPES = tuple(
    transaction_type for transaction_type in TRANSACTION_TYPES if transaction_type != "daily_login_reward"
)


def _update_transaction_type_constraint(transaction_types: tuple[str, ...]) -> None:
    allowed_types = ", ".join(f"'{transaction_type}'" for transaction_type in transaction_types)
    with op.batch_alter_table("wallet_transactions") as batch_op:
        batch_op.drop_constraint("ck_wallet_transactions_type", type_="check")
        batch_op.create_check_constraint(
            "ck_wallet_transactions_type",
            f"transaction_type IN ({allowed_types})",
        )


def upgrade() -> None:
    _update_transaction_type_constraint(TRANSACTION_TYPES)


def downgrade() -> None:
    bind = op.get_bind()
    existing_rewards = bind.scalar(
        sa.text(
            "SELECT count(*) FROM wallet_transactions "
            "WHERE transaction_type = 'daily_login_reward'"
        )
    )
    if existing_rewards:
        raise RuntimeError("Cannot remove daily login reward transactions during downgrade")
    _update_transaction_type_constraint(PREVIOUS_TRANSACTION_TYPES)
