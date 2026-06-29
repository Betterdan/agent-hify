"""tools table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "type",
            sa.Text,
            sa.CheckConstraint("type IN ('builtin','api','mcp')"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("schema", JSONB, nullable=False, server_default="{}"),
        sa.Column("credentials_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", "name", name="uq_tools_workspace_name"),
    )
    op.create_index("ix_tools_workspace_id", "tools", ["workspace_id"])
    op.create_index("ix_tools_workspace_id_type", "tools", ["workspace_id", "type"])


def downgrade() -> None:
    op.drop_index("ix_tools_workspace_id_type", "tools")
    op.drop_index("ix_tools_workspace_id", "tools")
    op.drop_table("tools")
