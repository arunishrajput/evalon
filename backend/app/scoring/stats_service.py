"""Recomputes the pre-computed `hackathon_stats` row (spec Stage 8 /
Section 5) — submission pipeline-stage buckets, score distribution
histogram, tech stack frequency, average score, and a top-5 preview."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.hackathon import HackathonStats
from app.models.submission import Submission, SubmissionStatus

_SCORE_BUCKETS = [f"{i}-{i + 10}" for i in range(0, 100, 10)]
_IN_PROGRESS_STATUSES = {SubmissionStatus.CLONING, SubmissionStatus.ANALYZING, SubmissionStatus.EVALUATING}
_TOP5_LIMIT = 5


def _bucket_for_score(score: float) -> str:
    index = min(int(score // 10), 9)  # score==100 falls into the last bucket, not an out-of-range 11th
    return _SCORE_BUCKETS[index]


async def compute_hackathon_stats(db: AsyncSession, hackathon_id: uuid.UUID) -> dict:
    submissions = list(
        await db.scalars(select(Submission).where(Submission.hackathon_id == hackathon_id))
    )
    total_submissions = len(submissions)
    evaluations_completed = sum(1 for s in submissions if s.status == SubmissionStatus.COMPLETED)
    evaluations_in_progress = sum(1 for s in submissions if s.status in _IN_PROGRESS_STATUSES)
    evaluations_queued = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    evaluations_failed = sum(1 for s in submissions if s.status == SubmissionStatus.FAILED)

    score_distribution = {bucket: 0 for bucket in _SCORE_BUCKETS}
    tech_stack_frequency: dict[str, int] = {}
    for submission in submissions:
        for tech in submission.tech_stack or []:
            tech_stack_frequency[tech] = tech_stack_frequency.get(tech, 0) + 1

    scored_rows = await db.execute(
        select(Evaluation.final_score, Submission.repo_name)
        .join(Submission, Submission.id == Evaluation.submission_id)
        .where(
            Evaluation.hackathon_id == hackathon_id,
            Evaluation.status.in_([EvaluationStatus.COMPLETED, EvaluationStatus.DEGRADED]),
            Evaluation.final_score.is_not(None),
        )
        .order_by(Evaluation.final_score.desc())
    )
    scored = [(float(score), repo_name) for score, repo_name in scored_rows.all()]

    for score, _ in scored:
        score_distribution[_bucket_for_score(score)] += 1

    avg_score = round(sum(score for score, _ in scored) / len(scored), 3) if scored else None
    top5_preview = [
        {"rank": i + 1, "repo_name": repo_name or "Untitled", "score": score}
        for i, (score, repo_name) in enumerate(scored[:_TOP5_LIMIT])
    ]

    return {
        "total_submissions": total_submissions,
        "evaluations_completed": evaluations_completed,
        "evaluations_in_progress": evaluations_in_progress,
        "evaluations_queued": evaluations_queued,
        "evaluations_failed": evaluations_failed,
        "score_distribution": score_distribution,
        "tech_stack_frequency": tech_stack_frequency,
        "avg_score": avg_score,
        "top5_preview": top5_preview,
    }


async def upsert_hackathon_stats(db: AsyncSession, hackathon_id: uuid.UUID) -> HackathonStats:
    stats_dict = await compute_hackathon_stats(db, hackathon_id)
    stats = await db.scalar(select(HackathonStats).where(HackathonStats.hackathon_id == hackathon_id))
    if stats is None:
        stats = HackathonStats(hackathon_id=hackathon_id)
        db.add(stats)
    for field, value in stats_dict.items():
        setattr(stats, field, value)
    await db.flush()
    return stats
