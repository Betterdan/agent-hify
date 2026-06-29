from __future__ import annotations

import asyncio as _asyncio

from agent_hify.worker.celery_app import celery


@celery.task(name="ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"


@celery.task(name="ingest_document")  # type: ignore[untyped-decorator]
def ingest_document_task(document_id: int) -> None:
    from agent_hify.modules.knowledge.service import ingest

    _asyncio.run(ingest(document_id))
