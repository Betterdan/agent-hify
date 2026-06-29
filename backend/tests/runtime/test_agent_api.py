from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app
from agent_hify.modules.models import service as models_service
from agent_hify.modules.models.schemas import InvokeResult


def _token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@agent-hify.local", "password": "admin123"},
    )
    return str(r.json()["data"]["access_token"])


def _create_model(client: TestClient, h: dict[str, str]) -> int:
    unique = uuid.uuid4().hex[:8]
    prov = client.post(
        "/api/v1/model-providers",
        headers=h,
        json={"type": "openai", "name": f"prov-{unique}", "credentials": {"api_key": "sk-x"}},
    )
    pid = prov.json()["data"]["id"]
    model = client.post(
        "/api/v1/models",
        headers=h,
        json={"provider_id": pid, "model_key": "gpt-4o-mini", "type": "llm"},
    )
    return int(model.json()["data"]["id"])


def _create_agent_app(
    client: TestClient,
    h: dict[str, str],
    model_id: int,
    tool_ids: list[int] | None = None,
) -> int:
    created = client.post(
        "/api/v1/apps",
        headers=h,
        json={
            "type": "agent",
            "name": f"agent-{uuid.uuid4().hex[:8]}",
            "config": {
                "model_id": model_id,
                "system_prompt": "你是 Agent",
                "tool_ids": tool_ids or [],
            },
        },
    )
    return int(created.json()["data"]["id"])


def _parse_sse(text: str) -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    events: list[tuple[str, dict]] = []  # type: ignore[type-arg]
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = line[len("data: "):]
        events.append((event, json.loads(data)))
    return events


@pytest.mark.integration
def test_agent_run_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent 无工具：invoke_with_tools 直接返回最终答案，SSE 含 done 事件。"""
    mock = AsyncMock(
        return_value=InvokeResult(
            content="Agent 回复",
            tokens_in=5,
            tokens_out=10,
            cost=0.001,
            finish_reason="stop",
            tool_calls=None,
        )
    )
    monkeypatch.setattr(models_service, "invoke_with_tools", mock)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)
    app_id = _create_agent_app(client, h, model_id)

    resp = client.post(f"/api/v1/apps/{app_id}/run", headers=h, json={"message": "你好"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert "done" in kinds
    assert "error" not in kinds

    done_evt = next(d for e, d in events if e == "done")
    assert "conversation_id" in done_evt
    assert "message_id" in done_evt


@pytest.mark.integration
def test_agent_tool_call_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent 工具调用：第一轮返回 tool_calls，产生 step 事件；第二轮返回最终答案。"""
    call1 = InvokeResult(
        content="",
        tokens_in=5,
        tokens_out=10,
        cost=0.001,
        finish_reason="tool_calls",
        tool_calls=[
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "echo", "arguments": '{"text":"hello"}'},
            }
        ],
    )
    call2 = InvokeResult(
        content="最终答案",
        tokens_in=5,
        tokens_out=10,
        cost=0.001,
        finish_reason="stop",
        tool_calls=None,
    )
    mock = AsyncMock(side_effect=[call1, call2])
    monkeypatch.setattr(models_service, "invoke_with_tools", mock)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)

    # 获取或创建 builtin echo 工具（幂等：名称有唯一约束，先查再建）
    list_resp = client.get("/api/v1/tools", headers=h)
    existing = next(
        (t for t in list_resp.json()["data"] if t["name"] == "echo"),
        None,
    )
    if existing:
        tool_id = existing["id"]
    else:
        tool_resp = client.post(
            "/api/v1/tools",
            headers=h,
            json={"type": "builtin", "name": "echo", "schema": {}, "config": {}},
        )
        assert tool_resp.json()["code"] == 0
        tool_id = tool_resp.json()["data"]["id"]

    app_id = _create_agent_app(client, h, model_id, tool_ids=[tool_id])

    resp = client.post(f"/api/v1/apps/{app_id}/run", headers=h, json={"message": "你好"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]

    step_events = [(e, d) for e, d in events if e == "step"]
    assert len(step_events) >= 1
    assert step_events[0][1]["tool_name"] == "echo"

    assert "done" in kinds
    assert "error" not in kinds
