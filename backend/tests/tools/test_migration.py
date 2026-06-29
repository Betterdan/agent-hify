from __future__ import annotations

from sqlalchemy import inspect

from agent_hify.core.db import engine


def test_tools_table_exists():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "tools" in tables


def test_tools_columns():
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("tools")}
    required = {
        "id", "workspace_id", "type", "name", "schema",
        "credentials_encrypted", "config", "enabled",
    }
    assert required.issubset(cols)
