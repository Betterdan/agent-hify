from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.pagination import CursorPage
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.runtime import service
from agent_hify.modules.runtime.schemas import ChatInput, ConversationOut, MessageOut

router = APIRouter(prefix="/api/v1", tags=["runtime"])


@router.get("/apps/{app_id}/conversations")
def list_conversations(
    app_id: int,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[CursorPage[ConversationOut]]:
    page = service.list_conversations(session, app_id, current.workspace_id, cursor, limit)
    return ApiResponse.ok(page)


@router.get("/conversations/{conv_id}/messages")
def list_messages(
    conv_id: int,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[CursorPage[MessageOut]]:
    page = service.list_messages(session, conv_id, cursor, limit)
    return ApiResponse.ok(page)


@router.post("/apps/{app_id}/chat")
async def chat(
    app_id: int,
    payload: ChatInput,
    current: UserOut = Depends(get_current_user),
) -> StreamingResponse:
    # 不注入 get_session：StreamingResponse 在 handler return 后才迭代生成器，
    # 注入会话此时已关闭。生成器内部自建 SessionLocal()（见 service.run_chat）。
    generator = service.run_chat(app_id, current.workspace_id, current.id, payload)
    return StreamingResponse(generator, media_type="text/event-stream")
