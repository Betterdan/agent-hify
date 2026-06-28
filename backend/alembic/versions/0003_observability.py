from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traces",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("conversation_id", sa.BigInteger, nullable=True),
        sa.Column("message_id", sa.BigInteger, nullable=True),
        sa.Column("app_id", sa.BigInteger, nullable=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("tokens_in", sa.Integer, server_default="0", nullable=False),
        sa.Column("tokens_out", sa.Integer, server_default="0", nullable=False),
        sa.Column("cost", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("error", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('llm_call','tool_call','retrieval','agent_step')",
            name="ck_traces_type",
        ),
    )
    # 列序匹配查询 select_traces: WHERE workspace_id=? ORDER BY created_at DESC, id DESC。
    # app_id 不作过滤条件，不放进复合索引前缀，否则无法支撑该排序。
    op.create_index(
        "ix_traces_ws_created",
        "traces",
        ["workspace_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )

    op.create_table(
        "usage_daily",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("app_id", sa.BigInteger, nullable=True),
        sa.Column("model_id", sa.BigInteger, nullable=True),
        sa.Column("tokens_in", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("tokens_out", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("cost", sa.Numeric(14, 6), server_default="0", nullable=False),
        sa.Column("requests", sa.Integer, server_default="0", nullable=False),
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
    op.execute(
        "CREATE UNIQUE INDEX uq_usage_daily_dim ON usage_daily "
        "(workspace_id, day, app_id, model_id) NULLS NOT DISTINCT"
    )


def downgrade() -> None:
    op.drop_table("usage_daily")
    op.drop_table("traces")
