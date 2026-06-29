from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TraceIn(BaseModel):
    workspace_id: int
    type: str
    status: str
    app_id: int | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: Decimal = Decimal(0)
    latency_ms: int = 0
    input: dict[str, object] | None = None
    output: dict[str, object] | None = None
    error: str | None = None


class TraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    app_id: int | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    tokens_in: int
    tokens_out: int
    cost: Decimal
    latency_ms: int
    error: str | None = None
    created_at: datetime


class UsageDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    app_id: int | None
    model_id: int | None
    tokens_in: int
    tokens_out: int
    cost: Decimal
    requests: int


class AnnotationIn(BaseModel):
    message_id: int
    rating: Annotated[int, Field(ge=-1, le=1)]
    comment: str | None = None


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    rating: int
    comment: str | None
    created_at: datetime


class EvalHookIn(BaseModel):
    name: str
    payload: dict[str, object] = {}
