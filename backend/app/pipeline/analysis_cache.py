"""Bridges the ingest_repository job (Phase 3) and the run_evaluation_pipeline
job's build_context_node (Phase 4) — two separate ARQ jobs, per spec Section
11's job dependency chain. The cloned repo stays on disk across both (cleanup
only happens at the very end of the evaluation graph), but re-running
semgrep/ESLint a second time in build_context_node would be wasteful, so the
already-computed StaticAnalysisReport and project analysis summary are cached
in Redis — same TTL pattern already used for progress events, no new DB
column invented for what is inherently ephemeral pipeline state."""

from redis.asyncio import Redis

from app.pipeline.file_processor import ProjectAnalysis
from app.pipeline.progress import PROGRESS_TTL_SECONDS
from app.pipeline.static_analysis import StaticAnalysisReport
from app.schemas.submission import CachedAnalysisResult


def _cache_key(submission_id: str) -> str:
    return f"evalon:analysis:{submission_id}"


async def cache_analysis_result(
    redis: Redis, submission_id: str, project: ProjectAnalysis, static_analysis: StaticAnalysisReport
) -> None:
    result = CachedAnalysisResult(
        project_type=project.project_type,
        primary_language=project.primary_language,
        language_breakdown=project.language_breakdown,
        dependency_manifest=project.dependency_manifest,
        readme_content=project.readme.content,
        readme_quality_score=project.readme.quality_score,
        tech_stack=project.tech_stack,
        static_analysis=static_analysis,
    )
    await redis.set(_cache_key(submission_id), result.model_dump_json(), ex=PROGRESS_TTL_SECONDS)


async def load_cached_analysis_result(redis: Redis, submission_id: str) -> CachedAnalysisResult | None:
    raw = await redis.get(_cache_key(submission_id))
    if raw is None:
        return None
    return CachedAnalysisResult.model_validate_json(raw)
