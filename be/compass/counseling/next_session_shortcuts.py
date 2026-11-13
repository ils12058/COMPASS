"""NS-1 shortcuts from a Follow-up or a case: Message student, Issue Call Slip, Propose session.

Shortcuts only point at existing, separately authorized workflows. None creates a conversation,
adds a participant, issues, books or completes anything, and none carries task narrative.
"""

from __future__ import annotations

from django.db.models import F

from .case_models import CounselingCase
from .session_proposal_models import CounselingSessionProposal, SessionProposalState
from .session_proposal_services import may_propose


def counseling_thread_id(actor, student_id):
    """The reader's most recent existing Counseling conversation with the Student, if any."""

    from compass.guidance_messages.errors import GuidanceMessagesError
    from compass.guidance_messages.models import ThreadKind
    from compass.guidance_messages.policy import authorized_threads

    if actor.role.code != "COUNSELOR":
        return None
    try:
        threads = authorized_threads(actor)
    except GuidanceMessagesError:
        return None
    row = (
        threads.filter(kind=ThreadKind.COUNSELING, student_id=student_id, counselor_id=actor.pk)
        .order_by(F("last_message_at").desc(nulls_last=True), "-created_at", "-id")
        .values_list("pk", flat=True)
        .first()
    )
    return row


def may_issue_call_slip(actor, student_id) -> bool:
    from compass.call_slips.services import OPERATIONAL_ROLES, _student_in_scope

    return bool(
        actor.is_active
        and actor.role.code in OPERATIONAL_ROLES
        and actor.has_capability("call_slips.manage")
        and _student_in_scope(actor, student_id)
    )


def may_link_case_call_slip(actor, case) -> bool:
    return bool(
        actor.role.code == "COUNSELOR"
        and may_issue_call_slip(actor, case.student_id)
        and may_propose(actor=actor, case=case)
    )


def _completion_prompt(item):
    proposal = (
        CounselingSessionProposal.objects.filter(
            follow_up_id=item.pk, state=SessionProposalState.ACCEPTED
        )
        .select_related("appointment")
        .order_by("-decided_at", "-id")
        .first()
    )
    if proposal is None or proposal.appointment is None:
        return None
    appointment = proposal.appointment
    from .models import CounselingEncounter

    recorded = CounselingEncounter.objects.filter(
        appointment_id=appointment.pk,
        case_links__case_id=proposal.case_id,
        case_links__removed_at__isnull=True,
    ).exists()
    return {
        "reason": "SESSION_RECORDED" if recorded else "SESSION_ACCEPTED",
        "appointment_id": appointment.pk,
        "appointment_reference": appointment.reference_code,
    }


def followup_shortcuts(actor, item):
    """Shortcuts for a pending Follow-up the reader may manage; ``None`` otherwise."""

    from compass.guidance_followups import policy

    if item.status != "PENDING" or not policy.authorized(actor, item, manage=True):
        return None
    case = None
    if item.case_id is not None:
        case = CounselingCase.objects.filter(pk=item.case_id).first()
    call_slip_case_id = case.pk if case and may_link_case_call_slip(actor, case) else None
    return {
        "message_thread_id": counseling_thread_id(actor, item.student_id),
        "can_issue_call_slip": may_issue_call_slip(actor, item.student_id),
        "call_slip_case_id": call_slip_case_id,
        "propose_session_case_id": (
            case.pk if case is not None and may_propose(actor=actor, case=case) else None
        ),
        "completion_prompt": _completion_prompt(item),
    }
