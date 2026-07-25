# Phase 2 Report — Authentication + Core API

## What was built

- `backend/app/core/security.py` — bcrypt password hashing and JWT
  access/refresh tokens. **Refresh token rotation and revocation via Redis**:
  the spec's Section 5 schema has no `refresh_tokens` table, so each refresh
  token's `jti` is tracked as a Redis key (`evalon:refresh_token:{jti}` →
  `user_id`, TTL-matched to `REFRESH_TOKEN_EXPIRE_DAYS`). Refreshing deletes
  the old key and issues a new pair (rotation); reusing an already-rotated or
  logged-out token fails because its key is gone (reuse detection) — this is
  what `POST /auth/logout`'s "invalidate refresh token" actually does.
- `backend/app/core/rate_limit.py` + wiring in `main.py` — slowapi limiter
  (10/min) on `/auth/register` and `/auth/login`.
- `backend/app/api/v1/auth.py` — all 5 spec'd auth endpoints:
  register (always creates a `participant` — admin accounts are seed-script-only,
  never self-service), login, refresh, logout, me.
- `backend/app/api/v1/hackathons.py` — hackathon CRUD, status transitions
  (with an explicit allowed-transition graph — draft→active→evaluating→finalized,
  plus evaluating→active as a "reopen" escape hatch), criteria (single-add and
  bulk-replace with weight-sum-to-1.0 validation), participant listing, and
  join. `GET /hackathons/{id}/submissions` and `POST /hackathons/{id}/finalize`
  are deferred to Phases 3 and 5 (they need the `Submission` pipeline and
  ranking engine respectively — not implementable yet, not stubbed).
- Extended `app/core/exceptions.py` with `AuthenticationError` (401),
  `AuthorizationError` (403), `NotFoundError` (404), `ConflictError` (409) —
  each `EvalonError` subclass now carries its own `status_code`, and a new
  `HTTPException` handler is a safety net for any raw `HTTPException` raised
  anywhere in the app, so every error path — not just the ones we
  anticipated — returns `{ "detail": str, "error_code": str }`.
- `app/dependencies.py` — `get_current_user` (bearer JWT → live DB user, not
  just token claims) and `require_admin`.
- **"[admin, owner]" interpreted literally**: mutating hackathon endpoints
  require the caller to be an admin *and* the specific admin who created that
  hackathon (`hackathons.admin_id`), not just any admin. Enforced by
  `_load_owned_hackathon` in `hackathons.py`, verified by
  `test_only_owning_admin_can_modify_hackathon`.
- `backend/tests/test_api/` — 16 tests against the real dev Postgres/Redis
  (not mocks) via `httpx.AsyncClient` + `ASGITransport` directly against the
  FastAPI app.

## Verification gate results (Section 16, Phase 2)

All verified twice: once live via curl against the running stack, once via
the automated suite.

| Check | Result |
|---|---|
| `POST /auth/register` creates user in DB | ✅ |
| `POST /auth/login` returns JWT tokens | ✅ |
| `GET /auth/me` returns current user | ✅ |
| `POST /hackathons` creates hackathon (admin role) | ✅ |
| `POST /hackathons/{id}/join` allows participant to join | ✅ |

Additional coverage beyond the minimum checklist (all passing):
refresh-token rotation + reuse rejection, logout revocation, duplicate-email
rejection, wrong-password rejection, non-admin creation rejection, weight-sum
validation (accept 0.4+0.35+0.25, reject a lone 0.5), owner-vs-any-admin
enforcement, draft-hackathon exclusion from public listing, duplicate-join
rejection, join-before-active rejection, invalid status transition rejection.

**23/23 tests pass** (16 new + 7 from Phase 0, confirming no regression).

## Architectural decisions

- Refresh tokens live in Redis, not a new DB table — see above. This keeps
  the schema exactly as spec'd in Section 5 while still delivering real
  rotation/revocation semantics (not just "trust the JWT expiry").
- `EvalonError.status_code` became a per-class attribute instead of an
  isinstance-check in the handler — cleaner as the exception hierarchy grows
  (Phase 2 alone added 4 new error types).

## Known issues / technical debt

- **pytest-asyncio + module-level async engine**: the app's `engine` and the
  `@lru_cache`d `get_redis()` client are singletons created once at import
  time, but pytest-asyncio gives each test function its own event loop by
  default (pytest-asyncio 0.24 has no reliable ini-level "session loop" option
  for auto-mode test items, only for fixtures) — pooled connections from a
  previous test's closed loop caused `RuntimeError: Event loop is closed`.
  Fixed by disposing/clearing both singletons at the start of the `clean_db`
  autouse fixture, forcing fresh connections bound to the current test's loop.
  Documented here and in `DEBUGGING_GUIDE.md` (Phase 8) since it will bite
  again if a future test file forgets to depend on `clean_db`.
- slowapi's in-memory rate-limit counters are also process-global state that
  leaked across tests (tests share one Python process) — `limiter.reset()` is
  now called in the same `clean_db` fixture.
- `GET /api/v1/admin/hackathons` and `GET /api/v1/admin/queue/status` remain
  unimplemented (still blocked on Phase 3's ARQ job introspection and the
  stats aggregation that Phase 5 builds).

## Testing results

23/23 tests pass (`test_core/` 7, `test_api/` 16).

## What's next

Phase 3 — Repository Pipeline: `ingestion.py` (gitpython clone with size/file
count/timeout limits), `file_processor.py` (language detection, tech stack
extraction, README scoring), `static_analysis.py` (radon/semgrep/ESLint via
subprocess), the `ingest_repository` ARQ job (finally giving `worker.py` a
real domain function), and the SSE progress endpoint.
