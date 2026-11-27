"""api keys for service accounts (public API, MCP server)

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_key",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("permissions", sa.String(400), nullable=False),
        sa.Column("scope_all", sa.Boolean(), nullable=False),
        sa.Column("warehouses", sa.String(2000), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_api_key_tenant_id", "api_key", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_api_key_tenant_id", table_name="api_key")
    op.drop_table("api_key")
