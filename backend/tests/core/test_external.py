from __future__ import annotations

import asyncio

import pytest

from agent_hify.core.exceptions import CircuitOpenError, ExternalServiceError
from agent_hify.core.external import CircuitBreaker, call_with_resilience


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(fail_threshold=2, reset_seconds=60)
    assert cb.allow() is True
    cb.record_failure()
    cb.record_failure()
    assert cb.allow() is False  # 已打开


@pytest.mark.asyncio
async def test_retry_then_success() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("boom")
        return "ok"

    out = await call_with_resilience("k1", flaky, timeout=1.0, max_retries=2)
    assert out == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_timeout_raises_external_error() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.2)
        return "late"

    with pytest.raises(ExternalServiceError):
        await call_with_resilience("k2", slow, timeout=0.01, max_retries=0)


@pytest.mark.asyncio
async def test_open_circuit_fast_fails() -> None:
    async def always_fail() -> str:
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ExternalServiceError):
            await call_with_resilience("k3", always_fail, timeout=1.0, max_retries=0)
    with pytest.raises(CircuitOpenError):
        await call_with_resilience("k3", always_fail, timeout=1.0, max_retries=0)


@pytest.mark.asyncio
async def test_custom_retryable_tuple_is_retried() -> None:
    # I1 回归：默认 _RETRYABLE 只含内置异常，真实 SDK(如 litellm)的瞬时异常须经
    # retryable 参数显式纳入才会被重试，否则落入"非可重试"分支永不重试。
    class MyTransient(Exception):
        pass

    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise MyTransient("boom")
        return "ok"

    out = await call_with_resilience(
        "kr", flaky, timeout=1.0, max_retries=2, retryable=(MyTransient,)
    )
    assert out == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_non_retryable_does_not_trip_breaker() -> None:
    # M6 回归：非可重试异常(鉴权/参数等客户端错误)不应计入熔断，
    # 否则一个配置错误的 provider 会把整条 key 的熔断打开、连累后续请求。
    async def bad() -> str:
        raise ValueError("client error")

    for _ in range(10):
        with pytest.raises(ExternalServiceError):
            await call_with_resilience("kn", bad, timeout=1.0, max_retries=0)
    # 熔断未打开：第 11 次仍是 ExternalServiceError 而非 CircuitOpenError
    with pytest.raises(ExternalServiceError):
        await call_with_resilience("kn", bad, timeout=1.0, max_retries=0)
