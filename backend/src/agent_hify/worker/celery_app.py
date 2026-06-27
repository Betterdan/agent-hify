from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]

from agent_hify.core.config import get_settings

settings = get_settings()
celery = Celery("agent_hify", broker=settings.redis_url, backend=settings.redis_url)
celery.autodiscover_tasks(["agent_hify.worker"])
