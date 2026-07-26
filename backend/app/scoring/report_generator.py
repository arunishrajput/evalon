"""Assembles the structured JSON evaluation report (spec Stage 6 / Section 6's
schema). Every number comes from aggregate_scores(); prose is drawn from the
agents' own grounded reasoning text, never freshly generated here."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base import AgentResult
    from app.pipeline.context_builder import RepoContext


def generate_report(
    *,
    repo_context: "RepoContext",
    agent_results: dict[str, "AgentResult"],
    aggregation: dict,
    model_versions: dict,
) -> dict:
    degraded = aggregation["status"] == "degraded"
    understanding = agent_results.get("repo_understanding")
    architecture_pattern = (
        understanding.details.get("architecture_pattern") if understanding and understanding.details else None
    ) or "Not determined"

    return {
        "summary": _build_summary(repo_context, aggregation),
        "degraded": degraded,
        "degraded_explanation": (
            "Some AI agents used fallback scoring. Results are based primarily on static "
            "analysis and may be less nuanced. Full AI evaluation was not possible at this time."
            if degraded
            else None
        ),
        "overall_assessment": _build_overall_assessment(agent_results),
        "tech_stack": repo_context.tech_stack,
        "project_type": repo_context.project_type,
        "scores": {
            "overall": aggregation["final_score"],
            "by_criterion": aggregation["by_criterion"],
        },
        "strengths": _collect(agent_results, "strengths"),
        "weaknesses": _collect(agent_results, "weaknesses"),
        "recommendations": _build_recommendations(agent_results),
        "architecture_notes": architecture_pattern,
        "agent_results": [_agent_result_dict(agent_id, result) for agent_id, result in agent_results.items()],
        "comparative": None,  # filled in by comparative_node, which runs after this node
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_versions": model_versions,
    }


def _agent_result_dict(agent_id: str, result: "AgentResult") -> dict:
    return {
        "agent_id": agent_id,
        "score_raw": result.score_raw,
        "confidence": result.confidence,
        "evidence": [e.model_dump() for e in result.evidence],
        "top_evidence": result.top_evidence,
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "reasoning": result.reasoning,
        "abstained": result.abstained,
        "abstain_reason": result.abstain_reason,
        "fallback_used": result.fallback_used,
    }


def _collect(agent_results: dict[str, "AgentResult"], field: str, limit: int = 6) -> list[str]:
    items: list[str] = []
    for result in agent_results.values():
        items.extend(getattr(result, field))
    seen: set[str] = set()
    deduped = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:limit]


def _build_summary(repo_context: "RepoContext", aggregation: dict) -> str:
    score = aggregation["final_score"]
    tier = "a strong" if score >= 80 else "a solid" if score >= 60 else "an early-stage"
    project_type = (repo_context.project_type or "software").lower()
    return (
        f"{repo_context.repo_name} is {tier} {project_type} project scoring {score:.1f}/100 "
        f"across {len(aggregation['by_criterion'])} judging criteria."
    )


def _build_overall_assessment(agent_results: dict[str, "AgentResult"]) -> str:
    paragraphs = []
    for agent_id in ("repo_understanding", "code_quality", "innovation"):
        result = agent_results.get(agent_id)
        if result and not result.abstained and result.reasoning:
            paragraphs.append(result.reasoning)
    if not paragraphs:
        paragraphs.append(
            "This evaluation relied primarily on static analysis; AI-generated narrative "
            "assessment was not available for this submission."
        )
    return "\n\n".join(paragraphs)


def _build_recommendations(agent_results: dict[str, "AgentResult"]) -> list[dict]:
    recommendations = []
    for agent_id, result in agent_results.items():
        for weakness in result.weaknesses[:2]:
            recommendations.append(
                {
                    "priority": "high" if agent_id == "code_quality" else "medium",
                    "recommendation": f"Address: {weakness}",
                    "rationale": f"Identified by the {agent_id.replace('_', ' ')} evaluation.",
                }
            )
    return recommendations[:8]
