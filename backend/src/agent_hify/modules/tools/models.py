from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, TimestampMixin


class Tool(Base, TimestampMixin):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("workspaces.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Python attribute "tool_schema" → DB column "schema" (avoids SQLAlchemy Table.schema clash)
    tool_schema: Mapped[dict[str, Any]] = mapped_column(
        "schema", JSONB, nullable=False, default=dict
    )
    credentials_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
