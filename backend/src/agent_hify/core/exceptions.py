from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.logging import get_logger
from agent_hify.core.response import ApiResponse

logger = get_logger("agent_hify.exceptions")


class AppError(Exception):
    """业务异常基类；http_status 恒为 200，成败由 code 区分（docs/standards.md §6.2）。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class PermissionError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class ExternalServiceError(AppError):
    pass


class RateLimitError(AppError):
    pass


class CircuitOpenError(AppError):
    pass


def _envelope(
    code: ErrorCode, message: str, details: dict[str, object] | None = None
) -> JSONResponse:
    body = ApiResponse[None].fail(code, message, details).model_dump()
    return JSONResponse(status_code=200, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(ErrorCode.PARAM_INVALID, "参数校验失败", {"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return _envelope(ErrorCode.INTERNAL_ERROR, "服务器内部错误")
