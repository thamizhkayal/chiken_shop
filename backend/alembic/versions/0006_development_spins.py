"""Allow multiple daily spin records for development testing."""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_development_spins"
down_revision: Union[str, None] = "0005_redemptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spin_sessions") as batch_op:
        batch_op.drop_constraint("uq_spin_sessions_user_business_date", type_="unique")
        batch_op.create_index(
            "ix_spin_sessions_user_business_date",
            ["user_id", "business_date"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("spin_sessions") as batch_op:
        batch_op.drop_index("ix_spin_sessions_user_business_date")
        batch_op.create_unique_constraint(
            "uq_spin_sessions_user_business_date",
            ["user_id", "business_date"],
        )
