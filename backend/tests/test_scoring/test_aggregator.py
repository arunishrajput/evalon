"""Deterministic static-analysis-only code quality formula, effective-score
fallback logic, and evaluation-level degradation status (spec Stage 5 /
Section 13's "UNIT TESTS — Graceful Degradation" and aggregation coverage)."""

from dataclasses import dataclass

from app.agents.base import AgentResult
from app.pipeline.static_analysis import (
    ComplexityFinding,
    DocumentationCoverage,
    ErrorHandlingCoverage,
    LintFinding,
    RadonReport,
    StaticAnalysisReport,
)
from app.scoring.aggregator import (
    aggregate_scores,
    compute_anti_pattern_score,
    compute_code_quality_score,
    compute_complexity_score,
    compute_documentation_score,
    compute_error_handling_score,
    compute_modularity_score,
    effective_criterion_score,
)


@dataclass
class _FakeCriterion:
    id: str
    name: str
    weight: float
    agent_id: str | None


def _empty_report() -> StaticAnalysisReport:
    return StaticAnalysisReport()


def test_complexity_score_no_data_is_mild_neutral():
    assert compute_complexity_score(_empty_report()) == 70.0


def test_complexity_score_penalizes_high_complexity_functions():
    report = StaticAnalysisReport(
        radon=RadonReport(
            functions_analyzed=10,
            average_complexity=15.0,
            high_complexity_functions=[
                ComplexityFinding(file="a.py", function_name="f", complexity=20, rank="D")
                for _ in range(5)
            ],
        )
    )
    score = compute_complexity_score(report)
    # high_ratio=0.5 -> -100; avg_complexity excess (15-5)*4=-40; clamped to 0
    assert score == 0.0


def test_modularity_score_uses_maintainability_index_directly():
    report = StaticAnalysisReport(radon=RadonReport(functions_analyzed=3, average_maintainability_index=72.4))
    assert compute_modularity_score(report) == 72.4


def test_documentation_score_ratio():
    report = StaticAnalysisReport(documentation_coverage=DocumentationCoverage(documented=3, total=4))
    assert compute_documentation_score(report) == 75.0


def test_error_handling_score_ratio():
    report = StaticAnalysisReport(error_handling=ErrorHandlingCoverage(functions_with_handling=1, total_functions=4))
    assert compute_error_handling_score(report) == 25.0


def test_anti_pattern_score_penalizes_per_finding():
    report = StaticAnalysisReport(
        semgrep_findings=[
            LintFinding(file="a.py", line=1, rule_id="r", message="m", severity="WARNING") for _ in range(4)
        ]
    )
    assert compute_anti_pattern_score(report) == 80.0  # 100 - 4*5


def test_code_quality_score_matches_hand_computed_weighted_sum():
    """The exact scenario observed live against a real minimal repo
    (octocat/Hello-World): no Python files, empty README, no findings."""
    report = _empty_report()
    # complexity=70*0.30=21, modularity=60*0.25=15, docs=50*0.20=10,
    # error_handling=50*0.15=7.5, anti_pattern=100*0.10=10 -> 63.5
    assert compute_code_quality_score(report) == 63.5


def test_effective_criterion_score_code_quality_fallback_recomputes_deterministically():
    criterion = _FakeCriterion(id="c1", name="Code Quality", weight=0.4, agent_id="code_quality")
    abstained = AgentResult.create_abstained("code_quality", "model down", fallback_used=True)
    report = _empty_report()

    score, confidence = effective_criterion_score(criterion, abstained, report)

    assert score == compute_code_quality_score(report)  # NOT the neutral 50 default
    assert confidence == 0.5


def test_effective_criterion_score_innovation_fallback_uses_neutral_default():
    """No deterministic tool measures 'originality' — abstained innovation
    falls back to the neutral AgentResult default, not a fabricated formula."""
    criterion = _FakeCriterion(id="c2", name="Innovation", weight=0.35, agent_id="innovation")
    abstained = AgentResult.create_abstained("innovation", "model down", fallback_used=True)

    score, confidence = effective_criterion_score(criterion, abstained, _empty_report())

    assert score == 50.0
    assert confidence == 0.0


def test_effective_criterion_score_unmapped_criterion_is_neutral():
    criterion = _FakeCriterion(id="c3", name="Presentation", weight=0.1, agent_id=None)
    score, confidence = effective_criterion_score(criterion, None, _empty_report())
    assert score == 50.0
    assert confidence == 0.0


def _criteria() -> list[_FakeCriterion]:
    return [
        _FakeCriterion(id="cq", name="Code Quality", weight=0.4, agent_id="code_quality"),
        _FakeCriterion(id="in", name="Innovation", weight=0.35, agent_id="innovation"),
        _FakeCriterion(id="ru", name="Understanding", weight=0.25, agent_id="repo_understanding"),
    ]


def test_aggregate_scores_all_succeed_is_completed():
    results = {
        "code_quality": AgentResult(agent_id="code_quality", score_raw=80, confidence=0.9),
        "innovation": AgentResult(agent_id="innovation", score_raw=60, confidence=0.7),
        "repo_understanding": AgentResult(agent_id="repo_understanding", score_raw=70, confidence=0.8),
    }
    aggregation = aggregate_scores(_criteria(), results, _empty_report())

    assert aggregation["status"] == "completed"
    assert aggregation["final_score"] == round(80 * 0.4 + 60 * 0.35 + 70 * 0.25, 3)
    assert len(aggregation["by_criterion"]) == 3


def test_aggregate_scores_one_fallback_is_degraded_not_failed():
    results = {
        "code_quality": AgentResult(agent_id="code_quality", score_raw=80, confidence=0.9),
        "innovation": AgentResult.create_abstained("innovation", "timed out", fallback_used=True),
        "repo_understanding": AgentResult(agent_id="repo_understanding", score_raw=70, confidence=0.8),
    }
    aggregation = aggregate_scores(_criteria(), results, _empty_report())

    assert aggregation["status"] == "degraded"
    assert aggregation["final_score"] is not None  # degraded evaluations still have a valid score


def test_aggregate_scores_all_abstained_is_failed():
    results = {
        agent_id: AgentResult.create_abstained(agent_id, "model down", fallback_used=True)
        for agent_id in ("code_quality", "innovation", "repo_understanding")
    }
    aggregation = aggregate_scores(_criteria(), results, _empty_report())

    assert aggregation["status"] == "failed"


def test_aggregate_scores_missing_agent_result_treated_as_abstained():
    """A criterion mapped to an agent that never even ran (e.g. crashed before
    populating state) must not crash aggregation."""
    results = {"code_quality": AgentResult(agent_id="code_quality", score_raw=80, confidence=0.9)}
    aggregation = aggregate_scores(_criteria(), results, _empty_report())

    assert aggregation["status"] == "degraded"  # 1/3 succeeded, not all abstained -> degraded
    scores_by_agent = {c["agent_id"]: c["score"] for c in aggregation["by_criterion"]}
    assert scores_by_agent["innovation"] == 50.0
    assert scores_by_agent["repo_understanding"] == 50.0


def test_aggregate_scores_empty_criteria_list_does_not_crash():
    aggregation = aggregate_scores([], {}, _empty_report())
    assert aggregation["status"] == "completed"
    assert aggregation["final_score"] == 0.0
    assert aggregation["by_criterion"] == []
