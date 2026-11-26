"""alert rules with signed webhooks

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rule",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("min_severity", sa.String(16), nullable=False),
        sa.Column("secret_cipher", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(120)),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_alert_rule_tenant_id", "alert_rule", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_rule_tenant_id", table_name="alert_rule")
    op.drop_table("alert_rule")
