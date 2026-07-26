"""Comparative Intelligence Agent (spec Section 8, Agent 4). Runs AFTER the
model lock is released — pure DB queries and arithmetic, no LLM call.

Pool comparison data comes from OTHER completed/degraded evaluations' stored
`report` JSONB in this hackathon, so per-criterion pool averages reflect the
same "effective" (fallback-aware) scores every participant sees on their own
report, rather than requiring a second, expensive re-aggregation pass."""

import statistics
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.submission import Submission
from app.pipeline.context_builder import RepoContext

MIN_POOL_SIZE_FOR_COMPARISON = 3


class ComparativeResult(BaseModel):
    agent_id: str = "comparative"
    total_submissions_in_pool: int
    this_submission_score: float
    pool_average_score: float
    pool_median_score: float
    percentile: float
    percentile_label: str
    rank_in_pool: int
    score_vs_average: str
    shared_tech_stacks: list[dict] = []
    unique_tech_stacks: list[dict] = []
    criterion_comparisons: list[dict] = []
    summary: str
    sufficient_data: bool
    data_note: str


class ComparativeAgent:
    agent_id = "comparative"
    agent_name = "Comparative Intelligence Agent"

    async def evaluate(
        self,
        *,
        repo_context: RepoContext,
        submission_id: str,
        hackathon_id: str,
        db: AsyncSession,
        this_score: float,
        this_criterion_scores: list[dict],
    ) -> ComparativeResult:
        pool = await self._fetch_pool(db, hackathon_id, exclude_submission_id=submission_id)
        total = len(pool) + 1  # + this submission

        if total < MIN_POOL_SIZE_FOR_COMPARISON:
            return ComparativeResult(
                total_submissions_in_pool=total,
                this_submission_score=this_score,
                pool_average_score=0.0,
                pool_median_score=0.0,
                percentile=0.0,
                percentile_label="N/A",
                rank_in_pool=0,
                score_vs_average="N/A",
                summary="Comparative analysis will be available once more submissions are evaluated.",
                sufficient_data=False,
                data_note=f"Based on {total} submission(s) evaluated so far.",
            )

        other_scores = sorted((e["score"] for e in pool), reverse=True)
        rank = sum(1 for s in other_scores if s > this_score) + 1
        percentile = (sum(1 for s in other_scores if s < this_score) / total) * 100
        all_scores = other_scores + [this_score]
        avg = sum(all_scores) / total
        median = statistics.median(all_scores)
        diff = this_score - avg

        shared, unique = self._tech_stack_comparison(repo_context.tech_stack, pool)

        return ComparativeResult(
            total_submissions_in_pool=total,
            this_submission_score=this_score,
            pool_average_score=round(avg, 1),
            pool_median_score=round(median, 1),
            percentile=round(percentile, 1),
            percentile_label=f"Top {max(1, round(100 - percentile))}%",
            rank_in_pool=rank,
            score_vs_average=f"{'+' if diff >= 0 else ''}{diff:.1f} {'above' if diff >= 0 else 'below'} average",
            shared_tech_stacks=shared,
            unique_tech_stacks=unique,
            criterion_comparisons=self._criterion_comparisons(pool, this_criterion_scores),
            summary=self._generate_summary(rank, total, percentile),
            sufficient_data=True,
            data_note=f"Based on {total} submissions evaluated so far.",
        )

    async def _fetch_pool(self, db: AsyncSession, hackathon_id: str, exclude_submission_id: str) -> list[dict]:
        rows = await db.execute(
            select(Evaluation.final_score, Evaluation.report, Submission.tech_stack)
            .join(Submission, Submission.id == Evaluation.submission_id)
            .where(
                Evaluation.hackathon_id == uuid.UUID(hackathon_id),
                Evaluation.submission_id != uuid.UUID(exclude_submission_id),
                Evaluation.status.in_([EvaluationStatus.COMPLETED, EvaluationStatus.DEGRADED]),
                Evaluation.final_score.is_not(None),
            )
        )
        return [
            {"score": float(final_score), "report": report or {}, "tech_stack": tech_stack or []}
            for final_score, report, tech_stack in rows.all()
        ]

    @staticmethod
    def _tech_stack_comparison(this_tech_stack: list[str], pool: list[dict]) -> tuple[list[dict], list[dict]]:
        shared, unique = [], []
        for tech in this_tech_stack:
            count = sum(1 for entry in pool if tech in entry["tech_stack"])
            if count > 0:
                plural = "s" if count != 1 else ""
                shared.append({"tech": tech, "count": count, "message": f"{count} other team{plural} also used {tech}"})
            else:
                unique.append({"tech": tech, "message": f"Only your team used {tech} — differentiator"})
        return shared, unique

    @staticmethod
    def _criterion_comparisons(pool: list[dict], this_criterion_scores: list[dict]) -> list[dict]:
        pool_by_criterion: dict[str, list[float]] = {}
        for entry in pool:
            for c in entry["report"].get("scores", {}).get("by_criterion", []):
                pool_by_criterion.setdefault(c["criterion"], []).append(c["score"])

        comparisons = []
        for c in this_criterion_scores:
            pool_scores = pool_by_criterion.get(c["criterion"], [])
            if not pool_scores:
                continue
            pool_avg = sum(pool_scores) / len(pool_scores)
            better_than = sum(1 for s in pool_scores if s < c["score"])
            percentile = (better_than / len(pool_scores)) * 100
            comparisons.append(
                {
                    "criterion": c["criterion"],
                    "your_score": c["score"],
                    "pool_average": round(pool_avg, 1),
                    "percentile": round(percentile, 1),
                    "label": f"Top {max(1, round(100 - percentile))}% in {c['criterion']}",
                }
            )
        return comparisons

    @staticmethod
    def _generate_summary(rank: int, total: int, percentile: float) -> str:
        """Template-based, no LLM (spec's explicit requirement for this agent)."""
        if percentile >= 90:
            tier = "top performer"
        elif percentile >= 75:
            tier = "strong performer"
        elif percentile >= 50:
            tier = "above-average performer"
        elif percentile >= 25:
            tier = "below-average performer"
        else:
            tier = "developing submission"

        return (
            f"Your project ranks #{rank} out of {total} submissions "
            f"(Top {100 - percentile:.0f}%), placing you as a {tier} "
            f"in this hackathon."
        )
