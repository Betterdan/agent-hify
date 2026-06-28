from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, TimestampMixin


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    input: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UsageDaily(Base, TimestampMixin):
    __tablename__ = "usage_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tokens_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=0, nullable=False)
    requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
