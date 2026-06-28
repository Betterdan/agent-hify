from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatInput(BaseModel):
    conversation_id: int | None = None
    message: str


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    app_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: list[dict[str, object]]
    created_at: datetime
