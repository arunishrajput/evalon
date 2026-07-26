"""Side-by-side submission comparison response schema (spec Section 6)."""

from decimal import Decimal

from pydantic import BaseModel


class CriterionScore(BaseModel):
    criterion: str
    score: float
    weight: float
    top_evidence: list[str]


class ComparisonSubmission(BaseModel):
    submission_id: str
    repo_name: str | None
    participant_name: str
    final_score: Decimal | None
    scores_by_criterion: list[CriterionScore]
    strengths: list[str]
    weaknesses: list[str]
    tech_stack: list[str]
    rank: int | None
    percentile: float | None


class ComparisonResponse(BaseModel):
    submissions: list[ComparisonSubmission]
