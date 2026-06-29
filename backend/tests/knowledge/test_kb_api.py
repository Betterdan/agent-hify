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
async def test_list_kbs_returns_200(app):
    """列表接口可达，返回 ApiResponse 格式。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/knowledge_bases")
    assert resp.status_code == 200
    body = resp.json()
    assert "code" in body


@pytest.mark.asyncio
async def test_kb_not_found(app):
    """获取不存在的知识库返回 KB_NOT_FOUND=43001。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/knowledge_bases/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 43001


@pytest.mark.asyncio
async def test_doc_not_found(app):
    """获取不存在的文档返回 DOC_NOT_FOUND=43002。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/documents/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 43002
