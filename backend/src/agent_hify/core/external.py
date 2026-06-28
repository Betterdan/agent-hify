from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import CircuitOpenError, ExternalServiceError
from agent_hify.core.logging import get_logger

logger = get_logger("agent_hify.external")

_RETRYABLE = (ConnectionError, TimeoutError, asyncio.TimeoutError)


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.reset_seconds:
            # 半开：放一个探测
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._opened_at = time.monotonic()


_breakers: dict[str, CircuitBreaker] = {}
_semaphores: dict[str, asyncio.Semaphore] = {}
_MAX_CONCURRENCY = 10


def _breaker(key: str) -> CircuitBreaker:
    return _breakers.setdefault(key, CircuitBreaker())


def _semaphore(key: str) -> asyncio.Semaphore:
    if key not in _semaphores:
        _semaphores[key] = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _semaphores[key]


async def call_with_resilience[T](
    key: str,
    fn: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    max_retries: int = 2,
    retry_backoff: float = 0.05,
    retryable: tuple[type[BaseException], ...] = _RETRYABLE,
) -> T:
    """带超时/重试/熔断/舱壁的外部调用封装。

    core 保持框架无关：`retryable` 由调用方(知道具体 SDK 异常类型的 adapter)传入，
    例如 litellm 的瞬时异常不继承内置 ConnectionError/TimeoutError，须显式纳入才会被重试。
    仅**可重试**(瞬时/服务侧)失败计入熔断；非可重试(鉴权/参数等客户端错误)不计入，
    以免一个配置错误的 provider 把整条 key 的熔断打开、连累后续请求。
    """
    breaker = _breaker(key)
    if not breaker.allow():
        raise CircuitOpenError(ErrorCode.CIRCUIT_OPEN, f"外部服务熔断中: {key}")

    last_exc: BaseException | None = None
    async with _semaphore(key):
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(fn(), timeout=timeout)
                breaker.record_success()
                return result
            except retryable as exc:
                last_exc = exc
                breaker.record_failure()
                if attempt < max_retries:
                    await asyncio.sleep(retry_backoff * (2**attempt))
            except Exception as exc:  # 非可重试(客户端错误)：不计入熔断，直接失败
                logger.warning("external call failed (non-retryable): %s", exc)
                raise ExternalServiceError(
                    ErrorCode.EXTERNAL_ERROR, f"外部服务调用失败: {key}"
                ) from exc

    raise ExternalServiceError(
        ErrorCode.EXTERNAL_TIMEOUT, f"外部服务调用失败(重试耗尽): {key}"
    ) from last_exc
