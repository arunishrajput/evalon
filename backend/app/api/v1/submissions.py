"""Submission creation (Stage 0 validation), status polling, SSE progress
streaming, and withdrawal."""

import uuid

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.v1.submission_access import get_submission_or_404, require_owner_or_admin
from app.config import Settings, get_settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user, get_redis
from app.jobs.queue import get_arq_pool
from app.models.hackathon import Hackathon, HackathonStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.pipeline.progress import stream_progress
from app.schemas.submission import SubmissionCreate, SubmissionRead
from app.utils.git_utils import validate_repo_exists_and_public

router = APIRouter(prefix="/submissions", tags=["submissions"])

_WITHDRAWABLE_STATUSES = {
    SubmissionStatus.PENDING,
    SubmissionStatus.CLONING,
    SubmissionStatus.ANALYZING,
    SubmissionStatus.FAILED,
}


@router.post("", response_model=SubmissionRead, status_code=201)
async def create_submission(
    payload: SubmissionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Submission:
    hackathon = await db.get(Hackathon, payload.hackathon_id)
    if hackathon is None:
        raise NotFoundError("Hackathon not found")
    if hackathon.status != HackathonStatus.ACTIVE:
        raise ConflictError("This hackathon is not currently accepting submissions", "hackathon_not_active")

    existing = await db.scalar(
        select(Submission).where(
            Submission.hackathon_id == payload.hackathon_id, Submission.user_id == user.id
        )
    )
    if existing is not None:
        raise ConflictError("You have already submitted to this hackathon", "already_submitted")

    metadata = await validate_repo_exists_and_public(payload.repo_url, settings.github_api_token)

    submission = Submission(
        hackathon_id=payload.hackathon_id,
        user_id=user.id,
        repo_url=payload.repo_url,
        repo_name=metadata.get("name"),
        repo_description=metadata.get("description"),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("You have already submitted to this hackathon", "already_submitted") from exc
    await db.refresh(submission)

    pool = await get_arq_pool()
    await pool.enqueue_job("ingest_repository", str(submission.id))
    await pool.enqueue_job("update_hackathon_stats", str(payload.hackathon_id))

    return submission


@router.get("/{submission_id}", response_model=SubmissionRead)
async def get_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)
    return submission


@router.get("/{submission_id}/status")
async def stream_submission_status(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)
    return StreamingResponse(
        stream_progress(redis, str(submission_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{submission_id}", status_code=204)
async def withdraw_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    submission = await get_submission_or_404(submission_id, db)
    if submission.user_id != user.id:
        raise AuthorizationError("Only the submitting participant can withdraw a submission")
    if submission.status not in _WITHDRAWABLE_STATUSES:
        raise ConflictError(
            "This submission can no longer be withdrawn — evaluation has already started",
            "withdrawal_not_allowed",
        )
    await db.delete(submission)
    await db.commit()
