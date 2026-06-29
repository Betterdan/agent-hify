from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from agent_hify.main import create_app
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut

FAKE_USER = UserOut(id=1, workspace_id=1, email="a@b.com", role="admin")


@pytest.fixture
def app():
    _app = create_app()
    _app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return _app


@pytest.mark.asyncio
async def test_create_annotation(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/observability/annotations",
            json={"message_id": 9999, "rating": 1, "comment": "很好"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["rating"] == 1
    assert data["comment"] == "很好"
    assert data["message_id"] == 9999


@pytest.mark.asyncio
async def test_upsert_annotation(app):
    """同一 workspace+message 再次 POST 应更新，不新建。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/observability/annotations",
            json={"message_id": 8888, "rating": 1},
        )
        resp = await client.post(
            "/api/v1/observability/annotations",
            json={"message_id": 8888, "rating": -1, "comment": "改变主意"},
        )
    data = resp.json()["data"]
    assert data["rating"] == -1

    # GET 应只返回一条
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r2 = await client.get(
            "/api/v1/observability/annotations?message_id=8888",
        )
    assert len(r2.json()["data"]) == 1


@pytest.mark.asyncio
async def test_eval_hook(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/observability/eval-hook",
            json={"name": "accuracy_test", "payload": {"value": 0.9}},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] > 0


@pytest.mark.asyncio
async def test_traces_filter_by_status(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/observability/traces?status=ok&days=1",
        )
    assert resp.status_code == 200
    for item in resp.json()["data"]:
        assert item["status"] == "ok"
