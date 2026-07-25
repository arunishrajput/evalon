"""FastAPI dependency injection: shared Redis connection and ModelQueueManager."""

from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings
from app.core.model_queue import ModelQueueManager


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache
def get_model_queue_manager() -> ModelQueueManager:
    return ModelQueueManager(redis=get_redis(), settings=get_settings())
