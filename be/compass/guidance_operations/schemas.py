"""Closed aggregate-only contract. Null is unavailable; zero is an authorized fact."""

from typing import Self

from ninja import Schema
from pydantic import AwareDatetime, ConfigDict, Field, model_validator


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class WaitingMetric(StrictSchema):
    count: int = Field(ge=0)
    oldest_waiting_since: AwareDatetime | None

    @model_validator(mode="after")
    def consistent_oldest(self) -> Self:
        if (self.count == 0) != (self.oldest_waiting_since is None):
            raise ValueError("A waiting population and its oldest timestamp must agree.")
        return self


class DueMetric(StrictSchema):
    count: int = Field(ge=0)
    oldest_due_at: AwareDatetime | None

    @model_validator(mode="after")
    def consistent_oldest(self) -> Self:
        if (self.count == 0) != (self.oldest_due_at is None):
            raise ValueError("A due population and its oldest timestamp must agree.")
        return self


class GuidanceOperationsBacklog(StrictSchema):
    guidance_messages: WaitingMetric | None
    routine_evaluations: WaitingMetric | None
    good_moral_preparation: WaitingMetric | None
    good_moral_issuance: WaitingMetric | None
    call_slips_due: DueMetric | None


class GuidanceOperationsSchedule(StrictSchema):
    upcoming_self_appointments_count: int | None = Field(ge=0)
    upcoming_managed_appointments_count: int | None = Field(ge=0)
    active_call_slips_count: int | None = Field(ge=0)


class GuidanceOperationsResponse(StrictSchema):
    generated_at: AwareDatetime
    backlog: GuidanceOperationsBacklog
    schedule: GuidanceOperationsSchedule
