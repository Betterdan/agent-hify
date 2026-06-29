from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.tools.models import Tool


def get_tool(session: Session, tool_id: int, workspace_id: int) -> Tool | None:
    return session.scalar(
        select(Tool).where(Tool.id == tool_id, Tool.workspace_id == workspace_id)
    )


def list_tools(session: Session, workspace_id: int) -> list[Tool]:
    return list(
        session.scalars(
            select(Tool).where(Tool.workspace_id == workspace_id).order_by(Tool.id)
        )
    )


def create_tool(session: Session, tool: Tool) -> Tool:
    session.add(tool)
    session.flush()
    session.refresh(tool)
    return tool


def update_tool(session: Session, tool: Tool, **kwargs: object) -> Tool:
    for k, v in kwargs.items():
        setattr(tool, k, v)
    session.flush()
    session.refresh(tool)
    return tool


def delete_tool(session: Session, tool: Tool) -> None:
    session.delete(tool)
    session.flush()
