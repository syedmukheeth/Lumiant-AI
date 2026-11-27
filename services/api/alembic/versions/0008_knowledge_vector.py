"""knowledge vectors: lasting cache of embedding vectors for knowledge search

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_vector",
        sa.Column("text_hash", sa.String(64), primary_key=True),  # sha256 of model|dims|text
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("dims", sa.Integer(), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),  # base64 of little-endian float32
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("knowledge_vector")
