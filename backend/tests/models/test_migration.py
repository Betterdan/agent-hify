from __future__ import annotations

import pytest
import sqlalchemy as sa

from agent_hify.core.db import engine


@pytest.mark.integration
def test_model_tables_exist() -> None:
    insp = sa.inspect(engine)
    names = set(insp.get_table_names())
    assert {"model_providers", "models"}.issubset(names)


@pytest.mark.integration
def test_models_partial_unique_index() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='models' AND indexname='uq_models_provider_key'"
            )
        ).first()
    assert row is not None and "deleted_at IS NULL" in row[0]
