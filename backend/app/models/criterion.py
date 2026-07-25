"""Judging criteria — admin-defined, weighted, optionally mapped to an agent."""

import uuid

from sqlalchemy import DECIMAL, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class Criterion(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "criteria"

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hackathons.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # 0.000 to 1.000 — all criteria for a hackathon must sum to 1.0 (enforced in API layer)
    weight: Mapped[float] = mapped_column(DECIMAL(4, 3), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(100))  # maps to agent registry key
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    hackathon: Mapped["Hackathon"] = relationship(back_populates="criteria")  # noqa: F821
