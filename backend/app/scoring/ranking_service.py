"""Recomputes the `rankings` table for a hackathon from completed/degraded
evaluations (spec Stage 8). Shared between the recompute_rankings ARQ job
(fires after every evaluation) and the finalize endpoint (one last
guaranteed-fresh pass before locking results)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.ranking import Ranking
from app.scoring.normalizer import compute_rankings


async def recompute_rankings_for_hackathon(db: AsyncSession, hackathon_id: uuid.UUID) -> list[Ranking]:
    """No-op if the hackathon's rankings are already finalized — finalization
    locks results; a late-arriving retry must not silently reshuffle a
    published leaderboard."""
    already_finalized = await db.scalar(
        select(Ranking.id).where(Ranking.hackathon_id == hackathon_id, Ranking.finalized.is_(True)).limit(1)
    )
    if already_finalized is not None:
        return list(await db.scalars(select(Ranking).where(Ranking.hackathon_id == hackathon_id)))

    rows = await db.execute(
        select(Evaluation.submission_id, Evaluation.final_score).where(
            Evaluation.hackathon_id == hackathon_id,
            Evaluation.status.in_([EvaluationStatus.COMPLETED, EvaluationStatus.DEGRADED]),
            Evaluation.final_score.is_not(None),
        )
    )
    scored = [(str(submission_id), float(final_score)) for submission_id, final_score in rows.all()]
    computed = compute_rankings(scored)

    existing = {
        r.submission_id: r
        for r in await db.scalars(select(Ranking).where(Ranking.hackathon_id == hackathon_id))
    }

    result_rows: list[Ranking] = []
    seen_submission_ids: set[uuid.UUID] = set()
    for entry in computed:
        submission_uuid = uuid.UUID(entry.submission_id)
        seen_submission_ids.add(submission_uuid)
        ranking = existing.get(submission_uuid)
        if ranking is None:
            ranking = Ranking(hackathon_id=hackathon_id, submission_id=submission_uuid)
            db.add(ranking)
        ranking.rank = entry.rank
        ranking.percentile = entry.percentile
        ranking.normalized_score = entry.normalized_score
        result_rows.append(ranking)

    # Drop rankings for submissions that no longer have a scored evaluation
    # (e.g. a submission was withdrawn after its evaluation completed).
    for submission_id, ranking in existing.items():
        if submission_id not in seen_submission_ids:
            await db.delete(ranking)

    await db.flush()
    return result_rows
