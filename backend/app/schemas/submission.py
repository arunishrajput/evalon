"""Submission API schemas, plus the cached-analysis-result shape shared
between the ingestion job and the (Phase 4) evaluation job."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.submission import SubmissionStatus
from app.pipeline.static_analysis import StaticAnalysisReport


class SubmissionCreate(BaseModel):
    hackathon_id: uuid.UUID
    repo_url: str = Field(min_length=1, max_length=500)


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hackathon_id: uuid.UUID
    user_id: uuid.UUID
    repo_url: str
    repo_name: str | None
    repo_description: str | None
    tech_stack: list[str]
    status: SubmissionStatus
    error_message: str | None
    degraded: bool
    degraded_reason: str | None
    submitted_at: datetime
    clone_completed_at: datetime | None
    analysis_completed_at: datetime | None
    evaluation_completed_at: datetime | None


class CachedAnalysisResult(BaseModel):
    project_type: str
    primary_language: str | None
    language_breakdown: dict[str, int]
    dependency_manifest: dict[str, list[str]]
    readme_content: str | None
    readme_quality_score: int
    tech_stack: list[str]
    static_analysis: StaticAnalysisReport
