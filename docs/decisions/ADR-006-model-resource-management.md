# ADR-006: Model Resource Management

**Status**: Accepted

## Context

Consumer hardware (Apple Silicon, 16–24GB unified memory) cannot load multiple
large LLMs simultaneously. EVALON's evaluation pipeline runs three sequential
LLM-backed agents, an embedding pipeline, and a mentor chatbot — all competing
for the same Ollama runtime. Naïve concurrent access (e.g., two evaluations
running in parallel, or a chatbot request landing mid-evaluation) would attempt
to load a second model while the first is still resident, causing partial
loads, OOM kills, or corrupted inference.

## Decision

Implement `ModelQueueManager` (`backend/app/core/model_queue.py`) as the single
component permitted to talk to the Ollama HTTP API directly. Every other
component — agents, the embedder, the mentor chatbot — goes through
`LLMProvider`, which goes through `ModelQueueManager`. Concretely:

- **Exactly two models**: `qwen2.5-coder:7b` (all reasoning) and
  `nomic-embed-text` (all embedding). No third model, ever.
- **Redis-backed distributed lock** (`evalon:model:lock`) with a bounded TTL
  (600s) so a crashed holder can't wedge the system forever.
- **Priority-ordered waiting**: a Redis sorted set (`evalon:model:queue`) orders
  waiters by `(priority, arrival_time)`. P0 (active evaluation agents) always
  overtakes P2 (embedding) and P3 (chatbot) waiters that arrived earlier —
  verified in `tests/test_core/test_model_queue.py::test_priority_ordering_p0_before_p2_before_p3`.
- **Mutual exclusion enforced at the load layer, not just the lock layer**:
  `_ensure_model_loaded` always unloads whatever else is resident (via Ollama's
  `keep_alive: "0"`) before loading the requested model, so even a bug in
  caller discipline can't result in two resident models.
- **Every acquisition has a timeout.** A caller that can't get the lock in time
  gets `ModelLockTimeoutError` (a subclass of `ModelUnavailableError`), not an
  indefinite hang. Pipeline callers catch this and fall back to
  static-analysis-only scoring instead of crashing (Section 7 of the spec).
- **Lazy loading, no preload.** Models load on first request. The Docker
  Compose `ollama` service memory is hard-capped at 8g with no swap.

## Consequences

**Gains:**
- Reliable on consumer hardware — no OOM crashes from concurrent model loads.
- Predictable, bounded memory usage (~4.8GB peak: inference + embedding never
  coexist, but the ceiling accounts for both being mid-swap).
- Fair scheduling under contention: an active evaluation is never starved by a
  chatbot request, and a chatbot request is never dropped, only queued.

**Costs:**
- First evaluation after a cold start is slower (~30–60s model load).
- The chatbot visibly queues behind active evaluations (by design — P3 is the
  lowest priority). The UI must communicate this as "AI is busy," not an error.
- All inference is strictly serialized: no two agents ever run concurrently,
  even across different submissions. This is a deliberate throughput trade for
  hardware safety (see Section 7 of `docs/SPEC.md` for why sequential-not-
  parallel execution is barely slower in practice — LLM inference is the
  bottleneck in every branch regardless of orchestration).

## macOS local-dev note

Ollama runs **natively on the host**, not inside Docker Compose, for local
development. Docker Desktop on macOS cannot pass through Apple Silicon's Metal
GPU to a container, so a containerized Ollama would run CPU-only. Backend and
worker containers reach the host's native (GPU-accelerated) Ollama via
`OLLAMA_BASE_URL=http://host.docker.internal:11434`. The `ollama` service is
still defined in `docker-compose.yml` for Linux/NVIDIA production parity,
gated behind the `docker-ollama` Compose profile. See `SETUP.md`.
