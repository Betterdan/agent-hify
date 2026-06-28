from __future__ import annotations

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.modules.apps import repository
from agent_hify.modules.apps.models import App
from agent_hify.modules.apps.schemas import AppCreate, AppOut, AppUpdate


def _get_or_404(session: Session, app_id: int, workspace_id: int) -> App:
    app = repository.get_app(session, app_id, workspace_id)
    if app is None:
        raise NotFoundError(ErrorCode.APP_NOT_FOUND, "应用不存在")
    return app


def create_app(session: Session, workspace_id: int, created_by: int, dto: AppCreate) -> AppOut:
    app = App(
        workspace_id=workspace_id,
        type=dto.type,
        name=dto.name,
        config=dto.config.model_dump(),
        created_by=created_by,
    )
    repository.insert_app(session, app)
    return AppOut.model_validate(app)


def get_app(session: Session, app_id: int, workspace_id: int) -> AppOut:
    return AppOut.model_validate(_get_or_404(session, app_id, workspace_id))


def list_apps(session: Session, workspace_id: int) -> list[AppOut]:
    return [AppOut.model_validate(a) for a in repository.list_apps(session, workspace_id)]


def update_app(session: Session, app_id: int, workspace_id: int, dto: AppUpdate) -> AppOut:
    app = _get_or_404(session, app_id, workspace_id)
    if dto.name is not None:
        app.name = dto.name
    if dto.config is not None:
        app.config = dto.config.model_dump()
    if dto.status is not None:
        app.status = dto.status
    repository.update_app(session, app)
    return AppOut.model_validate(app)


def delete_app(session: Session, app_id: int, workspace_id: int) -> None:
    app = _get_or_404(session, app_id, workspace_id)
    repository.soft_delete_app(session, app)
