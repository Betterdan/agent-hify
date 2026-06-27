from __future__ import annotations

import pytest
import sqlalchemy as sa

from agent_hify.core.db import engine


@pytest.mark.integration
def test_pgvector_extension_present() -> None:
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
    assert row is not None
