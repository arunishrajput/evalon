# EVALON — Project Structure

```
evalon/
├── docker-compose.yml          # Full stack: postgres, redis, ollama (opt-in), backend, worker, frontend, nginx
├── docker-compose.dev.yml      # Local-dev overrides
├── .env.example                # Every environment variable, documented inline
├── Makefile                    # make up/migrate/seed/test/model-status/...
├── README.md / SETUP.md / ARCHITECTURE.md / RESEARCH.md / FUTURE_SCOPE.md / DEBUGGING_GUIDE.md
├── docs/
│   ├── SPEC.md                 # The full build specification this project was built against
│   ├── decisions/               # ADR-001..006 — one per major architectural choice
│   └── reports/                 # PHASE-0..7-REPORT.md — a build log, phase by phase
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, exception handlers, CORS
│   │   ├── config.py           # Pydantic Settings — every env var, typed
│   │   ├── database.py         # Async SQLAlchemy engine/session factory
│   │   ├── core/
│   │   │   ├── model_queue.py  # ModelQueueManager — the Redis-backed lock (see ADR-006)
│   │   │   ├── security.py     # JWT issuance/verification, password hashing
│   │   │   └── exceptions.py   # EvalonError hierarchy → structured JSON responses
│   │   ├── models/              # SQLAlchemy ORM models — one file per table
│   │   ├── schemas/             # Pydantic v2 request/response schemas
│   │   ├── api/v1/               # One router file per domain (auth, hackathons, submissions, ...)
│   │   ├── pipeline/             # Repository ingestion, file processing, static analysis
│   │   ├── agents/               # The 3 LLM agents + the comparative (non-LLM) agent
│   │   ├── orchestration/        # The sequential LangGraph (graph.py, nodes.py, state.py)
│   │   ├── scoring/               # Aggregation, ranking, dashboard stats, PDF export
│   │   ├── embedding/             # Chunking + embedding + pgvector retrieval for the mentor
│   │   ├── chatbot/                # Mentor orchestration + RAG context assembly
│   │   ├── jobs/                    # ARQ worker definition + task functions
│   │   └── scripts/seed.py          # Demo data — make seed
│   └── tests/                        # pytest, against real Postgres/Redis — mirrors app/ structure
└── frontend/
    └── src/
        ├── app/                       # Next.js App Router pages — admin/*, participant/*, auth/*
        ├── components/
        │   ├── ui/                     # shadcn/ui-style primitives
        │   ├── states/                 # DegradedBanner, AgentAbstainedBadge, ModelLoadingState, MentorUnavailableState
        │   ├── evaluation/              # ScoreRadarChart, ScoreTooltip, ReportViewer, PrintableReport, ...
        │   ├── dashboard/                # LiveDashboard, ScoreHistogram, TechStackCloud
        │   ├── comparison/                # ComparisonView
        │   └── mentor/                     # ChatInterface
        ├── lib/                              # Typed API client, SSE parsing, shared TS types
        ├── hooks/                             # useEvaluationStream, useDashboardStream, useRequireAuth
        └── store/                              # Zustand auth store
```

## Where to start reading

- **New to the codebase?** Start with `ARCHITECTURE.md`'s diagrams, then
  `app/orchestration/graph.py` — the evaluation pipeline is the spine
  everything else hangs off.
- **Adding a feature?** Check `docs/decisions/` first — there's likely an
  ADR explaining a constraint that isn't obvious from the code alone
  (e.g., why agents never run in parallel).
- **Debugging a live issue?** `DEBUGGING_GUIDE.md` is written around
  actual failure modes, not a generic troubleshooting template.
- **Understanding a specific phase's reasoning?** `docs/reports/` has one
  file per build phase, including every bug found during live
  verification and exactly how it was diagnosed and fixed — closer to a
  commit-log narrative than typical documentation.
