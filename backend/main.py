"""Canonical backend entrypoint for FRIDAY (Phase 0)."""
from __future__ import annotations

import os
import logging
import uvicorn
from fastapi import FastAPI

from backend.api.chat import router as chat_router
from backend.api.capabilities import router as capabilities_router
from backend.api.health import router as health_router
from backend.api.jobs import router as jobs_router
from backend.middleware.identity import IdentityMiddleware

logging.basicConfig(level=os.getenv("FRIDAY_LOG_LEVEL", "INFO"))
logger = logging.getLogger("friday.backend")


def create_app() -> FastAPI:
    app = FastAPI(title="FRIDAY Core")
    app.add_middleware(IdentityMiddleware)
    app.include_router(chat_router, prefix="/api")
    app.include_router(capabilities_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(health_router)

    @app.get("/")
    def root():
        return {"status": "friday-online"}

    return app


app = create_app()


def run() -> None:
    port = int(os.getenv("FRIDAY_API_PORT", "9001"))
    logger.info("Starting FRIDAY backend on port %s", port)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
