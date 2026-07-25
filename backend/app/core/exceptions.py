"""Custom exception hierarchy. API layers catch these and translate them into
structured JSON responses — no raw exception ever reaches the client."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("evalon.errors")


class EvalonError(Exception):
    """Base class for all EVALON application errors."""

    error_code: str = "internal_error"
    status_code: int = 400

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
    status_code = 503


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


class AuthenticationError(EvalonError):
    """Missing, invalid, or expired credentials."""

    error_code = "authentication_failed"
    status_code = 401


class AuthorizationError(EvalonError):
    """Authenticated, but not permitted to perform this action."""

    error_code = "not_authorized"
    status_code = 403


class NotFoundError(EvalonError):
    """The requested resource does not exist."""

    error_code = "not_found"
    status_code = 404


class ConflictError(EvalonError):
    """The request conflicts with existing state (duplicate submission,
    weights that don't sum to 1.0, hackathon in the wrong status, etc.)."""

    error_code = "conflict"
    status_code = 409


def register_exception_handlers(app: FastAPI) -> None:
    """Ensures every error path returns { "detail": str, "error_code": str } —
    never a raw exception or stack trace."""

    @app.exception_handler(EvalonError)
    async def evalon_error_handler(_: Request, exc: EvalonError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail), "error_code": "http_error"},
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
