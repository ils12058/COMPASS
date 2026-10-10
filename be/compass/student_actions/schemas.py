"""Closed, structural Student Actions wire contract."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from compass.guidance_messages.models import ThreadKind

MAX_PAGE = 100
MAX_PAGE_SIZE = 50


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class StudentActionKind(StrEnum):
    INVENTORY_START = "INVENTORY_START"
    INVENTORY_CONTINUE = "INVENTORY_CONTINUE"
    ROUTINE_INTAKE = "ROUTINE_INTAKE"
    EXIT_INTERVIEW_START = "EXIT_INTERVIEW_START"
    EXIT_INTERVIEW_CONTINUE = "EXIT_INTERVIEW_CONTINUE"
    EXIT_INTERVIEW_CORRECTION = "EXIT_INTERVIEW_CORRECTION"
    GRADUATE_TRACER_CONTINUE = "GRADUATE_TRACER_CONTINUE"
    CALL_SLIP_ACTIVE = "CALL_SLIP_ACTIVE"
    ECOUNSELING_CONSENT = "ECOUNSELING_CONSENT"
    ECOUNSELING_JOIN = "ECOUNSELING_JOIN"
    GUIDANCE_MESSAGE_UNREAD = "GUIDANCE_MESSAGE_UNREAD"


class StudentActionPriority(StrEnum):
    TIME_SENSITIVE = "TIME_SENSITIVE"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    INCOMPLETE_SELF_SERVICE = "INCOMPLETE_SELF_SERVICE"


class StudentActionItem(StrictSchema):
    id: str
    kind: StudentActionKind
    priority: StudentActionPriority
    source_id: UUID
    due_at: datetime | None
    waiting_since: datetime | None
    conversation_kind: ThreadKind | None
    pending_count: int | None = Field(ge=1)


class StudentActionsQuery(StrictSchema):
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)


class StudentActionsResponse(StrictSchema):
    items: list[StudentActionItem]
    page: int
    page_size: int
    has_next: bool
    generated_at: datetime
