# P0-1 后端工程骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起 agent-hify 后端可运行骨架与基础设施，含 `/health`、Postgres(pgvector)/Redis、Alembic、Celery、CI 工具链，全部测试与检查绿灯。

**Architecture:** 模块化单体（FastAPI），src 布局 `backend/src/agent_hify`。本计划只建骨架与基础设施，不含业务模块（core/identity/models 等在后续计划）。

**Tech Stack:** Python 3.12 · uv · FastAPI · SQLAlchemy 2.0 · Alembic · psycopg3 · pgvector · Celery · Redis · Ruff · mypy · pytest · import-linter · Docker Compose

## Global Constraints

- Python `>=3.12`。
- 依赖管理 `uv`，单一 `backend/pyproject.toml`。
- 所有代码全量类型注解；文件头 `from __future__ import annotations`。
- Lint+格式化 `ruff`；类型 `mypy`；测试 `pytest`（含 `pytest-asyncio`）。
- 模块依赖分层用 `import-linter` 守护（见 DESIGN.md §6.1）。
- 数据库 `PostgreSQL 16 + pgvector`；镜像 `pgvector/pgvector:pg16`。Redis `7`。
- 所有配置走环境变量 → `pydantic-settings`；密钥不入库明文。
- 提交信息用 Conventional Commits（`feat:`/`chore:`/`test:` 等）。

---

### Task 1: 后端包初始化、工具链与 `/health`

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/agent_hify/__init__.py`
- Create: `backend/src/agent_hify/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/.python-version`

**Interfaces:**
- Produces: FastAPI app 工厂 `create_app() -> FastAPI`（后续计划挂载各模块 router 用）；`GET /health -> {"status": "ok"}`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_health.py`:
```python
from __future__ import annotations

from fastapi.testclient import TestClient

from agent_hify.main import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 写 `pyproject.toml`（依赖+工具配置）**

`backend/pyproject.toml`:
```toml
[project]
name = "agent-hify"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0.36",
    "alembic>=1.14",
    "psycopg[binary]>=3.2",
    "pgvector>=0.3.6",
    "celery>=5.4",
    "redis>=5.2",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
    "import-linter>=2.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_hify"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = "src"
packages = ["agent_hify"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 写最小实现**

`backend/.python-version`:
```
3.12
```

`backend/src/agent_hify/__init__.py`:
```python
from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
```

`backend/src/agent_hify/main.py`:
```python
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="agent-hify", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

`backend/tests/__init__.py`: （空文件）

- [ ] **Step 4: 安装依赖并跑测试（验证通过）**

Run:
```bash
cd backend && uv sync && uv run pytest tests/test_health.py -v
```
Expected: `test_health_ok PASSED`

- [ ] **Step 5: 跑 ruff + mypy（验证绿）**

Run:
```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```
Expected: ruff "All checks passed"，mypy "Success: no issues found"

- [ ] **Step 6: 提交**

```bash
git add backend/
git commit -m "feat: backend skeleton with health endpoint and toolchain"
```

---

### Task 2: 后端容器化 + Compose（Postgres/pgvector、Redis）

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `deploy/docker-compose.yml`
- Create: `deploy/.env.example`

**Interfaces:**
- Produces: Compose 服务 `api`(8000)、`postgres`(5432)、`redis`(6379)；环境变量 `DATABASE_URL`、`REDIS_URL`。

- [ ] **Step 1: 写 Dockerfile**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv sync --no-dev
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "agent_hify.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/.dockerignore`:
```
.venv
__pycache__
tests
*.pyc
```

- [ ] **Step 2: 写 Compose 与 env 示例**

`deploy/.env.example`:
```
POSTGRES_USER=hify
POSTGRES_PASSWORD=hify
POSTGRES_DB=hify
DATABASE_URL=postgresql+psycopg://hify:hify@postgres:5432/hify
REDIS_URL=redis://redis:6379/0
```

`deploy/docker-compose.yml`:
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7
    ports: ["6379:6379"]

  api:
    build: ../backend
    env_file: [.env]
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }

volumes:
  pgdata:
```

- [ ] **Step 3: 验证起服与 health**

Run:
```bash
cd deploy && cp .env.example .env && docker compose up -d --build && sleep 5 && curl -fsS http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 4: 关停并提交**

```bash
cd deploy && docker compose down
git add backend/Dockerfile backend/.dockerignore deploy/
git commit -m "chore: dockerize api and add compose with postgres(pgvector) and redis"
```

---

### Task 3: SQLAlchemy Base + Alembic + 启用 pgvector 扩展

**Files:**
- Create: `backend/src/agent_hify/core/__init__.py`
- Create: `backend/src/agent_hify/core/config.py`
- Create: `backend/src/agent_hify/core/db.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_enable_pgvector.py`
- Create: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `DATABASE_URL`（Task 2）。
- Produces: `core.config.get_settings() -> Settings`（含 `database_url`）；`core.db.Base`（DeclarativeBase）、`core.db.engine`、`core.db.get_session()`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_migrations.py`:
```python
from __future__ import annotations

import sqlalchemy as sa

from agent_hify.core.db import engine


def test_pgvector_extension_present() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).first()
    assert row is not None
```

- [ ] **Step 2: 写 config 与 db**

`backend/src/agent_hify/core/__init__.py`: （空文件）

`backend/src/agent_hify/core/config.py`:
```python
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hify:hify@localhost:5432/hify"
    redis_url: str = "redis://localhost:6379/0"
    embedding_dim: int = 1536


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/src/agent_hify/core/db.py`:
```python
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from agent_hify.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: 初始化 Alembic**

`backend/alembic.ini`（关键片段，其余用 `alembic init` 默认）:
```ini
[alembic]
script_location = alembic
sqlalchemy.url =
```

`backend/alembic/env.py`（用项目 settings 注入 URL，离线/在线均可）:
```python
from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from agent_hify.core.config import get_settings
from agent_hify.core.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 4: 写迁移（启用 pgvector）**

`backend/alembic/versions/0001_enable_pgvector.py`:
```python
from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 5: 跑迁移并验证测试**

Run（需 Postgres 在跑；本地可 `cd deploy && docker compose up -d postgres`，并 export 本机 DATABASE_URL 指向 localhost）:
```bash
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/test_migrations.py -v
```
Expected: 迁移到 `0001`；`test_pgvector_extension_present PASSED`

- [ ] **Step 6: ruff/mypy 并提交**

```bash
cd backend && uv run ruff check . && uv run mypy
git add backend/src/agent_hify/core backend/alembic* backend/tests/test_migrations.py
git commit -m "feat: sqlalchemy base, alembic, and enable pgvector extension"
```

---

### Task 4: Celery 骨架 + ping 任务

**Files:**
- Create: `backend/src/agent_hify/worker/__init__.py`
- Create: `backend/src/agent_hify/worker/celery_app.py`
- Create: `backend/src/agent_hify/worker/tasks.py`
- Create: `backend/tests/test_worker.py`
- Modify: `deploy/docker-compose.yml`（加 `worker` 服务）

**Interfaces:**
- Consumes: `REDIS_URL`（Task 2）。
- Produces: `worker.celery_app.celery`；任务 `worker.tasks.ping() -> "pong"`。

- [ ] **Step 1: 写失败测试（eager 模式）**

`backend/tests/test_worker.py`:
```python
from __future__ import annotations

from agent_hify.worker.celery_app import celery
from agent_hify.worker.tasks import ping


def test_ping_eager() -> None:
    celery.conf.task_always_eager = True
    assert ping.delay().get() == "pong"
```

- [ ] **Step 2: 写 Celery app 与任务**

`backend/src/agent_hify/worker/__init__.py`: （空文件）

`backend/src/agent_hify/worker/celery_app.py`:
```python
from __future__ import annotations

from celery import Celery

from agent_hify.core.config import get_settings

settings = get_settings()
celery = Celery("agent_hify", broker=settings.redis_url, backend=settings.redis_url)
celery.autodiscover_tasks(["agent_hify.worker"])
```

`backend/src/agent_hify/worker/tasks.py`:
```python
from __future__ import annotations

from agent_hify.worker.celery_app import celery


@celery.task(name="ping")
def ping() -> str:
    return "pong"
```

- [ ] **Step 3: 跑测试**

Run:
```bash
cd backend && uv run pytest tests/test_worker.py -v
```
Expected: `test_ping_eager PASSED`

- [ ] **Step 4: 加 worker 服务到 Compose**

在 `deploy/docker-compose.yml` 的 `services:` 下，`api` 之后插入:
```yaml
  worker:
    build: ../backend
    env_file: [.env]
    command: ["uv", "run", "celery", "-A", "agent_hify.worker.celery_app.celery", "worker", "-l", "info"]
    depends_on:
      redis: { condition: service_started }
      postgres: { condition: service_healthy }
```

- [ ] **Step 5: 提交**

```bash
git add backend/src/agent_hify/worker backend/tests/test_worker.py deploy/docker-compose.yml
git commit -m "feat: celery skeleton with ping task and worker service"
```

---

### Task 5: import-linter 分层契约

**Files:**
- Modify: `backend/pyproject.toml`（加 `[tool.importlinter]`）
- Create: `backend/src/agent_hify/observability/__init__.py`（占位，使横切层存在）
- Create: `backend/tests/test_architecture.py`

**Interfaces:**
- Produces: 分层契约，CI 用 `uv run lint-imports` 校验（对应 DESIGN.md §6.1）。

- [ ] **Step 1: 写架构测试（调用 import-linter）**

`backend/tests/test_architecture.py`:
```python
from __future__ import annotations

import subprocess


def test_import_contracts_hold() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd="..",  # 注意：从 backend 目录运行 pytest 时调整为合适的工作目录
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```
> 说明：执行时确保工作目录为 `backend`（含 pyproject）。如在 backend 下跑 pytest，把 `cwd=".."` 改为 `cwd="."`。

- [ ] **Step 2: 加占位包，建立横切层**

`backend/src/agent_hify/observability/__init__.py`:
```python
from __future__ import annotations
```

- [ ] **Step 3: 写 import-linter 契约**

在 `backend/pyproject.toml` 末尾追加（本计划只有 `core`、`observability` 两个内部包，先约束 core 独立；后续计划加入 identity/models 等时扩展 layers）:
```toml
[tool.importlinter]
root_package = "agent_hify"

[[tool.importlinter.contracts]]
name = "core is foundation (no internal deps except stdlib/third-party)"
type = "forbidden"
source_modules = ["agent_hify.core"]
forbidden_modules = [
    "agent_hify.observability",
    "agent_hify.worker",
]
```

- [ ] **Step 4: 跑契约检查与测试**

Run:
```bash
cd backend && uv run lint-imports && uv run pytest tests/test_architecture.py -v
```
Expected: import-linter "Contracts: 1 kept, 0 broken"；测试 PASSED

- [ ] **Step 5: 全量绿灯并提交**

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest -v
git add backend/pyproject.toml backend/src/agent_hify/observability backend/tests/test_architecture.py
git commit -m "chore: enforce module layering with import-linter"
```

---

## Self-Review

- **Spec coverage（对照 DESIGN §14 P0 第 1 项工程骨架）**：uv/ruff/mypy/pytest（T1）✓ · Compose pg(pgvector)/redis（T2）✓ · Alembic+pgvector（T3）✓ · Celery 骨架（T4）✓ · import-linter（T5）✓ · 前端骨架不在本计划（P0-4）。
- **Placeholder scan**：无 TBD；每步含完整文件内容与命令。
- **Type consistency**：`create_app()`、`get_settings()`、`Base`、`get_session()`、`celery`、`ping()` 在引用处与定义处一致。
- **完成判据（本计划）**：`docker compose up` 起 api+pg+redis；`/health` 返回 ok；`alembic upgrade head` 启用 pgvector；`uv run pytest`、`ruff`、`mypy`、`lint-imports` 全绿。
