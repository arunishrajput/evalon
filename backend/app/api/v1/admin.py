"""Admin utility endpoints."""

import re

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import outerjoin, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_queue import ModelQueueManager
from app.database import get_db
from app.dependencies import get_model_queue_manager, get_redis, require_admin
from app.models.hackathon import Hackathon, HackathonStats
from app.models.user import User
from app.schemas.admin import (
    AdminHackathonSummary,
    HealthResponse,
    ModelStatusResponse,
    QueueStatusResponse,
)

router = APIRouter()

_ARQ_HEALTH_KEY = "arq:queue:health-check"
_ARQ_HEALTH_PATTERN = re.compile(
    r"j_complete=(?P<complete>\d+) j_failed=(?P<failed>\d+) j_retried=(?P<retried>\d+) "
    r"j_ongoing=(?P<ongoing>\d+) queued=(?P<queued>\d+)"
)


@router.get("/admin/model/status", response_model=ModelStatusResponse)
async def get_model_status(
    model_queue: ModelQueueManager = Depends(get_model_queue_manager),
) -> ModelStatusResponse:
    """Current ModelQueueManager state — which model is loaded, who holds the
    lock, and how deep the wait queue is. Never triggers a model load."""
    status = await model_queue.get_queue_status()
    return ModelStatusResponse(**status)


@router.get("/admin/queue/status", response_model=QueueStatusResponse)
async def get_queue_status(
    admin: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
) -> QueueStatusResponse:
    """Parses ARQ's own periodic health-check string (written by the worker
    process to Redis) rather than reimplementing job bookkeeping — ARQ
    already tracks these counters internally."""
    raw = await redis.get(_ARQ_HEALTH_KEY)
    if raw is None:
        return QueueStatusResponse(
            reachable=False, jobs_complete=0, jobs_failed=0, jobs_retried=0,
            jobs_ongoing=0, jobs_queued=0, raw_health_check=None,
        )
    match = _ARQ_HEALTH_PATTERN.search(raw)
    if not match:
        return QueueStatusResponse(
            reachable=True, jobs_complete=0, jobs_failed=0, jobs_retried=0,
            jobs_ongoing=0, jobs_queued=0, raw_health_check=raw,
        )
    return QueueStatusResponse(
        reachable=True,
        jobs_complete=int(match["complete"]),
        jobs_failed=int(match["failed"]),
        jobs_retried=int(match["retried"]),
        jobs_ongoing=int(match["ongoing"]),
        jobs_queued=int(match["queued"]),
        raw_health_check=raw,
    )


@router.get("/admin/hackathons", response_model=list[AdminHackathonSummary])
async def list_admin_hackathons(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminHackathonSummary]:
    rows = (
        await db.execute(
            select(Hackathon, HackathonStats)
            .select_from(outerjoin(Hackathon, HackathonStats, HackathonStats.hackathon_id == Hackathon.id))
            .order_by(Hackathon.created_at.desc())
        )
    ).all()
    return [
        AdminHackathonSummary(
            id=str(hackathon.id),
            title=hackathon.title,
            status=hackathon.status.value,
            total_submissions=stats.total_submissions if stats else 0,
            evaluations_completed=stats.evaluations_completed if stats else 0,
            avg_score=stats.avg_score if stats else None,
        )
        for hackathon, stats in rows
    ]


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    model_queue: ModelQueueManager = Depends(get_model_queue_manager),
) -> HealthResponse:
    """Reports service health without ever raising — every dependency check is
    independently try/excepted so one down service doesn't 500 the health check
    itself."""
    try:
        await db.execute(select(1))
        database_ok = True
    except SQLAlchemyError:
        database_ok = False

    try:
        redis_ok = bool(await redis.ping())
    except RedisError:
        redis_ok = False

    ollama_status = await model_queue.health_check()

    all_healthy = database_ok and redis_ok and ollama_status["ollama_reachable"]
    return HealthResponse(
        status="ok" if all_healthy else "degraded",
        database=database_ok,
        redis=redis_ok,
        ollama_reachable=ollama_status["ollama_reachable"],
    )
