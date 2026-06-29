from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.security import decrypt, encrypt
from agent_hify.modules.tools import repository
from agent_hify.modules.tools.api_tool import ApiTool
from agent_hify.modules.tools.builtin_tools import get_builtin
from agent_hify.modules.tools.mcp_tool import McpTool
from agent_hify.modules.tools.models import Tool as ToolModel
from agent_hify.modules.tools.protocol import ToolResult, ToolSpec
from agent_hify.modules.tools.schemas import ToolCreate, ToolOut, ToolUpdate


def _to_out(tool: ToolModel) -> ToolOut:
    return ToolOut(
        id=tool.id,
        workspace_id=tool.workspace_id,
        type=tool.type,
        name=tool.name,
        schema=tool.tool_schema,  # alias "schema" used for construction (populate_by_name=True)
        config=tool.config,
        enabled=tool.enabled,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )


def _require_tool(session: Session, tool_id: int, workspace_id: int) -> ToolModel:
    from agent_hify.core.exceptions import NotFoundError

    tool = repository.get_tool(session, tool_id, workspace_id)
    if tool is None:
        raise NotFoundError(ErrorCode.TOOL_NOT_FOUND, f"tool {tool_id} not found")
    return tool


def list_tools(session: Session, workspace_id: int) -> list[ToolOut]:
    return [_to_out(t) for t in repository.list_tools(session, workspace_id)]


def get_tool_out(session: Session, tool_id: int, workspace_id: int) -> ToolOut:
    return _to_out(_require_tool(session, tool_id, workspace_id))


def create_tool(session: Session, workspace_id: int, body: ToolCreate) -> ToolOut:
    cred_bytes: bytes | None = None
    if body.credentials:
        cred_bytes = encrypt(body.credentials)
    tool = ToolModel(
        workspace_id=workspace_id,
        type=body.type,
        name=body.name,
        tool_schema=body.tool_schema or {},
        config=body.config,
        enabled=body.enabled,
        credentials_encrypted=cred_bytes,
    )
    return _to_out(repository.create_tool(session, tool))


def update_tool(session: Session, tool_id: int, workspace_id: int, body: ToolUpdate) -> ToolOut:
    tool = _require_tool(session, tool_id, workspace_id)
    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.tool_schema is not None:
        updates["tool_schema"] = body.tool_schema
    if body.config is not None:
        updates["config"] = body.config
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.credentials is not None:
        updates["credentials_encrypted"] = encrypt(body.credentials)
    return _to_out(repository.update_tool(session, tool, **updates))


def delete_tool(session: Session, tool_id: int, workspace_id: int) -> None:
    tool = _require_tool(session, tool_id, workspace_id)
    repository.delete_tool(session, tool)


def get_specs(session: Session, tool_ids: list[int], workspace_id: int) -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for tool_id in tool_ids:
        tool = repository.get_tool(session, tool_id, workspace_id)
        if tool is None or not tool.enabled:
            continue
        tool_schema = tool.tool_schema
        if tool.type == "builtin":
            bt = get_builtin(tool.name)
            if bt:
                specs.append(bt.spec())
        elif tool.type == "api":
            credential: str | None = None
            if tool.credentials_encrypted:
                credential = decrypt(tool.credentials_encrypted)
            api = ApiTool(tool.name, tool_schema, tool.config, credential)
            specs.append(api.spec())
        elif tool.type == "mcp":
            mcp = McpTool(tool.name, tool_schema, tool.config)
            specs.append(mcp.spec())
    return specs


async def call_tool(
    session: Session, tool_id: int, workspace_id: int, args: dict[str, Any]
) -> ToolResult:
    from agent_hify.core.exceptions import ValidationError

    tool = _require_tool(session, tool_id, workspace_id)
    if not tool.enabled:
        raise ValidationError(ErrorCode.TOOL_DISABLED, f"tool {tool.name} is disabled")

    tool_schema = tool.tool_schema
    if tool.type == "builtin":
        bt = get_builtin(tool.name)
        if bt is None:
            return ToolResult(
                content="", is_error=True, error=f"Builtin '{tool.name}' not registered"
            )
        return await bt.call(args)
    elif tool.type == "api":
        credential = decrypt(tool.credentials_encrypted) if tool.credentials_encrypted else None
        api = ApiTool(tool.name, tool_schema, tool.config, credential)
        return await api.call(args)
    elif tool.type == "mcp":
        mcp = McpTool(tool.name, tool_schema, tool.config)
        return await mcp.call(args)
    return ToolResult(content="", is_error=True, error=f"Unknown tool type: {tool.type}")
