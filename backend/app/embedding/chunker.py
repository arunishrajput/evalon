"""Splits a submission's captured RepoContext + evaluation report into small,
independently-retrievable text chunks for the mentor chatbot's RAG pipeline
(spec Section 4's embedding/chunker.py, Section 9's retrieval-by-similarity
design). Chunk boundaries follow natural content units (whole README, whole
code sample, one summary block) rather than fixed-size splitting, since
context_builder.py already caps code samples to 5 files / 500 lines each —
these are already small enough for nomic-embed-text's context window."""

from pydantic import BaseModel

from app.embedding.context_cache import CachedEmbeddingContext

MAX_CHUNK_CHARS = 3000


class Chunk(BaseModel):
    chunk_type: str
    content: str
    metadata: dict = {}


def build_chunks(ctx: CachedEmbeddingContext) -> list[Chunk]:
    repo = ctx.repo_context
    chunks: list[Chunk] = [_repo_summary_chunk(ctx), _evaluation_summary_chunk(ctx)]

    if repo.readme_content:
        chunks.append(Chunk(chunk_type="readme", content=_truncate(repo.readme_content)))

    for sample in repo.code_samples:
        chunks.append(
            Chunk(
                chunk_type="code",
                content=_truncate(f"File: {sample.file}\n\n{sample.content}"),
                metadata={"file": sample.file},
            )
        )

    static_analysis_chunk = _static_analysis_chunk(ctx)
    if static_analysis_chunk is not None:
        chunks.append(static_analysis_chunk)

    return chunks


def _repo_summary_chunk(ctx: CachedEmbeddingContext) -> Chunk:
    repo = ctx.repo_context
    content = (
        f"Project: {repo.repo_name}\n"
        f"Type: {repo.project_type}\n"
        f"Primary language: {repo.primary_language or 'unknown'}\n"
        f"Tech stack: {', '.join(repo.tech_stack) or 'unknown'}\n"
        f"Dependencies: {', '.join(sorted({dep for deps in repo.dependency_manifest.values() for dep in deps})) or 'none detected'}\n"
        f"Architecture: {ctx.architecture_notes}\n"
    )
    return Chunk(chunk_type="repo_summary", content=_truncate(content))


def _evaluation_summary_chunk(ctx: CachedEmbeddingContext) -> Chunk:
    content = (
        f"{ctx.report_summary}\n\n{ctx.overall_assessment}\n\n"
        f"Strengths: {'; '.join(ctx.strengths) or 'none noted'}\n"
        f"Weaknesses: {'; '.join(ctx.weaknesses) or 'none noted'}\n"
    )
    return Chunk(chunk_type="evaluation_summary", content=_truncate(content))


def _static_analysis_chunk(ctx: CachedEmbeddingContext) -> Chunk | None:
    sa = ctx.repo_context.static_analysis
    lines: list[str] = []

    if sa.radon.functions_analyzed:
        lines.append(
            f"Average cyclomatic complexity: {sa.radon.average_complexity:.1f} "
            f"across {sa.radon.functions_analyzed} functions."
        )
        for finding in sa.radon.high_complexity_functions[:5]:
            lines.append(f"High complexity: {finding.function_name} in {finding.file} (complexity {finding.complexity}).")

    for finding in sa.semgrep_findings[:5]:
        lines.append(f"Security finding ({finding.severity}) in {finding.file}:{finding.line} — {finding.message}")

    for finding in sa.eslint_findings[:5]:
        lines.append(f"Lint finding ({finding.severity}) in {finding.file}:{finding.line} — {finding.message}")

    if sa.documentation_coverage.total:
        lines.append(
            f"Documentation coverage: {sa.documentation_coverage.documented}/{sa.documentation_coverage.total} "
            f"functions documented."
        )

    if not lines:
        return None
    return Chunk(chunk_type="static_analysis", content=_truncate("\n".join(lines)))


def _truncate(text: str, limit: int = MAX_CHUNK_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"
