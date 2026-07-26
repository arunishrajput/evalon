"""Mentor chatbot endpoints: availability gating, ownership, and the
messages endpoint's two response shapes (streaming SSE / HTTP 202 queued).
Submissions are seeded directly via the DB (real evaluations are exercised
live, per docs/reports/PHASE-6-REPORT.md) with LLMProvider monkeypatched at
the class level so no real Ollama call is made."""

import asyncio
import json
import uuid

import pytest
from httpx import AsyncClient

from app.agents.llm_provider import LLMProvider
from app.core.model_queue import ModelQueueManager
from app.database import async_session_factory
from app.dependencies import get_model_queue_manager
from app.models.hackathon import Hackathon
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str) -> tuple[str, uuid.UUID]:
    payload = {"email": email, "password": "supersecret123"}
    register = await client.post("/auth/register", json=payload)
    login = await client.post("/auth/login", json=payload)
    return login.json()["access_token"], uuid.UUID(register.json()["id"])


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_submission(
    owner_id: uuid.UUID, *, status: SubmissionStatus = SubmissionStatus.COMPLETED, with_embeddings: bool = True
) -> uuid.UUID:
    async with async_session_factory() as db:
        admin = User(email=f"chat-admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
        db.add(admin)
        await db.flush()
        hackathon = Hackathon(title="Chat Test", admin_id=admin.id)
        db.add(hackathon)
        await db.flush()
        submission = Submission(
            hackathon_id=hackathon.id, user_id=owner_id, repo_url="https://github.com/x/y",
            repo_name="y", status=status,
        )
        db.add(submission)
        await db.flush()
        if with_embeddings:
            db.add(
                RepoEmbedding(
                    submission_id=submission.id, chunk_type="repo_summary",
                    chunk_content="A FastAPI project.", embedding=[0.1] * 768,
                )
            )
        await db.commit()
        return submission.id


async def test_sessions_reports_unavailable_when_evaluation_incomplete(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat1@example.com")
    submission_id = await _seed_submission(user_id, status=SubmissionStatus.EVALUATING, with_embeddings=False)

    resp = await client.post(f"/chat/{submission_id}/sessions", headers=_auth(token))

    assert resp.status_code == 201
    body = resp.json()
    assert body["mentor_available"] is False
    assert "isn't complete" in body["unavailable_reason"]


async def test_sessions_reports_unavailable_when_no_embeddings(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat2@example.com")
    submission_id = await _seed_submission(user_id, with_embeddings=False)

    resp = await client.post(f"/chat/{submission_id}/sessions", headers=_auth(token))

    assert resp.status_code == 201
    body = resp.json()
    assert body["mentor_available"] is False
    assert "being prepared" in body["unavailable_reason"]


async def test_sessions_available_when_completed_and_embedded(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat3@example.com")
    submission_id = await _seed_submission(user_id)

    resp = await client.post(f"/chat/{submission_id}/sessions", headers=_auth(token))

    assert resp.status_code == 201
    body = resp.json()
    assert body["mentor_available"] is True
    assert body["unavailable_reason"] is None


async def test_sessions_forbidden_for_non_owner(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat4@example.com")
    submission_id = await _seed_submission(user_id)
    other_token, _ = await _register_and_login(client, "chat5@example.com")

    resp = await client.post(f"/chat/{submission_id}/sessions", headers=_auth(other_token))

    assert resp.status_code == 403


async def test_messages_rejected_when_mentor_not_ready(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat6@example.com")
    submission_id = await _seed_submission(user_id, with_embeddings=False)

    resp = await client.post(f"/chat/{submission_id}/messages", json={"content": "Hi"}, headers=_auth(token))

    assert resp.status_code == 409
    assert resp.json()["error_code"] == "mentor_not_ready"


async def test_history_is_empty_before_any_session(client: AsyncClient):
    token, user_id = await _register_and_login(client, "chat7@example.com")
    submission_id = await _seed_submission(user_id)

    resp = await client.get(f"/chat/{submission_id}/history", headers=_auth(token))

    assert resp.status_code == 200
    assert resp.json() == []


async def test_messages_streams_tokens_and_history_reflects_them(client: AsyncClient, monkeypatch):
    async def fake_embed(self, text: str) -> list[float]:
        return [0.1] * 768

    async def fake_generate_stream(self, prompt: str, system: str):
        for token in ["Hi", " there"]:
            yield token

    monkeypatch.setattr(LLMProvider, "embed", fake_embed)
    monkeypatch.setattr(LLMProvider, "generate_stream", fake_generate_stream)

    token, user_id = await _register_and_login(client, "chat8@example.com")
    submission_id = await _seed_submission(user_id)

    resp = await client.post(f"/chat/{submission_id}/messages", json={"content": "Why this score?"}, headers=_auth(token))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[len("data: "):]) for line in resp.text.splitlines() if line.startswith("data: ")]
    tokens = [e["token"] for e in events if not e["done"]]
    assert tokens == ["Hi", " there"]
    assert events[-1]["done"] is True

    history = await client.get(f"/chat/{submission_id}/history", headers=_auth(token))
    contents = [m["content"] for m in history.json()]
    assert "Why this score?" in contents
    assert "Hi there" in contents


async def test_messages_returns_202_queued_when_lock_is_held(client: AsyncClient, monkeypatch):
    """The Phase 6 gate at the API layer: a chat request behind an active P0
    evaluation lock gets HTTP 202 queued, not a hang or a crash."""

    async def noop_ensure_model_loaded(self, model_name, keep_alive):
        return None

    monkeypatch.setattr(ModelQueueManager, "_ensure_model_loaded", noop_ensure_model_loaded)
    monkeypatch.setattr("app.chatbot.mentor.INFERENCE_WAIT_SECONDS", 0.3)

    token, user_id = await _register_and_login(client, "chat9@example.com")
    submission_id = await _seed_submission(user_id)

    model_queue = get_model_queue_manager()
    release_event = asyncio.Event()

    async def hold_evaluation_lock():
        async with model_queue.acquire_inference_lock("eval:other-submission", priority=0, timeout=5):
            await release_event.wait()

    holder_task = asyncio.create_task(hold_evaluation_lock())
    await asyncio.sleep(0.05)  # let the P0 holder actually grab the lock first

    resp = await client.post(f"/chat/{submission_id}/messages", json={"content": "Are you there?"}, headers=_auth(token))

    release_event.set()
    await holder_task

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["retry_after"] == 30
