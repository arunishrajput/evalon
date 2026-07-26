"""Cross-submission percentile normalization (spec Stage 8). Pure functions
— no DB access — so ranking math is trivially unit-testable in isolation
from the persistence layer.

Percentile formula is the spec's literal one:
    percentile = submissions_below / total_submissions × 100
Ties get the same percentile (by construction — "below" means strictly
less-than) and standard competition ranking (1, 1, 3 — not 1, 1, 2), matching
common leaderboard conventions.
"""

from dataclasses import dataclass


@dataclass
class RankedSubmission:
    submission_id: str
    score: float
    rank: int
    percentile: float
    normalized_score: float


def compute_rankings(scored_submissions: list[tuple[str, float]]) -> list[RankedSubmission]:
    """scored_submissions: (submission_id, final_score) pairs, any order.
    Returns rankings sorted by score descending. normalized_score currently
    mirrors final_score — the spec defines no separate normalization formula
    beyond percentile, so the `rankings.normalized_score` column is this
    (rounded) value rather than a second, undefined transform."""
    if not scored_submissions:
        return []

    total = len(scored_submissions)
    sorted_submissions = sorted(scored_submissions, key=lambda item: item[1], reverse=True)

    results = []
    current_rank = 0
    previous_score = None
    for index, (submission_id, score) in enumerate(sorted_submissions):
        if score != previous_score:
            current_rank = index + 1  # standard competition ranking (1, 1, 3)
        previous_score = score

        below = sum(1 for _, other_score in scored_submissions if other_score < score)
        percentile = round((below / total) * 100, 2)

        results.append(
            RankedSubmission(
                submission_id=submission_id,
                score=score,
                rank=current_rank,
                percentile=percentile,
                normalized_score=round(score, 3),
            )
        )
    return results
