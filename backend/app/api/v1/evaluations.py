"""Evaluation report retrieval, per-agent results, and admin retry."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.submission_access import get_submission_or_404, require_owner_or_admin
from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.jobs.queue import get_arq_pool
from app.models.agent_result import AgentResult as AgentResultModel
from app.models.evaluation import Evaluation
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.schemas.evaluation import AgentResultRead, EvaluationRead
from app.schemas.submission import SubmissionRead

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


async def _get_evaluation_or_404(submission_id: uuid.UUID, db: AsyncSession) -> Evaluation:
    evaluation = await db.scalar(select(Evaluation).where(Evaluation.submission_id == submission_id))
    if evaluation is None:
        raise NotFoundError("No evaluation found for this submission")
    return evaluation


@router.get("/{submission_id}", response_model=EvaluationRead)
async def get_evaluation(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Evaluation:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)
    return await _get_evaluation_or_404(submission_id, db)


@router.get("/{submission_id}/agents", response_model=list[AgentResultRead])
async def get_agent_results(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentResultModel]:
    submission = await get_submission_or_404(submission_id, db)
    require_owner_or_admin(submission, user)
    evaluation = await _get_evaluation_or_404(submission_id, db)
    rows = await db.scalars(
        select(AgentResultModel).where(AgentResultModel.evaluation_id == evaluation.id)
    )
    return list(rows)


@router.post("/{submission_id}/retry", response_model=SubmissionRead)
async def retry_evaluation(
    submission_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    submission = await get_submission_or_404(submission_id, db)
    if submission.status != SubmissionStatus.FAILED:
        raise ConflictError("Only failed submissions can be retried", "not_failed")

    submission.status = SubmissionStatus.PENDING
    submission.error_message = None
    submission.degraded = False
    submission.degraded_reason = None
    await db.commit()
    await db.refresh(submission)

    pool = await get_arq_pool()
    await pool.enqueue_job("ingest_repository", str(submission.id))

    return submission
