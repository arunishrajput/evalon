"""Leaderboard rankings — computed live, gated behind hackathon finalization."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class Ranking(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "rankings"
    __table_args__ = (Index("ix_rankings_hackathon_rank", "hackathon_id", "rank"),)

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False, index=True
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    percentile: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 2))
    normalized_score: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3))
    finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finalized_at: Mapped[datetime | None]
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    computation_metadata: Mapped[dict | None] = mapped_column(JSONB)
