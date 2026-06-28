from __future__ import annotations

import random
from datetime import date

import pytest

from agent_hify.core.db import SessionLocal
from agent_hify.modules.observability import service
from agent_hify.modules.observability.schemas import TraceIn


@pytest.mark.integration
def test_record_trace_and_list() -> None:
    with SessionLocal() as s:
        tid = service.record_trace(
            s,
            TraceIn(
                workspace_id=1,
                type="llm_call",
                status="ok",
                tokens_in=10,
                tokens_out=5,
                latency_ms=120,
                input={"q": "hi"},
                output={"a": "hello"},
            ),
        )
        s.commit()
        assert tid > 0
        traces = service.list_traces(s, workspace_id=1, limit=10)
        assert any(t.id == tid for t in traces)


@pytest.mark.integration
def test_record_usage_upsert_accumulates() -> None:
    # 使用随机 model_id 避免跨测试运行的数据累积
    model_id = random.randint(100_000, 999_999)
    with SessionLocal() as s:
        for _ in range(2):
            service.record_usage(
                s,
                workspace_id=1,
                day=date(2026, 6, 27),
                model_id=model_id,
                tokens_in=10,
                tokens_out=4,
                cost=0.001,
            )
        s.commit()
        rows = [
            u
            for u in service.list_usage(s, workspace_id=1)
            if u.model_id == model_id and str(u.day) == "2026-06-27"
        ]
        assert len(rows) == 1
        assert rows[0].tokens_in == 20
        assert rows[0].requests == 2
