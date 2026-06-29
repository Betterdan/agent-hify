from __future__ import annotations

from sqlalchemy import inspect, text

from agent_hify.core.db import engine


def test_knowledge_tables_exist():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "knowledge_bases" in tables
    assert "documents" in tables
    assert "chunks" in tables


def test_chunks_has_vector_column():
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='chunks' AND column_name='embedding'"
        ))
        row = result.fetchone()
        assert row is not None
        assert row[0] in ("USER-DEFINED", "vector")
