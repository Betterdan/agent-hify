from __future__ import annotations

import litellm
import pytest

from agent_hify.modules.models import adapter
from agent_hify.modules.models.adapter import ModelRef


@pytest.mark.asyncio
async def test_invoke_parses_litellm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Msg:
        content = "hello"

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Usage:
        prompt_tokens = 8
        completion_tokens = 3

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    async def fake_acompletion(**kwargs: object) -> _Resp:
        assert kwargs["model"] == "gpt-4o-mini"
        return _Resp()

    monkeypatch.setattr(adapter.litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(adapter.litellm, "completion_cost", lambda **_: 0.0009)

    ref = ModelRef(
        provider_id=1,
        provider_type="openai",
        model_key="gpt-4o-mini",
        api_key="sk-x",
        base_url=None,
        default_params={},
    )
    result = await adapter.invoke(ref, [{"role": "user", "content": "hi"}])
    assert result.content == "hello"
    assert result.tokens_in == 8
    assert result.tokens_out == 3
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_invoke_retries_litellm_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # I1 回归：litellm 的瞬时异常(不继承内置 ConnectionError/TimeoutError)须被重试。
    calls = {"n": 0}

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    async def flaky_acompletion(**kwargs: object) -> _Resp:
        calls["n"] += 1
        if calls["n"] < 2:
            raise litellm.APIConnectionError(message="boom", model="m", llm_provider="openai")
        return _Resp()

    monkeypatch.setattr(adapter.litellm, "acompletion", flaky_acompletion)
    monkeypatch.setattr(adapter.litellm, "completion_cost", lambda **_: 0.0)

    ref = ModelRef(
        provider_id=99,
        provider_type="openai",
        model_key="gpt-4o-mini",
        api_key="sk-x",
        base_url=None,
        default_params={},
    )
    result = await adapter.invoke(ref, [{"role": "user", "content": "hi"}])
    assert result.content == "ok"
    assert calls["n"] == 2  # 第一次瞬时失败被重试


@pytest.mark.asyncio
async def test_embed_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        data = [{"embedding": [0.1, 0.2]}]

    async def fake_aembedding(**kwargs: object) -> _Resp:
        return _Resp()

    monkeypatch.setattr(adapter.litellm, "aembedding", fake_aembedding)
    ref = ModelRef(
        provider_id=1,
        provider_type="openai",
        model_key="text-embedding-3-small",
        api_key="sk-x",
        base_url=None,
        default_params={},
    )
    vecs = await adapter.embed(ref, ["hi"])
    assert vecs == [[0.1, 0.2]]
