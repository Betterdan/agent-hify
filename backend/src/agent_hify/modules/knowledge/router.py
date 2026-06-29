from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from agent_hify.core.config import get_settings
from agent_hify.core.db import get_session
from agent_hify.core.pagination import OffsetPage
from agent_hify.core.response import ApiResponse
from agent_hify.modules.identity.deps import get_current_user
from agent_hify.modules.identity.schemas import UserOut
from agent_hify.modules.knowledge import service
from agent_hify.modules.knowledge.schemas import (
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge_bases")
def list_kbs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[OffsetPage[KnowledgeBaseOut]]:
    return ApiResponse.ok(service.list_kbs(session, current.workspace_id, page, page_size))


@router.post("/knowledge_bases")
def create_kb(
    body: KnowledgeBaseCreate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[KnowledgeBaseOut]:
    out = service.create_kb(session, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(out)


@router.get("/knowledge_bases/{kb_id}")
def get_kb(
    kb_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[KnowledgeBaseOut]:
    return ApiResponse.ok(service.get_kb(session, kb_id, current.workspace_id))


@router.patch("/knowledge_bases/{kb_id}")
def update_kb(
    kb_id: int,
    body: KnowledgeBaseUpdate,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[KnowledgeBaseOut]:
    out = service.update_kb(session, kb_id, current.workspace_id, body)
    session.commit()
    return ApiResponse.ok(out)


@router.delete("/knowledge_bases/{kb_id}")
def delete_kb(
    kb_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[None]:
    service.delete_kb(session, kb_id, current.workspace_id)
    session.commit()
    return ApiResponse.ok(None)


@router.post("/knowledge_bases/{kb_id}/documents")
async def upload_document(
    kb_id: int,
    file: UploadFile,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[DocumentOut]:
    from agent_hify.worker.tasks import ingest_document_task  # local import 避免循环

    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    dest = os.path.join(settings.upload_dir, f"{uuid.uuid4()}.{ext}")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    doc_out = service.create_document(session, kb_id, current.workspace_id, filename, dest)
    session.commit()
    ingest_document_task.delay(doc_out.id)
    return ApiResponse.ok(doc_out)


@router.get("/knowledge_bases/{kb_id}/documents")
def list_documents(
    kb_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[OffsetPage[DocumentOut]]:
    return ApiResponse.ok(
        service.list_documents(session, kb_id, current.workspace_id, page, page_size)
    )


@router.get("/documents/{doc_id}")
def get_document(
    doc_id: int,
    current: UserOut = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApiResponse[DocumentOut]:
    return ApiResponse.ok(service.get_document_out(session, doc_id, current.workspace_id))
