"""Stage 3 (static analysis) tests. semgrep/ESLint are network-dependent CLI
tools — their JSON-parsing logic is tested by mocking the subprocess
boundary (_run_subprocess) rather than hitting the real registry in tests."""

from pathlib import Path

from app.pipeline import static_analysis
from app.utils.file_utils import build_file_tree

# No module-level `pytestmark = pytest.mark.asyncio` here — this file mixes
# sync and async tests, and pytest.ini's `asyncio_mode = auto` already
# detects async tests automatically without it.


def test_radon_flags_high_complexity_function(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    python_files = [f for f in files if f.language == "Python"]
    report = static_analysis._run_radon(python_files)

    assert report.functions_analyzed >= 2
    flagged_names = {f.function_name for f in report.high_complexity_functions}
    assert "undocumented_function" in flagged_names
    assert "documented_function" not in flagged_names


def test_file_structure_detects_all_signals(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    report = static_analysis._analyze_file_structure(files)
    assert report.has_tests
    assert report.has_ci_config
    assert report.has_dockerfile
    assert report.has_gitignore
    assert report.has_license


def test_documentation_coverage_counts_docstrings(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    python_files = [f for f in files if f.language == "Python"]
    documented, total = static_analysis._python_doc_coverage(python_files)
    # main.py: documented_function, DocumentedClass have docstrings;
    # undocumented_function and DocumentedClass.method do not.
    # tests/test_main.py: test_ok has no docstring either.
    assert documented == 2
    assert total == 5


async def test_run_subprocess_missing_binary_returns_none_not_raise():
    result = await static_analysis._run_subprocess(["this-binary-does-not-exist"], cwd=Path("/tmp"))
    assert result is None


async def test_run_static_analysis_degrades_when_semgrep_unavailable(synthetic_repo: Path, monkeypatch):
    async def fake_subprocess_none(*args, **kwargs):
        return None

    monkeypatch.setattr(static_analysis, "_run_subprocess", fake_subprocess_none)

    files = build_file_tree(synthetic_repo)
    report = await static_analysis.run_static_analysis(synthetic_repo, files)

    assert report.semgrep_findings == []
    assert report.errors  # tool unavailability must be recorded, not silently treated as "no findings"
    assert report.radon.functions_analyzed >= 2
    assert report.file_structure.has_tests


async def test_run_static_analysis_parses_semgrep_json(synthetic_repo: Path, monkeypatch):
    fake_output = (
        '{"results": [{"path": "main.py", "start": {"line": 3}, '
        '"check_id": "python.lang.security.fake-rule", '
        '"extra": {"message": "fake finding", "severity": "WARNING"}}]}'
    )

    async def fake_subprocess(args, cwd):
        if args[0] == "semgrep":
            return fake_output
        return None

    monkeypatch.setattr(static_analysis, "_run_subprocess", fake_subprocess)

    files = build_file_tree(synthetic_repo)
    report = await static_analysis.run_static_analysis(synthetic_repo, files)

    assert len(report.semgrep_findings) == 1
    assert report.semgrep_findings[0].rule_id == "python.lang.security.fake-rule"
    assert report.semgrep_findings[0].line == 3
