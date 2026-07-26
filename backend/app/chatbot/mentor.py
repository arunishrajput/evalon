"""Mentor chatbot orchestration (spec Section 9): availability checks, RAG
context assembly, model-queue-aware (P3) streaming generation, and message
persistence."""

import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_provider import LLMProvider
from app.chatbot.context import MAX_HISTORY_MESSAGES, build_prompt_with_history, build_system_prompt
from app.core.exceptions import ModelUnavailableError
from app.core.model_queue import ModelQueueManager
from app.database import async_session_factory
from app.embedding.retriever import DEFAULT_TOP_K, has_embeddings, retrieve_top_chunks
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.repo_embedding import RepoEmbedding
from app.models.submission import Submission, SubmissionStatus

logger = logging.getLogger("evalon.chatbot")

CHAT_INFERENCE_PRIORITY = 3  # P3 — lowest priority, yields to active evaluations
INFERENCE_WAIT_SECONDS = 30  # spec Section 9: 30s before returning HTTP 202 queued
QUEUED_RETRY_AFTER_SECONDS = 30
_FIXED_CHUNK_TYPES = ("repo_summary", "evaluation_summary")


class MentorQueued(Exception):
    """Raised when the P3 inference lock can't be acquired within
    INFERENCE_WAIT_SECONDS. The API layer catches this and returns the
    spec's HTTP 202 queued response — this is expected traffic control,
    not an error."""

    def __init__(self, retry_after: int = QUEUED_RETRY_AFTER_SECONDS) -> None:
        self.retry_after = retry_after
        super().__init__("Mentor inference lock queued")


async def check_availability(db: AsyncSession, submission: Submission) -> tuple[bool, str | None]:
    """Spec Section 9's pre-open availability check (steps 1-3). A degraded
    evaluation is still available (step 4) — only "not complete yet" and
    "no embeddings yet" actually gate access."""
    if submission.status != SubmissionStatus.COMPLETED:
        return False, "Your evaluation isn't complete yet. The mentor will be available once it finishes."
    if not await has_embeddings(db, submission.id):
        return False, "Your mentor is being prepared. Check back in a few minutes."
    return True, None


async def get_or_create_session(
    db: AsyncSession, *, user_id: uuid.UUID, submission_id: uuid.UUID, hackathon_id: uuid.UUID
) -> ChatSession:
    session = await db.scalar(
        select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.submission_id == submission_id)
    )
    if session is not None:
        return session
    session = ChatSession(user_id=user_id, submission_id=submission_id, hackathon_id=hackathon_id)
    db.add(session)
    await db.flush()
    return session


async def get_history(db: AsyncSession, session_id: uuid.UUID, limit: int = MAX_HISTORY_MESSAGES) -> list[ChatMessage]:
    rows = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(list(rows)))


_EMBEDDING_WAIT_SECONDS = 5  # kept short and separate from INFERENCE_WAIT_SECONDS: this wait happens
# BEFORE the inference-lock attempt, so it adds directly to the time-to-202-queued. Spec Section 9
# promises a queued response "within 30 seconds" of the inference lock; a long embedding wait here
# would silently blow that budget even though embedding itself is meant to be a ~200ms operation.


async def _embed_query(
    llm: LLMProvider, model_queue: ModelQueueManager, submission_id: str, query: str
) -> list[float] | None:
    """Embedding the query is brief (~200ms, spec step 7) — if it can't
    happen right now, degrade to no retrieval augmentation rather than
    blocking or failing the whole chat turn over it."""
    try:
        async with model_queue.acquire_embedding_lock(f"chat:{submission_id}", timeout=_EMBEDDING_WAIT_SECONDS):
            return await llm.embed(query)
    except ModelUnavailableError as exc:
        logger.warning("Query embedding unavailable for chat on submission %s: %s", submission_id, exc)
        return None


async def _fixed_context_chunks(db: AsyncSession, submission_id: uuid.UUID) -> dict[str, str]:
    rows = await db.scalars(
        select(RepoEmbedding).where(
            RepoEmbedding.submission_id == submission_id, RepoEmbedding.chunk_type.in_(_FIXED_CHUNK_TYPES)
        )
    )
    return {row.chunk_type: row.chunk_content for row in rows}


async def stream_response(
    *,
    llm: LLMProvider,
    model_queue: ModelQueueManager,
    participant_name: str,
    submission_id: uuid.UUID,
    session_id: uuid.UUID,
    message: str,
) -> AsyncIterator[dict]:
    """Persists the user's message, retrieves RAG context, then streams the
    mentor's response as spec Section 9's SSE event dicts
    ({"token": "...", "done": False}, then a final {"token": "", "done":
    True, "message_id": "..."}), persisting the assembled response at the
    end. Raises MentorQueued if the P3 inference lock can't be acquired
    within INFERENCE_WAIT_SECONDS — always BEFORE any token is yielded, so
    callers can tell "queued, nothing sent yet" apart from "failed mid-stream".

    Opens and owns its own DB session rather than accepting one from the
    caller: FastAPI closes a `Depends(get_db)` session as soon as the route
    function returns, which for a StreamingResponse happens right after the
    first chunk is produced — long before this generator finishes streaming
    and needs to persist the assistant's reply. A self-managed session (the
    same pattern ARQ jobs already use) survives for the generator's full
    lifetime regardless of when the route function itself returns."""
    submission_id_str = str(submission_id)

    async with async_session_factory() as db:
        history = await get_history(db, session_id)

        user_message = ChatMessage(session_id=session_id, role=ChatRole.USER, content=message)
        db.add(user_message)
        await db.commit()  # durable immediately, so it survives even if we bail out to "queued" below

        query_embedding = await _embed_query(llm, model_queue, submission_id_str, message)
        retrieved: list[RepoEmbedding] = []
        if query_embedding is not None:
            retrieved = await retrieve_top_chunks(db, submission_id, query_embedding, k=DEFAULT_TOP_K)

        fixed_chunks = await _fixed_context_chunks(db, submission_id)
        system_prompt = build_system_prompt(
            participant_name=participant_name,
            repo_summary_chunk=fixed_chunks.get("repo_summary"),
            evaluation_report_chunk=fixed_chunks.get("evaluation_summary"),
            retrieved_chunks=[c for c in retrieved if c.chunk_type not in _FIXED_CHUNK_TYPES],
        )
        prompt = build_prompt_with_history(history, message)

        lock_cm = model_queue.acquire_inference_lock(
            f"chat:{submission_id_str}", priority=CHAT_INFERENCE_PRIORITY, timeout=INFERENCE_WAIT_SECONDS
        )
        try:
            await lock_cm.__aenter__()
        except ModelUnavailableError as exc:
            raise MentorQueued() from exc  # user message is already committed above

        full_response = ""
        stream_failed = False
        try:
            async for token in llm.generate_stream(prompt, system_prompt):
                full_response += token
                yield {"token": token, "done": False}
        except ModelUnavailableError as exc:
            logger.warning("Mentor response streaming failed mid-turn for submission %s: %s", submission_id_str, exc)
            stream_failed = True
            if not full_response:
                full_response = "Sorry, I ran into a problem generating a response. Please try asking again."
        finally:
            await lock_cm.__aexit__(None, None, None)

        assistant_message = ChatMessage(
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=full_response,
            retrieved_chunks=[{"chunk_id": str(c.id), "chunk_type": c.chunk_type} for c in retrieved],
        )
        db.add(assistant_message)
        await db.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(last_message_at=datetime.now(timezone.utc))
        )
        await db.commit()
        await db.refresh(assistant_message)

        final_event = {"token": "", "done": True, "message_id": str(assistant_message.id)}
        if stream_failed:
            final_event["error"] = "The mentor's response was interrupted. Please try asking again."
        yield final_event
