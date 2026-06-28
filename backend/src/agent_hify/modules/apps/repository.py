from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent_hify.modules.apps.models import App


def insert_app(session: Session, app: App) -> App:
    session.add(app)
    session.flush()
    return app


def get_app(session: Session, app_id: int, workspace_id: int) -> App | None:
    stmt = select(App).where(
        App.id == app_id,
        App.workspace_id == workspace_id,
        App.deleted_at.is_(None),
    )
    return session.execute(stmt).scalar_one_or_none()


def list_apps(session: Session, workspace_id: int) -> list[App]:
    stmt = (
        select(App)
        .where(App.workspace_id == workspace_id, App.deleted_at.is_(None))
        .order_by(App.created_at.desc(), App.id.desc())
    )
    return list(session.execute(stmt).scalars().all())


def update_app(session: Session, app: App) -> App:
    session.flush()
    return app


def soft_delete_app(session: Session, app: App) -> None:
    app.deleted_at = datetime.now(UTC)
    session.flush()
