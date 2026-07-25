"""ARQ job task definitions. generate_embeddings, recompute_rankings, and
update_hackathon_stats are added in Phases 5 and 6 as their dependencies
come online."""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.core.exceptions import RepositoryIngestionError
from app.database import async_session_factory
from app.dependencies import get_redis
from app.models.submission import Submission, SubmissionStatus
from app.pipeline.analysis_cache import cache_analysis_result
from app.pipeline.file_processor import ProjectAnalysis, analyze_project
from app.pipeline.ingestion import ingest_repository as clone_repo_to_disk
from app.pipeline.progress import emit_progress
from app.pipeline.static_analysis import StaticAnalysisReport, run_static_analysis

logger = logging.getLogger("evalon.jobs")


async def ping(ctx: dict) -> str:
    """Trivial job used to verify the ARQ worker is actually picking up and
    executing jobs from the queue (used by Phase 1 infra verification and,
    later, by `make model-status`-style operational checks)."""
    logger.info("ping job executed")
    return "pong"


async def ingest_repository(ctx: dict, submission_id: str) -> None:
    """Stages 0-3: clone, file processing, static analysis. Leaves the clone
    on disk and the analysis results cached in Redis for the Phase 4
    run_evaluation_pipeline job to pick up — cleanup only happens at the end
    of the full evaluation graph (spec Section 7's cleanup_node)."""
    settings = get_settings()
    redis = get_redis()

    async with async_session_factory() as db:
        submission = await db.get(Submission, uuid.UUID(submission_id))
        if submission is None:
            logger.error("ingest_repository: submission %s not found", submission_id)
            return

        try:
            repo_path = await _run_clone_stage(db, redis, submission, settings)
            project, static_report = await _run_analysis_stages(db, redis, submission, repo_path)
            await cache_analysis_result(redis, submission_id, project, static_report)
            await _emit_analysis_complete(redis, submission_id, static_report)
        except RepositoryIngestionError as exc:
            await _fail_submission(db, redis, submission, exc.message, stage="cloning")
        except Exception as exc:  # noqa: BLE001 - a job crash must never propagate as an unhandled task failure
            logger.error("ingest_repository failed for %s: %s", submission_id, exc, exc_info=True)
            await _fail_submission(
                db,
                redis,
                submission,
                "An unexpected error occurred while processing your submission.",
                stage="analyzing",
            )


async def _run_clone_stage(db, redis, submission: Submission, settings) -> Path:
    submission_id = str(submission.id)
    submission.status = SubmissionStatus.CLONING
    await db.commit()
    await emit_progress(
        redis, submission_id, "progress",
        {"stage": "cloning", "message": "Cloning your repository...", "progress_pct": 5, "degraded": False},
    )

    repo_path = await clone_repo_to_disk(
        submission.repo_url,
        submission_id,
        workspace_dir=settings.workspace_dir,
        timeout_seconds=settings.clone_timeout_seconds,
        max_size_mb=settings.max_repo_size_mb,
        max_file_count=settings.max_file_count,
    )

    submission.clone_completed_at = datetime.now(timezone.utc)
    await db.commit()
    await emit_progress(
        redis, submission_id, "progress",
        {"stage": "cloning", "message": "Repository cloned successfully.", "progress_pct": 20, "degraded": False},
    )
    return repo_path


async def _run_analysis_stages(
    db, redis, submission: Submission, repo_path: Path
) -> tuple[ProjectAnalysis, StaticAnalysisReport]:
    submission_id = str(submission.id)
    submission.status = SubmissionStatus.ANALYZING
    await db.commit()
    await emit_progress(
        redis, submission_id, "progress",
        {"stage": "analyzing", "message": "Analyzing file structure...", "progress_pct": 30, "degraded": False},
    )

    project = analyze_project(repo_path)
    submission.tech_stack = project.tech_stack
    await db.commit()
    await emit_progress(
        redis, submission_id, "progress",
        {"stage": "analyzing", "message": "File structure analyzed.", "progress_pct": 45, "degraded": False},
    )

    await emit_progress(
        redis, submission_id, "progress",
        {
            "stage": "analyzing",
            "message": "Running static analysis (complexity, security, lint)...",
            "progress_pct": 55,
            "degraded": False,
        },
    )
    static_report = await run_static_analysis(repo_path, project.files)

    if static_report.errors:
        submission.degraded = True
        submission.degraded_reason = "; ".join(static_report.errors)
    submission.analysis_completed_at = datetime.now(timezone.utc)
    await db.commit()
    return project, static_report


async def _emit_analysis_complete(redis, submission_id: str, static_report: StaticAnalysisReport) -> None:
    degraded = bool(static_report.errors)
    await emit_progress(
        redis, submission_id, "progress",
        {"stage": "analyzing", "message": "Static analysis complete.", "progress_pct": 65, "degraded": degraded},
    )
    if degraded:
        await emit_progress(
            redis, submission_id, "degraded",
            {
                "message": "Some static analysis tools failed. Results may be less precise.",
                "affected_agents": [],
            },
        )


async def _fail_submission(db, redis, submission: Submission, message: str, *, stage: str) -> None:
    submission.status = SubmissionStatus.FAILED
    submission.error_message = message
    await db.commit()
    await emit_progress(
        redis, str(submission.id), "error", {"message": message, "stage": stage, "recoverable": False}
    )
