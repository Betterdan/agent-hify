# P0-3 models + observability + 外部调用韧性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 core 外部调用韧性包装、observability 基线（traces / usage_daily / 评估钩子占位）、models 模型网关（厂商与模型注册+凭证加密、LiteLLM 适配、invoke/embed/连通性测试，调用经韧性包装并记 trace/用量），跑通 P0 闭环。

**Architecture:** 在 P0-2（core+identity）之上。`core/external.py` 提供韧性原语（L0）。`observability`（L1，横切，可被上层向下调用）拥有 traces/usage_daily。`models`（L2，依赖 core/identity/observability）通过 LiteLLM 适配器调外部模型，调用经 `core.external` 包装、经 `observability` 记账。P0 无 runtime，故"发起一次 LLM 调用并记账"由 models 的测试用 invoke 端点完成（models 向下调 observability 是允许的）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · LiteLLM（模型网关）· pydantic v2 · pytest（外部调用全部 mock，离线可测）

## Global Constraints

- Python `>=3.12`；文件头 `from __future__ import annotations`；全量类型注解。
- 依赖管理 `uv`；新增 `litellm`；不引入技术栈外依赖。
- Lint `ruff`；类型 `mypy --strict`；测试 `pytest`（**外部模型调用一律 monkeypatch，禁止测试真连外网**）。
- 依赖分层 `import-linter`：observability 仅依赖 core；models 依赖 core/identity/observability。
- 统一响应 `ApiResponse[T]`、**始终 HTTP 200**；错误码见 `core/error_codes.py`（按需新增 models/observability 段）。
- **软删除**：model_providers/models 带 `deleted_at` + 部分唯一索引。
- **凭证不入库明文**：provider 凭证用 `core.security.encrypt` 加密为 bytea。
- **所有外部调用必须经 `core.external.call_with_resilience`**（超时/重试/熔断/隔离）—— CLAUDE.md 编码准则强制。
- 需要 DB 的测试：本机先 `cd deploy && docker compose up -d postgres`，设 `DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify`，并先 `uv run alembic upgrade head`。
- 提交信息用 Conventional Commits。

---

### Task 1: core 外部调用韧性（超时 / 重试 / 熔断 / 隔离）

**Files:**
- Create: `backend/src/agent_hify/core/external.py`
- Create: `backend/tests/core/test_external.py`
- Modify: `backend/src/agent_hify/core/error_codes.py`（已含 19002/19003，无需改；如缺则补）

**Interfaces:**
- Consumes: `core.exceptions`（`ExternalServiceError`/`CircuitOpenError`）、`core.error_codes`。
- Produces:
  - `core.external.CircuitBreaker(fail_threshold:int=5, reset_seconds:float=30.0)`，方法 `allow()->bool`、`record_success()->None`、`record_failure()->None`。
  - `async core.external.call_with_resilience(key:str, fn:Callable[[], Awaitable[T]], *, timeout:float, max_retries:int=2, retry_backoff:float=0.05) -> T`。
    超时/连接失败按可重试处理；超阈值开熔断抛 `CircuitOpenError`；最终失败抛 `ExternalServiceError`。每 `key` 独立熔断器 + 信号量（默认并发 10）。

- [ ] **Step 1: 写失败测试**

`backend/tests/core/test_external.py`:
```python
from __future__ import annotations

import asyncio

import pytest

from agent_hify.core.exceptions import CircuitOpenError, ExternalServiceError
from agent_hify.core.external import CircuitBreaker, call_with_resilience


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(fail_threshold=2, reset_seconds=60)
    assert cb.allow() is True
    cb.record_failure()
    cb.record_failure()
    assert cb.allow() is False  # 已打开


@pytest.mark.asyncio
async def test_retry_then_success() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("boom")
        return "ok"

    out = await call_with_resilience("k1", flaky, timeout=1.0, max_retries=2)
    assert out == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_timeout_raises_external_error() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.2)
        return "late"

    with pytest.raises(ExternalServiceError):
        await call_with_resilience("k2", slow, timeout=0.01, max_retries=0)


@pytest.mark.asyncio
async def test_open_circuit_fast_fails() -> None:
    async def always_fail() -> str:
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ExternalServiceError):
            await call_with_resilience("k3", always_fail, timeout=1.0, max_retries=0)
    with pytest.raises(CircuitOpenError):
        await call_with_resilience("k3", always_fail, timeout=1.0, max_retries=0)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/core/test_external.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

`backend/src/agent_hify/core/external.py`:
```python
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import CircuitOpenError, ExternalServiceError
from agent_hify.core.logging import get_logger

T = TypeVar("T")
logger = get_logger("agent_hify.external")

_RETRYABLE = (ConnectionError, TimeoutError, asyncio.TimeoutError)


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.reset_seconds:
            # 半开：放一个探测
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._opened_at = time.monotonic()


_breakers: dict[str, CircuitBreaker] = {}
_semaphores: dict[str, asyncio.Semaphore] = {}
_MAX_CONCURRENCY = 10


def _breaker(key: str) -> CircuitBreaker:
    return _breakers.setdefault(key, CircuitBreaker())


def _semaphore(key: str) -> asyncio.Semaphore:
    return _semaphores.setdefault(key, asyncio.Semaphore(_MAX_CONCURRENCY))


async def call_with_resilience(
    key: str,
    fn: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    max_retries: int = 2,
    retry_backoff: float = 0.05,
) -> T:
    breaker = _breaker(key)
    if not breaker.allow():
        raise CircuitOpenError(ErrorCode.CIRCUIT_OPEN, f"外部服务熔断中: {key}")

    last_exc: Exception | None = None
    async with _semaphore(key):
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(fn(), timeout=timeout)
                breaker.record_success()
                return result
            except _RETRYABLE as exc:
                last_exc = exc
                breaker.record_failure()
                if attempt < max_retries:
                    await asyncio.sleep(retry_backoff * (2**attempt))
            except Exception as exc:  # 非可重试：直接失败
                breaker.record_failure()
                logger.warning("external call failed (non-retryable): %s", exc)
                raise ExternalServiceError(
                    ErrorCode.EXTERNAL_TIMEOUT, f"外部服务调用失败: {key}"
                ) from exc

    raise ExternalServiceError(
        ErrorCode.EXTERNAL_TIMEOUT, f"外部服务调用失败(重试耗尽): {key}"
    ) from last_exc
```
> 注：`asyncio.wait_for` 超时抛 `asyncio.TimeoutError`，属可重试集合；`max_retries=0` 时直接落到末尾抛 `ExternalServiceError`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/core/test_external.py -v && uv run ruff check . && uv run mypy`
Expected: 4 条 PASSED；ruff/mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add backend/src/agent_hify/core/external.py backend/tests/core/test_external.py
git commit -m "feat: core external-call resilience (timeout/retry/circuit/bulkhead)"
```

---

### Task 2: observability 数据模型 + 迁移（traces / usage_daily）

**Files:**
- Create: `backend/src/agent_hify/modules/observability/models.py`
- Modify: `backend/src/agent_hify/modules/observability/__init__.py`（P0-1 已建占位；保持空）
- Create: `backend/alembic/versions/0003_observability.py`
- Create: `backend/tests/observability/__init__.py`
- Create: `backend/tests/observability/test_migration.py`

> 注：P0-1 在 `src/agent_hify/observability/__init__.py` 建过占位包。本计划把 observability 作为**业务模块**放 `src/agent_hify/modules/observability/`（与 identity 同级）。Task 9 会删除旧 `src/agent_hify/observability/` 占位包并更新 import-linter。

**Interfaces:**
- Consumes: `core.db.Base`、`TimestampMixin`。
- Produces: ORM `Trace`、`UsageDaily`；迁移 `0003` 建表 `traces`、`usage_daily`（`usage_daily` 唯一索引 `(workspace_id,day,app_id,model_id) NULLS NOT DISTINCT`）。

- [ ] **Step 1: 写失败测试**

`backend/tests/observability/__init__.py`: （空文件）

`backend/tests/observability/test_migration.py`:
```python
from __future__ import annotations

import sqlalchemy as sa

from agent_hify.core.db import engine


def test_traces_and_usage_tables_exist() -> None:
    insp = sa.inspect(engine)
    names = set(insp.get_table_names())
    assert {"traces", "usage_daily"}.issubset(names)


def test_usage_daily_unique_nulls_not_distinct() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='usage_daily' AND indexname='uq_usage_daily_dim'"
            )
        ).first()
    assert row is not None
    assert "NULLS NOT DISTINCT" in row[0].upper()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/observability/test_migration.py -v`
Expected: FAIL（表不存在）

- [ ] **Step 3: 写 ORM 模型**

`backend/src/agent_hify/modules/observability/models.py`:
```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, TimestampMixin


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UsageDaily(Base, TimestampMixin):
    __tablename__ = "usage_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    model_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tokens_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=0, nullable=False)
    requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

- [ ] **Step 4: 写迁移**

`backend/alembic/versions/0003_observability.py`:
```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traces",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("conversation_id", sa.BigInteger, nullable=True),
        sa.Column("message_id", sa.BigInteger, nullable=True),
        sa.Column("app_id", sa.BigInteger, nullable=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("tokens_in", sa.Integer, server_default="0", nullable=False),
        sa.Column("tokens_out", sa.Integer, server_default="0", nullable=False),
        sa.Column("cost", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('llm_call','tool_call','retrieval','agent_step')",
            name="ck_traces_type",
        ),
    )
    op.create_index(
        "ix_traces_ws_app_created",
        "traces",
        ["workspace_id", "app_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "usage_daily",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("app_id", sa.BigInteger, nullable=True),
        sa.Column("model_id", sa.BigInteger, nullable=True),
        sa.Column("tokens_in", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("tokens_out", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("cost", sa.Numeric(14, 6), server_default="0", nullable=False),
        sa.Column("requests", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_usage_daily_dim ON usage_daily "
        "(workspace_id, day, app_id, model_id) NULLS NOT DISTINCT"
    )


def downgrade() -> None:
    op.drop_table("usage_daily")
    op.drop_table("traces")
```

- [ ] **Step 5: 跑迁移并验证测试通过**

Run:
```bash
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/observability/test_migration.py -v
```
Expected: 迁移到 `0003`；两条测试 PASSED。

- [ ] **Step 6: ruff/mypy 并提交**

```bash
cd backend && uv run ruff check . && uv run mypy
git add backend/src/agent_hify/modules/observability/models.py backend/alembic/versions/0003_observability.py backend/tests/observability
git commit -m "feat: observability models and migration (traces, usage_daily)"
```

---

### Task 3: observability service（trace / record_usage / 评估钩子占位）

**Files:**
- Create: `backend/src/agent_hify/modules/observability/schemas.py`
- Create: `backend/src/agent_hify/modules/observability/repository.py`
- Create: `backend/src/agent_hify/modules/observability/service.py`
- Create: `backend/tests/observability/test_service.py`

**Interfaces:**
- Consumes: `core.db`、ORM（Task 2）。
- Produces:
  - DTO `TraceIn`、`TraceOut`、`UsageDailyOut`。
  - `observability.service.record_trace(session, data: TraceIn) -> int`（返回 trace id）。
  - `observability.service.record_usage(session, *, workspace_id, day, model_id, tokens_in, tokens_out, cost, app_id=None, requests=1) -> None`（upsert 累加）。
  - `observability.service.list_traces(session, workspace_id, limit=50) -> list[TraceOut]`。
  - `observability.service.list_usage(session, workspace_id) -> list[UsageDailyOut]`。
  - `observability.service.run_eval_hook(name, payload) -> None`（占位：记录日志，不实现具体评估——评估方法由项目所有者定义）。

- [ ] **Step 1: 写失败测试**

`backend/tests/observability/test_service.py`:
```python
from __future__ import annotations

from datetime import date

from agent_hify.core.db import SessionLocal
from agent_hify.modules.observability import service
from agent_hify.modules.observability.schemas import TraceIn


def test_record_trace_and_list() -> None:
    with SessionLocal() as s:
        tid = service.record_trace(
            s,
            TraceIn(
                workspace_id=1, type="llm_call", status="ok",
                tokens_in=10, tokens_out=5, latency_ms=120,
                input={"q": "hi"}, output={"a": "hello"},
            ),
        )
        s.commit()
        assert tid > 0
        traces = service.list_traces(s, workspace_id=1, limit=10)
        assert any(t.id == tid for t in traces)


def test_record_usage_upsert_accumulates() -> None:
    with SessionLocal() as s:
        for _ in range(2):
            service.record_usage(
                s, workspace_id=1, day=date(2026, 6, 27), model_id=999,
                tokens_in=10, tokens_out=4, cost=0.001,
            )
        s.commit()
        rows = [u for u in service.list_usage(s, workspace_id=1)
                if u.model_id == 999 and str(u.day) == "2026-06-27"]
        assert len(rows) == 1
        assert rows[0].tokens_in == 20
        assert rows[0].requests == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/observability/test_service.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 schemas**

`backend/src/agent_hify/modules/observability/schemas.py`:
```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TraceIn(BaseModel):
    workspace_id: int
    type: str
    status: str
    app_id: int | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: Decimal = Decimal(0)
    latency_ms: int = 0
    input: dict[str, object] | None = None
    output: dict[str, object] | None = None
    error: str | None = None


class TraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    tokens_in: int
    tokens_out: int
    cost: Decimal
    latency_ms: int
    created_at: datetime


class UsageDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    app_id: int | None
    model_id: int | None
    tokens_in: int
    tokens_out: int
    cost: Decimal
    requests: int
```

- [ ] **Step 4: 写 repository**

`backend/src/agent_hify/modules/observability/repository.py`:
```python
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
    return trace.id


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
        workspace_id=workspace_id, day=day, app_id=app_id, model_id=model_id,
        tokens_in=tokens_in, tokens_out=tokens_out, cost=cost, requests=requests,
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
```
> 注：`on_conflict_do_update` 的 `index_elements` 命中 `uq_usage_daily_dim`（`NULLS NOT DISTINCT`），故 `app_id`/`model_id` 为 NULL 也能正确累加。

- [ ] **Step 5: 写 service**

`backend/src/agent_hify/modules/observability/service.py`:
```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from agent_hify.core.logging import get_logger
from agent_hify.modules.observability import repository
from agent_hify.modules.observability.models import Trace
from agent_hify.modules.observability.schemas import TraceIn, TraceOut, UsageDailyOut

logger = get_logger("agent_hify.observability")


def record_trace(session: Session, data: TraceIn) -> int:
    trace = Trace(
        workspace_id=data.workspace_id, type=data.type, status=data.status,
        app_id=data.app_id, conversation_id=data.conversation_id,
        message_id=data.message_id, tokens_in=data.tokens_in,
        tokens_out=data.tokens_out, cost=data.cost, latency_ms=data.latency_ms,
        input=data.input, output=data.output, error=data.error,
    )
    return repository.insert_trace(session, trace)


def record_usage(
    session: Session,
    *,
    workspace_id: int,
    day: date,
    model_id: int | None,
    tokens_in: int,
    tokens_out: int,
    cost: Decimal,
    app_id: int | None = None,
    requests: int = 1,
) -> None:
    repository.upsert_usage(
        session, workspace_id=workspace_id, day=day, app_id=app_id,
        model_id=model_id, tokens_in=tokens_in, tokens_out=tokens_out,
        cost=cost, requests=requests,
    )


def list_traces(session: Session, workspace_id: int, limit: int = 50) -> list[TraceOut]:
    return [TraceOut.model_validate(t) for t in repository.select_traces(session, workspace_id, limit)]


def list_usage(session: Session, workspace_id: int) -> list[UsageDailyOut]:
    return [UsageDailyOut.model_validate(u) for u in repository.select_usage(session, workspace_id)]


def run_eval_hook(name: str, payload: dict[str, object]) -> None:
    """评估钩子占位：具体评估方法/指标由项目所有者定义（见 METHODOLOGY.md）。当前仅记录。"""
    logger.info('{"eval_hook": "%s", "payload_keys": %s}', name, list(payload.keys()))
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/observability/test_service.py -v && uv run ruff check . && uv run mypy`
Expected: 两条 PASSED；ruff/mypy 绿。

- [ ] **Step 7: 提交**

```bash
git add backend/src/agent_hify/modules/observability backend/tests/observability/test_service.py
git commit -m "feat: observability service — trace, usage upsert, eval hook placeholder"
```

---

### Task 4: models 数据模型 + 迁移（model_providers / models）

**Files:**
- Create: `backend/src/agent_hify/modules/models/__init__.py`
- Create: `backend/src/agent_hify/modules/models/models.py`
- Create: `backend/alembic/versions/0004_models.py`
- Create: `backend/tests/models/__init__.py`
- Create: `backend/tests/models/test_migration.py`

**Interfaces:**
- Produces: ORM `ModelProvider`、`Model`；迁移 `0004` 建表（软删 + 部分唯一索引：`model_providers (workspace_id,name)`、`models (provider_id,model_key)`，均 `WHERE deleted_at IS NULL`；`models.provider_id` FK ON DELETE CASCADE）。

- [ ] **Step 1: 写失败测试**

`backend/tests/models/__init__.py`: （空文件）

`backend/tests/models/test_migration.py`:
```python
from __future__ import annotations

import sqlalchemy as sa

from agent_hify.core.db import engine


def test_model_tables_exist() -> None:
    insp = sa.inspect(engine)
    names = set(insp.get_table_names())
    assert {"model_providers", "models"}.issubset(names)


def test_models_partial_unique_index() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='models' AND indexname='uq_models_provider_key'"
            )
        ).first()
    assert row is not None and "deleted_at IS NULL" in row[0]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_migration.py -v`
Expected: FAIL（表不存在）

- [ ] **Step 3: 写 ORM 模型**

`backend/src/agent_hify/modules/models/__init__.py`: （空文件）

`backend/src/agent_hify/modules/models/models.py`:
```python
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, SoftDeleteMixin, TimestampMixin


class ModelProvider(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "model_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class Model(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("model_providers.id", ondelete="CASCADE"), nullable=False
    )
    model_key: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'"), nullable=False)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
```

- [ ] **Step 4: 写迁移**

`backend/alembic/versions/0004_models.py`:
```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_providers",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("base_url", sa.String, nullable=True),
        sa.Column("credentials_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('openai','anthropic','ollama','openai_compatible')",
            name="ck_provider_type",
        ),
    )
    op.create_index("ix_providers_workspace", "model_providers", ["workspace_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_providers_workspace_name ON model_providers "
        "(workspace_id, name) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "models",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("provider_id", sa.BigInteger, sa.ForeignKey("model_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_key", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("embedding_dim", sa.Integer, nullable=True),
        sa.Column("default_params", JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('llm','embedding','rerank')", name="ck_model_type"),
    )
    op.create_index("ix_models_provider", "models", ["provider_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_models_provider_key ON models "
        "(provider_id, model_key) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_table("models")
    op.drop_table("model_providers")
```

- [ ] **Step 5: 跑迁移并验证测试通过**

Run:
```bash
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/models/test_migration.py -v
```
Expected: 迁移到 `0004`；两条 PASSED。

- [ ] **Step 6: ruff/mypy 并提交**

```bash
cd backend && uv run ruff check . && uv run mypy
git add backend/src/agent_hify/modules/models/models.py backend/alembic/versions/0004_models.py backend/tests/models/test_migration.py backend/src/agent_hify/modules/models/__init__.py
git commit -m "feat: models tables — providers and models with soft-delete partial unique indexes"
```

---

### Task 5: models repository + provider/model 注册 service（凭证加密）

**Files:**
- Create: `backend/src/agent_hify/modules/models/schemas.py`
- Create: `backend/src/agent_hify/modules/models/repository.py`
- Create: `backend/src/agent_hify/modules/models/service.py`
- Create: `backend/tests/models/test_registry.py`

**Interfaces:**
- Consumes: `core.security.encrypt/decrypt`、`core.exceptions`、ORM（Task 4）。
- Produces:
  - DTO `ProviderIn(type,name,base_url,credentials)`、`ProviderOut(id,type,name,base_url,enabled)`、
    `ModelIn(provider_id,model_key,type,capabilities,embedding_dim,default_params)`、`ModelOut(...)`。
  - `models.service.create_provider(session, workspace_id, dto) -> ProviderOut`（凭证加密入库）。
  - `models.service.create_model(session, workspace_id, dto) -> ModelOut`。
  - `models.service.list_models(session, workspace_id) -> list[ModelOut]`。
  - `models.service.get_decrypted_credentials(session, provider_id) -> dict`（内部用）。

- [ ] **Step 1: 写失败测试**

`backend/tests/models/test_registry.py`:
```python
from __future__ import annotations

from agent_hify.core.db import SessionLocal
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import ModelIn, ProviderIn


def test_create_provider_encrypts_and_create_model() -> None:
    with SessionLocal() as s:
        prov = service.create_provider(
            s, workspace_id=1,
            dto=ProviderIn(type="openai", name="openai-main", base_url=None,
                           credentials={"api_key": "sk-secret"}),
        )
        s.commit()
        assert prov.id > 0
        # 凭证不明文：解密后才等于原值
        creds = service.get_decrypted_credentials(s, prov.id)
        assert creds["api_key"] == "sk-secret"

        m = service.create_model(
            s, workspace_id=1,
            dto=ModelIn(provider_id=prov.id, model_key="gpt-4o-mini", type="llm",
                        capabilities=["vision"], embedding_dim=None, default_params={}),
        )
        s.commit()
        assert m.id > 0
        assert any(x.id == m.id for x in service.list_models(s, workspace_id=1))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_registry.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 schemas**

`backend/src/agent_hify/modules/models/schemas.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderIn(BaseModel):
    type: str
    name: str
    base_url: str | None = None
    credentials: dict[str, str] = Field(default_factory=dict)


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    base_url: str | None
    enabled: bool


class ModelIn(BaseModel):
    provider_id: int
    model_key: str
    type: str
    capabilities: list[str] = Field(default_factory=list)
    embedding_dim: int | None = None
    default_params: dict[str, object] = Field(default_factory=dict)


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    model_key: str
    type: str
    capabilities: list[str]
    embedding_dim: int | None
    enabled: bool


class ChatMessage(BaseModel):
    role: str
    content: str


class InvokeResult(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    cost: float
    finish_reason: str


class ConnectivityResult(BaseModel):
    ok: bool
    error: str | None = None
```

- [ ] **Step 4: 写 repository**

`backend/src/agent_hify/modules/models/repository.py`:
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.models.models import Model, ModelProvider


def insert_provider(session: Session, provider: ModelProvider) -> ModelProvider:
    session.add(provider)
    session.flush()
    return provider


def get_provider(session: Session, provider_id: int) -> ModelProvider | None:
    stmt = select(ModelProvider).where(
        ModelProvider.id == provider_id, ModelProvider.deleted_at.is_(None)
    )
    return session.execute(stmt).scalar_one_or_none()


def insert_model(session: Session, model: Model) -> Model:
    session.add(model)
    session.flush()
    return model


def get_model(session: Session, model_id: int) -> Model | None:
    stmt = select(Model).where(Model.id == model_id, Model.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def list_models(session: Session, workspace_id: int) -> list[Model]:
    stmt = select(Model).where(
        Model.workspace_id == workspace_id, Model.deleted_at.is_(None)
    )
    return list(session.execute(stmt).scalars().all())
```

- [ ] **Step 5: 写 service（注册 + 凭证加密）**

`backend/src/agent_hify/modules/models/service.py`:
```python
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.core.security import decrypt, encrypt
from agent_hify.modules.models import repository
from agent_hify.modules.models.models import Model, ModelProvider
from agent_hify.modules.models.schemas import (
    ModelIn,
    ModelOut,
    ProviderIn,
    ProviderOut,
)


def create_provider(session: Session, workspace_id: int, dto: ProviderIn) -> ProviderOut:
    enc = encrypt(json.dumps(dto.credentials)) if dto.credentials else None
    provider = ModelProvider(
        workspace_id=workspace_id, type=dto.type, name=dto.name,
        base_url=dto.base_url, credentials_encrypted=enc,
    )
    repository.insert_provider(session, provider)
    return ProviderOut.model_validate(provider)


def get_decrypted_credentials(session: Session, provider_id: int) -> dict[str, str]:
    provider = repository.get_provider(session, provider_id)
    if provider is None:
        raise NotFoundError(ErrorCode.INTERNAL_ERROR, "厂商不存在")
    if not provider.credentials_encrypted:
        return {}
    return json.loads(decrypt(provider.credentials_encrypted))


def create_model(session: Session, workspace_id: int, dto: ModelIn) -> ModelOut:
    model = Model(
        workspace_id=workspace_id, provider_id=dto.provider_id,
        model_key=dto.model_key, type=dto.type, capabilities=dto.capabilities,
        embedding_dim=dto.embedding_dim, default_params=dto.default_params,
    )
    repository.insert_model(session, model)
    return ModelOut.model_validate(model)


def list_models(session: Session, workspace_id: int) -> list[ModelOut]:
    return [ModelOut.model_validate(m) for m in repository.list_models(session, workspace_id)]
```
> 注：`get_decrypted_credentials` 厂商不存在用 `INTERNAL_ERROR` 占位；Task 6 起会引入 models 专属错误码（如 `33001 MODEL_NOT_FOUND`）。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_registry.py -v && uv run ruff check . && uv run mypy`
Expected: PASSED；ruff/mypy 绿。

- [ ] **Step 7: 提交**

```bash
git add backend/src/agent_hify/modules/models/schemas.py backend/src/agent_hify/modules/models/repository.py backend/src/agent_hify/modules/models/service.py backend/tests/models/test_registry.py
git commit -m "feat: models registry — provider/model CRUD with credential encryption"
```

---

### Task 6: LiteLLM 适配器（ref-based invoke/embed，经韧性包装）

**Files:**
- Create: `backend/src/agent_hify/modules/models/adapter.py`
- Modify: `backend/src/agent_hify/core/error_codes.py`（加 `MODEL_NOT_FOUND=33001`、`EMBEDDING_DIM_MISMATCH=34001`、`MODEL_AUTH_FAILED=39001`）
- Modify: `backend/pyproject.toml`（加 `litellm`；mypy 忽略其缺失类型）
- Create: `backend/tests/models/test_adapter.py`

**Interfaces:**
- Consumes: `core.external.call_with_resilience`、`core.exceptions`。
- Produces:
  - DTO `ModelRef(provider_type, model_key, api_key, base_url, default_params)`。
  - `async adapter.invoke(ref, messages: list[dict]) -> InvokeResult`（messages 为 OpenAI 风格 `{role,content}`）。
  - `async adapter.embed(ref, texts: list[str]) -> list[list[float]]`。
  二者内部经 `call_with_resilience(key=ref.provider_type, ...)` 调 LiteLLM。

- [ ] **Step 1: 加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 追加 `"litellm>=1.55"`；在 `[tool.mypy]` 段后追加：
```toml
[[tool.mypy.overrides]]
module = ["litellm", "litellm.*"]
ignore_missing_imports = true
```
Run: `cd backend && uv sync`

- [ ] **Step 2: 加错误码**

在 `backend/src/agent_hify/core/error_codes.py` 的 `ErrorCode` 内（identity 段之后）追加：
```python
    # 3 models
    MODEL_NOT_FOUND = 33001
    EMBEDDING_DIM_MISMATCH = 34001
    MODEL_AUTH_FAILED = 39001
```

- [ ] **Step 3: 写失败测试（monkeypatch LiteLLM）**

`backend/tests/models/test_adapter.py`:
```python
from __future__ import annotations

import pytest

from agent_hify.modules.models import adapter
from agent_hify.modules.models.adapter import ModelRef


@pytest.mark.asyncio
async def test_invoke_parses_litellm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Msg:
        content = "hello"

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Usage:
        prompt_tokens = 8
        completion_tokens = 3

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    async def fake_acompletion(**kwargs: object) -> _Resp:
        assert kwargs["model"] == "gpt-4o-mini"
        return _Resp()

    monkeypatch.setattr(adapter.litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(adapter.litellm, "completion_cost", lambda **_: 0.0009)

    ref = ModelRef(provider_type="openai", model_key="gpt-4o-mini",
                   api_key="sk-x", base_url=None, default_params={})
    result = await adapter.invoke(ref, [{"role": "user", "content": "hi"}])
    assert result.content == "hello"
    assert result.tokens_in == 8
    assert result.tokens_out == 3
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_embed_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Item:
        def __init__(self, e: list[float]) -> None:
            self.embedding = e

    class _Resp:
        data = [{"embedding": [0.1, 0.2]}]

    async def fake_aembedding(**kwargs: object) -> _Resp:
        return _Resp()

    monkeypatch.setattr(adapter.litellm, "aembedding", fake_aembedding)
    ref = ModelRef(provider_type="openai", model_key="text-embedding-3-small",
                   api_key="sk-x", base_url=None, default_params={})
    vecs = await adapter.embed(ref, ["hi"])
    assert vecs == [[0.1, 0.2]]
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/models/test_adapter.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 5: 写适配器**

`backend/src/agent_hify/modules/models/adapter.py`:
```python
from __future__ import annotations

import litellm
from pydantic import BaseModel, Field

from agent_hify.core.external import call_with_resilience
from agent_hify.modules.models.schemas import InvokeResult

_TIMEOUT = 30.0


class ModelRef(BaseModel):
    provider_type: str
    model_key: str
    api_key: str | None = None
    base_url: str | None = None
    default_params: dict[str, object] = Field(default_factory=dict)


async def invoke(ref: ModelRef, messages: list[dict[str, str]]) -> InvokeResult:
    async def _call() -> InvokeResult:
        resp = await litellm.acompletion(
            model=ref.model_key, messages=messages,
            api_key=ref.api_key, api_base=ref.base_url, **ref.default_params,
        )
        choice = resp.choices[0]
        usage = resp.usage
        try:
            cost = float(litellm.completion_cost(completion_response=resp))
        except Exception:
            cost = 0.0
        return InvokeResult(
            content=choice.message.content or "",
            tokens_in=int(usage.prompt_tokens),
            tokens_out=int(usage.completion_tokens),
            cost=cost,
            finish_reason=str(choice.finish_reason or "stop"),
        )

    return await call_with_resilience(ref.provider_type, _call, timeout=_TIMEOUT)


async def embed(ref: ModelRef, texts: list[str]) -> list[list[float]]:
    async def _call() -> list[list[float]]:
        resp = await litellm.aembedding(
            model=ref.model_key, input=texts,
            api_key=ref.api_key, api_base=ref.base_url,
        )
        return [list(item["embedding"]) for item in resp.data]

    return await call_with_resilience(ref.provider_type, _call, timeout=_TIMEOUT)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/models/test_adapter.py -v && uv run ruff check . && uv run mypy`
Expected: 两条 PASSED；ruff/mypy 绿。

- [ ] **Step 7: 提交**

```bash
git add backend/src/agent_hify/modules/models/adapter.py backend/src/agent_hify/core/error_codes.py backend/pyproject.toml backend/tests/models/test_adapter.py
git commit -m "feat: litellm adapter for invoke/embed wrapped by resilience"
```

---

### Task 7: models 网关 service（resolve_ref / invoke[记 trace+用量] / embed / 连通性）

**Files:**
- Modify: `backend/src/agent_hify/modules/models/service.py`（加网关函数）
- Create: `backend/tests/models/test_gateway.py`

**Interfaces:**
- Consumes: `adapter`（Task 6）、`observability.service`（Task 3）、`repository`（Task 5）。
- Produces:
  - `models.service.resolve_ref(session, model_id) -> ModelRef`（解密凭证）。
  - `async models.service.invoke(session, *, model_id, workspace_id, messages: list[ChatMessage]) -> InvokeResult`（经 adapter 调用，**记 trace(llm_call) + record_usage**）。
  - `async models.service.embed(session, *, model_id, texts) -> list[list[float]]`。
  - `async models.service.test_connectivity(session, *, model_id, workspace_id) -> ConnectivityResult`（用 "ping" 做最小 invoke）。

- [ ] **Step 1: 写失败测试（monkeypatch adapter）**

`backend/tests/models/test_gateway.py`:
```python
from __future__ import annotations

import pytest

from agent_hify.core.db import SessionLocal
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import (
    ChatMessage,
    InvokeResult,
    ModelIn,
    ProviderIn,
)
from agent_hify.modules.observability import service as obs_service


@pytest.mark.asyncio
async def test_invoke_records_trace_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(ref: object, messages: object) -> InvokeResult:
        return InvokeResult(content="pong", tokens_in=3, tokens_out=1,
                            cost=0.0002, finish_reason="stop")

    monkeypatch.setattr(service.adapter, "invoke", fake_invoke)

    with SessionLocal() as s:
        prov = service.create_provider(
            s, 1, ProviderIn(type="openai", name="p-gw", base_url=None,
                             credentials={"api_key": "sk-x"}))
        m = service.create_model(
            s, 1, ModelIn(provider_id=prov.id, model_key="gpt-4o-mini",
                          type="llm", capabilities=[], embedding_dim=None,
                          default_params={}))
        s.commit()

        before = len(obs_service.list_traces(s, 1, limit=1000))
        result = await service.invoke(
            s, model_id=m.id, workspace_id=1,
            messages=[ChatMessage(role="user", content="ping")])
        s.commit()
        assert result.content == "pong"
        after = len(obs_service.list_traces(s, 1, limit=1000))
        assert after == before + 1
        usage = [u for u in obs_service.list_usage(s, 1) if u.model_id == m.id]
        assert usage and usage[0].tokens_in >= 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_gateway.py -v`
Expected: FAIL（`service.invoke` 不存在）

- [ ] **Step 3: 给 service 加网关函数**

在 `backend/src/agent_hify/modules/models/service.py` 追加（顶部补 import）：
```python
import time
from datetime import datetime, timezone
from decimal import Decimal

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.modules.models import adapter
from agent_hify.modules.models.adapter import ModelRef
from agent_hify.modules.models.schemas import (
    ChatMessage,
    ConnectivityResult,
    InvokeResult,
)
from agent_hify.modules.observability import service as obs_service
from agent_hify.modules.observability.schemas import TraceIn


def resolve_ref(session: Session, model_id: int) -> ModelRef:
    model = repository.get_model(session, model_id)
    if model is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "模型不存在")
    provider = repository.get_provider(session, model.provider_id)
    if provider is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "模型厂商不存在")
    creds = get_decrypted_credentials(session, provider.id)
    return ModelRef(
        provider_type=provider.type, model_key=model.model_key,
        api_key=creds.get("api_key"), base_url=provider.base_url,
        default_params=model.default_params,
    )


async def invoke(
    session: Session, *, model_id: int, workspace_id: int, messages: list[ChatMessage]
) -> InvokeResult:
    ref = resolve_ref(session, model_id)
    payload = [{"role": m.role, "content": m.content} for m in messages]
    started = time.monotonic()
    result = await adapter.invoke(ref, payload)
    latency_ms = int((time.monotonic() - started) * 1000)

    obs_service.record_trace(
        session,
        TraceIn(
            workspace_id=workspace_id, type="llm_call", status="ok",
            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            cost=Decimal(str(result.cost)), latency_ms=latency_ms,
            input={"messages": payload}, output={"content": result.content},
        ),
    )
    obs_service.record_usage(
        session, workspace_id=workspace_id,
        day=datetime.now(timezone.utc).date(), model_id=model_id,
        tokens_in=result.tokens_in, tokens_out=result.tokens_out,
        cost=Decimal(str(result.cost)),
    )
    return result


async def embed(session: Session, *, model_id: int, texts: list[str]) -> list[list[float]]:
    ref = resolve_ref(session, model_id)
    return await adapter.embed(ref, texts)


async def test_connectivity(
    session: Session, *, model_id: int, workspace_id: int
) -> ConnectivityResult:
    try:
        await invoke(
            session, model_id=model_id, workspace_id=workspace_id,
            messages=[ChatMessage(role="user", content="ping")],
        )
        return ConnectivityResult(ok=True)
    except Exception as exc:  # 归一为连通性失败
        return ConnectivityResult(ok=False, error=str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_gateway.py -v && uv run ruff check . && uv run mypy`
Expected: PASSED；ruff/mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add backend/src/agent_hify/modules/models/service.py backend/tests/models/test_gateway.py
git commit -m "feat: models gateway — resolve_ref, invoke (trace+usage), embed, connectivity"
```

---

### Task 8: models 路由 + observability 查询路由 + 装配

**Files:**
- Create: `backend/src/agent_hify/modules/models/router.py`
- Create: `backend/src/agent_hify/modules/observability/router.py`
- Modify: `backend/src/agent_hify/main.py`（挂载两路由）
- Create: `backend/tests/models/test_api.py`

**Interfaces:**
- Produces（均 `ApiResponse[T]`、需登录）：
  - `POST /api/v1/model-providers` → `ProviderOut`
  - `POST /api/v1/models` → `ModelOut`；`GET /api/v1/models` → `list[ModelOut]`
  - `POST /api/v1/models/{id}/test-connectivity` → `ConnectivityResult`
  - `POST /api/v1/models/{id}/invoke` → `InvokeResult`（P0 冒烟用）
  - `GET /api/v1/observability/traces` → `list[TraceOut]`；`GET /api/v1/observability/usage` → `list[UsageDailyOut]`

- [ ] **Step 1: 写失败测试（monkeypatch adapter，走真实 DB + 登录）**

`backend/tests/models/test_api.py`:
```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import InvokeResult


def _token(client: TestClient) -> str:
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@agent-hify.local", "password": "admin123"})
    return r.json()["data"]["access_token"]


def test_configure_model_and_invoke_records(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(ref: object, messages: object) -> InvokeResult:
        return InvokeResult(content="pong", tokens_in=2, tokens_out=1,
                            cost=0.0, finish_reason="stop")

    monkeypatch.setattr(service.adapter, "invoke", fake_invoke)
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}

    prov = client.post("/api/v1/model-providers", headers=h, json={
        "type": "openai", "name": "api-prov", "credentials": {"api_key": "sk-x"}})
    assert prov.json()["code"] == 0
    pid = prov.json()["data"]["id"]

    model = client.post("/api/v1/models", headers=h, json={
        "provider_id": pid, "model_key": "gpt-4o-mini", "type": "llm"})
    mid = model.json()["data"]["id"]

    conn = client.post(f"/api/v1/models/{mid}/test-connectivity", headers=h)
    assert conn.json()["data"]["ok"] is True

    inv = client.post(f"/api/v1/models/{mid}/invoke", headers=h,
                      json={"messages": [{"role": "user", "content": "ping"}]})
    assert inv.json()["data"]["content"] == "pong"

    traces = client.get("/api/v1/observability/traces", headers=h)
    assert len(traces.json()["data"]) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_api.py -v`
Expected: FAIL（路由不存在）

- [ ] **Step 3: 写 models 路由**

`backend/src/agent_hify/modules/models/router.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.identity.service import get_current_user
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import (
    ChatMessage,
    ConnectivityResult,
    InvokeResult,
    ModelIn,
    ModelOut,
    ProviderIn,
    ProviderOut,
)

router = APIRouter(prefix="/api/v1", tags=["models"])


class InvokeIn(BaseModel):
    messages: list[ChatMessage]


@router.post("/model-providers")
def create_provider(
    payload: ProviderIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ProviderOut]:
    out = service.create_provider(session, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.post("/models")
def create_model(
    payload: ModelIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ModelOut]:
    out = service.create_model(session, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.get("/models")
def list_models(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[ModelOut]]:
    return ApiResponse.ok(service.list_models(session, current.workspace_id))


@router.post("/models/{model_id}/test-connectivity")
async def test_connectivity(
    model_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ConnectivityResult]:
    out = await service.test_connectivity(
        session, model_id=model_id, workspace_id=current.workspace_id)
    session.commit()
    return ApiResponse.ok(out)


@router.post("/models/{model_id}/invoke")
async def invoke_model(
    model_id: int,
    payload: InvokeIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[InvokeResult]:
    out = await service.invoke(
        session, model_id=model_id, workspace_id=current.workspace_id,
        messages=payload.messages)
    session.commit()
    return ApiResponse.ok(out)
```

- [ ] **Step 4: 写 observability 路由**

`backend/src/agent_hify/modules/observability/router.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.identity.service import get_current_user
from agent_hify.modules.observability import service
from agent_hify.modules.observability.schemas import TraceOut, UsageDailyOut

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces")
def list_traces(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[TraceOut]]:
    return ApiResponse.ok(service.list_traces(session, current.workspace_id))


@router.get("/usage")
def list_usage(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[UsageDailyOut]]:
    return ApiResponse.ok(service.list_usage(session, current.workspace_id))
```

- [ ] **Step 5: 挂载路由**

`backend/src/agent_hify/main.py` 在挂载 identity router 之后追加：
```python
    from agent_hify.modules.models.router import router as models_router
    from agent_hify.modules.observability.router import router as observability_router

    app.include_router(models_router)
    app.include_router(observability_router)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && DATABASE_URL=... uv run pytest tests/models/test_api.py -v && uv run ruff check . && uv run mypy`
Expected: PASSED；ruff/mypy 绿。

- [ ] **Step 7: 提交**

```bash
git add backend/src/agent_hify/modules/models/router.py backend/src/agent_hify/modules/observability/router.py backend/src/agent_hify/main.py backend/tests/models/test_api.py
git commit -m "feat: models and observability routers, wired into app"
```

---

### Task 9: 清理占位包 + import-linter 契约扩展 + 全量绿灯

**Files:**
- Delete: `backend/src/agent_hify/observability/__init__.py`（P0-1 旧占位包；observability 已迁至 `modules/`）
- Modify: `backend/pyproject.toml`（扩展 `[tool.importlinter]`）
- Create: `backend/tests/test_architecture_models.py`

**Interfaces:**
- Produces: 分层契约——observability 仅依赖 core；models 依赖 core/identity/observability，不被它们依赖。

- [ ] **Step 1: 删除旧占位包并修正既有契约引用**

```bash
rm backend/src/agent_hify/observability/__init__.py
rmdir backend/src/agent_hify/observability 2>/dev/null || true
```
> 若 P0-1/P0-2 的 import-linter 契约里写过 `agent_hify.observability`，在下一步整体替换时一并改为 `agent_hify.modules.observability`。

- [ ] **Step 2: 替换 import-linter 契约段**

把 `backend/pyproject.toml` 的 `[tool.importlinter]` 段整体替换为：
```toml
[tool.importlinter]
root_package = "agent_hify"

[[tool.importlinter.contracts]]
name = "core is foundation (no internal deps)"
type = "forbidden"
source_modules = ["agent_hify.core"]
forbidden_modules = [
    "agent_hify.modules",
    "agent_hify.worker",
]

[[tool.importlinter.contracts]]
name = "observability depends only on core"
type = "forbidden"
source_modules = ["agent_hify.modules.observability"]
forbidden_modules = [
    "agent_hify.modules.identity",
    "agent_hify.modules.models",
    "agent_hify.worker",
]

[[tool.importlinter.contracts]]
name = "identity depends only on core"
type = "forbidden"
source_modules = ["agent_hify.modules.identity"]
forbidden_modules = [
    "agent_hify.modules.models",
    "agent_hify.modules.observability",
    "agent_hify.worker",
]
```
> 说明：models 可依赖 identity/observability，故不对 models 设禁；core 禁依赖任何 `agent_hify.modules`。

- [ ] **Step 3: 写架构测试**

`backend/tests/test_architecture_models.py`:
```python
from __future__ import annotations

import subprocess


def test_layering_contracts_hold() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
```
> 工作目录须为 `backend`。

- [ ] **Step 4: 全量绿灯**

前置：Postgres 在跑且迁移到 `0004`。
Run:
```bash
cd backend && uv run lint-imports
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest -v
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```
Expected: import-linter "0 broken"；全部 pytest PASSED；ruff/mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add backend/pyproject.toml backend/tests/test_architecture_models.py backend/src/agent_hify/observability
git commit -m "chore: drop placeholder package, extend import-linter for models/observability"
```

---

## Self-Review

- **Spec coverage（对照 DESIGN §14 P0 第 4、5、6 项 + §16 + standards）**：
  - models：厂商/凭证加密（T4/T5）✓ · 模型注册表 capabilities/embedding_dim（T4/T5）✓ · invoke/embed 网关（T6/T7）✓ · 连通性测试（T7/T8）✓。
  - observability 基线：traces 表+记录（T2/T3）✓ · 用量汇总 upsert（T2/T3）✓ · health 探针（P0-1 已有）✓ · 评估钩子接口占位（T3 `run_eval_hook`）✓。
  - 可扩展骨架：Provider 适配器（LiteLLM adapter，T6；新增厂商=改 ModelRef/适配，未来可加 Provider 协议）✓ · 外部调用韧性 core/external（T1）✓ · import-linter 扩展（T9）✓。Tool 协议在 P0 工具阶段（后续 P3）落，不在本计划。
  - **不在本计划**：前端（P0-4）；SSE 流式 invoke（P1 runtime）；content-block→厂商格式完整翻译（P1，P0 用 `ChatMessage` 文本）。
- **Placeholder scan**：无 TBD；`run_eval_hook` 是设计上的占位接口（评估方法由项目所有者定义），非计划空白。
- **Type consistency**：`call_with_resilience`/`CircuitBreaker`、`TraceIn/TraceOut/UsageDailyOut`、`record_trace/record_usage/list_traces/list_usage/run_eval_hook`、`ModelRef`、`adapter.invoke/embed`、`InvokeResult/ChatMessage/ConnectivityResult`、`service.create_provider/create_model/list_models/resolve_ref/invoke/embed/test_connectivity` 在定义与引用处一致。错误码 `MODEL_NOT_FOUND/EMBEDDING_DIM_MISMATCH/MODEL_AUTH_FAILED` 于 T6 注册。
- **完成判据（本计划 = P0 闭环主体）**：登录后 `POST /api/v1/model-providers` + `POST /api/v1/models` 配置模型 → `POST /models/{id}/test-connectivity` 通 → `POST /models/{id}/invoke` 发起调用 → `GET /api/v1/observability/traces`、`/usage` 看到记录（测试中 adapter 全程 mock）；`pytest`、`ruff`、`mypy`、`lint-imports` 全绿。

## 待执行者注意（已知风险点）

1. **LiteLLM 响应结构**：不同版本 `usage`/`completion_cost` 细节可能变；适配器已对 cost 做 try/except 兜底。真实联调（非 mock）时如字段不符，按实际响应微调 `adapter.invoke` 解析，不改对外签名。
2. **embedding 维度校验**：`EMBEDDING_DIM_MISMATCH` 错误码已备；真正校验在 P2（创建知识库选 embedding 模型时），本计划不触发。
3. **session/commit 边界**：本计划 router 内显式 `session.commit()`；P1 引入 runtime 后统一事务边界时可能上移，注意不要在 service 内部 commit（保持 service 无副作用提交，便于组合）。
4. **observability 迁移路径**：T2 把 observability 放 `modules/`，T9 删除 P0-1 的旧 `src/agent_hify/observability/` 占位包；执行顺序勿颠倒，否则 import-linter 旧契约引用会失败。
