"""scheduled alert rules: interval and the creator's rights snapshot

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alert_rule") as batch:
        batch.add_column(sa.Column("every_hours", sa.Integer()))
        batch.add_column(sa.Column("permissions", sa.String(400), nullable=False, server_default=""))
        batch.add_column(sa.Column("scope_all", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("warehouses", sa.String(2000), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("alert_rule") as batch:
        batch.drop_column("warehouses")
        batch.drop_column("scope_all")
        batch.drop_column("permissions")
        batch.drop_column("every_hours")
