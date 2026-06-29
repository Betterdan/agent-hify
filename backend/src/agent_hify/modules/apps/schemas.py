from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

AppType = Literal["chat", "agent"]


class AppConfigChat(BaseModel):
    model_id: int
    system_prompt: str = ""
    params: dict[str, object] = Field(
        default_factory=lambda: cast("dict[str, object]", {"temperature": 0.7, "max_tokens": 2048})
    )
    history_limit: int = 20
    kb_ids: list[int] = Field(default_factory=list)
    tool_ids: list[int] = Field(default_factory=list)


class AppCreate(BaseModel):
    type: AppType = "chat"
    name: str
    config: AppConfigChat


class AppUpdate(BaseModel):
    name: str | None = None
    config: AppConfigChat | None = None
    status: Literal["draft", "published"] | None = None


class AppOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    config: dict[str, object]
    status: str
    created_at: datetime
    updated_at: datetime
