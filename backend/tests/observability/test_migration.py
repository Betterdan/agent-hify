from __future__ import annotations

import pytest
import sqlalchemy as sa

from agent_hify.core.db import engine


@pytest.mark.integration
def test_traces_and_usage_tables_exist() -> None:
    insp = sa.inspect(engine)
    names = set(insp.get_table_names())
    assert {"traces", "usage_daily"}.issubset(names)


@pytest.mark.integration
def test_usage_daily_unique_nulls_not_distinct() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='usage_daily' AND indexname='uq_usage_daily_dim'"
            )
        ).first()
    assert row is not None
    assert "NULLS NOT DISTINCT" in row[0].upper()
