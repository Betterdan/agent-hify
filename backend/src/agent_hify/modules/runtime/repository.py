from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from agent_hify.modules.runtime.models import Conversation, Message


def insert_conversation(session: Session, conv: Conversation) -> Conversation:
    session.add(conv)
    session.flush()
    return conv


def get_conversation(session: Session, conv_id: int, workspace_id: int) -> Conversation | None:
    stmt = select(Conversation).where(
        Conversation.id == conv_id, Conversation.workspace_id == workspace_id
    )
    return session.execute(stmt).scalar_one_or_none()


def list_conversations(
    session: Session,
    app_id: int,
    workspace_id: int,
    cursor: tuple[datetime, int] | None,
    limit: int,
) -> list[Conversation]:
    stmt = select(Conversation).where(
        Conversation.app_id == app_id, Conversation.workspace_id == workspace_id
    )
    if cursor is not None:
        stmt = stmt.where(tuple_(Conversation.created_at, Conversation.id) < (cursor[0], cursor[1]))
    stmt = stmt.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def insert_message(session: Session, msg: Message) -> Message:
    session.add(msg)
    session.flush()
    return msg


def list_messages(
    session: Session,
    conversation_id: int,
    cursor: tuple[datetime, int] | None,
    limit: int,
) -> list[Message]:
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if cursor is not None:
        stmt = stmt.where(tuple_(Message.created_at, Message.id) > (cursor[0], cursor[1]))
    stmt = stmt.order_by(Message.created_at.asc(), Message.id.asc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_recent_messages(session: Session, conversation_id: int, limit: int) -> list[Message]:
    """取最近 N 条（按时间倒序取，再正序返回），用于拼装上下文。"""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    rows = list(session.execute(stmt).scalars().all())
    rows.reverse()
    return rows
