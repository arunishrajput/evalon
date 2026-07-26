"""Evaluation and per-agent-result read schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.evaluation import EvaluationStatus


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    hackathon_id: uuid.UUID
    status: EvaluationStatus
    final_score: Decimal | None
    report: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    model_versions: dict | None
    agents_completed: list[str]
    agents_abstained: list[str]
    created_at: datetime


class AgentResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: str
    criterion_id: uuid.UUID | None
    score_raw: Decimal | None
    confidence: Decimal | None
    evidence: list
    strengths: list
    weaknesses: list
    top_evidence: list
    reasoning: str | None
    abstained: bool
    abstain_reason: str | None
    fallback_used: bool
    processing_time_ms: int | None
    created_at: datetime
