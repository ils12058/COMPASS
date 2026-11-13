"""NS-1: Counselor-proposed next sessions with Student consent.

Rules kept here:

* A proposal never reserves a slot. Proposing only checks that each time is bookable now.
* Only the Student's acceptance books, through ``create_student_appointment`` with no bypass.
  The case row, then the proposal row, are locked first, so concurrent accepts serialize and at
  most one Appointment is created.
* Closed cases refuse proposals; a proposal whose case closed or whose proposer lost authority
  cannot be accepted.
* Nothing is booked, issued or completed automatically. A proposal that is not answered by its
  expiry simply stops being acceptable.
* Notifications and audit carry identifiers and closed codes only, never case narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.appointments.models import Appointment
from compass.appointments.services import (
    AppointmentCurrentAcademicYearNotConfigured,
    AppointmentCurrentInventoryRequired,
    AppointmentCurrentStudentRequired,
    AppointmentError,
    AppointmentTimeConflict,
    AppointmentTimeUnavailable,
    check_offerable_interval,
    create_student_appointment,
    list_offerable_slots,
)
from compass.audit.actions import (
    COUNSELING_CASE_APPOINTMENT_LINKED,
    SESSION_PROPOSAL_ACCEPTED,
    SESSION_PROPOSAL_CREATED,
    SESSION_PROPOSAL_DECLINED,
    SESSION_PROPOSAL_WITHDRAWN,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import create_notification_for_event
from compass.organization.integrity import catalog_dependent_write
from compass.service_catalog.models import DeliveryMode

from . import case_continuity_rules as rules
from .case_coverage_models import CounselingCaseCoverage
from .case_models import CounselingCase, CounselingCaseAppointment, CounselingCaseStatus
from .case_services import (
    MANAGE_CAPABILITY,
    VIEW_CAPABILITY,
    CounselingCaseChanged,
    CounselingCaseClosed,
    CounselingCaseError,
    CounselingCaseNotFound,
    CounselingCaseNotPermitted,
    _bump,
    _lock_users,
)
from .services import CounselingConfigurationConflict, get_counseling_service
from .session_proposal_models import (
    MAX_PROPOSAL_OPTIONS,
    CounselingSessionProposal,
    CounselingSessionProposalOption,
    SessionProposalPurpose,
    SessionProposalState,
)

MAX_OPEN_PERIOD = timedelta(days=7)
STUDENT_CAPABILITY = "appointments.manage_self"


class SessionProposalError(CounselingCaseError):
    code = "session_proposal_error"
    status = 409


class SessionProposalNotFound(SessionProposalError):
    code = "session_proposal_not_found"
    status = 404


class SessionProposalInvalid(SessionProposalError):
    code = "session_proposal_invalid"
    status = 422


class SessionProposalOpen(SessionProposalError):
    code = "session_proposal_open"


class SessionProposalClosed(SessionProposalError):
    """No longer waiting for the Student: answered, withdrawn or expired."""

    code = "session_proposal_closed"


class SessionProposalChanged(SessionProposalError):
    code = "session_proposal_changed"


class SessionProposalUnavailable(SessionProposalError):
    """The case closed, or the proposing Counselor may no longer offer this session."""

    code = "session_proposal_unavailable"


class SessionProposalTimeUnavailable(SessionProposalError):
    """An offered time can't be booked. ``option`` names it (1-based) when proposing."""

    code = "session_proposal_time_unavailable"

    def __init__(self, message: str, *, option: int | None = None, reason: str = "") -> None:
        super().__init__(message)
        self.option = option
        self.reason = reason


class SessionProposalStudentAction(SessionProposalError):
    """The Student must do something first (for example, submit the Inventory)."""

    code = "session_proposal_student_action_required"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class OptionInput:
    delivery_mode: str
    starts_at: datetime


# ---------------------------------------------------------------------------
# Authority (D1): the case owner; a covering Counselor only while coverage is active.


def _counselor(actor, *, capability: str, at: datetime) -> bool:
    return bool(
        getattr(actor, "pk", None)
        and actor.is_active
        and actor.role.code == "COUNSELOR"
        and actor.has_capability(capability, at=at)
    )


def active_coverage(*, actor, case, at: datetime) -> CounselingCaseCoverage | None:
    return (
        CounselingCaseCoverage.objects.filter(
            case_id=case.pk,
            receiving_counselor_id=actor.pk,
            primary_counselor_id=case.primary_counselor_id,
            state="ACCEPTED",
            starts_at__lte=at,
            expires_at__gt=at,
        )
        .order_by("starts_at", "id")
        .first()
    )


def proposer_authority(*, actor, case, at: datetime) -> str | None:
    """``OWNER``, ``COVERAGE`` or ``None``. Closed cases give no one authority."""

    if case.status != CounselingCaseStatus.ACTIVE:
        return None
    if not _counselor(actor, capability=MANAGE_CAPABILITY, at=at):
        return None
    if not actor.has_capability("appointments.view_self", at=at):
        return None
    if case.primary_counselor_id == actor.pk:
        return "OWNER"
    if rules.receiver_eligible(actor, at) and active_coverage(actor=actor, case=case, at=at):
        return "COVERAGE"
    return None


def may_propose(*, actor, case, at: datetime | None = None) -> bool:
    return proposer_authority(actor=actor, case=case, at=at or timezone.now()) is not None


def effective_state(proposal: CounselingSessionProposal, *, at: datetime | None = None) -> str:
    """A pending proposal past its expiry, or on a closed case, reads as EXPIRED; no job runs."""

    if proposal.state == SessionProposalState.PENDING and (
        proposal.expires_at <= (at or timezone.now())
        or proposal.case.status != CounselingCaseStatus.ACTIVE
    ):
        return SessionProposalState.EXPIRED
    return proposal.state


def _expire_stale(*, case_id: UUID, at: datetime) -> None:
    CounselingSessionProposal.objects.filter(
        case_id=case_id, state=SessionProposalState.PENDING, expires_at__lte=at
    ).update(state=SessionProposalState.EXPIRED, decided_at=at, version=F("version") + 1)


def _queryset():
    return CounselingSessionProposal.objects.select_related(
        "case",
        "student",
        "student__role",
        "proposed_by",
        "proposed_by__role",
        "service",
        "appointment",
        "follow_up",
    ).prefetch_related("options")


# ---------------------------------------------------------------------------
# Staff reads


def _staff_reader(actor, proposal, *, at: datetime) -> bool:
    if not _counselor(actor, capability=VIEW_CAPABILITY, at=at):
        return False
    return actor.pk in (proposal.proposed_by_id, proposal.case.primary_counselor_id)


def get_staff_proposal(*, actor, proposal_id: UUID, now: datetime | None = None):
    at = now or timezone.now()
    proposal = _queryset().filter(pk=proposal_id).first()
    if proposal is None or not _staff_reader(actor, proposal, at=at):
        raise SessionProposalNotFound("The session proposal was not found.")
    return proposal


def case_proposals(*, actor, case, limit: int = 10):
    """The case owner's view of the case's proposals, newest first."""

    if actor.pk != case.primary_counselor_id:
        return ()
    return tuple(_queryset().filter(case_id=case.pk).order_by("-created_at", "-id")[:limit])


def _resolve_case_for_proposer(*, actor, case_id: UUID, at: datetime, lock: bool):
    query = CounselingCase.objects
    if lock:
        query = query.select_for_update()
    case = query.filter(pk=case_id).first()
    if case is None:
        raise CounselingCaseNotFound("The requested case was not found.")
    authority = proposer_authority(actor=actor, case=case, at=at)
    if authority is None:
        if case.primary_counselor_id == actor.pk and case.status != CounselingCaseStatus.ACTIVE:
            raise CounselingCaseClosed("This case is closed. Sessions can't be proposed.")
        if case.primary_counselor_id == actor.pk or active_coverage(actor=actor, case=case, at=at):
            raise CounselingCaseNotPermitted("You don't have permission to propose sessions.")
        raise CounselingCaseNotFound("The requested case was not found.")
    return case, authority


@dataclass(frozen=True, slots=True)
class ProposalContext:
    case: CounselingCase
    student: User
    authority: str
    open_proposal: CounselingSessionProposal | None
    duration_minutes: int | None
    delivery_modes: tuple[str, ...]


def get_proposal_context(*, actor, case_id: UUID, now: datetime | None = None) -> ProposalContext:
    """What the propose form needs. Works for a covering Counselor who can't read the case."""

    at = now or timezone.now()
    case, authority = _resolve_case_for_proposer(actor=actor, case_id=case_id, at=at, lock=False)
    student = User.objects.select_related("role").get(pk=case.student_id)
    service = _service()
    open_proposal = (
        _queryset()
        .filter(case_id=case.pk, state=SessionProposalState.PENDING, expires_at__gt=at)
        .first()
    )
    modes = tuple(
        sorted(service.delivery_mode_assignments.values_list("mode", flat=True).distinct())
    )
    return ProposalContext(
        case=case,
        student=student,
        authority=authority,
        open_proposal=open_proposal,
        duration_minutes=service.default_appointment_duration_minutes,
        delivery_modes=modes,
    )


def list_proposal_slots(
    *,
    actor,
    case_id: UUID,
    delivery_mode: str,
    target_date: date,
    now: datetime | None = None,
):
    """Bookable times the proposing Counselor may offer on a date. Reserves nothing."""

    at = now or timezone.now()
    case, _authority = _resolve_case_for_proposer(actor=actor, case_id=case_id, at=at, lock=False)
    student = User.objects.select_related("role").get(pk=case.student_id)
    service = _service()
    try:
        return list_offerable_slots(
            student=student,
            provider=actor,
            service=service,
            delivery_mode=delivery_mode,
            target_date=target_date,
            now=at,
        )
    except AppointmentCurrentStudentRequired as exc:
        raise SessionProposalUnavailable("This Student can't book Appointments now.") from exc
    except AppointmentError as exc:
        raise SessionProposalTimeUnavailable(
            "No times can be offered for this choice.", reason="not_offerable"
        ) from exc


def _service():
    try:
        return get_counseling_service()
    except CounselingConfigurationConflict as exc:
        raise SessionProposalUnavailable(str(exc)) from exc


# ---------------------------------------------------------------------------
# Propose and withdraw (Counselor)


def _clean_options(options, *, at: datetime) -> tuple[OptionInput, ...]:
    if not isinstance(options, (list, tuple)) or not 1 <= len(options) <= MAX_PROPOSAL_OPTIONS:
        raise SessionProposalInvalid(f"Offer 1 to {MAX_PROPOSAL_OPTIONS} session times.")
    cleaned = []
    for item in options:
        mode = getattr(item, "delivery_mode", None)
        mode = getattr(mode, "value", mode)
        starts_at = getattr(item, "starts_at", None)
        if mode not in DeliveryMode.values:
            raise SessionProposalInvalid("Choose In person or Online for each time.")
        if not isinstance(starts_at, datetime) or timezone.is_naive(starts_at):
            raise SessionProposalInvalid("Enter a valid date and time for each option.")
        if starts_at <= at:
            raise SessionProposalInvalid("Each proposed time must be in the future.")
        cleaned.append(OptionInput(delivery_mode=mode, starts_at=starts_at))
    starts = [item.starts_at for item in cleaned]
    if len(set(starts)) != len(starts):
        raise SessionProposalInvalid("Offer different times.")
    return tuple(sorted(cleaned, key=lambda item: item.starts_at))


def _follow_up_for(*, actor, follow_up_id, case):
    if follow_up_id is None:
        return None
    from compass.guidance_followups import policy
    from compass.guidance_followups.models import GuidanceFollowUp

    item = (
        GuidanceFollowUp.objects.select_related("student", "student__role")
        .filter(pk=follow_up_id)
        .first()
    )
    if (
        item is None
        or item.case_id != case.pk
        or item.status != "PENDING"
        or not policy.authorized(actor, item, manage=True)
    ):
        raise SessionProposalInvalid("This Follow-up can't be used for a proposal.")
    return item


def propose_session(
    *,
    actor,
    case_id: UUID,
    purpose: str,
    options,
    call_slip_requested: bool,
    follow_up_id: UUID | None,
    expected_version: int | None,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingSessionProposal:
    at = now or timezone.now()
    if purpose not in SessionProposalPurpose.values:
        raise SessionProposalInvalid("Choose the session purpose.")
    if type(call_slip_requested) is not bool:
        raise SessionProposalInvalid("Choose whether to issue a Call Slip.")
    cleaned = _clean_options(options, at=at)
    if call_slip_requested and not any(
        item.delivery_mode == DeliveryMode.IN_PERSON for item in cleaned
    ):
        raise SessionProposalInvalid("A Call Slip needs at least one In person time.")
    if expected_version is not None and (type(expected_version) is not int or expected_version < 1):
        raise SessionProposalInvalid("An expected version is required.")

    with transaction.atomic():
        # Lock order: case, proposals, users (the same order as accepting).
        case, authority = _resolve_case_for_proposer(actor=actor, case_id=case_id, at=at, lock=True)
        if expected_version is not None and case.version != expected_version:
            raise CounselingCaseChanged("This case changed. Review the latest details.")
        _expire_stale(case_id=case.pk, at=at)
        if CounselingSessionProposal.objects.filter(
            case_id=case.pk, state=SessionProposalState.PENDING
        ).exists():
            raise SessionProposalOpen(
                "This case already has a proposal waiting for the Student. "
                "Withdraw it before proposing other times."
            )
        locked = _lock_users(actor.pk, case.student_id)
        proposer, student = locked[actor.pk], locked[case.student_id]
        if proposer_authority(actor=proposer, case=case, at=at) != authority:
            raise CounselingCaseNotPermitted("You don't have permission to propose sessions.")
        if not student.is_active or not is_current_student(student):
            raise SessionProposalUnavailable("This Student can't book Appointments now.")
        follow_up = _follow_up_for(actor=proposer, follow_up_id=follow_up_id, case=case)
        service = _service()
        rows = []
        for position, item in enumerate(cleaned, start=1):
            try:
                ends_at = check_offerable_interval(
                    student=student,
                    provider=proposer,
                    service=service,
                    delivery_mode=item.delivery_mode,
                    starts_at=item.starts_at,
                    now=at,
                )
            except (AppointmentTimeUnavailable, AppointmentTimeConflict) as exc:
                raise SessionProposalTimeUnavailable(
                    f"Time {position} isn't available. Choose another time.",
                    option=position,
                    reason="conflict" if isinstance(exc, AppointmentTimeConflict) else "outside",
                ) from exc
            except AppointmentError as exc:
                raise SessionProposalTimeUnavailable(
                    f"Time {position} can't be offered for this Service.",
                    option=position,
                    reason="not_offerable",
                ) from exc
            rows.append((position, item, ends_at))
        proposal = CounselingSessionProposal.objects.create(
            case=case,
            student=student,
            proposed_by=proposer,
            service=service,
            purpose=purpose,
            follow_up=follow_up,
            call_slip_requested=call_slip_requested,
            expires_at=min(min(item.starts_at for item in cleaned), at + MAX_OPEN_PERIOD),
            created_at=at,
        )
        CounselingSessionProposalOption.objects.bulk_create(
            CounselingSessionProposalOption(
                proposal=proposal,
                position=position,
                delivery_mode=item.delivery_mode,
                starts_at=item.starts_at,
                ends_at=ends_at,
            )
            for position, item, ends_at in rows
        )
        record_event(
            context=context,
            action=SESSION_PROPOSAL_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.session_proposal",
            target_id=proposal.pk,
            metadata={
                "case_id": str(case.pk),
                "authority": authority,
                "purpose": purpose,
                "option_count": len(rows),
                "delivery_modes": sorted({item.delivery_mode for item in cleaned}),
                "call_slip_requested": call_slip_requested,
                "from_follow_up": follow_up is not None,
            },
        )
        create_notification_for_event(
            recipient=student,
            event=NotificationEvent.SESSION_PROPOSAL_RECEIVED,
            source_type="counseling_session_proposal",
            source_id=proposal.pk,
            target_type=NotificationTargetType.SESSION_PROPOSAL,
            target_id=proposal.pk,
        )
        _bump(case)
    return _queryset().get(pk=proposal.pk)


def withdraw_proposal(
    *,
    actor,
    proposal_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingSessionProposal:
    """D3: the proposer or the case owner may withdraw until the Student accepts."""

    at = now or timezone.now()
    if type(expected_version) is not int or expected_version < 1:
        raise SessionProposalInvalid("An expected version is required.")
    head = CounselingSessionProposal.objects.filter(pk=proposal_id).values("case_id").first()
    if head is None:
        raise SessionProposalNotFound("The session proposal was not found.")
    with transaction.atomic():
        case = CounselingCase.objects.select_for_update().get(pk=head["case_id"])
        proposal = CounselingSessionProposal.objects.select_for_update().get(pk=proposal_id)
        proposal.case = case
        if not _staff_reader(actor, proposal, at=at) or not _counselor(
            actor, capability=MANAGE_CAPABILITY, at=at
        ):
            raise SessionProposalNotFound("The session proposal was not found.")
        if effective_state(proposal, at=at) != SessionProposalState.PENDING:
            raise SessionProposalClosed("This proposal is no longer waiting for the Student.")
        if proposal.version != expected_version:
            raise SessionProposalChanged("This proposal changed. Review the latest details.")
        proposal.state = SessionProposalState.WITHDRAWN
        proposal.withdrawn_by = actor
        proposal.decided_at = at
        proposal.version += 1
        proposal.save(
            update_fields=["state", "withdrawn_by", "decided_at", "version", "updated_at"]
        )
        record_event(
            context=context,
            action=SESSION_PROPOSAL_WITHDRAWN,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.session_proposal",
            target_id=proposal.pk,
            metadata={"case_id": str(case.pk)},
        )
        if case.status == CounselingCaseStatus.ACTIVE:
            _bump(case)
    return _queryset().get(pk=proposal.pk)


# ---------------------------------------------------------------------------
# Student reads and decisions


def _require_student(actor, *, at: datetime):
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "STUDENT"
        or not actor.has_capability(STUDENT_CAPABILITY, at=at)
    ):
        raise CounselingCaseNotPermitted("You don't have permission to answer session proposals.")


def get_my_proposal(*, actor, proposal_id: UUID, now: datetime | None = None):
    at = now or timezone.now()
    _require_student(actor, at=at)
    proposal = _queryset().filter(pk=proposal_id, student_id=actor.pk).first()
    if proposal is None:
        raise SessionProposalNotFound("The session proposal was not found.")
    return proposal


def list_my_proposals(*, actor, now: datetime | None = None, limit: int = 20):
    at = now or timezone.now()
    _require_student(actor, at=at)
    return tuple(_queryset().filter(student_id=actor.pk).order_by("-created_at", "-id")[:limit])


def pending_for_student(*, student, now: datetime, limit: int):
    """Student Actions: proposals still waiting for this Student's answer."""

    if not student.has_capability(STUDENT_CAPABILITY, at=now):
        return ()
    return tuple(
        CounselingSessionProposal.objects.filter(
            student_id=student.pk,
            state=SessionProposalState.PENDING,
            expires_at__gt=now,
            case__status=CounselingCaseStatus.ACTIVE,
        )
        .only("id", "created_at", "expires_at")
        .order_by("expires_at", "created_at", "id")[:limit]
    )


def _lock_for_student(*, actor, proposal_id: UUID):
    head = (
        CounselingSessionProposal.objects.filter(pk=proposal_id, student_id=actor.pk)
        .values("case_id")
        .first()
    )
    if head is None:
        raise SessionProposalNotFound("The session proposal was not found.")
    case = CounselingCase.objects.select_for_update().get(pk=head["case_id"])
    proposal = (
        CounselingSessionProposal.objects.select_for_update(of=("self",))
        .select_related("proposed_by", "proposed_by__role")
        .get(pk=proposal_id)
    )
    proposal.case = case
    return case, proposal


def _notify_staff(proposal, case) -> None:
    recipients = {proposal.proposed_by_id: proposal.proposed_by}
    if case.primary_counselor_id not in recipients:
        recipients[case.primary_counselor_id] = case.primary_counselor
    for user_id, user in recipients.items():
        if user_id == case.primary_counselor_id:
            target = (NotificationTargetType.COUNSELING_CASE, case.pk)
        elif proposal.follow_up_id is not None:
            target = (NotificationTargetType.GUIDANCE_FOLLOW_UP, proposal.follow_up_id)
        else:
            target = ("", None)
        create_notification_for_event(
            recipient=user,
            event=NotificationEvent.SESSION_PROPOSAL_DECIDED,
            source_type="counseling_session_proposal",
            source_id=proposal.pk,
            target_type=target[0],
            target_id=target[1],
        )


def _booking_refusal(exc: AppointmentError) -> SessionProposalError:
    if isinstance(exc, AppointmentCurrentInventoryRequired):
        return SessionProposalStudentAction(
            "Submit your Individual Inventory for this Academic Year before accepting.",
            reason="current_inventory_required",
        )
    if isinstance(exc, AppointmentCurrentAcademicYearNotConfigured):
        return SessionProposalStudentAction(
            "Appointments can't be booked until the Academic Year is set up. "
            "Contact the Guidance Office.",
            reason="current_academic_year_not_configured",
        )
    if isinstance(exc, AppointmentCurrentStudentRequired):
        return SessionProposalUnavailable("Your account can't book Appointments now.")
    if isinstance(exc, (AppointmentTimeUnavailable, AppointmentTimeConflict)):
        return SessionProposalTimeUnavailable(
            "That time is no longer available. Choose another time or decline.",
            reason="conflict" if isinstance(exc, AppointmentTimeConflict) else "outside",
        )
    return SessionProposalTimeUnavailable(
        "That time can't be booked now. Choose another time or decline.",
        reason="not_offerable",
    )


@catalog_dependent_write
def accept_proposal(
    *,
    actor,
    proposal_id: UUID,
    option_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingSessionProposal:
    at = now or timezone.now()
    _require_student(actor, at=at)
    if type(expected_version) is not int or expected_version < 1:
        raise SessionProposalInvalid("An expected version is required.")
    with transaction.atomic():
        case, proposal = _lock_for_student(actor=actor, proposal_id=proposal_id)
        if proposal.state == SessionProposalState.ACCEPTED:
            accepted = proposal.options.filter(position=proposal.accepted_position).first()
            if accepted is not None and accepted.pk == option_id:
                # The same answer again (a retry or a second tab): the one Appointment stands.
                return _queryset().get(pk=proposal.pk)
        if effective_state(proposal, at=at) != SessionProposalState.PENDING:
            raise SessionProposalClosed("This proposal is no longer open.")
        if proposal.version != expected_version:
            raise SessionProposalChanged("This proposal changed. Review the latest details.")
        option = proposal.options.filter(pk=option_id).first()
        if option is None:
            raise SessionProposalInvalid("Choose one of the proposed times.")
        if proposer_authority(actor=proposal.proposed_by, case=case, at=at) is None:
            raise SessionProposalUnavailable(
                "This proposal can no longer be accepted. Contact the Guidance Office."
            )
        try:
            appointment = create_student_appointment(
                student=actor,
                service_id=proposal.service_id,
                provider_id=proposal.proposed_by_id,
                delivery_mode=option.delivery_mode,
                starts_at=option.starts_at,
                context=context,
                now=at,
            )
        except AppointmentError as exc:
            raise _booking_refusal(exc) from exc
        # If the Service duration changed after proposing, the booked interval is the truth.
        proposal.state = SessionProposalState.ACCEPTED
        proposal.accepted_position = option.position
        proposal.appointment = appointment
        proposal.decided_at = at
        proposal.version += 1
        proposal.save(
            update_fields=[
                "state",
                "accepted_position",
                "appointment",
                "decided_at",
                "version",
                "updated_at",
            ]
        )
        _link_appointment(case=case, proposal=proposal, appointment=appointment, context=context)
        record_event(
            context=context,
            action=SESSION_PROPOSAL_ACCEPTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.session_proposal",
            target_id=proposal.pk,
            metadata={
                "case_id": str(case.pk),
                "appointment_id": str(appointment.pk),
                "position": option.position,
                "delivery_mode": option.delivery_mode,
            },
        )
        _notify_staff(proposal, case)
        _bump(case)
    return _queryset().get(pk=proposal.pk)


def _link_appointment(*, case, proposal, appointment: Appointment, context) -> None:
    """The accepted Appointment joins the case it was proposed from (CW-2 link rows)."""

    try:
        with transaction.atomic():
            CounselingCaseAppointment.objects.create(
                case=case,
                appointment=appointment,
                linked_by_id=proposal.proposed_by_id,
                linked_at=proposal.decided_at,
            )
    except IntegrityError as exc:  # pragma: no cover - a new Appointment has no links
        raise SessionProposalChanged("Couldn't add the Appointment to the case.") from exc
    record_event(
        context=context,
        action=COUNSELING_CASE_APPOINTMENT_LINKED,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case",
        target_id=case.pk,
        metadata={"appointment_id": str(appointment.pk), "via": "session_proposal"},
    )


def decline_proposal(
    *,
    actor,
    proposal_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingSessionProposal:
    at = now or timezone.now()
    _require_student(actor, at=at)
    if type(expected_version) is not int or expected_version < 1:
        raise SessionProposalInvalid("An expected version is required.")
    with transaction.atomic():
        case, proposal = _lock_for_student(actor=actor, proposal_id=proposal_id)
        if proposal.state == SessionProposalState.DECLINED:
            return _queryset().get(pk=proposal.pk)
        if effective_state(proposal, at=at) != SessionProposalState.PENDING:
            raise SessionProposalClosed("This proposal is no longer open.")
        if proposal.version != expected_version:
            raise SessionProposalChanged("This proposal changed. Review the latest details.")
        proposal.state = SessionProposalState.DECLINED
        proposal.decided_at = at
        proposal.version += 1
        proposal.save(update_fields=["state", "decided_at", "version", "updated_at"])
        record_event(
            context=context,
            action=SESSION_PROPOSAL_DECLINED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.session_proposal",
            target_id=proposal.pk,
            metadata={"case_id": str(case.pk)},
        )
        _notify_staff(proposal, case)
    return _queryset().get(pk=proposal.pk)
