"""Weighted score aggregation with graceful degradation (spec Stage 5).

DETERMINISTIC STATIC-ANALYSIS-ONLY CODE QUALITY FORMULA (documented per spec's
explicit requirement, and per P1 — "scores come from structured tool output,
never a raw LLM number"):

    code_quality_score =
        0.30 * complexity_score        (penalizes high-cyclomatic-complexity functions)
      + 0.25 * modularity_score        (radon maintainability index, already 0-100)
      + 0.20 * documentation_score     (documented / total function+class ratio)
      + 0.15 * error_handling_score    (functions with try/except or try/catch)
      + 0.10 * anti_pattern_score      (penalized per semgrep finding)

This is the SAME formula CodeQualityAgent uses for score_raw in the normal
(non-degraded) path — the LLM's role for that agent is narrative
interpretation only, never the score itself (spec Section 8, Agent 2's
explicit weighted formula). Using one function for both the normal and the
fallback path guarantees "AI explained this score" and "static analysis
computed this score" are always consistent.

repo_understanding and innovation have no equivalent deterministic tool (no
formula measures "clarity of vision" or "originality") — when those agents
abstain, aggregation falls back to the neutral AgentResult default
(score 50, confidence 0) rather than inventing a formula the spec doesn't
provide.
"""

from typing import TYPE_CHECKING

from app.pipeline.static_analysis import StaticAnalysisReport

if TYPE_CHECKING:
    from app.agents.base import AgentResult
    from app.models.criterion import Criterion

COMPLEXITY_WEIGHT = 0.30
MODULARITY_WEIGHT = 0.25
DOCUMENTATION_WEIGHT = 0.20
ERROR_HANDLING_WEIGHT = 0.15
ANTI_PATTERN_WEIGHT = 0.10

NEUTRAL_ABSTAIN_SCORE = 50.0  # matches AgentResult.create_abstained's default
CODE_QUALITY_AGENT_ID = "code_quality"


def compute_complexity_score(static_analysis: StaticAnalysisReport) -> float:
    radon = static_analysis.radon
    if radon.functions_analyzed == 0:
        return 70.0  # insufficient data — mild neutral, not a reward or penalty
    high_ratio = len(radon.high_complexity_functions) / radon.functions_analyzed
    score = 100.0 - (high_ratio * 100 * 2) - max(0.0, radon.average_complexity - 5) * 4
    return max(0.0, min(100.0, score))


def compute_modularity_score(static_analysis: StaticAnalysisReport) -> float:
    radon = static_analysis.radon
    if radon.functions_analyzed == 0:
        return 60.0  # no maintainability-index data available (e.g. non-Python repo)
    return max(0.0, min(100.0, radon.average_maintainability_index))


def compute_documentation_score(static_analysis: StaticAnalysisReport) -> float:
    coverage = static_analysis.documentation_coverage
    if coverage.total == 0:
        return 50.0
    return coverage.ratio * 100


def compute_error_handling_score(static_analysis: StaticAnalysisReport) -> float:
    coverage = static_analysis.error_handling
    if coverage.total_functions == 0:
        return 50.0
    return coverage.ratio * 100


def compute_anti_pattern_score(static_analysis: StaticAnalysisReport) -> float:
    finding_count = len(static_analysis.semgrep_findings)
    return max(0.0, 100.0 - min(finding_count * 5, 100))


def compute_code_quality_score(static_analysis: StaticAnalysisReport) -> float:
    return (
        compute_complexity_score(static_analysis) * COMPLEXITY_WEIGHT
        + compute_modularity_score(static_analysis) * MODULARITY_WEIGHT
        + compute_documentation_score(static_analysis) * DOCUMENTATION_WEIGHT
        + compute_error_handling_score(static_analysis) * ERROR_HANDLING_WEIGHT
        + compute_anti_pattern_score(static_analysis) * ANTI_PATTERN_WEIGHT
    )


def effective_criterion_score(
    criterion: "Criterion", agent_result: "AgentResult | None", static_analysis: StaticAnalysisReport
) -> tuple[float, float]:
    """Returns (effective_score, confidence) for one criterion. If the mapped
    agent abstained or used fallback scoring: code_quality is recomputed
    deterministically (it never actually needed the LLM for its score); the
    other two agents fall back to the neutral abstain default they already
    carry, since no deterministic formula exists for them."""
    if agent_result is None:
        return NEUTRAL_ABSTAIN_SCORE, 0.0
    if agent_result.abstained or agent_result.fallback_used:
        if criterion.agent_id == CODE_QUALITY_AGENT_ID:
            return compute_code_quality_score(static_analysis), 0.5
        return agent_result.score_raw, agent_result.confidence
    return agent_result.score_raw, agent_result.confidence


def aggregate_scores(
    criteria: list["Criterion"],
    agent_results: dict[str, "AgentResult"],
    static_analysis: StaticAnalysisReport,
) -> dict:
    """final_score = Σ (criterion_weight × effective_criterion_score), plus
    the evaluation-level degradation status per Stage 5:
      - ANY agent used fallback/abstained → status='degraded' (partial results)
      - ALL agents abstained → status='failed' (no results)
      - otherwise → status='completed'
    """
    by_criterion = []
    weighted_sum = 0.0
    any_real_result = False
    any_fallback = False

    for criterion in criteria:
        agent_result = agent_results.get(criterion.agent_id) if criterion.agent_id else None
        score, confidence = effective_criterion_score(criterion, agent_result, static_analysis)
        weighted_sum += float(criterion.weight) * score
        by_criterion.append(
            {
                "criterion_id": str(criterion.id),
                "criterion": criterion.name,
                "score": round(score, 2),
                "weight": float(criterion.weight),
                "agent_id": criterion.agent_id,
                "confidence": confidence,
            }
        )
        if agent_result is not None and not agent_result.abstained:
            any_real_result = True
        # A missing agent_result (criterion mapped to an agent that never even
        # ran) is at least as bad as an abstained one — must also count
        # toward "degraded", not be silently ignored.
        if agent_result is None or agent_result.abstained or agent_result.fallback_used:
            any_fallback = True

    if criteria and not any_real_result:
        status = "failed"
    elif any_fallback:
        status = "degraded"
    else:
        status = "completed"

    return {
        "final_score": round(weighted_sum, 3),
        "by_criterion": by_criterion,
        "status": status,
    }
