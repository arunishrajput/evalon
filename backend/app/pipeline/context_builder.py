"""Assembles the final RepoContext consumed by the Phase 4 AI agents, from
the file-processing and static-analysis stage outputs. Enforces the memory
standard: at most 5 code samples, 500 lines each (spec Section 18)."""

from pathlib import Path

from pydantic import BaseModel

from app.pipeline.file_processor import ProjectAnalysis
from app.pipeline.static_analysis import StaticAnalysisReport
from app.utils.file_utils import FileEntry, read_text_file_safe

MAX_CODE_SAMPLES = 5
MAX_SAMPLE_LINES = 500

_LOW_SIGNAL_NAMES = {"package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml"}


class CodeSample(BaseModel):
    file: str
    content: str


class RepoContext(BaseModel):
    submission_id: str
    hackathon_id: str
    repo_url: str
    repo_name: str
    repo_description: str | None
    project_type: str
    primary_language: str | None
    language_breakdown: dict[str, int]
    tech_stack: list[str]
    dependency_manifest: dict[str, list[str]]
    readme_content: str | None
    readme_quality_score: int
    file_count: int
    file_paths: list[str]
    code_samples: list[CodeSample]
    static_analysis: StaticAnalysisReport


def _select_representative_files(files: list[FileEntry]) -> list[FileEntry]:
    """Largest non-binary source files, excluding lockfiles (large but not
    meaningful for a human/LLM code-quality read)."""
    candidates = [
        f
        for f in files
        if f.language is not None
        and Path(f.relative_path).name not in _LOW_SIGNAL_NAMES
        and f.language not in ("JSON", "YAML", "Markdown")
    ]
    return sorted(candidates, key=lambda f: f.size_bytes, reverse=True)[:MAX_CODE_SAMPLES]


def _truncate_lines(content: str, max_lines: int) -> str:
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content
    return "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines) - max_lines} more lines)"


def build_repo_context(
    *,
    submission_id: str,
    hackathon_id: str,
    repo_url: str,
    repo_name: str,
    repo_description: str | None,
    project: ProjectAnalysis,
    static_analysis: StaticAnalysisReport,
) -> RepoContext:
    samples = []
    for entry in _select_representative_files(project.files):
        content = read_text_file_safe(entry.absolute_path, max_bytes=100_000)
        if content:
            samples.append(CodeSample(file=entry.relative_path, content=_truncate_lines(content, MAX_SAMPLE_LINES)))

    return RepoContext(
        submission_id=submission_id,
        hackathon_id=hackathon_id,
        repo_url=repo_url,
        repo_name=repo_name,
        repo_description=repo_description,
        project_type=project.project_type,
        primary_language=project.primary_language,
        language_breakdown=project.language_breakdown,
        tech_stack=project.tech_stack,
        dependency_manifest=project.dependency_manifest,
        readme_content=project.readme.content,
        readme_quality_score=project.readme.quality_score,
        file_count=len(project.files),
        file_paths=[f.relative_path for f in project.files],
        code_samples=samples,
        static_analysis=static_analysis,
    )
