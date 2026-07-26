"""Admin live-dashboard response schema (spec Section 6's dashboard endpoints)."""

from decimal import Decimal

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_submissions: int
    evaluations_completed: int
    evaluations_in_progress: int
    evaluations_queued: int
    evaluations_failed: int
    score_distribution: dict[str, int]
    tech_stack_frequency: dict[str, int]
    avg_score: Decimal | None
    top5_preview: list[dict]
