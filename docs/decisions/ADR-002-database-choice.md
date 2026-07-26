# ADR-002: Database Choice (PostgreSQL + pgvector)

**Status**: Accepted

## Context

EVALON's data is overwhelmingly relational: users, hackathons, criteria,
submissions, evaluations, agent results, rankings — a chain of foreign
keys and constraints (one submission per user per hackathon, weights
summing to 1.0 per hackathon, one evaluation per submission) that matter
for correctness. Two things complicate a pure-relational choice: the
evaluation report itself is a genuinely variable-shape JSON document
(different agents contribute different evidence structures), and the
mentor chatbot needs vector similarity search over embedded repo content.

Alternatives considered: MongoDB (document-native, would need a separate
vector search product or Atlas-specific tooling); a standalone vector
database (Qdrant/Chroma) alongside a relational store for everything else.

## Decision

PostgreSQL 16 with the `pgvector` extension, one database for both
relational and vector data. `evaluations.report` is a `JSONB` column for
the flexible-shape scorecard; `repo_embeddings.embedding` is a
`VECTOR(768)` column with an HNSW index (cosine ops) for chat retrieval.

## Consequences

**Gains:**
- Foreign key constraints and unique constraints enforce real invariants
  at the database level (e.g., `UniqueConstraint("hackathon_id",
  "user_id")` on submissions) rather than relying on application code to
  never have a bug.
- One database to operate, back up, and reason about failure modes for —
  not two.
- Rankings, leaderboards, and dashboard aggregates are natural SQL joins
  and aggregations; a document store would need its aggregation pipeline
  to do the same joins less naturally.
- `JSONB` gives the evaluation report's genuinely-variable shape a home
  without sacrificing relational integrity for the 90% of the schema that
  isn't the report.

**Costs:**
- pgvector's HNSW index needs pgvector ≥0.5.0 — the Docker image is
  pinned to `pgvector/pgvector:pg16` specifically (not plain
  `postgres:16-alpine`) to guarantee this.
- A dedicated vector database (Qdrant) would have better vector-search
  performance at scale, but EVALON's chat-retrieval workload (a few
  hundred chunks per submission, queried only during active chat
  sessions) is nowhere near the scale where that matters — see
  `RESEARCH.md` for the full comparison.
