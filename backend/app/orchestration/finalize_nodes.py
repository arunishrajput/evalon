"""Sequential LangGraph node implementations, finalization phase (spec
Section 7): aggregate -> generate_report -> comparative -> save_results ->
cleanup. Agent-phase nodes (build_context through release_model_lock) live
in nodes.py; both share PipelineContext/EvaluationState from there."""

import logging
import uuid
from datetime import datetime, timezone

from app.embedding.context_cache import cache_embedding_context
from app.models.agent_result import AgentResult as AgentResultModel
from app.models.evaluation import Evaluation, EvaluationStatus
from app.models.submission import Submission, SubmissionStatus
from app.orchestration.nodes import PipelineContext
from app.orchestration.state import EvaluationState
from app.pipeline.ingestion import cleanup_workspace
from app.pipeline.progress import emit_progress
from app.scoring.aggregator import aggregate_scores
from app.scoring.report_generator import generate_report

logger = logging.getLogger("evalon.orchestration")

_EVALUATION_STATUS_MAP = {
    "completed": EvaluationStatus.COMPLETED,
    "degraded": EvaluationStatus.DEGRADED,
    "failed": EvaluationStatus.FAILED,
}


async def aggregate_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    state["aggregation"] = aggregate_scores(
        criteria=ctx.criteria,
        agent_results=state["agent_results"],
        static_analysis=state["repo_context"].static_analysis,
    )
    return state


async def generate_report_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    model_versions = {
        "inference_model": ctx.model_queue.INFERENCE_MODEL,
        "embedding_model": ctx.model_queue.EMBEDDING_MODEL,
    }
    state["report"] = generate_report(
        repo_context=state["repo_context"],
        agent_results=state["agent_results"],
        aggregation=state["aggregation"],
        model_versions=model_versions,
    )
    await emit_progress(
        ctx.redis, state["submission_id"], "progress",
        {
            "stage": "generating_report",
            "message": "Generating evaluation report...",
            "progress_pct": 90,
            "degraded": state["aggregation"]["status"] == "degraded",
        },
    )
    return state


async def comparative_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    """Pure analytics, no LLM — must still never crash the pipeline (P3)."""
    from app.agents.comparative import ComparativeAgent  # deferred: avoids a nodes.py <-> comparative import cycle

    submission_id = state["submission_id"]
    try:
        result = await ComparativeAgent().evaluate(
            repo_context=state["repo_context"],
            submission_id=submission_id,
            hackathon_id=state["hackathon_id"],
            db=ctx.db,
            this_score=state["aggregation"]["final_score"],
            this_criterion_scores=state["aggregation"]["by_criterion"],
        )
        state["report"]["comparative"] = result.model_dump()
        await emit_progress(
            ctx.redis, submission_id, "progress",
            {
                "stage": "agent_comparative",
                "message": "Comparative analysis complete.",
                "progress_pct": 93,
                "degraded": state["aggregation"]["status"] == "degraded",
            },
        )
    except Exception as exc:  # noqa: BLE001 - analytics-only agent, but P3 applies to every node
        logger.error("Comparative agent failed for %s: %s", submission_id, exc, exc_info=True)
        state["report"]["comparative"] = None
        state["errors"].append(f"Comparative analysis failed: {exc}")
    return state


async def save_results_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    submission_id = uuid.UUID(state["submission_id"])
    aggregation = state["aggregation"]
    evaluation_status = _EVALUATION_STATUS_MAP[aggregation["status"]]

    evaluation = Evaluation(
        submission_id=submission_id,
        hackathon_id=uuid.UUID(state["hackathon_id"]),
        status=evaluation_status,
        final_score=aggregation["final_score"] if evaluation_status != EvaluationStatus.FAILED else None,
        report=state["report"],
        started_at=ctx.started_at,
        completed_at=datetime.now(timezone.utc),
        model_versions=state["report"]["model_versions"],
        agents_completed=state["completed_agents"],
        agents_abstained=[aid for aid, r in state["agent_results"].items() if r.abstained],
    )
    ctx.db.add(evaluation)
    await ctx.db.flush()

    criteria_by_agent = {c.agent_id: c for c in ctx.criteria if c.agent_id}
    for agent_id, result in state["agent_results"].items():
        criterion = criteria_by_agent.get(agent_id)
        ctx.db.add(
            AgentResultModel(
                evaluation_id=evaluation.id,
                agent_id=agent_id,
                criterion_id=criterion.id if criterion else None,
                score_raw=result.score_raw,
                confidence=result.confidence,
                evidence=[e.model_dump() for e in result.evidence],
                strengths=result.strengths,
                weaknesses=result.weaknesses,
                top_evidence=result.top_evidence,
                reasoning=result.reasoning,
                abstained=result.abstained,
                abstain_reason=result.abstain_reason,
                fallback_used=result.fallback_used,
                model_version=ctx.model_queue.INFERENCE_MODEL,
            )
        )

    submission = await ctx.db.get(Submission, submission_id)
    submission.status = SubmissionStatus.FAILED if evaluation_status == EvaluationStatus.FAILED else SubmissionStatus.COMPLETED
    submission.degraded = evaluation_status == EvaluationStatus.DEGRADED
    submission.degraded_reason = state["report"].get("degraded_explanation")
    submission.evaluation_completed_at = datetime.now(timezone.utc)

    await ctx.db.commit()

    if evaluation_status != EvaluationStatus.FAILED:
        # cleanup_node (next in the graph) deletes the cloned repo from disk;
        # generate_embeddings runs as a separate ARQ job/process afterward and
        # has no access to this run's in-memory RepoContext, so it must be
        # captured here first (see embedding/context_cache.py).
        await cache_embedding_context(ctx.redis, state["submission_id"], state["repo_context"], state["report"])

    if evaluation_status == EvaluationStatus.FAILED:
        await emit_progress(
            ctx.redis, state["submission_id"], "error",
            {"message": "All evaluation agents were unable to produce a result.", "stage": "evaluating", "recoverable": True},
        )
    else:
        await emit_progress(
            ctx.redis, state["submission_id"], "completed",
            {
                "evaluation_id": str(evaluation.id),
                "final_score": aggregation["final_score"],
                "degraded": evaluation_status == EvaluationStatus.DEGRADED,
            },
        )
    return state


async def cleanup_node(state: EvaluationState, ctx: PipelineContext) -> EvaluationState:
    cleanup_workspace(ctx.settings.workspace_dir, state["submission_id"])
    return state
