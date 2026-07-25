"""Pydantic schemas for admin utility endpoints."""

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
