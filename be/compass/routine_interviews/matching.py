"""Shared Routine Interview ↔ Counseling Encounter matching semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.utils import timezone

from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from .models import RoutineInterview


class RoutineEncounterMatchIssue(StrEnum):
    STUDENT = "STUDENT"
    COUNSELOR = "COUNSELOR"
    SERVICE = "SERVICE"
    DELIVERY_MODE = "DELIVERY_MODE"
    NOT_COMPLETED = "NOT_COMPLETED"
    ENTRY_MODE = "ENTRY_MODE"
    APPOINTMENT = "APPOINTMENT"


@dataclass(frozen=True, slots=True)
class RoutineEncounterFacts:
    student_id: UUID
    counselor_id: UUID
    service_code: str
    delivery_mode: str
    ended_at: datetime
    entry_mode: str
    appointment_id: UUID | None


def routine_interview_encounter_match_issue_for_facts(
    *,
    item: RoutineInterview,
    facts: RoutineEncounterFacts,
    now: datetime | None = None,
) -> RoutineEncounterMatchIssue | None:
    current = now or timezone.now()
    if facts.student_id != item.student_id:
        return RoutineEncounterMatchIssue.STUDENT
    if facts.counselor_id != item.counselor_id:
        return RoutineEncounterMatchIssue.COUNSELOR
    if facts.service_code != COUNSELING_SERVICE_CODE:
        return RoutineEncounterMatchIssue.SERVICE
    if facts.delivery_mode != item.delivery_mode:
        return RoutineEncounterMatchIssue.DELIVERY_MODE
    if facts.ended_at > current:
        return RoutineEncounterMatchIssue.NOT_COMPLETED

    if item.appointment_id is not None:
        if facts.entry_mode != CounselingEntryMode.APPOINTMENT:
            return RoutineEncounterMatchIssue.ENTRY_MODE
        if facts.appointment_id != item.appointment_id:
            return RoutineEncounterMatchIssue.APPOINTMENT
        return None

    if facts.appointment_id is not None:
        return RoutineEncounterMatchIssue.APPOINTMENT
    if facts.entry_mode != item.entry_mode:
        return RoutineEncounterMatchIssue.ENTRY_MODE
    return None


def routine_interview_encounter_match_issue(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    now: datetime | None = None,
) -> RoutineEncounterMatchIssue | None:
    return routine_interview_encounter_match_issue_for_facts(
        item=item,
        facts=RoutineEncounterFacts(
            student_id=encounter.student_id,
            counselor_id=encounter.counselor_id,
            service_code=encounter.service.code,
            delivery_mode=encounter.delivery_mode,
            ended_at=encounter.ended_at,
            entry_mode=encounter.entry_mode,
            appointment_id=encounter.appointment_id,
        ),
        now=now,
    )


def routine_interview_encounter_matches(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    now: datetime | None = None,
) -> bool:
    return routine_interview_encounter_match_issue(item=item, encounter=encounter, now=now) is None


__all__ = [
    "RoutineEncounterFacts",
    "RoutineEncounterMatchIssue",
    "routine_interview_encounter_match_issue",
    "routine_interview_encounter_match_issue_for_facts",
    "routine_interview_encounter_matches",
]
