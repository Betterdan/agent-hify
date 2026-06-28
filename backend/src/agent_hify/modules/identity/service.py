from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import PermissionError, UnauthorizedError
from agent_hify.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from agent_hify.modules.identity import repository
from agent_hify.modules.identity.schemas import TokenOut, UserOut


def authenticate(session: Session, email: str, password: str) -> TokenOut:
    user = repository.get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(ErrorCode.INVALID_CREDENTIALS, "邮箱或密码错误")
    token = create_access_token(user_id=user.id, role=user.role, workspace_id=user.workspace_id)
    return TokenOut(access_token=token)


def get_current_user(
    authorization: str = Header(default=""),
    session: Session = Depends(get_session),
) -> UserOut:
    if not authorization.lower().startswith("bearer "):
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "缺少 Bearer 令牌")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_access_token(token)
    except Exception as exc:  # jwt 异常归一
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "令牌无效或过期") from exc
    user = repository.get_user_by_id(session, int(str(claims["sub"])))
    if user is None:
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "用户不存在")
    return UserOut(id=user.id, email=user.email, role=user.role, workspace_id=user.workspace_id)


def require_role(role: str) -> Callable[[UserOut], UserOut]:
    def _dep(current: UserOut = Depends(get_current_user)) -> UserOut:
        if current.role != role:
            raise PermissionError(ErrorCode.PERMISSION_DENIED, "权限不足")
        return current

    return _dep
