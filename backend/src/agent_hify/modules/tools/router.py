from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.tools import service
from agent_hify.modules.tools.schemas import ToolCreate, ToolOut, ToolUpdate

router = APIRouter(prefix="/tools", tags=["tools"])

CurrentUser = Annotated[UserOut, Depends(get_current_user)]
Sess = Annotated[Session, Depends(get_session)]


@router.get("", response_model=ApiResponse[list[ToolOut]])
def list_tools(current: CurrentUser, session: Sess) -> ApiResponse[list[ToolOut]]:
    return ApiResponse.ok(service.list_tools(session, current.workspace_id))


@router.get("/{tool_id}", response_model=ApiResponse[ToolOut])
def get_tool(tool_id: int, current: CurrentUser, session: Sess) -> ApiResponse[ToolOut]:
    return ApiResponse.ok(service.get_tool_out(session, tool_id, current.workspace_id))


@router.post("", response_model=ApiResponse[ToolOut])
def create_tool(body: ToolCreate, current: CurrentUser, session: Sess) -> ApiResponse[ToolOut]:
    out = service.create_tool(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(out)


@router.patch("/{tool_id}", response_model=ApiResponse[ToolOut])
def update_tool(
    tool_id: int, body: ToolUpdate, current: CurrentUser, session: Sess
) -> ApiResponse[ToolOut]:
    out = service.update_tool(session, tool_id, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(out)


@router.delete("/{tool_id}", response_model=ApiResponse[None])
def delete_tool(tool_id: int, current: CurrentUser, session: Sess) -> ApiResponse[None]:
    service.delete_tool(session, tool_id, current.workspace_id)
    session.commit()
    return ApiResponse.ok(None)
