"""FastAPI application factory."""

import logging

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import configure_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="EVALON API",
        description="AI-native hackathon evaluation engine.",
        version="0.1.0",
    )

    configure_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
