"""Pydantic schemas for admin utility endpoints."""

from decimal import Decimal

from pydantic import BaseModel


class ModelStatusResponse(BaseModel):
    ollama_reachable: bool
    inference_model: str
    inference_model_loaded: bool
    embedding_model: str
    embedding_model_loaded: bool
    lock_held_by: str | None
    queue_depth: int
    estimated_wait_seconds: int


class HealthResponse(BaseModel):
    status: str
    database: bool
    redis: bool
    ollama_reachable: bool


class QueueStatusResponse(BaseModel):
    reachable: bool
    jobs_complete: int
    jobs_failed: int
    jobs_retried: int
    jobs_ongoing: int
    jobs_queued: int
    raw_health_check: str | None


class AdminHackathonSummary(BaseModel):
    id: str
    title: str
    status: str
    total_submissions: int
    evaluations_completed: int
    avg_score: Decimal | None
