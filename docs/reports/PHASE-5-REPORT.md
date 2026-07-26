# Phase 5 Report — Scoring, Ranking, Dashboard, Comparison, PDF Export

## What was built

- `backend/app/scoring/normalizer.py` — pure `compute_rankings` function
  implementing the spec's literal percentile formula
  (`submissions_below / total × 100`) with standard competition ranking for
  ties (1, 1, 3 — not 1, 1, 2). No DB access, trivially unit-testable.
- `backend/app/scoring/ranking_service.py` — `recompute_rankings_for_hackathon`:
  upserts `Ranking` rows from completed/degraded evaluations, and — the
  important guarantee — is a no-op once any ranking for the hackathon is
  finalized, so a late-arriving retry or stray job can never reshuffle a
  published leaderboard.
- `backend/app/scoring/stats_service.py` — `compute_hackathon_stats` /
  `upsert_hackathon_stats`: submission pipeline-stage buckets
  (completed/in_progress/queued/failed), score-distribution histogram,
  tech-stack frequency, average score, top-5 preview.
- `backend/app/scoring/dashboard_stream.py` — the admin dashboard SSE stream:
  a literal 15-second poll-and-push loop (spec's exact cadence), not a
  pub/sub relay — a fresh DB session per cycle, no long-held connection.
- `backend/app/scoring/pdf_report.py` — server-side PDF export via
  weasyprint. Built as a direct HTML+CSS string rather than a Jinja2
  template file, since the report has exactly one fixed shape.
- `backend/app/api/v1/rankings.py`, `dashboard.py`, `comparison.py`,
  `export.py` — the four remaining routers from the spec's directory
  listing. Plus the two hackathon endpoints deferred since Phase 2:
  `GET /hackathons/{id}/submissions` and `POST /hackathons/{id}/finalize`
  (which does one guaranteed-fresh `recompute_rankings_for_hackathon` pass
  before locking every ranking row).
- `backend/app/jobs/tasks.py` — `recompute_rankings` and
  `update_hackathon_stats` ARQ jobs, dispatched after every evaluation
  completes and after every new submission (increment queued count, per
  spec Section 11).
- `GET /admin/hackathons` and `GET /admin/queue/status` — the two admin
  endpoints deferred since Phase 0/1, now unblocked by the stats system and
  by jobs actually running. Queue status parses ARQ's own periodic
  `arq:queue:health-check` Redis key rather than reimplementing job
  bookkeeping.

## Deliberate deviation from the spec's literal job chain

Section 11 describes a linear chain: `run_evaluation_pipeline →
generate_embeddings → recompute_rankings → update_hackathon_stats`. Since
`generate_embeddings` doesn't exist until Phase 6, and — more importantly —
rankings/stats must never be blocked by embedding generation being slow,
absent, or failed (P3: one agent/feature failure never crashes or stalls
the rest), `recompute_rankings` and `update_hackathon_stats` are dispatched
directly from `run_evaluation_pipeline`'s completion, independent of
whatever `generate_embeddings` does later in Phase 6.

## Live end-to-end verification (real Ollama, 3-submission pool)

Ran 3 full evaluations against real repos (`Hello-World`, `Spoon-Knife`,
`git-consortium`) through one hackathon:

- **Dashboard** correctly showed live pipeline-stage counts while
  evaluations were still running (`1 completed / 2 in progress` mid-run),
  then settled to `3 completed / 0 in progress`, with a correct score
  histogram, tech-stack frequency, and a rank-ordered top-5 preview.
- **Rankings**: ranks 1/2/3 with percentiles 66.67/33.33/0.00 — matching the
  literal formula by hand.
- **Comparison API**: real evidence-grounded `scores_by_criterion` with
  `top_evidence` correctly cross-referenced from each submission's stored
  `agent_results`.
- **Finalization**: `POST /finalize` transitioned the hackathon to
  `finalized` and every ranking row to `finalized=true`; a subsequent
  ranking fetch correctly began showing participant identities (hidden
  before finalization, per spec Section 10).
- **Dashboard SSE stream**: confirmed the `stats_update` event fires
  immediately on connect with the correct snapshot shape.
- **PDF export**: downloaded a real, valid PDF (verified via `file` — "PDF
  document, version 1.7") from a live evaluation.

One nuance surfaced during this run and confirmed as *correct, not a bug*:
each submission's `report.comparative` section is a snapshot taken at the
moment that specific evaluation's `comparative_node` ran, not a live
recomputation. The first-evaluated submission in a batch legitimately shows
`sufficient_data=false` (small pool at that moment); the last-evaluated
submission in the same batch shows the full 3-submission comparison. This
is inherent to the "comparative agent runs once per evaluation" design the
spec itself describes — there's no mechanism (or requirement) to retroactively
refresh earlier submissions' comparative snapshots as the pool grows.

## Bug found and fixed during live verification

PDF export crashed every time with `AttributeError: 'super' object has no
attribute 'transform'`. Root cause: weasyprint 62.x's PDF stream backend
subclasses `pydyf.Stream` and calls `super().transform(...)`; `pydyf` had no
version pin in `requirements.txt`, so pip resolved `pydyf==0.12.1`, which
removed the method weasyprint 62.x's subclass depends on — a real
version-compatibility gap in weasyprint's own packaging (no pin declared on
their end either). Fixed by pinning `pydyf==0.10.0` (the version weasyprint
62.x was actually built against), rebuilding the backend/worker images, and
re-verifying a real PDF downloads successfully.

## Testing results

**117/117 tests pass** (33 new this phase, no regressions): normalizer edge
cases (empty pool, single submission, tied scores — spec Section 13's
explicit list), stats bucketing (including the `score == 100` boundary,
which would silently overflow a naive `int(score // 10)` bucket index into
an 11th nonexistent bucket if not clamped), the ranking service's
finalized-is-immutable guarantee against a real DB, the rankings API's
finalization-gated visibility (hidden / early-visible / finalized-visible /
admin-always-visible), and the comparison endpoint's input validation
(max 3, invalid UUID) plus a real evidence-cross-referencing round trip.

## Known issues / technical debt

- None introduced knowingly. The one real bug found (pydyf/weasyprint) was
  fixed and verified live within this phase.

## What's next

Phase 6 — Chatbot + Embeddings: the embedding pipeline
(chunker/embedder/retriever) with embedding-lock integration, and the
mentor chatbot with P3-priority queuing and SSE token streaming. This is
also where `generate_embeddings` finally joins the job chain described in
Section 11 — dispatched alongside (not blocking) the rankings/stats jobs
this phase already wired up.
