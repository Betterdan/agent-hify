from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent_hify.modules.knowledge.models import Chunk, Document, KnowledgeBase


def insert_kb(session: Session, kb: KnowledgeBase) -> KnowledgeBase:
    session.add(kb)
    session.flush()
    session.refresh(kb)
    return kb


def get_kb(session: Session, kb_id: int, workspace_id: int) -> KnowledgeBase | None:
    return session.scalars(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    ).first()


def list_kbs(
    session: Session, workspace_id: int, page: int, page_size: int
) -> tuple[list[KnowledgeBase], int | None]:
    base_q = select(KnowledgeBase).where(
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.deleted_at.is_(None),
    )
    total: int | None = None
    if page == 1:
        total = session.scalar(select(func.count()).select_from(base_q.subquery())) or 0
    rows = list(
        session.scalars(
            base_q.order_by(KnowledgeBase.id).limit(page_size).offset((page - 1) * page_size)
        )
    )
    return rows, total


def update_kb(session: Session, kb: KnowledgeBase, updates: dict[str, object]) -> KnowledgeBase:
    for k, v in updates.items():
        setattr(kb, k, v)
    kb.updated_at = datetime.now(UTC)
    session.flush()
    return kb


def soft_delete_kb(session: Session, kb: KnowledgeBase) -> None:
    kb.deleted_at = datetime.now(UTC)
    session.flush()


def insert_document(session: Session, doc: Document) -> Document:
    session.add(doc)
    session.flush()
    session.refresh(doc)
    return doc


def get_document(session: Session, doc_id: int) -> Document | None:
    return session.get(Document, doc_id)


def list_documents(
    session: Session, kb_id: int, page: int, page_size: int
) -> tuple[list[Document], int | None]:
    base_q = select(Document).where(Document.kb_id == kb_id)
    total: int | None = None
    if page == 1:
        total = session.scalar(select(func.count()).select_from(base_q.subquery())) or 0
    rows = list(
        session.scalars(
            base_q.order_by(Document.id).limit(page_size).offset((page - 1) * page_size)
        )
    )
    return rows, total


def update_document_status(
    session: Session, doc: Document, status: str, error: str | None = None
) -> None:
    doc.status = status
    doc.error = error
    doc.updated_at = datetime.now(UTC)
    session.flush()


def delete_chunks_for_document(session: Session, document_id: int) -> None:
    session.query(Chunk).filter(Chunk.document_id == document_id).delete()


def insert_chunks(session: Session, chunks: list[Chunk]) -> None:
    session.add_all(chunks)
    session.flush()


def search_chunks(
    session: Session,
    kb_id: int,
    query_vec: list[float],
    top_k: int,
    threshold: float | None,
) -> list[tuple[Chunk, float]]:
    """返回 (Chunk, cosine_distance) 列表，按距离升序（越小越相似）。"""
    distance_expr = Chunk.embedding.op("<=>")(query_vec)
    q = (
        select(Chunk, distance_expr.label("score"))
        .where(Chunk.kb_id == kb_id)
        .order_by(distance_expr)
        .limit(top_k)
    )
    if threshold is not None:
        q = q.where(distance_expr < threshold)
    rows = session.execute(q).all()
    return [(row[0], float(row[1])) for row in rows]
