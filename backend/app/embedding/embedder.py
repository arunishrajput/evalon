"""Embeds chunks via nomic-embed-text (through LLMProvider) and stores them
as repo_embeddings rows. Acquires the embedding lock ONCE for the whole
batch (spec Stage 7: "Acquires acquire_embedding_lock() ... Generates
embeddings, stores in repo_embeddings ... Releases embedding lock") rather
than per chunk, since the inference model was already unloaded for this
submission's evaluation and there's no benefit to churning the lock."""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_provider import LLMProvider
from app.core.exceptions import ModelUnavailableError
from app.core.model_queue import ModelQueueManager
from app.embedding.chunker import Chunk
from app.models.repo_embedding import RepoEmbedding

logger = logging.getLogger("evalon.embedding")


async def embed_and_store_chunks(
    *,
    db: AsyncSession,
    llm: LLMProvider,
    model_queue: ModelQueueManager,
    submission_id: str,
    chunks: list[Chunk],
    lock_timeout: int = 120,
) -> int:
    """Returns the number of chunks successfully embedded and stored. Raises
    ModelUnavailableError if the embedding lock can't be acquired or Ollama
    is unreachable — callers must treat that as "skip embeddings, don't
    crash the job" per spec Stage 7, not retry indefinitely here."""
    if not chunks:
        return 0

    async with model_queue.acquire_embedding_lock(f"embed:{submission_id}", timeout=lock_timeout):
        rows = []
        for chunk in chunks:
            try:
                vector = await llm.embed(chunk.content)
            except ModelUnavailableError:
                logger.warning("Embedding failed for a %s chunk of submission %s — skipping this chunk", chunk.chunk_type, submission_id)
                continue
            rows.append(
                RepoEmbedding(
                    submission_id=uuid.UUID(submission_id),
                    chunk_type=chunk.chunk_type,
                    chunk_content=chunk.content,
                    embedding=vector,
                    chunk_metadata=chunk.metadata,
                )
            )

    # Replace any prior embeddings for this submission (e.g. a retried evaluation)
    # rather than accumulating duplicates across attempts.
    await db.execute(delete(RepoEmbedding).where(RepoEmbedding.submission_id == uuid.UUID(submission_id)))
    db.add_all(rows)
    await db.flush()
    return len(rows)
