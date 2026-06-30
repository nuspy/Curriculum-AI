from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .. import __version__
from ..utils.logging import setup_logging
from .dashboard import router as dashboard_router
from .health import router as health_router
from .lifespan import base_lifespan
from .mcp_mount import get_mcp_app
from .ws_bridge import router as ws_router


def create_app() -> FastAPI:
    setup_logging()
    mcp_app = get_mcp_app()
    mcp_lifespan = getattr(mcp_app, "lifespan", None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if mcp_lifespan is not None:
            async with mcp_lifespan(app):
                async with base_lifespan(app):
                    yield
        else:
            async with base_lifespan(app):
                yield

    app = FastAPI(title="AutoJob daemon", version=__version__, lifespan=lifespan)

    from .activity import touch

    @app.middleware("http")
    async def _activity_mw(request, call_next):
        touch()
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(ws_router)
    app.include_router(dashboard_router)  # cockpit su "/"
    app.mount("/mcp", mcp_app)

    return app
