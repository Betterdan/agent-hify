from __future__ import annotations

import asyncio
from typing import Any

from agent_hify.modules.tools.protocol import ToolResult, ToolSpec

_MCP_TIMEOUT = 30.0


class McpTool:
    """MCP-based tool via stdio subprocess. config: {command, args, tool_name, description}"""

    def __init__(self, name: str, schema: dict[str, Any], config: dict[str, Any]) -> None:
        self._name = name
        self._schema = schema
        self._config = config

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self._name,
            description=self._config.get("description", f"MCP tool: {self._name}"),
            parameters=self._schema,
        )

    async def call(self, args: dict[str, Any]) -> ToolResult:
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client
        except ImportError:
            return ToolResult(content="", is_error=True, error="mcp SDK not available")

        command: str = self._config["command"]
        cmd_args: list[str] = self._config.get("args", [])
        tool_name: str = self._config.get("tool_name", self._name)

        server_params = StdioServerParameters(command=command, args=cmd_args)
        try:
            async with asyncio.timeout(_MCP_TIMEOUT):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, args)
                        content_text = " ".join(
                            c.text for c in result.content if hasattr(c, "text")
                        )
                        return ToolResult(content=content_text, is_error=result.isError)
        except TimeoutError:
            return ToolResult(content="", is_error=True, error="MCP call timed out")
        except Exception as exc:
            return ToolResult(content="", is_error=True, error=str(exc))
