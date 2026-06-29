"""annotations + eval_events

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),  # -1=down, 0=neutral, 1=up
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_annotations_message_id", "annotations", ["message_id"])
    op.create_index("ix_annotations_workspace_id", "annotations", ["workspace_id"])
    op.create_index(
        "uq_annotations_workspace_message",
        "annotations",
        ["workspace_id", "message_id"],
        unique=True,
    )

    op.create_table(
        "eval_events",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_eval_events_name", "eval_events", ["name"])


def downgrade() -> None:
    op.drop_table("eval_events")
    op.drop_table("annotations")
