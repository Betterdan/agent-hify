from __future__ import annotations

import litellm
from pydantic import BaseModel, Field

from agent_hify.core.external import call_with_resilience
from agent_hify.modules.models.schemas import InvokeResult

_TIMEOUT = 30.0


class ModelRef(BaseModel):
    provider_type: str
    model_key: str
    api_key: str | None = None
    base_url: str | None = None
    default_params: dict[str, object] = Field(default_factory=dict)


async def invoke(ref: ModelRef, messages: list[dict[str, str]]) -> InvokeResult:
    async def _call() -> InvokeResult:
        resp = await litellm.acompletion(
            model=ref.model_key,
            messages=messages,
            api_key=ref.api_key,
            api_base=ref.base_url,
            **ref.default_params,
        )
        choice = resp.choices[0]
        usage = resp.usage
        try:
            cost = float(litellm.completion_cost(completion_response=resp))
        except Exception:
            cost = 0.0
        return InvokeResult(
            content=choice.message.content or "",
            tokens_in=int(usage.prompt_tokens),
            tokens_out=int(usage.completion_tokens),
            cost=cost,
            finish_reason=str(choice.finish_reason or "stop"),
        )

    return await call_with_resilience(ref.provider_type, _call, timeout=_TIMEOUT)


async def embed(ref: ModelRef, texts: list[str]) -> list[list[float]]:
    async def _call() -> list[list[float]]:
        resp = await litellm.aembedding(
            model=ref.model_key,
            input=texts,
            api_key=ref.api_key,
            api_base=ref.base_url,
        )
        return [list(item["embedding"]) for item in resp.data]

    return await call_with_resilience(ref.provider_type, _call, timeout=_TIMEOUT)
