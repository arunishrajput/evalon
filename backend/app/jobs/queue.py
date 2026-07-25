"""ARQ pool client for dispatching jobs from the FastAPI process (the worker
process consumes them; this is the producer side)."""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            settings = get_settings()
            _pool = await create_pool(RedisSettings(host=settings.redis_host, port=settings.redis_port))
    return _pool
