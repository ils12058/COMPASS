"""Counseling-owned exact Encounter metadata adapter; no ordinary ownership changes."""

from compass.appointments.models import Appointment, AppointmentStatus
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import DeliveryMode, Service


def encounter_revision(encounter):
    return encounter.updated_at.isoformat()


def _lock_encounter(*, encounter_id, student_id, original_counselor_id, now):
    encounter = (
        CounselingEncounter.objects.select_for_update(of=("self",), nowait=True)
        .only(
            "id",
            "student_id",
            "counselor_id",
            "updated_at",
            "service_id",
            "appointment_id",
            "started_at",
            "ended_at",
            "entry_mode",
            "delivery_mode",
        )
        .filter(pk=encounter_id, student_id=student_id, ended_at__lte=now)
        .first()
    )
    if (
        encounter is None
        or encounter.started_at >= encounter.ended_at
        or encounter.entry_mode not in CounselingEntryMode.values
        or encounter.delivery_mode not in DeliveryMode.values
        or (original_counselor_id is not None and encounter.counselor_id != original_counselor_id)
    ):
        raise ContinuityError("source_not_found", 404)
    service = (
        Service.objects.select_for_update(of=("self",), nowait=True)
        .only("id", "code")
        .filter(pk=encounter.service_id)
        .first()
    )
    if service is None or service.code != COUNSELING_SERVICE_CODE:
        raise ContinuityError("source_not_found", 404)
    if encounter.appointment_id is not None:
        parent = (
            Appointment.objects.select_for_update(of=("self",), nowait=True)
            .only("id", "student_id", "provider_id", "service_id", "delivery_mode", "status")
            .filter(pk=encounter.appointment_id)
            .first()
        )
        if (
            parent is None
            or parent.status in {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
            or parent.student_id != student_id
            or parent.provider_id != encounter.counselor_id
            or parent.service_id != encounter.service_id
            or parent.delivery_mode != encounter.delivery_mode
            or encounter.entry_mode != CounselingEntryMode.APPOINTMENT
        ):
            raise ContinuityError("source_not_found", 404)
    elif encounter.entry_mode == CounselingEntryMode.APPOINTMENT:
        raise ContinuityError("source_not_found", 404)
    return encounter, service


def _encounter_projection(encounter):
    return {
        name: getattr(encounter, name)
        for name in (
            "id",
            "started_at",
            "ended_at",
            "entry_mode",
            "delivery_mode",
            "counselor_id",
        )
    }


def read_selected_encounter_for_continuity(
    *,
    actor,
    grant_id,
    encounter_id,
    expected_version,
    context=None,
    actor_session_id=None,
    actor_session_digest=None,
):
    from compass.counseling.continuity_access import read_selected_continuity_record

    return read_selected_continuity_record(
        actor=actor,
        grant_id=grant_id,
        source_id=encounter_id,
        resource_kind="ENCOUNTER",
        projection="ENCOUNTER_METADATA_V1",
        expected_version=expected_version,
        context=context,
        actor_session_id=actor_session_id,
        actor_session_digest=actor_session_digest,
    )
