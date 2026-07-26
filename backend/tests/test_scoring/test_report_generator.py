"""Report generator (Stage 6): assembled report reflects aggregation
numbers exactly, surfaces degraded state correctly, and never crashes on an
all-abstained (empty-narrative) result set."""

from app.agents.base import AgentResult
from app.pipeline.context_builder import RepoContext
from app.pipeline.static_analysis import StaticAnalysisReport
from app.scoring.report_generator import generate_report


def _repo_context() -> RepoContext:
    return RepoContext(
        submission_id="sub-1",
        hackathon_id="hack-1",
        repo_url="https://github.com/example/project",
        repo_name="project",
        repo_description=None,
        project_type="Python",
        primary_language="Python",
        language_breakdown={},
        tech_stack=["Python"],
        dependency_manifest={},
        readme_content=None,
        readme_quality_score=0,
        file_count=1,
        file_paths=[],
        code_samples=[],
        static_analysis=StaticAnalysisReport(),
    )


def test_report_reflects_aggregation_scores_exactly():
    agent_results = {
        "repo_understanding": AgentResult(
            agent_id="repo_understanding", score_raw=70, confidence=0.8, reasoning="Clear goals.",
            details={"architecture_pattern": "Monolith"},
        ),
    }
    aggregation = {
        "final_score": 70.0,
        "by_criterion": [{"criterion_id": "c1", "criterion": "Understanding", "score": 70.0, "weight": 1.0, "agent_id": "repo_understanding", "confidence": 0.8}],
        "status": "completed",
    }

    report = generate_report(
        repo_context=_repo_context(), agent_results=agent_results, aggregation=aggregation,
        model_versions={"inference_model": "qwen2.5-coder:7b", "embedding_model": "nomic-embed-text"},
    )

    assert report["scores"]["overall"] == 70.0
    assert report["scores"]["by_criterion"] == aggregation["by_criterion"]
    assert report["degraded"] is False
    assert report["degraded_explanation"] is None
    assert report["architecture_notes"] == "Monolith"


def test_degraded_status_surfaces_explanation():
    agent_results = {
        "code_quality": AgentResult.create_abstained("code_quality", "model down", fallback_used=True),
    }
    aggregation = {"final_score": 50.0, "by_criterion": [], "status": "degraded"}

    report = generate_report(
        repo_context=_repo_context(), agent_results=agent_results, aggregation=aggregation, model_versions={},
    )

    assert report["degraded"] is True
    assert "fallback scoring" in report["degraded_explanation"]


def test_all_abstained_report_does_not_crash_and_has_fallback_assessment():
    agent_results = {
        agent_id: AgentResult.create_abstained(agent_id, "model down", fallback_used=True)
        for agent_id in ("repo_understanding", "code_quality", "innovation")
    }
    aggregation = {"final_score": 50.0, "by_criterion": [], "status": "failed"}

    report = generate_report(
        repo_context=_repo_context(), agent_results=agent_results, aggregation=aggregation, model_versions={},
    )

    assert "static analysis" in report["overall_assessment"].lower()
    assert report["architecture_notes"] == "Not determined"


def test_recommendations_and_strengths_deduplicated_across_agents():
    shared_weakness = "No test coverage"
    agent_results = {
        "code_quality": AgentResult(agent_id="code_quality", score_raw=60, weaknesses=[shared_weakness]),
        "innovation": AgentResult(agent_id="innovation", score_raw=60, weaknesses=[shared_weakness]),
    }
    aggregation = {"final_score": 60.0, "by_criterion": [], "status": "completed"}

    report = generate_report(
        repo_context=_repo_context(), agent_results=agent_results, aggregation=aggregation, model_versions={},
    )

    assert report["weaknesses"].count(shared_weakness) == 1  # deduplicated
    assert len(report["recommendations"]) == 2  # one per agent, not merged away
