"""Leaderboard / ranking response schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel


class RankingEntry(BaseModel):
    submission_id: uuid.UUID
    rank: int
    percentile: Decimal | None
    normalized_score: Decimal | None
    final_score: Decimal | None
    finalized: bool
    repo_name: str | None = None
    participant_name: str | None = None  # only populated after finalization, per spec Section 10
    is_you: bool = False
