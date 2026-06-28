from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.observability import service
from agent_hify.modules.observability.schemas import TraceOut, UsageDailyOut

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces")
def list_traces(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[TraceOut]]:
    return ApiResponse.ok(service.list_traces(session, current.workspace_id))


@router.get("/usage")
def list_usage(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[UsageDailyOut]]:
    return ApiResponse.ok(service.list_usage(session, current.workspace_id))
