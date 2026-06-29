from __future__ import annotations

import uuid

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
async def test_list_tools_empty(app):
    """列表接口可达，返回 ApiResponse 格式，data 是 list。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_create_and_get_tool(app):
    """POST 创建 builtin echo 工具（唯一名称），GET 取回确认字段正确。"""
    unique_name = f"echo-{uuid.uuid4().hex[:8]}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/tools",
            json={"type": "builtin", "name": unique_name, "schema": {}, "config": {}},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["code"] == 0
        tool_id = body["data"]["id"]
        assert body["data"]["name"] == unique_name

        fetched = await client.get(f"/api/v1/tools/{tool_id}")
        assert fetched.status_code == 200
        fetched_body = fetched.json()
        assert fetched_body["code"] == 0
        assert fetched_body["data"]["name"] == unique_name


@pytest.mark.asyncio
async def test_tool_not_found(app):
    """获取不存在的工具返回 TOOL_NOT_FOUND=53001。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/tools/99999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 53001
