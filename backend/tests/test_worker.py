from __future__ import annotations

from agent_hify.worker.celery_app import celery
from agent_hify.worker.tasks import ping


def test_ping_eager() -> None:
    celery.conf.task_always_eager = True
    assert ping.delay().get() == "pong"
