# EVALON Setup Guide

## Prerequisites

- **Docker** and **Docker Compose** (v2, the `docker compose` subcommand —
  not the standalone `docker-compose` binary).
- **Ollama**, installed and running natively on the host machine (not in a
  container — see the macOS note below).
- Minimum hardware:
  - **16GB RAM minimum** (roughly 8GB for the OS + Docker services, 8GB
    for the inference model resident in memory).
  - **24GB RAM recommended** for smooth chatbot + evaluation concurrence
    (the model queue serializes access, but you still want headroom for
    the OS, Docker, and Postgres/Redis caches simultaneously).
  - **Apple Silicon (M-series):** fully supported, GPU-accelerated via
    Metal — this is the reference platform EVALON was built and verified
    against (M4, 24GB).
  - **NVIDIA GPU:** supported — uncomment the GPU reservation block in
    `docker-compose.yml`'s `ollama` service and run Ollama in the
    container instead of natively.
  - **CPU-only:** supported but slow — expect 5–10 minutes per evaluation
    instead of 1.5–5.

## Step-by-step setup

### 1. Install and start Ollama

```bash
# macOS: https://ollama.com/download, or `brew install ollama`
ollama serve   # if it isn't already running as a background service
```

### 2. Pull the two models EVALON uses

```bash
ollama pull qwen2.5-coder:7b   # ~4.7GB — all agent reasoning + report generation + mentor chat
ollama pull nomic-embed-text   # ~270MB — all embedding operations
```

EVALON uses **exactly these two models, never more** — this is a hard
architectural constraint (see `docs/decisions/ADR-006-model-resource-management.md`),
not a default you should casually change. Swapping the inference model is
possible via the `INFERENCE_MODEL` env var, but every prompt template and
score calibration was tuned against `qwen2.5-coder:7b` specifically.

### 3. Clone and configure

```bash
git clone <this-repo>
cd evalon
cp .env.example .env
```

Open `.env` and, at minimum:
- Change `JWT_SECRET` to a long random string before any deployment
  reachable outside your own machine.
- Leave `OLLAMA_BASE_URL` as `http://host.docker.internal:11434` on
  macOS/Windows (Docker Desktop's DNS alias for the host). On Linux, this
  alias doesn't exist by default — either add
  `extra_hosts: ["host.docker.internal:host-gateway"]` (already present in
  `docker-compose.yml`) or point `OLLAMA_BASE_URL` at your host's real LAN
  IP.

### 4. Start the stack

```bash
make up        # docker compose up -d — postgres, redis, backend, worker, frontend, nginx
make migrate   # alembic upgrade head — creates the schema, enables pgvector, builds the HNSW index
```

Verify everything is actually healthy before moving on:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","database":true,"redis":true,"ollama_reachable":true}
```

If `ollama_reachable` is `false`, Ollama isn't running or isn't reachable
at `OLLAMA_BASE_URL` from inside the container — this is the single most
common setup failure. See Troubleshooting below.

### 5. Seed demo data

```bash
make seed
```

This creates:
- Admin: `admin@evalon.dev` / `admin123`
- 3 participants: `participant1@evalon.dev`, `participant2@evalon.dev`,
  `participant3@evalon.dev` (all: `test123`)
- One demo hackathon, **"AI Hackathon 2025"** (already `active`), with
  judging criteria Code Quality (40%), Innovation (35%), Project
  Understanding (25%)
- A printed list of 3 suggested demo repo URLs to submit

The script is idempotent — re-running it after data already exists just
confirms what's there rather than duplicating it.

### 6. Open the app

`http://localhost:3000` (frontend directly) or `http://localhost` (through
nginx, which also proxies `/api/*` to the backend — use this URL if you
want to demo the exact production topology).

## First evaluation: what to expect

**The first evaluation is slower than every one after it.** Ollama loads
a model into memory lazily, on first request — EVALON deliberately never
preloads a model at startup (spec principle: don't guess what a demo needs
before it's asked for). Expect:

- Model load time: **~30–60 seconds** the first time `qwen2.5-coder:7b` is
  requested (subsequent requests reuse the already-loaded model, held
  warm for 10 minutes of inactivity via Ollama's `keep_alive`).
- First full evaluation, cold: **3–5 minutes** end to end (clone → static
  analysis → model load → 3 sequential agent calls → comparative analysis
  → report).
- Subsequent evaluations, model already warm: **1.5–3 minutes**.
- Embedding generation (for the mentor chatbot): **20–40 seconds**,
  running as a separate background job right after evaluation completes.
- Mentor's first chat response: **5–15 seconds** if the model is already
  warm from a recent evaluation; add the model-load time above if not.

Watch the live SSE progress stream on the evaluation page — it shows every
stage explicitly, including `model_loading` and (if another evaluation
currently holds the lock) `model_waiting`, so a slow first run never looks
like it's hung.

### Monitoring the model queue

```bash
make model-status
# {
#   "ollama_reachable": true,
#   "inference_model": "qwen2.5-coder:7b",
#   "inference_model_loaded": true,
#   "embedding_model": "nomic-embed-text",
#   "embedding_model_loaded": false,
#   "lock_held_by": "eval:3f1274a0-...",
#   "queue_depth": 1,
#   "estimated_wait_seconds": 60
# }
```

`lock_held_by` and `queue_depth` tell you exactly what's happening if
things seem stuck: is an evaluation running right now, and how many other
requests (evaluations or chat messages) are waiting behind it.

## Running the full demo script

This mirrors `docs/SPEC.md` Section 20 exactly — the flow EVALON is
designed to survive live, in front of an audience, without a single raw
error reaching the screen.

1. `make up && make migrate && make seed` — zero manual steps beyond this.
2. Sign in as `admin@evalon.dev`. Open the live dashboard for "AI Hackathon
   2025" — it shows `0 submissions, 0 evaluations`, live via SSE.
3. In a second browser (or incognito window), sign in as
   `participant1@evalon.dev`, join the hackathon, and submit one of the
   three suggested repo URLs the seed script printed (e.g.
   `https://github.com/tiangolo/fastapi`).
4. Watch the admin dashboard update to `1 submission | 0 completed | 1
   queued` — **no page refresh**.
5. Watch the participant's SSE progress stream move through: cloning →
   static analysis → `model_loading` (~30–60s the first time) → each of
   the three agents in sequence → comparative analysis → report generated
   → a final score.
6. While that evaluation is still running, sign in as `participant2` and
   `participant3` in two more windows and submit the other two suggested
   repos. Their progress streams show `model_waiting`: *"AI is finishing
   another evaluation. You're next in queue..."* — not an error, not a
   stall.
7. Once all three complete, the admin dashboard shows `3 submissions | 3
   completed | 0 queued`, a 3-point score histogram, and a top-5
   leaderboard preview.
8. As `participant1`, open the evaluation page: the large score, the radar
   chart with **both** overlays now visible (their score + the 3-submission
   pool average, since the comparative agent now has enough data), a
   "why this score?" tooltip on click showing real evidence, and a "how
   you compare" card ("Rank #1 of 3 | Top 33%" or similar).
9. As admin, open the Comparison view, select all 3 submissions — a
   side-by-side grid appears with shared weaknesses and unique strengths
   highlighted.
10. As admin, click **Finalize rankings**.
11. As `participant1`, click **Download Report (PDF)** — a clean,
    single-page-per-section PDF with an EVALON header and the same scores.
12. As `participant1`, open the mentor chat and ask *"Why did I score
    lower on Innovation?"* — the model reloads if it isn't already warm
    (~5–15s), then streams a specific, encouraging answer grounded in the
    actual evaluation.

If anything in this flow fails, the failure should be a specific,
human-readable message somewhere in the UI — never a raw 500, never a
blank screen. If you see either of those, that's a real bug; check
`DEBUGGING_GUIDE.md` first, then the relevant `docs/reports/PHASE-N-REPORT.md`.

## Troubleshooting

**`ollama_reachable: false` in `/health`**
Confirm Ollama is actually running (`ollama list` should print your pulled
models) and reachable from inside a container:
```bash
docker compose exec backend curl -s http://host.docker.internal:11434/api/version
```
If that fails on Linux, `host.docker.internal` likely isn't resolving —
add the DNS override or switch `OLLAMA_BASE_URL` to your host's LAN IP.

**An evaluation seems stuck on `model_loading` or `model_waiting`**
Check `make model-status`. If `queue_depth` is genuinely 0 and
`lock_held_by` is `null` but nothing is progressing, the lock may be
orphaned from an abruptly-killed process (see `DEBUGGING_GUIDE.md`'s
"force-release a stuck lock" section) — this is rare and self-heals within
10 minutes regardless (`MODEL_LOCK_TIMEOUT_SECONDS`), since the lock key
carries a TTL.

**Frontend shows "Not Found" or every request 404s**
Check `NEXT_PUBLIC_API_URL` — it must end in `/api/v1`, not `/api`. This
was a real bug caught during Phase 7's live browser verification; if
you've hand-edited `.env`, it's easy to reintroduce.

**A submission fails immediately with a generic error**
Check `docker compose logs worker` — the actual failure (invalid/private
repo URL, repo too large, clone timeout) is logged there even though the
participant only sees a friendly message (spec principle: no raw errors
reach the UI).

**Semgrep or ESLint findings are missing from a report**
Static analysis tools are independently fault-tolerant — if one fails
(e.g., semgrep hits a timeout on a huge repo), the evaluation continues
with `degraded=true` and a note in `degraded_reason`. This is by design,
not a bug to "fix" by disabling the tool.

## Cloud deployment

For a public demo URL without exposing your own machine:

- **Backend: keep it on local Docker Compose.** It needs to reach Ollama,
  and running Ollama in the cloud with GPU access is expensive and not
  necessary for a demo — your laptop's Metal/CUDA acceleration is already
  fast enough.
- **Frontend: deploy to Vercel.**
  1. Push `frontend/` to a GitHub repo (or use this repo's root — Vercel
     lets you select a subdirectory as the project root).
  2. Import the project at vercel.com, selecting `frontend/` as the root.
  3. Set the `NEXT_PUBLIC_API_URL` environment variable in Vercel's
     project settings, pointing at a publicly reachable URL for your local
     backend (e.g. an ngrok/Cloudflare Tunnel forwarding to `localhost:8000`,
     or `localhost/api/v1` through nginx if tunneling port 80).
  4. Deploy — Vercel generates a public `your-project.vercel.app` URL.
  5. Add that Vercel URL to `CORS_ORIGINS` in your backend's `.env` and
     restart the backend (`docker compose restart backend`) — otherwise
     the browser will block every request with a CORS error.
- If you'd rather not expose your own machine at all, the backend can be
  deployed to **Railway** or **Render** instead — either supports Docker
  Compose-style deployment. You'd still need an Ollama instance reachable
  from that deployment (their own GPU-backed compute, or a tunnel back to
  a machine that has one) — this is real infrastructure cost, unlike the
  local-backend option above, so only worth it for a longer-lived public
  demo rather than a single presentation.
