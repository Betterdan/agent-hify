from __future__ import annotations

import pytest

from agent_hify.core.db import SessionLocal
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import (
    ChatMessage,
    InvokeResult,
    ModelIn,
    ProviderIn,
)
from agent_hify.modules.observability import service as obs_service


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invoke_records_trace_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(ref: object, messages: object) -> InvokeResult:
        return InvokeResult(
            content="pong", tokens_in=3, tokens_out=1, cost=0.0002, finish_reason="stop"
        )

    monkeypatch.setattr(service.adapter, "invoke", fake_invoke)

    with SessionLocal() as s:
        prov = service.create_provider(
            s,
            1,
            ProviderIn(
                type="openai", name="p-gw", base_url=None, credentials={"api_key": "sk-x"}
            ),
        )
        m = service.create_model(
            s,
            1,
            ModelIn(
                provider_id=prov.id,
                model_key="gpt-4o-mini",
                type="llm",
                capabilities=[],
                embedding_dim=None,
                default_params={},
            ),
        )
        s.commit()

        before = len(obs_service.list_traces(s, 1, limit=1000))
        result = await service.invoke(
            s,
            model_id=m.id,
            workspace_id=1,
            messages=[ChatMessage(role="user", content="ping")],
        )
        s.commit()
        assert result.content == "pong"
        after = len(obs_service.list_traces(s, 1, limit=1000))
        assert after == before + 1
        usage = [u for u in obs_service.list_usage(s, 1) if u.model_id == m.id]
        assert usage and usage[0].tokens_in >= 3
