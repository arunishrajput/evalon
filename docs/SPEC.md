====================================================
CLAUDE CODE MVP EXECUTION PROMPT (don't push it to git)
PROJECT: **EVALON** - HACKATHON EVALUATION ENGINE
VERSION: MVP-1.0 (RESOURCE-AWARE BUILD)
CLASSIFICATION: AUTONOMOUS ENGINEERING HANDOFF
====================================================

YOU ARE THE FOUNDING ENGINEER OF THIS PROJECT.

You are a senior software engineer, systems architect, AI systems designer,
technical writer, DevOps engineer, and product engineer operating as a
single autonomous entity. Your job is to design, build, document, test,
and ship the MVP of EVALON — the Hackathon Evaluation Engine described below.

You will work autonomously. You will think deeply before writing code.
You will verify your work. You will document your decisions. You will not
take shortcuts that create hidden technical debt. You will not write
placeholder logic without explicitly labeling it as such.

_READ THIS ENTIRE PROMPT BEFORE WRITING A SINGLE LINE OF CODE._

====================================================
SECTION 1: PRODUCT OVERVIEW
====================================================

EVALON is an AI-native hackathon infrastructure platform that:

1. Allows admins to create hackathons, define custom judging criteria with
   configurable weightages, and manage the full evaluation lifecycle.

2. Allows participants to join hackathons, submit GitHub repository URLs,
   receive AI-generated evaluation reports, view ranked standings, and
   interact with a personalized AI mentor chatbot.

3. Automatically clones, analyzes, and evaluates submitted repositories
   using a multi-stage pipeline combining static analysis tools and
   specialized AI agents running via Ollama (local LLM inference).

4. Generates explainable, evidence-backed, structured evaluation reports
   that feel like they were written by an elite engineering review panel —
   not a generic AI summary.

5. Converts hackathon participation into a learning experience by providing
   specific, actionable feedback grounded in observed code evidence.

====================================================
SECTION 2: CORE PHILOSOPHY
====================================================

_NEVER VIOLATE THESE PRINCIPLES:_

P1: AI explains. Deterministic tools measure. Scores are computed from
structured tool output, not from raw LLM number generation.

P2: Every score must trace to specific evidence observed in the repository.
"Good code quality" is insufficient. "12 functions with cyclomatic
complexity > 10, 0 docstrings in core modules, no error handling in
3 API endpoints" is the standard.

P3: The evaluation pipeline must be resilient. An agent failure must not
crash the entire evaluation. Partial results are better than no results.
Every failure path must produce a human-readable degraded state —
never a raw error or 500 in the UI.

P4: No submitted code is ever executed. Static analysis only. No npm
install, no pip install, no build steps, no script execution.
Cloned repos are treated as text files only.

P5: The system must feel fair and transparent. Admins must be able to
inspect every AI decision. Participants must see the reasoning
behind every score.

P6: Build for the demo, architect for production. The MVP runs on
Docker Compose. The architecture must support horizontal scaling
without rewrites.

P7: ONE MODEL AT A TIME. The system must never attempt to load multiple
large language models simultaneously. All LLM inference is serialized
through a single resource-aware queue. Memory budget is always respected.

====================================================
SECTION 3: TECHNOLOGY STACK
====================================================

BACKEND:

- Language: Python 3.11+
- Framework: FastAPI (async)
- Task Queue: ARQ (async Python job queue backed by Redis)
- ORM: SQLAlchemy 2.0 (async) with Alembic migrations
- Validation: Pydantic v2
- Authentication: JWT (python-jose) with refresh token rotation
- AI Orchestration: LangGraph 0.2+
- LLM Runtime: Ollama (local)

PRIMARY MODEL STRATEGY (CRITICAL — READ CAREFULLY):
Use EXACTLY TWO models total. No more.

- Inference model: qwen2.5-coder:7b (Q4_K_M quantization)
  Used for: ALL agent reasoning, report generation, mentor chatbot
  Memory footprint: ~4.5GB unified memory
- Embedding model: nomic-embed-text
  Used for: ALL embedding operations only
  Memory footprint: ~274MB unified memory
- DO NOT use qwen2.5:7b or any third model.
- Total peak memory: ~4.8GB (when inference model + embedding model coexist)
- qwen2.5-coder:7b handles general reasoning perfectly well. No separate
  general model is needed or permitted.

- Static Analysis: gitpython, pygments, radon, semgrep (Python API),
  subprocess-based ESLint for JS/TS projects
- Repository Ingestion: gitpython
- HTTP Client: httpx (async)
- Real-time: SSE via FastAPI streaming responses
- PDF Generation: weasyprint (server-side PDF for report export)

FRONTEND:

- Framework: Next.js 14+ (App Router)
- Styling: Tailwind CSS
- Component Library: shadcn/ui
- Charts: Recharts (RadarChart for score visualization, BarChart for dashboard)
- Icons: Lucide React
- HTTP: fetch with SWR for data fetching
- Real-time: EventSource API (SSE client)
- State: Zustand (lightweight, sufficient for MVP)
- PDF Export: browser window.print() with dedicated print stylesheet
  (simpler and more reliable than react-pdf for this use case)

DATABASE:

- Primary: PostgreSQL 16 with pgvector extension
- Cache / Queue Broker: Redis 7

INFRASTRUCTURE:

- Container: Docker + Docker Compose (primary development and demo)
- Frontend Deployment (optional): Vercel (free tier, one-click deploy)
- Reverse Proxy: Nginx (in Docker Compose, routes /api to backend, / to frontend)
- Volume: Named Docker volumes for postgres data, redis data, ollama models,
  repo clone workspace

DEVELOPMENT TOOLING:

- Backend: pytest, pytest-asyncio, httpx (test client), factory-boy
- Frontend: ESLint, Prettier
- Pre-commit: configured but not blocking in MVP CI
- Environment: .env files, python-dotenv, pydantic Settings

====================================================
SECTION 3A: MODEL RESOURCE MANAGEMENT — CRITICAL SYSTEM
====================================================

THIS IS THE MOST IMPORTANT INFRASTRUCTURE DECISION IN EVALON.
Failure to implement this correctly will cause model loading failures,
OOM errors, and evaluation crashes on consumer hardware.

PROBLEM STATEMENT:
On a MacBook Pro M4 with 24GB unified memory, attempting to load multiple
Ollama models simultaneously will fail. The evaluation pipeline has multiple
agents, an embedding pipeline, and a chatbot — all competing for the same
inference runtime. Naïve parallel execution causes partial model loads,
corrupted inference, and broken user-facing features.

SOLUTION: ModelQueueManager — A Redis-backed serialization layer for ALL
Ollama calls across the entire system.

ARCHITECTURE:

```
┌─────────────────────────────────────────────────────┐
│                   ModelQueueManager                  │
│                                                      │
│  Redis Key: evalon:model:lock (distributed lock)     │
│  Redis Key: evalon:model:current (loaded model name) │
│  Redis Key: evalon:model:queue (priority queue)      │
│                                                      │
│  Priority Levels:                                    │
│  P0 (highest): active evaluation agents              │
│  P1: report generation                               │
│  P2: embedding generation                            │
│  P3 (lowest): chatbot inference                      │
└─────────────────────────────────────────────────────┘
```

IMPLEMENT ModelQueueManager as app/core/model_queue.py:

```python
class ModelQueueManager:
    """
    Serializes all Ollama inference calls to prevent simultaneous
    model loading. Uses Redis distributed lock to coordinate across
    multiple ARQ worker processes.
    """

    INFERENCE_MODEL = "qwen2.5-coder:7b"
    EMBEDDING_MODEL = "nomic-embed-text"
    LOCK_KEY = "evalon:model:lock"
    LOCK_TIMEOUT = 600  # 10 minutes — max time any single inference call holds lock
    CURRENT_MODEL_KEY = "evalon:model:current"

    async def acquire_inference_lock(
        self,
        requester_id: str,
        priority: int = 2,
        timeout: int = 300
    ) -> AsyncContextManager:
        """
        Acquire exclusive access to the inference model.
        Blocks until lock is available (with timeout).
        Unloads embedding model if it is currently loaded.
        Loads inference model if not already loaded.
        """

    async def acquire_embedding_lock(
        self,
        requester_id: str,
        timeout: int = 120
    ) -> AsyncContextManager:
        """
        Acquire exclusive access to the embedding model.
        Blocks until inference lock is released.
        Unloads inference model if loaded (keeps_alive=0).
        Loads embedding model.
        """

    async def _ensure_model_loaded(self, model_name: str) -> None:
        """
        Check if model is loaded via Ollama /api/ps endpoint.
        If different model is loaded, unload it first (keep_alive: 0).
        Then load the required model via /api/generate with empty prompt.
        """

    async def _unload_model(self, model_name: str) -> None:
        """
        Unload model from memory via Ollama API:
        POST /api/generate with keep_alive: "0"
        Verify model is unloaded via /api/ps check.
        """

    async def health_check(self) -> dict:
        """
        Returns: {
          "ollama_reachable": bool,
          "inference_model_available": bool,
          "embedding_model_available": bool,
          "current_loaded_model": str | None,
          "queue_depth": int
        }
        """
```

MODEL SWITCHING STRATEGY:

- During evaluation pipeline: inference model is held for ALL agents (no switching)
  The pipeline acquires lock ONCE before Agent 1, holds it through Agent 3, releases after
- After all agents complete: release inference lock
- Embedding job: acquires embedding lock (unloads inference model first)
- Chatbot request: acquires inference lock with P3 priority
  If evaluation is in progress, chatbot waits in queue — does NOT crash
  UI shows "Mentor is loading, please wait a moment..." during wait

OLLAMA KEEP_ALIVE CONFIGURATION:

- During active evaluation: keep_alive = "10m"
- After evaluation completes (waiting for next request): keep_alive = "2m"
- Embedding model: keep_alive = "1m" (small, fast to reload)
- Set via Ollama API parameter on each request, not globally

STARTUP BEHAVIOR:

- DO NOT preload any models at Docker Compose startup
- Models are loaded on first request (lazy loading)
- Health check endpoint reports model availability but does NOT load models
- First evaluation will be slower (model load time). Document this in SETUP.md.

OLLAMA DOCKER SERVICE MEMORY LIMIT:
In docker-compose.yml, set Ollama service memory limit:

```yaml
ollama:
    mem_limit: 8g # Hard cap — prevents OOM from killing host system
    memswap_limit: 8g # No swap (swap kills performance)
```

ERROR HANDLING FOR MODEL LOCK TIMEOUT:
If a requester cannot acquire the model lock within their timeout:

- Return a structured ModelUnavailableError
- Pipeline catches this and sets agent to abstained with reason:
  "Model temporarily unavailable due to resource contention. Score computed
  from static analysis only."
- UI displays this as a warning badge, NOT an error
- Evaluation continues with static-analysis-only scoring for that agent

====================================================
SECTION 4: DIRECTORY STRUCTURE
====================================================

You MUST organize the project exactly as follows. Create this structure
before writing any business logic.

```
evalon/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── CHANGELOG.md
├── SETUP.md
├── ARCHITECTURE.md
├── RESEARCH.md
├── PROJECT_STRUCTURE.md
├── FUTURE_SCOPE.md
├── DEBUGGING_GUIDE.md
├── docs/
│   ├── api/                      # Auto-generated OpenAPI docs
│   ├── architecture/             # Architecture diagrams (Mermaid)
│   ├── decisions/                # Architecture Decision Records
│   │   ├── ADR-001-framework-choice.md
│   │   ├── ADR-002-database-choice.md
│   │   ├── ADR-003-ai-orchestration.md
│   │   ├── ADR-004-queue-system.md
│   │   ├── ADR-005-evaluation-strategy.md
│   │   └── ADR-006-model-resource-management.md
│   └── reports/                  # Implementation phase reports
│       ├── PHASE-1-REPORT.md
│       ├── PHASE-2-REPORT.md
│       └── ...
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # FastAPI application factory
│   │   ├── config.py             # Pydantic Settings
│   │   ├── database.py           # Async SQLAlchemy engine + session
│   │   ├── dependencies.py       # FastAPI dependency injection
│   │   ├── core/
│   │   │   ├── security.py       # JWT, password hashing
│   │   │   ├── exceptions.py     # Custom exception classes
│   │   │   ├── middleware.py     # CORS, request logging
│   │   │   └── model_queue.py    # ModelQueueManager
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── hackathon.py
│   │   │   ├── criterion.py
│   │   │   ├── submission.py
│   │   │   ├── evaluation.py
│   │   │   ├── agent_result.py
│   │   │   ├── ranking.py
│   │   │   ├── chat.py
│   │   │   └── repo_embedding.py
│   │   ├── schemas/              # Pydantic v2 request/response schemas
│   │   │   ├── user.py
│   │   │   ├── hackathon.py
│   │   │   ├── submission.py
│   │   │   ├── evaluation.py
│   │   │   ├── ranking.py
│   │   │   ├── chat.py
│   │   │   └── dashboard.py      # admin dashboard schemas
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── router.py     # Main APIRouter aggregator
│   │   │   │   ├── auth.py       # /auth endpoints
│   │   │   │   ├── hackathons.py # /hackathons CRUD
│   │   │   │   ├── submissions.py# /submissions + SSE status
│   │   │   │   ├── evaluations.py# /evaluations reports
│   │   │   │   ├── rankings.py   # /rankings leaderboard
│   │   │   │   ├── chat.py       # /chat mentor chatbot
│   │   │   │   ├── dashboard.py      # live admin dashboard API
│   │   │   │   ├── comparison.py     # side-by-side comparison API
│   │   │   │   └── export.py         # PDF report export API
│   │   ├── pipeline/
│   │   │   ├── ingestion.py      # Repository clone + sanitize
│   │   │   ├── file_processor.py # File tree, language detection
│   │   │   ├── static_analysis.py# All static analysis orchestration
│   │   │   └── context_builder.py# Assembles RepoContext from all above
│   │   ├── agents/
│   │   │   ├── base.py           # BaseEvaluator abstract class
│   │   │   ├── registry.py       # Agent registry (auto-discover)
│   │   │   ├── llm_provider.py   # Ollama LLM provider abstraction
│   │   │   ├── repo_understanding.py
│   │   │   ├── code_quality.py
│   │   │   ├── innovation.py
│   │   │   ├── comparative.py        # PARTIAL IMPLEMENTATION (see Section 8)
│   │   │   └── prompts/          # Jinja2 prompt templates
│   │   │       ├── repo_understanding.j2
│   │   │       ├── code_quality.j2
│   │   │       └── innovation.j2
│   │   ├── orchestration/
│   │   │   ├── graph.py              # SEQUENTIAL graph (not parallel)
│   │   │   ├── state.py
│   │   │   └── nodes.py
│   │   ├── scoring/
│   │   │   ├── aggregator.py     # Weighted score aggregation
│   │   │   ├── normalizer.py     # Cross-submission percentile normalization
│   │   │   └── report_generator.py# Final report assembly
│   │   ├── embedding/
│   │   │   ├── chunker.py        # Content chunking strategy
│   │   │   ├── embedder.py       # nomic-embed-text via Ollama
│   │   │   └── retriever.py      # pgvector similarity search
│   │   ├── chatbot/
│   │   │   ├── mentor.py         # AI Mentor chatbot logic
│   │   │   └── context.py        # Chat context assembly (RAG)
│   │   ├── jobs/
│   │   │   ├── worker.py         # ARQ worker definition
│   │   │   ├── tasks.py          # Job task definitions
│   │   │   └── queue.py          # Queue client + job dispatch
│   │   └── utils/
│   │       ├── file_utils.py
│   │       ├── git_utils.py
│   │       └── logging_utils.py
│   └── tests/
│       ├── conftest.py
│       ├── test_pipeline/
│       ├── test_agents/
│       ├── test_scoring/
│       └── test_api/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── .eslintrc.json
│   ├── vercel.json                   # Vercel deployment config
│   ├── public/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx             # Landing page
│       │   ├── auth/
│       │   │   ├── login/page.tsx
│       │   │   └── register/page.tsx
│       │   ├── admin/
│       │   │   ├── layout.tsx
│       │   │   ├── page.tsx         # Admin home / hackathon list
│       │   │   ├── dashboard/page.tsx        # live hackathon dashboard
│       │   │   ├── hackathons/
│       │   │   │   ├── new/page.tsx
│       │   │   │   └── [id]/
│       │   │   │       ├── page.tsx        # Hackathon overview
│       │   │   │       ├── criteria/page.tsx
│       │   │   │       ├── submissions/page.tsx
│       │   │   │       ├── rankings/page.tsx
│       │   │   │       └── compare/page.tsx  # side-by-side comparison
│       │   └── participant/
│       │       ├── layout.tsx
│       │       ├── page.tsx         # Participant home
│       │       ├── hackathons/page.tsx
│       │       ├── submit/[hackathonId]/page.tsx
│       │       ├── evaluation/[submissionId]/page.tsx
│       │       ├── leaderboard/[hackathonId]/page.tsx
│       │       └── mentor/[submissionId]/page.tsx
│       ├── components/
│       │   ├── ui/                  # shadcn/ui components
│       │   ├── layout/
│       │   ├── hackathon/
│       │   ├── evaluation/
│       │   │   ├── ScoreRadarChart.tsx       # REINFORCED SPEC — see Section 10
│       │   │   ├── AgentResultCard.tsx
│       │   │   ├── EvidenceList.tsx
│       │   │   ├── ProgressStream.tsx   # SSE consumer
│       │   │   ├── ReportViewer.tsx
│       │   │   ├── ScoreTooltip.tsx          # "Why This Score?" tooltip
│       │   │   └── PrintableReport.tsx       # PDF print layout
│       │   ├── leaderboard/
│       │   ├── dashboard/
│       │   │   ├── LiveDashboard.tsx         # real-time admin stats
│       │   │   ├── ScoreHistogram.tsx        # score distribution chart
│       │   │   └── TechStackCloud.tsx        # tech stack frequency
│       │   ├── comparison/
│       │   │   └── ComparisonView.tsx        # side-by-side submissions
│       │   └── mentor/
│       │       └── ChatInterface.tsx
│       ├── lib/
│       │   ├── api.ts               # API client
│       │   ├── auth.ts              # Auth utilities
│       │   └── types.ts             # TypeScript type definitions
│       ├── store/
│       │   └── auth.ts              # Zustand auth store
│       └── hooks/
│           ├── useEvaluationStream.ts  # SSE hook
│           ├── useDashboardStream.ts         # SSE for live dashboard
│           └── useSWR hooks
└── nginx/
    └── nginx.conf
```

====================================================
SECTION 5: DATABASE SCHEMA
====================================================

Design and implement the following complete schema via Alembic migrations.
All tables use UUID primary keys. All timestamps are stored in UTC.

TABLE: users

- id: UUID PK
- email: VARCHAR(255) UNIQUE NOT NULL
- hashed_password: VARCHAR(255) NOT NULL
- full_name: VARCHAR(255)
- role: ENUM('admin', 'participant') NOT NULL DEFAULT 'participant'
- is_active: BOOLEAN DEFAULT TRUE
- created_at: TIMESTAMPTZ DEFAULT NOW()
- updated_at: TIMESTAMPTZ

TABLE: hackathons

- id: UUID PK
- title: VARCHAR(255) NOT NULL
- description: TEXT
- admin_id: UUID FK → users.id
- status: ENUM('draft', 'active', 'evaluating', 'finalized') DEFAULT 'draft'
- start_date: TIMESTAMPTZ
- end_date: TIMESTAMPTZ
- max_submissions: INTEGER DEFAULT 100
- settings: JSONB DEFAULT '{}'
    # settings schema: { "allow_private_repos": false,
    # "max_repo_size_mb": 50, "evaluation_mode": "standard",
    # "show_rankings_before_finalization": false }
- created_at: TIMESTAMPTZ DEFAULT NOW()
- updated_at: TIMESTAMPTZ

TABLE: hackathon_participants

- id: UUID PK
- hackathon_id: UUID FK → hackathons.id
- user_id: UUID FK → users.id
- joined_at: TIMESTAMPTZ DEFAULT NOW()
- UNIQUE(hackathon_id, user_id)

TABLE: criteria

- id: UUID PK
- hackathon_id: UUID FK → hackathons.id
- name: VARCHAR(255) NOT NULL
- description: TEXT
- weight: DECIMAL(4,3) NOT NULL # 0.000 to 1.000, must sum to 1.0 per hackathon
- agent_id: VARCHAR(100) # Maps to agent registry key
- display_order: INTEGER DEFAULT 0
- created_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: submissions

- id: UUID PK
- hackathon_id: UUID FK → hackathons.id
- user_id: UUID FK → users.id
- repo_url: VARCHAR(500) NOT NULL
- repo_name: VARCHAR(255)
- repo_description: TEXT # Extracted from GitHub API or README
- tech_stack: JSONB DEFAULT '[]' # extracted tech stack list for dashboard
- status: ENUM('pending', 'cloning', 'analyzing', 'evaluating',
  'completed', 'failed') DEFAULT 'pending'
- error_message: TEXT
- degraded: BOOLEAN DEFAULT FALSE # true if any agent abstained/failed
- degraded_reason: TEXT # human-readable explanation
- submitted_at: TIMESTAMPTZ DEFAULT NOW()
- clone_completed_at: TIMESTAMPTZ
- analysis_completed_at: TIMESTAMPTZ
- evaluation_completed_at: TIMESTAMPTZ
- UNIQUE(hackathon_id, user_id) # One submission per participant per hackathon

TABLE: evaluations

- id: UUID PK
- submission_id: UUID FK → submissions.id UNIQUE
- hackathon_id: UUID FK → hackathons.id
- status: ENUM('pending', 'running', 'completed', 'failed', 'degraded') DEFAULT 'pending'
- final_score: DECIMAL(6,3)
- report: JSONB
- started_at: TIMESTAMPTZ
- completed_at: TIMESTAMPTZ
- model_versions: JSONB
- agents_completed: JSONB DEFAULT '[]' # list of agent_ids that completed
- agents_abstained: JSONB DEFAULT '[]' # list of agent_ids that abstained
- created_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: agent_results

- id: UUID PK
- evaluation_id: UUID FK → evaluations.id
- agent_id: VARCHAR(100) NOT NULL
- criterion_id: UUID FK → criteria.id # Which criterion this maps to
- score_raw: DECIMAL(6,3) # 0.000 to 100.000
- confidence: DECIMAL(4,3) # 0.000 to 1.000
- evidence: JSONB # List of { finding: str, impact: str, file_ref: str }
- strengths: JSONB # List[str]
- weaknesses: JSONB # List[str]
- top_evidence: JSONB DEFAULT '[]' # top 2 evidence items for tooltip display
- reasoning: TEXT # Full AI reasoning text
- abstained: BOOLEAN DEFAULT FALSE
- abstain_reason: TEXT
- fallback_used: BOOLEAN DEFAULT FALSE # true if static-analysis-only scoring
- prompt_version: VARCHAR(50)
- model_version: VARCHAR(100)
- processing_time_ms: INTEGER
- created_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: rankings

- id: UUID PK
- hackathon_id: UUID FK → hackathons.id
- submission_id: UUID FK → submissions.id
- rank: INTEGER NOT NULL
- percentile: DECIMAL(5,2) # 0.00 to 100.00
- normalized_score: DECIMAL(6,3)
- finalized: BOOLEAN DEFAULT FALSE
- finalized_at: TIMESTAMPTZ
- finalized_by: UUID FK → users.id
- computation_metadata: JSONB # How ranking was computed
- created_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: hackathon_stats # NEW — pre-computed dashboard stats

- id: UUID PK
- hackathon_id: UUID FK → hackathons.id UNIQUE
- total_submissions: INTEGER DEFAULT 0
- evaluations_completed: INTEGER DEFAULT 0
- evaluations_in_progress: INTEGER DEFAULT 0
- evaluations_queued: INTEGER DEFAULT 0
- evaluations_failed: INTEGER DEFAULT 0
- score_distribution: JSONB DEFAULT '{}'
    # { "0-10": 0, "10-20": 0, "20-30": 0, ..., "90-100": 0 }
- tech_stack_frequency: JSONB DEFAULT '{}'
    # { "React": 12, "FastAPI": 8, "Python": 22, ... }
- avg_score: DECIMAL(6,3)
- top5_preview: JSONB DEFAULT '[]'
    # [{ rank, repo_name, score }, ...]
- updated_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: chat_sessions

- id: UUID PK
- user_id: UUID FK → users.id
- submission_id: UUID FK → submissions.id
- hackathon_id: UUID FK → hackathons.id
- created_at: TIMESTAMPTZ DEFAULT NOW()
- last_message_at: TIMESTAMPTZ

TABLE: chat_messages

- id: UUID PK
- session_id: UUID FK → chat_sessions.id
- role: ENUM('user', 'assistant') NOT NULL
- content: TEXT NOT NULL
- retrieved_chunks: JSONB # Which embedding chunks were retrieved
- created_at: TIMESTAMPTZ DEFAULT NOW()

TABLE: repo_embeddings

- id: UUID PK
- submission_id: UUID FK → submissions.id
- chunk_type: VARCHAR(100)
- chunk_content: TEXT NOT NULL
- embedding: VECTOR(768) # nomic-embed-text dimension
- metadata: JSONB # Additional context for retrieval
- created_at: TIMESTAMPTZ DEFAULT NOW()

INDEX REQUIREMENTS:

- INDEX on submissions(hackathon_id, status)
- INDEX on submissions(hackathon_id) — for dashboard aggregation
- INDEX on evaluations(submission_id)
- INDEX on agent_results(evaluation_id, agent_id)
- INDEX on rankings(hackathon_id, rank)
- HNSW INDEX on repo_embeddings(embedding) using pgvector

====================================================
SECTION 6: API CONTRACT
====================================================

Implement ALL of the following endpoints. All endpoints return JSON.
All non-public endpoints require Bearer JWT authentication.
All list endpoints support pagination (page, page_size query params).

AUTH ENDPOINTS:
POST /api/v1/auth/register # Create account
POST /api/v1/auth/login # Returns access_token + refresh_token
POST /api/v1/auth/refresh # Refresh access token
POST /api/v1/auth/logout # Invalidate refresh token
GET /api/v1/auth/me # Current user profile

HACKATHON ENDPOINTS (Admin only for mutating operations):
GET /api/v1/hackathons # List all hackathons (public metadata)
POST /api/v1/hackathons # Create hackathon [admin]
GET /api/v1/hackathons/{id} # Hackathon details
PATCH /api/v1/hackathons/{id} # Update hackathon [admin, owner]
DELETE /api/v1/hackathons/{id} # Delete hackathon [admin, owner]
PATCH /api/v1/hackathons/{id}/status # Transition status [admin, owner]
GET /api/v1/hackathons/{id}/criteria # List criteria
POST /api/v1/hackathons/{id}/criteria # Add criterion [admin, owner]
PUT /api/v1/hackathons/{id}/criteria # Replace all criteria (bulk) [admin, owner]
GET /api/v1/hackathons/{id}/participants # List participants [admin, owner]
POST /api/v1/hackathons/{id}/join # Join hackathon [participant]
GET /api/v1/hackathons/{id}/submissions # List all submissions [admin, owner]
POST /api/v1/hackathons/{id}/finalize # Finalize rankings [admin, owner]

SUBMISSION ENDPOINTS:
POST /api/v1/submissions # Submit repo URL
GET /api/v1/submissions/{id} # Submission details + current status
GET /api/v1/submissions/{id}/status # SSE stream — evaluation progress events
DELETE /api/v1/submissions/{id} # Withdraw submission [owner, before evaluation]

EVALUATION ENDPOINTS:
GET /api/v1/evaluations/{submission_id} # Full evaluation report [owner or admin]
GET /api/v1/evaluations/{submission_id}/agents # Per-agent results [owner or admin]
POST /api/v1/evaluations/{submission_id}/retry # Retry failed evaluation [admin]

RANKING ENDPOINTS:
GET /api/v1/rankings/{hackathon_id} # Leaderboard (respects finalization gate)
GET /api/v1/rankings/{hackathon_id}/me # Caller's own ranking

COMPARISON ENDPOINTS:
GET /api/v1/compare/{hackathon_id}
Query params: submission_ids (comma-separated, max 3)
Returns: side-by-side comparison of up to 3 submissions
Response schema:
{
"submissions": [
{
"submission_id": "uuid",
"repo_name": "string",
"participant_name": "string",
"final_score": 87.3,
"scores_by_criterion": [
{ "criterion": "Code Quality", "score": 82.1, "weight": 0.4,
"top_evidence": ["finding 1", "finding 2"] }
],
"strengths": ["str"],
"weaknesses": ["str"],
"tech_stack": ["str"],
"rank": 1,
"percentile": 94.5
}
]
}

DASHBOARD ENDPOINTS:
GET /api/v1/dashboard/{hackathon_id} [admin]
Returns: hackathon_stats record
{
"total_submissions": 34,
"evaluations_completed": 28,
"evaluations_in_progress": 3,
"evaluations_queued": 3,
"evaluations_failed": 0,
"score_distribution": { "0-10": 0, ..., "80-90": 12, "90-100": 3 },
"tech_stack_frequency": { "React": 12, "FastAPI": 8 },
"avg_score": 71.4,
"top5_preview": [...]
}

GET /api/v1/dashboard/{hackathon_id}/stream [admin]
SSE stream: emits updated stats object every 15 seconds
Event format: { "event": "stats_update", "data": { ...dashboard object } }

CHAT ENDPOINTS:
POST /api/v1/chat/{submission_id}/sessions # Create or get chat session
POST /api/v1/chat/{submission_id}/messages # Send message, stream response (SSE)
GET /api/v1/chat/{submission_id}/history # Chat history for session

ADMIN UTILITY ENDPOINTS:
GET /api/v1/admin/hackathons # All hackathons with stats [admin]
GET /api/v1/admin/queue/status # ARQ queue job status [admin]
GET /api/v1/admin/model/status # current model queue status
GET /api/v1/health # Health check

MODEL STATUS ENDPOINT RESPONSE:
GET /api/v1/admin/model/status returns:
{
"ollama_reachable": true,
"inference_model": "qwen2.5-coder:7b",
"inference_model_loaded": true,
"embedding_model": "nomic-embed-text",
"embedding_model_loaded": false,
"lock_held_by": "eval:submission_uuid_here",
"queue_depth": 1,
"estimated_wait_seconds": 45
}

SSE EVENT FORMAT for /submissions/{id}/status:
{ "event": "progress", "data": {
"stage": "cloning|analyzing|agent_repo_understanding|agent_code_quality|
agent_innovation|agent_comparative|aggregating|
generating_report|embedding|model_loading|model_waiting",
"message": "Human readable status message",
"progress_pct": 0-100,
"timestamp": "iso8601",
"degraded": false
}}
{ "event": "agent_complete", "data": {
"agent_id": "code_quality",
"score": 78.3,
"abstained": false
}}
{ "event": "completed", "data": { "evaluation_id": "uuid", "final_score": 87.3,
"degraded": false }}
{ "event": "degraded", "data": { "message": "Some agents used fallback scoring.
Results may be less precise.", "affected_agents": ["innovation"] }}
{ "event": "error", "data": { "message": "Human-readable error", "stage": "cloning",
"recoverable": false }}

====================================================
SECTION 7: EVALUATION PIPELINE — DETAILED SPECIFICATION
====================================================

THE EVALUATION PIPELINE IS THE CORE OF EVALON. Build it with care.

STAGE 0: SUBMISSION VALIDATION

- Validate repo URL is a valid GitHub URL (regex + HTTP HEAD check for existence)
- Check: not already submitted to this hackathon by this user
- Check: hackathon is in 'active' status
- Validate: repo URL is a public repository (attempt unauthenticated GitHub API call)
- On success: create submission record (status=pending), dispatch ingestion job to ARQ queue
- Return immediately with submission ID and job_id

STAGE 1: REPOSITORY INGESTION (ARQ Job: ingest_repository)

- Set submission status = 'cloning'
- Emit SSE event: stage=cloning, message="Cloning your repository..."
- Clone to: /workspace/repos/{submission_id}/ using gitpython
- Enforce limits:
    - Max clone size: 50MB (configurable via hackathon settings)
    - Max file count: 5000
    - Max clone time: 120 seconds (timeout)
- Excluded: binary files over 1MB, node_modules/, .git/, venv/, **pycache**/, binary files > 1MB
- On failure: set status=failed, emit error SSE with human-readable message, stop pipeline
- On success: record clone_completed_at, emit progress SSE

STAGE 2: FILE PROCESSING

- Set submission status = 'analyzing'
- Generate file tree, detect languages
- Identify project type: detect primary framework from file patterns
  (package.json → Node.js, requirements.txt/setup.py → Python, pom.xml → Java,
  go.mod → Go, Cargo.toml → Rust, etc.)
- Extract dependency manifest: parse package.json dependencies, requirements.txt, etc.
- Parse README: extract content, check for: project description, setup instructions,
  demo links, architecture diagrams, badges
- README quality score: 0-100 based on presence of key sections
- Extract tech_stack list from dependencies and file patterns
  (e.g., ["React", "FastAPI", "PostgreSQL", "Docker"])
  Store in submissions.tech_stack column for dashboard aggregation

STAGE 3: STATIC ANALYSIS

- Run all applicable analyzers based on detected language/framework
- PYTHON PROJECTS: radon cc (cyclomatic complexity), radon mi (maintainability index),
  radon hal (Halstead metrics), semgrep with p/python rules
- JAVASCRIPT/TYPESCRIPT: ESLint via subprocess (install ESLint globally in container,
  use recommended ruleset + @typescript-eslint if TS detected)
- ALL PROJECTS: semgrep with p/default security rules (detect hardcoded secrets,
  SQL injection patterns, XSS patterns, insecure configs)
- FILE STRUCTURE ANALYSIS: check for: test directory presence, CI config files
  (.github/workflows, .gitlab-ci.yml), Dockerfile presence, environment example files,
  .gitignore quality, license file presence
- DOCUMENTATION COVERAGE: ratio of documented functions/classes (detect docstrings/JSDoc)
  to total functions/classes
- Assemble all results into StaticAnalysisReport (Pydantic model)
- Emit progress SSE

STAGE 4: AI EVALUATION — SEQUENTIAL LANGGRAPH EXECUTION

CRITICAL DESIGN DECISION — SEQUENTIAL NOT PARALLEL:
The LangGraph graph MUST execute agents SEQUENTIALLY, not in parallel.
Rationale: Parallel execution would require multiple concurrent LLM calls,
loading the inference model multiple times, causing OOM on consumer hardware.
Sequential execution is barely slower in practice because LLM inference is
the bottleneck in every branch anyway. The previous parallel design was
theoretically faster but practically broken on real hardware.

GRAPH STATE (TypedDict):

```python
class EvaluationState(TypedDict):
    submission_id: str
    hackathon_id: str
    repo_context: RepoContext          # Built from stages 2+3
    agent_results: Dict[str, AgentResult]
    errors: List[str]
    completed_agents: List[str]
    model_lock_acquired: bool
    pipeline_start_time: float         # for timeout enforcement
```

GRAPH NODES (SEQUENTIAL ORDER):

1. build_context_node: Assembles final RepoContext from DB and file system
2. acquire_model_lock_node: acquires ModelQueueManager lock
3. repo_understanding_node: Runs Repository Understanding Agent
4. code_quality_node: Runs Code Quality Agent
5. innovation_node: Runs Innovation Agent
6. release_model_lock_node : releases lock before embedding
7. aggregate_node: Calls scoring aggregator with all agent results
8. generate_report_node: Calls report generator
9. comparative_node : runs AFTER lock released (no LLM needed)
10. save_results_node: Persists all results to DB
11. cleanup_node: Removes cloned repo from filesystem

GRAPH EDGES (STRICTLY SEQUENTIAL):
START → build_context_node
build_context_node → acquire_model_lock_node
acquire_model_lock_node → repo_understanding_node
repo_understanding_node → code_quality_node
code_quality_node → innovation_node
innovation_node → release_model_lock_node
release_model_lock_node → aggregate_node
aggregate_node → generate_report_node
generate_report_node → comparative_node
comparative_node → save_results_node
save_results_node → cleanup_node
cleanup_node → END

acquire_model_lock_node BEHAVIOR:

- Calls ModelQueueManager.acquire_inference_lock(priority=P0)
- Emits SSE: stage=model_loading, message="Loading AI models..."
- If lock acquired: sets model_lock_acquired=True, continues
- If timeout waiting for lock: sets all agents to abstained with ModelUnavailableError
  reason, skips to aggregate_node with static-analysis-only scoring
  Emits SSE: stage=model_waiting,
  message="AI model busy with another evaluation. Using static analysis only."

release_model_lock_node BEHAVIOR:

- Calls ModelQueueManager.release_inference_lock()
- Emits SSE: progress update
- ALWAYS runs even if a previous node failed (conditional edge)

RESILIENCE RULES FOR EACH AGENT NODE:
Each agent node MUST implement this pattern:

```python
async def agent_node(state: EvaluationState) -> EvaluationState:
    try:
        result = await agent.safe_evaluate(state["repo_context"])
        state["agent_results"][agent.agent_id] = result
        state["completed_agents"].append(agent.agent_id)
        # Emit SSE: agent_complete event
    except ModelUnavailableError as e:
        result = AgentResult.abstained(
            agent_id=agent.agent_id,
            reason=f"Model unavailable: {str(e)}. Score from static analysis only.",
            fallback_used=True
        )
        state["agent_results"][agent.agent_id] = result
        # Emit SSE: degraded warning
    except asyncio.TimeoutError:
        result = AgentResult.abstained(
            agent_id=agent.agent_id,
            reason="Agent timed out after 90 seconds. Score from static analysis only.",
            fallback_used=True
        )
        state["agent_results"][agent.agent_id] = result
        # Emit SSE: degraded warning
    except Exception as e:
        logger.error(f"Agent {agent.agent_id} failed: {e}", exc_info=True)
        result = AgentResult.abstained(
            agent_id=agent.agent_id,
            reason="Evaluation agent encountered an error. Score from static analysis only.",
            fallback_used=True
        )
        state["agent_results"][agent.agent_id] = result
        state["errors"].append(str(e))
    return state
```

NO EXCEPTION MUST EVER PROPAGATE OUT OF AN AGENT NODE.

STAGE 5: SCORE AGGREGATION

- For each criterion: find agent_result, apply confidence weighting
- If agent abstained/fallback_used: compute score purely from StaticAnalysisReport
  using deterministic formula (no LLM). Document this formula explicitly.
  Static-only code quality score = f(complexity, docs, structure, semgrep)
- final_score = Σ (criterion_weight × effective_criterion_score)
- Store raw scores, weighted scores, and confidence values separately in evaluation record
- If ANY agent used fallback: set evaluation.status = 'degraded'
  (not 'failed' — degraded means partial results, not no results)
- If ALL agents abstained: set evaluation.status = 'failed' with clear message

STAGE 6: REPORT GENERATION
The report generator assembles a structured JSON report from agent results.
Report includes 'degraded' field and explanation when applicable.
Report structure:

```json
{
    "summary": "Two-sentence high-level assessment",
    "degraded": false,
    "degraded_explanation": null,
    "overall_assessment": "Three paragraphs of narrative assessment",
    "tech_stack": ["detected", "technologies"],
    "project_type": "Web Application | CLI Tool | API | ML Project | ...",
    "scores": {
        "overall": 87.3,
        "by_criterion": [
            { "criterion": "Code Quality", "score": 82.1, "weight": 0.3 }
        ]
    },
    "strengths": ["Specific strength 1", "Specific strength 2"],
    "weaknesses": ["Specific weakness 1", "Specific weakness 2"],
    "recommendations": [
        {
            "priority": "high|medium|low",
            "recommendation": "...",
            "rationale": "..."
        }
    ],
    "architecture_notes": "Paragraph about detected architecture",
    "agent_results": [
        /* Per-agent detailed results */
    ],
    "generated_at": "iso8601",
    "model_versions": {}
}
```

STAGE 7: EMBEDDING GENERATION (Separate ARQ Job: generate_embeddings)

- Acquires ModelQueueManager.acquire_embedding_lock()
- Inference model is UNLOADED before embedding model is loaded
- Generates embeddings, stores in repo_embeddings
- Releases embedding lock
- If lock timeout: log warning, skip embeddings, chatbot will be unavailable
  (not a crash — just a feature gracefully unavailable)
- Updates hackathon_stats table after completion

STAGE 8: RANKING UPDATE + STATS UPDATE

- After each evaluation completes, recompute rankings for the hackathon
- Recompute hackathon_stats:
    - Aggregate score_distribution histogram
    - Aggregate tech_stack_frequency from submissions.tech_stack
    - Compute avg_score, top5_preview
    - Update hackathon_stats.updated_at
- Rankings are computed but NOT finalized (finalized=false)
- Admins see live rankings; participants do NOT see rankings until admin finalizes
  (controlled by hackathon.settings.show_rankings_before_finalization)
- Normalization: for each submission pool in a hackathon, compute percentile rank
  based on final_score (percentile = submissions_below / total_submissions × 100)
- Emit SSE on dashboard stream channel: `evalon:dashboard:{hackathon_id}`

====================================================
SECTION 8: AI AGENT SPECIFICATIONS
====================================================

AGENT INTERFACE (BaseEvaluator):

```python
class AgentResult(BaseModel):
    agent_id: str
    score_raw: float         # 0-100
    confidence: float        # 0-1
    evidence: List[EvidenceItem]
    top_evidence: List[str]  # Top 2 evidence strings for tooltip display
    strengths: List[str]
    weaknesses: List[str]
    reasoning: str
    abstained: bool = False
    abstain_reason: Optional[str] = None
    fallback_used: bool = False

    @classmethod
    def abstained(cls, agent_id: str, reason: str,
                  fallback_used: bool = False) -> "AgentResult":
        return cls(
            agent_id=agent_id,
            score_raw=50.0,
            confidence=0.0,
            evidence=[],
            top_evidence=[],
            strengths=[],
            weaknesses=[],
            reasoning="",
            abstained=True,
            abstain_reason=reason,
            fallback_used=fallback_used
        )
```

All agents use the SAME model: qwen2.5-coder:7b
All agents have a hard timeout of 90 seconds
All agents use the ModelQueueManager lock (acquired once at pipeline level)

AGENT 1: Repository Understanding Agent (agent_id: "repo_understanding")
Purpose: Understand what the project IS before other agents evaluate it.
Input: README content, file tree, language breakdown, dependency manifest
Task: Extract structured project understanding
Output must include:

- project_goals: What problem does this solve?
- target_audience: Who is this for?
- technical_approach: How does it solve the problem?
- architecture_pattern: Detected architectural pattern (MVC, microservices, etc.)
- key_technologies: Primary tech choices and their purpose
- demo_maturity: Is this demo-ready, prototype, or production-quality?
- score_raw: 0-100 on clarity of project vision and technical coherence
- evidence: Specific observations from README and file structure

Prompt Engineering Notes:

- Use structured output (JSON mode)
- Provide explicit schema in prompt
- Include anti-hallucination instruction: "Only describe what you can directly
  observe in the provided files. Do not invent features or capabilities."
- Few-shot: provide one example of a good project understanding extraction
  Key addition: extract top_evidence = first 2 evidence items in plain English strings
  for tooltip rendering.

AGENT 2: Code Quality Agent (agent_id: "code_quality")
Purpose: Evaluate engineering quality of the codebase.
Input: Static analysis results (radon/ESLint/Semgrep output), 3-5 representative
code file samples (largest files by significance, non-binary), file structure assessment
Task: Interpret static analysis metrics and code samples into quality assessment
Evidence-grounded scoring formula (AI MUST follow this):

- Code complexity (radon/ESLint): contributes 30%
    - Cyclomatic complexity distribution, deep nesting, long functions
- Modularity indicators: contributes 25%
    - File organization, separation of concerns, function size distribution
- Documentation coverage: contributes 20%
    - Docstring/JSDoc ratio, README quality score
- Error handling patterns: contributes 15%
    - Try/catch presence, error propagation, graceful failures
- Anti-pattern detection (Semgrep): contributes 10%
    - Security smells, code smells, deprecated patterns
      AI role: Interpret these metrics into human language, find patterns,
      provide specific code improvement suggestions with file references.
      STRICTLY: Do not invent findings not present in the provided static analysis output.
      Key addition: top_evidence = the 2 highest-impact specific findings
      Example: ["12 functions exceed complexity threshold of 10",
      "0% docstring coverage in core modules"]

AGENT 3: Innovation Agent (agent_id: "innovation")
Purpose: Evaluate originality, problem-solving sophistication, and creative use of technology.
Input: Project understanding (from repo_understanding agent output), tech stack,
project description, hackathon problem statement (if provided)
Task: Evaluate novelty and sophistication
Evaluation dimensions:

- Problem originality (25%): Is the problem interesting and underserved?
- Solution creativity (30%): Is the approach creative or formulaic?
- Technical sophistication (25%): Advanced techniques, non-trivial implementations?
- Execution quality (20%): Does the project feel complete and polished?
  This is the most subjective agent. Prompt must include:
- Clear rubric definition per dimension
- Instruction to cite specific technical observations from project understanding
- Calibration anchor: "A score of 50 represents a competent but unremarkable
  CRUD application. 70+ requires genuine technical creativity. 90+ requires
  a novel approach that a senior engineer would find impressive."
  Key addition: top_evidence = 2 most specific observations
  Example: ["Novel use of prompt injection as adversarial detection",
  "AI agent fingerprinting is an underexplored problem space"]

AGENT 4: Comparative Agent (agent_id: "comparative") — PARTIAL IMPLEMENTATION
Implement the following real functionality.
This agent runs AFTER the model lock is released (no LLM calls needed).
It uses only database queries and arithmetic.

```python
class ComparativeAgent:
    agent_id = "comparative"
    agent_name = "Comparative Intelligence Agent"

    async def evaluate(
        self,
        repo_context: RepoContext,
        submission_id: str,
        hackathon_id: str,
        db: AsyncSession
    ) -> ComparativeResult:
        """
        Computes comparative intelligence from existing DB data.
        No LLM calls. Pure analytics.
        """
        # 1. Fetch all completed evaluations for this hackathon
        # 2. Compute pool statistics

        return ComparativeResult(
            agent_id="comparative",
            total_submissions_in_pool=47,
            this_submission_score=81.3,
            pool_average_score=68.2,
            pool_median_score=71.0,
            percentile=77.0,
            percentile_label="Top 23%",
            rank_in_pool=11,
            score_vs_average="+13.1 above average",

            # Tech stack comparison
            shared_tech_stacks=[
                { "tech": "React", "count": 4,
                  "message": "4 other teams also used React" },
                { "tech": "FastAPI", "count": 6,
                  "message": "6 other teams also used FastAPI" }
            ],
            unique_tech_stacks=[
                { "tech": "LangGraph",
                  "message": "Only your team used LangGraph — differentiator" }
            ],

            # Criterion-level comparison
            criterion_comparisons=[
                {
                    "criterion": "Code Quality",
                    "your_score": 78.3,
                    "pool_average": 65.1,
                    "percentile": 81.0,
                    "label": "Top 19% in Code Quality"
                }
            ],

            # Contextual insight (template-generated, no LLM)
            summary=self._generate_summary(rank, total, percentile),

            # Whether we have enough data for meaningful comparison
            sufficient_data=total_submissions >= 3,
            data_note="Based on 47 submissions evaluated so far"
        )

    def _generate_summary(self, rank: int, total: int, percentile: float) -> str:
        """
        Generates a human-readable summary using templates.
        No LLM. Template-based only.
        """
        if percentile >= 90:
            tier = "top performer"
        elif percentile >= 75:
            tier = "strong performer"
        elif percentile >= 50:
            tier = "above-average performer"
        elif percentile >= 25:
            tier = "below-average performer"
        else:
            tier = "developing submission"

        return (
            f"Your project ranks #{rank} out of {total} submissions "
            f"(Top {100 - percentile:.0f}%), placing you as a {tier} "
            f"in this hackathon."
        )
```

Store ComparativeResult in evaluations.report under "comparative" key.
Display on participant evaluation page as a dedicated "How You Compare" section.
If sufficient_data=False: show message "Comparative analysis will be available
once more submissions are evaluated." — no crash, no error.

LLM PROVIDER ABSTRACTION (LLMProvider — updated for queue integration):

```python
class LLMProvider:
    def __init__(self, model_queue: ModelQueueManager):
        self.model_queue = model_queue
        self.model = ModelQueueManager.INFERENCE_MODEL

    async def generate(
        self,
        prompt: str,
        system: str,
        json_mode: bool = True,
        timeout: int = 90
    ) -> str:
        """
        Assumes model lock is already held by caller.
        Does NOT acquire lock here — lock is acquired at pipeline level.
        Raises asyncio.TimeoutError if inference takes > timeout seconds.
        Raises ModelUnavailableError if Ollama is unreachable.
        NEVER raises any other exception — catch and re-raise as ModelUnavailableError.
        """

    async def embed(self, text: str) -> List[float]:
        """
        Assumes embedding lock is already held by caller.
        Uses EMBEDDING_MODEL only.
        """

    async def health_check(self) -> dict:
        """Returns model queue status dict."""
```

====================================================
SECTION 9: AI MENTOR CHATBOT — SPECIFICATION
====================================================

The EVALON mentor chatbot must be MODEL-QUEUE AWARE.
The mentor chatbot allows participants to have a conversation about their
evaluation, ask questions about their code, and receive improvement guidance.

CHATBOT MODEL HANDLING:

- Each chat message request acquires ModelQueueManager.acquire_inference_lock(priority=P3)
- P3 = lowest priority — chatbot yields to active evaluations
- If lock cannot be acquired within 30 seconds:
  Return HTTP 202 with body:
  { "status": "queued", "message": "The AI mentor is currently evaluating
  another submission. Your message will be processed in approximately
  30-60 seconds. Please wait.", "retry_after": 30 }
  Frontend polls /api/v1/chat/{session_id}/pending to check if response is ready
  Do NOT timeout the SSE connection — show "Mentor is thinking..." spinner

CHATBOT AVAILABILITY CHECK:
Before allowing a participant to open the mentor:

1. Check if evaluation is complete (submission.status == 'completed')
2. Check if embeddings are generated (at least one repo_embedding exists)
3. If embeddings not yet ready: show "Your mentor is being prepared.
   Check back in a few minutes." — NOT an error
4. If evaluation is degraded: show "Your mentor has limited context due to
   a partial evaluation. It can still help you." — mentor still works

CONTEXT ASSEMBLY (for each user message):

1. Retrieve participant's chat session (or create new one)
2. Retrieve top-5 most relevant embedding chunks from repo_embeddings
   for this submission, ranked by cosine similarity to the user's message
3. Assemble system prompt:

    ```
    You are an expert software engineering mentor. You are reviewing the
    hackathon submission of {participant_name}.

    THEIR PROJECT:
    {repo_summary_chunk}

    THEIR EVALUATION REPORT:
    {evaluation_report_chunk}

    RELEVANT CONTEXT:
    {retrieved_chunks}

    Your role is to:
    - Help them understand why they received specific scores
    - Teach them engineering best practices relevant to their code
    - Suggest concrete improvements with examples
    - Be encouraging and educational, not discouraging
    - Only reference what you can see in the provided context

    Do NOT make up information about their code that isn't in the context.
    ```

4. Include last 10 chat messages as conversation history
5. Stream response via SSE (token-by-token)
6. Acquire embedding lock to check retrieval (nomic-embed-text is tiny, fast)
   Actually: retrieval from pgvector does NOT require model — it uses stored vectors
   Only embedding of the USER'S QUERY needs the embedding model
7. Embed the user's query (requires embedding lock — brief, ~200ms)
8. Release embedding lock
9. Retrieve top-5 chunks by cosine similarity (no model needed)
10. Acquire inference lock (P3)
11. Stream response using qwen2.5-coder:7b
12. Release inference lock
13. Store response

CHATBOT RESPONSE STREAMING:

- SSE format: `data: {"token": "...", "done": false}`
- Final event: `data: {"token": "", "done": true, "message_id": "uuid"}`
- Store complete response in chat_messages after streaming completes

====================================================
SECTION 10: FRONTEND SPECIFICATION
====================================================

DESIGN SYSTEM:

- Color palette: dark background (#0a0a0a), cards (#111111, #1a1a1a)
- Accent: electric blue (#3b82f6)
- Degraded state: amber (#f59e0b) — used when evaluation is partial
- Error state: red (#ef4444) — used for hard failures only
- Typography: Inter for UI, JetBrains Mono for code blocks
- The EVALON wordmark appears top-left on all authenticated layouts.

GRACEFUL UI DEGRADATION DESIGN SYSTEM:
Define these reusable UI states used throughout:

- <DegradedBanner>: amber banner shown when evaluation.degraded=true
  "Some AI agents used fallback scoring. Results are based primarily on
  static analysis and may be less nuanced. Full AI evaluation was not
  possible at this time."
- <AgentAbstainedBadge>: shown per agent card when abstained=true
  "This agent used static analysis only"
- <ModelLoadingState>: shown in SSE progress when stage=model_waiting
  "AI is finishing another evaluation. You're next in queue..."
- <MentorUnavailableState>: shown when embeddings not ready
  "Your mentor is being prepared. Check back soon."
- NO raw error codes or stack traces should EVER appear in the UI.
  Every failure state has a human-readable, encouraging message.

===== KEY PAGES =====

PAGE: Landing (/)

- Hero: "EVALON — AI-Powered Hackathon Evaluation"
- Feature highlights (AI evaluation, explainable scoring, mentor chatbot)
- CTA: Create Hackathon (admin) / Join Hackathon (participant)

PAGE: Admin — Live Hackathon Dashboard (/admin/dashboard) — NEW
This is the mission control view during a live hackathon.
Layout: Full-width, auto-refreshing, dark theme

TOP ROW — stat cards (large numbers, icon, label):
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Submissions │ Completed │ In Progress │ Queued │ Failed │
│ 34 │ 28 │ 3 │ 3 │ 0 │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘

MIDDLE ROW — two columns:
Left: Score Distribution Histogram (Recharts BarChart)
X-axis: score ranges (0-10, 10-20, ..., 90-100)
Y-axis: number of submissions
Shows where the field clusters

Right: Top Tech Stacks (horizontal bar chart)
"React (12)" ████████████
"Python (22)" ████████████████████████
"FastAPI (8)" ████████
Sorted by frequency

BOTTOM ROW — two columns:
Left: Top 5 Leaderboard Preview
Rank | Project Name (masked) | Score
Updates live as evaluations complete

Right: Model Queue Status
Current model: qwen2.5-coder:7b ● Loaded
Queue depth: 2 evaluations pending
Estimated completion: ~4 min

LIVE UPDATES: Uses SSE connection to /api/v1/dashboard/{id}/stream
Refreshes entire stat block every 15 seconds
No page reload needed

PAGE: Admin — Hackathon Creation (/admin/hackathons/new)

- Form: title, description, dates, max submissions
- Criteria builder: add/remove criteria, set name, description, weight
- Real-time weight sum validation (must equal 1.0, shown as progress bar)
- Agent mapping: for each criterion, optionally map to a specific evaluator agent
- Settings: show rankings before finalization toggle, max repo size

PAGE: Admin — Hackathon Overview Side-by-Side Comparison (/admin/hackathons/[id]/compare)
This is what makes EVALON feel like a real judging platform.

- Status badge with transition buttons (Draft → Active → Evaluating → Finalized)
- Summary stats: total submissions, evaluations in progress, completed, failed
- Submission table with: repo URL, participant name, status indicator, score (if complete)
- "View Report" link per submission
- "Finalize Rankings" button (only when all evaluations complete)
- Real-time status updates via polling or WebSocket

PAGE: Admin — Ranking View (/admin/hackathons/[id]/rankings)

- Ranked table with: rank, participant name, repo name, score, percentile
- Score breakdown columns per criterion
- Export as CSV button

PAGE: Participant — Hackathon List (/participant/hackathons)

- Cards for all active hackathons
- Joined badge for enrolled hackathons
- Submit/View Status button

PAGE: Participant — Submit (/participant/submit/[hackathonId])

- GitHub URL input with real-time validation
- Repository preview (name, description, language fetched via GitHub API on client)
- Submission confirmation

Layout: Horizontal columns, 2-3 submissions side by side
Left sidebar: Submission selector (checkbox list, max 3)
Main area: Comparison grid

Each column contains:

```
  ┌─────────────────────────────┐
  │ [Repo Name]   Rank #2       │
  │ Score: 84.2   Top 8%        │
  │                             │
  │ SCORES BY CRITERION         │
  │ Code Quality    82.1  ████  │
  │ Innovation      91.3  █████ │
  │ Understanding   79.0  ████  │
  │                             │
  │ TECH STACK                  │
  │ React, FastAPI, PostgreSQL  │
  │                             │
  │ TOP STRENGTHS               │
  │ • Clean modular structure   │
  │ • Novel AI integration      │
  │                             │
  │ TOP WEAKNESSES              │
  │ • No test coverage          │
  │ • Missing error handling    │
  └─────────────────────────────┘
```

Differences are highlighted: if Submission A has a strength that
Submission B lists as a weakness, highlight both cells in contrasting colors.
Export comparison as PDF button at top.

PAGE: Admin — Ranking View (/admin/hackathons/[id]/rankings)
(Unchanged, add Compare button to select rows)

PAGE: Participant — Evaluation (/participant/evaluation/[submissionId])
THIS IS THE MOST IMPORTANT PAGE. Build it with maximum care.

Layout:
TOP SECTION: - Overall score: large (72px), prominent, centered - Status badge: Completed / Degraded (amber) / In Progress - If degraded: <DegradedBanner> component

SCORE RADAR CHART — MANDATORY, MOST VISUALLY IMPRESSIVE ELEMENT:
Implement using Recharts RadarChart showing per-criterion scores

```tsx
<RadarChart cx={300} cy={250} outerRadius={150} data={criteriaData}>
    <PolarGrid stroke="#333" />
    <PolarAngleAxis
        dataKey="criterion"
        tick={{ fill: "#9ca3af", fontSize: 12 }}
    />
    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#666" }} />
    <Radar
        name="Your Score"
        dataKey="score"
        stroke="#3b82f6"
        fill="#3b82f6"
        fillOpacity={0.25}
        strokeWidth={2}
    />
    <Radar
        name="Hackathon Average"
        dataKey="average"
        stroke="#f59e0b"
        fill="#f59e0b"
        fillOpacity={0.1}
        strokeWidth={1}
        strokeDasharray="4 4"
    />
    <Legend />
    <Tooltip content={<ScoreTooltip />} />
</RadarChart>
```

    IMPORTANT: Include TWO radar overlays:
    1. Participant's scores (blue, filled)
    2. Hackathon pool average per criterion (amber dashed, light fill)
    This makes comparison immediately visual. Participants see exactly where
    they are above or below average at a glance.

"WHY THIS SCORE?" TOOLTIPS — NEW:
Implement ScoreTooltip component used on: - Each axis label in the radar chart - Each criterion row in the score table
On hover/click, shows a popover containing:

```
┌─────────────────────────────────────┐
│  Code Quality: 78.3 / 100           │
│                                     │
│  Top findings that drove this score:│
│  • 12 functions exceed complexity   │
│    threshold (cyclomatic > 10)      │
│  • 0% docstring coverage in core   │
│    modules                          │
│                                     │
│  [View Full Analysis →]             │
└─────────────────────────────────────┘
```

    Data source: agent_results.top_evidence (top 2 items)
    Use shadcn/ui Popover component
    Renders on both desktop (hover) and mobile (tap)
    This is the single most important explainability UX feature.
    Judges see immediately that scores are evidence-backed.

HOW YOU COMPARE SECTION (from Comparative Agent) — NEW:
Shown below the radar chart.
Cards layout:

```
    ┌──────────────┬──────────────┬──────────────┐
    │ Your Rank    │  Percentile  │ vs Average   │
    │    #11       │   Top 23%    │  +13.1 pts   │
    │  of 47 subs  │              │  above avg   │
    └──────────────┴──────────────┴──────────────┘
```

    Below: Tech stack comparison
    "4 other teams used React" | "Only you used LangGraph ⭐"

    If sufficient_data=False: soft gray card "Comparative data will be
    available once more teams complete evaluation."

PROGRESS STREAM (visible during evaluation):
Animated timeline of stages
After completion: collapses to summary "Evaluated in 2m 34s"

REPORT TABS:
Overview | Code Quality | Innovation | Architecture | Recommendations

    Each tab: agent result card with:
    - Score badge (colored by score range)
    - Evidence list with impact badges
    - Strengths/weaknesses
    - Full AI reasoning (collapsed by default, expandable)
    - If abstained: <AgentAbstainedBadge>

PDF EXPORT BUTTON:
Positioned top-right of the report section.
Label: "Download Report (PDF)"
Icon: Download
Implementation:

```tsx
const handleExportPDF = () => {
    // Add print class to body to trigger print stylesheet
    document.body.classList.add("printing-report");
    window.print();
    document.body.classList.remove("printing-report");
};
```

    Print stylesheet (globals.css @media print):
    - Hide: navbar, sidebar, chat button, progress stream, browser chrome
    - Show: all report content expanded (no collapsed sections)
    - Add: EVALON header with logo, submission metadata, timestamp footer
    - Page breaks: before each agent section
    - Colors: invert to light background for print readability
    - Radar chart: ensure it renders in print (use Recharts' static rendering)
    Alternative server-side: GET /api/v1/evaluations/{id}/export returns
    a weasyprint-generated PDF with same content.
    Offer both: "Download PDF" (server-side, reliable) and
    "Print Report" (client-side, instant)

PAGE: Participant — Leaderboard (/participant/leaderboard/[hackathonId])

- Visible only after admin finalizes OR if hackathon setting allows early view
- Ranked table with: rank, project name (NOT participant name until finalized), score
- Highlight current user's row
- Percentile badge ("Top 15%")

PAGE: Participant — Mentor Chatbot (/participant/mentor/[submissionId])
Left panel: condensed evaluation summary + comparative rank card
Right panel: chat interface with model queue status indicator
If model is busy: show amber indicator "AI is finishing another evaluation..."
Suggested questions include comparative questions:
"Why am I ranked #11 and not higher?"
"What did teams above me do differently?"

===== COMPONENT SPECIFICATIONS =====

ScoreRadarChart.tsx:

- Two overlays: participant score + pool average (dashed)
- Clickable axes → trigger ScoreTooltip popover
- Responsive: full width on mobile, 600px max on desktop
- Animates in on mount (Recharts animation)

ScoreTooltip.tsx:

- shadcn/ui Popover
- Triggered by hover (desktop) and click (all)
- Shows criterion name, score, top 2 evidence items
- Link to full agent section

LiveDashboard.tsx:

- SSE connection to dashboard stream
- Auto-reconnects on disconnect
- Stat cards animate when values change (number flip)
- Histogram updates smoothly (no flash)
- Model status indicator with pulsing dot (green=idle, blue=active, amber=queued)

ComparisonView.tsx:

- Horizontal scroll on mobile
- Column headers are sticky
- Difference highlighting: green cell = strength not shared by others,
  red cell = weakness shared by majority
- Export button uses same print stylesheet approach

PrintableReport.tsx:

- Hidden in normal view (display:none except @media print)
- Contains full expanded report content optimized for A4 print
- EVALON watermark in footer
- Page numbers

====================================================
SECTION 11: ASYNC JOB SYSTEM SPECIFICATION
====================================================

ARQ WORKER CONFIGURATION:

```python
WorkerSettings = {
    "functions": [
        ingest_repository,
        run_evaluation_pipeline,
        generate_embeddings,
        recompute_rankings,
        update_hackathon_stats
    ],
    "redis_settings": RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT),
    "max_jobs": 3,       # prevents simultaneous model loads
    "job_timeout": 900,
    "keep_result": 3600,
    "health_check_interval": 30,
    "retry_jobs": True,
    "max_tries": 3
}
```

IMPORTANT: max_jobs is reduced to 3.
This means at most 3 jobs run concurrently across all workers.
Combined with the ModelQueueManager lock, only 1 job uses the LLM at a time.
The other 2 slots handle non-LLM work (cloning, static analysis, DB writes).

NEW JOB: update_hackathon_stats

- Triggered after: each evaluation completion, each new submission
- Recomputes hackathon_stats table
- Emits dashboard SSE event

JOB DEPENDENCIES:

1. ingest_repository → run_evaluation_pipeline
2. run_evaluation_pipeline → generate_embeddings → recompute_rankings
   → update_hackathon_stats
3. Each new submission → update_hackathon_stats (increment queued count)

SSE ARCHITECTURE:

- Evaluation progress: `evalon:progress:{submission_id}` channel
- Dashboard stream: `evalon:dashboard:{hackathon_id}` channel
- Both stored as Redis lists with 2h TTL for late-connecting clients

====================================================
SECTION 12: DOCUMENTATION REQUIREMENTS
====================================================

You MUST produce ALL of the following documentation files.
These are not optional. These must be complete and professional.

README.md — The public-facing project introduction:

- Project overview and value proposition
- Screenshots section (describe what screenshots should show)
- Feature list
- Tech stack table
- Quick start (Docker Compose)
- Environment variable reference
- Contributing guidelines
- License

SETUP.md — Complete setup guide:

- Prerequisites (Docker, Docker Compose, minimum hardware)
- Step-by-step setup instructions
- Ollama model download instructions
- Environment configuration
- Database initialization
- First admin account creation
- Running demo hackathon (step-by-step script)
- Troubleshooting section

SETUP.md must include:

- Minimum hardware requirements:
    - 16GB RAM minimum (8GB for system + 8GB for models)
    - 24GB RAM recommended (smooth chatbot + evaluation concurrence)
    - Apple Silicon M-series: fully supported (GPU acceleration via Metal)
    - NVIDIA GPU: supported (uncomment GPU section in docker-compose.yml)
    - CPU-only: supported but slow (~5-10 min per evaluation)
- Expected first-evaluation experience:
  "The first evaluation takes longer because models must download and load
  (typically 2-5 minutes for model load on first run). Subsequent
  evaluations are faster. Model downloads are one-time."
- How to monitor model queue: `make model-status`

ARCHITECTURE.md — Technical architecture document:

- System overview diagram (Mermaid)
- Component interaction diagram (Mermaid)
- Evaluation pipeline flow diagram (Mermaid)
- Database schema diagram (Mermaid ER)
- Technology choice justifications
- Key design patterns used
- Data flow narrative

RESEARCH.md — Engineering research document:

- Framework comparison: FastAPI vs NestJS vs Django for this use case
- Database comparison: PostgreSQL vs MongoDB for evaluation data
- Queue comparison: ARQ vs Celery vs RQ for async evaluation jobs
- AI orchestration: LangGraph vs CrewAI vs custom pipeline
- LLM runtime: Ollama vs vLLM vs API-only for local evaluation
- Vector storage: pgvector vs Qdrant vs Chroma for embedding retrieval
- Static analysis tool evaluation
- Conclusion for each decision

ARCHITECTURE DECISION RECORDS (docs/decisions/):
Write proper ADRs for each key decision:

- ADR-001: Backend framework choice (FastAPI)
- ADR-002: Database choice (PostgreSQL + pgvector)
- ADR-003: AI orchestration approach (LangGraph)
- ADR-004: Queue system (ARQ + Redis)
- ADR-005: Evaluation strategy (static-analysis-grounded AI)
  ADR format: Status | Context | Decision | Consequences

FUTURE_SCOPE.md:

- Comparative Intelligence Agent: full design
- Private repository support: OAuth flow design
- UI/UX Agent: implementation approach
- Security Agent: full Trivy + Semgrep integration design
- Multi-tenant SaaS: architecture changes needed
- Kubernetes deployment: resource requirements and configuration
- API for external hackathon platforms
- Billing system design

DEBUGGING_GUIDE.md:

- Common failure modes and their logs
- How to inspect ARQ job status
- How to read evaluation pipeline logs
- How to test a single agent in isolation
- How to add a new evaluator agent
- How to verify Ollama is running correctly
- Database debugging queries

DEBUGGING_GUIDE.md must include:

- How to check which model is currently loaded: `make model-status`
- How to manually unload a model: instructions for Ollama API keep_alive:0
- How to diagnose OOM: checking Docker stats, Ollama logs
- What "degraded evaluation" means and how to recover (retry endpoint)
- How to force-release a stuck model lock: Redis key deletion procedure

IMPLEMENTATION REPORTS (docs/reports/PHASE-N-REPORT.md):
After each development phase, write a phase report including:

- What was built
- Architectural decisions made
- Deviations from plan and why
- Known issues / technical debt introduced
- Testing results
- What to build next

ADR-006-model-resource-management.md:
Status: Accepted
Context: Consumer hardware (Apple Silicon, 16-24GB unified memory) cannot
load multiple large LLMs simultaneously. Parallel agent execution causes
OOM failures.
Decision: Implement ModelQueueManager with Redis distributed lock.
Use exactly 2 models (inference + embedding). Sequential agent execution.
Lazy model loading. Hard memory limits on Ollama Docker service.

Consequences:

- Reliable on consumer hardware
- Predictable memory usage
- No OOM crashes

* First evaluation is slower (model load ~30-60s)
* Chatbot queues behind evaluations

====================================================
SECTION 13: TESTING REQUIREMENTS
====================================================

Write tests at these levels:

UNIT TESTS (test_agents/, test_scoring/):

- Test each agent's output parsing and validation
- Test score aggregation with various weight configurations
- Test normalization logic with edge cases (empty pool, tied scores, abstained agents)
- Test README quality scorer
- Test file processor language detection

INTEGRATION TESTS (test_pipeline/):

- Test full pipeline with a mock repository (create synthetic test repo fixture)
- Test SSE event sequence completeness
- Test job queue dispatch and pickup
- Test failure recovery: what happens when an agent throws

API TESTS (test_api/):

- Test authentication flow end-to-end
- Test submission creation and status polling
- Test evaluation report retrieval access control
- Test ranking finalization gate
- Test chatbot session creation and message

Use pytest with pytest-asyncio. Use factory-boy for model factories.
Use httpx AsyncClient for API tests. Mock Ollama calls in unit tests.

UNIT TESTS — ModelQueueManager:

- Test lock acquisition and release
- Test priority ordering (P0 before P3)
- Test lock timeout behavior → ModelUnavailableError
- Test model switch (inference → embedding → inference)
- Test concurrent lock requests (simulate 3 evaluation requests)

UNIT TESTS — Graceful Degradation:

- Test pipeline continues when one agent throws exception
- Test pipeline continues when model lock times out
- Test static-analysis-only scoring produces valid score
- Test 'degraded' status is set correctly
- Test all agents abstained → 'failed' status (not crash)

UNIT TESTS — Comparative Agent:

- Test percentile calculation with various pool sizes
- Test sufficient_data=False when pool < 3 submissions
- Test tech_stack comparison logic
- Test summary template generation across all tiers

INTEGRATION TESTS — Full Pipeline with Model Queue:

- Test that two simultaneous pipeline requests do not load model twice
- Test that chatbot request queues behind active evaluation
- Test embedding job acquires lock after inference lock released

====================================================
SECTION 14: GIT WORKFLOW REQUIREMENTS
====================================================

Repository name: evalon

Initialize a git repository at project root on first run.

Commit after completing each major logical unit. Commit message format:

```
type(scope): short description

Longer explanation if needed.
```

Types: feat, fix, docs, test, refactor, style, chore
Scopes: backend, frontend, pipeline, agents, scoring, chatbot, infra, docs

REQUIRED COMMIT MILESTONES:

1.  `chore(infra): initialize evalon project structure and docker compose`
2.  `feat(backend): database schema and alembic migrations`
3.  `feat(backend): authentication system with JWT`
4.  `feat(backend): hackathon and submission management API`
5.  `feat(core): ModelQueueManager with Redis distributed lock`
6.  `feat(pipeline): repository ingestion and file processing`
7.  `feat(pipeline): static analysis integration`
8.  `feat(agents): sequential LangGraph evaluation graph`
9.  `feat(agents): repository understanding agent`
10. `feat(agents): code quality agent with static analysis grounding`
11. `feat(agents): innovation agent`
12. `feat(agents): comparative agent — partial analytics implementation`
13. `feat(scoring): aggregation engine with graceful degradation`
14. `feat(scoring): report generator with degraded state support`
15. `feat(backend): ranking system with finalization gate`
16. `feat(backend): dashboard stats and live SSE stream`
17. `feat(backend): side-by-side comparison API`
18. `feat(backend): PDF report export endpoint`
19. `feat(chatbot): embedding pipeline with model queue integration`
20. `feat(chatbot): AI mentor chatbot with queue-aware streaming`
21. `feat(frontend): evalon design system and graceful degradation components`
22. `feat(frontend): score radar chart with pool average overlay`
23. `feat(frontend): why-this-score tooltip on all criterion scores`
24. `feat(frontend): admin live dashboard with SSE stats`
25. `feat(frontend): side-by-side submission comparison view`
26. `feat(frontend): PDF export with print stylesheet`
27. `feat(frontend): participant evaluation, leaderboard, mentor UI`
28. `feat(infra): vercel.json and frontend deployment configuration`
29. `docs: complete evalon documentation suite`
30. `test: full test suite including model queue and graceful degradation`
31. `chore(infra): Docker Compose production-ready with memory limits`

====================================================
SECTION 15: DOCKER COMPOSE SPECIFICATION
====================================================

SERVICES:

1. postgres: postgres:16-alpine with pgvector
    - Named volume: evalon_postgres_data
    - Health check: pg_isready
    - Init script: CREATE EXTENSION IF NOT EXISTS vector;

2. redis: redis:7-alpine
    - Named volume: evalon_redis_data

3. ollama: ollama/ollama:latest
    - Named volume: evalon_ollama_models
    - mem_limit: 8g ← CRITICAL: prevents OOM host kill
    - memswap_limit: 8g
    - DO NOT preload models at startup
    - Healthcheck: curl http://localhost:11434/api/version
    - GPU section (commented with instructions):

```yaml
# Uncomment for NVIDIA GPU:
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: 1
#           capabilities: [gpu]
```

- Note in SETUP.md: "Apple Silicon users — Metal GPU acceleration is
  automatic. No configuration needed. Ollama detects it natively."

4. backend: ./backend (FastAPI — EVALON API)
    - Depends on: postgres (healthy), redis (healthy), ollama (healthy)
    - mem_limit: 2g
    - Volumes: ./workspace:/workspace

5. worker: ./backend (ARQ worker)
    - Command: python -m arq app.jobs.worker.WorkerSettings
    - mem_limit: 3g
    - Depends on: same as backend
    - DO NOT scale above 2 workers on consumer hardware
      Document: "docker compose scale worker=2 is the recommended max
      on 24GB RAM. Scaling beyond this risks model loading conflicts."

6. frontend: ./frontend (Next.js — EVALON UI)
    - Depends on: backend
    - Env: NEXT_PUBLIC_API_URL from .env

7. nginx: ./nginx
    - Routes: / → frontend, /api → backend
    - Ports: 80:80

MAKEFILE COMMANDS:

- `make up`: docker compose up -d
- `make down`: docker compose down
- `make logs`: docker compose logs -f
- `make migrate`: run alembic upgrade head
- `make seed`: run seed script (create default admin, example hackathon)
- `make test`: run pytest
- `make shell`: open backend container shell
- `make model-status`: curl http://localhost:8000/api/v1/admin/model/status
- `make model-unload`: curl to unload current model (emergency reset)
- `make worker-scale-2`: docker compose scale worker=2

====================================================
SECTION 15A: VERCEL FRONTEND DEPLOYMENT
====================================================

EVALON's frontend should be deployable to Vercel in addition to the local
Docker Compose setup. This gives a live public URL for demos.

vercel.json:

```json
{
    "framework": "nextjs",
    "buildCommand": "next build",
    "devCommand": "next dev",
    "installCommand": "npm install",
    "env": {
        "NEXT_PUBLIC_API_URL": "https://your-evalon-backend.railway.app/api"
    }
}
```

SETUP for Vercel deployment:

1. Push frontend/ to GitHub repository
2. Import project at vercel.com (select the frontend/ subdirectory)
3. Set environment variable: NEXT_PUBLIC_API_URL pointing to deployed backend
4. Deploy — generates evalon.vercel.app URL

BACKEND DEPLOYMENT NOTE (for full cloud demo):
Backend can remain on Docker Compose locally or be deployed to Railway/Render.
Document both options in SETUP.md under "Cloud Deployment" section.

For demo purposes, the recommended configuration is:

- Backend: local Docker Compose (for Ollama model access)
- Frontend: Vercel (public URL for judges to access)
- Set CORS in backend to allow the Vercel domain

====================================================
SECTION 16: VERIFICATION GATES
====================================================

After completing each major phase, you MUST verify before proceeding.

PHASE 0 VERIFICATION (Model Queue — verify FIRST before any other phase):
□ Ollama service starts and /api/version responds
□ ModelQueueManager can acquire and release inference lock
□ ModelQueueManager can acquire and release embedding lock
□ Attempting to acquire lock while held → blocks, then succeeds after release
□ Lock timeout → raises ModelUnavailableError (not a crash)
□ GET /api/v1/admin/model/status returns valid response

PHASE 1 VERIFICATION (Infrastructure):
□ Docker Compose starts all 7 services without errors
□ PostgreSQL is reachable and pgvector extension is enabled
□ Redis is reachable
□ Ollama health check passes
□ FastAPI /health endpoint returns all services healthy
□ Alembic migrations run without errors
□ All schema tables exist in PostgreSQL

PHASE 2 VERIFICATION (Auth + Core API):
□ POST /auth/register creates user in DB
□ POST /auth/login returns JWT tokens
□ GET /auth/me returns current user
□ POST /hackathons creates hackathon (admin role)
□ POST /hackathons/{id}/join allows participant to join

PHASE 3 VERIFICATION (Pipeline):
□ Submit a known public GitHub repo URL
□ SSE stream emits model_loading stage
□ Repository clones successfully
□ ARQ job dispatches and executes
□ Repository clones to /workspace/repos/{submission_id}/
□ File tree is extracted correctly
□ Language detection identifies primary language
□ Static analysis runs without crashing
□ SSE stream emits at least 5 progress events

PHASE 4 VERIFICATION (AI Agents):
□ acquire_model_lock_node acquires lock before agents run
□ All three agents run SEQUENTIALLY (verify via log timestamps — no overlap)
□ release_model_lock_node releases lock after agents complete
□ Simulated agent timeout → abstained result, pipeline continues
□ Simulated model unavailable → degraded evaluation (not failed)
□ Comparative agent returns valid data (no LLM, pure analytics)
□ Evaluation with degraded=true: status is 'degraded', not 'failed'

PHASE 5 VERIFICATION (Scoring + Ranking):
□ Score aggregation produces correct weighted average
□ Normalization handles edge cases (single submission, tied scores)
□ Ranking table updated after evaluation completes
□ Finalization gate works: participants cannot see rankings before finalization
□ After finalization: rankings visible to participants
□ Score computed from static analysis when agent abstained
□ 'degraded' evaluations have valid final_score (not null)
□ Comparative percentile correct for multiple submissions

PHASE 6 VERIFICATION (Chatbot):

□ Chatbot request while evaluation in progress → queues (waits, not errors)
□ After evaluation releases lock, chatbot acquires it and responds
□ If embeddings not ready → clean "Mentor being prepared" message, not crash

PHASE 7 VERIFICATION (Frontend):
□ Admin can create hackathon end-to-end via UI
□ Participant can submit a repo via UI
□ Evaluation progress stream is visible in real-time
□ Agent result cards show evidence items
□ Leaderboard shows correct ranking after finalization
□ Mentor chatbot renders streamed responses correctly
□ Radar chart renders with two overlays (participant + pool average)
□ "Why This Score?" tooltip appears on hover for each criterion
□ Tooltip shows exactly 2 evidence items
□ DegradedBanner shows when evaluation.degraded=true
□ AgentAbstainedBadge shows on abstained agent cards
□ Live dashboard shows correct stats and updates via SSE
□ Side-by-side comparison loads 2-3 submissions correctly
□ PDF export produces readable output (test via print preview)
□ Chatbot shows "AI is busy" state when model is in use

====================================================
SECTION 17: DEVELOPMENT EXECUTION PHASES
====================================================

PHASE 0 — MODEL QUEUE INFRASTRUCTURE (do this before anything else):

1. Implement app/core/model_queue.py (ModelQueueManager)
2. Write unit tests for lock acquisition, release, timeout, priority
3. Verify Ollama API endpoints: /api/ps (list loaded), /api/generate (load/unload)
4. Test lazy loading: cold start, first inference, model switch
5. Add GET /api/v1/admin/model/status endpoint
6. Verify phase 0 gates
7. Write ADR-006

PHASE 1 — FOUNDATION (Start here):

1. Create all directories and files from Section 4 (empty files for now)
2. Write docker-compose.yml with memory limits
3. Write all .env.example variables
4. Write backend/app/config.py (Pydantic Settings loading from env)
5. Write backend/app/database.py (async SQLAlchemy engine)
6. Write all SQLAlchemy models (including hackathon_stats)
7. Write Alembic migration
8. Verify all tables including new columns (tech_stack, degraded, etc.)
9. Write phase 1 report

PHASE 2 — AUTHENTICATION + CORE API:

1. Implement JWT auth (security.py, auth endpoints)
2. Implement hackathon CRUD endpoints with admin authorization
3. Implement criteria management endpoints
4. Implement participant join endpoint
5. Write Pydantic schemas for all models
6. Write API tests for auth and hackathons
7. Verify phase 2 gates

PHASE 3 — REPOSITORY PIPELINE:

1. Implement ingestion.py (clone + sanitize)
2. Implement file_processor.py (tree, language detection)
3. Implement static_analysis.py (radon, ESLint, Semgrep)
4. Implement context_builder.py (assemble RepoContext)
5. Implement ARQ job: ingest_repository
6. Implement SSE endpoint for submission status
7. Implement Redis pub/sub for SSE events from workers
8. Test with a real public GitHub repo
9. tech_stack extraction to file_processor.py
10. Verify phase 3 gates

PHASE 4 — AI EVALUATION AGENTS:

1. Implement LLMProvider with model queue integration
2. Write BaseEvaluator with resilience pattern
3. Write all three prompt templates
4. Implement agents (Repo Understanding, Code Quality, Innovation)
5. Implement Comparative Agent (analytics only, no LLM)
6. Implement sequential LangGraph graph with acquire/release nodes
7. Implement graceful degradation throughout
8. Test with real repo — verify sequential execution in logs
9. Test agent timeout → degraded result (not crash)
10. Verify phase 4 gates

PHASE 5 — SCORING + RANKING:

1. Aggregator with static-analysis fallback scoring
2. Normalizer with comparative percentile data
3. Report generator with degraded state support
4. Ranking + hackathon_stats computation
5. Dashboard API endpoint + SSE stream
6. Comparison API endpoint
7. PDF export endpoint (weasyprint)
8. Verify phase 5 gates

PHASE 6 — CHATBOT + EMBEDDINGS:

1. Embedding pipeline with model queue integration
2. Query embedding with queue awareness
3. Retrieval (pgvector, no model lock needed)
4. Mentor chatbot with P3 priority queuing
5. Queue-wait response (HTTP 202 pattern)
6. Test chatbot during active evaluation → properly queues
7. Verify phase 6 gates

PHASE 7 — FRONTEND:

1. Design system + graceful degradation components
   (DegradedBanner, AgentAbstainedBadge, ModelLoadingState, MentorUnavailableState)
2. Authentication pages
3. Score Radar Chart (two overlays, tooltip integration)
4. "Why This Score?" ScoreTooltip component
5. Admin: Live Dashboard with SSE (LiveDashboard.tsx)
6. Admin: Hackathon management pages
7. Admin: Side-by-Side Comparison View
8. Participant: Submission and evaluation pages
9. Participant: Evaluation page (radar + tooltips + comparative section)
10. Participant: PDF export (print stylesheet + server-side button)
11. Participant: Leaderboard and mentor chatbot
12. vercel.json configuration
13. Verify all phase 7 gates

PHASE 8 — DOCUMENTATION + POLISH:

1. Write all documentation files (Section 12)
2. Write all ADRs (Section 12)
3. Run full test suite and fix failures
4. Demo script run end-to-end
5. Verify Vercel deployment works
6. PHASE-8-REPORT.md

====================================================
SECTION 18: QUALITY STANDARDS
====================================================

These standards are MANDATORY. Violations must be fixed before proceeding.

CODE QUALITY:

- Every Python function has type annotations
- Every public function has a docstring (at minimum one-line summary)
- No function exceeds 50 lines (refactor if needed)
- No file exceeds 300 lines (split if needed)
- No hardcoded values — all config via environment variables through Settings
- No bare `except` clauses — always catch specific exceptions
- All database operations use the async session context manager
- No synchronous I/O in async functions (no blocking os.path, time.sleep, etc.)

SECURITY:

- JWT secrets loaded from environment only
- Repository clone directory uses submission_id as subfolder (path traversal prevention)
- Submitted URLs validated against regex AND HTTP HEAD check before cloning
- File access restricted to clone directory (no path escape)
- Database queries use SQLAlchemy parameterized queries only (no raw SQL string concat)
- Rate limiting on auth endpoints (use slowapi)
- Passwords hashed with bcrypt (passlib[bcrypt])

ERROR HANDLING:

- All pipeline stages have explicit try/except with error status updates
- Agent failures are captured, logged, and stored — they do not crash the pipeline
- HTTP errors return structured JSON: { "detail": str, "error_code": str }
- All background jobs have retry logic (max 3 attempts with exponential backoff)

LOGGING:

- Structured JSON logging for all backend operations
- Log levels: DEBUG for dev, INFO for production
- Include: request_id, user_id, submission_id in relevant log entries
- Log all agent calls with: agent_id, processing_time_ms, success/failure

GRACEFUL DEGRADATION STANDARDS (MANDATORY):

- Every API endpoint that touches Ollama MUST handle ModelUnavailableError
- Every API endpoint MUST return structured JSON errors (never raw exceptions)
- Every UI state has a defined fallback display:
    - evaluation pending → progress stream
    - agent abstained → AgentAbstainedBadge with reason
    - evaluation degraded → DegradedBanner + partial results
    - evaluation failed → clear failure message + retry option (admin)
    - model loading → "AI loading..." indicator
    - model waiting → "AI is busy, you're next..." indicator
    - embeddings not ready → "Mentor being prepared..." message
    - chatbot queued → spinner + "Processing your question..." message
- Zero 500 errors visible in UI during a demo scenario
- Zero undefined/null rendering crashes in React components
  (use optional chaining everywhere, provide sensible defaults)

MODEL QUEUE STANDARDS:

- ModelQueueManager is the ONLY component that interacts with Ollama directly
- LLMProvider calls ModelQueueManager — not Ollama API directly
- No code outside of ModelQueueManager calls /api/generate, /api/ps, /api/embed
  except through LLMProvider interface
- Every lock acquisition has a timeout (never infinite wait)
- Lock release ALWAYS happens (use try/finally pattern)

MEMORY STANDARDS:

- No repository files held in memory (stream, don't load full file)
- File samples for agents: max 500 lines per file, max 5 files
- Prompt length: enforce max token budget per agent (2048 tokens input max)
- After cleanup_node: verify /workspace/repos/{submission_id}/ is deleted

====================================================
SECTION 19: THINGS YOU MUST NEVER DO
====================================================

1. NEVER execute cloned repository code. Static analysis only.
2. NEVER store repository files permanently — clean up after embeddings are generated.
3. NEVER return LLM-generated scores as-is. Always ground in static analysis evidence.
4. NEVER skip error handling on pipeline stages.
5. NEVER expose other participants' raw code to the chatbot context.
6. NEVER write placeholder implementations without a TODO comment and FUTURE_SCOPE.md entry.
7. NEVER skip the verification gates.
8. NEVER commit broken code to main.
9. NEVER generate a score without a corresponding evidence array.
10. NEVER expose internal stack traces in API error responses.
11. NEVER load two Ollama models simultaneously. Enforce via ModelQueueManager.
12. NEVER run agents in parallel. Sequential only.
13. NEVER let a single agent failure crash the evaluation pipeline.
14. NEVER show a raw error state to participants or admins during a demo.
    Every error has a human-readable fallback. No exceptions.
15. NEVER hardcode model names outside of ModelQueueManager constants.

====================================================
SECTION 20: DEMO SCENARIO
====================================================

When the MVP is complete, it must support this exact demo flow with zero manual steps beyond running the seed script:
FULL DEMO FLOW (must work reliably, zero manual steps after seed):

1. `make up` — all 7 EVALON services start
2. `make migrate` — schema initialized
3. `make seed` — creates:
    - Admin: admin@evalon.dev / admin123
    - 3 Participants: participant1@evalon.dev, participant2@evalon.dev,
      participant3@evalon.dev (all: test123)
    - One demo hackathon "AI Hackathon 2025" (active status)
    - Judging Criteria: Code Quality (40%), Innovation (35%), Project Understanding (25%)
    - Suggest 3 demo repos in seed output:
        - https://github.com/tiangolo/fastapi (Python, well-structured)
        - https://github.com/vercel/next.js (JS/TS, large, good test)
        - https://github.com/fastapi-practices/fastapi_best_architecture (architecture)

4. Admin opens browser → Admin logs in → views hackathon → observes empty submissions
   EVALON Live Dashboard
   Sees: "0 submissions, 0 evaluations"

5. Participant1 logs in → joins hackathon → submits a real GitHub repo URL
   Admin dashboard: "1 submission | 0 completed | 1 queued"
   Live update (no refresh)

6. SSE progress stream shows:
   ✓ Repository cloned
   ✓ File structure analyzed
   ✓ Static analysis complete
   ⟳ Loading AI models... (model_loading stage — expected ~30s first time)
   ✓ AI models ready
   ⟳ Repository Understanding Agent running...
   ✓ Repository Understanding complete (score shown)
   ⟳ Code Quality Agent running...
   ✓ Code Quality complete (score shown)
   ⟳ Innovation Agent running...
   ✓ Innovation complete (score shown)
   ✓ Comparative analysis complete
   ✓ Report generated
   ✓ Evaluation complete — Score: 84.2

7. While Participant1's evaluation runs:
   Participant2 and Participant3 submit simultaneously
   Their SSE shows: "AI is finishing another evaluation. You're next in queue..."
   (model_waiting stage — no crash, clean UX)

8. All three evaluations complete sequentially
   Admin dashboard: "3 submissions | 3 completed | 0 queued"
   Score distribution histogram shows 3 data points
   Top 5 preview shows all 3 ranked

9. Participant1 views evaluation:
    - Overall score prominent (84.2)
    - Radar chart renders with their scores + pool average overlay
    - Hovering "Code Quality" axis → tooltip shows top 2 evidence
    - "How You Compare" section: "Rank #1 of 3 | Top 33%"
    - Tech stack comparison: "2 others also used Python"

10. Admin opens Comparison View:
    Selects all 3 submissions → side-by-side columns appear
    Score differences highlighted

11. Admin finalizes rankings

12. Participant1 clicks "Download Report (PDF)"
    Clean PDF opens in print preview with EVALON header

13. Participant1 opens EVALON Mentor:
    "Why did I score lower on Innovation?"
    Chatbot responds with grounded, specific advice referencing their evaluation
    (Model loads again — clean ~5-10s wait, then streaming response)

14. If any step fails during demo:
    EVERY failure shows a clean, human-readable message.
    NO 500 errors. NO raw exceptions. NO broken UI states.
    The judges see resilience as a feature.

TARGET TIMINGS (on M4 MacBook Pro 24GB):

- First evaluation (cold model load): 3-5 minutes
- Subsequent evaluations (model warm): 1.5-3 minutes
- Embedding generation: 20-40 seconds
- Chatbot first response: 5-15 seconds (model already warm from evaluation)
- Dashboard refresh: real-time (SSE, <1s lag)
- PDF export: 2-5 seconds (server-side)

====================================================
BEGIN EXECUTION.

Think deeply.
Build methodically.
Model queue first — everything else depends on it.
Document everything, every decision.
Verify at every gate.
Do not rush.
The code you ship must be something a senior engineer would be proud to present.
Build EVALON so it cannot crash in front of an audience.

# This is EVALON. Build it to last.
