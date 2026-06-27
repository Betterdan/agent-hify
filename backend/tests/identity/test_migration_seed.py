from __future__ import annotations

import pytest
import sqlalchemy as sa

from agent_hify.core.db import engine


@pytest.mark.integration
def test_seed_default_workspace_and_admin() -> None:
    with engine.connect() as conn:
        ws = conn.execute(sa.text("SELECT name FROM workspaces WHERE name='default'")).first()
        admin = conn.execute(
            sa.text("SELECT role FROM users WHERE email='admin@agent-hify.local'")
        ).first()
    assert ws is not None
    assert admin is not None and admin[0] == "admin"


@pytest.mark.integration
def test_users_email_partial_unique_index_exists() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='users' AND indexname='uq_users_workspace_email'"
            )
        ).first()
    assert row is not None
    assert "deleted_at IS NULL" in row[0]
