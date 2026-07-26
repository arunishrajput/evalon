"""Builds the SEQUENTIAL (never parallel) LangGraph evaluation pipeline, per
spec Section 7's exact node order:

START -> build_context -> acquire_model_lock -> repo_understanding ->
code_quality -> innovation -> release_model_lock -> aggregate ->
generate_report -> comparative -> save_results -> cleanup -> END
"""

from functools import partial

from langgraph.graph import END, StateGraph

from app.orchestration.finalize_nodes import (
    aggregate_node,
    cleanup_node,
    comparative_node,
    generate_report_node,
    save_results_node,
)
from app.orchestration.nodes import (
    PipelineContext,
    acquire_model_lock_node,
    build_context_node,
    code_quality_node,
    innovation_node,
    release_model_lock_node,
    repo_understanding_node,
)
from app.orchestration.state import EvaluationState

_NODE_ORDER = [
    ("build_context", build_context_node),
    ("acquire_model_lock", acquire_model_lock_node),
    ("repo_understanding", repo_understanding_node),
    ("code_quality", code_quality_node),
    ("innovation", innovation_node),
    ("release_model_lock", release_model_lock_node),
    ("aggregate", aggregate_node),
    ("generate_report", generate_report_node),
    ("comparative", comparative_node),
    ("save_results", save_results_node),
    ("cleanup", cleanup_node),
]


def build_graph(ctx: PipelineContext):
    graph = StateGraph(EvaluationState)
    for name, node_fn in _NODE_ORDER:
        graph.add_node(name, partial(node_fn, ctx=ctx))

    graph.set_entry_point(_NODE_ORDER[0][0])
    for (current_name, _), (next_name, _) in zip(_NODE_ORDER, _NODE_ORDER[1:]):
        graph.add_edge(current_name, next_name)
    graph.add_edge(_NODE_ORDER[-1][0], END)

    return graph.compile()
