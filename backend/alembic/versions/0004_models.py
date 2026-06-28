from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_providers",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("base_url", sa.String, nullable=True),
        sa.Column("credentials_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "type IN ('openai','anthropic','ollama','openai_compatible')",
            name="ck_provider_type",
        ),
    )
    op.create_index("ix_providers_workspace", "model_providers", ["workspace_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_providers_workspace_name ON model_providers "
        "(workspace_id, name) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "models",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column(
            "provider_id",
            sa.BigInteger,
            sa.ForeignKey("model_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_key", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("embedding_dim", sa.Integer, nullable=True),
        sa.Column("default_params", JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("type IN ('llm','embedding','rerank')", name="ck_model_type"),
    )
    op.create_index("ix_models_provider", "models", ["provider_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_models_provider_key ON models "
        "(provider_id, model_key) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_table("models")
    op.drop_table("model_providers")
