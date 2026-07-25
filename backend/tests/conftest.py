"""Shared pytest fixtures. Model queue tests run against a real Redis instance
(the point of Phase 0 is proving the distributed lock actually serializes) but
never hit real Ollama — Ollama HTTP calls are monkeypatched per-test."""

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.core.model_queue import ModelQueueManager


@pytest.fixture
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest_asyncio.fixture
async def redis_client(settings: Settings):
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def model_queue(redis_client: Redis, settings: Settings) -> ModelQueueManager:
    return ModelQueueManager(redis=redis_client, settings=settings)
