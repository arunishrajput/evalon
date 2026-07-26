# ADR-005: Evaluation Strategy (Static-Analysis-Grounded AI)

**Status**: Accepted

## Context

The most common failure mode of "AI judges a hackathon" systems is that
the score is unfalsifiable: a model is asked "rate this code 0–100" and
returns a number with no auditable trail back to *why*. A participant who
disagrees has no way to check the claim, and a judge reviewing the AI's
output has no way to verify it either — "good code quality" is not
evidence, it's an assertion. This is explicitly called out as the
system's non-negotiable principle (spec Section 2, restated at the top of
`CLAUDE.md`): "Tools measure. AI explains. Scores come from structured
tool output, never a raw LLM number."

Alternatives considered: a single LLM call per submission that returns a
holistic score and written feedback (simplest to build, fastest to run,
and exactly the unfalsifiable pattern above); an ensemble of multiple LLM
calls per criterion with no static analysis grounding, relying on
prompt engineering alone for consistency.

## Decision

**Static analysis runs first and unconditionally**, before any LLM is
invoked — cyclomatic complexity and maintainability index (radon),
security/pattern findings (semgrep), lint findings (ESLint for JS/TS),
file-structure checks (tests present, CI config present, Dockerfile
present, `.gitignore` present), and documentation/error-handling coverage
computed directly from the AST/regex, not asked of a model.

Every LLM agent's prompt is **built from these measurements**, not from
raw source alone — `context_builder.py` assembles a `RepoContext`
carrying the static analysis report, tech stack, and a capped set of
representative code samples, and every agent's Jinja2 prompt template
explicitly includes the relevant static-analysis facts. Each agent's
structured output (`AgentResult`) requires an `evidence` list — items
that must reference something observable, not a vibe — and a
`top_evidence` field (the 2 most load-bearing items) that the frontend
surfaces directly in the "why this score?" tooltip on every criterion.

The final score for each criterion is a **deterministic weighted
aggregation** (`scoring/aggregator.py`) of the agent's `score_raw`, never
an LLM's own claimed "final score" — and when an agent abstains (model
unavailable, timeout, malformed output), the aggregator falls back to a
formula computed purely from static analysis for that criterion, so a
score is *never* silently dropped, only its provenance changes (and that
change is surfaced to the user via `degraded=true`).

## Consequences

**Gains:**
- Every number a participant sees traces to specific, inspectable
  evidence — clicking "why this score?" shows the actual static-analysis
  facts and agent reasoning that produced it, not a re-generated
  justification.
- The system degrades gracefully by construction: because static
  analysis output already exists independently of any LLM call, an
  unavailable model doesn't mean "no score," it means "a score computed
  from measurements alone," which is strictly better than either a
  crash or a null result.
- Consistency across submissions is structurally encouraged, not just
  prompt-engineered: two submissions with genuinely comparable
  cyclomatic complexity and documentation coverage receive comparable
  Code Quality scores, because the same measurements ground both prompts.

**Costs:**
- More upfront engineering than a single "rate this 0–100" call — three
  separate static analysis tools, a context-assembly layer, and per-agent
  structured-output parsing, all before the first LLM token is generated.
- Static analysis tools have their own failure modes (semgrep timeouts on
  huge repos, ESLint config mismatches on unconventional project
  layouts) that the system must handle gracefully rather than treating as
  fatal — this is why every analyzer in `static_analysis.py` is
  independently wrapped and contributes an `errors` list rather than
  raising.
- The comparative agent is explicitly analytics-only (no LLM call at
  all) specifically because ranking and percentile calculations are
  *definitionally* deterministic arithmetic over the pool's scores — using
  an LLM there would reintroduce exactly the unfalsifiability this whole
  ADR exists to avoid, for a computation that doesn't need one.
