# Phase 0 Report — Model Queue Infrastructure

## What was built

- `backend/app/core/model_queue.py` — `ModelQueueManager`: a Redis-backed
  distributed lock (`evalon:model:lock`, SET NX PX with a 600s safety TTL) with
  a priority-ordered waiting queue (`evalon:model:queue`, a Redis sorted set
  keyed by `priority × 10¹³ + arrival_ms` so priority strictly beats arrival
  order). `acquire_inference_lock` / `acquire_embedding_lock` are async context
  managers; acquiring either always unloads whatever else is resident before
  loading the target model, via Ollama's `keep_alive` parameter on `/api/generate`
  (inference) or `/api/embed` (embedding).
- `backend/app/core/exceptions.py` — `EvalonError` hierarchy
  (`ModelUnavailableError`, `ModelLockTimeoutError`, plus two forward-declared
  for later phases) and `register_exception_handlers`, which guarantees every
  API error — including genuinely unhandled ones — comes back as
  `{ "detail": str, "error_code": str }`, never a raw stack trace.
- `backend/app/config.py` — Pydantic Settings (env-driven, no hardcoded config).
- `backend/app/dependencies.py`, `app/core/middleware.py`, `app/main.py` — the
  minimum FastAPI scaffold needed to expose real endpoints this phase.
- `GET /api/v1/admin/model/status` and `GET /api/v1/health` — both implemented
  for real (not stubbed) and independently try/excepted per dependency, so a
  down Redis or unreachable Ollama degrades the response instead of 500ing.
- `tests/test_core/test_model_queue.py` — 7 tests against a **real** Redis
  instance (mocking Redis would defeat the point of Phase 0 — proving the
  distributed lock actually serializes) with Ollama HTTP calls monkeypatched
  per spec's testing guidance.
- `docs/decisions/ADR-006-model-resource-management.md`.

## Verification gate results (Section 16, Phase 0)

All items verified for real, not assumed:

| Check | Result |
|---|---|
| Ollama `/api/version` responds | ✅ native host Ollama, `{"version":"0.30.10"}` |
| Acquire/release inference lock | ✅ unit test + live run against real Ollama (see below) |
| Acquire/release embedding lock | ✅ unit test + live run against real Ollama |
| Lock held → second acquirer blocks, then succeeds after release | ✅ `test_second_requester_blocks_until_release` |
| Priority ordering (P0 before P2 before P3, regardless of arrival order) | ✅ `test_priority_ordering_p0_before_p2_before_p3` |
| Lock timeout → `ModelLockTimeoutError`, not a crash, queue cleaned up | ✅ `test_lock_timeout_raises_and_cleans_up_queue` |
| `GET /api/v1/admin/model/status` returns valid response | ✅ live: see below |

Live end-to-end run (real Redis + real native Ollama, not mocked) — confirms the
whole stack, not just unit-tested logic:

```
before:           inference_loaded=False embedding_loaded=False lock_held_by=None
during inference: inference_loaded=True  embedding_loaded=False lock_held_by=manual-verify
after release:     inference_loaded=True  embedding_loaded=False lock_held_by=None
during embedding: inference_loaded=False embedding_loaded=True  lock_held_by=manual-verify-embed
```

This proves the "never two models loaded at once" invariant end-to-end: entering
the embedding lock force-unloaded the still-warm inference model before loading
`nomic-embed-text`.

## Architectural decisions

- Priority queue implemented as a Redis sorted set rather than separate Redis
  lists per priority level — a single ZSET with a composite score
  (`priority × 10¹³ + arrival_ms`) gives strict priority ordering with
  FIFO-within-priority using one data structure and one atomic `ZRANGE 0 0`
  head-check, rather than coordinating across four queues.
- Lock release uses a Lua script (`GET` + compare + `DEL`) so a caller can only
  release a lock it actually holds — prevents a timed-out/expired caller from
  releasing a subsequent holder's lock.
- `/admin/hackathons` and `/admin/queue/status` (also listed under "Admin
  Utility Endpoints" in the spec) are intentionally not implemented yet — they
  need the database (Phase 1/2) and ARQ (Phase 3) respectively. This isn't a
  placeholder; the routes simply don't exist until their dependencies do.
- `GET /api/v1/health` currently reports `"database": false` unconditionally —
  honest placeholder value, not a lie, since `app/database.py` doesn't exist
  until Phase 1. Will be wired to a real check next phase.

## Known issues / technical debt

- None introduced. `ModelQueueManager` has no TODOs — every method is a real
  implementation exercised by both the unit tests and the live verification
  runs above.

## Testing results

7/7 `test_model_queue.py` tests pass. Live manual verification (documented
above) confirms behavior holds against the real Ollama runtime, not just
mocks.

## What's next

Phase 1 — Foundation: `database.py` (async SQLAlchemy engine), all ORM models
from Section 5 of the spec, and the Alembic migration (including the pgvector
extension and HNSW index). `GET /api/v1/health`'s database check gets wired up
as part of this phase.
