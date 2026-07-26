"""Mentor chatbot request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import ChatRole


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: ChatRole
    content: str
    created_at: datetime


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    created_at: datetime
    last_message_at: datetime | None
    # Not literal DB columns — computed availability info the frontend needs
    # to render <MentorUnavailableState> without a second round trip
    # (spec Section 9's pre-open availability check).
    mentor_available: bool
    unavailable_reason: str | None
    degraded: bool
