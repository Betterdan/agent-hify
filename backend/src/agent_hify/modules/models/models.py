from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, SoftDeleteMixin, TimestampMixin


class ModelProvider(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "model_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class Model(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("model_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_key: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'"), nullable=False
    )
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_params: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'{}'"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
