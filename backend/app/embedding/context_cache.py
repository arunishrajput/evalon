"""Bridges the evaluation graph (which builds RepoContext + the final report
in-process, inside run_evaluation_pipeline) and the separately-dispatched
generate_embeddings ARQ job — a distinct process invocation with no access to
that in-memory state. cleanup_node deletes the cloned repo from disk at the
end of the graph (spec P2: never store repo files permanently), so by the
time generate_embeddings runs there is nothing left on disk to re-read —
everything the embedding pipeline needs must be captured here first. Same
Redis-cache-bridge pattern as pipeline/analysis_cache.py."""

from pydantic import BaseModel
from redis.asyncio import Redis

from app.pipeline.context_builder import RepoContext

_TTL_SECONDS = 30 * 60  # generous buffer for generate_embeddings to be picked up off the ARQ queue


class CachedEmbeddingContext(BaseModel):
    repo_context: RepoContext
    report_summary: str
    overall_assessment: str
    strengths: list[str]
    weaknesses: list[str]
    architecture_notes: str


def _key(submission_id: str) -> str:
    return f"evalon:embedding_context:{submission_id}"


async def cache_embedding_context(redis: Redis, submission_id: str, repo_context: RepoContext, report: dict) -> None:
    payload = CachedEmbeddingContext(
        repo_context=repo_context,
        report_summary=report.get("summary", "") or "",
        overall_assessment=report.get("overall_assessment", "") or "",
        strengths=report.get("strengths", []) or [],
        weaknesses=report.get("weaknesses", []) or [],
        architecture_notes=report.get("architecture_notes", "") or "",
    )
    await redis.set(_key(submission_id), payload.model_dump_json(), ex=_TTL_SECONDS)


async def load_embedding_context(redis: Redis, submission_id: str) -> CachedEmbeddingContext | None:
    raw = await redis.get(_key(submission_id))
    if raw is None:
        return None
    return CachedEmbeddingContext.model_validate_json(raw)
