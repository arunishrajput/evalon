"""LangGraph state for the sequential evaluation pipeline (spec Section 7)."""

from typing import TypedDict

from app.agents.base import AgentResult
from app.pipeline.context_builder import RepoContext


class EvaluationState(TypedDict):
    submission_id: str
    hackathon_id: str
    repo_context: RepoContext | None
    agent_results: dict[str, AgentResult]
    errors: list[str]
    completed_agents: list[str]
    model_lock_acquired: bool
    pipeline_start_time: float
    # Extensions beyond the spec's literal field list: aggregate_node and
    # generate_report_node need somewhere to hand their output to
    # comparative_node/save_results_node without stuffing non-state objects
    # into the shared pipeline context.
    aggregation: dict | None
    report: dict | None
