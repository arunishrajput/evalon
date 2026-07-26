# Phase 4 Report — AI Evaluation Agents + Sequential LangGraph

## What was built

- `backend/app/agents/llm_provider.py` — `LLMProvider`. Assumes the model
  lock is already held (never acquires it itself); wraps `/api/generate` with
  `asyncio.wait_for` so a hard timeout raises `asyncio.TimeoutError` distinctly
  from `ModelUnavailableError` (any other failure), matching the spec's exact
  two-exception contract.
- `backend/app/agents/base.py` — `AgentResult`, `EvidenceItem`,
  `BaseEvaluator`. **Deviation from spec's literal pseudocode**: the spec
  names the "abstained" classmethod the same as the `abstained: bool` field,
  which is a genuine Python collision — the classmethod would overwrite the
  field's default in the class namespace and break Pydantic's model
  construction. Renamed to `AgentResult.create_abstained(...)`, documented
  inline and covered by a regression test.
- `backend/app/agents/prompts/*.j2` + `prompt_loader.py` — Jinja2 templates
  for all three LLM agents, each with a strict JSON schema, an
  anti-hallucination instruction, and a worked few-shot example;
  Innovation's additionally includes the spec's calibration anchor.
- `backend/app/agents/{repo_understanding,code_quality,innovation}.py` — the
  three LLM agents. **Key architectural decision**: Code Quality's
  `score_raw` is *always* computed deterministically
  (`app.scoring.aggregator.compute_code_quality_score`, the exact
  spec-mandated weighted formula: complexity 30%/modularity 25%/docs
  20%/error-handling 15%/anti-pattern 10%) — never from the LLM. The LLM's
  only job is narrative interpretation of those same metrics. This is the
  most literal possible reading of P1 ("scores come from structured tool
  output, never a raw LLM number") combined with Section 8 Agent 2's
  explicit formula. Repo Understanding and Innovation have no equivalent
  deterministic tool (no formula measures "clarity of vision" or
  "originality"), so their `score_raw` is LLM-produced exactly as spec
  describes for those two agents, grounded via schema + anti-hallucination +
  few-shot + (Innovation only) a calibration anchor.
- `backend/app/agents/comparative.py` — `ComparativeAgent`, pure DB queries
  and arithmetic (no LLM), implementing the spec's Section 8 pseudocode for
  real: percentile/rank/tech-stack comparison/template summary. Pool
  per-criterion averages are read from OTHER submissions' already-stored
  `Evaluation.report` JSONB rather than re-aggregating from scratch, so every
  participant's comparison uses the same "effective" fallback-aware scores
  they'd see on their own report.
- `backend/app/scoring/aggregator.py` — `aggregate_scores` (Stage 5): weighted
  final score, per-criterion effective-score fallback (code_quality
  recomputes deterministically on abstain/fallback; the other two use the
  neutral default), and the `completed`/`degraded`/`failed` status logic.
- `backend/app/scoring/report_generator.py` — `generate_report` (Stage 6):
  assembles the full JSON report matching Section 6's schema exactly.
- `backend/app/orchestration/{state,nodes,finalize_nodes,graph}.py` — the
  sequential LangGraph pipeline, split into two node files to stay under the
  300-line file standard (agent phase vs. finalization phase). Every node
  returns normally by construction (agent failures are caught *inside* the
  node, not by graph branching), so a plain sequential edge chain is
  sufficient — matches spec's explicit "STRICTLY SEQUENTIAL" edge list with
  no LangGraph conditional routing needed anywhere.
- `backend/app/jobs/tasks.py::run_evaluation_pipeline` — the ARQ job wiring
  the graph to a submission; `ingest_repository` now chains into it via
  `ctx["redis"].enqueue_job(...)` on success (spec Section 11's job
  dependency: `ingest_repository → run_evaluation_pipeline`).
- `backend/app/api/v1/evaluations.py` — `GET /evaluations/{id}`,
  `GET /evaluations/{id}/agents`, `POST /evaluations/{id}/retry`.

## Scope note: aggregator.py and report_generator.py pulled forward from Phase 5

The original plan put `aggregator.py`/`report_generator.py` in Phase 5, but
spec Section 7's graph node list places `aggregate_node`/`generate_report_node`
*inside the same sequential graph* as the three agents (nodes 7–8 of 11) —
the graph cannot run end-to-end without them. Built them now so Phase 4
delivers a genuinely complete, working pipeline rather than a half-graph.
Phase 5 is now scoped to `normalizer.py` (cross-submission percentile
ranking), the ranking/`hackathon_stats` system, dashboard SSE, comparison
API, and PDF export — everything Section 5's `aggregate_scores`/
`generate_report` don't already cover.

## Live end-to-end verification (real Ollama, not mocked)

Ran the full pipeline against `octocat/Hello-World` end-to-end: SSE showed
cloning → analyzing → model_loading → all three agents → aggregating →
generating_report → comparative → completed, with a real evaluation
persisted (`final_score=46.15`, evidence-grounded reasoning like *"The README
file is entirely empty..."* for the low Understanding score, exactly matching
the actual repo content).

**Sequential-execution proof** (spec Phase 4 gate — "verify via log
timestamps, no overlap"): repo_understanding 26.493→33.357, code_quality
33.363→40.643, innovation 40.645→49.213 — strictly non-overlapping.

**Cross-submission serialization proof** (the harder, more important
guarantee — spec Section 20's actual demo scenario): submitted two
evaluations seconds apart. The second submission's SSE showed the new
`model_waiting` "AI is finishing another evaluation. You're next in
queue..." message (added during this phase — see below), blocked until
Submission 1 released the lock, then ran its own three agents. Timestamps
confirm Submission 1's agents (22.629→38.421) and Submission 2's agents
(38.956→58.585) never overlapped — the model lock correctly serializes
*across* submissions, not just within one.

**Deterministic formula verified against live data**: for the empty
Hello-World repo (no Python files, no README, zero findings),
`compute_code_quality_score` returns exactly 63.5, matching a hand
computation of the weighted formula — and a unit test now pins this exact
value as a regression check.

## Bug found and fixed during test-writing

`aggregate_scores` only flagged `any_fallback` (→ `degraded` status) when an
`AgentResult` object existed with `abstained`/`fallback_used` set — a
criterion whose mapped agent *never even ran* (missing from
`agent_results` entirely, e.g. a genuine orchestration bug) fell through
unflagged, silently returning `status='completed'` with a neutral score
baked into the average. Caught by
`test_aggregate_scores_missing_agent_result_treated_as_abstained`. Fixed:
`agent_result is None` now counts the same as abstained for degradation
purposes.

## UX gap found and fixed during live verification

Re-reading spec Section 20's demo flow while testing concurrency exposed a
real gap: a participant queued behind another active evaluation only saw a
generic "Loading AI models..." message for the entire wait — there was no
distinct "you're queued" state, unlike spec's demo script which shows "AI is
finishing another evaluation. You're next in queue...". Fixed in
`acquire_model_lock_node`: checks whether the lock is currently held
*before* blocking on acquisition and emits the distinct `model_waiting`
message if so. Verified live in the concurrency test above.

## Testing results

**84/84 tests pass** (61 new this phase + 23 from prior phases, no
regressions): agent JSON-parsing/clamping (`test_agents/`), the deterministic
formula and every degradation transition (`test_scoring/test_aggregator.py`),
the Comparative Agent's percentile/rank/tech-stack/summary logic against a
**real Postgres DB** (`test_scoring/test_comparative.py`), and the node-level
resilience patterns — model-unavailable, timeout, generic exception, lock
acquired but agent skipped, lock-timeout populating all three agents as
abstained (`test_orchestration/test_resilience.py`) — satisfying spec Section
13's explicit "UNIT TESTS — Graceful Degradation" and "UNIT TESTS —
Comparative Agent" lists.

## Known issues / technical debt

- None introduced knowingly. The one real gap found (queue-visibility
  messaging) was fixed and verified live within this phase, not deferred.

## What's next

Phase 5 — Scoring + Ranking (narrowed per the scope note above):
`normalizer.py` for cross-submission percentile ranking, the
`rankings`/`hackathon_stats` system with finalization gating, the dashboard
API + SSE stream, the side-by-side comparison API, and the weasyprint PDF
export endpoint.
