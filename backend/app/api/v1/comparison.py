"""Side-by-side comparison of up to 3 submissions (spec Section 6)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user
from app.models.evaluation import Evaluation
from app.models.ranking import Ranking
from app.models.submission import Submission
from app.models.user import User
from app.schemas.comparison import ComparisonResponse, ComparisonSubmission, CriterionScore

router = APIRouter(prefix="/compare", tags=["comparison"])

_MAX_SUBMISSIONS = 3


def _parse_submission_ids(raw: str) -> list[uuid.UUID]:
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    if not ids:
        raise ConflictError("submission_ids must contain at least one id", "invalid_submission_ids")
    if len(ids) > _MAX_SUBMISSIONS:
        raise ConflictError(f"submission_ids supports at most {_MAX_SUBMISSIONS} submissions", "too_many_submissions")
    try:
        return [uuid.UUID(part) for part in ids]
    except ValueError as exc:
        raise ConflictError("submission_ids contains an invalid UUID", "invalid_submission_ids") from exc


def _top_evidence_by_agent(report: dict) -> dict[str, list[str]]:
    return {a["agent_id"]: a.get("top_evidence", []) for a in report.get("agent_results", [])}


@router.get("/{hackathon_id}", response_model=ComparisonResponse)
async def compare_submissions(
    hackathon_id: uuid.UUID,
    submission_ids: str = Query(..., description="Comma-separated submission UUIDs, max 3"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComparisonResponse:
    ids = _parse_submission_ids(submission_ids)

    rows = (
        await db.execute(
            select(Submission, Evaluation, User.full_name, User.email, Ranking.rank, Ranking.percentile)
            .join(Evaluation, Evaluation.submission_id == Submission.id)
            .join(User, User.id == Submission.user_id)
            .outerjoin(Ranking, Ranking.submission_id == Submission.id)
            .where(Submission.hackathon_id == hackathon_id, Submission.id.in_(ids))
        )
    ).all()
    if not rows:
        raise NotFoundError("No evaluated submissions found for the given ids")

    by_id = {submission.id: (submission, evaluation, full_name, email, rank, percentile) for submission, evaluation, full_name, email, rank, percentile in rows}

    submissions = []
    for submission_id in ids:
        if submission_id not in by_id:
            continue
        submission, evaluation, full_name, email, rank, percentile = by_id[submission_id]
        report = evaluation.report or {}
        top_evidence_by_agent = _top_evidence_by_agent(report)

        scores_by_criterion = [
            CriterionScore(
                criterion=c["criterion"],
                score=c["score"],
                weight=c["weight"],
                top_evidence=top_evidence_by_agent.get(c.get("agent_id"), []),
            )
            for c in report.get("scores", {}).get("by_criterion", [])
        ]

        submissions.append(
            ComparisonSubmission(
                submission_id=str(submission.id),
                repo_name=submission.repo_name,
                participant_name=full_name or email,
                final_score=evaluation.final_score,
                scores_by_criterion=scores_by_criterion,
                strengths=report.get("strengths", []),
                weaknesses=report.get("weaknesses", []),
                tech_stack=submission.tech_stack or [],
                rank=rank,
                percentile=float(percentile) if percentile is not None else None,
            )
        )

    return ComparisonResponse(submissions=submissions)
