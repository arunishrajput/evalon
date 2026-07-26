"""ARQ job task definitions."""

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.agents.llm_provider import LLMProvider
from app.config import get_settings
from app.core.exceptions import ModelUnavailableError, RepositoryIngestionError
from app.database import async_session_factory
from app.dependencies import get_model_queue_manager, get_redis
from app.embedding.chunker import build_chunks
from app.embedding.context_cache import load_embedding_context
from app.embedding.embedder import embed_and_store_chunks
from app.models.criterion import Criterion
from app.models.submission import Submission, SubmissionStatus
from app.orchestration.graph import build_graph
from app.orchestration.nodes import PipelineContext
from app.pipeline.analysis_cache import cache_analysis_result
from app.pipeline.file_processor import ProjectAnalysis, analyze_project
from app.pipeline.ingestion import ingest_repository as clone_repo_to_disk
from app.pipeline.progress import emit_progress
from app.pipeline.static_analysis import StaticAnalysisReport, run_static_analysis
from app.scoring.ranking_service import recompute_rankings_for_hackathon
from app.scoring.stats_service import upsert_hackathon_stats

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
            await ctx["redis"].enqueue_job("run_evaluation_pipeline", submission_id)
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


async def run_evaluation_pipeline(ctx: dict, submission_id: str) -> None:
    """Stage 4-8: the sequential LangGraph evaluation (spec Section 7). Every
    node in the graph is independently fault-tolerant by construction — this
    top-level try/except is a last-resort safety net for a genuine bug in
    the orchestration layer itself, not the expected failure path."""
    settings = get_settings()
    redis = get_redis()
    model_queue = get_model_queue_manager()

    async with async_session_factory() as db:
        submission = await db.get(Submission, uuid.UUID(submission_id))
        if submission is None:
            logger.error("run_evaluation_pipeline: submission %s not found", submission_id)
            return

        criteria = list(
            await db.scalars(select(Criterion).where(Criterion.hackathon_id == submission.hackathon_id))
        )
        pipeline_ctx = PipelineContext(
            db=db,
            redis=redis,
            model_queue=model_queue,
            llm=LLMProvider(settings),
            settings=settings,
            criteria=criteria,
        )
        graph = build_graph(pipeline_ctx)

        initial_state = {
            "submission_id": submission_id,
            "hackathon_id": str(submission.hackathon_id),
            "repo_context": None,
            "agent_results": {},
            "errors": [],
            "completed_agents": [],
            "model_lock_acquired": False,
            "pipeline_start_time": time.monotonic(),
            "aggregation": None,
            "report": None,
        }
        hackathon_id = submission.hackathon_id
        try:
            await graph.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001 - top-level safety net; nodes should never raise, but a bug here must not crash the ARQ worker
            logger.error("run_evaluation_pipeline crashed for %s: %s", submission_id, exc, exc_info=True)
            submission.status = SubmissionStatus.FAILED
            submission.error_message = "An unexpected error occurred during evaluation."
            await db.commit()
            await emit_progress(
                redis, submission_id, "error",
                {"message": "An unexpected error occurred during evaluation.", "stage": "evaluating", "recoverable": True},
            )

    # Deviates from the spec's literal linear job chain (run_evaluation_pipeline
    # -> generate_embeddings -> recompute_rankings -> update_hackathon_stats):
    # rankings/stats must never be blocked by embeddings being slow, absent, or
    # failed — all three are dispatched directly here, independent of each other.
    await ctx["redis"].enqueue_job("generate_embeddings", submission_id)
    await ctx["redis"].enqueue_job("recompute_rankings", str(hackathon_id))
    await ctx["redis"].enqueue_job("update_hackathon_stats", str(hackathon_id))


async def recompute_rankings(ctx: dict, hackathon_id: str) -> None:
    async with async_session_factory() as db:
        await recompute_rankings_for_hackathon(db, uuid.UUID(hackathon_id))
        await db.commit()


async def update_hackathon_stats(ctx: dict, hackathon_id: str) -> None:
    async with async_session_factory() as db:
        await upsert_hackathon_stats(db, uuid.UUID(hackathon_id))
        await db.commit()


async def generate_embeddings(ctx: dict, submission_id: str) -> None:
    """Stage 7 (spec Section 7): chunks the repo + evaluation context cached
    by save_results_node and embeds them via nomic-embed-text. A missing
    cache entry, a lock timeout, or an Ollama outage are all treated the
    same way — log a warning and leave the mentor chatbot unavailable for
    this submission — never a crash, never a retryable failure that blocks
    anything else in the pipeline (P3)."""
    redis = get_redis()
    model_queue = get_model_queue_manager()
    settings = get_settings()

    embedding_context = await load_embedding_context(redis, submission_id)
    if embedding_context is None:
        logger.warning("generate_embeddings: no cached context for submission %s — skipping", submission_id)
        return

    chunks = build_chunks(embedding_context)
    async with async_session_factory() as db:
        try:
            count = await embed_and_store_chunks(
                db=db, llm=LLMProvider(settings), model_queue=model_queue,
                submission_id=submission_id, chunks=chunks,
            )
        except ModelUnavailableError as exc:
            logger.warning("generate_embeddings: model unavailable for submission %s (%s) — skipping", submission_id, exc)
            return
        await db.commit()

    await ctx["redis"].enqueue_job("update_hackathon_stats", str(embedding_context.repo_context.hackathon_id))
    logger.info("generate_embeddings: stored %d chunks for submission %s", count, submission_id)
