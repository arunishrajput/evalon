"""Cross-submission percentile normalization (spec Stage 8's literal formula
and Section 13's explicit edge cases: empty pool, single submission, tied
scores)."""

from app.scoring.normalizer import compute_rankings


def test_empty_pool_returns_empty_list():
    assert compute_rankings([]) == []


def test_single_submission_ranks_first_with_zero_percentile():
    """Literal spec formula: percentile = submissions_below / total × 100.
    With one submission, submissions_below=0, so percentile is 0% even
    though it's the only (and therefore best) entry — an intentional,
    literal implementation of the spec's formula, not a bug."""
    result = compute_rankings([("a", 75.0)])
    assert len(result) == 1
    assert result[0].rank == 1
    assert result[0].percentile == 0.0
    assert result[0].normalized_score == 75.0


def test_distinct_scores_rank_and_percentile():
    result = compute_rankings([("a", 40.0), ("b", 80.0), ("c", 60.0)])
    by_id = {r.submission_id: r for r in result}

    assert by_id["b"].rank == 1
    assert by_id["b"].percentile == round(2 / 3 * 100, 2)
    assert by_id["c"].rank == 2
    assert by_id["c"].percentile == round(1 / 3 * 100, 2)
    assert by_id["a"].rank == 3
    assert by_id["a"].percentile == 0.0


def test_tied_scores_share_rank_and_percentile():
    """Standard competition ranking (1, 1, 3) — ties skip the next rank."""
    result = compute_rankings([("a", 80.0), ("b", 80.0), ("c", 50.0)])
    by_id = {r.submission_id: r for r in result}

    assert by_id["a"].rank == 1
    assert by_id["b"].rank == 1
    assert by_id["a"].percentile == by_id["b"].percentile == round(1 / 3 * 100, 2)
    assert by_id["c"].rank == 3
    assert by_id["c"].percentile == 0.0


def test_all_tied_scores_all_rank_first():
    result = compute_rankings([("a", 50.0), ("b", 50.0), ("c", 50.0)])
    assert all(r.rank == 1 for r in result)
    assert all(r.percentile == 0.0 for r in result)


def test_result_sorted_by_score_descending():
    result = compute_rankings([("a", 10.0), ("b", 90.0), ("c", 50.0)])
    assert [r.submission_id for r in result] == ["b", "c", "a"]
