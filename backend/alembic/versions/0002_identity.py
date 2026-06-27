from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT

from agent_hify.core.security import hash_password

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "workspaces",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
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
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.BigInteger,
            sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column("email", CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default="member"),
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
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_users_workspace_email ON users (workspace_id, email) "
        "WHERE deleted_at IS NULL"
    )

    # 种子：default 工作区 + admin 用户
    conn = op.get_bind()
    ws_id = conn.execute(
        sa.text("INSERT INTO workspaces (name) VALUES ('default') RETURNING id")
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO users (workspace_id, email, password_hash, role) "
            "VALUES (:ws, :email, :ph, 'admin')"
        ),
        {"ws": ws_id, "email": "admin@agent-hify.local", "ph": hash_password("admin123")},
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("workspaces")
