"""build_chunks: which chunk types get produced from a captured evaluation
context, and that each carries the content a mentor conversation would
actually need."""

from app.embedding.chunker import build_chunks
from app.embedding.context_cache import CachedEmbeddingContext
from app.pipeline.context_builder import CodeSample, RepoContext
from app.pipeline.static_analysis import ComplexityFinding, DocumentationCoverage, RadonReport, StaticAnalysisReport


def _repo_context(**overrides) -> RepoContext:
    defaults = dict(
        submission_id="sub-1",
        hackathon_id="hack-1",
        repo_url="https://github.com/x/y",
        repo_name="y",
        repo_description=None,
        project_type="Python",
        primary_language="Python",
        language_breakdown={"Python": 5},
        tech_stack=["Python", "FastAPI"],
        dependency_manifest={"pip": ["fastapi"]},
        readme_content="# Y\n\nDoes things.",
        readme_quality_score=50,
        file_count=3,
        file_paths=["main.py"],
        code_samples=[CodeSample(file="main.py", content="def f():\n    pass\n")],
        static_analysis=StaticAnalysisReport(
            radon=RadonReport(
                functions_analyzed=3,
                average_complexity=4.0,
                high_complexity_functions=[ComplexityFinding(file="main.py", function_name="f", complexity=15, rank="D")],
            ),
            documentation_coverage=DocumentationCoverage(documented=1, total=3),
        ),
    )
    defaults.update(overrides)
    return RepoContext(**defaults)


def _context(**overrides) -> CachedEmbeddingContext:
    defaults = dict(
        repo_context=_repo_context(),
        report_summary="y is a solid project scoring 80/100.",
        overall_assessment="Well structured.",
        strengths=["Clean code"],
        weaknesses=["No tests"],
        architecture_notes="Monolith",
    )
    defaults.update(overrides)
    return CachedEmbeddingContext(**defaults)


def test_build_chunks_includes_expected_types():
    chunks = build_chunks(_context())
    types = {c.chunk_type for c in chunks}
    assert {"repo_summary", "evaluation_summary", "readme", "code", "static_analysis"} <= types


def test_repo_summary_chunk_mentions_tech_stack_and_architecture():
    chunks = build_chunks(_context())
    summary = next(c for c in chunks if c.chunk_type == "repo_summary")
    assert "FastAPI" in summary.content
    assert "Monolith" in summary.content


def test_evaluation_summary_chunk_mentions_strengths_and_weaknesses():
    chunks = build_chunks(_context())
    summary = next(c for c in chunks if c.chunk_type == "evaluation_summary")
    assert "Clean code" in summary.content
    assert "No tests" in summary.content


def test_code_chunk_carries_file_metadata():
    chunks = build_chunks(_context())
    code_chunks = [c for c in chunks if c.chunk_type == "code"]
    assert len(code_chunks) == 1
    assert code_chunks[0].metadata == {"file": "main.py"}
    assert "def f():" in code_chunks[0].content


def test_missing_readme_skips_readme_chunk():
    context = _context(repo_context=_repo_context(readme_content=None))
    chunks = build_chunks(context)
    assert not any(c.chunk_type == "readme" for c in chunks)


def test_static_analysis_chunk_surfaces_high_complexity_finding():
    chunks = build_chunks(_context())
    static_chunk = next(c for c in chunks if c.chunk_type == "static_analysis")
    assert "complexity 15" in static_chunk.content
    assert "f" in static_chunk.content


def test_no_static_analysis_findings_omits_chunk():
    context = _context(repo_context=_repo_context(static_analysis=StaticAnalysisReport()))
    chunks = build_chunks(context)
    assert not any(c.chunk_type == "static_analysis" for c in chunks)


def test_long_content_is_truncated():
    context = _context(repo_context=_repo_context(readme_content="x" * 10_000))
    chunks = build_chunks(context)
    readme_chunk = next(c for c in chunks if c.chunk_type == "readme")
    assert len(readme_chunk.content) < 10_000
    assert readme_chunk.content.endswith("(truncated)")
