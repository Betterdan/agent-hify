from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.observability import service
from agent_hify.modules.observability.schemas import (
    AnnotationIn,
    AnnotationOut,
    EvalHookIn,
    TraceOut,
    UsageDailyOut,
)

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces")
def list_traces(
    app_id: int | None = None,
    status: str | None = None,
    days: int = 7,
    limit: int = 100,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[TraceOut]]:
    return ApiResponse.ok(
        service.list_traces(
            session, current.workspace_id,
            limit=limit, app_id=app_id, status=status, days=days
        )
    )


@router.get("/usage")
def list_usage(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[UsageDailyOut]]:
    return ApiResponse.ok(service.list_usage(session, current.workspace_id))


@router.post("/annotations")
def create_annotation(
    body: AnnotationIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[AnnotationOut]:
    result = service.annotate(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(result)


@router.get("/annotations")
def list_annotations(
    message_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[AnnotationOut]]:
    return ApiResponse.ok(service.get_annotations(session, current.workspace_id, message_id))


@router.post("/eval-hook")
def trigger_eval_hook(
    body: EvalHookIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[dict[str, int]]:
    ev_id = service.run_eval_hook(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok({"id": ev_id})
