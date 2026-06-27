from __future__ import annotations

from agent_hify.worker.celery_app import celery


@celery.task(name="ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
