# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); entries are
grouped by build phase rather than by release, since this is the initial
build (see `docs/reports/PHASE-N-REPORT.md` for the full narrative behind
each phase).

## [Unreleased] — 2026-07-26

### Phase 0 — Model Queue Infrastructure
- `ModelQueueManager`: Redis distributed lock, P0–P3 priority queue, lazy
  model load/unload via Ollama's `/api/ps` and `/api/generate`.
- `GET /api/v1/admin/model/status`.

### Phase 1 — Foundation
- Docker Compose stack (postgres+pgvector, redis, ollama, backend,
  worker, frontend, nginx), Pydantic Settings, async SQLAlchemy engine.
- Full schema via Alembic: users, hackathons, hackathon_participants,
  criteria, submissions, evaluations, agent_results, rankings,
  hackathon_stats, chat_sessions, chat_messages, repo_embeddings.

### Phase 2 — Authentication + Core API
- JWT auth with refresh rotation, rate-limited auth routes.
- Hackathon CRUD, weighted-criteria management, participant join flow.

### Phase 3 — Repository Pipeline
- Repository ingestion (clone, size/file-count/timeout limits), file
  processing (tree, language detection, tech stack, README scoring),
  static analysis (radon, semgrep, ESLint), SSE progress streaming.

### Phase 4 — AI Evaluation Agents
- `LLMProvider`, `BaseEvaluator` resilience pattern, the sequential
  LangGraph pipeline (never parallel), Repository Understanding / Code
  Quality / Innovation agents, and the analytics-only Comparative agent.

### Phase 5 — Scoring + Ranking
- Weighted score aggregation with static-analysis-only fallback,
  percentile normalization, ranking finalization gate, admin live
  dashboard (SSE), side-by-side comparison API, weasyprint PDF export.
- **Fixed:** `pydyf` version incompatibility with weasyprint 62.x
  (unconstrained transitive dependency resolved to a breaking version).

### Phase 6 — Chatbot + Embeddings
- Embedding pipeline (chunking, `nomic-embed-text` embedding, pgvector
  retrieval), the queue-aware (P3) mentor chatbot with SSE token
  streaming and the spec's HTTP 202 queued response.
- **Fixed:** the embedding-lock timeout compounding the chat inference
  lock's 30-second queued-response budget.
- **Fixed:** a `StreamingResponse` + FastAPI `Depends(yield)` session
  lifetime mismatch causing a real foreign-key violation on the
  assistant's persisted reply.
- **Fixed:** a test-infrastructure gap where `get_model_queue_manager()`
  wasn't cache-cleared between tests the way `get_redis()` was.

### Phase 7 — Frontend
- Full Next.js 14 App Router frontend: design system, degradation
  components, the evaluation page (radar chart with pool-average
  overlay, "why this score?" tooltips, live SSE progress, tabbed
  report, PDF/print export), admin live dashboard, hackathon
  management, side-by-side comparison, mentor chat UI, participant flow.
- **Fixed:** `NEXT_PUBLIC_API_URL` was missing the `/v1` path segment.
- **Fixed:** zustand `persist` middleware's async rehydration racing the
  auth guard, logging out already-authenticated users on a hard reload.
- **Fixed:** the submission page's stale-state check stranding a user on
  their own success path.
- **Fixed:** a cross-account localStorage leak — submission/join tracking
  wasn't scoped per user.
- **Fixed:** `ComparisonView`'s `position: sticky` header overlapping and
  hiding its own card's content.
- **Fixed:** a `top5_preview` type/response mismatch causing a React key
  warning.

### Phase 8 — Documentation + Polish
- `make seed` demo data script (previously referenced by the Makefile
  and the spec's demo script, but never implemented).
- Full documentation suite: README, SETUP, ARCHITECTURE, RESEARCH,
  FUTURE_SCOPE, DEBUGGING_GUIDE, PROJECT_STRUCTURE, this changelog, and
  ADR-001 through ADR-005 (joining ADR-006 from Phase 0).
- Docker Compose memory limits extended to every service, not just the
  three most obviously memory-hungry ones.
