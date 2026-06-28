from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import PermissionError, UnauthorizedError
from agent_hify.modules.identity import service
from agent_hify.modules.identity.schemas import UserOut


def get_current_user(
    authorization: str = Header(default=""),
    session: Session = Depends(get_session),
) -> UserOut:
    """Web 层鉴权依赖：解析 Bearer 头并委托纯 service.resolve_user。"""
    if not authorization.lower().startswith("bearer "):
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "缺少 Bearer 令牌")
    token = authorization.split(" ", 1)[1]
    return service.resolve_user(session, token)


def require_role(role: str) -> Callable[[UserOut], UserOut]:
    def _dep(current: UserOut = Depends(get_current_user)) -> UserOut:
        if current.role != role:
            raise PermissionError(ErrorCode.PERMISSION_DENIED, "权限不足")
        return current

    return _dep
