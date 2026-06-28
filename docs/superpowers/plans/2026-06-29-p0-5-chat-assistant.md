# P0-5 聊天助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 P0-5「聊天助手」：用户可创建 chat 类型应用（绑定模型 + 系统提示 + 采样参数），并在该应用下进行多轮流式对话；对话产生的 token/费用计入 observability。后端新增 `apps`(L3) 与 `runtime`(L4) 两个模块，前端新增「应用」与「对话」两个页面。

**Architecture:**
- 后端分层（DESIGN.md §6.1）：`core`(L0) → `identity`/`observability`(L1) → `models`(L2) → `apps`(L3) → `runtime`(L4)。
- `apps` 模块只管应用 CRUD（不依赖 models/runtime），`runtime` 模块负责跨模块编排：校验 app → 落 conversation/message → 调 `models.service.invoke_stream` 流式 → 落 assistant 消息 → 记 trace/usage。
- **SSE 流式的会话生命周期**：FastAPI 在 handler `return` 后即关闭注入的 `Depends(get_session)` 会话，而流式生成器在 `return` 之后才真正产出（被 `StreamingResponse` 迭代）。因此 `/chat` 端点**绝不**用 `Depends(get_session)`，而是在生成器闭包内部用 `SessionLocal()` 自建会话并自行 `commit/close`（与 `observability.service.record_trace_committed` 同一思路）。
- 前端：feature-based 目录，所有调用经 `request()`（响应永远 HTTP 200，按 `body.code` 判错）；流式对话用 `fetch` + `ReadableStream` 解析 SSE（axios 不适合 SSE）。

**Tech Stack:** FastAPI（async 路由）· SQLAlchemy 2.0 同步会话 · litellm `acompletion(stream=True)` · PostgreSQL · React + TypeScript + Ant Design + TanStack Query · Vitest。

## Global Constraints

- **架构纪律（CLAUDE.md / DESIGN.md §6.3）**：只走 service 接口；跨边界只传 DTO（Pydantic schema / 基本类型），不传 ORM 实例；依赖单向无环，任何模块可向下调 `observability`；`router` 只鉴权+校验+调本模块 service，跨模块编排只在 `runtime`。
- **所有外部调用必须有超时**：`invoke_stream` 的建连用 `asyncio.wait_for(..., timeout=60.0)` 包裹。
- **错误信封**：业务异常抛 `AppError` 子类，由全局处理器转成 HTTP 200 + `{code,message}`；SSE 流内的错误**不能**走 HTTP 状态码，必须以 `event: error` 事件下发。
- **软删除**：`apps` 用 `SoftDeleteMixin`，所有查询默认 `deleted_at IS NULL`。`conversations`/`messages` 不软删（随 app 级联）。
- **始终携带 `workspace_id`**：所有查询按 `workspace_id` 过滤（预埋多工作区，UI 不暴露切换）。
- **TDD**：每个 Task 先写测试再写实现；改完跑测试确认通过再提交。
- **生成物不手改**：前端 `src/lib/api/generated/` 由 orval 生成；本计划页面用手写 `features/*/api.ts`，不阻塞于生成的 hook 名。
- **后端命令经 WSL 运行**：`wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run <cmd>"`。
- **前端命令经 WSL 运行**：`wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run <cmd>"`。
- **集成测试需真实数据库**（标 `@pytest.mark.integration`），运行前确保已 `alembic upgrade head`。

---

## Task 1：DB 迁移 + 错误码 + apps 模块

落地 `apps`(L3) 模块：应用 CRUD。新建 `apps`/`conversations`/`messages` 三张表的迁移（conversations/messages 供 Task 2 的 runtime 使用，一并在本迁移建好）。

### Files

**Create**
- `backend/alembic/versions/0005_apps_runtime.py` — 迁移：建 `apps`、`conversations`、`messages` 三表
- `backend/src/agent_hify/modules/apps/__init__.py`
- `backend/src/agent_hify/modules/apps/models.py` — `App` ORM
- `backend/src/agent_hify/modules/apps/schemas.py` — DTO
- `backend/src/agent_hify/modules/apps/repository.py`
- `backend/src/agent_hify/modules/apps/service.py`
- `backend/src/agent_hify/modules/apps/router.py`
- `backend/tests/apps/__init__.py`
- `backend/tests/apps/test_apps_api.py`

**Modify**
- `backend/src/agent_hify/core/error_codes.py` — 加 `APP_NOT_FOUND=60003`、`CONVERSATION_NOT_FOUND=70001`
- `backend/src/agent_hify/main.py` — include apps router
- `backend/pyproject.toml` — 加 apps import-linter 契约

### Interfaces

**Consumes**
- `agent_hify.core.db`: `Base`, `TimestampMixin`, `SoftDeleteMixin`
- `agent_hify.core.response`: `ApiResponse`
- `agent_hify.core.error_codes`: `ErrorCode`
- `agent_hify.core.exceptions`: `NotFoundError`
- `agent_hify.modules.identity.deps`: `get_current_user`
- `agent_hify.modules.identity.schemas`: `UserOut`

**Produces**（供 Task 2 `runtime` 使用）
- `apps.service.create_app(session: Session, workspace_id: int, created_by: int, dto: AppCreate) -> AppOut`
- `apps.service.get_app(session: Session, app_id: int, workspace_id: int) -> AppOut`（不存在抛 `NotFoundError(APP_NOT_FOUND)`）
- `apps.service.list_apps(session: Session, workspace_id: int) -> list[AppOut]`
- `apps.service.update_app(session: Session, app_id: int, workspace_id: int, dto: AppUpdate) -> AppOut`
- `apps.service.delete_app(session: Session, app_id: int, workspace_id: int) -> None`
- `apps.schemas.AppOut`（含 `config: dict[str, object]`）、`AppConfigChat`

### Steps

- [ ] **Step 1.1 — 写迁移 `0005_apps_runtime.py`**

`backend/alembic/versions/0005_apps_runtime.py`：

```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apps",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("status", sa.String, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("share_token", sa.String, nullable=True),
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("type IN ('chat','agent')", name="ck_app_type"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_app_status"),
    )
    op.create_index("ix_apps_workspace", "apps", ["workspace_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_apps_share_token ON apps (share_token) "
        "WHERE share_token IS NOT NULL"
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "app_id",
            sa.BigInteger,
            sa.ForeignKey("apps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.BigInteger, nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String, server_default=sa.text("''"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_conversations_app_created", "conversations", ["app_id", "created_at"]
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.BigInteger,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','system','tool')", name="ck_message_role"
        ),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("apps")
```

- [ ] **Step 1.2 — 加错误码**

`backend/src/agent_hify/core/error_codes.py`，在 `MODEL_AUTH_FAILED = 39001` 之后追加：

```python
    # 6 apps
    APP_NOT_FOUND = 60003

    # 7 runtime
    CONVERSATION_NOT_FOUND = 70001
```

- [ ] **Step 1.3 — 写 `apps/__init__.py`（空文件）与 `apps/models.py`**

`backend/src/agent_hify/modules/apps/__init__.py`：空文件。

`backend/src/agent_hify/modules/apps/models.py`：

```python
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, SoftDeleteMixin, TimestampMixin


class App(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "apps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'{}'"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, server_default=text("'draft'"), nullable=False)
    share_token: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 1.4 — 写 `apps/schemas.py`**

`backend/src/agent_hify/modules/apps/schemas.py`：

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AppType = Literal["chat", "agent"]


class AppConfigChat(BaseModel):
    model_id: int
    system_prompt: str = ""
    params: dict[str, object] = Field(
        default_factory=lambda: {"temperature": 0.7, "max_tokens": 2048}
    )
    history_limit: int = 20


class AppCreate(BaseModel):
    type: AppType = "chat"
    name: str
    config: AppConfigChat


class AppUpdate(BaseModel):
    name: str | None = None
    config: AppConfigChat | None = None
    status: Literal["draft", "published"] | None = None


class AppOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    config: dict[str, object]
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 1.5 — 写 `apps/repository.py`**

`backend/src/agent_hify/modules/apps/repository.py`：

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.apps.models import App


def insert_app(session: Session, app: App) -> App:
    session.add(app)
    session.flush()
    return app


def get_app(session: Session, app_id: int, workspace_id: int) -> App | None:
    stmt = select(App).where(
        App.id == app_id,
        App.workspace_id == workspace_id,
        App.deleted_at.is_(None),
    )
    return session.execute(stmt).scalar_one_or_none()


def list_apps(session: Session, workspace_id: int) -> list[App]:
    stmt = (
        select(App)
        .where(App.workspace_id == workspace_id, App.deleted_at.is_(None))
        .order_by(App.created_at.desc(), App.id.desc())
    )
    return list(session.execute(stmt).scalars().all())


def update_app(session: Session, app: App) -> App:
    session.flush()
    return app


def soft_delete_app(session: Session, app: App) -> None:
    from datetime import UTC, datetime

    app.deleted_at = datetime.now(UTC)
    session.flush()
```

- [ ] **Step 1.6 — 写 `apps/service.py`**

`backend/src/agent_hify/modules/apps/service.py`：

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.modules.apps import repository
from agent_hify.modules.apps.models import App
from agent_hify.modules.apps.schemas import AppCreate, AppOut, AppUpdate


def _get_or_404(session: Session, app_id: int, workspace_id: int) -> App:
    app = repository.get_app(session, app_id, workspace_id)
    if app is None:
        raise NotFoundError(ErrorCode.APP_NOT_FOUND, "应用不存在")
    return app


def create_app(session: Session, workspace_id: int, created_by: int, dto: AppCreate) -> AppOut:
    app = App(
        workspace_id=workspace_id,
        type=dto.type,
        name=dto.name,
        config=dto.config.model_dump(),
        created_by=created_by,
    )
    repository.insert_app(session, app)
    return AppOut.model_validate(app)


def get_app(session: Session, app_id: int, workspace_id: int) -> AppOut:
    return AppOut.model_validate(_get_or_404(session, app_id, workspace_id))


def list_apps(session: Session, workspace_id: int) -> list[AppOut]:
    return [AppOut.model_validate(a) for a in repository.list_apps(session, workspace_id)]


def update_app(session: Session, app_id: int, workspace_id: int, dto: AppUpdate) -> AppOut:
    app = _get_or_404(session, app_id, workspace_id)
    if dto.name is not None:
        app.name = dto.name
    if dto.config is not None:
        app.config = dto.config.model_dump()
    if dto.status is not None:
        app.status = dto.status
    repository.update_app(session, app)
    return AppOut.model_validate(app)


def delete_app(session: Session, app_id: int, workspace_id: int) -> None:
    app = _get_or_404(session, app_id, workspace_id)
    repository.soft_delete_app(session, app)
```

- [ ] **Step 1.7 — 写 `apps/router.py`**

`backend/src/agent_hify/modules/apps/router.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.apps import service
from agent_hify.modules.apps.schemas import AppCreate, AppOut, AppUpdate
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut

router = APIRouter(prefix="/api/v1", tags=["apps"])


@router.post("/apps")
def create_app(
    payload: AppCreate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    out = service.create_app(session, current.workspace_id, current.id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.get("/apps")
def list_apps(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[AppOut]]:
    return ApiResponse.ok(service.list_apps(session, current.workspace_id))


@router.get("/apps/{app_id}")
def get_app(
    app_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    return ApiResponse.ok(service.get_app(session, app_id, current.workspace_id))


@router.put("/apps/{app_id}")
def update_app(
    app_id: int,
    payload: AppUpdate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    out = service.update_app(session, app_id, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.delete("/apps/{app_id}")
def delete_app(
    app_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[None]:
    service.delete_app(session, app_id, current.workspace_id)
    session.commit()
    return ApiResponse.ok(None)
```

- [ ] **Step 1.8 — 注册 router 到 `main.py`**

`backend/src/agent_hify/main.py`，在 import 区与 include 区分别加入 apps router（保持现有顺序，apps 在 models 之后）：

```python
    from agent_hify.modules.apps.router import router as apps_router
    from agent_hify.modules.identity.router import router as identity_router
    from agent_hify.modules.models.router import router as models_router
    from agent_hify.modules.observability.router import router as observability_router

    app.include_router(identity_router)
    app.include_router(models_router)
    app.include_router(observability_router)
    app.include_router(apps_router)
```

- [ ] **Step 1.9 — 加 apps import-linter 契约**

`backend/pyproject.toml`，在最后一个契约（`models does not depend on upper layers`）之后追加。`apps`(L3) 只能向下依赖 `core`/`identity`/`observability`/`models`；但本期 `apps` 模块**不依赖 `models`**（应用 CRUD 不调模型），故 `models` 也列入 forbidden，确保 apps 保持纯净（模型解析的编排归 runtime）：

```toml
# apps(L3) 只做应用 CRUD，禁止依赖 models 及任何更上层/编排模块；
# 模型调用编排归 runtime(L4)。forbidden 容忍尚未落地的 knowledge/tools。
[[tool.importlinter.contracts]]
name = "apps does not depend on upper layers"
type = "forbidden"
source_modules = ["agent_hify.modules.apps"]
forbidden_modules = [
    "agent_hify.modules.models",
    "agent_hify.modules.runtime",
    "agent_hify.modules.knowledge",
    "agent_hify.modules.tools",
    "agent_hify.worker",
]
```

- [ ] **Step 1.10 — 写测试 `tests/apps/__init__.py` 与 `tests/apps/test_apps_api.py`**

`backend/tests/apps/__init__.py`：空文件。

`backend/tests/apps/test_apps_api.py`：

```python
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app


def _token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    )
    return str(r.json()["data"]["access_token"])


@pytest.mark.integration
def test_app_crud_flow() -> None:
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    name = f"chat-app-{uuid.uuid4().hex[:8]}"

    # create
    created = client.post(
        "/api/v1/apps",
        headers=h,
        json={
            "type": "chat",
            "name": name,
            "config": {"model_id": 1, "system_prompt": "你是助手"},
        },
    )
    assert created.json()["code"] == 0
    app_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    assert created.json()["data"]["config"]["model_id"] == 1

    # list contains it
    listing = client.get("/api/v1/apps", headers=h)
    assert listing.json()["code"] == 0
    assert any(a["id"] == app_id for a in listing.json()["data"])

    # get
    got = client.get(f"/api/v1/apps/{app_id}", headers=h)
    assert got.json()["data"]["name"] == name

    # update
    updated = client.put(
        f"/api/v1/apps/{app_id}",
        headers=h,
        json={"name": f"{name}-v2", "status": "published"},
    )
    assert updated.json()["data"]["name"] == f"{name}-v2"
    assert updated.json()["data"]["status"] == "published"

    # delete (soft)
    deleted = client.delete(f"/api/v1/apps/{app_id}", headers=h)
    assert deleted.json()["code"] == 0

    # gone -> APP_NOT_FOUND
    missing = client.get(f"/api/v1/apps/{app_id}", headers=h)
    assert missing.status_code == 200
    assert missing.json()["code"] == 60003


@pytest.mark.integration
def test_get_missing_app_returns_app_not_found() -> None:
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.get("/api/v1/apps/99999999", headers=h)
    assert resp.status_code == 200
    assert resp.json()["code"] == 60003


@pytest.mark.integration
def test_create_app_invalid_type_returns_param_invalid() -> None:
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.post(
        "/api/v1/apps",
        headers=h,
        json={"type": "not-real", "name": "x", "config": {"model_id": 1}},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 10001
```

- [ ] **Step 1.11 — 跑迁移 + 测试 + lint**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run alembic upgrade head"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run pytest tests/apps -m integration -q"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run lint-imports"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run ruff check . && uv run ruff format --check ."
```

Expected：alembic 输出 `Running upgrade 0004 -> 0005`；pytest `3 passed`；lint-imports `Contracts: N kept, 0 broken.`；ruff `All checks passed!`。

- [ ] **Step 1.12 — 提交**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify && git add -A && git status"
```

确认范围仅含本 Task 文件后：

```
feat(apps): 应用 CRUD 模块 + apps/conversations/messages 迁移

- 新增 apps(L3) 模块：App ORM + schemas + repository + service + router
- 迁移 0005 建 apps/conversations/messages 三表（后两者供 runtime 使用）
- 错误码 APP_NOT_FOUND=60003 / CONVERSATION_NOT_FOUND=70001
- import-linter：apps 禁止依赖 models/runtime/上层模块

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Task 2：流式适配器 + runtime 模块

扩展 `models` 适配器/服务以支持流式；落地 `runtime`(L4) 模块：conversation/message 持久化 + 流式对话编排 + SSE 端点。

### Files

**Create**
- `backend/src/agent_hify/modules/runtime/__init__.py`
- `backend/src/agent_hify/modules/runtime/models.py` — `Conversation`、`Message` ORM
- `backend/src/agent_hify/modules/runtime/schemas.py` — DTO
- `backend/src/agent_hify/modules/runtime/repository.py`
- `backend/src/agent_hify/modules/runtime/service.py` — 含 `run_chat` 流式编排
- `backend/src/agent_hify/modules/runtime/router.py` — 含 SSE `/chat` 端点
- `backend/tests/runtime/__init__.py`
- `backend/tests/runtime/test_chat_api.py`

**Modify**
- `backend/src/agent_hify/modules/models/adapter.py` — 加 `invoke_stream`
- `backend/src/agent_hify/modules/models/service.py` — 加 `invoke_stream`
- `backend/src/agent_hify/main.py` — include runtime router
- `backend/pyproject.toml` — 加 runtime import-linter 契约

### Interfaces

**Consumes**
- `models.service.invoke_stream(session, *, model_id, messages, usage_sink) -> AsyncGenerator[str, None]`
- `apps.service.get_app(session, app_id, workspace_id) -> AppOut`、`apps.schemas.AppConfigChat`
- `observability.service.record_trace`、`record_trace_committed`、`record_usage`；`observability.schemas.TraceIn`
- `core.db.SessionLocal`、`core.pagination.{CursorPage, encode_cursor, decode_cursor}`
- `core.exceptions.{AppError, NotFoundError, ValidationError}`、`core.error_codes.ErrorCode`

**Produces**
- `GET /api/v1/apps/{app_id}/conversations -> CursorPage[ConversationOut]`
- `GET /api/v1/conversations/{conv_id}/messages -> CursorPage[MessageOut]`
- `POST /api/v1/apps/{app_id}/chat -> StreamingResponse(text/event-stream)`

**SSE 事件格式**（每个事件以 `\n\n` 结尾）：
```
event: message\ndata: {"delta": "token text"}\n\n
event: usage\ndata: {"tokens_in": N, "tokens_out": N, "cost": "0.001"}\n\n
event: done\ndata: {"conversation_id": 42, "message_id": 99}\n\n
event: error\ndata: {"code": 79001, "message": "..."}\n\n
```

### Steps

- [ ] **Step 2.1 — 扩展 `models/adapter.py`：加 `invoke_stream`**

在 `backend/src/agent_hify/modules/models/adapter.py` 顶部加 import：

```python
from collections.abc import AsyncGenerator
```

文件末尾追加（`_STREAM_CONNECT_TIMEOUT` 为建连超时，仅包裹建连/首响应；流式增量本身不设单超时，由客户端断开控制）：

```python
_STREAM_CONNECT_TIMEOUT = 60.0


async def invoke_stream(
    ref: ModelRef,
    messages: list[dict[str, str]],
    usage_sink: dict[str, object] | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用模型，逐段 yield 文本增量。

    用量经 `usage_sink`（可变 out 参数）回传：流结束后写入
    {"tokens_in","tokens_out","cost"}；provider 不支持 usage 时回退 0。
    仅对“建连/首响应”包 asyncio.wait_for 超时（litellm 流式的网络在迭代时发生，
    但建连本身也可能阻塞，故按设计统一加 60s 上限）。
    """

    async def _open() -> object:
        return await litellm.acompletion(
            model=ref.model_key,
            messages=messages,
            api_key=ref.api_key,
            api_base=ref.base_url,
            stream=True,
            stream_options={"include_usage": True},
            **ref.default_params,
        )

    stream = await asyncio.wait_for(_open(), timeout=_STREAM_CONNECT_TIMEOUT)
    final_chunk: object = None
    async for chunk in stream:
        final_chunk = chunk
        try:
            delta = chunk.choices[0].delta.content
        except (IndexError, AttributeError):
            delta = None
        if delta:
            yield delta

    if usage_sink is not None:
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        usage = getattr(final_chunk, "usage", None)
        if usage is not None:
            tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
        try:
            cost = float(litellm.completion_cost(completion_response=final_chunk))
        except Exception:
            cost = 0.0
        usage_sink["tokens_in"] = tokens_in
        usage_sink["tokens_out"] = tokens_out
        usage_sink["cost"] = cost
```

- [ ] **Step 2.2 — 扩展 `models/service.py`：加 `invoke_stream`**

在 `backend/src/agent_hify/modules/models/service.py` 顶部加 import：

```python
from collections.abc import AsyncGenerator
```

文件末尾（`test_connectivity` 之后）追加：

```python
async def invoke_stream(
    session: Session,
    *,
    model_id: int,
    messages: list[dict[str, str]],
    usage_sink: dict[str, object] | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用：解析 ref 后委托 adapter.invoke_stream，逐段透传文本增量。

    记账（trace/usage）不在此层做——流式编排的 token/费用须等流结束后由
    runtime.service 统一落账，故这里只负责取数与转发。
    """
    ref = resolve_ref(session, model_id)
    async for delta in adapter.invoke_stream(ref, messages, usage_sink):
        yield delta
```

- [ ] **Step 2.3 — 写 `runtime/__init__.py`（空）与 `runtime/models.py`**

`backend/src/agent_hify/modules/runtime/__init__.py`：空文件。

`backend/src/agent_hify/modules/runtime/models.py`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    app_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, server_default=text("''"), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2.4 — 写 `runtime/schemas.py`**

`backend/src/agent_hify/modules/runtime/schemas.py`：

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatInput(BaseModel):
    conversation_id: int | None = None
    message: str


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    app_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: list[dict[str, object]]
    created_at: datetime
```

- [ ] **Step 2.5 — 写 `runtime/repository.py`**

`backend/src/agent_hify/modules/runtime/repository.py`：游标分页用 `(created_at, id)` 复合游标，借 `sqlalchemy.tuple_` 比较保证稳定排序。

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from agent_hify.modules.runtime.models import Conversation, Message


def insert_conversation(session: Session, conv: Conversation) -> Conversation:
    session.add(conv)
    session.flush()
    return conv


def get_conversation(
    session: Session, conv_id: int, workspace_id: int
) -> Conversation | None:
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
        stmt = stmt.where(
            tuple_(Conversation.created_at, Conversation.id) < (cursor[0], cursor[1])
        )
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


def get_recent_messages(
    session: Session, conversation_id: int, limit: int
) -> list[Message]:
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
```

- [ ] **Step 2.6 — 写 `runtime/service.py`**

`backend/src/agent_hify/modules/runtime/service.py`。核心是 `run_chat`：**在生成器内部自建 `SessionLocal()`**（SSE 流出注入会话生命周期），异常一律转成 `event: error` 下发（不抛 HTTP 错误）。

```python
from __future__ import annotations

import json
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
from agent_hify.modules.models import service as models_service
from agent_hify.modules.observability import service as obs_service
from agent_hify.modules.observability.schemas import TraceIn
from agent_hify.modules.runtime import repository
from agent_hify.modules.runtime.models import Conversation, Message
from agent_hify.modules.runtime.schemas import ConversationOut, MessageOut


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
    next_cursor = (
        encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    )
    return CursorPage(
        items=[ConversationOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def list_messages(
    session: Session,
    conversation_id: int,
    cursor: str | None,
    limit: int,
) -> CursorPage[MessageOut]:
    decoded = decode_cursor(cursor) if cursor else None
    rows = repository.list_messages(session, conversation_id, decoded, limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    )
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
    """流式对话编排。自建会话（SSE 流出注入会话生命周期），逐段下发 SSE 事件。

    异常处理：业务/系统异常一律转 event: error（HTTP 已是 200 流），并以独立会话
    留痕 error trace（请求事务会回滚，故 error trace 另存，见 record_trace_committed）。
    """
    session = SessionLocal()
    try:
        app = apps_service.get_app(session, app_id, workspace_id)  # 不存在抛 APP_NOT_FOUND
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

        usage_sink: dict[str, object] = {}
        parts: list[str] = []
        started = time.monotonic()
        async for delta in models_service.invoke_stream(
            session,
            model_id=config.model_id,
            messages=llm_messages,
            usage_sink=usage_sink,
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

        tokens_in = int(usage_sink.get("tokens_in", 0) or 0)
        tokens_out = int(usage_sink.get("tokens_out", 0) or 0)
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
```

注意 `ChatInput` 需在 import 区引入：把上方 import 块的 schemas 行改为

```python
from agent_hify.modules.runtime.schemas import ChatInput, ConversationOut, MessageOut
```

- [ ] **Step 2.7 — 写 `runtime/router.py`**

`backend/src/agent_hify/modules/runtime/router.py`。**`/chat` 端点绝不用 `Depends(get_session)`**——只用 `get_current_user`（其内部会话仅用于同步解析用户，随依赖关闭，不影响流）；DB 写在 `run_chat` 自建会话内完成。列表端点正常用注入会话。

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.pagination import CursorPage
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.runtime import service
from agent_hify.modules.runtime.schemas import ChatInput, ConversationOut, MessageOut

router = APIRouter(prefix="/api/v1", tags=["runtime"])


@router.get("/apps/{app_id}/conversations")
def list_conversations(
    app_id: int,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[CursorPage[ConversationOut]]:
    page = service.list_conversations(session, app_id, current.workspace_id, cursor, limit)
    return ApiResponse.ok(page)


@router.get("/conversations/{conv_id}/messages")
def list_messages(
    conv_id: int,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[CursorPage[MessageOut]]:
    page = service.list_messages(session, conv_id, cursor, limit)
    return ApiResponse.ok(page)


@router.post("/apps/{app_id}/chat")
async def chat(
    app_id: int,
    payload: ChatInput,
    current: UserOut = Depends(get_current_user),
) -> StreamingResponse:
    # 不注入 get_session：StreamingResponse 在 handler return 后才迭代生成器，
    # 注入会话此时已关闭。生成器内部自建 SessionLocal()（见 service.run_chat）。
    generator = service.run_chat(app_id, current.workspace_id, current.id, payload)
    return StreamingResponse(generator, media_type="text/event-stream")
```

- [ ] **Step 2.8 — 注册 runtime router 到 `main.py`**

`backend/src/agent_hify/main.py`，import 区与 include 区加入 runtime（在 apps 之后）：

```python
    from agent_hify.modules.runtime.router import router as runtime_router

    app.include_router(runtime_router)
```

- [ ] **Step 2.9 — 加 runtime import-linter 契约**

`backend/pyproject.toml`，在 apps 契约之后追加。`runtime`(L4) 可向下依赖 `apps`/`models`/`observability`/`identity`/`core`，但**禁止**依赖 `knowledge`/`tools`/`worker`。沿用本仓库既有的 `forbidden` 表达分层（`forbidden` 容忍尚未落地的目标模块；这是“runtime 不得依赖更高/同层未就绪能力”的分层约束的落地方式）：

```toml
# runtime(L4) 编排层：可向下依赖 apps/models/observability，
# 但禁止依赖尚未落地的 knowledge/tools 与 worker（分层约束，forbidden 表达）。
[[tool.importlinter.contracts]]
name = "runtime does not depend on knowledge/tools/worker"
type = "forbidden"
source_modules = ["agent_hify.modules.runtime"]
forbidden_modules = [
    "agent_hify.modules.knowledge",
    "agent_hify.modules.tools",
    "agent_hify.worker",
]
```

- [ ] **Step 2.10 — 写测试 `tests/runtime/__init__.py` 与 `tests/runtime/test_chat_api.py`**

`backend/tests/runtime/__init__.py`：空文件。

`backend/tests/runtime/test_chat_api.py`。Mock `adapter.invoke_stream`（异步生成器）；解析 SSE 流验证 `message`/`usage`/`done` 事件；再验证 conversations/messages 列表端点。

```python
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app
from agent_hify.modules.models import adapter as models_adapter


def _token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    )
    return str(r.json()["data"]["access_token"])


def _create_model(client: TestClient, h: dict[str, str]) -> int:
    unique = uuid.uuid4().hex[:8]
    prov = client.post(
        "/api/v1/model-providers",
        headers=h,
        json={"type": "openai", "name": f"prov-{unique}", "credentials": {"api_key": "sk-x"}},
    )
    pid = prov.json()["data"]["id"]
    model = client.post(
        "/api/v1/models",
        headers=h,
        json={"provider_id": pid, "model_key": "gpt-4o-mini", "type": "llm"},
    )
    return int(model.json()["data"]["id"])


def _create_app(client: TestClient, h: dict[str, str], model_id: int) -> int:
    created = client.post(
        "/api/v1/apps",
        headers=h,
        json={
            "type": "chat",
            "name": f"chat-{uuid.uuid4().hex[:8]}",
            "config": {"model_id": model_id, "system_prompt": "你是助手"},
        },
    )
    return int(created.json()["data"]["id"])


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        events.append((event, json.loads(data)))
    return events


@pytest.mark.integration
def test_chat_streams_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(
        ref: object,
        messages: object,
        usage_sink: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        for token in ["你", "好", "！"]:
            yield token
        if usage_sink is not None:
            usage_sink["tokens_in"] = 5
            usage_sink["tokens_out"] = 3
            usage_sink["cost"] = 0.001

    monkeypatch.setattr(models_adapter, "invoke_stream", fake_stream)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)
    app_id = _create_app(client, h, model_id)

    resp = client.post(f"/api/v1/apps/{app_id}/chat", headers=h, json={"message": "在吗"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds.count("message") == 3
    assert "usage" in kinds
    assert "done" in kinds

    deltas = "".join(d["delta"] for e, d in events if e == "message")
    assert deltas == "你好！"

    usage_evt = next(d for e, d in events if e == "usage")
    assert usage_evt["tokens_in"] == 5
    assert usage_evt["tokens_out"] == 3

    done_evt = next(d for e, d in events if e == "done")
    conv_id = done_evt["conversation_id"]

    # conversations list
    convs = client.get(f"/api/v1/apps/{app_id}/conversations", headers=h)
    assert convs.json()["code"] == 0
    assert any(c["id"] == conv_id for c in convs.json()["data"]["items"])

    # messages list: user + assistant
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h)
    items = msgs.json()["data"]["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[1]["content"][0]["text"] == "你好！"


@pytest.mark.integration
def test_chat_continues_existing_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(
        ref: object,
        messages: object,
        usage_sink: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        yield "ok"

    monkeypatch.setattr(models_adapter, "invoke_stream", fake_stream)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)
    app_id = _create_app(client, h, model_id)

    first = client.post(f"/api/v1/apps/{app_id}/chat", headers=h, json={"message": "第一句"})
    conv_id = next(d for e, d in _parse_sse(first.text) if e == "done")["conversation_id"]

    second = client.post(
        f"/api/v1/apps/{app_id}/chat",
        headers=h,
        json={"conversation_id": conv_id, "message": "第二句"},
    )
    done = next(d for e, d in _parse_sse(second.text) if e == "done")
    assert done["conversation_id"] == conv_id

    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h)
    # 两轮 = 2 user + 2 assistant
    assert len(msgs.json()["data"]["items"]) == 4


@pytest.mark.integration
def test_chat_missing_app_yields_error_event() -> None:
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.post("/api/v1/apps/99999999/chat", headers=h, json={"message": "x"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 60003
```

- [ ] **Step 2.11 — 跑测试 + lint**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run pytest tests/runtime tests/models -m integration -q"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run lint-imports"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy"
```

Expected：pytest `... passed`（runtime 3 个 + models 既有）；lint-imports `Contracts: N kept, 0 broken.`；ruff `All checks passed!`；mypy `Success: no issues found`。

> 若 `TestClient` 对 `StreamingResponse` 返回的 `resp.text` 为空，确认 mock 的 `fake_stream` 是 `async def ... yield`（异步生成器），且 `chat` 端点为 `async def`。`TestClient`（基于 httpx）会同步聚合整个流到 `resp.text`。

- [ ] **Step 2.12 — 提交**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify && git add -A && git status"
```

```
feat(runtime): 流式聊天编排 + SSE 端点 + 会话/消息持久化

- models.adapter/service 新增 invoke_stream（litellm 流式 + usage 回传）
- runtime(L4)：Conversation/Message ORM + 游标分页 repository
- run_chat 在自建会话内编排：落消息→流式→落账→SSE 事件下发
- /chat 端点不注入 get_session（流出注入会话生命周期）
- import-linter：runtime 禁止依赖 knowledge/tools/worker

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Task 3：前端 — 应用页 + 对话页

新增「应用」管理页（卡片列表 + 新建 Modal）与「对话」页（会话侧栏 + 消息区 + 流式输入）。

### Files

**Create**
- `frontend/src/features/apps/api.ts`
- `frontend/src/features/apps/AppsPage.tsx`
- `frontend/src/features/apps/__tests__/AppsPage.test.tsx`
- `frontend/src/features/chat/api.ts`
- `frontend/src/features/chat/ChatPage.tsx`
- `frontend/src/features/chat/__tests__/ChatPage.test.tsx`

**Modify**
- `frontend/src/app/routes.tsx` — 加 `/apps`、`/apps/:appId/chat` 路由
- `frontend/src/app/Layout.tsx` — 加「应用」菜单项
- `frontend/openapi.json` — 更新快照（含新端点）

### Interfaces

**Consumes**
- `@/lib/api/http`: `request`、`ApiError`、`http`（测试用）
- `@/lib/auth/token`: `getToken`（流式 `fetch` 需手动带 Bearer）
- `@/features/models/api`: `listModels`、`ModelOut`（新建应用选模型）

**Produces**
- `apps/api.ts`: `AppOut`、`listApps()`、`createApp()`、`deleteApp()`
- `chat/api.ts`: `ConversationOut`、`MessageOut`、`listConversations()`、`listMessages()`、`streamChat()`

### Steps

- [ ] **Step 3.1 — 写 `features/apps/api.ts`**

`frontend/src/features/apps/api.ts`：

```typescript
import { request } from '@/lib/api/http';

export interface AppOut {
  id: number;
  type: string;
  name: string;
  config: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AppConfigChat {
  model_id: number;
  system_prompt?: string;
  params?: Record<string, unknown>;
  history_limit?: number;
}

export function listApps(): Promise<AppOut[]> {
  return request({ url: '/api/v1/apps', method: 'get' });
}

export function createApp(body: { name: string; config: AppConfigChat }): Promise<AppOut> {
  return request({
    url: '/api/v1/apps',
    method: 'post',
    data: { type: 'chat', name: body.name, config: body.config },
  });
}

export function deleteApp(appId: number): Promise<null> {
  return request({ url: `/api/v1/apps/${appId}`, method: 'delete' });
}
```

- [ ] **Step 3.2 — 写 `features/apps/AppsPage.tsx`**

`frontend/src/features/apps/AppsPage.tsx`：卡片列表 + 「新建应用」Modal（name、model 选择器、system_prompt、temperature 滑块）。

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Slider,
  Space,
  message,
} from 'antd';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { createApp, deleteApp, listApps } from '@/features/apps/api';
import { listModels } from '@/features/models/api';
import { ApiError } from '@/lib/api/http';

export function AppsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: apps = [] } = useQuery({ queryKey: ['apps'], queryFn: listApps });
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: listModels });

  const create = useMutation({
    mutationFn: (v: {
      name: string;
      model_id: number;
      system_prompt?: string;
      temperature: number;
    }) =>
      createApp({
        name: v.name,
        config: {
          model_id: v.model_id,
          system_prompt: v.system_prompt ?? '',
          params: { temperature: v.temperature, max_tokens: 2048 },
        },
      }),
    onSuccess: () => {
      message.success('已创建');
      setOpen(false);
      form.resetFields();
      void qc.invalidateQueries({ queryKey: ['apps'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '创建失败'),
  });

  const remove = useMutation({
    mutationFn: deleteApp,
    onSuccess: () => {
      message.success('已删除');
      void qc.invalidateQueries({ queryKey: ['apps'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '删除失败'),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button type="primary" onClick={() => setOpen(true)}>
        新建应用
      </Button>
      <Row gutter={[16, 16]}>
        {apps.map((app) => (
          <Col key={app.id} span={8}>
            <Card
              title={app.name}
              actions={[
                <Link key="chat" to={`/apps/${app.id}/chat`}>
                  进入对话
                </Link>,
                <Popconfirm
                  key="del"
                  title="确认删除该应用？"
                  onConfirm={() => remove.mutate(app.id)}
                >
                  <a>删除</a>
                </Popconfirm>,
              ]}
            >
              <div>类型：{app.type}</div>
              <div>状态：{app.status}</div>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal
        title="新建应用"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={create.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ temperature: 0.7 }}
          onFinish={(v) => create.mutate(v)}
        >
          <Form.Item name="name" label="应用名" rules={[{ required: true }]}>
            <Input placeholder="如：客服助手" />
          </Form.Item>
          <Form.Item name="model_id" label="模型" rules={[{ required: true }]}>
            <Select
              placeholder="选择模型"
              options={models.map((m) => ({ value: m.id, label: m.model_key }))}
            />
          </Form.Item>
          <Form.Item name="system_prompt" label="系统提示">
            <Input.TextArea rows={3} placeholder="你是一个乐于助人的助手" />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature">
            <Slider min={0} max={2} step={0.1} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
```

- [ ] **Step 3.3 — 写 `features/apps/__tests__/AppsPage.test.tsx`**

`frontend/src/features/apps/__tests__/AppsPage.test.tsx`：

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { AppsPage } from '@/features/apps/AppsPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders app list from api', async () => {
  mock.onGet('/api/v1/apps').reply(200, {
    code: 0,
    message: 'ok',
    data: [
      {
        id: 1,
        type: 'chat',
        name: '客服助手',
        config: { model_id: 1 },
        status: 'draft',
        created_at: '2026-06-29T00:00:00Z',
        updated_at: '2026-06-29T00:00:00Z',
      },
    ],
  });
  mock.onGet('/api/v1/models').reply(200, { code: 0, message: 'ok', data: [] });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AppsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('客服助手')).toBeInTheDocument();
});
```

- [ ] **Step 3.4 — 写 `features/chat/api.ts`**

`frontend/src/features/chat/api.ts`。列表用 `request`；流式用 `fetch` + `ReadableStream` 手写 SSE 解析（axios 不支持流），并手动带 Bearer（`fetch` 不经 axios 拦截器）。

```typescript
import { request } from '@/lib/api/http';
import { getToken } from '@/lib/auth/token';

export interface ConversationOut {
  id: number;
  app_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: number;
  conversation_id: number;
  role: string;
  content: { type: string; text?: string }[];
  created_at: string;
}

interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export function listConversations(appId: number): Promise<CursorPage<ConversationOut>> {
  return request({ url: `/api/v1/apps/${appId}/conversations`, method: 'get' });
}

export function listMessages(convId: number): Promise<CursorPage<MessageOut>> {
  return request({ url: `/api/v1/conversations/${convId}/messages`, method: 'get' });
}

export interface ChatStreamHandlers {
  onDelta: (text: string) => void;
  onUsage?: (u: { tokens_in: number; tokens_out: number; cost: string }) => void;
  onDone?: (d: { conversation_id: number; message_id: number }) => void;
  onError?: (e: { code: number; message: string }) => void;
}

export async function streamChat(
  appId: number,
  body: { conversation_id?: number; message: string },
  handlers: ChatStreamHandlers,
): Promise<void> {
  const token = getToken();
  const resp = await fetch(`/api/v1/apps/${appId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!resp.body) return;

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const dispatch = (block: string): void => {
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7);
      else if (line.startsWith('data: ')) data = line.slice(6);
    }
    if (!data) return;
    const parsed = JSON.parse(data);
    if (event === 'message') handlers.onDelta(parsed.delta);
    else if (event === 'usage') handlers.onUsage?.(parsed);
    else if (event === 'done') handlers.onDone?.(parsed);
    else if (event === 'error') handlers.onError?.(parsed);
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (block.trim()) dispatch(block);
    }
  }
}
```

- [ ] **Step 3.5 — 写 `features/chat/ChatPage.tsx`**

`frontend/src/features/chat/ChatPage.tsx`：左侧会话列表（+新建对话）、右侧消息气泡、底部输入框（流式中禁用）。

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Layout, List, Space } from 'antd';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  listConversations,
  listMessages,
  streamChat,
  type MessageOut,
} from '@/features/chat/api';

interface Bubble {
  role: string;
  text: string;
}

function toBubbles(messages: MessageOut[]): Bubble[] {
  return messages.map((m) => ({
    role: m.role,
    text: m.content.map((c) => c.text ?? '').join(''),
  }));
}

export function ChatPage() {
  const { appId } = useParams<{ appId: string }>();
  const appIdNum = Number(appId);
  const qc = useQueryClient();

  const [activeConv, setActiveConv] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);

  const { data: convPage } = useQuery({
    queryKey: ['conversations', appIdNum],
    queryFn: () => listConversations(appIdNum),
  });

  const openConversation = async (convId: number): Promise<void> => {
    setActiveConv(convId);
    const page = await listMessages(convId);
    setBubbles(toBubbles(page.items));
  };

  const newConversation = (): void => {
    setActiveConv(null);
    setBubbles([]);
  };

  const send = async (): Promise<void> => {
    if (!draft.trim() || streaming) return;
    const text = draft;
    setDraft('');
    setBubbles((prev) => [...prev, { role: 'user', text }, { role: 'assistant', text: '' }]);
    setStreaming(true);

    await streamChat(
      appIdNum,
      { conversation_id: activeConv ?? undefined, message: text },
      {
        onDelta: (delta) =>
          setBubbles((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'assistant',
              text: next[next.length - 1].text + delta,
            };
            return next;
          }),
        onDone: (d) => {
          setActiveConv(d.conversation_id);
          void qc.invalidateQueries({ queryKey: ['conversations', appIdNum] });
        },
      },
    );
    setStreaming(false);
  };

  return (
    <Layout style={{ height: 'calc(100vh - 112px)' }}>
      <Layout.Sider width={240} theme="light" style={{ padding: 12, overflow: 'auto' }}>
        <Button block onClick={newConversation} style={{ marginBottom: 12 }}>
          新建对话
        </Button>
        <List
          dataSource={convPage?.items ?? []}
          renderItem={(conv) => (
            <List.Item
              onClick={() => void openConversation(conv.id)}
              style={{
                cursor: 'pointer',
                fontWeight: conv.id === activeConv ? 600 : 400,
              }}
            >
              {conv.title || `对话 #${conv.id}`}
            </List.Item>
          )}
        />
      </Layout.Sider>
      <Layout.Content style={{ display: 'flex', flexDirection: 'column', padding: 16 }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {bubbles.map((b, i) => (
            <div
              key={i}
              style={{ textAlign: b.role === 'user' ? 'right' : 'left', margin: '8px 0' }}
            >
              <span
                style={{
                  display: 'inline-block',
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: b.role === 'user' ? '#1677ff' : '#f0f0f0',
                  color: b.role === 'user' ? '#fff' : '#000',
                  maxWidth: '70%',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {b.text}
              </span>
            </div>
          ))}
        </div>
        <Space.Compact style={{ width: '100%', marginTop: 12 }}>
          <Input
            value={draft}
            disabled={streaming}
            onChange={(e) => setDraft(e.target.value)}
            onPressEnter={() => void send()}
            placeholder="输入消息，回车发送"
          />
          <Button type="primary" disabled={streaming} onClick={() => void send()}>
            发送
          </Button>
        </Space.Compact>
      </Layout.Content>
    </Layout>
  );
}
```

- [ ] **Step 3.6 — 写 `features/chat/__tests__/ChatPage.test.tsx`**

`frontend/src/features/chat/__tests__/ChatPage.test.tsx`：smoke 测试（mock conversations + messages 列表；进入会话后渲染消息）。`streamChat` 用 `fetch`，本测试不触发发送，无需 mock fetch。

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ChatPage } from '@/features/chat/ChatPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

function renderChat() {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/apps/1/chat']}>
        <Routes>
          <Route path="/apps/:appId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test('renders conversation list and opens messages', async () => {
  mock.onGet('/api/v1/apps/1/conversations').reply(200, {
    code: 0,
    message: 'ok',
    data: {
      items: [
        {
          id: 7,
          app_id: 1,
          title: '历史对话',
          created_at: '2026-06-29T00:00:00Z',
          updated_at: '2026-06-29T00:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    },
  });
  mock.onGet('/api/v1/conversations/7/messages').reply(200, {
    code: 0,
    message: 'ok',
    data: {
      items: [
        {
          id: 1,
          conversation_id: 7,
          role: 'user',
          content: [{ type: 'text', text: '你好' }],
          created_at: '2026-06-29T00:00:00Z',
        },
        {
          id: 2,
          conversation_id: 7,
          role: 'assistant',
          content: [{ type: 'text', text: '你好，有什么可以帮你' }],
          created_at: '2026-06-29T00:00:01Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    },
  });

  renderChat();
  const conv = await screen.findByText('历史对话');
  await userEvent.click(conv);
  expect(await screen.findByText('你好，有什么可以帮你')).toBeInTheDocument();
});
```

- [ ] **Step 3.7 — 改 `routes.tsx` 加路由**

`frontend/src/app/routes.tsx`，加 import 与两条路由：

```tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';

import { Layout } from '@/app/Layout';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { LoginPage } from '@/features/auth/LoginPage';
import { ModelsPage } from '@/features/models/ModelsPage';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';
import { AppsPage } from '@/features/apps/AppsPage';
import { ChatPage } from '@/features/chat/ChatPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <Navigate to="/models" replace /> },
          { path: '/models', element: <ModelsPage /> },
          { path: '/apps', element: <AppsPage /> },
          { path: '/apps/:appId/chat', element: <ChatPage /> },
          { path: '/observability', element: <ObservabilityPage /> },
        ],
      },
    ],
  },
]);
```

- [ ] **Step 3.8 — 改 `Layout.tsx` 加菜单项**

`frontend/src/app/Layout.tsx`，`items` 中加「应用」（放在「模型」之后）：

```tsx
const items = [
  { key: '/models', label: <Link to="/models">模型</Link> },
  { key: '/apps', label: <Link to="/apps">应用</Link> },
  { key: '/observability', label: <Link to="/observability">用量 / Trace</Link> },
];
```

> 注：`selectedKeys={[pathname]}`，进入 `/apps/:appId/chat` 时 pathname 不等于 `/apps`，菜单不高亮属预期（对话页是应用的子页）。无需特殊处理。

- [ ] **Step 3.9 — 更新 `openapi.json` 快照**

后端新增了 apps/runtime 端点，重生成快照供 orval（生成物入库但页面不依赖生成 hook，主要为类型与未来替换）。需后端可导出 OpenAPI：

方式 A（推荐，无需起服务）—— 直接从 app 对象 dump：

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run python -c \"import json; from agent_hify.main import create_app; print(json.dumps(create_app().openapi(), ensure_ascii=False))\" > /mnt/e/codespace/project/me/agent-hify/frontend/openapi.json"
```

然后重生成客户端：

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run gen:api"
```

Expected：`frontend/openapi.json` 的 `paths` 含 `/api/v1/apps`、`/api/v1/apps/{app_id}`、`/api/v1/apps/{app_id}/conversations`、`/api/v1/conversations/{conv_id}/messages`、`/api/v1/apps/{app_id}/chat`；orval 在 `src/lib/api/generated/` 下生成 `apps/`、`runtime/` 标签目录。

> 若 `create_app()` 因无数据库连接而失败：OpenAPI 生成不触发 DB（仅构建路由），通常无碍；如确有副作用，改用方式 B：`uv run uvicorn agent_hify.main:app --port 8000` 起服务后 `curl -s localhost:8000/openapi.json > frontend/openapi.json`，再 `npm run gen:api`。

- [ ] **Step 3.10 — 跑前端测试 + lint + 构建**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run test"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run lint && npm run format:check"
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run build"
```

Expected：vitest 全绿（含新增 AppsPage/ChatPage 两个 smoke 测试 + 既有测试）；eslint `0 warnings`；prettier 通过；`tsc -b && vite build` 成功。

> 若 prettier 对生成物报格式：生成物入库但格式由 orval 决定，可在 `.prettierignore` 确认已忽略 `src/lib/api/generated/`（既有约定）；若未忽略，沿用既有处理方式。

- [ ] **Step 3.11 — 提交**

```bash
wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify && git add -A && git status"
```

```
feat(frontend): 应用管理页 + 流式对话页

- features/apps：应用卡片列表 + 新建 Modal（选模型/系统提示/温度）
- features/chat：会话侧栏 + 消息气泡 + fetch/ReadableStream SSE 流式输入
- 路由 /apps、/apps/:appId/chat；Layout 加「应用」菜单
- 更新 openapi.json 快照并重生成 orval 客户端

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## 收尾校验（三 Task 完成后）

- [ ] 后端全量：`wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/backend && uv run pytest -q && uv run lint-imports && uv run ruff check . && uv run ruff format --check . && uv run mypy"`
- [ ] 前端全量：`wsl bash -c "cd /mnt/e/codespace/project/me/agent-hify/frontend && npm run test && npm run lint && npm run build"`
- [ ] 端到端手测（可选）：起后端 + `npm run dev`，登录 → 模型页建一个真实模型 → 应用页建 chat 应用 → 进对话页发消息，确认流式逐字显示、刷新后历史可见、observability 页 usage 增长。
- [ ] **方法论归纳**：P0-5 完成后，把「SSE 流式与注入会话生命周期的冲突及自建会话方案」「流式用量经 out 参数回传」「跨模块编排归 runtime」等洞见增量写入 `METHODOLOGY.md`（由项目所有者定稿）。
- [ ] 更新 `docs/superpowers/STATUS.md` 与自动记忆中的 P0 进度。

## 风险与注意事项

1. **TestClient 对 SSE 的处理**：httpx 的 `TestClient` 会同步聚合整个流到 `resp.text`，故集成测试可直接断言 `resp.text`。生产中浏览器按事件增量接收。
2. **流式 token 计费**：依赖 provider 支持 `stream_options={"include_usage": True}`；不支持时 usage 回退 0（不报错），费用记 0。这是已知降级，非缺陷。
3. **错误在流内的语义**：`/chat` HTTP 状态恒 200，业务/系统错误以 `event: error` 下发（含 `code`）。前端 `streamChat` 的 `onError` 应提示用户，但不应跳登录（鉴权失败发生在流开始前的 `fetch` 响应，可按需扩展处理 401，本期从简）。
4. **import-linter 既有契约**：`models does not depend on upper layers` 已含 `apps`/`runtime`，无需改动；新增的 apps/runtime 契约与之不冲突。
5. **游标分页方向**：conversations 按 `created_at DESC`（新会话在前），messages 按 `created_at ASC`（对话顺序）；两者游标编码一致（`encode_cursor(created_at, id)`），但比较方向相反（DESC 用 `<`，ASC 用 `>`），见 repository。
