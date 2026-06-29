from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    error: str | None = None


class Tool(Protocol):
    def spec(self) -> ToolSpec: ...
    async def call(self, args: dict[str, Any]) -> ToolResult: ...
