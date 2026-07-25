"""Stage 2 (file processing) tests against the synthetic repo fixture."""

from pathlib import Path

from app.pipeline.file_processor import (
    analyze_project,
    analyze_readme,
    detect_project_type,
    extract_tech_stack,
    parse_dependency_manifest,
)
from app.utils.file_utils import build_file_tree, language_breakdown


def test_detect_project_type_python(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    assert detect_project_type(files) == "Python"


def test_readme_quality_score_all_signals_present(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    readme = analyze_readme(files)
    assert readme.has_description
    assert readme.has_setup_instructions
    assert readme.has_demo_link
    assert readme.has_architecture_diagram
    assert readme.has_badges
    assert readme.quality_score == 100


def test_readme_missing_returns_zero_score(tmp_path: Path):
    empty_root = tmp_path / "no_readme"
    empty_root.mkdir()
    files = build_file_tree(empty_root)
    readme = analyze_readme(files)
    assert readme.content is None
    assert readme.quality_score == 0


def test_dependency_manifest_parses_requirements_txt(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    manifest = parse_dependency_manifest(files)
    assert set(manifest["pip"]) == {"fastapi", "sqlalchemy"}


def test_tech_stack_includes_language_and_dependencies(synthetic_repo: Path):
    files = build_file_tree(synthetic_repo)
    lang_breakdown = language_breakdown(files)
    manifest = parse_dependency_manifest(files)
    tech_stack = extract_tech_stack(files, manifest, lang_breakdown)

    assert "Python" in tech_stack
    assert "FastAPI" in tech_stack
    assert "SQLAlchemy" in tech_stack
    assert "Docker" in tech_stack
    assert "GitHub Actions" in tech_stack


def test_analyze_project_end_to_end(synthetic_repo: Path):
    result = analyze_project(synthetic_repo)
    assert result.project_type == "Python"
    assert result.primary_language == "Python"
    assert result.readme.quality_score == 100
    assert len(result.files) > 0
