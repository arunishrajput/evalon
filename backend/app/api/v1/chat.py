"""Mentor chatbot endpoints (spec Section 6 CHAT ENDPOINTS, Section 9). The
POST .../messages endpoint IS the SSE stream (spec's literal "Send message,
stream response (SSE)") — it returns HTTP 202 with a queued body instead of
starting the stream when the P3 inference lock can't be acquired within 30
seconds. Deviation from Section 9's prose: the frontend retries this same
POST after `retry_after` seconds rather than polling a separate
`/chat/{session_id}/pending` endpoint, which Section 6's own endpoint list
(the one this project treats as the authoritative contract) never defines."""

import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, StreamingResponse

from app.agents.llm_provider import LLMProvider
from app.api.v1.submission_access import get_submission_or_404, require_owner_or_admin
from app.chatbot import mentor
from app.config import get_settings
from app.core.exceptions import ConflictError
from app.database import get_db
from app.dependencies import get_current_user, get_model_queue_manager
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatSessionRead

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{submission_id}/sessions", response_model=ChatSessionRead, status_code=201)
async def create_or_get_session(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionRead:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)

    available, reason = await mentor.check_availability(db, submission)
    session = await mentor.get_or_create_session(
        db, user_id=user.id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )
    await db.commit()
    await db.refresh(session)

    return ChatSessionRead(
        id=session.id,
        submission_id=session.submission_id,
        created_at=session.created_at,
        last_message_at=session.last_message_at,
        mentor_available=available,
        unavailable_reason=reason,
        degraded=submission.degraded,
    )


@router.post("/{submission_id}/messages")
async def send_message(
    submission_id: uuid.UUID,
    payload: ChatMessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)

    available, reason = await mentor.check_availability(db, submission)
    if not available:
        raise ConflictError(reason, "mentor_not_ready")

    session = await mentor.get_or_create_session(
        db, user_id=user.id, submission_id=submission.id, hackathon_id=submission.hackathon_id
    )
    await db.commit()  # session row must be durable before the streaming generator (its own DB session) reads it

    settings = get_settings()
    generator = mentor.stream_response(
        llm=LLMProvider(settings),
        model_queue=get_model_queue_manager(),
        participant_name=user.full_name or user.email,
        submission_id=submission.id,
        session_id=session.id,
        message=payload.content,
    )

    try:
        first_event = await generator.__anext__()
    except mentor.MentorQueued as exc:
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "message": (
                    "The AI mentor is currently evaluating another submission. Your message will be "
                    "processed in approximately 30-60 seconds. Please wait."
                ),
                "retry_after": exc.retry_after,
            },
        )

    async def _sse() -> AsyncIterator[str]:
        yield f"data: {json.dumps(first_event)}\n\n"
        async for event in generator:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        _sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{submission_id}/history", response_model=list[ChatMessageRead])
async def get_chat_history(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)

    session = await db.scalar(
        select(ChatSession).where(ChatSession.user_id == user.id, ChatSession.submission_id == submission_id)
    )
    if session is None:
        return []
    rows = await db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at)
    )
    return list(rows)
