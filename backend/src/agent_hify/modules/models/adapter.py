from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import litellm
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pydantic import BaseModel, Field

from agent_hify.core.external import call_with_resilience
from agent_hify.modules.models.schemas import InvokeResult

_TIMEOUT = 30.0

# litellm 的瞬时异常**不**继承内置 ConnectionError/TimeoutError，须显式列出才会被韧性层重试。
# 鉴权/参数类(AuthenticationError/BadRequestError 等)故意不在此列：它们是客户端错误，
# 重试无益且不应计入熔断。
_RETRYABLE: tuple[type[BaseException], ...] = (
    Timeout,
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


class ModelRef(BaseModel):
    provider_id: int
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

    # 熔断/舱壁 key 细化到 provider 实例 + 操作：避免某个配置错误的 provider 连累
    # 同类型其它 provider/workspace，且让 completion 与 embedding 互不抢占并发名额。
    return await call_with_resilience(
        f"{ref.provider_id}:invoke", _call, timeout=_TIMEOUT, retryable=_RETRYABLE
    )


async def embed(ref: ModelRef, texts: list[str]) -> list[list[float]]:
    async def _call() -> list[list[float]]:
        resp = await litellm.aembedding(
            model=ref.model_key,
            input=texts,
            api_key=ref.api_key,
            api_base=ref.base_url,
        )
        return [list(item["embedding"]) for item in resp.data]

    return await call_with_resilience(
        f"{ref.provider_id}:embed", _call, timeout=_TIMEOUT, retryable=_RETRYABLE
    )


_STREAM_CONNECT_TIMEOUT = 60.0


async def invoke_stream(
    ref: ModelRef,
    messages: list[dict[str, str]],
    usage_sink: dict[str, object] | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用模型，逐段 yield 文本增量。

    用量经 `usage_sink`（可变 out 参数）回传：流结束后写入
    {"tokens_in","tokens_out","cost"}；provider 不支持 usage 时回退 0。
    """

    async def _open() -> Any:
        return await litellm.acompletion(
            model=ref.model_key,
            messages=messages,
            api_key=ref.api_key,
            api_base=ref.base_url,
            stream=True,
            stream_options={"include_usage": True},
            **ref.default_params,
        )

    stream = await asyncio.wait_for(_open(), timeout=_STREAM_CONNECT_TIMEOUT)

    final_chunk: object = None
    async for chunk in stream:
        final_chunk = chunk
        try:
            delta = chunk.choices[0].delta.content
        except (IndexError, AttributeError):
            delta = None
        if delta:
            yield delta

    if usage_sink is not None:
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        usage = getattr(final_chunk, "usage", None)
        if usage is not None:
            tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
        try:
            cost = float(litellm.completion_cost(completion_response=final_chunk))
        except Exception:
            cost = 0.0
        usage_sink["tokens_in"] = tokens_in
        usage_sink["tokens_out"] = tokens_out
        usage_sink["cost"] = cost
