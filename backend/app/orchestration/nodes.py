"""Sequential LangGraph node implementations, agent phase (spec Section 7):
build_context -> acquire_model_lock -> repo_understanding -> code_quality ->
innovation -> release_model_lock. Finalization-phase nodes (aggregate,
report, comparative, save, cleanup) live in finalize_nodes.py.

Every node returns normally (never raises) so a plain sequential edge chain
is sufficient — no LangGraph conditional routing needed; resilience is
guaranteed by construction at each node rather than by graph branching.

Non-serializable shared dependencies (DB session, Redis, LLMProvider, model
queue, loaded criteria) live on PipelineContext, captured via closure in
graph.py — NOT stuffed into EvaluationState, which stays close to the
spec's literal TypedDict field list.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult
from app.agents.code_quality import CodeQualityAgent
from app.agents.innovation import InnovationAgent
from app.agents.llm_provider import LLMProvider
from app.agents.repo_understanding import RepoUnderstandingAgent
from app.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.core.model_queue import ModelQueueManager
from app.models.criterion import Criterion
from app.models.submission import Submission, SubmissionStatus
from app.orchestration.state import EvaluationState
from app.pipeline.analysis_cache import load_cached_analysis_result
from app.pipeline.context_builder import build_repo_context
from app.pipeline.file_processor import analyze_project
from app.pipeline.ingestion import workspace_path
from app.pipeline.progress import emit_progress
from app.pipeline.static_analysis import run_static_analysis

logger = logging.getLogger("evalon.orchestration")

_LLM_AGENT_IDS = ("repo_understanding", "code_quality", "innovation")
_STAGE_PROGRESS = {
    "agent_repo_understanding": 72,
    "agent_code_quality": 78,
    "agent_innovation": 84,
}


@dataclass
class PipelineContext:
    db: AsyncSession
    redis: Redis
    model_queue: ModelQueueManager
    llm: LLMProvider
    settings: Settings
    criteria: list[Criterion]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock_cm: object | None = None  # set by acquire_model_lock_node, cleared by release_model_lock_node


async def build_context_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    submission_id = state["submission_id"]
    submission = await ctx.db.get(Submission, uuid.UUID(submission_id))
    if submission is None:
        raise RuntimeError(f"Submission {submission_id} not found")

    repo_path = workspace_path(ctx.settings.workspace_dir, submission_id)
    project = analyze_project(repo_path)  # cheap (file tree only) — safe to always recompute

    cached = await load_cached_analysis_result(ctx.redis, submission_id)
    if cached is not None:
        static_report = cached.static_analysis
    else:
        logger.warning("Analysis cache miss for %s — recomputing static analysis", submission_id)
        static_report = await run_static_analysis(repo_path, project.files)

    state["repo_context"] = build_repo_context(
        submission_id=submission_id,
        hackathon_id=state["hackathon_id"],
        repo_url=submission.repo_url,
        repo_name=submission.repo_name or "unknown",
        repo_description=submission.repo_description,
        project=project,
        static_analysis=static_report,
    )

    submission.status = SubmissionStatus.EVALUATING
    await ctx.db.commit()
    await emit_progress(
        ctx.redis, submission_id, "progress",
        {"stage": "analyzing", "message": "Preparing evaluation context...", "progress_pct": 66, "degraded": False},
    )
    return state


async def acquire_model_lock_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    """If another evaluation currently holds the lock, this can block for a
    while inside cm.__aenter__() — emit a distinct "you're queued behind
    another evaluation" message first (spec Section 20's demo flow: "AI is
    finishing another evaluation. You're next in queue...") so a queued
    participant doesn't just see a stuck "Loading AI models..." spinner for
    the whole wait."""
    submission_id = state["submission_id"]
    if await ctx.redis.get(ctx.model_queue.LOCK_KEY) is not None:
        await emit_progress(
            ctx.redis, submission_id, "progress",
            {
                "stage": "model_waiting",
                "message": "AI is finishing another evaluation. You're next in queue...",
                "progress_pct": 67,
                "degraded": False,
            },
        )
    await emit_progress(
        ctx.redis, submission_id, "progress",
        {"stage": "model_loading", "message": "Loading AI models...", "progress_pct": 68, "degraded": False},
    )

    cm = ctx.model_queue.acquire_inference_lock(f"eval:{submission_id}", priority=0, timeout=300)
    try:
        await cm.__aenter__()
    except ModelUnavailableError as exc:
        logger.warning("Model lock unavailable for %s: %s", submission_id, exc)
        state["model_lock_acquired"] = False
        reason = f"Model temporarily unavailable due to resource contention. Score computed from static analysis only. ({exc.message})"
        for agent_id in _LLM_AGENT_IDS:
            state["agent_results"][agent_id] = AgentResult.create_abstained(agent_id, reason, fallback_used=True)
        await emit_progress(
            ctx.redis, submission_id, "progress",
            {
                "stage": "model_waiting",
                "message": "AI model busy with another evaluation. Using static analysis only.",
                "progress_pct": 70,
                "degraded": True,
            },
        )
        await emit_progress(
            ctx.redis, submission_id, "degraded",
            {"message": "AI evaluation unavailable — using static analysis only.", "affected_agents": list(_LLM_AGENT_IDS)},
        )
        return state

    ctx.lock_cm = cm
    state["model_lock_acquired"] = True
    await emit_progress(
        ctx.redis, submission_id, "progress",
        {"stage": "model_loading", "message": "AI models ready.", "progress_pct": 70, "degraded": False},
    )
    return state


async def _run_agent_node(state: EvaluationState, ctx: PipelineContext, agent, stage_name: str, **extra_kwargs) -> EvaluationState:
    """Shared resilience wrapper for all three LLM agent nodes (spec Section
    7's agent_node pattern). If the model lock wasn't acquired, the agent's
    result was already populated by acquire_model_lock_node — nothing to do."""
    submission_id = state["submission_id"]
    if not state["model_lock_acquired"]:
        return state

    await emit_progress(
        ctx.redis, submission_id, "progress",
        {"stage": stage_name, "message": f"{agent.agent_name} running...", "progress_pct": _STAGE_PROGRESS[stage_name], "degraded": False},
    )
    try:
        result = await agent.safe_evaluate(state["repo_context"], **extra_kwargs)
        state["agent_results"][agent.agent_id] = result
        state["completed_agents"].append(agent.agent_id)
        await emit_progress(
            ctx.redis, submission_id, "agent_complete",
            {"agent_id": agent.agent_id, "score": result.score_raw, "abstained": result.abstained},
        )
    except ModelUnavailableError as exc:
        state["agent_results"][agent.agent_id] = AgentResult.create_abstained(
            agent.agent_id, f"Model unavailable: {exc.message}. Score from static analysis only.", fallback_used=True
        )
        await emit_progress(
            ctx.redis, submission_id, "degraded",
            {"message": f"{agent.agent_name} used fallback scoring.", "affected_agents": [agent.agent_id]},
        )
    except asyncio.TimeoutError:
        state["agent_results"][agent.agent_id] = AgentResult.create_abstained(
            agent.agent_id, "Agent timed out after 90 seconds. Score from static analysis only.", fallback_used=True
        )
        await emit_progress(
            ctx.redis, submission_id, "degraded",
            {"message": f"{agent.agent_name} timed out.", "affected_agents": [agent.agent_id]},
        )
    except Exception as exc:  # noqa: BLE001 - NO exception may ever propagate out of an agent node (spec Section 7)
        logger.error("Agent %s failed: %s", agent.agent_id, exc, exc_info=True)
        state["agent_results"][agent.agent_id] = AgentResult.create_abstained(
            agent.agent_id, "Evaluation agent encountered an error. Score from static analysis only.", fallback_used=True
        )
        state["errors"].append(str(exc))
        await emit_progress(
            ctx.redis, submission_id, "degraded",
            {"message": f"{agent.agent_name} encountered an error.", "affected_agents": [agent.agent_id]},
        )
    return state


async def repo_understanding_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    return await _run_agent_node(state, ctx, RepoUnderstandingAgent(ctx.llm), "agent_repo_understanding")


async def code_quality_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    return await _run_agent_node(state, ctx, CodeQualityAgent(ctx.llm), "agent_code_quality")


async def innovation_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    understanding = state["agent_results"].get("repo_understanding")
    return await _run_agent_node(
        state, ctx, InnovationAgent(ctx.llm), "agent_innovation", understanding=understanding
    )


async def release_model_lock_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    """Always runs (every prior node returns normally by construction — see
    module docstring) even when the lock was never acquired."""
    if state["model_lock_acquired"] and ctx.lock_cm is not None:
        await ctx.lock_cm.__aexit__(None, None, None)
        ctx.lock_cm = None
    await emit_progress(
        ctx.redis, state["submission_id"], "progress",
        {
            "stage": "aggregating",
            "message": "AI evaluation complete. Aggregating scores...",
            "progress_pct": 86,
            "degraded": not state["model_lock_acquired"],
        },
    )
    return state
