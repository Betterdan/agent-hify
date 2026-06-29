from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent_hify.modules.tools.protocol import Tool, ToolResult, ToolSpec

_REGISTRY: dict[str, Tool] = {}


def _register(tool: Any) -> Any:
    _REGISTRY[tool.spec().name] = tool
    return tool


class _DatetimeTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="datetime",
            description="Returns the current UTC date and time in ISO 8601 format.",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    async def call(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(content=datetime.now(UTC).isoformat())


class _EchoTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="echo",
            description="Returns the input text unchanged. Useful for testing tool integration.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Text to echo back"}},
                "required": ["text"],
            },
        )

    async def call(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(content=str(args.get("text", "")))


_register(_DatetimeTool())
_register(_EchoTool())


def get_builtin(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def list_builtins() -> list[ToolSpec]:
    return [t.spec() for t in _REGISTRY.values()]
