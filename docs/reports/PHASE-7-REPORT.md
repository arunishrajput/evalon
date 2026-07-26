# Phase 7 Report — Frontend

## What was built

The complete Next.js 14 App Router frontend against the spec's Section 10
design (dark theme, `#0a0a0a` background / `#3b82f6` accent / `#f59e0b`
degraded / `#ef4444` error tokens, already scaffolded into
`tailwind.config.js` in the setup phase):

- **Design system & degradation components** — hand-authored shadcn/ui-style
  primitives (button, card, badge, dialog, popover, tabs, select, table,
  progress, avatar, alert, etc.) and the four spec-mandated states:
  `DegradedBanner`, `AgentAbstainedBadge`, `ModelLoadingState`,
  `MentorUnavailableState`.
- **Foundation** — a typed API client (`lib/api.ts`) covering every
  endpoint with automatic access-token refresh on 401, TypeScript types
  mirroring every backend Pydantic schema (`lib/types.ts`), a fetch-based
  SSE frame parser (`lib/sse.ts` — the browser's native `EventSource` can't
  send an `Authorization` header, and every EVALON SSE endpoint requires
  one), and a Zustand auth store.
- **Auth pages** — login/register, JWT session persisted via
  `zustand/middleware`'s `persist`.
- **The evaluation page** — spec's "most important page, built with
  maximum care": huge color-coded score, `ScoreRadarChart` with the exact
  dual-overlay design (participant score solid blue, pool average dashed
  amber, shown only when the comparative agent has `sufficient_data`),
  clickable axes, `ScoreTooltip` ("why this score?" — a shadcn/ui Popover
  showing the top 2 evidence items, on hover *and* click) on both the
  radar axes and the criterion table, live `ProgressStream` (SSE) that
  collapses to a duration summary on completion, tabbed `ReportViewer`
  (Overview / Code Quality / Innovation / Architecture / Recommendations),
  and `PrintableReport` — a fully separate flat pre-expanded render, hidden
  except under `@media print`, since the interactive tabs can't print one
  panel at a time.
- **Admin live dashboard** — `LiveDashboard.tsx` connected to the 15s SSE
  stream, animated stat cards, `ScoreHistogram` / `TechStackCloud`
  (Recharts), top-5 leaderboard preview, model-queue status with a pulsing
  dot. Plus the full hackathon lifecycle: creation with the criteria
  builder's live weight-sum validation, gated status transitions, a
  Finalize button disabled until every evaluation completes, submissions
  table with up-to-3 comparison selection, CSV-exportable rankings.
- **Comparison view** — `ComparisonView.tsx` with green/red
  strength/weakness highlighting per the component spec.
- **Mentor chatbot UI** — `ChatInterface.tsx` streaming the SSE token
  response live, suggested comparative questions, HTTP 202 queued state
  shown as the spec's exact "AI mentor is currently evaluating..." notice.
- **Participant flow** — hackathon list with join/submit, submit page with
  live client-side GitHub repo preview, leaderboard respecting the
  finalization gate.
- **Print stylesheet** in `globals.css` (`@media print`, A4 `@page`
  margins, `print:hidden` on all interactive chrome).

## A deliberate deviation: no "list my submissions" tracking on the backend

The API contract (spec Section 6) has no endpoint for a participant to
list their own submissions across hackathons — `GET
/hackathons/{id}/submissions` is admin-only, and `GET /submissions/{id}`
needs an id the client already has. Rather than add a new backend
endpoint not in the spec's contract, `lib/mySubmissions.ts` tracks
`{hackathonId -> submissionId}` and joined-hackathon state client-side in
localStorage, scoped per logged-in user id.

## Five real bugs found and fixed via live browser testing

Every page was actually driven in a browser end-to-end (register → create
hackathon → join → submit two real repos → watch live SSE progress →
evaluate → compare → rank → chat with the mentor), not just built and
assumed correct. This surfaced five real bugs a purely-static review would
have missed:

1. **Wrong API base URL.** `NEXT_PUBLIC_API_URL` was `.../api` — missing
   the `/v1` the backend actually mounts at — an artifact from the Phase 1
   scaffold, before any route existed to catch it against. Every request
   404'd. Fixed in `.env`, `.env.example`, `docker-compose.yml`.
2. **Hard reload logged users out.** Zustand's `persist` middleware
   rehydrates from localStorage asynchronously (by design, to avoid
   SSR/CSR hydration mismatches); the auth guard's `!accessToken` check ran
   before rehydration finished, so any hard page load — refresh, a pasted
   link, a new tab — bounced an already-logged-in user to `/auth/login`.
   Fixed with a `hasHydrated` flag the guard now waits on.
3. **The submit page could strand a user on itself.** Its "already
   submitted" check re-read localStorage on every render; its own success
   path wrote to that same key immediately before `router.push()`
   navigated away, so the very next render (before the navigation
   committed) saw the now-true check and rendered the "already submitted"
   branch instead. Fixed by capturing the check once at mount via
   `useState`'s lazy initializer.
4. **Cross-account data leak.** All `mySubmissions.ts` localStorage keys
   were global, not scoped per user — logging out and into a *different*
   participant account in the same browser showed the *previous* user's
   "already joined" / "already submitted" state. Confirmed live by
   registering a second participant and watching it happen. Fixed by
   namespacing every key with the logged-in user's id.
5. **ComparisonView's own content was invisible.** The spec calls for
   "sticky" column headers; with the page's normal vertical scroll as the
   only scrolling ancestor, `position: sticky` on each card's header caused
   it to paint on top of — fully hiding — the "Scores by criterion"
   heading and the first criterion row underneath it. Confirmed via
   `getBoundingClientRect()`: the header's rendered bottom edge sat past
   the content div's top edge, and `document.elementFromPoint()` at the
   heading's coordinates returned the header's score span instead. Fixed
   by dropping `sticky` for a plain header — correctness over a partial
   mobile-scroll nicety.

A sixth, smaller issue (a React "missing key prop" console warning) traced
to a real type mismatch: the frontend's `DashboardStats.top5_preview` type
included a `submission_id` field the backend's actual response
(`stats_service.py`) never sends — the preview is deliberately anonymous
pre-finalization. Fixed the type and switched the list key to `rank`.

## Live end-to-end verification

Ran the complete flow against the real stack (real Postgres/Redis/Ollama,
not mocks) via Claude-in-Chrome browser automation:

- Register → promote to admin (public registration is participant-only,
  matching the backend's own design) → create a hackathon with the
  criteria builder (weight-sum progress bar correctly red until 1.00,
  green after) → activate it.
- Register two separate participant accounts → join → submit two real
  public repos (`octocat/Hello-World`, `octocat/Spoon-Knife`) → watched
  live SSE `ProgressStream` render the real per-stage timeline (cloning →
  static analysis → three agents → comparative → report) → both completed
  with real Ollama-generated scores (46.1, 56.2).
- Evaluation page: radar chart rendered correctly (no pool-average overlay
  for the first submission, since it was alone in the pool at eval time —
  correct, not a bug), `ScoreTooltip` on a criterion row popped up the
  real "Average maintainability index: 0.0 / Documentation coverage: 0/0"
  evidence, tab switching and reasoning expand/collapse worked, PDF
  download and print both triggered cleanly with no console errors.
- Mentor chat: real streamed, markdown-formatted, RAG-grounded response
  from `qwen2.5-coder:7b`, referencing the actual (empty) README and
  suggesting concrete next steps with a code example.
- Admin dashboard: SSE-live stat cards, score histogram, tech stack chart,
  top-5 preview (both submissions, correctly ranked), model queue status
  (`qwen2.5-coder:7b`, loaded/not-loaded reflecting real state).
- Rankings and side-by-side comparison (after the sticky-header fix): both
  submissions' full criterion breakdown, tech stack, and green-highlighted
  unique strengths rendered correctly.
- `npm run build` — clean production build, zero TypeScript errors, all 18
  routes compiled.

## Testing results

Backend's 155/155 test suite re-run after all frontend/infra changes
(config edits touch the backend container's environment) — still green,
no regressions. Frontend has no dedicated automated test suite this
phase (not part of the spec's stack — Jest/Playwright aren't listed in
Section 2's tooling); correctness was established via the live
browser-driven verification above and a clean production build.

## Known issues / technical debt

- **Comparison view's headers are no longer sticky** (see bug #5). The
  spec's literal ask was "sticky column headers"; a correct partial
  implementation (sticky only during the mobile horizontal scroll, not
  the page's vertical scroll) would need a dedicated scroll container
  with independent axis handling — left as a documented simplification
  rather than risk reintroducing the content-hiding bug under time
  pressure.
- **The evaluation page's status badge can be briefly stale** during an
  active evaluation — the header's `SubmissionStatusBadge` reads from an
  SWR-fetched `Submission` object that isn't polled as frequently as the
  SSE `ProgressStream` below it updates live; it self-corrects once
  `ProgressStream`'s `onCompleted` callback triggers a refetch. Cosmetic
  only — the detailed live progress list is fully accurate throughout.

## What's next

Phase 8 — Documentation + Polish: `README.md`, `SETUP.md`,
`ARCHITECTURE.md`, `RESEARCH.md`, `FUTURE_SCOPE.md`,
`DEBUGGING_GUIDE.md`, the remaining ADRs (001–005), a full test suite
pass, and an end-to-end demo script run per spec Section 20.
