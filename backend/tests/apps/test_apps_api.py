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
