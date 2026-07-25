"""Per-agent evaluation output: score, evidence, and abstain/fallback state."""

import uuid
from decimal import Decimal

from sqlalchemy import DECIMAL, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class AgentResult(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "agent_results"
    __table_args__ = (Index("ix_agent_results_evaluation_agent", "evaluation_id", "agent_id"),)

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("criteria.id")
    )
    score_raw: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3))
    confidence: Mapped[Decimal | None] = mapped_column(DECIMAL(4, 3))
    # List[{ finding: str, impact: str, file_ref: str }]
    evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    strengths: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    top_evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    abstain_reason: Mapped[str | None] = mapped_column(Text)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(100))
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="agent_results")  # noqa: F821
