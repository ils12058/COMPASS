"""Shared Routine Interview ↔ Counseling Encounter matching semantics."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

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


def routine_interview_encounter_match_issue(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    now: datetime | None = None,
) -> RoutineEncounterMatchIssue | None:
    current = now or timezone.now()
    if encounter.student_id != item.student_id:
        return RoutineEncounterMatchIssue.STUDENT
    if encounter.counselor_id != item.counselor_id:
        return RoutineEncounterMatchIssue.COUNSELOR
    if encounter.service.code != COUNSELING_SERVICE_CODE:
        return RoutineEncounterMatchIssue.SERVICE
    if encounter.delivery_mode != item.delivery_mode:
        return RoutineEncounterMatchIssue.DELIVERY_MODE
    if encounter.ended_at > current:
        return RoutineEncounterMatchIssue.NOT_COMPLETED

    if item.appointment_id is not None:
        if encounter.entry_mode != CounselingEntryMode.APPOINTMENT:
            return RoutineEncounterMatchIssue.ENTRY_MODE
        if encounter.appointment_id != item.appointment_id:
            return RoutineEncounterMatchIssue.APPOINTMENT
        return None

    if encounter.appointment_id is not None:
        return RoutineEncounterMatchIssue.APPOINTMENT
    if encounter.entry_mode != item.entry_mode:
        return RoutineEncounterMatchIssue.ENTRY_MODE
    return None


def routine_interview_encounter_matches(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    now: datetime | None = None,
) -> bool:
    return routine_interview_encounter_match_issue(item=item, encounter=encounter, now=now) is None


__all__ = [
    "RoutineEncounterMatchIssue",
    "routine_interview_encounter_match_issue",
    "routine_interview_encounter_matches",
]
