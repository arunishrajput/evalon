"""Round-trip for the Redis bridge between the evaluation graph (which builds
RepoContext in-process) and the separately-dispatched generate_embeddings job."""

from app.embedding.context_cache import cache_embedding_context, load_embedding_context
from app.pipeline.context_builder import CodeSample, RepoContext
from app.pipeline.static_analysis import StaticAnalysisReport


def _repo_context() -> RepoContext:
    return RepoContext(
        submission_id="sub-1",
        hackathon_id="hack-1",
        repo_url="https://github.com/x/y",
        repo_name="y",
        repo_description=None,
        project_type="Python",
        primary_language="Python",
        language_breakdown={"Python": 5},
        tech_stack=["Python"],
        dependency_manifest={},
        readme_content="# Y",
        readme_quality_score=50,
        file_count=1,
        file_paths=["main.py"],
        code_samples=[CodeSample(file="main.py", content="pass")],
        static_analysis=StaticAnalysisReport(),
    )


async def test_cache_embedding_context_roundtrip(redis_client):
    report = {
        "summary": "Solid project.",
        "overall_assessment": "Nice work.",
        "strengths": ["A"],
        "weaknesses": ["B"],
        "architecture_notes": "Monolith",
    }

    await cache_embedding_context(redis_client, "sub-1", _repo_context(), report)
    loaded = await load_embedding_context(redis_client, "sub-1")

    assert loaded is not None
    assert loaded.repo_context.repo_name == "y"
    assert loaded.report_summary == "Solid project."
    assert loaded.strengths == ["A"]
    assert loaded.weaknesses == ["B"]
    assert loaded.architecture_notes == "Monolith"


async def test_load_embedding_context_returns_none_when_absent(redis_client):
    assert await load_embedding_context(redis_client, "missing-submission") is None


async def test_cache_embedding_context_handles_missing_report_fields(redis_client):
    await cache_embedding_context(redis_client, "sub-2", _repo_context(), report={})
    loaded = await load_embedding_context(redis_client, "sub-2")

    assert loaded is not None
    assert loaded.report_summary == ""
    assert loaded.strengths == []
