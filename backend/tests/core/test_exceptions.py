from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import (
    NotFoundError,
    register_exception_handlers,
)


class _Body(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _no_bad(cls, v: str) -> str:
        if v == "bad":
            # ValueError 会被 Pydantic 放进 error 的 ctx（异常实例，非 JSON 原生），
            # 用于复现校验错误信封序列化崩溃（I1）。
            raise ValueError("name 不能为 bad")
        return v


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise NotFoundError(message="用户不存在", code=ErrorCode.USER_NOT_FOUND)

    @app.get("/bad")
    def bad(n: int) -> dict[str, int]:
        return {"n": n}

    @app.post("/validate")
    def validate(body: _Body) -> dict[str, str]:
        return {"name": body.name}

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


def test_validation_error_with_non_json_ctx_returns_200() -> None:
    # I1 回归：校验错误 ctx 含异常实例时，信封不得崩成 500，须仍返回 200 + 10001。
    client = TestClient(_app())
    resp = client.post("/validate", json={"name": "bad"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 10001
    assert "errors" in body["details"]
