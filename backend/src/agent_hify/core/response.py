from __future__ import annotations

from pydantic import BaseModel

from agent_hify.core.error_codes import ErrorCode


class ApiResponse[T](BaseModel):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    details: dict[str, object] | None = None

    @classmethod
    def ok(cls, data: T | None = None) -> ApiResponse[T]:
        return cls(code=ErrorCode.SUCCESS.value, message="ok", data=data)

    @classmethod
    def fail(
        cls,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> ApiResponse[T]:
        return cls(code=code.value, message=message, data=None, details=details)
