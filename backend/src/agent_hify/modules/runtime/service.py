from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from agent_hify.core.db import SessionLocal
from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import AppError, NotFoundError, ValidationError
from agent_hify.core.pagination import CursorPage, decode_cursor, encode_cursor
from agent_hify.modules.apps import service as apps_service
from agent_hify.modules.apps.schemas import AppConfigChat
from agent_hify.modules.knowledge import service as knowledge_service
from agent_hify.modules.knowledge.schemas import RetrievedChunk
from agent_hify.modules.models import service as models_service
from agent_hify.modules.observability import service as obs_service
from agent_hify.modules.observability.schemas import TraceIn
from agent_hify.modules.runtime import repository
from agent_hify.modules.runtime.models import Conversation, Message
from agent_hify.modules.runtime.schemas import ChatInput, ConversationOut, MessageOut

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _text_of(content: list[dict[str, object]]) -> str:
    return "".join(
        str(part.get("text", ""))
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def _title_from(message: str) -> str:
    title = message.strip().splitlines()[0] if message.strip() else "新对话"
    return title[:40]


def list_conversations(
    session: Session,
    app_id: int,
    workspace_id: int,
    cursor: str | None,
    limit: int,
) -> CursorPage[ConversationOut]:
    decoded = decode_cursor(cursor) if cursor else None
    rows = repository.list_conversations(session, app_id, workspace_id, decoded, limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return CursorPage(
        items=[ConversationOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def list_messages(
    session: Session,
    conversation_id: int,
    workspace_id: int,
    cursor: str | None,
    limit: int,
) -> CursorPage[MessageOut]:
    conv = repository.get_conversation(session, conversation_id, workspace_id)
    if conv is None:
        raise NotFoundError(ErrorCode.CONVERSATION_NOT_FOUND, "对话不存在")
    decoded = decode_cursor(cursor) if cursor else None
    rows = repository.list_messages(session, conversation_id, decoded, limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return CursorPage(
        items=[MessageOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def run_chat(
    app_id: int,
    workspace_id: int,
    user_id: int,
    payload: ChatInput,
) -> AsyncGenerator[str, None]:
    """流式对话编排。自建会话（SSE 流出注入会话生命周期），逐段下发 SSE 事件。"""
    session = SessionLocal()
    try:
        app = apps_service.get_app(session, app_id, workspace_id)
        if app.type != "chat":
            raise ValidationError(ErrorCode.PARAM_INVALID, "该应用不是聊天类型")
        config = AppConfigChat.model_validate(app.config)

        if payload.conversation_id is not None:
            conv = repository.get_conversation(session, payload.conversation_id, workspace_id)
            if conv is None:
                raise NotFoundError(ErrorCode.CONVERSATION_NOT_FOUND, "对话不存在")
        else:
            conv = repository.insert_conversation(
                session,
                Conversation(
                    app_id=app_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    title=_title_from(payload.message),
                ),
            )

        repository.insert_message(
            session,
            Message(
                conversation_id=conv.id,
                role="user",
                content=[{"type": "text", "text": payload.message}],
            ),
        )

        history = repository.get_recent_messages(session, conv.id, config.history_limit)
        llm_messages: list[dict[str, str]] = []
        if config.system_prompt:
            llm_messages.append({"role": "system", "content": config.system_prompt})
        for m in history:
            llm_messages.append({"role": m.role, "content": _text_of(m.content)})

        # RAG 检索：kb_ids 非空时 embed 用户消息并检索 context
        retrieved: list[RetrievedChunk] = []
        for kb_id in config.kb_ids:
            try:
                chunks = await knowledge_service.retrieve(
                    session,
                    kb_id=kb_id,
                    workspace_id=workspace_id,
                    query=payload.message,
                )
                retrieved.extend(chunks)
            except Exception as exc:
                logger.warning("RAG retrieve kb_id=%d failed: %s", kb_id, exc)

        if retrieved:
            context_text = "\n\n---\n".join(c.content for c in retrieved)
            rag_msg = {"role": "system", "content": f"参考资料：\n{context_text}"}
            insert_pos = 1 if llm_messages and llm_messages[0]["role"] == "system" else 0
            llm_messages.insert(insert_pos, rag_msg)
            obs_service.record_trace(
                session,
                TraceIn(
                    workspace_id=workspace_id,
                    type="retrieval",
                    status="ok",
                    app_id=app_id,
                    conversation_id=conv.id,
                    input={"query": payload.message, "kb_ids": list(config.kb_ids)},
                    output={"chunk_count": len(retrieved)},
                ),
            )

        extra_params: dict[str, object] = dict(config.params)
        usage_sink: dict[str, object] = {}
        parts: list[str] = []
        started = time.monotonic()
        async for delta in models_service.invoke_stream(
            session,
            model_id=config.model_id,
            messages=llm_messages,
            usage_sink=usage_sink,
            extra_params=extra_params,
        ):
            parts.append(delta)
            yield _sse("message", {"delta": delta})

        full = "".join(parts)
        latency_ms = int((time.monotonic() - started) * 1000)

        assistant = repository.insert_message(
            session,
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=[{"type": "text", "text": full}],
            ),
        )

        tokens_in = int(str(usage_sink.get("tokens_in") or 0))
        tokens_out = int(str(usage_sink.get("tokens_out") or 0))
        cost = Decimal(str(usage_sink.get("cost", 0) or 0))

        obs_service.record_trace(
            session,
            TraceIn(
                workspace_id=workspace_id,
                type="llm_call",
                status="ok",
                app_id=app_id,
                conversation_id=conv.id,
                message_id=assistant.id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                latency_ms=latency_ms,
                input={"messages": llm_messages},
                output={"content": full},
            ),
        )
        obs_service.record_usage(
            session,
            workspace_id=workspace_id,
            day=datetime.now(UTC).date(),
            model_id=config.model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            app_id=app_id,
        )
        session.commit()

        yield _sse(
            "usage",
            {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost": str(cost)},
        )
        yield _sse("done", {"conversation_id": conv.id, "message_id": assistant.id})
    except AppError as exc:
        session.rollback()
        obs_service.record_trace_committed(
            TraceIn(
                workspace_id=workspace_id,
                type="llm_call",
                status="error",
                app_id=app_id,
                error=exc.message,
            )
        )
        yield _sse("error", {"code": exc.code.value, "message": exc.message})
    except Exception as exc:
        session.rollback()
        obs_service.record_trace_committed(
            TraceIn(
                workspace_id=workspace_id,
                type="llm_call",
                status="error",
                app_id=app_id,
                error=str(exc),
            )
        )
        yield _sse(
            "error",
            {"code": ErrorCode.INTERNAL_ERROR.value, "message": "对话失败"},
        )
    finally:
        session.close()
