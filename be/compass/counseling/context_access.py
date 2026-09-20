"""Derived, time-bounded Counseling Context authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.routine_interviews.matching import routine_interview_encounter_matches
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from .models import CounselingEncounter, CounselingEntryMode


class CounselingContextSource(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    ROUTINE_INTERVIEW = "ROUTINE_INTERVIEW"


class CounselingContextNotFound(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CounselingContextAccess:
    student_id: UUID
    counselor_id: UUID
    source_type: CounselingContextSource
    source_id: UUID
    valid_from: datetime
    valid_until: datetime
    entry_mode: str
    delivery_mode: str
    appointment_id: UUID | None = None
    routine_interview_id: UUID | None = None
    encounter_id: UUID | None = None


def _not_found() -> CounselingContextNotFound:
    return CounselingContextNotFound("The requested Counseling Context was not found.")


def _require_context_actor(actor: User, *, at: datetime) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("counseling.view_assigned", at=at)
    ):
        raise _not_found()


def _appointment_matching_encounter(
    appointment: Appointment,
    *,
    base_valid_until: datetime,
    now: datetime,
) -> CounselingEncounter | None:
    return (
        CounselingEncounter.objects.select_related("service")
        .filter(
            appointment_id=appointment.pk,
            student_id=appointment.student_id,
            counselor_id=appointment.provider_id,
            service__code=COUNSELING_SERVICE_CODE,
            entry_mode=CounselingEntryMode.APPOINTMENT,
            delivery_mode=appointment.delivery_mode,
            ended_at__lte=now,
            ended_at__gte=appointment.starts_at
            - timedelta(hours=settings.COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS),
            started_at__lte=base_valid_until,
        )
        .order_by("ended_at", "id")
        .first()
    )


def _resolve_appointment_context(
    *,
    actor: User,
    appointment_id: UUID,
    now: datetime,
) -> CounselingContextAccess:
    appointment = (
        Appointment.objects.select_related("student__role", "provider__role", "service")
        .filter(pk=appointment_id)
        .first()
    )
    if (
        appointment is None
        or appointment.service.code != COUNSELING_SERVICE_CODE
        or appointment.provider_id != actor.pk
        or appointment.status != AppointmentStatus.SCHEDULED
    ):
        raise _not_found()

    valid_from = appointment.starts_at - timedelta(
        hours=settings.COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS
    )
    base_valid_until = appointment.ends_at + timedelta(
        hours=settings.COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS
    )
    encounter = _appointment_matching_encounter(
        appointment,
        base_valid_until=base_valid_until,
        now=now,
    )
    valid_until = (
        encounter.ended_at + timedelta(days=settings.COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS)
        if encounter is not None
        else base_valid_until
    )
    if now < valid_from or now > valid_until:
        raise _not_found()

    routine_interview_id = (
        RoutineInterview.objects.filter(appointment_id=appointment.pk)
        .values_list("pk", flat=True)
        .first()
    )
    return CounselingContextAccess(
        student_id=appointment.student_id,
        counselor_id=appointment.provider_id,
        source_type=CounselingContextSource.APPOINTMENT,
        source_id=appointment.pk,
        valid_from=valid_from,
        valid_until=valid_until,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        delivery_mode=appointment.delivery_mode,
        appointment_id=appointment.pk,
        routine_interview_id=routine_interview_id,
        encounter_id=encounter.pk if encounter is not None else None,
    )


def _candidate_direct_encounter(
    item: RoutineInterview,
    *,
    activation_at: datetime,
    base_valid_until: datetime,
    now: datetime,
) -> CounselingEncounter | None:
    if item.counseling_encounter_id is not None:
        linked = (
            CounselingEncounter.objects.select_related("service")
            .filter(pk=item.counseling_encounter_id)
            .first()
        )
        if (
            linked is not None
            and linked.ended_at >= activation_at
            and linked.started_at <= base_valid_until
            and routine_interview_encounter_matches(item=item, encounter=linked, now=now)
        ):
            return linked

    candidates = (
        CounselingEncounter.objects.select_related("service")
        .filter(
            student_id=item.student_id,
            counselor_id=item.counselor_id,
            appointment__isnull=True,
            service__code=COUNSELING_SERVICE_CODE,
            entry_mode=item.entry_mode,
            delivery_mode=item.delivery_mode,
            ended_at__lte=now,
            ended_at__gte=activation_at,
            started_at__lte=base_valid_until,
        )
        .order_by("ended_at", "id")
    )
    for encounter in candidates[:5]:
        if routine_interview_encounter_matches(item=item, encounter=encounter, now=now):
            return encounter
    return None


def _resolve_routine_interview_context(
    *,
    actor: User,
    routine_interview_id: UUID,
    now: datetime,
) -> CounselingContextAccess:
    item = (
        RoutineInterview.objects.select_related(
            "student__role",
            "counselor__role",
            "inventory__academic_year",
            "appointment",
            "counseling_encounter__service",
        )
        .filter(pk=routine_interview_id)
        .first()
    )
    if (
        item is None
        or item.counselor_id != actor.pk
        or item.appointment_id is not None
        or item.entry_mode
        not in {
            CounselingEntryMode.WALK_IN,
            CounselingEntryMode.CALLED_IN,
            CounselingEntryMode.REFERRED,
        }
        or item.intake_submitted_at is None
    ):
        raise _not_found()

    valid_from = item.intake_submitted_at
    base_valid_until = valid_from + timedelta(
        hours=settings.COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS
    )
    encounter = _candidate_direct_encounter(
        item,
        activation_at=valid_from,
        base_valid_until=base_valid_until,
        now=now,
    )
    valid_until = (
        encounter.ended_at + timedelta(days=settings.COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS)
        if encounter is not None
        else base_valid_until
    )
    if now < valid_from or now > valid_until:
        raise _not_found()

    return CounselingContextAccess(
        student_id=item.student_id,
        counselor_id=item.counselor_id,
        source_type=CounselingContextSource.ROUTINE_INTERVIEW,
        source_id=item.pk,
        valid_from=valid_from,
        valid_until=valid_until,
        entry_mode=item.entry_mode,
        delivery_mode=item.delivery_mode,
        routine_interview_id=item.pk,
        encounter_id=encounter.pk if encounter is not None else None,
    )


def resolve_counseling_context(
    *,
    actor: User,
    anchor_type: CounselingContextSource | str,
    anchor_id: UUID,
    now: datetime | None = None,
) -> CounselingContextAccess:
    current = now or timezone.now()
    _require_context_actor(actor, at=current)
    try:
        source = (
            anchor_type
            if isinstance(anchor_type, CounselingContextSource)
            else CounselingContextSource(anchor_type)
        )
    except ValueError as exc:
        raise _not_found() from exc

    if source == CounselingContextSource.APPOINTMENT:
        return _resolve_appointment_context(actor=actor, appointment_id=anchor_id, now=current)
    return _resolve_routine_interview_context(
        actor=actor,
        routine_interview_id=anchor_id,
        now=current,
    )


__all__ = [
    "CounselingContextAccess",
    "CounselingContextNotFound",
    "CounselingContextSource",
    "resolve_counseling_context",
]
