"""Hackathon, criteria, and participant schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.hackathon import HackathonStatus

WEIGHT_SUM_TOLERANCE = Decimal("0.001")


class HackathonSettings(BaseModel):
    allow_private_repos: bool = False
    max_repo_size_mb: int = 50
    evaluation_mode: str = "standard"
    show_rankings_before_finalization: bool = False


class HackathonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_submissions: int = Field(default=100, gt=0)
    settings: HackathonSettings = Field(default_factory=HackathonSettings)


class HackathonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_submissions: int | None = Field(default=None, gt=0)
    settings: HackathonSettings | None = None


class HackathonStatusUpdate(BaseModel):
    status: HackathonStatus


class HackathonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    admin_id: uuid.UUID
    status: HackathonStatus
    start_date: datetime | None
    end_date: datetime | None
    max_submissions: int
    settings: dict
    created_at: datetime
    updated_at: datetime | None


class CriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    weight: Decimal = Field(ge=0, le=1, decimal_places=3)
    agent_id: str | None = Field(default=None, max_length=100)
    display_order: int = 0


class CriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hackathon_id: uuid.UUID
    name: str
    description: str | None
    weight: Decimal
    agent_id: str | None
    display_order: int
    created_at: datetime


class CriteriaBulkReplace(BaseModel):
    """Replaces every criterion for a hackathon in one call. Weights must sum
    to 1.0 (within floating-point tolerance) across the whole set."""

    criteria: list[CriterionCreate] = Field(min_length=1)

    @field_validator("criteria")
    @classmethod
    def weights_sum_to_one(cls, criteria: list[CriterionCreate]) -> list[CriterionCreate]:
        total = sum((c.weight for c in criteria), start=Decimal("0"))
        if abs(total - Decimal("1")) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Criteria weights must sum to 1.0, got {total}")
        return criteria


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hackathon_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime
