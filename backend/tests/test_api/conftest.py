"""API test fixtures: an httpx AsyncClient wired directly to the FastAPI app
(no running server needed) against the real Postgres/Redis dev instances,
with tables truncated before each test for isolation."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.rate_limit import limiter
from app.database import engine
from app.dependencies import get_redis
from app.main import app

_TABLES_TO_CLEAN = [
    "chat_messages",
    "chat_sessions",
    "repo_embeddings",
    "agent_results",
    "rankings",
    "evaluations",
    "submissions",
    "criteria",
    "hackathon_participants",
    "hackathon_stats",
    "hackathons",
    "users",
]


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    # pytest-asyncio gives each test function its own event loop, but `engine`
    # and the cached get_redis() client are module-level singletons created
    # once at import time — any pooled connections from a previous test's
    # (now-closed) loop are unusable here. Disposing/clearing first forces
    # fresh connections bound to the current loop.
    await engine.dispose()
    try:
        await get_redis().aclose()
    except RuntimeError:
        pass  # previous loop already closed; nothing to clean up
    get_redis.cache_clear()

    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(_TABLES_TO_CLEAN)} CASCADE"))
    await get_redis().flushdb()
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        yield ac
