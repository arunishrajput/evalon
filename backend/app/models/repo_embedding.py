"""Chunked, embedded repository content for RAG retrieval by the mentor
chatbot. Embedding dimension (768) matches nomic-embed-text."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

EMBEDDING_DIMENSION = 768


class RepoEmbedding(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "repo_embeddings"
    __table_args__ = (
        Index(
            "ix_repo_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False, index=True
    )
    chunk_type: Mapped[str | None] = mapped_column(String(100))
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
