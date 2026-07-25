"""The evaluation record for a submission: aggregate status, final score, and
the assembled report."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class EvaluationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class Evaluation(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "evaluations"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), unique=True, nullable=False, index=True
    )
    hackathon_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("hackathons.id"))
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status", native_enum=True),
        default=EvaluationStatus.PENDING,
        nullable=False,
    )
    final_score: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3))
    report: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    model_versions: Mapped[dict | None] = mapped_column(JSONB)
    agents_completed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    agents_abstained: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    agent_results: Mapped[list["AgentResult"]] = relationship(  # noqa: F821
        back_populates="evaluation", cascade="all, delete-orphan"
    )
