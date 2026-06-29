from __future__ import annotations

from fastapi import FastAPI

from agent_hify.core.exceptions import register_exception_handlers
from agent_hify.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="agent-hify", version="0.1.0")
    register_exception_handlers(app)

    from agent_hify.modules.apps.router import router as apps_router
    from agent_hify.modules.identity.router import router as identity_router
    from agent_hify.modules.knowledge.router import router as knowledge_router
    from agent_hify.modules.models.router import router as models_router
    from agent_hify.modules.observability.router import router as observability_router
    from agent_hify.modules.runtime.router import router as runtime_router
    from agent_hify.modules.tools.router import router as tools_router

    app.include_router(apps_router)
    app.include_router(identity_router)
    app.include_router(knowledge_router, prefix="/api/v1")
    app.include_router(models_router)
    app.include_router(observability_router)
    app.include_router(runtime_router)
    app.include_router(tools_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
