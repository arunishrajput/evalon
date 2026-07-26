"""Mentor orchestration: availability gating, session reuse, and — the
critical Phase 6 verification gate — that a chat request queues cleanly (P3)
behind an active P0 evaluation lock, persisting the user's message even
while queued, rather than crashing or losing it."""

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.chatbot import mentor
from app.chatbot.mentor import MentorQueued
from app.models.chat import ChatMessage, ChatRole
from app.models.hackathon import Hackathon
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User


class FakeChatLLM:
    def __init__(self, tokens: list[str] | None = None, embed_vector: list[float] | None = None):
        self.tokens = tokens if tokens is not None else ["Hi", " Ada"]
        self.embed_vector = embed_vector or [0.1] * 768

    async def embed(self, text: str) -> list[float]:
        return self.embed_vector

    async def generate_stream(self, prompt, system):
        for token in self.tokens:
            yield token


async def _seed_submission(db, *, status=SubmissionStatus.COMPLETED, degraded=False) -> tuple[User, Submission]:
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(admin)
    await db.flush()
    hackathon = Hackathon(title="Mentor Test", admin_id=admin.id)
    db.add(hackathon)
    await db.flush()
    user = User(email=f"user-{uuid.uuid4().hex[:6]}@test.com", hashed_password="x", full_name="Ada Lovelace")
    db.add(user)
    await db.flush()
    submission = Submission(
        hackathon_id=hackathon.id, user_id=user.id, repo_url="https://github.com/x/y",
        repo_name="y", status=status, degraded=degraded,
    )
    db.add(submission)
    await db.flush()
    await db.commit()
    return user, submission


async def test_check_availability_false_when_evaluation_not_complete(db_session):
    _, submission = await _seed_submission(db_session, status=SubmissionStatus.EVALUATING)
    available, reason = await mentor.check_availability(db_session, submission)
    assert available is False
    assert "isn't complete" in reason


async def test_check_availability_false_when_no_embeddings_yet(db_session):
    _, submission = await _seed_submission(db_session)
    available, reason = await mentor.check_availability(db_session, submission)
    assert available is False
    assert "being prepared" in reason


async def test_check_availability_true_when_completed_and_embedded(db_session):
    _, submission = await _seed_submission(db_session)
    db_session.add(
        RepoEmbedding(submission_id=submission.id, chunk_type="readme", chunk_content="hi", embedding=[0.0] * 768)
    )
    await db_session.commit()

    available, reason = await mentor.check_availability(db_session, submission)
    assert available is True
    assert reason is None


async def test_check_availability_true_when_degraded_but_embedded(db_session):
    _, submission = await _seed_submission(db_session, degraded=True)
    db_session.add(
        RepoEmbedding(submission_id=submission.id, chunk_type="readme", chunk_content="hi", embedding=[0.0] * 768)
    )
    await db_session.commit()

    available, _ = await mentor.check_availability(db_session, submission)
    assert available is True


async def test_get_or_create_session_is_idempotent(db_session):
    _, submission = await _seed_submission(db_session)

    first = await mentor.get_or_create_session(
        db_session, user_id=submission.user_id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )
    await db_session.commit()
    second = await mentor.get_or_create_session(
        db_session, user_id=submission.user_id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )

    assert first.id == second.id


async def test_stream_response_persists_messages_and_streams_tokens(db_session, model_queue, stub_model_load):
    user, submission = await _seed_submission(db_session)
    db_session.add(
        RepoEmbedding(
            submission_id=submission.id, chunk_type="repo_summary", chunk_content="A FastAPI app.", embedding=[0.1] * 768
        )
    )
    await db_session.commit()

    session = await mentor.get_or_create_session(
        db_session, user_id=user.id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )
    await db_session.commit()

    events = [
        event
        async for event in mentor.stream_response(
            llm=FakeChatLLM(tokens=["Hi", " Ada"]), model_queue=model_queue, participant_name=user.full_name,
            submission_id=submission.id, session_id=session.id, message="Why did I lose points?",
        )
    ]

    tokens = [e["token"] for e in events if not e["done"]]
    assert tokens == ["Hi", " Ada"]
    assert events[-1]["done"] is True
    assert "message_id" in events[-1]

    messages = list(
        await db_session.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at)
        )
    )
    assert len(messages) == 2
    assert messages[0].role == ChatRole.USER
    assert messages[0].content == "Why did I lose points?"
    assert messages[1].role == ChatRole.ASSISTANT
    assert messages[1].content == "Hi Ada"


async def test_stream_response_queues_behind_active_evaluation_lock(
    db_session, model_queue, stub_model_load, monkeypatch
):
    """The Phase 6 gate: a P3 chat request behind an active P0 evaluation
    lock must queue (raise MentorQueued after timing out), not crash — and
    the participant's question must not be lost."""
    monkeypatch.setattr(mentor, "INFERENCE_WAIT_SECONDS", 0.3)
    user, submission = await _seed_submission(db_session)
    db_session.add(
        RepoEmbedding(
            submission_id=submission.id, chunk_type="repo_summary", chunk_content="A FastAPI app.", embedding=[0.1] * 768
        )
    )
    await db_session.commit()

    session = await mentor.get_or_create_session(
        db_session, user_id=user.id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )
    await db_session.commit()

    release_event = asyncio.Event()

    async def hold_evaluation_lock():
        async with model_queue.acquire_inference_lock("eval:other-submission", priority=0, timeout=5):
            await release_event.wait()

    holder_task = asyncio.create_task(hold_evaluation_lock())
    await asyncio.sleep(0.05)  # let the P0 holder actually grab the lock first

    with pytest.raises(MentorQueued):
        async for _ in mentor.stream_response(
            llm=FakeChatLLM(), model_queue=model_queue, participant_name=user.full_name,
            submission_id=submission.id, session_id=session.id, message="Are you there?",
        ):
            pass

    release_event.set()
    await holder_task

    messages = list(await db_session.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)))
    assert len(messages) == 1
    assert messages[0].role == ChatRole.USER
    assert messages[0].content == "Are you there?"
