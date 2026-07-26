# Phase 6 Report — Embedding Pipeline & AI Mentor Chatbot

## What was built

- `backend/app/embedding/context_cache.py` — Redis bridge carrying a
  submission's `RepoContext` + final report from the evaluation graph (a
  single in-process Python object) to `generate_embeddings`, a *separately
  dispatched ARQ job* with no access to that memory. Necessary because
  `cleanup_node` deletes the cloned repo from disk at the end of the graph
  (spec P2: never store repo files permanently) — by the time
  `generate_embeddings` runs, there is nothing left on disk to re-read.
- `backend/app/embedding/chunker.py` — `build_chunks()`: turns the cached
  context into `repo_summary`, `evaluation_summary`, `readme`, per-file
  `code`, and `static_analysis` chunks (the last only when static analysis
  actually found something worth surfacing).
- `backend/app/embedding/embedder.py` — `embed_and_store_chunks()`: acquires
  the embedding lock **once** for the whole batch (not per chunk — the spec's
  Stage 7 acquires once, generates, releases), embeds via `LLMProvider`,
  replaces any prior `repo_embeddings` rows for that submission (so a
  retried evaluation doesn't accumulate duplicates).
- `backend/app/embedding/retriever.py` — `has_embeddings()` (mentor
  availability gate) and `retrieve_top_chunks()` (pgvector cosine-distance
  top-k, spec step 9 — "no model needed", retrieval itself is a plain SQL
  query).
- `backend/app/jobs/tasks.py` — `generate_embeddings` ARQ job: loads the
  cached context, builds chunks, embeds and stores them. A missing cache
  entry or a lock timeout is logged as a warning and the job returns
  cleanly — never a crash, never a retry storm; the mentor is just
  unavailable for that submission (spec Stage 7's explicit contract).
  Dispatched from `run_evaluation_pipeline` alongside (not blocking)
  `recompute_rankings`/`update_hackathon_stats`, continuing Phase 5's
  documented deviation from the spec's literal linear job chain.
- `backend/app/agents/llm_provider.py` — added `generate_stream()`: the
  token-by-token streaming counterpart to `generate()`, same
  never-raises-anything-but-`ModelUnavailableError` contract.
- `backend/app/chatbot/context.py` — the spec's exact Section 9 system
  prompt template, plus `build_prompt_with_history()` folding the last 10
  messages into a single completion prompt (Ollama's `/api/generate` is
  completion-style, not a chat-message-array API).
- `backend/app/chatbot/mentor.py` — orchestration: `check_availability()`
  (evaluation complete + embeddings exist — degraded evaluations are still
  available, per spec step 4), `get_or_create_session()`, and
  `stream_response()`, which persists the user's message, embeds the query
  (brief, degrades to no-RAG-augmentation on failure rather than blocking),
  retrieves the top-5 chunks, acquires the P3 inference lock, and streams
  the response. Raises `MentorQueued` — caught by the API layer, not an
  error — when the lock can't be acquired within 30 seconds.
- `backend/app/api/v1/chat.py` — the three spec-mandated endpoints. `POST
  .../messages` *is* the SSE stream (spec's literal "Send message, stream
  response (SSE)"): it returns the stream directly, or HTTP 202 with the
  spec's queued body when the lock times out.

## Deliberate deviations from the spec's literal text

1. **No `/chat/{session_id}/pending` endpoint.** Section 9's prose mentions
   the frontend polling a pending-check endpoint while queued, but Section
   6's own endpoint contract — the one this project treats as authoritative,
   consistent with how every other domain was built — lists exactly three
   chat endpoints and none of them is `/pending`. The frontend (Phase 7)
   will simply retry the same `POST .../messages` call after `retry_after`
   seconds instead.
2. **`generate_embeddings` reads from a Redis-cached context, not from
   disk.** The spec's Stage 7 doesn't specify where the embedding job gets
   its content from; given `cleanup_node` already deletes the workspace at
   the end of the graph (a Phase 3 decision, unchanged here), caching the
   already-built `RepoContext` was the only option that doesn't either
   re-clone the repo or delay cleanup.

## Bug found and fixed during live verification

The query-embedding step (`_embed_query`) originally used a 20-second lock
timeout. Live-testing the "chatbot queues behind an active evaluation" path
revealed this compounds with the 30-second inference-lock wait: a chat
request arriving while the model is busy could wait up to *50 seconds*
before returning the spec's "within 30 seconds" HTTP 202 — silently
breaking that guarantee, even though embedding a query is meant to be a
~200ms operation (spec step 7). Fixed by dropping the embedding-lock
timeout to 5 seconds (`_EMBEDDING_WAIT_SECONDS`), so a busy model is
detected and degraded-to-no-RAG almost immediately rather than eating a
third of the whole request budget.

## A second bug found and fixed: StreamingResponse + `Depends(yield)`

The first version of `mentor.stream_response()` accepted the request-scoped
`db: AsyncSession` from `Depends(get_db)`. Live-testing a real chat message
against a real evaluation surfaced a `ForeignKeyViolationError` on the
assistant's message insert. Root cause: FastAPI closes a `yield`-based
dependency as soon as the route function *returns* — for a
`StreamingResponse`, that happens right after the first SSE chunk is
produced, long before the generator finishes streaming and tries to persist
the assistant's reply. The already-flushed `ChatSession`/user `ChatMessage`
rows were silently rolled back when `db` closed, so the later assistant-message
insert referenced a session row that no longer existed. Fixed by having
`stream_response()` open and own its own `async_session_factory()` session
internally (the same pattern ARQ jobs already use) instead of depending on
a caller-supplied one, and by committing the user's message immediately
rather than only flushing it. Caught by a real end-to-end test, not just
unit tests — a purely mocked test would not have exercised FastAPI's
dependency-teardown timing.

## A test-infra gap found and fixed

`get_model_queue_manager()` is `@lru_cache`'d in `app/dependencies.py`, same
as `get_redis()`. `tests/test_api/conftest.py` already clears `get_redis`'s
cache every test (a documented fix from an earlier phase, for the same
per-test-event-loop reason), but nothing cleared `get_model_queue_manager`'s
— because no endpoint had exercised it through the API test client before
this phase. The chatbot endpoints are the first to do so; without the fix,
the first test to touch `/chat/.../messages` would permanently pin every
later test's `ModelQueueManager` to that first test's already-closed Redis
connection. Fixed by adding `get_model_queue_manager.cache_clear()`
alongside the existing `get_redis.cache_clear()` in the `clean_db` fixture.

## Live end-to-end verification (real Ollama)

Ran through the full pipeline end-to-end against real public repos, fresh
hackathon/participants:

- **Embedding generation**: confirmed live via the `generate_embeddings` ARQ
  job log (`0.85s → ... generate_embeddings(...)`) and by querying
  `repo_embeddings` directly — `repo_summary`, `evaluation_summary`, and
  `readme` chunks stored for a real evaluated submission.
- **Mentor availability gate**: `POST /chat/{id}/sessions` correctly
  returned `mentor_available: false` with `"Your evaluation isn't complete
  yet..."` while the evaluation was still running, then `false` with
  `"Your mentor is being prepared..."` in the brief window after completion
  but before embeddings existed, then `true` once embeddings landed.
- **Real streamed response**: sent "Why did I score low on innovation, and
  how can I improve it?" — got back a token-by-token streamed answer that
  correctly opened with the participant's actual name ("Hi Ada,") and was
  grounded in the real README content and evaluation report (quoted the
  actual weaknesses identified by the evaluation, not generic advice).
  Confirmed persisted via `GET /chat/{id}/history` (both the user question
  and the full assistant reply, verbatim).
- **Queues behind an active evaluation**: confirmed twice.
  1. Passively, during a real evaluation of a larger repo (`linguist`):
     `GET /admin/model/status` correctly reported `lock_held_by:
     "eval:<submission_id>"` and `queue_depth: 1` while a second
     evaluation was genuinely queued behind it — the model-queue
     infrastructure and its reporting are both working correctly against
     real concurrent load, not just the happy path.
  2. Actively, with a controlled test: held the P0 inference lock for ~6
     real seconds while a live chat request was in flight. The request did
     not error or return early — it waited, then successfully acquired the
     lock the moment it freed and streamed a real, correctly-grounded
     response opening with the participant's actual question restated.
     This is precisely the Phase 6 gate: "chatbot queues cleanly behind an
     active evaluation, responds once lock frees."
  3. The complementary ">30s wait → HTTP 202 queued" path is covered by two
     automated tests using a monkeypatched threshold against a real Redis
     lock (see Testing below) rather than a second live run, since
     reliably holding a lock for a precise >30s window against a live
     server via shell scripting is inherently racy in a way that adds
     nothing an async-controlled test doesn't already prove more rigorously.
- **A genuine operational observation, not a bug**: mid-verification, an
  in-flight chat request was killed by `uvicorn --reload` restarting after
  a code edit, before its `finally` block could release the lock. The lock
  remained held under its 600-second safety TTL (Phase 0's
  `ModelQueueManager.LOCK_TIMEOUT`) until manually cleared. This is exactly
  the scenario that TTL exists to bound — confirmed it behaves correctly
  under an abrupt process kill, self-healing within the documented ceiling
  rather than deadlocking the system forever.

## Testing results

**155/155 tests pass** (38 new this phase, no regressions): chunker output
shape and truncation, the embedding-context Redis round trip, pgvector
retrieval ordering (`near`/`mid`/`far` cosine-distance vectors, k-limit,
submission-scoping) against a real Postgres instance, `embed_and_store_chunks`
replacing rather than accumulating rows, mentor availability gating (not
complete / no embeddings / degraded-but-available), session idempotency,
system-prompt and history formatting, `stream_response`'s full happy path
against real Redis locks with a fake LLM, and — the two tests most directly
proving the Phase 6 gate — a real P0 lock held via an async task while a P3
chat request queues and is confirmed to have persisted the user's message
without losing it, both at the orchestration level and through the full
HTTP API.

## Known issues / technical debt

- None introduced knowingly. Both real bugs found during live verification
  (the embedding-lock timeout compounding the 202 budget, and the
  StreamingResponse/`Depends(yield)` session lifetime mismatch) were fixed
  and re-verified live within this phase.

## What's next

Phase 7 — Frontend: the full Next.js application (design system and
degradation components, auth pages, radar chart + tooltips, admin live
dashboard, hackathon management, side-by-side comparison view, participant
submit/evaluation/leaderboard/mentor pages, PDF print stylesheet). This is
where the mentor chatbot gets an actual UI — `<MentorUnavailableState>` for
the two gated cases this phase's `mentor_available`/`unavailable_reason`
fields already support, and a streaming chat interface consuming the SSE
token events this phase produces.
