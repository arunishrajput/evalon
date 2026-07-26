# ADR-001: Backend Framework Choice (FastAPI)

**Status**: Accepted

## Context

EVALON needs a backend that serves a JSON API, holds a long-lived SSE
connection per active evaluation and per admin dashboard, and coordinates
with a Python-native AI orchestration layer (LangGraph, Ollama's HTTP
client) and a Python-native async job queue (ARQ). The framework choice
has to serve all three well simultaneously — a framework that's a poor
fit for any one of them pushes complexity elsewhere in the stack.

Alternatives considered: NestJS (Node/TypeScript), Django + Django REST
Framework (Python, sync-first).

## Decision

FastAPI, async throughout — every route, every DB call (SQLAlchemy 2.0's
async engine), every Ollama call.

Concretely, this means:
- Pydantic v2 models are the single source of truth for request/response
  validation *and* the auto-generated OpenAPI schema — no separate
  serializer layer to keep in sync.
- Every endpoint that touches the DB, Redis, or Ollama is `async def`,
  so a slow Ollama call in one request doesn't block the event loop from
  serving other requests (dashboard polling, other participants' status
  checks) concurrently.
- Custom exception classes (`EvalonError` and subclasses) map to
  structured JSON responses via a single registered exception handler —
  no raw exception or stack trace ever reaches a client.

## Consequences

**Gains:**
- The AI orchestration layer (LangGraph, static analysis subprocess
  wrappers, the Ollama HTTP client) stays in the same language and
  process family as the API — no cross-language IPC or duplicated domain
  models between an API service and a worker service.
- Async-native SSE (`StreamingResponse`) handles both the per-submission
  progress stream and the 15-second admin dashboard stream without
  threads or a separate WebSocket layer.
- Automatic OpenAPI docs at `/docs` come for free from the same Pydantic
  models used for validation — zero extra maintenance.

**Costs:**
- Async discipline has to be maintained everywhere — a single accidental
  sync/blocking call (e.g., a sync HTTP client used instead of `httpx`)
  would stall the entire event loop, not just one request. This is why
  every external call in the codebase (Ollama, GitHub API) explicitly
  uses `httpx.AsyncClient`.
- FastAPI's ecosystem for things like admin panels or auto-generated CRUD
  scaffolding is thinner than Django's — EVALON hand-writes its CRUD
  endpoints rather than relying on scaffolding, which is more code but
  gives full control over the async/degradation behavior every endpoint
  needs.
