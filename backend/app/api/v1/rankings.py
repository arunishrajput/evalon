"""Leaderboard endpoints, gated by hackathon.settings.show_rankings_before_finalization
(spec Section 10: participants see project name only — not participant
identity — until the admin finalizes)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_user
from app.models.evaluation import Evaluation
from app.models.hackathon import Hackathon
from app.models.ranking import Ranking
from app.models.submission import Submission
from app.models.user import User, UserRole
from app.schemas.ranking import RankingEntry

router = APIRouter(prefix="/rankings", tags=["rankings"])


async def _get_hackathon_or_404(hackathon_id: uuid.UUID, db: AsyncSession) -> Hackathon:
    hackathon = await db.get(Hackathon, hackathon_id)
    if hackathon is None:
        raise NotFoundError("Hackathon not found")
    return hackathon


def _is_visible(hackathon: Hackathon, is_admin: bool, any_finalized: bool) -> bool:
    if is_admin:
        return True
    if any_finalized:
        return True
    return bool(hackathon.settings.get("show_rankings_before_finalization", False))


async def _fetch_ranking_rows(db: AsyncSession, hackathon_id: uuid.UUID):
    return (
        await db.execute(
            select(Ranking, Submission, Evaluation.final_score, User.full_name, User.email, Submission.user_id)
            .join(Submission, Submission.id == Ranking.submission_id)
            .join(Evaluation, Evaluation.submission_id == Ranking.submission_id)
            .join(User, User.id == Submission.user_id)
            .where(Ranking.hackathon_id == hackathon_id)
            .order_by(Ranking.rank)
        )
    ).all()


def _to_entry(ranking: Ranking, submission: Submission, final_score, full_name, email, submission_user_id, *, show_identity: bool, caller_id: uuid.UUID) -> RankingEntry:
    return RankingEntry(
        submission_id=ranking.submission_id,
        rank=ranking.rank,
        percentile=ranking.percentile,
        normalized_score=ranking.normalized_score,
        final_score=final_score,
        finalized=ranking.finalized,
        repo_name=submission.repo_name,
        participant_name=(full_name or email) if show_identity else None,
        is_you=submission_user_id == caller_id,
    )


@router.get("/{hackathon_id}", response_model=list[RankingEntry])
async def get_leaderboard(
    hackathon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RankingEntry]:
    hackathon = await _get_hackathon_or_404(hackathon_id, db)
    is_admin = user.role == UserRole.ADMIN
    any_finalized = bool(
        await db.scalar(
            select(Ranking.id).where(Ranking.hackathon_id == hackathon_id, Ranking.finalized.is_(True)).limit(1)
        )
    )
    if not _is_visible(hackathon, is_admin, any_finalized):
        raise ConflictError("Rankings are not available until the admin finalizes results", "rankings_not_visible")

    rows = await _fetch_ranking_rows(db, hackathon_id)
    show_identity = is_admin or any_finalized
    return [
        _to_entry(ranking, submission, final_score, full_name, email, submission_user_id, show_identity=show_identity, caller_id=user.id)
        for ranking, submission, final_score, full_name, email, submission_user_id in rows
    ]


@router.get("/{hackathon_id}/me", response_model=RankingEntry)
async def get_my_ranking(
    hackathon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RankingEntry:
    await _get_hackathon_or_404(hackathon_id, db)
    row = (
        await db.execute(
            select(Ranking, Submission, Evaluation.final_score, User.full_name, User.email, Submission.user_id)
            .join(Submission, Submission.id == Ranking.submission_id)
            .join(Evaluation, Evaluation.submission_id == Ranking.submission_id)
            .join(User, User.id == Submission.user_id)
            .where(Ranking.hackathon_id == hackathon_id, Submission.user_id == user.id)
        )
    ).first()
    if row is None:
        raise NotFoundError("You do not have a ranked submission in this hackathon yet")

    ranking, submission, final_score, full_name, email, submission_user_id = row
    return _to_entry(ranking, submission, final_score, full_name, email, submission_user_id, show_identity=True, caller_id=user.id)
