from __future__ import annotations

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import UnauthorizedError
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


def resolve_user(session: Session, token: str) -> UserOut:
    """从令牌解析当前用户（纯函数、框架无关；Web 层 DI 见 deps.py）。"""
    try:
        claims = decode_access_token(token)
        user_id = int(str(claims["sub"]))
    except Exception as exc:  # jwt 异常 / 缺 sub / sub 非数字 一律归一为未授权(401 而非 500)
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "令牌无效或过期") from exc
    user = repository.get_user_by_id(session, user_id)
    if user is None:
        raise UnauthorizedError(ErrorCode.UNAUTHORIZED, "用户不存在")
    return UserOut(id=user.id, email=user.email, role=user.role, workspace_id=user.workspace_id)
