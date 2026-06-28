from __future__ import annotations

import json

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.core.security import decrypt, encrypt
from agent_hify.modules.models import repository
from agent_hify.modules.models.models import Model, ModelProvider
from agent_hify.modules.models.schemas import (
    ModelIn,
    ModelOut,
    ProviderIn,
    ProviderOut,
)


def create_provider(session: Session, workspace_id: int, dto: ProviderIn) -> ProviderOut:
    enc = encrypt(json.dumps(dto.credentials)) if dto.credentials else None
    provider = ModelProvider(
        workspace_id=workspace_id,
        type=dto.type,
        name=dto.name,
        base_url=dto.base_url,
        credentials_encrypted=enc,
    )
    repository.insert_provider(session, provider)
    return ProviderOut.model_validate(provider)


def get_decrypted_credentials(session: Session, provider_id: int) -> dict[str, str]:
    provider = repository.get_provider(session, provider_id)
    if provider is None:
        raise NotFoundError(ErrorCode.INTERNAL_ERROR, "厂商不存在")
    if not provider.credentials_encrypted:
        return {}
    raw: dict[str, str] = json.loads(decrypt(provider.credentials_encrypted))
    return raw


def create_model(session: Session, workspace_id: int, dto: ModelIn) -> ModelOut:
    model = Model(
        workspace_id=workspace_id,
        provider_id=dto.provider_id,
        model_key=dto.model_key,
        type=dto.type,
        capabilities=dto.capabilities,
        embedding_dim=dto.embedding_dim,
        default_params=dto.default_params,
    )
    repository.insert_model(session, model)
    return ModelOut.model_validate(model)


def list_models(session: Session, workspace_id: int) -> list[ModelOut]:
    return [ModelOut.model_validate(m) for m in repository.list_models(session, workspace_id)]
