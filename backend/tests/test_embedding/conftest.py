"""Real-DB fixture for embedding pipeline tests, mirroring test_scoring/conftest.py.
`settings`/`redis_client`/`model_queue` come from the top-level tests/conftest.py."""

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.model_queue import ModelQueueManager
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


@pytest.fixture
def stub_model_load(monkeypatch):
    """Skips real Ollama load/unload so lock-behavior tests run fast and
    deterministically, same fixture pattern as test_core/test_model_queue.py."""

    async def _noop(self, model_name, keep_alive):
        return None

    monkeypatch.setattr(ModelQueueManager, "_ensure_model_loaded", _noop)
