from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_hify.core.db import get_session
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity import service
from agent_hify.modules.identity.schemas import LoginIn, TokenOut, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginIn, session: Session = Depends(get_session)) -> ApiResponse[TokenOut]:
    token = service.authenticate(session, payload.email, payload.password)
    return ApiResponse.ok(token)


@router.get("/me")
def me(current: UserOut = Depends(service.get_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse.ok(current)
