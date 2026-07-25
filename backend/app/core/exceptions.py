"""Custom exception hierarchy. API layers catch these and translate them into
structured JSON responses — no raw exception ever reaches the client."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("evalon.errors")


class EvalonError(Exception):
    """Base class for all EVALON application errors."""

    error_code: str = "internal_error"

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code


class ModelUnavailableError(EvalonError):
    """Raised when the inference/embedding model cannot be acquired within the
    caller's timeout, or when Ollama itself is unreachable. Callers MUST treat
    this as a degrade-not-crash signal, never propagate it as a 500."""

    error_code = "model_unavailable"


class ModelLockTimeoutError(ModelUnavailableError):
    """Raised when a caller could not acquire the model lock before its timeout
    elapsed (queue contention, not an Ollama outage)."""

    error_code = "model_lock_timeout"


class RepositoryIngestionError(EvalonError):
    """Raised when cloning or sanitizing a submitted repository fails."""

    error_code = "repository_ingestion_failed"


class StaticAnalysisError(EvalonError):
    """Raised when a static analysis tool fails in a way that cannot be
    gracefully skipped for the affected analyzer."""

    error_code = "static_analysis_failed"


def register_exception_handlers(app: FastAPI) -> None:
    """Ensures every error path returns { "detail": str, "error_code": str } —
    never a raw exception or stack trace."""

    @app.exception_handler(EvalonError)
    async def evalon_error_handler(_: Request, exc: EvalonError) -> JSONResponse:
        status_code = 503 if isinstance(exc, ModelUnavailableError) else 400
        return JSONResponse(
            status_code=status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Something went wrong on our end. Please try again shortly.",
                "error_code": "internal_error",
            },
        )
