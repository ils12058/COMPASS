"""Call Slips issued from a counseling case (NS-1).

Issuance stays the ordinary Call Slip service; this module only adds the case/Appointment link
and its rules. Standalone and Referral Call Slips never get a link row and are unchanged.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.utils import timezone

from compass.appointments.models import Appointment
from compass.audit.actions import CALL_SLIP_INTERVIEW_ENDED, COUNSELING_CASE_CALL_SLIP_LINKED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .case_models import CounselingCase, CounselingCaseAppointment
from .case_services import _bump
from .session_proposal_models import (
    CounselingCaseCallSlip,
    CounselingSessionProposal,
    SessionProposalState,
)
from .session_proposal_services import proposer_authority


class CaseCallSlipRefused(Exception):
    """``kind`` is ``not_found``, ``invalid`` or ``conflict``; the Call Slip API maps it."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def lock_case_call_slip_target(
    *,
    actor,
    case_id: UUID,
    appointment_id: UUID | None,
    student_id: UUID,
    at: datetime | None = None,
):
    """Lock and validate the case (and Appointment) a new Call Slip will be linked to.

    Call first in the issuing transaction: case, then Appointment, then users.
    """

    current = at or timezone.now()
    case = CounselingCase.objects.select_for_update().filter(pk=case_id).first()
    if case is None or proposer_authority(actor=actor, case=case, at=current) is None:
        if case is not None and case.primary_counselor_id == actor.pk and case.status != "ACTIVE":
            raise CaseCallSlipRefused("conflict", "This case is closed.")
        raise CaseCallSlipRefused("not_found", "The case was not found.")
    if case.student_id != student_id:
        raise CaseCallSlipRefused("invalid", "The case belongs to a different Student.")
    appointment = None
    proposal = None
    if appointment_id is not None:
        appointment = (
            Appointment.objects.select_for_update(of=("self",)).filter(pk=appointment_id).first()
        )
        linked = CounselingCaseAppointment.objects.filter(
            case_id=case.pk, appointment_id=appointment_id, removed_at__isnull=True
        ).exists()
        if appointment is None or not linked:
            raise CaseCallSlipRefused("not_found", "The case Appointment was not found.")
        if (
            appointment.status != "SCHEDULED"
            or appointment.delivery_mode != "IN_PERSON"
            or appointment.student_id != student_id
        ):
            raise CaseCallSlipRefused(
                "invalid", "A Call Slip can be linked only to a scheduled In person Appointment."
            )
        if CounselingCaseCallSlip.objects.filter(
            appointment_id=appointment.pk, call_slip__voided_at__isnull=True
        ).exists():
            raise CaseCallSlipRefused(
                "conflict", "This Appointment already has an active Call Slip."
            )
        proposal = CounselingSessionProposal.objects.filter(
            appointment_id=appointment.pk, state=SessionProposalState.ACCEPTED
        ).first()
    return case, appointment, proposal


def link_case_call_slip(*, case, appointment, proposal, call_slip, actor, context) -> None:
    CounselingCaseCallSlip.objects.create(
        case=case,
        call_slip=call_slip,
        appointment=appointment,
        proposal=proposal,
        linked_by=actor,
    )
    record_event(
        context=context,
        action=COUNSELING_CASE_CALL_SLIP_LINKED,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case",
        target_id=case.pk,
        metadata={
            "call_slip_id": str(call_slip.pk),
            "appointment_id": str(appointment.pk) if appointment else None,
        },
    )
    _bump(case)


def end_linked_call_slips(*, case, encounter, context, at: datetime) -> int:
    """A session recorded for a linked Appointment ends that Appointment's case Call Slip.

    Runs inside the session-link transaction, after the case lock. Voided or already ended Call
    Slips are untouched. Returns how many were ended.
    """

    if encounter.appointment_id is None:
        return 0
    from compass.call_slips.models import CallSlip

    ids = CounselingCaseCallSlip.objects.filter(
        case_id=case.pk, appointment_id=encounter.appointment_id
    ).values("call_slip_id")
    ended = 0
    for item in CallSlip.objects.select_for_update().filter(
        pk__in=ids, voided_at__isnull=True, interview_ended_at__isnull=True
    ):
        item.interview_ended_at = min(encounter.ended_at, at)
        item.save(update_fields=["interview_ended_at", "updated_at"])
        record_event(
            context=context,
            action=CALL_SLIP_INTERVIEW_ENDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata={
                "destination_type": item.destination_type,
                "issued_by_id": str(item.issued_by_id),
                "via": "case_session",
            },
        )
        ended += 1
    return ended


def case_call_slips(*, actor, case):
    """The case owner's view of Call Slips issued from the case."""

    if actor.pk != case.primary_counselor_id:
        return ()
    return tuple(
        CounselingCaseCallSlip.objects.filter(case_id=case.pk)
        .select_related("call_slip", "appointment")
        .order_by("-linked_at", "-id")
    )
