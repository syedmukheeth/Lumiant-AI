"""demo requests from the public landing page

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_request",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("company", sa.String(160), nullable=False),
        sa.Column("role", sa.String(120)),
        sa.Column("systems", sa.String(200)),
        sa.Column("message", sa.String(1000)),
    )
    op.create_index("ix_demo_request_received_at", "demo_request", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_demo_request_received_at", table_name="demo_request")
    op.drop_table("demo_request")
