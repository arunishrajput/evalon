# EVALON — Future Scope

What's deliberately out of scope for the current build, and how each
would actually be built if taken on. "Out of scope" here means
*considered and consciously deferred*, not overlooked — several of these
(private repos, a real Security agent) are natural next asks the moment
someone tries to use EVALON for a real event with real constraints this
build doesn't yet handle.

## Comparative Intelligence Agent — full design

The current `ComparativeAgent` (`app/agents/comparative.py`) is
explicitly partial by spec design: pure analytics over `final_score` and
`by_criterion` scores already stored in the pool's `Evaluation.report`
rows — rank, percentile, pool average/median, tech-stack overlap, and a
template-generated (not LLM-generated) summary sentence. A full version
would add:

- **Cross-submission pattern detection**: cluster submissions by
  approach (not just tech stack) using the same embeddings already
  generated for the mentor chatbot — "3 other teams also built a
  REST-API-plus-React-dashboard; yours is the only one using
  server-sent events for live updates" is a genuinely useful comparative
  insight the current implementation can't produce, because it requires
  semantic similarity over architecture, not scores.
- **An LLM-written comparative narrative**, gated behind the same
  evidence-grounding principle as every other agent (ADR-005): the model
  would receive the deterministic analytics above as *input*, and its
  job would be phrasing, not computing the numbers themselves — never a
  second, competing scoring pathway.
- **Judges are also always P0 in the requester priority ordering** —
  currently comparative analysis runs as part of the same evaluation
  pipeline that holds the P0 inference lock; if it grows into an LLM call
  of its own, it would need its own priority tier (likely P1, alongside
  report generation) so it doesn't compete with active evaluations for
  the lock.

## Private repository support — OAuth flow design

Currently `hackathon.settings.allow_private_repos` exists in the schema
but nothing implements it — every submission must be a public repo,
verified via an unauthenticated GitHub API call
(`utils/git_utils.py::validate_repo_exists_and_public`). Supporting
private repos needs:

1. **GitHub OAuth App registration**, with the `repo` scope (or the
   narrower `contents:read` if using a GitHub App instead of an OAuth
   App — a GitHub App is the better fit here, since it can be installed
   per-organization by a hackathon's participants without granting EVALON
   blanket access to every repo they own).
2. A new `github_installations` table: `user_id`, `installation_id`,
   `access_token` (encrypted at rest — this is the first place EVALON
   would hold a credential with real blast radius, so this needs its own
   security review before shipping, not a quick add).
3. `ingestion.py`'s clone step would need to inject a short-lived
   installation token into the clone URL rather than cloning anonymously
   — gitpython supports this via
   `https://x-access-token:{token}@github.com/...`.
4. **Never persist the token longer than the clone step needs it** —
   consistent with the existing "never store repository files
   permanently" principle, a private-repo token should be used once and
   discarded, not cached for reuse across submissions.

## UI/UX Agent — implementation approach

A fourth evaluator specifically for frontend/design quality — currently
out of scope because it needs something none of the existing agents do:
**visually rendering the submission**, not just reading its source. Design:

- Would require actually running the submitted project in a sandboxed,
  network-isolated container (a real exception to the "never execute
  cloned code" principle — this is exactly why it's deferred, not a
  small addition) to take a screenshot via a headless browser.
- Screenshot(s) would go to a vision-capable model — `qwen2.5-coder:7b`
  is text-only, so this agent would need a model swap, which interacts
  directly with `ModelQueueManager`'s "exactly two models" constraint
  (ADR-006) and would need that decision revisited, not just a new
  requester type added.
- Static, non-execution-based signals (Lighthouse-style checks against
  built static assets, if a `dist/`/`build/` directory is present and
  committed; presence of a `README.md` screenshot; responsive CSS media
  query usage) are the safer, execution-free subset that could ship
  first without touching the "never execute" principle at all.

## Security Agent — full Trivy + Semgrep integration design

The current Code Quality agent already runs semgrep, but folded into a
single criterion alongside complexity/maintainability — not a dedicated,
separately-weighted Security criterion. A full Security agent would add:

- **Trivy** for dependency vulnerability scanning (`requirements.txt`,
  `package.json`/`package-lock.json` lockfiles) — a different concern
  than semgrep's pattern-based source scanning, and currently entirely
  absent.
- **Semgrep's security-specific rule packs** (`p/security-audit`,
  `p/secrets`) run explicitly, separately from the general rule set
  currently used, with severity-weighted scoring rather than a flat
  finding count.
- Secret-scanning (hardcoded API keys, credentials committed to the
  repo) as a distinct, high-severity finding category — genuinely useful
  for a hackathon context, where participants under time pressure are a
  realistic source of committed secrets.
- Would plug into the same evidence-grounding pattern as every other
  agent — Trivy/Semgrep findings become the `evidence` list, never a
  freeform LLM security opinion.

## Multi-tenant SaaS — architecture changes needed

EVALON is currently single-tenant (one Postgres database, one Redis
instance, any admin can see any hackathon via `GET /admin/hackathons`).
Multi-tenant SaaS would need:

- An `organization_id` on `users` and `hackathons`, with every admin
  query scoped to the caller's organization — a real, systematic change
  touching most of `app/api/v1/*.py`, not an additive feature.
- Per-tenant resource isolation for the model queue: today, one
  `ModelQueueManager` instance serves every hackathon system-wide, which
  is fine for one organization's event but would let one tenant's
  evaluation load starve another tenant's chatbot users. Would need
  per-tenant priority weighting, or genuinely separate Ollama instances
  per tenant (defeating the whole "share one GPU" cost model this
  architecture is built around).
- Billing hooks (see below) become mandatory, not optional, the moment
  multiple paying organizations share infrastructure.

## Kubernetes deployment — resource requirements and configuration

Current deployment target is a single Docker Compose host. A Kubernetes
version would need:

- A `StatefulSet` for Postgres (or, more realistically, a managed
  Postgres service — RDS/Cloud SQL — rather than self-managing storage
  in-cluster) and Redis.
- The backend and worker as separate `Deployment`s (already
  architecturally separate processes, so this maps cleanly) — but the
  worker's replica count is capped by the model-queue constraint:
  scaling worker replicas doesn't scale evaluation throughput past what
  the single-GPU Ollama instance can serve, so a naive
  `HorizontalPodAutoscaler` on the worker would just create more waiters
  in the same queue, not faster evaluations. Real throughput scaling
  needs multiple Ollama instances (one per available GPU node) and the
  model queue lock namespaced per-GPU — a genuine architecture change,
  not a config change.
- GPU node pool with the NVIDIA device plugin for the `ollama` service
  (the `docker-compose.yml` GPU reservation block is the Compose-side
  equivalent already present, commented out).

## API for external hackathon platforms

An integration surface (Devpost, MLH's platform, etc.) so an existing
hackathon platform could push submissions into EVALON and pull scores
back out, rather than EVALON being the whole platform:

- A webhook-receiving endpoint accepting `{repo_url, participant_email,
  hackathon_external_id}` and mapping it onto EVALON's existing
  submission flow.
- A signed-webhook callback (or a polling endpoint) delivering
  `{final_score, report_url}` back to the external platform once
  evaluation completes.
- API-key auth (distinct from the JWT user-session auth that exists
  today) scoped to "create submissions on behalf of X hackathon" — a new
  auth model, not an extension of the current one.

## Billing system design

Not implemented at all today (every hackathon is free to run). A real
billing system would need: a `subscriptions`/`usage` table tracking
evaluations-per-billing-period per organization, a payment provider
integration (Stripe is the natural default), and a hard usage cap
enforced *before* a submission is accepted (not after evaluation, which
would mean doing the compute work and then refusing to show the result —
worse for everyone). This is explicitly the last item on this list
because it only becomes necessary once multi-tenant SaaS (above) is
real — a self-hosted, single-organization deployment (today's actual
target) has no billing concern at all.
