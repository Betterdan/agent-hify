from __future__ import annotations

from fastapi import FastAPI

from agent_hify.core.exceptions import register_exception_handlers
from agent_hify.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="agent-hify", version="0.1.0")
    register_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
