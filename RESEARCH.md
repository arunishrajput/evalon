# EVALON — Engineering Research

The technology comparisons behind every major architectural choice in
EVALON. Each section states the alternatives actually considered, the
criteria that mattered *for this specific system*, and the conclusion —
deliberately not a generic "X vs Y" writeup, since the right choice here
depends heavily on constraints most comparisons ignore: a single consumer
GPU, a hard requirement that AI never crash the pipeline, and a
demo-in-front-of-judges reliability bar.

## Backend framework: FastAPI vs. NestJS vs. Django

| | FastAPI | NestJS | Django (+ DRF) |
|---|---|---|---|
| Async-native | Yes, from the ground up | Yes (Node's event loop) | Bolted on (ASGI + `async def` views), ORM is sync by default |
| Type safety | Pydantic v2 models double as request/response validation *and* docs | TypeScript, strong | Python type hints, weaker enforcement without extra tooling |
| Ecosystem fit | SQLAlchemy 2.0 async, Alembic, ARQ — all first-class async | Would need a Python subprocess or a full Node rewrite of the AI pipeline (LangGraph, Ollama clients are Python-first) | Same async-ORM friction as above; DRF serializers duplicate what Pydantic gives free |
| OpenAPI generation | Automatic, from the same models used for validation | Automatic via decorators | Requires drf-spectacular or similar, a separate source of truth |

**Conclusion: FastAPI.** The deciding factor isn't really "FastAPI vs.
NestJS vs. Django" in the abstract — it's that the AI orchestration layer
(LangGraph, Ollama's HTTP client, the static analysis tool integrations)
is Python-native, and a polyglot split (Node API + Python worker) would
mean either duplicating domain models across two languages or routing
every AI-touching request through an extra network hop. FastAPI's async
model also matters concretely here: the API process must stay responsive
(serving dashboard SSE, submission status polls) while the worker process
is deep inside a multi-minute LLM call — a sync framework would need
explicit threading to avoid the API blocking on its own DB queries during
that window.

## Database: PostgreSQL vs. MongoDB

| | PostgreSQL | MongoDB |
|---|---|---|
| Relational integrity | Foreign keys, unique constraints (e.g., one submission per user per hackathon) enforced at the DB level | Enforced in application code, or not at all |
| Vector search | pgvector extension — one database for both relational and vector data | Atlas Vector Search exists but ties you to Atlas specifically; self-hosted vector search is a separate product (or absent) |
| Evaluation reports | `JSONB` column handles the genuinely-variable-shape report structure (agent results, comparative data) without a document-DB migration | Native fit for the same data, but loses relational integrity everywhere else |
| Query patterns | Rankings, leaderboards, and dashboard aggregates are all relational joins/aggregations — SQL is the natural fit | Aggregation pipeline can do this, but it's a worse fit for "join evaluations to submissions to users, filter, sort by rank" |

**Conclusion: PostgreSQL + pgvector.** The evaluation report genuinely
does want a flexible-schema JSON blob (`evaluations.report`), which is
exactly the case MongoDB is built for — but it's a small fraction of the
system's actual data. Everything else (who owns what submission, which
criteria belong to which hackathon, ranking order, finalization state) is
relentlessly relational, and a hackathon leaderboard is fundamentally a
sorted, filtered, joined query. `JSONB` gives the flexible-shape benefit
without giving up relational integrity for the other 90% of the schema,
and pgvector means the mentor chatbot's retrieval doesn't need a second
database at all.

## Async job queue: ARQ vs. Celery vs. RQ

| | ARQ | Celery | RQ |
|---|---|---|---|
| Async support | Native — jobs are `async def` | Bolted on; Celery's core execution model is sync workers, async requires extra care | Sync only |
| Broker | Redis only (matches what's already required for the model lock + pub/sub) | Redis, RabbitMQ, others — flexibility EVALON doesn't need | Redis only |
| Operational complexity | Single dependency, minimal config | Beat scheduler, result backend, routing — a lot of moving parts for 5 job types | Simple, but sync-only is disqualifying |
| Fit for LLM calls | A job can `await` an Ollama HTTP call without blocking the worker's event loop for other jobs | Would need `gevent`/`eventlet` monkey-patching to get the same behavior | N/A |

**Conclusion: ARQ.** Every other piece of coordination infrastructure in
EVALON (the model lock, the SSE pub/sub, the job queue itself) already
runs on Redis — Celery's broker flexibility is a non-benefit here, and its
operational surface (result backends, Beat, routing) is built for a scale
and complexity EVALON's 5 job types don't need. ARQ's jobs being plain
`async def` functions matters concretely: `run_evaluation_pipeline`
awaits the LangGraph, which awaits Ollama calls that can take 10–30
seconds each — a sync worker model would need a thread per concurrent job
just to not block, which is exactly the kind of accidental complexity ARQ
avoids by being async-native.

## AI orchestration: LangGraph vs. CrewAI vs. a custom pipeline

| | LangGraph | CrewAI | Custom (plain Python) |
|---|---|---|---|
| Execution model | Explicit directed graph, state passed node-to-node | Agents "collaborate" via a crew abstraction — implicitly conversational | Whatever you write |
| Sequential guarantee | A plain edge chain (no conditional routing needed) *is* the guarantee — nodes execute in the order the graph defines | Crew agents can be run sequentially, but the abstraction is built around delegation/conversation, fighting the "agents never talk to each other" requirement here | Guaranteed by construction (a for-loop), but no structured resilience, retry, or observability pattern reused |
| Resilience pattern | Node-level try/except with explicit state mutation (abstain, degrade) composes cleanly with LangGraph's state-passing model | Would require suppressing CrewAI's built-in agent-to-agent communication, working against the library | Reinvented per-agent, harder to keep consistent across 3+ agents |
| Observability | Node names/state map directly onto the SSE progress stages the frontend needs to show | Crew execution logs are conversation-shaped, awkward to map onto discrete pipeline stages | Whatever logging you add |

**Conclusion: LangGraph.** EVALON's agents explicitly **do not**
collaborate or converse — each runs once, independently, grounded in the
same static analysis context, and their outputs are aggregated
mechanically (a weighted sum), not synthesized by another LLM call. That's
the opposite of what CrewAI is designed for. LangGraph's plain
directed-graph model, where a node is just a function that receives and
returns state, maps almost one-to-one onto the spec's literal pipeline
stages (`build_context → acquire_lock → repo_understanding → code_quality
→ innovation → release_lock → aggregate → report → comparative → save →
cleanup`) and gives every node the same resilience shape for free (catch,
degrade, continue) without fighting an abstraction built for a different
problem.

## LLM runtime: Ollama vs. vLLM vs. API-only (OpenAI/Anthropic/etc.)

| | Ollama | vLLM | API-only |
|---|---|---|---|
| Cost model | Free, runs on hardware you already own | Free, but wants a real GPU server to be worth its complexity | Per-token, scales with hackathon size |
| Concurrency | Single active model by design (fits `ModelQueueManager`'s "exactly one loaded" constraint naturally) | Built for high-throughput batched serving of *many* concurrent requests — the opposite of this system's needs | Provider-managed, effectively unlimited but costs scale linearly |
| Offline/local operation | Fully local — works at a hackathon venue with bad wifi | Fully local | Requires reliable internet + provider uptime, both real risks during a live judging event |
| Setup complexity | `ollama pull`, done | Requires CUDA, a real GPU, model format conversion | An API key |
| Data privacy | Participant code never leaves the local machine | Same | Participant code is sent to a third party |

**Conclusion: Ollama.** vLLM's whole value proposition — batching many
concurrent requests efficiently — is irrelevant to a system whose
`ModelQueueManager` deliberately serializes everything to a concurrency of
1; vLLM's operational complexity (real GPU server, CUDA setup) would be
pure cost with no corresponding benefit here. An API-only approach removes
the memory-management problem entirely but reintroduces two risks this
system specifically wants to avoid: per-submission cost that scales with
hackathon size, and a hard dependency on internet connectivity and a
third party's uptime during a live event — plus it means every
participant's source code leaves the building. Ollama running natively on
the organizer's own laptop, with Metal/CUDA acceleration, is the only
option that's simultaneously free, local, private, and simple to set up
day-of.

## Vector storage: pgvector vs. Qdrant vs. Chroma

| | pgvector | Qdrant | Chroma |
|---|---|---|---|
| Infrastructure | Extension on the database EVALON already runs | Separate service to deploy, monitor, back up | Separate service (or embedded, with its own persistence concerns) |
| Scale of this use case | A few hundred chunks per submission, retrieval only for active chat sessions — genuinely low QPS | Built for millions of vectors and high-QPS similarity search | Built for prototyping RAG apps, not necessarily production durability |
| Query pattern | `ORDER BY embedding <=> query_vector LIMIT 5`, joined against the same table's other columns in one query | Would require a second round-trip to fetch chunk metadata from Postgres after the vector search | Same round-trip concern |
| Operational cost | Zero — one more index on an existing table | A whole additional service: deployment, credentials, monitoring, another thing that can go down | Same |

**Conclusion: pgvector.** The mentor chatbot's retrieval workload is
small — a few hundred embedded chunks per submission, queried only when a
participant is actively chatting — nowhere near the scale that justifies
a dedicated vector database's operational cost. Since `repo_embeddings`
already needs its relational columns (`submission_id`, `chunk_type`,
`metadata`) alongside the vector, keeping it in Postgres means retrieval
is a single indexed query instead of a vector-DB round-trip followed by a
Postgres join. One fewer service to deploy, monitor, and keep available
during a live demo is a real reliability win, not just a simplicity one.

## Static analysis tools

| Tool | Role | Why chosen |
|---|---|---|
| **radon** | Cyclomatic complexity + maintainability index (Python) | Pure-Python library, no subprocess overhead, well-maintained, exactly the two metrics the Code Quality agent needs to ground its findings in |
| **semgrep** | Security/pattern findings across languages | Broad language coverage in one tool, JSON output designed for programmatic consumption, actively maintained rule sets |
| **ESLint** | JS/TS lint findings | The de facto standard for JS/TS; running it via subprocess (rather than searching for a stable embeddable Python API, which doesn't exist) mirrors how semgrep is already invoked |

All three are invoked as **read-only static analysis subprocesses against
a disk copy of the cloned repo** — EVALON's hardest non-negotiable
constraint is that cloned code is **never executed**, so tools that
require running the target project (test runners, linters that execute
plugins from the repo itself) were out of consideration regardless of
their analysis quality. Every analyzer is independently fault-tolerant:
a semgrep timeout on an unusually large repo degrades that submission's
static analysis contribution rather than failing the whole evaluation —
consistent with the "one failure never crashes the pipeline" principle
applied all the way down to the tool level, not just the agent level.
