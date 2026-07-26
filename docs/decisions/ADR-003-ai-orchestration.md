# ADR-003: AI Orchestration Approach (LangGraph)

**Status**: Accepted

## Context

EVALON's evaluation pipeline runs three independent LLM-backed agents
(Repository Understanding, Code Quality, Innovation) plus a non-LLM
comparative analytics step, in a fixed, strictly sequential order, each
grounded in the same static-analysis context — never as a conversation
and never in parallel (the latter is a hard hardware constraint; see
ADR-006). Every node needs the same resilience shape: catch its own
failures, degrade to a fallback, and never let a bug propagate out of the
node and crash the whole pipeline.

Alternatives considered: CrewAI (an agent-collaboration framework built
around delegation and conversation between agents); a hand-rolled
sequence of plain async function calls with no shared framework.

## Decision

LangGraph, with a plain sequential edge chain (`app/orchestration/graph.py`)
— no conditional routing between nodes. Shared state
(`EvaluationState`, a `TypedDict`) is passed node-to-node explicitly;
non-serializable shared dependencies (the DB session, Redis client,
`LLMProvider`, the loaded criteria) live on a separate `PipelineContext`
dataclass captured via closure, kept out of the state dict so it stays
close to the spec's literal field list.

## Consequences

**Gains:**
- The graph's node names and order map almost one-to-one onto the SSE
  progress stages the frontend shows (`agent_repo_understanding`,
  `agent_code_quality`, `agent_innovation`, `agent_comparative`,
  `generating_report`) — the orchestration structure *is* the
  observability structure.
- Every node follows the same resilience pattern (`_run_agent_node` in
  `nodes.py`): catch `ModelUnavailableError`, `asyncio.TimeoutError`, and
  any other exception, and in every case populate an abstained
  `AgentResult` rather than letting the exception propagate. Because
  every prior node is guaranteed to return normally by construction, a
  plain sequential chain is sufficient — no conditional graph routing
  needed to handle failure paths.
- Sequential-by-construction: there is no code path where two agent
  nodes could execute concurrently, which is exactly the guarantee
  `ModelQueueManager`'s single-lock design depends on upstream of it.

**Costs:**
- LangGraph is overkill for a pipeline this simple in one sense — a
  five-line `for` loop would execute the same three agents in the same
  order. The value isn't runtime behavior, it's the state-passing and
  node-composition conventions being explicit and consistent, which pays
  off as the pipeline grows (Phase 5 added `aggregate`, `generate_report`,
  `comparative`, `save_results`, `cleanup` nodes onto the same graph
  without changing the agent-phase nodes at all).
- CrewAI's agent-to-agent delegation abstraction was explicitly rejected,
  not just unused — the spec requires the opposite of what CrewAI is
  built for (agents that never talk to each other, whose outputs are
  combined by a deterministic weighted sum, not synthesized by another
  LLM call).
