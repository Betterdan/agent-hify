from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


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
