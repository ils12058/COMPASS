"""Atomic composition of Appointment completion and Counseling Encounter recording."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.access import appointment_management_access_allowed
from compass.appointments.models import Appointment, AppointmentStatus
from compass.appointments.services import (
    AppointmentECounselingAccessOpen,
    AppointmentLifecycleConflict,
    AppointmentNotFound,
    InvalidAppointmentInput,
    complete_appointment,
)
from compass.audit.context import AuditContext
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.counseling.services import (
    CounselingAppointmentAlreadyUsed,
    CounselingAppointmentInvalid,
    CounselingError,
    CounselingNotFound,
    CounselingNotPermitted,
    CounselingRoutineInterviewAlreadyLinked,
    CounselingRoutineInterviewMismatch,
    InvalidCounselingInput,
    _normalize_actual_times,
    _normalize_delivery_mode,
    create_encounter,
)
from compass.routine_interviews.matching import RoutineEncounterFacts
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    RoutineInterviewEncounterConflict,
    RoutineInterviewEncounterMismatch,
    RoutineInterviewParentClosed,
    lock_routine_for_encounter_recording,
    validate_encounter_for_routine_context,
)
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import DeliveryMode


class CounselingAppointmentClosed(CounselingError):
    pass


class CounselingFinishConflict(CounselingError):
    pass


class CounselingFinishLifecycleConflict(CounselingError):
    pass


class CounselingFinishECounselingAccessOpen(CounselingError):
    pass


@dataclass(frozen=True, slots=True)
class FinishCounselingResult:
    appointment: Appointment
    encounter: CounselingEncounter
    encounter_result: Literal["CREATED", "EXISTING"]
    routine_interview: RoutineInterview | None
    already_finished: bool


def _encounter_matches(
    *,
    encounter: CounselingEncounter,
    appointment: Appointment,
    delivery_mode: str,
    started_at: datetime,
    ended_at: datetime,
) -> bool:
    return (
        encounter.appointment_id == appointment.pk
        and encounter.student_id == appointment.student_id
        and encounter.counselor_id == appointment.provider_id
        and encounter.service_id == appointment.service_id
        and encounter.delivery_mode == delivery_mode
        and encounter.entry_mode == CounselingEntryMode.APPOINTMENT
        and encounter.started_at == started_at
        and encounter.ended_at == ended_at
    )


def _require_finish_actor(counselor: User) -> None:
    if (
        not counselor.is_active
        or counselor.role.code != "COUNSELOR"
        or not counselor.has_capability("counseling.manage_assigned")
        or not counselor.has_capability("appointments.manage")
    ):
        raise CounselingNotPermitted("Active Counselor access is required.")


def _validate_routine_linkability(
    *,
    routine: RoutineInterview,
    appointment: Appointment,
    delivery_mode: str,
    ended_at: datetime,
    existing_encounter_id: UUID | None,
) -> None:
    """Fail before any write when the deterministic Routine can never link this Encounter."""

    if routine.counseling_encounter_id is not None:
        if routine.counseling_encounter_id != existing_encounter_id:
            raise CounselingRoutineInterviewAlreadyLinked(
                "This Routine Interview is already linked to a different Counseling Encounter."
            )
        return
    try:
        validate_encounter_for_routine_context(
            item=routine,
            facts=RoutineEncounterFacts(
                student_id=appointment.student_id,
                counselor_id=appointment.provider_id,
                service_code=appointment.service.code,
                delivery_mode=delivery_mode,
                ended_at=ended_at,
                entry_mode=CounselingEntryMode.APPOINTMENT,
                appointment_id=appointment.pk,
            ),
        )
    except RoutineInterviewEncounterConflict as exc:
        raise CounselingRoutineInterviewAlreadyLinked(str(exc)) from exc
    except (RoutineInterviewEncounterMismatch, RoutineInterviewParentClosed) as exc:
        raise CounselingRoutineInterviewMismatch(str(exc)) from exc


def finish_counseling_appointment(
    *,
    appointment_id: UUID,
    counselor: User,
    counseling_occurred: bool,
    actual_started_at: datetime,
    actual_ended_at: datetime,
    context: AuditContext,
    now: datetime | None = None,
) -> FinishCounselingResult:
    """Finish one Counseling Appointment and record its single Encounter atomically."""

    if counseling_occurred is not True:
        raise InvalidCounselingInput(
            "The Counselor must confirm that Counseling actually took place."
        )
    normalized_start, normalized_end = _normalize_actual_times(
        actual_started_at, actual_ended_at, now=now
    )
    _require_finish_actor(counselor)

    current = now or timezone.now()

    with transaction.atomic():
        locked_routine = lock_routine_for_encounter_recording(
            counselor=counselor,
            routine_interview_id=None,
            appointment_id=appointment_id,
        )
        appointment = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("service", "student", "provider__role")
            .filter(pk=appointment_id)
            .first()
        )
        if appointment is None:
            raise CounselingNotFound("The requested Appointment was not found.")

        if (
            appointment.provider_id != counselor.pk
            or not appointment.provider.is_active
            or appointment.provider.role.code != "COUNSELOR"
            or not appointment_management_access_allowed(actor=counselor, appointment=appointment)
        ):
            raise CounselingNotFound("The requested Appointment was not found.")

        # The Routine lookup above is unlocked. A Routine created after that lookup and before
        # the Appointment lock would otherwise be locked after the Appointment by the Encounter
        # creation path, inverting the canonical Routine -> Appointment order. The creator cannot
        # commit while this transaction holds the Appointment row, so one recheck closes the race.
        routine_id_now = (
            RoutineInterview.objects.filter(appointment_id=appointment.pk)
            .values_list("pk", flat=True)
            .first()
        )
        locked_routine_pk = locked_routine.pk if locked_routine is not None else None
        if routine_id_now is not None and routine_id_now != locked_routine_pk:
            raise CounselingFinishConflict(
                "The Appointment's Routine Interview state changed; retry the finish request."
            )

        if appointment.status not in {
            AppointmentStatus.SCHEDULED,
            AppointmentStatus.COMPLETED,
        }:
            raise CounselingAppointmentClosed("This Appointment was cancelled or marked no-show.")

        if appointment.service.code != COUNSELING_SERVICE_CODE:
            raise CounselingAppointmentInvalid(
                "The linked Appointment doesn't use the Counseling Service."
            )
        delivery_mode = _normalize_delivery_mode(appointment.delivery_mode)

        existing = (
            CounselingEncounter.objects.select_for_update()
            .filter(appointment_id=appointment.pk)
            .first()
        )
        encounter_existed = existing is not None
        if existing is not None and not _encounter_matches(
            encounter=existing,
            appointment=appointment,
            delivery_mode=delivery_mode,
            started_at=normalized_start,
            ended_at=normalized_end,
        ):
            raise CounselingFinishConflict(
                "This Counseling session has already been recorded with different details. "
                "Review the existing Encounter."
            )

        if locked_routine is not None:
            _validate_routine_linkability(
                routine=locked_routine,
                appointment=appointment,
                delivery_mode=delivery_mode,
                ended_at=normalized_end,
                existing_encounter_id=existing.pk if existing is not None else None,
            )

        if appointment.delivery_mode == DeliveryMode.ONLINE:
            from compass.ecounseling.services import (
                ECounselingJoinState,
                ecounseling_access_window,
            )

            access_window = ecounseling_access_window(appointment, now=current)
            if access_window.state == ECounselingJoinState.OPEN:
                raise CounselingFinishECounselingAccessOpen(
                    "This Counseling Appointment can't be finished while the E-Counseling "
                    "access period is open."
                )

        was_completed = appointment.status == AppointmentStatus.COMPLETED
        try:
            completed_appointment = complete_appointment(
                appointment_id=appointment.pk,
                actor=counselor,
                context=context,
                now=current,
            )
        except AppointmentECounselingAccessOpen as exc:
            raise CounselingFinishECounselingAccessOpen(str(exc)) from exc
        except AppointmentLifecycleConflict as exc:
            raise CounselingFinishLifecycleConflict(str(exc)) from exc
        except AppointmentNotFound as exc:
            raise CounselingNotFound("The requested Appointment was not found.") from exc
        except InvalidAppointmentInput as exc:
            raise InvalidCounselingInput(str(exc)) from exc

        if existing is None:
            try:
                encounter = create_encounter(
                    counselor=counselor,
                    entry_mode=CounselingEntryMode.APPOINTMENT,
                    appointment_id=appointment.pk,
                    started_at=normalized_start,
                    ended_at=normalized_end,
                    context=context,
                )
            except CounselingAppointmentAlreadyUsed:
                concurrent = (
                    CounselingEncounter.objects.select_for_update()
                    .filter(appointment_id=appointment.pk)
                    .first()
                )
                if concurrent is None or not _encounter_matches(
                    encounter=concurrent,
                    appointment=appointment,
                    delivery_mode=delivery_mode,
                    started_at=normalized_start,
                    ended_at=normalized_end,
                ):
                    raise CounselingFinishConflict(
                        "This Counseling session was recorded concurrently with different "
                        "details. Review the existing Encounter."
                    ) from None
                encounter = concurrent
                encounter_existed = True
                encounter_result: Literal["CREATED", "EXISTING"] = "EXISTING"
            else:
                encounter_result = "CREATED"
        else:
            encounter = existing
            encounter_result = "EXISTING"

        if locked_routine is not None:
            linked_encounter_id = (
                RoutineInterview.objects.filter(pk=locked_routine.pk)
                .values_list("counseling_encounter_id", flat=True)
                .first()
            )
            if linked_encounter_id != encounter.pk:
                raise CounselingFinishConflict(
                    "Couldn't link the Routine Interview. Try finishing the Appointment again."
                )
            routine_interview = locked_routine
        else:
            routine_interview = None

        result = FinishCounselingResult(
            appointment=completed_appointment,
            encounter=encounter,
            encounter_result=encounter_result,
            routine_interview=routine_interview,
            already_finished=was_completed and encounter_existed,
        )

    return result
