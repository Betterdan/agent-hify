"""knowledge_bases, documents, chunks

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "embedding_model_id",
            sa.BigInteger,
            sa.ForeignKey("models.id"),
            nullable=False,
        ),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    )
    op.create_index("ix_knowledge_bases_workspace_id", "knowledge_bases", ["workspace_id"])
    op.create_index(
        "ix_knowledge_bases_embedding_model_id", "knowledge_bases", ["embedding_model_id"]
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_knowledge_bases_workspace_name "
        "ON knowledge_bases(workspace_id, name) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "kb_id",
            sa.BigInteger,
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            sa.CheckConstraint("status IN ('pending','processing','done','failed')"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("char_count", sa.Integer, nullable=False, server_default="0"),
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
    )
    op.create_index("ix_documents_kb_id", "documents", ["kb_id"])
    op.create_index("ix_documents_kb_id_status", "documents", ["kb_id", "status"])

    # chunks 用原生 SQL 建（pgvector vector 类型需 raw SQL）
    op.execute("""
        CREATE TABLE chunks (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            kb_id BIGINT NOT NULL REFERENCES knowledge_bases(id),
            content TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            position INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_kb_id", "chunks", ["kb_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.drop_table("documents")
    op.drop_index("uq_knowledge_bases_workspace_name", "knowledge_bases")
    op.drop_table("knowledge_bases")
