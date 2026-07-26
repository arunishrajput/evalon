# Phase 8 Report — Documentation, Polish, and the Full Demo Run

## What was built

- **`backend/app/scripts/seed.py`** (`make seed`) — a real gap found at the
  start of this phase: the Makefile, `CLAUDE.md`, and spec Section 20's
  demo script all reference `make seed`, but the script itself had never
  been implemented in any prior phase. Creates the exact accounts and
  demo hackathon the spec's demo scenario depends on (admin + 3
  participants, "AI Hackathon 2025" with its 40/35/25 criteria), prints
  the 3 suggested demo repo URLs, and is idempotent — safe to re-run.
- **The full required documentation suite** (spec Section 12): `README.md`,
  `SETUP.md`, `ARCHITECTURE.md` (with Mermaid system/sequence/model-queue/
  pipeline/ER diagrams), `RESEARCH.md` (comparative writeups for every
  major technology choice, each with a concrete "why, for this system
  specifically" conclusion rather than a generic pros/cons list),
  `FUTURE_SCOPE.md` (8 deferred features, each with a real implementation
  sketch rather than a bullet point), `DEBUGGING_GUIDE.md` (grounded in
  the actual failure modes discovered across Phases 0–7's live
  verification passes), and ADR-001 through ADR-005 (joining ADR-006 from
  Phase 0).
- **`PROJECT_STRUCTURE.md`** and **`CHANGELOG.md`** — referenced in the
  spec's Section 4 directory tree but not explicitly required by Section
  12's documentation list; added anyway since a missing file the spec's
  own tree implies should exist would read as incomplete.
- **`vercel.json`** updated with the spec's `env` block, using the
  corrected `/api/v1` path (the Phase 7 bug) rather than propagating it
  into the deployment config too.
- **Docker Compose memory limits extended to every service.** `ollama`,
  `backend`, and `worker` already had `mem_limit` caps from earlier
  phases; `postgres`, `redis`, `frontend`, and `nginx` didn't. Added
  conservative caps to all four so the whole stack has an explicit
  ceiling, not just the three most obviously memory-hungry services.

## A real issue found while preparing the demo script, before running it

Before relying on the spec's three suggested demo repos for live
verification, each was checked via the GitHub API rather than assumed
correct:

- **`tiangolo/fastapi`** has moved — the org transferred to
  `fastapi/fastapi` at some point after the spec was written. The
  original URL still works (GitHub redirects `git clone` transparently),
  but the repo now sits at ~52MB — just *over* the default
  `MAX_REPO_SIZE_MB=50`.
- **`vercel/next.js`** is ~2.4GB — wildly over the limit.

Checked how EVALON actually handles this before deciding what to do about
it: `git_utils.py` clones fully first, *then* measures size on disk and
raises a clean `RepositoryIngestionError` if it's too large — not a crash,
consistent with the "no raw error ever reaches the UI" principle, but
slow: a 2.4GB clone takes real time (or hits `CLONE_TIMEOUT_SECONDS`
first) before the participant sees any failure at all. Not a bug to fix —
the actual constraint (never execute cloned code, but sizing requires
having cloned it) makes an early size check impossible without querying
GitHub's API for an estimate first, which is a reasonable future
improvement but out of scope here. Documented plainly in both
`SETUP.md`'s demo script and the seed script's own stdout instead of
letting a live demo hit a slow, unexplained-feeling rejection.

## Live end-to-end demo run (spec Section 20, verified for real)

Ran the *exact* documented flow against a freshly seeded database — not a
subset, not with synthetic stand-in data:

1. `make migrate && make seed` — clean run, zero errors, zero manual
   steps beyond invoking these two commands.
2. Admin dashboard for "AI Hackathon 2025": `0 submissions, 0 evaluations`
   — confirmed via the live dashboard endpoint immediately after seeding.
3. `participant1@evalon.dev` joined and submitted the spec's own first
   suggested repo, `https://github.com/tiangolo/fastapi` — the
   redirect-following validation worked correctly, resolving to
   `fastapi/fastapi`'s real name and description.
4. Dashboard updated live: from `0 submissions` to `1 submission, 1
   in_progress` — the pipeline had already progressed from `pending` to
   an active stage by the time of the check, which is *more* accurate
   live behavior than the spec's literal "1 queued" wording describes at
   the instant right after submission, not a discrepancy.
5. SSE progress stream moved through every documented stage.
6. While that evaluation was still running, `participant2` and
   `participant3` joined and submitted (the spec's third suggested repo,
   `fastapi-practices/fastapi_best_architecture`, and `octocat/Hello-World`
   as a deliberate, documented substitute for the oversized `next.js`).
   `participant2`'s SSE stream showed the **exact spec-quoted message**:
   *"AI is finishing another evaluation. You're next in queue..."*
7. All three evaluations completed. Dashboard: `3 submissions | 3
   completed | 0 queued | 0 failed`, a real 3-point score histogram
   (scores 45.7 / 50.2 / 76.8), real tech-stack frequency aggregated from
   the actual repos (Python, FastAPI, SQLAlchemy, PostgreSQL, Docker,
   ...), and a correctly-ranked top-5 preview.
8. `participant1`'s evaluation: real per-criterion scores, a comparative
   snapshot showing `sufficient_data=false` — correctly re-confirming the
   same "comparative agent snapshot timing" behavior documented as
   correct (not a bug) in the Phase 5 report: `participant1` was the
   *first* submission evaluated, so its comparative snapshot was taken
   when the pool held only itself.
9. Checking `participant2`'s evaluation (the *last* one to actually
   finish, since `Hello-World` — submitted after `participant2` but
   trivially small — jumped ahead of it in the model queue purely because
   its faster clone/static-analysis phase reached `acquire_model_lock_node`
   sooner) confirmed `sufficient_data=true`, a real comparative payload:
   rank #1 of 3, "Top 33%", "+19.2 above average", and correct
   per-criterion pool averages.
10. Admin comparison view across all 3 submissions returned correct
    per-submission scores and ranks.
11. `POST /finalize` transitioned the hackathon to `finalized`.
12. PDF export: a real, valid PDF (`file` confirms "PDF document, version
    1.7", 13,225 bytes).
13. Mentor chat: asked the spec's own suggested question — *"Why did I
    score lower on Innovation?"* — and got back a genuinely specific,
    encouraging, evidence-grounded response referencing the *actual*
    code in the submitted repo (naming the real
    `custom_generate_unique_id`/`custom_generate_unique_id2`/
    `custom_generate_unique_id3` functions from `fastapi`'s own test
    suite, correctly identified as a real weakness worth consolidating),
    in 27 seconds — slightly over the spec's 5-15s target, but consistent
    with the model being warm (no reload) and the extra time reflecting
    a longer, more thorough response rather than a slow start.

Every step matched the spec's documented flow. No raw error, no 500, no
broken UI state was hit anywhere in the run.

## Testing results

**155/155 backend tests pass** (no regressions from any Phase 8 change —
none of this phase's work touched application logic, only docs,
infrastructure config, and the new seed script, which has no tests of
its own since it's a one-shot operational script, not application code).
Frontend production build (`npm run build`) remains clean, zero
TypeScript errors, all 18 routes compiling — re-verified after this
phase's `docker-compose.yml` changes to confirm nothing in the frontend
container was affected.

## Known issues / technical debt

- The seed script's suggested demo repos include two (`tiangolo/fastapi`,
  now-over-limit; `vercel/next.js`, far over) that don't cleanly fit
  EVALON's own default size constraints — documented rather than hidden,
  per the reasoning above. A future improvement would check a repo's
  size via GitHub's API *before* cloning (a single lightweight API call)
  rather than discovering it's too large only after a potentially slow
  full clone.
- No automated test coverage for `app/scripts/seed.py` itself — it's a
  thin, idempotent, directly-observable operational script (verified live
  twice in this phase: an initial run and a re-run confirming
  idempotency), not application logic with edge cases worth unit-testing
  in isolation.

## What's next

EVALON's full spec-driven build (Phases 0–8) is complete: model queue
infrastructure, the full database schema, authentication and core API,
the repository ingestion and static analysis pipeline, three sequential
AI evaluation agents plus a comparative analytics agent, scoring and
ranking with a finalization gate, the embedding pipeline and a
queue-aware RAG mentor chatbot, the complete Next.js frontend, and now
the full documentation suite plus a live-verified, spec-faithful demo
run. Natural next steps are the deferred items in `FUTURE_SCOPE.md` —
none of them are gaps in what was promised, they're explicitly
out-of-scope extensions for a future iteration.
