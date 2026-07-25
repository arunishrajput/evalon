"""Hackathon lifecycle: the hackathon itself, its participant roster, and its
pre-computed dashboard stats."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, UpdatedAtMixin, UUIDPKMixin


class HackathonStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EVALUATING = "evaluating"
    FINALIZED = "finalized"


class Hackathon(Base, UUIDPKMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "hackathons"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    admin_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[HackathonStatus] = mapped_column(
        Enum(HackathonStatus, name="hackathon_status", native_enum=True),
        default=HackathonStatus.DRAFT,
        nullable=False,
    )
    start_date: Mapped[datetime | None]
    end_date: Mapped[datetime | None]
    max_submissions: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    # settings schema: { "allow_private_repos": bool, "max_repo_size_mb": int,
    # "evaluation_mode": str, "show_rankings_before_finalization": bool }
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="hackathon", cascade="all, delete-orphan", order_by="Criterion.display_order"
    )
    participants: Mapped[list["HackathonParticipant"]] = relationship(
        back_populates="hackathon", cascade="all, delete-orphan"
    )


class HackathonParticipant(Base, UUIDPKMixin):
    __tablename__ = "hackathon_participants"
    __table_args__ = (UniqueConstraint("hackathon_id", "user_id", name="uq_hackathon_user_participant"),)

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    hackathon: Mapped["Hackathon"] = relationship(back_populates="participants")


class HackathonStats(Base, UUIDPKMixin):
    __tablename__ = "hackathon_stats"

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hackathons.id"), unique=True, nullable=False
    )
    total_submissions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluations_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluations_in_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluations_queued: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluations_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # { "0-10": 0, "10-20": 0, ..., "90-100": 0 }
    score_distribution: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # { "React": 12, "FastAPI": 8, ... }
    tech_stack_frequency: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    avg_score: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3))
    top5_preview: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
