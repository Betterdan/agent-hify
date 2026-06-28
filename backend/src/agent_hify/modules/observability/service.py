from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from agent_hify.core.db import SessionLocal
from agent_hify.core.logging import get_logger
from agent_hify.modules.observability import repository
from agent_hify.modules.observability.models import Trace
from agent_hify.modules.observability.schemas import TraceIn, TraceOut, UsageDailyOut

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


def list_traces(session: Session, workspace_id: int, limit: int = 50) -> list[TraceOut]:
    return [
        TraceOut.model_validate(t) for t in repository.select_traces(session, workspace_id, limit)
    ]


def list_usage(session: Session, workspace_id: int) -> list[UsageDailyOut]:
    return [UsageDailyOut.model_validate(u) for u in repository.select_usage(session, workspace_id)]


def run_eval_hook(name: str, payload: dict[str, object]) -> None:
    """评估钩子占位：具体评估方法/指标由项目所有者定义（见 METHODOLOGY.md）。当前仅记录。"""
    logger.info('{"eval_hook": "%s", "payload_keys": %s}', name, list(payload.keys()))
