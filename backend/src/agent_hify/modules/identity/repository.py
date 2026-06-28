from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.identity.models import User


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()
