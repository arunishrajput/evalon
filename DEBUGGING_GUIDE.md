# EVALON — Debugging Guide

## Common failure modes and where to look

| Symptom | Where to look | What you'll find |
|---|---|---|
| Submission stuck on "cloning" | `docker compose logs worker` | `RepositoryIngestionError` — invalid URL, private repo, repo exceeds `MAX_REPO_SIZE_MB`/`MAX_FILE_COUNT`, or clone timeout |
| Submission stuck on "analyzing" | `docker compose logs worker` | A static analysis tool errored — check for `StaticAnalysisError`; the pipeline continues with `degraded=true` rather than actually stalling, so a genuine stall here is more likely `docker compose ps` showing the worker container itself unhealthy |
| Evaluation never leaves `model_loading` | `make model-status` | Check `lock_held_by` and `queue_depth` — if another evaluation genuinely holds the lock, this is expected (spec's designed queuing behavior, not a bug); if `lock_held_by` is stuck non-null with nothing actually running, see "force-release a stuck lock" below |
| Frontend shows a generic error but the backend looks fine | Browser devtools → Network tab | Check the actual HTTP status/body — every EVALON error response is `{"detail": "...", "error_code": "..."}`; also check `NEXT_PUBLIC_API_URL` ends in `/api/v1` (a real bug found during Phase 7's live testing — easy to reintroduce by hand-editing `.env`) |
| Mentor chat returns 202 immediately | Expected under load | Spec's designed behavior when the P3 chat request can't acquire the inference lock within 30s — the frontend should retry after `retry_after` seconds, not treat this as a failure |
| Mentor chat says "being prepared" | `docker compose logs worker \| grep generate_embeddings` | Embeddings haven't finished generating yet (runs as a background job right after evaluation completes, ~20-40s) — check the job actually ran, not just that time has passed |

## Inspecting ARQ job status

```bash
# Live worker logs — every job logs its start, duration, and result
docker compose logs -f worker

# Admin API view of ARQ's own health-check counters
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/api/v1/admin/queue/status
# {"reachable": true, "jobs_complete": 42, "jobs_failed": 0, "jobs_retried": 0,
#  "jobs_ongoing": 1, "jobs_queued": 0, "raw_health_check": "..."}

# Raw Redis view of ARQ's queue depth
docker compose exec redis redis-cli LLEN arq:queue
```

A job's `max_tries = 3` (set in `app/jobs/worker.py`'s `WorkerSettings`) —
if you see the same job ID appear 3 times in the logs before finally
being marked failed, that's ARQ's own retry behavior working correctly,
not a symptom of something else being wrong.

## Reading evaluation pipeline logs

Every stage of `run_evaluation_pipeline` logs to the `evalon.orchestration`
logger with the submission ID, so you can grep a single evaluation's full
timeline out of a busy worker log:

```bash
docker compose logs worker | grep "<submission-id>"
```

To verify agents actually ran **strictly sequentially** (the spec's core
constraint, not just an implementation detail) — check that each agent's
start timestamp is at or after the previous agent's completion timestamp,
never overlapping:

```bash
docker compose logs worker | grep -E "agent_(repo_understanding|code_quality|innovation)" 
```

The SSE progress stream itself is also a complete, replayable log — every
event is `RPUSH`'d to a Redis list with a 2-hour TTL before being
published, so you can read a submission's full event history directly:

```bash
docker compose exec redis redis-cli LRANGE "evalon:progress:<submission-id>" 0 -1
```

## Testing a single agent in isolation

Agents are plain classes taking an `LLMProvider` and a `RepoContext` — no
need to run the full pipeline to test one:

```python
# From backend/, with the venv/container's Python
import asyncio
from app.agents.code_quality import CodeQualityAgent
from app.agents.llm_provider import LLMProvider
from app.config import get_settings
from tests.test_agents.conftest import repo_context  # or build your own RepoContext

async def main():
    llm = LLMProvider(get_settings())
    agent = CodeQualityAgent(llm)
    result = await agent.safe_evaluate(repo_context())
    print(result.model_dump_json(indent=2))

asyncio.run(main())
```

Note `safe_evaluate` (not `evaluate`) — this is the resilience-wrapped
entry point every pipeline node actually calls; calling `evaluate`
directly bypasses the timeout/malformed-JSON/model-unavailable handling
and will raise on the failure modes the pipeline is specifically built to
absorb.

For fully offline testing with no real Ollama call, see the `FakeLLM`
stub in `tests/test_agents/conftest.py` — every agent test in the suite
uses it rather than hitting real Ollama, so agent *logic* (prompt
construction, response parsing, score computation) is fast and
deterministic to test; only the live-verification passes documented in
`docs/reports/PHASE-4-REPORT.md` onward exercise real Ollama.

## Adding a new evaluator agent

1. Create `app/agents/your_agent.py`, subclassing `BaseEvaluator`
   (`app/agents/base.py`) — implement `evaluate(repo_context, **kwargs) ->
   AgentResult`, following an existing agent (`code_quality.py` is the
   most representative example) for the evidence-grounding pattern:
   every score needs `evidence` items that trace back to something in
   `repo_context.static_analysis` or the code samples, not a bare LLM
   claim.
2. Add a Jinja2 prompt template under `app/agents/prompts/your_agent.j2`,
   following the existing templates' structure — the static analysis
   findings relevant to this agent go in the prompt explicitly, not left
   for the model to infer from raw source alone.
3. Register it in `app/agents/registry.py`'s `AGENT_REGISTRY` dict.
4. Add a node function in `app/orchestration/nodes.py` following
   `_run_agent_node`'s wrapper pattern, and wire it into the graph's edge
   chain in `app/orchestration/graph.py` — sequentially, never in
   parallel with another LLM-calling node.
5. Add the new `agent_id` as a valid `Criterion.agent_id` value so admins
   can map a judging criterion to it via the criteria builder.
6. Write tests following `tests/test_agents/test_code_quality.py`'s
   pattern: `FakeLLM` for logic tests, no real Ollama calls needed.

## Verifying Ollama is running correctly

```bash
# From the host — is Ollama itself up, and are the two required models pulled?
ollama list
# NAME                       ID              SIZE      MODIFIED
# qwen2.5-coder:7b           ...             4.7 GB    ...
# nomic-embed-text           ...             274 MB    ...

# From inside a container — is Ollama actually reachable at OLLAMA_BASE_URL?
docker compose exec backend curl -s http://host.docker.internal:11434/api/version

# What's currently loaded into memory?
curl -s http://host.docker.internal:11434/api/ps

# EVALON's own aggregated view (never triggers a load as a side effect of checking)
curl http://localhost:8000/api/v1/admin/model/status
```

If `ollama list` shows the models but `/api/version` isn't reachable from
inside a container, Ollama likely isn't listening on all interfaces —
check `OLLAMA_HOST` in your Ollama service config, or (on Linux, where
`host.docker.internal` doesn't resolve by default) confirm the
`extra_hosts` entry in `docker-compose.yml` is actually taking effect.

## How to check which model is currently loaded

```bash
make model-status
```

This is `GET /api/v1/admin/model/status` — see the exact response shape
documented in `SETUP.md`. `inference_model_loaded` / `embedding_model_loaded`
tell you directly; only one can ever be `true` at a time (`ModelQueueManager`'s
core invariant — see ADR-006).

## How to manually unload a model

Ollama's own API, called directly (bypassing `ModelQueueManager` — only
do this when nothing is actively evaluating, since it can race a legit
in-progress request):

```bash
curl http://host.docker.internal:11434/api/generate -d '{
  "model": "qwen2.5-coder:7b",
  "keep_alive": 0
}'
```

`keep_alive: 0` unloads immediately rather than waiting out the normal
10-minute idle timeout. Confirm it worked via `curl .../api/ps` — the
model should no longer appear in the response.

## Diagnosing OOM

```bash
# Container-level memory usage — is Ollama (running natively, so NOT in this
# list) or a Docker service the one climbing?
docker stats

# Ollama's own logs, if OOM is actually happening inside Ollama itself
# (macOS: wherever your Ollama install logs; check `ollama serve`'s own
# terminal output if you started it manually)
```

The Docker Compose `ollama` service (used only in the Linux/NVIDIA
containerized-Ollama profile, not the default macOS native-host setup)
has a hard `mem_limit: 8g` / `memswap_limit: 8g` (no swap) specifically so
an OOM there kills the Ollama *container* cleanly rather than swap-thrashing
the whole host — if you see this happening, it's the cap doing its job,
not a bug; the fix is a machine with more memory or the CPU-only smaller
model swap documented in `SETUP.md`, not raising the limit past what the
host actually has.

## What "degraded evaluation" means and how to recover

`evaluation.status == "degraded"` means: a real, non-null `final_score`
was computed, but at least one LLM agent couldn't run (model unavailable,
timeout, or malformed output) and fell back to a static-analysis-only
formula for its criterion instead. This is **not a failure** — it's the
system doing exactly what ADR-005 requires: a score always has *some*
grounded provenance, just potentially less nuanced than a full AI pass.

`submission.degraded_reason` (and, for degraded evaluations specifically,
`evaluation.report.degraded_explanation`) carries the human-readable why.

**To recover a genuinely bad degraded result** (e.g., the model was
unavailable due to a transient Ollama restart, not sustained load):

```bash
curl -X POST http://localhost:8000/api/v1/evaluations/{submission_id}/retry \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Admin-only, and only valid when `submission.status == "failed"` — a
*degraded-but-completed* evaluation isn't retryable via this endpoint by
design (it already produced a valid score; re-running it would just spend
another full evaluation cycle for a result that might not even change).
If you specifically want a degraded evaluation re-run, that's a manual
DB-level status reset to `pending` followed by re-dispatching
`ingest_repository` — deliberately not a one-click UI action, since
silently re-scoring already-shown results has fairness implications for
other participants.

## How to force-release a stuck model lock

Should essentially never be necessary — the lock carries a 600-second TTL
(`MODEL_LOCK_TIMEOUT_SECONDS`) specifically so an abruptly-killed holder
(a crashed worker process, a `docker compose restart` mid-request) can't
wedge the system forever; it self-heals within 10 minutes. If you need it
sooner (e.g., mid-demo):

```bash
# Confirm it's actually orphaned first — is anything genuinely running?
curl http://localhost:8000/api/v1/admin/model/status
# check lock_held_by against docker compose logs worker for a matching in-flight job

# If genuinely orphaned, delete the lock key directly
docker compose exec redis redis-cli DEL evalon:model:lock
docker compose exec redis redis-cli DEL evalon:model:queue
```

Deleting `evalon:model:queue` too clears any waiters that piled up behind
the stuck lock, so they don't immediately re-contend for a lock that's
about to be re-acquired by whichever request happens to poll first.

## Database debugging queries

```sql
-- Live pipeline state across all submissions
SELECT id, repo_url, status, degraded, submitted_at
FROM submissions ORDER BY submitted_at DESC LIMIT 20;

-- A specific evaluation's full report (pretty-printed)
SELECT jsonb_pretty(report) FROM evaluations WHERE submission_id = '<uuid>';

-- Which agents abstained, and why, across the whole hackathon
SELECT s.repo_name, ar.agent_id, ar.abstain_reason
FROM agent_results ar
JOIN evaluations e ON e.id = ar.evaluation_id
JOIN submissions s ON s.id = e.submission_id
WHERE ar.abstained = true AND e.hackathon_id = '<uuid>';

-- Current leaderboard (mirrors what /rankings/{id} returns)
SELECT r.rank, r.percentile, s.repo_name, e.final_score
FROM rankings r
JOIN submissions s ON s.id = r.submission_id
JOIN evaluations e ON e.submission_id = s.id
WHERE r.hackathon_id = '<uuid>'
ORDER BY r.rank;

-- Has a hackathon actually been finalized? (rankings immutability check)
SELECT DISTINCT finalized FROM rankings WHERE hackathon_id = '<uuid>';

-- How many chunks does a submission have for the mentor's RAG context?
SELECT chunk_type, count(*) FROM repo_embeddings
WHERE submission_id = '<uuid>' GROUP BY chunk_type;
```
