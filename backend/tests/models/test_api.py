from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import InvokeResult


def _token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    )
    return str(r.json()["data"]["access_token"])


@pytest.mark.integration
def test_configure_model_and_invoke_records(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(ref: object, messages: object) -> InvokeResult:
        return InvokeResult(
            content="pong", tokens_in=2, tokens_out=1, cost=0.0, finish_reason="stop"
        )

    monkeypatch.setattr(service.adapter, "invoke", fake_invoke)
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    unique = uuid.uuid4().hex[:8]

    prov = client.post(
        "/api/v1/model-providers",
        headers=h,
        json={
            "type": "openai",
            "name": f"api-prov-{unique}",
            "credentials": {"api_key": "sk-x"},
        },
    )
    assert prov.json()["code"] == 0
    pid = prov.json()["data"]["id"]

    model = client.post(
        "/api/v1/models",
        headers=h,
        json={"provider_id": pid, "model_key": "gpt-4o-mini", "type": "llm"},
    )
    mid = model.json()["data"]["id"]

    conn = client.post(f"/api/v1/models/{mid}/test-connectivity", headers=h)
    assert conn.json()["data"]["ok"] is True

    inv = client.post(
        f"/api/v1/models/{mid}/invoke",
        headers=h,
        json={"messages": [{"role": "user", "content": "ping"}]},
    )
    assert inv.json()["data"]["content"] == "pong"

    traces = client.get("/api/v1/observability/traces", headers=h)
    assert len(traces.json()["data"]) >= 1


@pytest.mark.integration
def test_create_provider_invalid_type_returns_param_invalid() -> None:
    # #10 回归：非法 type 应在 Pydantic 层即拒为 PARAM_INVALID(10001)，而非落到 DB 约束→500。
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.post(
        "/api/v1/model-providers",
        headers=h,
        json={"type": "not-a-real-type", "name": "x", "credentials": {}},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 10001
