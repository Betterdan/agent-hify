from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.models import service
from agent_hify.modules.models.schemas import (
    ChatMessage,
    ConnectivityResult,
    InvokeResult,
    ModelIn,
    ModelOut,
    ProviderIn,
    ProviderOut,
)

router = APIRouter(prefix="/api/v1", tags=["models"])


class InvokeIn(BaseModel):
    messages: list[ChatMessage]


@router.post("/model-providers")
def create_provider(
    payload: ProviderIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ProviderOut]:
    out = service.create_provider(session, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.post("/models")
def create_model(
    payload: ModelIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ModelOut]:
    out = service.create_model(session, current.workspace_id, payload)
    session.commit()
    return ApiResponse.ok(out)


@router.get("/models")
def list_models(
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[list[ModelOut]]:
    return ApiResponse.ok(service.list_models(session, current.workspace_id))


@router.post("/models/{model_id}/test-connectivity")
async def test_connectivity(
    model_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[ConnectivityResult]:
    out = await service.test_connectivity(
        session, model_id=model_id, workspace_id=current.workspace_id
    )
    session.commit()
    return ApiResponse.ok(out)


@router.post("/models/{model_id}/invoke")
async def invoke_model(
    model_id: int,
    payload: InvokeIn,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[InvokeResult]:
    out = await service.invoke(
        session,
        model_id=model_id,
        workspace_id=current.workspace_id,
        messages=payload.messages,
    )
    session.commit()
    return ApiResponse.ok(out)
