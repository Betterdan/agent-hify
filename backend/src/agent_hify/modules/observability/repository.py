from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from agent_hify.modules.observability.models import Trace, UsageDaily


def insert_trace(session: Session, trace: Trace) -> int:
    session.add(trace)
    session.flush()
    return int(trace.id)


def select_traces(session: Session, workspace_id: int, limit: int) -> list[Trace]:
    stmt = (
        select(Trace)
        .where(Trace.workspace_id == workspace_id)
        .order_by(desc(Trace.created_at), desc(Trace.id))
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


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
