# P0-9 可观测深化 + 评估钩子 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 Annotation（消息评分/备注）为核心评估钩子，加上增强 trace 过滤、前端评分控件和评估钩子存储，走通"生产→记录→评估"闭环。

**Architecture:** observability 模块新增 `annotations` 表（rating 1-5 + comment + message_id）；`eval_events` JSONB 记录表存储 `run_eval_hook` 触发结果；trace 查询加 app_id/status/date 过滤；前端 ChatPage 消息下方加评分按钮，新建轻量可观测页（Traces 表 + Usage 图表）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · React + Ant Design + TanStack Query

## Global Constraints

- 后端命令：`wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && <cmd>"`
- `annotation.rating` 取值 1–5（整数），-1 代表 thumbs-down，1 代表 thumbs-up（简化为 rating: int，1=positive, -1=negative, 0=neutral）；也可保留 1-5 stars — **选用：-1/0/+1 三值**（thumbs down / neutral / up），存 `SmallInteger`
- Annotation 与 Message 关联：只记录 `message_id`（不加外键，避免跨模块约束）
- `run_eval_hook` 结果写入 `eval_events` 表（JSONB），不驱动业务
- 遵循已有架构分层：observability 在 L1，不依赖 L2-L4
- Trace 过滤：`app_id: int | None`, `status: str | None`, `days: int = 7`（最近 N 天），结果限 200 条
- Git commit 用中文，PowerShell `@'...'@` heredoc

---

### Task 1: 后端 — Annotations + eval_events + 增强 trace 查询

**Files:**
- Create: `backend/alembic/versions/0009_annotations.py`
- Create: `backend/src/agent_hify/modules/observability/annotation_models.py`
- Modify: `backend/src/agent_hify/modules/observability/schemas.py`
- Modify: `backend/src/agent_hify/modules/observability/repository.py`
- Modify: `backend/src/agent_hify/modules/observability/service.py`
- Modify: `backend/src/agent_hify/modules/observability/router.py`
- Create: `backend/tests/observability/test_annotations.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/observability/annotations` body: `{message_id, rating, comment}` → `AnnotationOut`
  - `GET /api/v1/observability/annotations?message_id=X` → `list[AnnotationOut]`
  - `GET /api/v1/observability/traces?app_id=&status=&days=7` → `list[TraceOut]`（同时补全 TraceOut 字段）
  - `POST /api/v1/observability/eval-hook` body: `{name, payload}` → `{id}` (eval_event saved)

**Steps:**

- [ ] **Step 1: 读现有代码**

```
wsl -d Ubuntu-26.04 bash -c "cat /mnt/e/codespace/project/me/agent-hify/backend/src/agent_hify/modules/observability/models.py"
wsl -d Ubuntu-26.04 bash -c "cat /mnt/e/codespace/project/me/agent-hify/backend/src/agent_hify/modules/observability/repository.py"
wsl -d Ubuntu-26.04 bash -c "ls /mnt/e/codespace/project/me/agent-hify/backend/alembic/versions/ | sort"
wsl -d Ubuntu-26.04 bash -c "tail -5 /mnt/e/codespace/project/me/agent-hify/backend/alembic/versions/0007_tools.py"
```

- [ ] **Step 2: 创建 Alembic 迁移**

创建 `backend/alembic/versions/0009_annotations.py`（下一个序号，读版本目录确认）：

```python
"""annotations + eval_events

Revision ID: 0009
Revises: <上一个 revision id>
Create Date: 2026-06-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "<上一个 revision id>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),  # -1/0/1
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_annotations_message_id", "annotations", ["message_id"])
    op.create_index("ix_annotations_workspace_id", "annotations", ["workspace_id"])
    op.create_index(
        "uq_annotations_workspace_message", "annotations",
        ["workspace_id", "message_id"], unique=True
    )

    op.create_table(
        "eval_events",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_events_name", "eval_events", ["name"])


def downgrade() -> None:
    op.drop_table("eval_events")
    op.drop_table("annotations")
```

**注意**: `sa.dialects.postgresql.JSONB()` 需要正确 import，可以用：
```python
from sqlalchemy.dialects.postgresql import JSONB
# 然后 sa.Column("payload", JSONB(), nullable=False)
```

- [ ] **Step 3: 运行迁移**

```
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify uv run alembic upgrade head 2>&1"
```

- [ ] **Step 4: 添加 ORM 模型（annotation_models.py）**

创建 `backend/src/agent_hify/modules/observability/annotation_models.py`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvalEvent(Base):
    __tablename__ = "eval_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 5: 扩展 schemas.py**

在 `observability/schemas.py` 中添加：

```python
from datetime import datetime

class AnnotationIn(BaseModel):
    message_id: int
    rating: int   # -1, 0, or 1
    comment: str | None = None

class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message_id: int
    rating: int
    comment: str | None
    created_at: datetime

class EvalHookIn(BaseModel):
    name: str
    payload: dict[str, object] = {}

class EvalEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
```

同时扩展 `TraceOut`，补全缺失字段（现有字段 id/type/status/tokens_in/tokens_out/cost/latency_ms/created_at，需要添加）：

```python
class TraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    app_id: int | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    tokens_in: int
    tokens_out: int
    cost: Decimal
    latency_ms: int
    error: str | None = None
    created_at: datetime
```

- [ ] **Step 6: 扩展 repository.py**

在 `observability/repository.py` 中添加：

```python
from agent_hify.modules.observability.annotation_models import Annotation, EvalEvent

def upsert_annotation(session: Session, ann: Annotation) -> Annotation:
    existing = (
        session.query(Annotation)
        .filter_by(workspace_id=ann.workspace_id, message_id=ann.message_id)
        .first()
    )
    if existing:
        existing.rating = ann.rating
        existing.comment = ann.comment
        return existing
    session.add(ann)
    session.flush()
    return ann

def select_annotations(session: Session, workspace_id: int, message_id: int) -> list[Annotation]:
    return (
        session.query(Annotation)
        .filter_by(workspace_id=workspace_id, message_id=message_id)
        .all()
    )

def insert_eval_event(session: Session, ev: EvalEvent) -> int:
    session.add(ev)
    session.flush()
    return ev.id
```

同时修改 `select_traces`，添加过滤参数：

```python
from datetime import datetime, timedelta, timezone

def select_traces(
    session: Session,
    workspace_id: int,
    limit: int = 50,
    app_id: int | None = None,
    status: str | None = None,
    days: int = 7,
) -> list[Trace]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = session.query(Trace).filter(
        Trace.workspace_id == workspace_id,
        Trace.created_at >= since,
    )
    if app_id is not None:
        q = q.filter(Trace.app_id == app_id)
    if status is not None:
        q = q.filter(Trace.status == status)
    return q.order_by(Trace.created_at.desc()).limit(limit).all()
```

- [ ] **Step 7: 扩展 service.py**

在 `observability/service.py` 中添加：

```python
from agent_hify.modules.observability.annotation_models import Annotation, EvalEvent
from agent_hify.modules.observability.schemas import AnnotationIn, AnnotationOut, EvalHookIn

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
    """评估钩子：记录触发事件，具体评估逻辑由项目所有者扩展。"""
    logger.info('{"eval_hook": "%s", "payload_keys": %s}', data.name, list(data.payload.keys()))
    ev = EvalEvent(workspace_id=workspace_id, name=data.name, payload=dict(data.payload))
    return repository.insert_eval_event(session, ev)
```

同时修改 `list_traces` 函数签名，传递过滤参数：

```python
def list_traces(
    session: Session,
    workspace_id: int,
    limit: int = 50,
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
```

- [ ] **Step 8: 扩展 router.py**

在 `observability/router.py` 中添加：

```python
from agent_hify.modules.observability.schemas import (
    AnnotationIn, AnnotationOut, EvalHookIn, EvalEventOut, TraceOut, UsageDailyOut
)

@router.post("/annotations")
def create_annotation(
    body: AnnotationIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AnnotationOut]:
    result = service.annotate(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(result)

@router.get("/annotations")
def list_annotations(
    message_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[AnnotationOut]]:
    return ApiResponse.ok(service.get_annotations(session, current.workspace_id, message_id))

@router.post("/eval-hook")
def trigger_eval_hook(
    body: EvalHookIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[dict[str, int]]:
    ev_id = service.run_eval_hook(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok({"id": ev_id})
```

同时修改 `list_traces` 端点，添加查询参数：

```python
@router.get("/traces")
def list_traces(
    app_id: int | None = None,
    status: str | None = None,
    days: int = 7,
    limit: int = 100,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[TraceOut]]:
    return ApiResponse.ok(
        service.list_traces(session, current.workspace_id, limit=limit, app_id=app_id, status=status, days=days)
    )
```

- [ ] **Step 9: 写测试（tests/observability/test_annotations.py）**

先读 `backend/tests/` 目录结构，确认是否有 `tests/observability/` 目录，了解 conftest 和 fixture 路径。

然后创建 `backend/tests/observability/test_annotations.py`（参考 test_chat_api.py 的鉴权模式）：

```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from agent_hify.main import create_app

app = create_app()

# 复用相同的 db_session 和 auth_headers fixture（参考已有测试文件确认路径）


@pytest.mark.asyncio
async def test_create_annotation(auth_headers):
    """POST /observability/annotations 返回 200 + annotation。"""
    # 需要一个有效的 message_id。简单起见，用一个不存在的 message_id 测试
    # （annotation 不做外键约束，所以任意 id 都能存）
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/observability/annotations",
            json={"message_id": 999, "rating": 1, "comment": "很好"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["rating"] == 1
    assert data["comment"] == "很好"


@pytest.mark.asyncio
async def test_list_annotations(auth_headers):
    """POST then GET annotations for same message_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/observability/annotations",
            json={"message_id": 888, "rating": -1, "comment": None},
            headers=auth_headers,
        )
        resp = await client.get(
            "/api/v1/observability/annotations?message_id=888",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["rating"] == -1


@pytest.mark.asyncio
async def test_eval_hook(auth_headers):
    """POST /observability/eval-hook 返回 event id。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/observability/eval-hook",
            json={"name": "test_eval", "payload": {"metric": "accuracy", "value": 0.9}},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] > 0


@pytest.mark.asyncio
async def test_traces_filter_by_status(auth_headers):
    """GET /observability/traces?status=ok 只返回 status=ok 的 trace。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/observability/traces?status=ok&days=1",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    items = resp.json()["data"]
    for item in items:
        assert item["status"] == "ok"
```

**注意**：先读 `backend/tests/` 中一个已有测试文件（如 `tests/runtime/test_chat_api.py`）来确认 `auth_headers` fixture 的导入方式，使用完全相同的模式，不要重新发明。

- [ ] **Step 10: 运行测试**

```
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify uv run pytest tests/ -v 2>&1 | tail -20"
```
预期：≥73 passed（69 原有 + 4 新）。

- [ ] **Step 11: lint**

```
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run ruff check . && uv run mypy src/ && uv run lint-imports"
```

- [ ] **Step 12: 提交**

```powershell
cd E:\codespace\project\me\agent-hify
git add backend/alembic/versions/0009_annotations.py `
        backend/src/agent_hify/modules/observability/annotation_models.py `
        backend/src/agent_hify/modules/observability/schemas.py `
        backend/src/agent_hify/modules/observability/repository.py `
        backend/src/agent_hify/modules/observability/service.py `
        backend/src/agent_hify/modules/observability/router.py `
        backend/tests/observability/test_annotations.py
git commit -m @'
feat(observability): Annotation 评分 + eval_events + 增强 trace 查询

- annotations 表：message 评分(-1/0/+1) + 备注，UPSERT
- eval_events 表：记录 eval_hook 触发事件（不驱动业务）
- TraceOut 补全 app_id/conversation_id/message_id/error 字段
- GET /traces 增加 app_id/status/days 过滤参数
- POST /annotations, GET /annotations, POST /eval-hook 端点

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
```

---

### Task 2: 前端 — 评分控件 + 可观测页面增强

**Files:**
- Modify: `frontend/src/features/chat/ChatPage.tsx`
- Modify: `frontend/src/features/chat/api.ts`
- Modify: `frontend/src/features/observability/ObservabilityPage.tsx`（若存在）或创建
- Modify: `frontend/src/app/routes.tsx`
- Update: `frontend/openapi.json` (regenerate)

**Interfaces:**
- Consumes: Task 1 的 `POST /api/v1/observability/annotations`, `GET /api/v1/observability/traces?*`, `POST /api/v1/observability/eval-hook`
- Produces: ChatPage 消息下方 👍👎 按钮；TraceList 显示更多字段；UsageChart 按日期柱状图

**Steps:**

- [ ] **Step 1: 读现有文件**

```
wsl -d Ubuntu-26.04 bash -c "cat /mnt/e/codespace/project/me/agent-hify/frontend/src/features/chat/ChatPage.tsx"
wsl -d Ubuntu-26.04 bash -c "ls /mnt/e/codespace/project/me/agent-hify/frontend/src/features/observability/"
wsl -d Ubuntu-26.04 bash -c "cat /mnt/e/codespace/project/me/agent-hify/frontend/src/app/routes.tsx"
```

- [ ] **Step 2: 重新生成 openapi.json**

```
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify uv run python -c \"import json; from agent_hify.main import create_app; print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))\" > /mnt/e/codespace/project/me/agent-hify/frontend/openapi.json"
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run gen:api"
```

- [ ] **Step 3: 创建/扩展 observability/api.ts**

找到现有 observability api 文件（可能在 `features/observability/` 或 `features/usage/`）。创建/修改以添加：

```typescript
// frontend/src/features/observability/api.ts
import { request } from '@/lib/api/http';

export interface TraceOut {
  id: number;
  type: string;
  status: string;
  app_id: number | null;
  conversation_id: number | null;
  message_id: number | null;
  tokens_in: number;
  tokens_out: number;
  cost: string;
  latency_ms: number;
  error: string | null;
  created_at: string;
}

export interface AnnotationOut {
  id: number;
  message_id: number;
  rating: number;
  comment: string | null;
  created_at: string;
}

export function listTraces(params?: { app_id?: number; status?: string; days?: number }): Promise<TraceOut[]> {
  const searchParams = new URLSearchParams();
  if (params?.app_id != null) searchParams.set('app_id', String(params.app_id));
  if (params?.status) searchParams.set('status', params.status);
  if (params?.days != null) searchParams.set('days', String(params.days));
  return request({ url: `/api/v1/observability/traces?${searchParams.toString()}`, method: 'get' });
}

export function createAnnotation(body: { message_id: number; rating: number; comment?: string }): Promise<AnnotationOut> {
  return request({ url: '/api/v1/observability/annotations', method: 'post', data: body });
}
```

- [ ] **Step 4: 创建 AnnotationButtons 组件（嵌入 ChatPage）**

在 ChatPage.tsx 消息气泡下方（assistant 消息）添加评分按钮。找到消息渲染处，在 assistant 消息后追加：

```tsx
// 简单内联或提取为子组件
function ThumbButtons({ messageId }: { messageId: number }) {
  const [rated, setRated] = useState<number | null>(null);
  const handleRate = async (rating: number) => {
    await createAnnotation({ message_id: messageId, rating });
    setRated(rating);
  };
  return (
    <Space style={{ fontSize: 12, marginTop: 4 }}>
      <Button
        type="text" size="small"
        icon={<LikeOutlined />}
        style={rated === 1 ? { color: '#52c41a' } : undefined}
        onClick={() => void handleRate(1)}
      />
      <Button
        type="text" size="small"
        icon={<DislikeOutlined />}
        style={rated === -1 ? { color: '#ff4d4f' } : undefined}
        onClick={() => void handleRate(-1)}
      />
    </Space>
  );
}
```

Import: `import { LikeOutlined, DislikeOutlined } from '@ant-design/icons'` and `import { createAnnotation } from '@/features/observability/api'`.

ChatPage 的消息渲染需要 `message_id`。检查现有代码中消息对象是否包含 id — 若已有 `message_id` 在 `done` 事件中记录，则可使用；若没有，则在 done 事件中存储并关联最后一条 assistant 消息。

**如果 ChatPage 没有 message_id 存储**: 暂时用最后一次 done 事件的 `message_id` 关联最后一条 assistant 消息。具体实现参考现有 ChatPage 结构调整。

- [ ] **Step 5: 增强 ObservabilityPage（traces 表 + usage 图表）**

读现有 observability 页面（可能叫 UsagePage 或 ObservabilityPage），增强 traces 表，显示更多字段：

```tsx
// 在 traces 表中添加列：
{ title: 'App', dataIndex: 'app_id', render: (v: number | null) => v ?? '-' },
{ title: 'Status', dataIndex: 'status', render: (s: string) => (
    <Tag color={s === 'ok' ? 'green' : 'red'}>{s}</Tag>
  )
},
{ title: '延迟(ms)', dataIndex: 'latency_ms' },
{ title: '错误', dataIndex: 'error', render: (e: string | null) => e ? <Text type="danger">{e.slice(0, 50)}</Text> : '-' },
```

对 usage 数据，添加一个简单的 Ant Design 条形展示（无需引入 Recharts，用 Progress 组件或 Table 即可）。

- [ ] **Step 6: 写测试**

创建 `frontend/src/features/observability/__tests__/AnnotationButtons.test.tsx`：

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import * as obsApi from '@/features/observability/api';

// 若 ThumbButtons 提取为独立组件则直接测试；否则测试 createAnnotation 被调用
test('thumbs-up calls createAnnotation with rating 1', async () => {
  const spy = vi.spyOn(obsApi, 'createAnnotation').mockResolvedValue({
    id: 1, message_id: 42, rating: 1, comment: null, created_at: '',
  });
  // render ThumbButtons or the containing component
  // If ThumbButtons is extracted:
  const { ThumbButtons } = await import('@/features/chat/ChatPage'); // 调整 import
  render(<ThumbButtons messageId={42} />);
  fireEvent.click(screen.getByRole('button', { name: /like/i }));
  await waitFor(() => expect(spy).toHaveBeenCalledWith({ message_id: 42, rating: 1 }));
});
```

**注意**: 若 ThumbButtons 没有独立导出，改为 smoke test（renders without crash）。

- [ ] **Step 7: lint + 测试 + build**

```
wsl -d Ubuntu-26.04 bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run test && npm run lint && npm run build"
```

预期：≥12 tests passed（11 原有 + 1 新）。

- [ ] **Step 8: 提交**

```powershell
cd E:\codespace\project\me\agent-hify
git add frontend/src/features/observability/ `
        frontend/src/features/chat/ChatPage.tsx `
        frontend/src/app/routes.tsx `
        frontend/openapi.json `
        frontend/src/lib/api/generated/
git commit -m @'
feat(observability): 前端评分控件 + 可观测页面增强

- ChatPage: assistant 消息下方 👍👎 评分按钮
- ObservabilityPage: traces 表加 status/latency/error 列
- openapi.json 更新含 /annotations /eval-hook 端点

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
```
