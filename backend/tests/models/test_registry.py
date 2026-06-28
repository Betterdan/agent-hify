from __future__ import annotations

import uuid

import pytest

from agent_hify.core.db import SessionLocal
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import ModelIn, ProviderIn


@pytest.mark.integration
def test_create_provider_encrypts_and_create_model() -> None:
    unique = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        prov = service.create_provider(
            s,
            workspace_id=1,
            dto=ProviderIn(
                type="openai",
                name=f"openai-{unique}",
                base_url=None,
                credentials={"api_key": "sk-secret"},
            ),
        )
        s.commit()
        assert prov.id > 0
        # 凭证不明文：解密后才等于原值
        creds = service.get_decrypted_credentials(s, prov.id)
        assert creds["api_key"] == "sk-secret"

        m = service.create_model(
            s,
            workspace_id=1,
            dto=ModelIn(
                provider_id=prov.id,
                model_key="gpt-4o-mini",
                type="llm",
                capabilities=["vision"],
                embedding_dim=None,
                default_params={},
            ),
        )
        s.commit()
        assert m.id > 0
        assert any(x.id == m.id for x in service.list_models(s, workspace_id=1))
