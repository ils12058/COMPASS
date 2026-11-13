"""Explicit case/Appointment links, independent of booking and Appointment lifecycle."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from .case_models import CounselingCaseAppointment, CounselingCaseAppointmentRemovalReason
from .case_services import (
    MANAGE_CAPABILITY,
    CounselingCaseError,
    CounselingCaseInvalid,
    CounselingCaseNotFound,
    _accessible_cases,
    _bump,
    _expected_version,
    _lock_case,
    _lock_users,
    _require_actor,
    _validate_page,
)


class CounselingCaseAppointmentNotFound(CounselingCaseError):
    code = "counseling_case_appointment_not_found"
    status = 404


class CounselingCaseAppointmentInvalid(CounselingCaseError):
    code = "counseling_case_appointment_ineligible"


class CounselingCaseAppointmentAlreadyLinked(CounselingCaseError):
    code = "counseling_case_appointment_already_linked"


@dataclass(frozen=True, slots=True)
class AppointmentCandidatePage:
    items: tuple[Appointment, ...]
    page: int
    page_size: int
    has_next: bool


def current_links():
    return CounselingCaseAppointment.objects.filter(removed_at__isnull=True)


def eligible_appointments(*, actor, case):
    query = Appointment.objects.filter(
        student_id=case.student_id,
        provider_id=case.primary_counselor_id,
        service__code=COUNSELING_SERVICE_CODE,
        status="SCHEDULED",
    )
    if case.primary_counselor_id != actor.pk or not actor.has_capability("appointments.view_self"):
        return query.none()
    return query


def appointment_accessible(*, actor, case, appointment):
    return (
        actor.has_capability("appointments.view_self")
        and appointment.provider_id == actor.pk == case.primary_counselor_id
        and appointment.student_id == case.student_id
        and appointment.service.code == COUNSELING_SERVICE_CODE
    )


def list_appointment_candidates(*, actor, case_id, page=1, page_size=20):
    _require_actor(actor, MANAGE_CAPABILITY)
    page, page_size = _validate_page(page, page_size)
    case = _accessible_cases(actor).filter(pk=case_id, status="ACTIVE").first()
    if case is None:
        raise CounselingCaseNotFound("The requested Active case was not found.")
    query = (
        eligible_appointments(actor=actor, case=case)
        .alias(_linked=Exists(current_links().filter(appointment_id=OuterRef("pk"))))
        .filter(_linked=False)
        .select_related("service", "provider")
        .order_by("starts_at", "id")
    )
    offset = (page - 1) * page_size
    rows = list(query[offset : offset + page_size + 1])
    return AppointmentCandidatePage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def create_link(*, case, appointment, actor, context, at):
    """Caller holds the case/Appointment/actor locks (or has just created the case)."""
    if appointment.status != "SCHEDULED" or not appointment_accessible(
        actor=actor, case=case, appointment=appointment
    ):
        raise CounselingCaseAppointmentInvalid(
            "Choose a scheduled Counseling Appointment for this Student and primary Counselor."
        )
    if current_links().filter(appointment_id=appointment.pk).exists():
        raise CounselingCaseAppointmentAlreadyLinked("This Appointment already belongs to a case.")
    try:
        with transaction.atomic():
            link = CounselingCaseAppointment.objects.create(
                case=case, appointment=appointment, linked_by=actor, linked_at=at
            )
    except IntegrityError as exc:
        raise CounselingCaseAppointmentAlreadyLinked(
            "This Appointment already belongs to a case."
        ) from exc
    record_event(
        context=context,
        action="counseling.case.appointment_linked",
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case",
        target_id=case.pk,
        metadata={"appointment_id": str(appointment.pk)},
    )
    _bump(case)
    return link


def link_appointment(
    *,
    actor,
    case_id: UUID,
    appointment_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
):
    version = _expected_version(expected_version)
    at = now or timezone.now()
    # Lock order: case, Appointment, participants. Two cases serialize on the Appointment.
    with transaction.atomic():
        case = _lock_case(actor=actor, case_id=case_id, expected_version=version)
        appointment = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("service")
            .filter(pk=appointment_id, provider_id=actor.pk)
            .first()
        )
        if appointment is None:
            raise CounselingCaseAppointmentNotFound("The requested Appointment was not found.")
        locked = _lock_users(actor.pk, case.student_id)
        actor = locked[actor.pk]
        _require_actor(actor, MANAGE_CAPABILITY, at=at)
        if not locked[case.student_id].is_active:
            raise CounselingCaseAppointmentInvalid("The Student's account isn't active.")
        create_link(case=case, appointment=appointment, actor=actor, context=context, at=at)
    return case


def unlink_appointment(
    *,
    actor,
    case_id: UUID,
    appointment_id: UUID,
    reason: str,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
):
    version = _expected_version(expected_version)
    if reason not in CounselingCaseAppointmentRemovalReason.values:
        raise CounselingCaseInvalid("Choose why this Appointment doesn't belong in the case.")
    at = now or timezone.now()
    with transaction.atomic():
        case = _lock_case(actor=actor, case_id=case_id, expected_version=version)
        # Lock the Appointment even when its current provider/status no longer makes it eligible.
        appointment = Appointment.objects.select_for_update().filter(pk=appointment_id).first()
        if appointment is None:
            raise CounselingCaseAppointmentNotFound("The current Appointment link was not found.")
        link = current_links().filter(case_id=case.pk, appointment_id=appointment_id).first()
        if link is None:
            raise CounselingCaseAppointmentNotFound("The current Appointment link was not found.")
        actor = _lock_users(actor.pk)[actor.pk]
        _require_actor(actor, MANAGE_CAPABILITY, at=at)
        link.removed_at = at
        link.removed_by = actor
        link.removal_reason = reason
        link.save(update_fields=["removed_at", "removed_by", "removal_reason"])
        record_event(
            context=context,
            action="counseling.case.appointment_unlinked",
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.case",
            target_id=case.pk,
            metadata={"appointment_id": str(appointment_id), "reason": reason},
        )
        _bump(case)
    return case
