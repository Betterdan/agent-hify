from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_hify.modules.tools.protocol import ToolResult, ToolSpec

__all__ = ["ToolCreate", "ToolUpdate", "ToolOut", "ToolSpec", "ToolResult"]


class ToolCreate(BaseModel):
    type: str  # builtin|api|mcp
    name: str
    tool_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")
    credentials: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    model_config = ConfigDict(populate_by_name=True)


class ToolUpdate(BaseModel):
    name: str | None = None
    tool_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    credentials: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None

    model_config = ConfigDict(populate_by_name=True)


class ToolOut(BaseModel):
    id: int
    workspace_id: int
    type: str
    name: str
    tool_schema: dict[str, Any] = Field(alias="schema")
    config: dict[str, Any]
    enabled: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
