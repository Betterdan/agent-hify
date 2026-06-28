from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.apps import service
from agent_hify.modules.apps.schemas import AppCreate, AppOut, AppUpdate
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut

router = APIRouter(prefix="/api/v1", tags=["apps"])


@router.post("/apps")
def create_app(
    payload: AppCreate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    out = service.create_app(session, current.workspace_id, current.id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.get("/apps")
def list_apps(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[AppOut]]:
    return ApiResponse.ok(service.list_apps(session, current.workspace_id))


@router.get("/apps/{app_id}")
def get_app(
    app_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    return ApiResponse.ok(service.get_app(session, app_id, current.workspace_id))


@router.put("/apps/{app_id}")
def update_app(
    app_id: int,
    payload: AppUpdate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AppOut]:
    out = service.update_app(session, app_id, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.delete("/apps/{app_id}")
def delete_app(
    app_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[None]:
    service.delete_app(session, app_id, current.workspace_id)
    session.commit()
    return ApiResponse.ok(None)
