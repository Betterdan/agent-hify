from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from agent_hify.core.config import get_settings
from agent_hify.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_me_without_token_returns_unauthorized() -> None:
    # 无 DB：缺 Bearer 头在依赖层即拒，不查库。
    resp = _client().get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["code"] == 11001


def test_me_token_missing_sub_returns_unauthorized() -> None:
    # M2 回归：签名有效但缺 sub 的令牌须归一为 401(11001) 而非 500。无 DB（解析即拒）。
    token = jwt.encode({"role": "admin"}, get_settings().secret_key, algorithm="HS256")
    resp = _client().get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 11001


@pytest.mark.integration
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


@pytest.mark.integration
def test_login_wrong_password_returns_invalid_credentials() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "nope"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 21001


@pytest.mark.integration
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
