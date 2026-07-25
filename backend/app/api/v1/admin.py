"""Admin utility endpoints. Hackathon-with-stats listing and ARQ queue status are
added in later phases once the database and job queue exist — see
docs/reports/PHASE-0-REPORT.md for what's intentionally deferred."""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.model_queue import ModelQueueManager
from app.dependencies import get_model_queue_manager, get_redis
from app.schemas.admin import HealthResponse, ModelStatusResponse

router = APIRouter()


@router.get("/admin/model/status", response_model=ModelStatusResponse)
async def get_model_status(
    model_queue: ModelQueueManager = Depends(get_model_queue_manager),
) -> ModelStatusResponse:
    """Current ModelQueueManager state — which model is loaded, who holds the
    lock, and how deep the wait queue is. Never triggers a model load."""
    status = await model_queue.get_queue_status()
    return ModelStatusResponse(**status)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    redis: Redis = Depends(get_redis),
    model_queue: ModelQueueManager = Depends(get_model_queue_manager),
) -> HealthResponse:
    """Reports service health without ever raising — every dependency check is
    independently try/excepted so one down service doesn't 500 the health check
    itself. Database check is added once app/database.py exists (Phase 1)."""
    try:
        redis_ok = bool(await redis.ping())
    except RedisError:
        redis_ok = False

    ollama_status = await model_queue.health_check()

    return HealthResponse(
        status="ok" if redis_ok and ollama_status["ollama_reachable"] else "degraded",
        database=False,
        redis=redis_ok,
        ollama_reachable=ollama_status["ollama_reachable"],
    )
