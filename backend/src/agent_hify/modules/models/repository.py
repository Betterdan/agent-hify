from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.models.models import Model, ModelProvider


def insert_provider(session: Session, provider: ModelProvider) -> ModelProvider:
    session.add(provider)
    session.flush()
    return provider


def get_provider(session: Session, provider_id: int) -> ModelProvider | None:
    stmt = select(ModelProvider).where(
        ModelProvider.id == provider_id, ModelProvider.deleted_at.is_(None)
    )
    return session.execute(stmt).scalar_one_or_none()


def insert_model(session: Session, model: Model) -> Model:
    session.add(model)
    session.flush()
    return model


def get_model(session: Session, model_id: int) -> Model | None:
    stmt = select(Model).where(Model.id == model_id, Model.deleted_at.is_(None))
    return session.execute(stmt).scalar_one_or_none()


def list_models(session: Session, workspace_id: int) -> list[Model]:
    stmt = select(Model).where(
        Model.workspace_id == workspace_id, Model.deleted_at.is_(None)
    )
    return list(session.execute(stmt).scalars().all())
