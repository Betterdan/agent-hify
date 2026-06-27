from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import (
    NotFoundError,
    register_exception_handlers,
)


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise NotFoundError(message="用户不存在", code=ErrorCode.USER_NOT_FOUND)

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
