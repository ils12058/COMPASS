"""Closed, privacy-minimized wire contract for the read-only Guidance work projection."""

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


class WorkKind(StrEnum):
    GUIDANCE_MESSAGE_REPLY = "GUIDANCE_MESSAGE_REPLY"
    ROUTINE_EVALUATION = "ROUTINE_EVALUATION"
    GOOD_MORAL_PREPARATION = "GOOD_MORAL_PREPARATION"
    GOOD_MORAL_ISSUANCE = "GOOD_MORAL_ISSUANCE"
    CALL_SLIP_DUE = "CALL_SLIP_DUE"


class WorkPriority(StrEnum):
    TIME_SENSITIVE = "TIME_SENSITIVE"
    ACTION_REQUIRED = "ACTION_REQUIRED"


class WorkStudent(StrictSchema):
    id: UUID
    display_name: str


class WorkItem(StrictSchema):
    id: str
    kind: WorkKind
    priority: WorkPriority
    source_id: UUID
    student: WorkStudent
    conversation_kind: ThreadKind | None
    due_at: datetime | None
    waiting_since: datetime | None


class WorkQueueQuery(StrictSchema):
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)


class WorkQueueResponse(StrictSchema):
    items: list[WorkItem]
    page: int
    page_size: int
    has_next: bool
    generated_at: datetime
