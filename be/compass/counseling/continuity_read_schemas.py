"""Fixed selected-read wire inventories; unrelated source fields default absent."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from compass.counseling.models import CounselingEntryMode
from compass.service_catalog.models import DeliveryMode


class SelectedReadSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class SelectedReadProvenance(SelectedReadSchema):
    grant_id: UUID
    grant_version: int


class SelectedEncounterFields(SelectedReadSchema):
    id: UUID
    started_at: datetime
    ended_at: datetime
    entry_mode: CounselingEntryMode
    delivery_mode: DeliveryMode
    counselor_id: UUID


class ContinuitySelectedEncounterResponse(SelectedReadProvenance):
    projection: Literal["ENCOUNTER_METADATA_V1"]
    encounter: SelectedEncounterFields


class SelectedEvaluationFields(SelectedReadSchema):
    academic_adjustment_rating: int | None = Field(default=None, ge=1, le=10)
    recommendations: str | None = None


class ContinuitySelectedEvaluationResponse(SelectedReadProvenance):
    projection: Literal["FINALIZED_EVALUATION_V1"]
    routine_interview_id: UUID
    evaluation: SelectedEvaluationFields
