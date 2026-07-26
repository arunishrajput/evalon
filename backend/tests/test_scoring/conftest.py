"""Real-DB fixture for comparative agent tests — pool percentile/ranking
logic is exercised against actual Postgres queries, not mocks."""

import pytest_asyncio
from sqlalchemy import text

from app.database import async_session_factory, engine

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
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(_TABLES_TO_CLEAN)} CASCADE"))
    yield


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
