from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from agent_hify.core.db import SessionLocal


@pytest.fixture(scope="session")
def db_session() -> Generator[Session, None, None]:
    """Session 级 DB fixture，供集成测试复用。测试结束后回滚并关闭连接。

    用法（需标记 @pytest.mark.integration）：
        def test_something(db_session: Session) -> None:
            ...
    """
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
