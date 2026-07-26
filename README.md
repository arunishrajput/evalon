# EVALON

**AI-native hackathon evaluation engine.** Participants submit a GitHub repo
URL; EVALON clones it, runs static analysis, runs three sequential AI
agents against it, and produces an explainable, evidence-backed
scorecard — never a raw model opinion.

> Tools measure. AI explains. Every score traces to specific, observed
> evidence. One agent failure never crashes the pipeline — it degrades.

## Why EVALON

Most "AI judges" hackathons a repo by pasting it into an LLM and asking for
a number. That number is unfalsifiable — the judge (human or AI) can't
show their work, and a participant who disagrees has no way to check it.

EVALON inverts that: **static analysis tools measure first** (cyclomatic
complexity, security findings, documentation coverage, test presence), and
the AI agents are grounded in those measurements — every score a
participant sees links to the specific evidence that produced it, visible
in a "why this score?" tooltip on click. If the AI model is temporarily
unavailable (resource contention on a single consumer GPU, judging 30+
submissions), the evaluation still completes from static analysis alone,
clearly marked as degraded — never a hard failure, never a 500 the
participant has to guess about.

## Features

- **Three-agent evaluation pipeline** (Repository Understanding, Code
  Quality, Innovation) running strictly sequentially, each grounded in the
  same static analysis pass — never in parallel, so a single consumer GPU
  never has to hold two models in memory at once.
- **Explainable scorecards** — a radar chart with a pool-average overlay,
  and a click/hover "why this score?" tooltip on every criterion showing
  the top evidence that produced it.
- **Live admin dashboard** — SSE-streamed submission counts, score
  distribution, tech stack frequency, and model queue status, updating
  without a page refresh.
- **Side-by-side comparison** of up to 3 submissions, with shared
  weaknesses and unique strengths highlighted.
- **AI mentor chatbot** — a RAG-grounded conversation about *your*
  evaluation, queue-aware so it always yields to an active evaluation
  rather than fighting it for the model.
- **PDF export** (server-side, via weasyprint) and a client-side print
  stylesheet.
- **Graceful degradation everywhere** — a model-queue timeout, a stalled
  static analysis tool, or a comparative agent with too small a pool never
  crashes the pipeline or shows a raw error; every failure state has a
  specific, human-readable UI state.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI (async), SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Job queue | ARQ (Redis-backed async job queue) |
| AI orchestration | LangGraph (sequential graph), Ollama (`qwen2.5-coder:7b` inference, `nomic-embed-text` embeddings) |
| Static analysis | radon (complexity/maintainability), semgrep (security), ESLint (JS/TS lint) |
| Database | PostgreSQL 16 + pgvector (HNSW index for chat retrieval) |
| Cache / queue / pub-sub | Redis 7 |
| PDF generation | weasyprint |
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn/ui-style components, Recharts, Zustand, SWR |
| Deployment | Docker Compose (full stack) or Vercel (frontend) + Docker Compose (backend, for local Ollama/GPU access) |

## Screenshots

*(Run the app and capture these for your own README — described here so
you know what to show.)*

- **Landing page** — dark hero, feature highlights, participant/admin CTAs.
- **Admin live dashboard** — stat cards, score histogram, tech stack chart,
  top-5 preview, model queue status, all updating live via SSE.
- **Evaluation page** — the large color-coded score, the dual-overlay radar
  chart (your score vs. pool average), and a "why this score?" tooltip
  open on a criterion showing its evidence.
- **Side-by-side comparison** — 2–3 submissions in columns, unique
  strengths highlighted green, shared weaknesses highlighted red.
- **Mentor chat** — a streamed, markdown-formatted response grounded in
  the participant's own repository and evaluation report.

## Quick start (Docker Compose)

```bash
git clone <this-repo>
cd evalon
cp .env.example .env          # edit JWT_SECRET at minimum before any real deployment
ollama pull qwen2.5-coder:7b  # ~4.7GB — do this once, before `make up`
ollama pull nomic-embed-text  # ~270MB

make up          # starts postgres, redis, backend, worker, frontend, nginx
make migrate      # alembic upgrade head
make seed         # admin@evalon.dev / admin123, 3 participants, demo hackathon
```

Open `http://localhost:3000` (or `http://localhost` via nginx) and sign in
with the seeded admin account, or register a new participant. Full
step-by-step walkthrough — including the exact demo script and
troubleshooting — is in [`SETUP.md`](SETUP.md).

**macOS note:** Ollama runs natively on the host (not in Docker) so it can
use Metal GPU acceleration — Docker Desktop on macOS can't pass Metal
through to a container. `docker-compose.yml` points backend/worker at
`http://host.docker.internal:11434` by default. See `SETUP.md` for the
Linux/NVIDIA containerized-Ollama alternative.

## Environment variables

Full reference lives in [`.env.example`](.env.example) with inline
comments; the ones you're most likely to actually change:

| Variable | Purpose | Default |
|---|---|---|
| `JWT_SECRET` | Signs access/refresh tokens | placeholder — **change before any real deployment** |
| `OLLAMA_BASE_URL` | Where the backend/worker reach Ollama | `http://host.docker.internal:11434` (native host Ollama) |
| `INFERENCE_MODEL` / `EMBEDDING_MODEL` | Ollama model names | `qwen2.5-coder:7b` / `nomic-embed-text` |
| `MAX_REPO_SIZE_MB` / `MAX_FILE_COUNT` | Ingestion limits | `50` / `5000` |
| `GITHUB_API_TOKEN` | Raises GitHub's unauthenticated 60/hr rate limit | empty (works, just rate-limited) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `localhost:3000`, `localhost`, a Vercel placeholder |
| `NEXT_PUBLIC_API_URL` | Frontend's API base URL — **must include `/api/v1`** | `http://localhost:8000/api/v1` |

## Project structure

See [`docs/architecture/`](docs/architecture) for diagrams and
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full technical writeup. At a
glance:

```
backend/app/
  core/          ModelQueueManager — the Redis-backed lock serializing all Ollama access
  pipeline/      Repository ingestion, file processing, static analysis
  agents/        The three LLM agents + the comparative (non-LLM) agent
  orchestration/ The sequential LangGraph evaluation graph
  scoring/       Aggregation, ranking, dashboard stats, PDF export
  embedding/     Chunking + embedding + retrieval for the mentor's RAG context
  chatbot/       Mentor orchestration and system-prompt assembly
  jobs/          ARQ worker + task definitions
frontend/src/
  app/           Next.js App Router pages (admin/*, participant/*, auth/*)
  components/    Evaluation, dashboard, comparison, mentor, and shadcn/ui components
  lib/           Typed API client, SSE parsing, shared types
```

## Testing

```bash
make test    # backend: pytest against real Postgres/Redis, 155+ tests
cd frontend && npm run build   # production build — catches TS errors dev mode won't
```

Backend tests exercise real Postgres and Redis (not mocks) — the model
queue's distributed-lock tests specifically depend on that being real, to
actually prove concurrent requesters serialize correctly. Frontend
correctness for this phase was established via live browser-driven
verification (see `docs/reports/PHASE-7-REPORT.md`) rather than a
dedicated test suite — Jest/Playwright aren't part of the spec's stack.

## Documentation

- [`SETUP.md`](SETUP.md) — full setup, the demo script, troubleshooting
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system diagrams, data flow, design patterns
- [`RESEARCH.md`](RESEARCH.md) — the technology comparisons behind every major choice
- [`FUTURE_SCOPE.md`](FUTURE_SCOPE.md) — what's deliberately out of scope, and how it'd be built
- [`DEBUGGING_GUIDE.md`](DEBUGGING_GUIDE.md) — common failure modes and how to diagnose them
- [`docs/decisions/`](docs/decisions) — Architecture Decision Records
- [`docs/reports/`](docs/reports) — a phase-by-phase build log, including every bug found during live verification and how it was fixed

## Contributing

This project was built end-to-end against a fixed specification
(`docs/SPEC.md`) as a phased build exercise. If you're extending it:

1. Read `docs/SPEC.md`'s non-negotiable principles first (Section 2) —
   they constrain design decisions throughout the codebase (e.g., "agents
   run sequentially, never in parallel" isn't a performance choice, it's a
   hardware constraint the `ModelQueueManager` exists to enforce).
2. Check `docs/decisions/` before changing a core architectural choice —
   there's likely an ADR explaining why it's built the way it is.
3. Run `make test` before opening a PR; the model queue and degradation
   paths are the parts most likely to break silently.

## License

MIT.
