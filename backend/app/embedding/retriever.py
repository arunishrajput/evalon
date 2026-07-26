"""pgvector similarity search over a submission's repo_embeddings. Retrieval
itself needs no model — only embedding the query does (spec Section 9, step
9: "Retrieve top-5 chunks by cosine similarity (no model needed)")."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repo_embedding import RepoEmbedding

DEFAULT_TOP_K = 5


async def has_embeddings(db: AsyncSession, submission_id: uuid.UUID) -> bool:
    return (
        await db.scalar(select(RepoEmbedding.id).where(RepoEmbedding.submission_id == submission_id).limit(1))
    ) is not None


async def retrieve_top_chunks(
    db: AsyncSession, submission_id: uuid.UUID, query_embedding: list[float], k: int = DEFAULT_TOP_K
) -> list[RepoEmbedding]:
    rows = await db.scalars(
        select(RepoEmbedding)
        .where(RepoEmbedding.submission_id == submission_id)
        .order_by(RepoEmbedding.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(rows)
