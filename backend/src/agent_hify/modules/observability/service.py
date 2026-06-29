from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from agent_hify.core.db import SessionLocal
from agent_hify.core.logging import get_logger
from agent_hify.modules.observability import repository
from agent_hify.modules.observability.annotation_models import Annotation, EvalEvent
from agent_hify.modules.observability.models import Trace
from agent_hify.modules.observability.schemas import (
    AnnotationIn,
    AnnotationOut,
    EvalHookIn,
    TraceIn,
    TraceOut,
    UsageDailyOut,
)

logger = get_logger("agent_hify.observability")


def record_trace(session: Session, data: TraceIn) -> int:
    trace = Trace(
        workspace_id=data.workspace_id,
        type=data.type,
        status=data.status,
        app_id=data.app_id,
        conversation_id=data.conversation_id,
        message_id=data.message_id,
        tokens_in=data.tokens_in,
        tokens_out=data.tokens_out,
        cost=data.cost,
        latency_ms=data.latency_ms,
        input=data.input,
        output=data.output,
        error=data.error,
    )
    return repository.insert_trace(session, trace)


def record_trace_committed(data: TraceIn) -> int:
    """在独立会话中写入并提交一条 trace。

    用于即便业务事务回滚也须留痕的场景（如失败的外部调用）：失败请求的会话会被
    回滚，错误 trace 若写在同一会话里会一并丢失，故另开会话单独提交。
    """
    with SessionLocal() as s:
        tid = record_trace(s, data)
        s.commit()
        return tid


def record_usage(
    session: Session,
    *,
    workspace_id: int,
    day: date,
    model_id: int | None,
    tokens_in: int,
    tokens_out: int,
    cost: Decimal | float,
    app_id: int | None = None,
    requests: int = 1,
) -> None:
    repository.upsert_usage(
        session,
        workspace_id=workspace_id,
        day=day,
        app_id=app_id,
        model_id=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=Decimal(str(cost)),
        requests=requests,
    )


def list_traces(
    session: Session,
    workspace_id: int,
    limit: int = 100,
    app_id: int | None = None,
    status: str | None = None,
    days: int = 7,
) -> list[TraceOut]:
    return [
        TraceOut.model_validate(t)
        for t in repository.select_traces(
            session, workspace_id, limit=limit, app_id=app_id, status=status, days=days
        )
    ]


def list_usage(session: Session, workspace_id: int) -> list[UsageDailyOut]:
    return [UsageDailyOut.model_validate(u) for u in repository.select_usage(session, workspace_id)]


def annotate(session: Session, workspace_id: int, data: AnnotationIn) -> AnnotationOut:
    ann = Annotation(
        workspace_id=workspace_id,
        message_id=data.message_id,
        rating=data.rating,
        comment=data.comment,
    )
    saved = repository.upsert_annotation(session, ann)
    return AnnotationOut.model_validate(saved)


def get_annotations(session: Session, workspace_id: int, message_id: int) -> list[AnnotationOut]:
    return [
        AnnotationOut.model_validate(a)
        for a in repository.select_annotations(session, workspace_id, message_id)
    ]


def run_eval_hook(session: Session, workspace_id: int, data: EvalHookIn) -> int:
    """评估钩子：记录触发事件。具体评估指标由项目所有者扩展（见 METHODOLOGY.md）。"""
    logger.info('{"eval_hook": "%s", "payload_keys": %s}', data.name, list(data.payload.keys()))
    ev = EvalEvent(workspace_id=workspace_id, name=data.name, payload=dict(data.payload))
    return repository.insert_eval_event(session, ev)
