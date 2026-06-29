from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from agent_hify.core.config import get_settings
from agent_hify.core.db import SessionLocal
from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError, ValidationError
from agent_hify.core.pagination import OffsetPage
from agent_hify.modules.knowledge import repository
from agent_hify.modules.knowledge.models import Chunk, Document, KnowledgeBase
from agent_hify.modules.knowledge.schemas import (
    DocumentOut,
    KbConfig,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    RetrievedChunk,
)
from agent_hify.modules.models import adapter as models_adapter
from agent_hify.modules.models import repository as models_repo
from agent_hify.modules.models import service as models_service

logger = logging.getLogger(__name__)


def _get_kb_or_raise(session: Session, kb_id: int, workspace_id: int) -> KnowledgeBase:
    kb = repository.get_kb(session, kb_id, workspace_id)
    if kb is None:
        raise NotFoundError(ErrorCode.KB_NOT_FOUND, "知识库不存在")
    return kb


def create_kb(session: Session, workspace_id: int, dto: KnowledgeBaseCreate) -> KnowledgeBaseOut:
    settings = get_settings()
    model = models_repo.get_model(session, dto.embedding_model_id)
    if model is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "模型不存在")
    if model.embedding_dim != settings.embedding_dim:
        raise ValidationError(
            ErrorCode.EMBEDDING_DIM_MISMATCH,
            f"embedding 模型维度 {model.embedding_dim} != 系统配置维度 {settings.embedding_dim}",
        )
    kb = KnowledgeBase(
        workspace_id=workspace_id,
        name=dto.name,
        embedding_model_id=dto.embedding_model_id,
        config=dto.config.model_dump(),
    )
    repository.insert_kb(session, kb)
    return KnowledgeBaseOut.model_validate(kb)


def get_kb(session: Session, kb_id: int, workspace_id: int) -> KnowledgeBaseOut:
    return KnowledgeBaseOut.model_validate(_get_kb_or_raise(session, kb_id, workspace_id))


def list_kbs(
    session: Session, workspace_id: int, page: int, page_size: int
) -> OffsetPage[KnowledgeBaseOut]:
    rows, total = repository.list_kbs(session, workspace_id, page, page_size)
    return OffsetPage(
        items=[KnowledgeBaseOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def update_kb(
    session: Session, kb_id: int, workspace_id: int, dto: KnowledgeBaseUpdate
) -> KnowledgeBaseOut:
    kb = _get_kb_or_raise(session, kb_id, workspace_id)
    updates: dict[str, object] = {}
    if dto.name is not None:
        updates["name"] = dto.name
    if dto.config is not None:
        updates["config"] = dto.config.model_dump()
    if updates:
        repository.update_kb(session, kb, updates)
    return KnowledgeBaseOut.model_validate(kb)


def delete_kb(session: Session, kb_id: int, workspace_id: int) -> None:
    kb = _get_kb_or_raise(session, kb_id, workspace_id)
    repository.soft_delete_kb(session, kb)


def create_document(
    session: Session,
    kb_id: int,
    workspace_id: int,
    filename: str,
    file_path: str,
) -> DocumentOut:
    _get_kb_or_raise(session, kb_id, workspace_id)
    doc = Document(kb_id=kb_id, filename=filename, file_path=file_path)
    repository.insert_document(session, doc)
    return DocumentOut.model_validate(doc)


def get_document_out(session: Session, doc_id: int, workspace_id: int) -> DocumentOut:
    doc = repository.get_document(session, doc_id)
    if doc is None:
        raise NotFoundError(ErrorCode.DOC_NOT_FOUND, "文档不存在")
    # 通过 kb 校验工作区归属
    if repository.get_kb(session, doc.kb_id, workspace_id) is None:
        raise NotFoundError(ErrorCode.DOC_NOT_FOUND, "文档不存在")
    return DocumentOut.model_validate(doc)


def list_documents(
    session: Session, kb_id: int, workspace_id: int, page: int, page_size: int
) -> OffsetPage[DocumentOut]:
    _get_kb_or_raise(session, kb_id, workspace_id)
    rows, total = repository.list_documents(session, kb_id, page, page_size)
    return OffsetPage(
        items=[DocumentOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _parse_file(file_path: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("txt", "md"):
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    elif ext == "pdf":
        try:
            import pypdf

            reader = pypdf.PdfReader(file_path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValidationError(ErrorCode.DOC_INGEST_FAILED, f"PDF 解析失败: {exc}") from exc
    else:
        raise ValidationError(
            ErrorCode.DOC_INGEST_FAILED, f"不支持的文件类型: .{ext}（支持 .txt .md .pdf）"
        )


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    try:
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.core.schema import Document as LlamaDoc

        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
        nodes = splitter.get_nodes_from_documents([LlamaDoc(text=text)])
        chunks = [node.get_content() for node in nodes if node.get_content().strip()]
        return chunks if chunks else ([text[:4096]] if text.strip() else [])
    except Exception:
        # Fallback: 朴素分块
        words = text.split()
        result, buf = [], []
        for w in words:
            buf.append(w)
            if len(" ".join(buf)) >= chunk_size:
                result.append(" ".join(buf))
                buf = buf[-overlap:] if overlap else []
        if buf:
            result.append(" ".join(buf))
        return result if result else ([text[:4096]] if text.strip() else [])


async def ingest(document_id: int) -> None:
    """文档摄取管线（由 Celery task 以 asyncio.run 调用）。"""
    session = SessionLocal()
    try:
        doc = repository.get_document(session, document_id)
        if doc is None:
            logger.error("ingest: document %d not found", document_id)
            return

        repository.update_document_status(session, doc, "processing")
        session.commit()

        kb = session.get(KnowledgeBase, doc.kb_id)
        if kb is None:
            raise RuntimeError(f"KB {doc.kb_id} not found")

        config = KbConfig.model_validate(kb.config)
        ref = models_service.resolve_ref(session, kb.embedding_model_id)

        text = _parse_file(doc.file_path, doc.filename)
        chunk_texts = _chunk_text(text, config.chunk_size, config.overlap)

        batch_size = 96
        all_vecs: list[list[float]] = []
        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i : i + batch_size]
            vecs = await models_adapter.embed(ref, batch)
            all_vecs.extend(vecs)

        repository.delete_chunks_for_document(session, document_id)
        chunks = [
            Chunk(
                document_id=document_id,
                kb_id=doc.kb_id,
                content=txt,
                embedding=vec,
                metadata_={},
                position=i,
                created_at=datetime.now(UTC),
            )
            for i, (txt, vec) in enumerate(zip(chunk_texts, all_vecs, strict=False))
        ]
        repository.insert_chunks(session, chunks)

        doc.char_count = len(text)
        repository.update_document_status(session, doc, "done")
        session.commit()

    except Exception as exc:
        session.rollback()
        try:
            doc2 = repository.get_document(session, document_id)
            if doc2 is not None:
                repository.update_document_status(session, doc2, "failed", str(exc)[:500])
                session.commit()
        except Exception:
            pass
        logger.exception("ingest failed for document %d", document_id)
    finally:
        session.close()


async def retrieve(
    session: Session,
    kb_id: int,
    workspace_id: int,
    query: str,
    top_k: int = 5,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    """向量检索：embed query → HNSW 余弦近邻。"""
    kb = _get_kb_or_raise(session, kb_id, workspace_id)
    config = KbConfig.model_validate(kb.config)
    effective_top_k = top_k or config.top_k
    effective_threshold = threshold if threshold is not None else config.threshold

    vecs = await models_service.embed(session, model_id=kb.embedding_model_id, texts=[query])
    query_vec = vecs[0]

    pairs = repository.search_chunks(
        session, kb_id, query_vec, effective_top_k, effective_threshold
    )
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            kb_id=chunk.kb_id,
            content=chunk.content,
            score=score,
            metadata=dict(chunk.metadata_),
        )
        for chunk, score in pairs
    ]
