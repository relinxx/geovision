"""create saved maps table

Revision ID: 0002_create_saved_maps_table
Revises: 0001_create_users_table
Create Date: 2026-04-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_create_saved_maps_table"
down_revision = "0001_create_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("saved_maps"):
        return

    op.create_table(
        "saved_maps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parcel_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_plan_rank", sa.Integer(), nullable=True),
        sa.Column("input_parcels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("optimization_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index("ix_saved_maps_user_id", "saved_maps", ["user_id"])
    op.create_index("ix_saved_maps_created_at", "saved_maps", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_saved_maps_created_at", table_name="saved_maps")
    op.drop_index("ix_saved_maps_user_id", table_name="saved_maps")
    op.drop_table("saved_maps")