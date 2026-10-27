"""audit_event table

Revision ID: 0001
Revises:
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("dataset", sa.String(64)),
        sa.Column("fields", sa.String(1000)),
        sa.Column("decision", sa.String(8), nullable=False),
        sa.Column("reason_code", sa.String(64)),
        sa.Column("row_count", sa.Integer()),
        sa.Column("duration_ms", sa.Float()),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_audit_event_occurred_at", "audit_event", ["occurred_at"])
    op.create_index("ix_audit_event_tenant_id", "audit_event", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_tenant_id", table_name="audit_event")
    op.drop_index("ix_audit_event_occurred_at", table_name="audit_event")
    op.drop_table("audit_event")
