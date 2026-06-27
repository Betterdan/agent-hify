# P0-2 core 基础设施 + identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 core 横切基础设施（公共类型/错误码/统一响应/异常处理/分页/安全/日志/时间戳与软删 Mixin）与 identity 模块（用户/工作区、登录鉴权、角色、默认种子），全部 TDD 绿灯。

**Architecture:** 在 P0-1 骨架之上扩展 `backend/src/agent_hify/core` 与新增 `modules/identity`。core 不含业务，只提供横切能力；identity 是 L1 模块，仅依赖 core。统一响应 `ApiResponse[T]` 始终 HTTP 200、错误码按模块分段（DESIGN.md §9、docs/standards.md §6）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0(Mapped) · Alembic · pydantic v2 · bcrypt(密码) · cryptography/Fernet(凭证加密) · PyJWT(令牌) · pytest

## Global Constraints

- Python `>=3.12`；文件头 `from __future__ import annotations`；全量类型注解。
- 依赖管理 `uv`；新增依赖加入 `backend/pyproject.toml`，不引入技术栈外依赖。
- Lint+格式化 `ruff`；类型 `mypy --strict`；测试 `pytest`。
- 模块依赖分层用 `import-linter` 守护（DESIGN.md §6.1）：identity 仅依赖 core/observability。
- **统一响应**：业务接口一律 `ApiResponse[T]`、**始终 HTTP 200**；`/health` 等探针例外（docs/standards.md §6.2）。
- **错误码**：5 位 `M K NNN`，集中登记在 `core/error_codes.py`（docs/standards.md §6.4）。
- **软删除**：配置/用户表带 `deleted_at`，唯一约束用**部分唯一索引**（`WHERE deleted_at IS NULL`）。
- **所有时间** `timestamptz`、UTC；字段 `snake_case`。
- 密钥不入库明文：模型/工具凭证用 Fernet 加密；密码用 bcrypt 哈希。
- 提交信息用 Conventional Commits。
- 需要数据库的测试：本机先 `cd deploy && docker compose up -d postgres`，并设 `DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify`。

---

### Task 1: core 公共基座（类型 / 错误码 / 日志 / 时间戳与软删 Mixin）

**Files:**
- Create: `backend/src/agent_hify/core/types.py`
- Create: `backend/src/agent_hify/core/error_codes.py`
- Create: `backend/src/agent_hify/core/logging.py`
- Modify: `backend/src/agent_hify/core/db.py`（加 `TimestampMixin`、`SoftDeleteMixin`）
- Create: `backend/tests/core/__init__.py`
- Create: `backend/tests/core/test_error_codes.py`
- Create: `backend/tests/core/test_types.py`

**Interfaces:**
- Produces:
  - `core.types.ContentBlock`（`TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock` 判别联合，判别键 `type`）。
  - `core.error_codes.ErrorCode`（IntEnum，`SUCCESS=0` 及各 5 位码）。
  - `core.logging.setup_logging() -> None`、`core.logging.get_logger(name) -> logging.Logger`（JSON 输出）。
  - `core.db.TimestampMixin`（`created_at`/`updated_at`）、`core.db.SoftDeleteMixin`（`deleted_at`）。

- [ ] **Step 1: 写失败测试**

`backend/tests/core/__init__.py`: （空文件）

`backend/tests/core/test_error_codes.py`:
```python
from __future__ import annotations

from agent_hify.core.error_codes import ErrorCode


def test_success_is_zero() -> None:
    assert ErrorCode.SUCCESS.value == 0


def test_codes_unique_and_five_digit() -> None:
    values = [c.value for c in ErrorCode if c is not ErrorCode.SUCCESS]
    assert len(values) == len(set(values)), "错误码不得重号"
    assert all(10000 <= v <= 89999 for v in values), "错误码须为 5 位 M K NNN"


def test_first_digit_is_known_module_domain() -> None:
    for c in ErrorCode:
        if c is ErrorCode.SUCCESS:
            continue
        assert int(str(c.value)[0]) in range(1, 9), f"{c.name} 首位模块域非法"
```

`backend/tests/core/test_types.py`:
```python
from __future__ import annotations

from agent_hify.core.types import parse_content_blocks


def test_parse_text_and_image_blocks() -> None:
    raw = [
        {"type": "text", "text": "hi"},
        {"type": "image", "source": {"kind": "url", "url": "http://x/y.png"}},
    ]
    blocks = parse_content_blocks(raw)
    assert blocks[0].type == "text"
    assert blocks[1].type == "image"
    assert blocks[1].source.url == "http://x/y.png"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/core/test_error_codes.py tests/core/test_types.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写错误码**

`backend/src/agent_hify/core/error_codes.py`:
```python
from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """错误码 5 位 M K NNN：M 模块域(1公用·2identity·3models·4knowledge·5tools·6apps·7runtime·8observability)，
    K 类别(0参数·1鉴权·2权限·3资源·4业务·5限流·9外部/系统)，NNN 序号。详见 docs/standards.md §6.4。"""

    SUCCESS = 0

    # 1 公用 / core
    PARAM_INVALID = 10001
    UNAUTHORIZED = 11001
    PERMISSION_DENIED = 12001
    RATE_LIMITED = 15001
    INTERNAL_ERROR = 19001
    EXTERNAL_TIMEOUT = 19002
    CIRCUIT_OPEN = 19003

    # 2 identity
    INVALID_CREDENTIALS = 21001
    USER_NOT_FOUND = 23001
    EMAIL_ALREADY_EXISTS = 23002
```

- [ ] **Step 4: 写公共类型**

`backend/src/agent_hify/core/types.py`:
```python
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    kind: Literal["url", "base64"]
    url: str | None = None
    data: str | None = None
    media_type: str | None = None


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, object] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: list["ContentBlock"] = Field(default_factory=list)


ContentBlock = Annotated[
    Union[TextBlock, ImageBlock, ToolUseBlock, ToolResultBlock],
    Field(discriminator="type"),
]

_blocks_adapter: TypeAdapter[list[ContentBlock]] = TypeAdapter(list[ContentBlock])


def parse_content_blocks(raw: list[dict[str, object]]) -> list[ContentBlock]:
    return _blocks_adapter.validate_python(raw)
```

- [ ] **Step 5: 写结构化日志**

`backend/src/agent_hify/core/logging.py`:
```python
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 6: 给 db.py 加 Mixin**

在 `backend/src/agent_hify/core/db.py` 顶部 import 与 `Base` 之后追加（保留已有 `Base`/`engine`/`get_session`）：
```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

- [ ] **Step 7: 运行测试与检查（验证通过）**

Run:
```bash
cd backend && uv run pytest tests/core/test_error_codes.py tests/core/test_types.py -v && uv run ruff check . && uv run ruff format --check . && uv run mypy
```
Expected: 测试 PASSED；ruff/mypy 绿。

- [ ] **Step 8: 提交**

```bash
git add backend/src/agent_hify/core backend/tests/core
git commit -m "feat: core base — content types, error codes, json logging, db mixins"
```

---

### Task 2: 统一响应信封 `ApiResponse[T]`

**Files:**
- Create: `backend/src/agent_hify/core/response.py`
- Create: `backend/tests/core/test_response.py`

**Interfaces:**
- Produces: `core.response.ApiResponse[T]`（字段 `code:int=0`、`message:str="ok"`、`data:T|None`、`details:dict|None`）；类方法 `ApiResponse.ok(data)` 与 `ApiResponse.fail(code, message, details=None)`。

- [ ] **Step 1: 写失败测试**

`backend/tests/core/test_response.py`:
```python
from __future__ import annotations

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.response import ApiResponse


def test_ok_envelope() -> None:
    resp = ApiResponse.ok({"id": 1})
    assert resp.code == 0
    assert resp.message == "ok"
    assert resp.data == {"id": 1}


def test_fail_envelope() -> None:
    resp = ApiResponse.fail(ErrorCode.USER_NOT_FOUND, "用户不存在")
    assert resp.code == 23001
    assert resp.data is None
    assert resp.message == "用户不存在"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/core/test_response.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

`backend/src/agent_hify/core/response.py`:
```python
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from agent_hify.core.error_codes import ErrorCode

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    details: dict[str, object] | None = None

    @classmethod
    def ok(cls, data: T | None = None) -> "ApiResponse[T]":
        return cls(code=ErrorCode.SUCCESS.value, message="ok", data=data)

    @classmethod
    def fail(
        cls,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> "ApiResponse[T]":
        return cls(code=code.value, message=message, data=None, details=details)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/core/test_response.py -v && uv run mypy`
Expected: PASSED；mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add backend/src/agent_hify/core/response.py backend/tests/core/test_response.py
git commit -m "feat: unified ApiResponse envelope"
```

---

### Task 3: 异常体系 + FastAPI 处理器（始终 HTTP 200）+ 装配

**Files:**
- Create: `backend/src/agent_hify/core/exceptions.py`
- Modify: `backend/src/agent_hify/main.py`（注册异常处理器）
- Create: `backend/tests/core/test_exceptions.py`

**Interfaces:**
- Consumes: `ApiResponse`（Task 2）、`ErrorCode`（Task 1）。
- Produces:
  - `core.exceptions.AppError(code: ErrorCode, message: str, details: dict | None = None)` 及子类
    `NotFoundError / ValidationError / PermissionError / UnauthorizedError / ExternalServiceError / RateLimitError / CircuitOpenError`。
  - `core.exceptions.register_exception_handlers(app: FastAPI) -> None`：把 `AppError`、`RequestValidationError`、兜底 `Exception` 统一转 `ApiResponse`、**HTTP 200**。

- [ ] **Step 1: 写失败测试**

`backend/tests/core/test_exceptions.py`:
```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_hify.core.exceptions import (
    NotFoundError,
    register_exception_handlers,
)


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise NotFoundError(message="用户不存在", code=__import__(
            "agent_hify.core.error_codes", fromlist=["ErrorCode"]
        ).ErrorCode.USER_NOT_FOUND)

    @app.get("/bad")
    def bad(n: int) -> dict[str, int]:
        return {"n": n}

    return app


def test_app_error_returns_200_envelope() -> None:
    client = TestClient(_app())
    resp = client.get("/boom")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 23001
    assert body["data"] is None
    assert body["message"] == "用户不存在"


def test_validation_error_returns_200_param_invalid() -> None:
    client = TestClient(_app())
    resp = client.get("/bad", params={"n": "notint"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 10001
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/core/test_exceptions.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写异常体系与处理器**

`backend/src/agent_hify/core/exceptions.py`:
```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.logging import get_logger
from agent_hify.core.response import ApiResponse

logger = get_logger("agent_hify.exceptions")


class AppError(Exception):
    """业务异常基类；http_status 恒为 200，成败由 code 区分（docs/standards.md §6.2）。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class PermissionError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class ExternalServiceError(AppError):
    pass


class RateLimitError(AppError):
    pass


class CircuitOpenError(AppError):
    pass


def _envelope(code: ErrorCode, message: str, details: dict[str, object] | None = None) -> JSONResponse:
    body = ApiResponse.fail(code, message, details).model_dump()
    return JSONResponse(status_code=200, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(ErrorCode.PARAM_INVALID, "参数校验失败", {"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return _envelope(ErrorCode.INTERNAL_ERROR, "服务器内部错误")
```

- [ ] **Step 4: 装配到 main**

`backend/src/agent_hify/main.py` 改为（保留 `/health`，新增 logging 与异常处理器）：
```python
from __future__ import annotations

from fastapi import FastAPI

from agent_hify.core.exceptions import register_exception_handlers
from agent_hify.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="agent-hify", version="0.1.0")
    register_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/core/test_exceptions.py tests/test_health.py -v && uv run mypy`
Expected: PASSED；mypy 绿。

> 注：FastAPI 默认对 `RequestValidationError` 返回 422。本处理器覆盖为 200 + `ApiResponse`。`Exception` 兜底处理器在 `TestClient` 下需 `raise_server_exceptions=False` 才能观察到响应；本测试用例只验证 AppError 与校验两类，故无需该参数。

- [ ] **Step 6: 提交**

```bash
git add backend/src/agent_hify/core/exceptions.py backend/src/agent_hify/main.py backend/tests/core/test_exceptions.py
git commit -m "feat: AppError hierarchy and handlers returning ApiResponse (always 200)"
```

---

### Task 4: 分页（游标 + offset）

**Files:**
- Create: `backend/src/agent_hify/core/pagination.py`
- Create: `backend/tests/core/test_pagination.py`

**Interfaces:**
- Produces:
  - `core.pagination.CursorPage[T]`（`items: list[T]`、`next_cursor: str | None`、`has_more: bool`）。
  - `core.pagination.OffsetPage[T]`（`items: list[T]`、`total: int | None`、`page: int`、`page_size: int`）。
  - `encode_cursor(created_at: datetime, id: int) -> str`、`decode_cursor(cursor: str) -> tuple[datetime, int]`。

- [ ] **Step 1: 写失败测试**

`backend/tests/core/test_pagination.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone

from agent_hify.core.pagination import (
    CursorPage,
    OffsetPage,
    decode_cursor,
    encode_cursor,
)


def test_cursor_roundtrip() -> None:
    ts = datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc)
    cur = encode_cursor(ts, 42)
    got_ts, got_id = decode_cursor(cur)
    assert got_ts == ts
    assert got_id == 42


def test_cursor_page_shape() -> None:
    page: CursorPage[int] = CursorPage(items=[1, 2], next_cursor="abc", has_more=True)
    assert page.has_more is True


def test_offset_page_total_optional() -> None:
    page: OffsetPage[int] = OffsetPage(items=[1], total=None, page=2, page_size=20)
    assert page.total is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/core/test_pagination.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

`backend/src/agent_hify/core/pagination.py`:
```python
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class OffsetPage(BaseModel, Generic[T]):
    items: list[T]
    total: int | None = None
    page: int = 1
    page_size: int = 20


def encode_cursor(created_at: datetime, id: int) -> str:
    raw = json.dumps([created_at.isoformat(), id]).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
    ts_str, id_ = json.loads(raw)
    return datetime.fromisoformat(ts_str), int(id_)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/core/test_pagination.py -v && uv run mypy`
Expected: PASSED；mypy 绿。

- [ ] **Step 5: 提交**

```bash
git add backend/src/agent_hify/core/pagination.py backend/tests/core/test_pagination.py
git commit -m "feat: cursor and offset pagination helpers"
```

---

### Task 5: security（密码哈希 / 凭证加密 / JWT）+ config 扩展

**Files:**
- Create: `backend/src/agent_hify/core/security.py`
- Modify: `backend/src/agent_hify/core/config.py`（加 `secret_key`、`encryption_key`、`access_token_expire_minutes`）
- Modify: `backend/pyproject.toml`（加 `bcrypt`、`cryptography`、`pyjwt`）
- Create: `backend/tests/core/test_security.py`

**Interfaces:**
- Produces:
  - `core.security.hash_password(p: str) -> str`、`verify_password(p: str, hashed: str) -> bool`。
  - `core.security.encrypt(plaintext: str) -> bytes`、`decrypt(token: bytes) -> str`。
  - `core.security.create_access_token(*, user_id: int, role: str, workspace_id: int) -> str`、
    `decode_access_token(token: str) -> dict[str, object]`。

- [ ] **Step 1: 加依赖**

在 `backend/pyproject.toml` 的 `[project].dependencies` 追加：
```toml
    "bcrypt>=4.2",
    "cryptography>=44.0",
    "pyjwt>=2.10",
```
Run: `cd backend && uv sync`

- [ ] **Step 2: 写失败测试**

`backend/tests/core/test_security.py`:
```python
from __future__ import annotations

from agent_hify.core.security import (
    create_access_token,
    decode_access_token,
    decrypt,
    encrypt,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_credential_encrypt_roundtrip() -> None:
    token = encrypt("sk-abc-123")
    assert isinstance(token, bytes)
    assert decrypt(token) == "sk-abc-123"


def test_jwt_roundtrip() -> None:
    token = create_access_token(user_id=7, role="admin", workspace_id=1)
    claims = decode_access_token(token)
    assert claims["sub"] == "7"
    assert claims["role"] == "admin"
    assert claims["workspace_id"] == 1
```

- [ ] **Step 3: 扩展 config**

在 `backend/src/agent_hify/core/config.py` 的 `Settings` 内追加字段（保留已有 `database_url`/`redis_url`/`embedding_dim`）：
```python
    # 32 字节 url-safe base64 密钥（Fernet）；生产用环境变量覆盖
    encryption_key: str = "ZmFrZS1kZXYta2V5LTMyLWJ5dGVzLWxvbmctXzEyMw=="
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 1440
```

- [ ] **Step 4: 写 security**

`backend/src/agent_hify/core/security.py`:
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from agent_hify.core.config import get_settings

_settings = get_settings()
_fernet = Fernet(_settings.encryption_key.encode("ascii"))
_ALGORITHM = "HS256"


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(p: str, hashed: str) -> bool:
    return bcrypt.checkpw(p.encode("utf-8"), hashed.encode("ascii"))


def encrypt(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return _fernet.decrypt(token).decode("utf-8")


def create_access_token(*, user_id: int, role: str, workspace_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=_settings.access_token_expire_minutes
    )
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "workspace_id": workspace_id,
        "exp": expire,
    }
    return jwt.encode(claims, _settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, _settings.secret_key, algorithms=[_ALGORITHM])
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/core/test_security.py -v && uv run ruff check . && uv run mypy`
Expected: PASSED；ruff/mypy 绿。

- [ ] **Step 6: 提交**

```bash
git add backend/src/agent_hify/core/security.py backend/src/agent_hify/core/config.py backend/pyproject.toml backend/tests/core/test_security.py
git commit -m "feat: security — bcrypt password hash, fernet encryption, jwt tokens"
```

---

### Task 6: identity 数据模型 + 迁移 + 默认种子

**Files:**
- Create: `backend/src/agent_hify/modules/__init__.py`
- Create: `backend/src/agent_hify/modules/identity/__init__.py`
- Create: `backend/src/agent_hify/modules/identity/models.py`
- Create: `backend/alembic/versions/0002_identity.py`
- Create: `backend/tests/identity/__init__.py`
- Create: `backend/tests/identity/test_migration_seed.py`

**Interfaces:**
- Consumes: `core.db.Base`、`TimestampMixin`、`SoftDeleteMixin`（Task 1）、`security.hash_password`（Task 5）。
- Produces: ORM `Workspace`、`User`；迁移 `0002` 建表 `workspaces`/`users`（含 citext 扩展、`users` 部分唯一索引 `(workspace_id,email) WHERE deleted_at IS NULL`）、种子 `default` 工作区 + admin 用户 `admin@agent-hify.local` / `admin123`。

- [ ] **Step 1: 写失败测试**

`backend/tests/identity/__init__.py`: （空文件）

`backend/tests/identity/test_migration_seed.py`:
```python
from __future__ import annotations

import sqlalchemy as sa

from agent_hify.core.db import engine


def test_seed_default_workspace_and_admin() -> None:
    with engine.connect() as conn:
        ws = conn.execute(sa.text("SELECT name FROM workspaces WHERE name='default'")).first()
        admin = conn.execute(
            sa.text("SELECT role FROM users WHERE email='admin@agent-hify.local'")
        ).first()
    assert ws is not None
    assert admin is not None and admin[0] == "admin"


def test_users_email_partial_unique_index_exists() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='users' AND indexname='uq_users_workspace_email'"
            )
        ).first()
    assert row is not None
    assert "deleted_at IS NULL" in row[0]
```

- [ ] **Step 2: 运行测试确认失败**

前置：`cd deploy && docker compose up -d postgres`
Run: `cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/identity/test_migration_seed.py -v`
Expected: FAIL（表不存在）

- [ ] **Step 3: 写 ORM 模型**

`backend/src/agent_hify/modules/__init__.py`: （空文件）
`backend/src/agent_hify/modules/identity/__init__.py`: （空文件）

`backend/src/agent_hify/modules/identity/models.py`:
```python
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from agent_hify.core.db import Base, SoftDeleteMixin, TimestampMixin


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workspaces.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'member'")
    )
```

- [ ] **Step 4: 写迁移（建表 + 部分唯一索引 + 种子）**

`backend/alembic/versions/0002_identity.py`:
```python
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from agent_hify.core.security import hash_password

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "workspaces",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("email", postgresql_citext(), nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False, server_default="member"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_users_workspace_email ON users (workspace_id, email) "
        "WHERE deleted_at IS NULL"
    )

    # 种子：default 工作区 + admin 用户
    conn = op.get_bind()
    ws_id = conn.execute(
        sa.text("INSERT INTO workspaces (name) VALUES ('default') RETURNING id")
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO users (workspace_id, email, password_hash, role) "
            "VALUES (:ws, :email, :ph, 'admin')"
        ),
        {"ws": ws_id, "email": "admin@agent-hify.local", "ph": hash_password("admin123")},
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("workspaces")


def postgresql_citext() -> sa.types.TypeEngine[str]:
    from sqlalchemy.dialects.postgresql import CITEXT

    return CITEXT()
```

- [ ] **Step 5: 跑迁移并验证测试通过**

Run:
```bash
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run alembic upgrade head
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/identity/test_migration_seed.py -v
```
Expected: 迁移到 `0002`；两条测试 PASSED。

- [ ] **Step 6: ruff/mypy 并提交**

```bash
cd backend && uv run ruff check . && uv run mypy
git add backend/src/agent_hify/modules backend/alembic/versions/0002_identity.py backend/tests/identity
git commit -m "feat: identity models, migration with soft-delete partial unique index, default seed"
```

---

### Task 7: identity service + router（登录 / 当前用户 / 角色守卫）

**Files:**
- Create: `backend/src/agent_hify/modules/identity/schemas.py`
- Create: `backend/src/agent_hify/modules/identity/repository.py`
- Create: `backend/src/agent_hify/modules/identity/service.py`
- Create: `backend/src/agent_hify/modules/identity/router.py`
- Modify: `backend/src/agent_hify/main.py`（挂载 identity router）
- Create: `backend/tests/identity/test_auth_api.py`

**Interfaces:**
- Consumes: `core.security`（Task 5）、`core.exceptions`（Task 3）、`core.db.get_session`、ORM（Task 6）。
- Produces:
  - DTO `LoginIn(email,password)`、`TokenOut(access_token, token_type="bearer")`、`UserOut(id,email,role,workspace_id)`。
  - `identity.service.authenticate(session, email, password) -> TokenOut`（失败抛 `AppError(INVALID_CREDENTIALS)`）。
  - `identity.service.get_current_user(token, session) -> UserOut`（FastAPI 依赖）。
  - `identity.service.require_role(role) -> 依赖工厂`。
  - 路由：`POST /api/v1/auth/login -> ApiResponse[TokenOut]`、`GET /api/v1/auth/me -> ApiResponse[UserOut]`。

- [ ] **Step 1: 写失败测试**

`backend/tests/identity/test_auth_api.py`:
```python
from __future__ import annotations

from fastapi.testclient import TestClient

from agent_hify.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_login_success_returns_token() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"]


def test_login_wrong_password_returns_invalid_credentials() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "nope"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 21001


def test_me_with_token() -> None:
    client = _client()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    ).json()
    token = login["data"]["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"
```

- [ ] **Step 2: 运行测试确认失败**

前置：Postgres 在跑且已迁移到 `0002`。
Run: `cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/identity/test_auth_api.py -v`
Expected: FAIL（路由不存在）

- [ ] **Step 3: 写 schemas**

`backend/src/agent_hify/modules/identity/schemas.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    workspace_id: int
```
> 依赖 `email-validator`（`EmailStr` 需要）：在 `backend/pyproject.toml` 的 dependencies 追加 `"email-validator>=2.2"`，然后 `cd backend && uv sync`。

- [ ] **Step 4: 写 repository**

`backend/src/agent_hify/modules/identity/repository.py`:
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.identity.models import User


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()
```

- [ ] **Step 5: 写 service**

`backend/src/agent_hify/modules/identity/service.py`:
```python
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import PermissionError, UnauthorizedError
from agent_hify.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from agent_hify.modules.identity import repository
from agent_hify.modules.identity.schemas import TokenOut, UserOut


def authenticate(session: Session, email: str, password: str) -> TokenOut:
    user = repository.get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(ErrorCode.INVALID_CREDENTIALS, "邮箱或密码错误")
    token = create_access_token(
        user_id=user.id, role=user.role, workspace_id=user.workspace_id
    )
    return TokenOut(access_token=token)


def get_current_user(
    authorization: str = Header(default=""),
    session: Session = Depends(get_session),
) -> UserOut:
    if not authorization.lower().startswith("bearer "):
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "缺少 Bearer 令牌")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_access_token(token)
    except Exception as exc:  # jwt 异常归一
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "令牌无效或过期") from exc
    user = repository.get_user_by_id(session, int(str(claims["sub"])))
    if user is None:
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "用户不存在")
    return UserOut(
        id=user.id, email=user.email, role=user.role, workspace_id=user.workspace_id
    )


def require_role(role: str) -> Callable[[UserOut], UserOut]:
    def _dep(current: UserOut = Depends(get_current_user)) -> UserOut:
        if current.role != role:
            raise PermissionError(ErrorCode.PERMISSION_DENIED, "权限不足")
        return current

    return _dep
```

- [ ] **Step 6: 写 router**

`backend/src/agent_hify/modules/identity/router.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity import service
from agent_hify.modules.identity.schemas import LoginIn, TokenOut, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(
    payload: LoginIn, session: Session = Depends(get_session)
) -> ApiResponse[TokenOut]:
    token = service.authenticate(session, payload.email, payload.password)
    return ApiResponse.ok(token)


@router.get("/me")
def me(current: UserOut = Depends(service.get_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse.ok(current)
```

- [ ] **Step 7: 挂载 router**

`backend/src/agent_hify/main.py` 在 `register_exception_handlers(app)` 之后、`/health` 之前插入：
```python
    from agent_hify.modules.identity.router import router as identity_router

    app.include_router(identity_router)
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest tests/identity/test_auth_api.py -v && uv run ruff check . && uv run mypy`
Expected: 三条测试 PASSED；ruff/mypy 绿。

- [ ] **Step 9: 提交**

```bash
git add backend/src/agent_hify/modules/identity backend/src/agent_hify/main.py backend/pyproject.toml backend/tests/identity/test_auth_api.py
git commit -m "feat: identity auth — login, current user, role guard"
```

---

### Task 8: import-linter 分层契约扩展 + 全量绿灯

**Files:**
- Modify: `backend/pyproject.toml`（扩展 `[tool.importlinter]`）
- Create: `backend/tests/test_architecture_identity.py`

**Interfaces:**
- Produces: 分层契约，确保 `core` 不依赖任何业务模块、`identity` 只依赖 `core`/`observability`。

- [ ] **Step 1: 扩展契约**

把 `backend/pyproject.toml` 的 core forbidden 契约扩展并新增 identity 约束（替换 P0-1 的 `[tool.importlinter]` 段）：
```toml
[tool.importlinter]
root_package = "agent_hify"

[[tool.importlinter.contracts]]
name = "core is foundation (no internal deps)"
type = "forbidden"
source_modules = ["agent_hify.core"]
forbidden_modules = [
    "agent_hify.observability",
    "agent_hify.identity",
    "agent_hify.worker",
]

[[tool.importlinter.contracts]]
name = "identity depends only on core/observability"
type = "forbidden"
source_modules = ["agent_hify.modules.identity"]
forbidden_modules = [
    "agent_hify.modules",
    "agent_hify.worker",
]
```
> 说明：`forbidden_modules` 含 `agent_hify.modules` 会拦截 identity import 任何其它业务模块；但 identity 自身在 `agent_hify.modules.identity` 下——import-linter 的 forbidden 按"源是否 import 了被禁模块"判定，identity 内部互 import 不会命中（同包子模块不属于被禁的兄弟模块路径前缀冲突）。若误报，改为显式列出后续模块名。

- [ ] **Step 2: 写架构测试**

`backend/tests/test_architecture_identity.py`:
```python
from __future__ import annotations

import subprocess


def test_layering_contracts_hold() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```
> 执行时工作目录须为 `backend`（含 pyproject.toml）。

- [ ] **Step 3: 跑契约 + 全量测试**

前置：Postgres 在跑且迁移到 `0002`。
Run:
```bash
cd backend && uv run lint-imports
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run pytest -v
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```
Expected: import-linter "Contracts: N kept, 0 broken"；全部 pytest PASSED；ruff/mypy 绿。

- [ ] **Step 4: 提交**

```bash
git add backend/pyproject.toml backend/tests/test_architecture_identity.py
git commit -m "chore: extend import-linter contracts for identity layer"
```

---

## Self-Review

- **Spec coverage（对照 DESIGN §14 P0 第 2、3 项 + standards）**：
  - core：config（T5 扩展）✓ · db/session/Base（P0-1）+ Mixin（T1）✓ · 异常体系+处理器（T3）✓ · security 加密/哈希/token（T5）✓ · logging（T1）✓ · types/ContentBlock（T1）✓ · pagination 游标+offset（T4）✓ · ApiResponse 信封（T2）✓ · error_codes 注册表（T1）✓。
  - identity：登录鉴权（T7）✓ · 单工作区种子（T6）✓ · admin/member 角色 + 守卫（T6/T7）✓ · 软删+部分唯一索引（T6）✓。
  - **不在本计划**：外部调用韧性 `core/external.py`（移至 P0-3，models 为首个消费者）；models/observability（P0-3）；前端（P0-4）。
- **Placeholder scan**：无 TBD；每步含完整文件内容与命令。
- **Type consistency**：`ApiResponse.ok/fail`、`ErrorCode`、`AppError` 子类、`TimestampMixin/SoftDeleteMixin`、`encode/decode_cursor`、`hash_password/verify_password/encrypt/decrypt/create_access_token/decode_access_token`、`authenticate/get_current_user/require_role`、DTO `LoginIn/TokenOut/UserOut` 在定义与引用处一致。
- **完成判据（本计划）**：迁移到 `0002`；`POST /api/v1/auth/login` 用 admin 种子登录得令牌、`GET /api/v1/auth/me` 返回 admin；错误统一 `ApiResponse`+HTTP 200+模块错误码；`pytest`、`ruff`、`mypy`、`lint-imports` 全绿。

## 待执行者注意（已知风险点）

1. **bcrypt 72 字节上限**：超长密码会被截断；本期密码短，无需处理，后续如开放注册再加长度校验（归 `PARAM_INVALID`）。
2. **Fernet 默认 dev 密钥**：`encryption_key`/`secret_key` 仅供本地；部署必须用环境变量覆盖（DESIGN.md §13 密钥）。
3. **import-linter forbidden 规则**：Task 8 Step 1 的注释已说明潜在误报，若 `lint-imports` 报 identity 内部命中，改为显式列出 `agent_hify.modules.models` 等后续模块名。
4. **测试 DB 依赖**：T6–T8 需要真实 Postgres+citext+迁移；纯 core 测试（T1–T5）无需 DB。
