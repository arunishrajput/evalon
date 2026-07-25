# Phase 3 Report — Repository Ingestion + Static Analysis Pipeline

## What was built

- `backend/app/utils/git_utils.py` — GitHub URL validation (regex + HTTP HEAD
  + unauthenticated GitHub API check for public/existence), and cloning:
  shallow (`depth=1`) with `--filter=blob:limit=1m` (a partial-clone blob-size
  filter that implements "exclude binary files over 1MB" at the network
  level, not just after the fact), followed by stripping `node_modules/`,
  `.git/`, `venv/`, `__pycache__/`, then enforcing the 50MB / 5000-file
  limits with cleanup on violation. Clone runs in a thread executor under
  `asyncio.wait_for` — gitpython is blocking, never called directly in async
  code.
- `backend/app/utils/file_utils.py` — file tree walking, extension-based
  language detection, binary-file sniffing (NUL-byte heuristic), and capped
  text reads (never loads more than ~200KB of any file).
- `backend/app/pipeline/file_processor.py` — project type detection (8
  language/framework markers), dependency manifest parsing (`package.json`,
  `requirements.txt`, `pyproject.toml` incl. Poetry), README quality scoring
  (5 weighted signals: description/setup/demo/architecture/badges), and tech
  stack extraction.
- `backend/app/pipeline/static_analysis.py` — radon (in-process, cyclomatic
  complexity + maintainability index), semgrep (CLI subprocess + `--json`,
  per the plan's adaptation from the spec's "Python API" wording — no such
  stable API exists), ESLint (CLI subprocess against a bundled, fixed
  `--no-eslintrc` config so a submitted repo's own possibly-broken ESLint
  config is never loaded), file structure checks, and documentation coverage
  (Python via `ast.get_docstring`, JS/TS via a JSDoc-preceding-declaration
  regex heuristic).
- `backend/app/pipeline/context_builder.py` — assembles the `RepoContext`
  Phase 4's agents will consume, enforcing the memory standard (max 5 code
  samples, 500 lines each, lockfiles/JSON/YAML/Markdown excluded from
  candidacy).
- `backend/app/pipeline/analysis_cache.py` — bridges `ingest_repository`
  (this job) and Phase 4's `run_evaluation_pipeline`/`build_context_node`
  (see "architectural decisions" below for why this exists).
- `backend/app/pipeline/progress.py` — SSE plumbing: `emit_progress` RPUSHes
  to a Redis list (2h TTL, for late-connecting clients) and PUBLISHes for
  live subscribers; `stream_progress` replays history then streams live with
  15s keepalive comments.
- `backend/app/jobs/tasks.py::ingest_repository` — the ARQ job wiring all of
  the above together with DB status updates and SSE emission at each stage.
- `backend/app/api/v1/submissions.py` — `POST /submissions` (Stage 0:
  hackathon-active check, duplicate check, repo validation, dispatch),
  `GET /submissions/{id}`, `GET /submissions/{id}/status` (SSE), `DELETE
  /submissions/{id}` (withdraw, gated to pre-evaluation statuses).

## An underspecified area, resolved

The spec defines `ingest_repository` and `run_evaluation_pipeline` as two
separate ARQ jobs (Section 11's job dependency chain), with
`build_context_node` (Phase 4, inside `run_evaluation_pipeline`) described as
"assembles final RepoContext from DB **and file system**." But
`submissions` has no static-analysis JSONB column — only `tech_stack`
survives permanently. Since the clone isn't deleted until the very end of
the full evaluation graph (`cleanup_node`), the filesystem is genuinely still
there for Phase 4 to re-read, but re-running semgrep/ESLint a second time
would be wasteful. Resolved by caching the full `StaticAnalysisReport` +
project-analysis summary as JSON in Redis (same TTL pattern as progress
events) — Phase 4's `build_context_node` will load this cache and only fall
back to recomputation if it's expired.

## Verification gate results (Section 16, Phase 3)

All verified live against the real Ollama-adjacent stack (not mocked), using
a real GitHub submission end-to-end:

| Check | Result |
|---|---|
| Submit a known public GitHub repo URL | ✅ `octocat/Hello-World`, then `tiangolo/fastapi` (one of the spec's own suggested demo repos) |
| Repository clones successfully | ✅ |
| ARQ job dispatches and executes | ✅ |
| Repository clones to `/workspace/repos/{submission_id}/` | ✅ confirmed via container `ls`, `.git`/excluded dirs stripped |
| File tree extracted correctly | ✅ |
| Language detection identifies primary language | ✅ (see bug fix below) |
| Static analysis runs without crashing | ✅ |
| SSE stream emits at least 5 progress events | ✅ 6 events on both test repos |

Full `fastapi` run in ~60s end-to-end: radon analyzed 5003 functions (40
flagged >10 complexity), semgrep found 23 real findings, doc coverage 159/5413,
file structure correctly detected tests/CI/license/gitignore, `degraded=false`
throughout (no analyzer failures).

## Bug found and fixed during live verification

Submitting `fastapi` against itself surfaced a real bug: `primary_language`
came back `"Markdown"`, not `"Python"` — the repo's internationalized docs
have more `.md` files than `.py` files, and language ranking was pure file-count
with no distinction between source and documentation formats. Fixed by
excluding `Markdown`/`JSON`/`YAML` from primary-language and tech-stack
candidacy in `file_processor.py` (`_primary_candidate_languages`). Re-verified
against the same on-disk repo: `primary_language` now correctly `"Python"`,
tech_stack `["Python", "Shell", "GitHub Actions"]`.

A second correctness gap was caught before it shipped: `_run_semgrep`/
`_run_eslint` were silently returning `[]` when the underlying subprocess
failed (missing binary, timeout) — indistinguishable from "the tool ran and
found nothing," which would have made `submission.degraded` never fire for a
genuine tool outage. Fixed by raising `StaticAnalysisError` on subprocess
failure so the existing per-analyzer `try/except` in `run_static_analysis`
correctly records it in `errors` (and downstream, sets `degraded=True`).

## Known issues / technical debt

- `ingest_repository` does not yet chain into `run_evaluation_pipeline`
  (Phase 4 doesn't exist). The job intentionally stops after static analysis,
  leaving `submission.status = 'analyzing'`. The SSE stream correctly stays
  open (keepalives only, no `completed`/`error`) since evaluation genuinely
  hasn't happened yet — this is not a bug, just the honest Phase 3/4 boundary.
- `GET /hackathons/{id}/submissions` (admin submission listing) remains
  unimplemented, still blocked on Phase 5's need to join in ranking/score data
  for a useful view.

## Testing results

**41/41 tests pass** (35 automated + re-verified no regression): 6 new
`test_pipeline/` tests use a synthetic, hand-built repo fixture (no network
dependency) per spec's testing guidance; semgrep/ESLint's JSON-parsing logic
is tested by mocking the subprocess boundary rather than hitting the real
semgrep registry in CI.

## What's next

Phase 4 — AI Evaluation Agents: `LLMProvider`, `BaseEvaluator`, the three LLM
agent prompts (Repository Understanding, Code Quality, Innovation), the
analytics-only Comparative Agent, and the sequential LangGraph orchestration
with lock acquire/release nodes — finally chaining `ingest_repository` into
`run_evaluation_pipeline` and completing the submission lifecycle.
