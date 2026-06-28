from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
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
    # mode="json" 让 datetime 等转成 JSON 安全值，避免裸 json.dumps 在本处理器内崩成
    # 500、绕过始终 200 约定（standards §6.2）。注意：details 须已是 JSON 安全
    # （校验错误的 exc.errors() 含异常实例，由调用方先用 jsonable_encoder 净化）。
    body = ApiResponse[None].fail(code, message, details).model_dump(mode="json")
    return JSONResponse(status_code=200, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # exc.errors() 的 ctx 可能含异常实例等非 JSON 对象，先净化再入信封。
        errors = jsonable_encoder(exc.errors())
        return _envelope(ErrorCode.PARAM_INVALID, "参数校验失败", {"errors": errors})

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return _envelope(ErrorCode.INTERNAL_ERROR, "服务器内部错误")
