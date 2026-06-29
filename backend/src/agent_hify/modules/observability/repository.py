from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from agent_hify.modules.observability.annotation_models import Annotation, EvalEvent
from agent_hify.modules.observability.models import Trace, UsageDaily


def insert_trace(session: Session, trace: Trace) -> int:
    session.add(trace)
    session.flush()
    return int(trace.id)


def select_traces(
    session: Session,
    workspace_id: int,
    limit: int = 100,
    app_id: int | None = None,
    status: str | None = None,
    days: int = 7,
) -> list[Trace]:
    since = datetime.now(UTC) - timedelta(days=days)
    stmt = select(Trace).where(
        Trace.workspace_id == workspace_id,
        Trace.created_at >= since,
    )
    if app_id is not None:
        stmt = stmt.where(Trace.app_id == app_id)
    if status is not None:
        stmt = stmt.where(Trace.status == status)
    stmt = stmt.order_by(desc(Trace.created_at), desc(Trace.id)).limit(limit)
    return list(session.execute(stmt).scalars().all())


def upsert_annotation(session: Session, ann: Annotation) -> Annotation:
    now = datetime.now(UTC)
    stmt = (
        pg_insert(Annotation)
        .values(
            workspace_id=ann.workspace_id,
            message_id=ann.message_id,
            rating=ann.rating,
            comment=ann.comment,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["workspace_id", "message_id"],
            set_={
                "rating": ann.rating,
                "comment": ann.comment,
                "updated_at": now,
            },
        )
        .returning(Annotation)
    )
    return session.execute(stmt).scalar_one()


def select_annotations(session: Session, workspace_id: int, message_id: int) -> list[Annotation]:
    stmt = select(Annotation).where(
        Annotation.workspace_id == workspace_id,
        Annotation.message_id == message_id,
    )
    return list(session.execute(stmt).scalars().all())


def insert_eval_event(session: Session, ev: EvalEvent) -> int:
    session.add(ev)
    session.flush()
    return int(ev.id)


def upsert_usage(
    session: Session,
    *,
    workspace_id: int,
    day: date,
    app_id: int | None,
    model_id: int | None,
    tokens_in: int,
    tokens_out: int,
    cost: Decimal,
    requests: int,
) -> None:
    stmt = pg_insert(UsageDaily).values(
        workspace_id=workspace_id,
        day=day,
        app_id=app_id,
        model_id=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        requests=requests,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "day", "app_id", "model_id"],
        set_={
            "tokens_in": UsageDaily.tokens_in + stmt.excluded.tokens_in,
            "tokens_out": UsageDaily.tokens_out + stmt.excluded.tokens_out,
            "cost": UsageDaily.cost + stmt.excluded.cost,
            "requests": UsageDaily.requests + stmt.excluded.requests,
        },
    )
    session.execute(stmt)


def select_usage(session: Session, workspace_id: int) -> list[UsageDaily]:
    stmt = select(UsageDaily).where(UsageDaily.workspace_id == workspace_id)
    return list(session.execute(stmt).scalars().all())
