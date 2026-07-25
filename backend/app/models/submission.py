"""A participant's submitted repository and its pipeline progress."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPKMixin


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class Submission(Base, UUIDPKMixin):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("hackathon_id", "user_id", name="uq_hackathon_user_submission"),
        Index("ix_submissions_hackathon_status", "hackathon_id", "status"),
    )

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    repo_name: Mapped[str | None] = mapped_column(String(255))
    repo_description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status", native_enum=True),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    degraded: Mapped[bool] = mapped_column(default=False, nullable=False)
    degraded_reason: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    clone_completed_at: Mapped[datetime | None]
    analysis_completed_at: Mapped[datetime | None]
    evaluation_completed_at: Mapped[datetime | None]
