from __future__ import annotations

from typing import Any

import httpx

from agent_hify.modules.tools.protocol import ToolResult, ToolSpec

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 30.0


class ApiTool:
    """HTTP-based tool. config: {url, method, headers, description}; credential: Bearer token."""

    def __init__(
        self,
        name: str,
        schema: dict[str, Any],
        config: dict[str, Any],
        credential: str | None,
    ) -> None:
        self._name = name
        self._schema = schema
        self._config = config
        self._credential = credential

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self._name,
            description=self._config.get("description", f"HTTP API tool: {self._name}"),
            parameters=self._schema,
        )

    async def call(self, args: dict[str, Any]) -> ToolResult:
        url: str = self._config["url"]
        method: str = self._config.get("method", "POST").upper()
        headers: dict[str, str] = dict(self._config.get("headers", {}))
        if self._credential:
            headers["Authorization"] = f"Bearer {self._credential}"

        timeout = httpx.Timeout(
            connect=_CONNECT_TIMEOUT,
            read=_READ_TIMEOUT,
            write=_READ_TIMEOUT,
            pool=5.0,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url, params=args, headers=headers)
                else:
                    resp = await client.post(url, json=args, headers=headers)
            resp.raise_for_status()
            return ToolResult(content=resp.text)
        except httpx.TimeoutException as exc:
            return ToolResult(content="", is_error=True, error=f"Timeout: {exc}")
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                content="",
                is_error=True,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return ToolResult(content="", is_error=True, error=str(exc))
