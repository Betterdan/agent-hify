from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.identity.models import User


def get_user_by_email(session: Session, email: str) -> User | None:
    # 不变量：唯一约束是 (workspace_id, email) 部分唯一索引，故同一 email 可跨 workspace
    # 各存一份。当前为单工作区，全局按 email 查安全。**多工作区落地前必改**：否则同 email
    # 跨 workspace 会触发 scalar_one_or_none 的 MultipleResultsFound（登录需带 workspace 上下文）。
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()
