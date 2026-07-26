# ADR-004: Queue System (ARQ + Redis)

**Status**: Accepted

## Context

Repository cloning, static analysis, and the LLM-backed evaluation
pipeline all take seconds to minutes — far too long to run inside an HTTP
request/response cycle. EVALON needs a background job system that: runs
jobs as native coroutines (so an `await`-ing Ollama call doesn't tie up a
worker thread), shares its broker with infrastructure the system already
requires (the model lock and SSE pub/sub both run on Redis), and keeps
operational complexity proportional to EVALON's actual job count (five
job types: `ingest_repository`, `run_evaluation_pipeline`,
`generate_embeddings`, `recompute_rankings`, `update_hackathon_stats`).

Alternatives considered: Celery (Python's default choice, broker-flexible,
sync-core with async support bolted on); RQ (simple, Redis-backed, but
synchronous only).

## Decision

ARQ. Jobs are plain `async def` functions (`app/jobs/tasks.py`),
registered on a `WorkerSettings.functions` list (`app/jobs/worker.py`),
dispatched via `pool.enqueue_job(...)` from API request handlers. Worker
concurrency is capped at `max_jobs = 3` — deliberately low, since only one
of those three slots can ever be doing LLM work at a time regardless (the
other two handle cloning/static-analysis/DB-write work that doesn't touch
Ollama).

## Consequences

**Gains:**
- A job can `await` an Ollama HTTP call for 10–30 seconds without
  blocking the worker process from picking up other (non-LLM) jobs — no
  `gevent`/`eventlet` monkey-patching required, unlike getting the same
  behavior out of Celery.
- One broker (Redis) for the job queue, the model lock, and the SSE
  pub/sub — one dependency to run, monitor, and reason about instead of
  three.
- ARQ's own periodic health-check string (written to a well-known Redis
  key) is parsed directly for the admin queue-status endpoint
  (`GET /admin/queue/status`) rather than reimplementing job-count
  bookkeeping — see `app/api/v1/admin.py`.

**Costs:**
- ARQ's ecosystem and tooling are thinner than Celery's — no Flower-style
  monitoring dashboard out of the box, no complex routing/priority-queue
  features (not needed here — job priority isn't a concept EVALON's job
  queue needs; the *model lock's* priority system in `ModelQueueManager`
  is a separate, purpose-built mechanism, not delegated to the job queue).
- `max_jobs = 3` intentionally limits throughput — this is a deliberate
  trade for hardware safety, not an oversight (see ADR-006): more worker
  slots wouldn't let more evaluations progress faster anyway, since
  they'd all funnel through the same single-model-at-a-time lock the
  moment they need Ollama.
