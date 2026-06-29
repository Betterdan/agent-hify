from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from agent_hify.main import create_app
from agent_hify.modules.models import adapter as models_adapter


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


def _create_app(client: TestClient, h: dict[str, str], model_id: int) -> int:
    created = client.post(
        "/api/v1/apps",
        headers=h,
        json={
            "type": "chat",
            "name": f"chat-{uuid.uuid4().hex[:8]}",
            "config": {"model_id": model_id, "system_prompt": "你是助手"},
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
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        events.append((event, json.loads(data)))
    return events


@pytest.mark.integration
def test_chat_streams_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(
        ref: object,
        messages: object,
        usage_sink: dict[str, object] | None = None,
        extra_params: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        for token in ["你", "好", "！"]:
            yield token
        if usage_sink is not None:
            usage_sink["tokens_in"] = 5
            usage_sink["tokens_out"] = 3
            usage_sink["cost"] = 0.001

    monkeypatch.setattr(models_adapter, "invoke_stream", fake_stream)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)
    app_id = _create_app(client, h, model_id)

    resp = client.post(f"/api/v1/apps/{app_id}/chat", headers=h, json={"message": "在吗"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds.count("message") == 3
    assert "usage" in kinds
    assert "done" in kinds

    deltas = "".join(d["delta"] for e, d in events if e == "message")
    assert deltas == "你好！"

    usage_evt = next(d for e, d in events if e == "usage")
    assert usage_evt["tokens_in"] == 5
    assert usage_evt["tokens_out"] == 3

    done_evt = next(d for e, d in events if e == "done")
    conv_id = done_evt["conversation_id"]

    # conversations list
    convs = client.get(f"/api/v1/apps/{app_id}/conversations", headers=h)
    assert convs.json()["code"] == 0
    assert any(c["id"] == conv_id for c in convs.json()["data"]["items"])

    # messages list: user + assistant
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h)
    items = msgs.json()["data"]["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[1]["content"][0]["text"] == "你好！"


@pytest.mark.integration
def test_chat_continues_existing_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_stream(
        ref: object,
        messages: object,
        usage_sink: dict[str, object] | None = None,
        extra_params: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        yield "ok"

    monkeypatch.setattr(models_adapter, "invoke_stream", fake_stream)

    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    model_id = _create_model(client, h)
    app_id = _create_app(client, h, model_id)

    first = client.post(f"/api/v1/apps/{app_id}/chat", headers=h, json={"message": "第一句"})
    conv_id = next(d for e, d in _parse_sse(first.text) if e == "done")["conversation_id"]

    second = client.post(
        f"/api/v1/apps/{app_id}/chat",
        headers=h,
        json={"conversation_id": conv_id, "message": "第二句"},
    )
    done = next(d for e, d in _parse_sse(second.text) if e == "done")
    assert done["conversation_id"] == conv_id

    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages", headers=h)
    assert len(msgs.json()["data"]["items"]) == 4


@pytest.mark.integration
def test_chat_missing_app_yields_error_event() -> None:
    client = TestClient(create_app())
    h = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.post("/api/v1/apps/99999999/chat", headers=h, json={"message": "x"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == 60003
