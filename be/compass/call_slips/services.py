"""Transactional Call Slip issuance, scoped access, and interview-end recording."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    CALL_SLIP_APPROVED,
    CALL_SLIP_CREATED,
    CALL_SLIP_INTERVIEW_ENDED,
    CALL_SLIP_RESUBMITTED,
    CALL_SLIP_RETURNED,
    CALL_SLIP_VOIDED,
    CALL_SLIP_WITHDRAWN,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_day_start, to_institution_time
from compass.common.ordering import parse_ordering
from compass.documents.rendering import DocumentRenderError, render_document_pdf
from compass.institutional_forms.filter_options import represented_form_revisions
from compass.institutional_forms.models import FormRevision
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    UnsupportedInstitutionalFormRevision,
    is_supported_form_revision,
    require_active_supported_form_revision,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.operational_students import (
    InvalidOperationalStudentQuery,
    OperationalStudentPage,
    list_scoped_operational_students,
)
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.organization.catalog_availability import existing_college_q
from compass.organization.models import StaffSupervision
from compass.referrals.confidential_content import ReferralConfidentialContentUnavailable
from compass.referrals.models import Referral, ReferralAction, ReferralActionType
from compass.referrals.services import (
    InvalidReferralInput,
    ReferralActionConflict,
    ReferralError,
    ReferralNotFound,
    ReferralNotPermitted,
    ReferralVoidConflict,
    ensure_call_slip_action,
)
from compass.student_academics.reads import student_is_placed_in_colleges

from .models import (
    CallSlip,
    CallSlipApprovalStatus,
    CallSlipDestinationType,
    CallSlipIssuanceMode,
    CallSlipLifecycleState,
)

CALL_SLIP_FORM_FAMILY_KEY = "call_slip"
OPERATIONAL_ROLES = frozenset({"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"})
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_COURSE_YEAR_LENGTH = 255
MAX_OTHER_DESTINATION_LENGTH = 255
MAX_SEARCH_LENGTH = 160
MAX_VOID_REASON_LENGTH = 1000


class CallSlipError(RuntimeError):
    pass


class CallSlipNotFound(CallSlipError):
    pass


class CallSlipNotPermitted(CallSlipError):
    pass


class InvalidCallSlipInput(CallSlipError):
    pass


class CallSlipConfigurationConflict(CallSlipError):
    pass


class CallSlipCreationConflict(CallSlipError):
    pass


class CallSlipReferralConflict(CallSlipError):
    pass


class CallSlipInterviewEndConflict(CallSlipError):
    pass


class CallSlipVoidConflict(CallSlipError):
    pass


class CallSlipCaseConflict(CallSlipError):
    pass


class CallSlipDocumentUnavailable(CallSlipError):
    pass


class CallSlipOrdering(StrEnum):
    """Closed Call Slip orderings (ADR-090).

    ``report_at`` is when the Student is expected to report. Active Call Slips are a schedule and
    default to the earliest report time; completed, voided, and mixed lists are history and
    default to the latest.
    """

    EARLIEST_REPORT = "EARLIEST_REPORT"
    LATEST_REPORT = "LATEST_REPORT"
    STUDENT_ASC = "STUDENT_ASC"
    STUDENT_DESC = "STUDENT_DESC"


_CALL_SLIP_STUDENT_NAME = ("student__last_name", "student__first_name")
_CALL_SLIP_ORDER_BY: dict[CallSlipOrdering, tuple[str, ...]] = {
    CallSlipOrdering.EARLIEST_REPORT: ("report_at", "created_at", "id"),
    CallSlipOrdering.LATEST_REPORT: ("-report_at", "-created_at", "-id"),
    CallSlipOrdering.STUDENT_ASC: (*_CALL_SLIP_STUDENT_NAME, "report_at", "id"),
    CallSlipOrdering.STUDENT_DESC: (
        *(f"-{field}" for field in _CALL_SLIP_STUDENT_NAME),
        "-report_at",
        "-id",
    ),
}


def _call_slip_ordering(
    value: str | CallSlipOrdering | None, *, state: str | CallSlipLifecycleState | None
) -> CallSlipOrdering:
    default = (
        CallSlipOrdering.EARLIEST_REPORT
        if state == CallSlipLifecycleState.ACTIVE
        else CallSlipOrdering.LATEST_REPORT
    )
    return parse_ordering(value, CallSlipOrdering, default=default, error=InvalidCallSlipInput)


@dataclass(frozen=True, slots=True)
class CallSlipPage:
    items: tuple[CallSlip, ...]
    page: int
    page_size: int
    has_next: bool
    form_revisions: tuple[FormRevision, ...] = ()
    ordering: CallSlipOrdering | None = None


@dataclass(frozen=True, slots=True)
class _CallSlipCreationInput:
    fingerprint: str
    course_snapshot: str
    destination_type: str
    other_destination: str
    report_at: datetime
    digest: str


def _clean_required(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidCallSlipInput(f"{label} is required.")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise InvalidCallSlipInput(f"{label} is too long.")
    return cleaned


def _clean_optional(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidCallSlipInput(f"{label} must be text.")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise InvalidCallSlipInput(f"{label} is too long.")
    return cleaned


def _validate_idempotency_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or value.strip() != value
        or not value.isprintable()
    ):
        raise InvalidCallSlipInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    return value


def _validate_fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise InvalidCallSlipInput("The Call Slip creation request fingerprint is invalid.")
    return value


def _creation_digest(*, actor_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{actor_id}\0{key}".encode()).hexdigest()


def _validate_operational_actor(actor: User) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in OPERATIONAL_ROLES
    ):
        raise CallSlipNotPermitted("You don't have permission to manage Call Slips.")


def _validate_student_actor(actor: User) -> None:
    if not getattr(actor, "pk", None) or not actor.is_active or actor.role.code != "STUDENT":
        raise CallSlipNotPermitted("Active Student self-service access is required.")


def _validate_student(student: User | None) -> User:
    if student is None or not student.is_active or student.role.code != "STUDENT":
        raise InvalidCallSlipInput("An active Student account is required.")
    return student


def _scope_college_ids(actor: User) -> tuple[UUID, ...] | None:
    # This domain explicitly grants oversight to the actor who holds Head designation.
    if is_head_guidance(actor):
        return None
    return resolve_operational_responsibility_scope(actor).college_ids


def _student_in_scope(actor: User, student_id: UUID) -> bool:
    college_ids = _scope_college_ids(actor)
    if college_ids is None:
        return True
    if not college_ids:
        return False
    return student_is_placed_in_colleges(student_id=student_id, college_ids=college_ids)


def _scope_queryset(queryset, actor: User):
    college_ids = _scope_college_ids(actor)
    if college_ids is None:
        return queryset
    pending_supervision_q = Q(
        voided_at__isnull=True,
        approval_status__in=(
            CallSlipApprovalStatus.PENDING_APPROVAL,
            CallSlipApprovalStatus.RETURNED,
        ),
    ) & (
        Q(recorded_by_id=actor.pk)
        | Q(
            recorded_by_id__in=StaffSupervision.objects.filter(
                supervisor_id=actor.pk,
                supervisor__is_active=True,
                supervisor__role__code="COUNSELOR",
            ).values("staff_id")
        )
    )
    if not college_ids:
        return queryset.filter(pending_supervision_q | Q(approved_by_id=actor.pk))
    return queryset.filter(
        (
            existing_college_q("student__student_academic_profile__current_college__")
            & Q(student__student_academic_profile__current_college_id__in=college_ids)
        )
        | pending_supervision_q
        | Q(approved_by_id=actor.pk)
    )


def _queryset():
    return CallSlip.objects.select_related(
        "student",
        "student__role",
        "issued_by",
        "issued_by__role",
        "approved_by",
        "approved_by__role",
        "returned_by",
        "returned_by__role",
        "form_revision",
        "form_revision__family",
        "recorded_by",
        "voided_by",
        "referral",
        "case_link",
        "case_link__case",
        "case_link__appointment",
    )


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidCallSlipInput("page must be a positive integer.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidCallSlipInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _normalize_destination_type(
    destination_type: str | CallSlipDestinationType,
) -> str:
    normalized = (
        destination_type.value
        if isinstance(destination_type, CallSlipDestinationType)
        else destination_type
    )
    if normalized not in CallSlipDestinationType.values:
        raise InvalidCallSlipInput("Choose a valid Destination.")
    return normalized


def _normalize_destination(
    destination_type: str | CallSlipDestinationType,
    other_destination: str,
) -> tuple[str, str]:
    normalized = (
        destination_type.value
        if isinstance(destination_type, CallSlipDestinationType)
        else destination_type
    )
    if normalized not in CallSlipDestinationType.values:
        raise InvalidCallSlipInput("Choose a valid Destination.")
    cleaned_other = _clean_optional(
        other_destination,
        "other_destination",
        MAX_OTHER_DESTINATION_LENGTH,
    )
    if normalized == CallSlipDestinationType.GUIDANCE_OFFICE:
        if cleaned_other:
            raise InvalidCallSlipInput("Leave Other destination blank for the Guidance Office.")
        return normalized, ""
    if not cleaned_other:
        raise InvalidCallSlipInput("Enter the Other destination.")
    return normalized, cleaned_other


def _normalize_report_at(value: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidCallSlipInput("Enter a valid Report date and time.")
    return to_institution_time(value)


def _normalize_interview_ended_at(value: datetime, *, now: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidCallSlipInput("Enter a valid Interview end date and time.")
    normalized = to_institution_time(value)
    if normalized > now:
        raise InvalidCallSlipInput("The Interview end time can't be in the future.")
    return normalized


def _date_bounds(
    from_date: date | None,
    to_date: date | None,
) -> tuple[datetime | None, datetime | None]:
    if from_date is not None and not isinstance(from_date, date):
        raise InvalidCallSlipInput("Enter a valid From date.")
    if to_date is not None and not isinstance(to_date, date):
        raise InvalidCallSlipInput("Enter a valid To date.")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvalidCallSlipInput("The From date can't be after the To date.")
    start = institution_day_start(from_date) if from_date else None
    end = institution_day_start(to_date + timedelta(days=1)) if to_date else None
    return start, end


def _apply_date_filters(queryset, *, from_date: date | None, to_date: date | None):
    start, end = _date_bounds(from_date, to_date)
    if start is not None:
        queryset = queryset.filter(report_at__gte=start)
    if end is not None:
        queryset = queryset.filter(report_at__lt=end)
    return queryset


def _issued_q() -> Q:
    return Q(approval_status__isnull=True) | Q(approval_status=CallSlipApprovalStatus.ISSUED)


def _apply_state_filter(queryset, state: str | CallSlipLifecycleState | None):
    if state is None:
        return queryset
    normalized = state.value if isinstance(state, CallSlipLifecycleState) else str(state)
    if normalized == CallSlipLifecycleState.PENDING_APPROVAL:
        return queryset.filter(
            voided_at__isnull=True,
            approval_status=CallSlipApprovalStatus.PENDING_APPROVAL,
        )
    if normalized == CallSlipLifecycleState.RETURNED:
        return queryset.filter(
            voided_at__isnull=True,
            approval_status=CallSlipApprovalStatus.RETURNED,
        )
    if normalized == CallSlipLifecycleState.ACTIVE:
        return queryset.filter(
            _issued_q(),
            voided_at__isnull=True,
            interview_ended_at__isnull=True,
        )
    if normalized == CallSlipLifecycleState.COMPLETED:
        return queryset.filter(
            _issued_q(),
            voided_at__isnull=True,
            interview_ended_at__isnull=False,
        )
    if normalized == CallSlipLifecycleState.VOIDED:
        return queryset.filter(voided_at__isnull=False)
    raise InvalidCallSlipInput(
        "state must be PENDING_APPROVAL, RETURNED, ACTIVE, COMPLETED, or VOIDED."
    )


def _page(
    queryset,
    *,
    page: int,
    page_size: int,
    ordering: CallSlipOrdering,
    form_revisions: tuple[FormRevision, ...] = (),
) -> CallSlipPage:
    page, page_size = _pagination(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset.order_by(*_CALL_SLIP_ORDER_BY[ordering])[offset : offset + page_size + 1])
    return CallSlipPage(
        tuple(rows[:page_size]), page, page_size, len(rows) > page_size, form_revisions, ordering
    )


def _active_call_slip_revision():
    try:
        return require_active_supported_form_revision(CALL_SLIP_FORM_FAMILY_KEY)
    except UnsupportedInstitutionalFormRevision as exc:
        raise CallSlipConfigurationConflict(
            "The active Call Slip Form Revision is not supported by this COMPASS version."
        ) from exc
    except InstitutionalFormConflict as exc:
        raise CallSlipConfigurationConflict(
            "No active supported Call Slip Form Revision is configured."
        ) from exc


def _prepare_creation_input(
    *,
    actor: User,
    course_year: str,
    destination_type: str | CallSlipDestinationType,
    other_destination: str,
    report_at: datetime,
    idempotency_key: str,
    request_fingerprint: str,
) -> _CallSlipCreationInput:
    _validate_operational_actor(actor)
    key = _validate_idempotency_key(idempotency_key)
    fingerprint = _validate_fingerprint(request_fingerprint)
    course_snapshot = _clean_required(
        course_year,
        "course_year",
        MAX_COURSE_YEAR_LENGTH,
    )
    normalized_destination, cleaned_other = _normalize_destination(
        destination_type,
        other_destination,
    )
    normalized_report_at = _normalize_report_at(report_at)
    return _CallSlipCreationInput(
        fingerprint=fingerprint,
        course_snapshot=course_snapshot,
        destination_type=normalized_destination,
        other_destination=cleaned_other,
        report_at=normalized_report_at,
        digest=_creation_digest(actor_id=actor.pk, key=key),
    )


def _lock_creation_actor(actor: User) -> User:
    locked_actor = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=actor.pk)
        .first()
    )
    if locked_actor is None:
        raise CallSlipNotPermitted("The authenticated Guidance actor no longer exists.")
    _validate_operational_actor(locked_actor)
    return locked_actor


def _existing_creation_locked(
    *,
    actor: User,
    digest: str,
    fingerprint: str,
) -> CallSlip | None:
    existing = CallSlip.objects.select_for_update().filter(creation_key_digest=digest).first()
    if existing is None:
        return None
    if existing.creation_request_fingerprint != fingerprint:
        raise CallSlipCreationConflict(
            "The Idempotency-Key was already used for a different Call Slip request."
        )
    if not _student_in_scope(actor, existing.student_id):
        raise CallSlipNotFound("The requested Call Slip was not found.")
    return _queryset().get(pk=existing.pk)


def _resolve_issuer_locked(actor: User) -> User:
    if actor.role.code == "COUNSELOR":
        return actor
    if actor.role.code != "GUIDANCE_OFFICE_ASSISTANT":
        raise CallSlipNotPermitted("You don't have permission to issue Call Slips.")

    supervision = StaffSupervision.objects.select_for_update().filter(staff_id=actor.pk).first()
    if supervision is None:
        raise CallSlipNotPermitted(
            "Guidance Office Assistant requires a current supervising Counselor."
        )
    supervisor = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=supervision.supervisor_id)
        .first()
    )
    if supervisor is None or not supervisor.is_active or supervisor.role.code != "COUNSELOR":
        raise CallSlipNotPermitted(
            "Guidance Office Assistant requires an active supervising Counselor."
        )
    return supervisor


def _lock_linked_referral(
    *,
    actor: User,
    referral_id: UUID,
    student_id: UUID,
) -> Referral:
    referral = Referral.objects.select_for_update().filter(pk=referral_id).first()
    if referral is None or not _student_in_scope(actor, referral.student_id):
        raise CallSlipNotFound("The linked Referral was not found.")
    if referral.voided_at is not None:
        raise CallSlipReferralConflict("A voided Referral cannot receive a new Call Slip.")
    if referral.student_id != student_id:
        raise CallSlipReferralConflict("The linked Referral belongs to a different Student.")
    if not ReferralAction.objects.filter(
        referral_id=referral.pk,
        action_type=ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT,
    ).exists():
        raise CallSlipReferralConflict(
            "Record permission to send a Call Slip on the linked Referral first."
        )
    if CallSlip.objects.filter(
        referral_id=referral.pk,
        voided_at__isnull=True,
    ).exists():
        raise CallSlipReferralConflict("The linked Referral already has an active Call Slip.")
    return referral


def _safe_audit_metadata(item: CallSlip) -> dict[str, object]:
    revision = item.form_revision
    return {
        "destination_type": item.destination_type,
        "issued_by_id": str(item.issued_by_id),
        "form_revision_id": str(revision.pk),
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
    }


def _create_new_call_slip_locked(
    *,
    actor: User,
    student_id: UUID,
    prepared: _CallSlipCreationInput,
    referral_id: UUID | None,
    notify_student: bool,
    context: AuditContext,
) -> CallSlip:
    issuer = _resolve_issuer_locked(actor)
    student = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=student_id)
        .first()
    )
    student = _validate_student(student)
    if not _student_in_scope(actor, student.pk):
        raise CallSlipNotPermitted(
            "You don't have permission to issue a Call Slip for the selected Student."
        )

    referral = None
    if referral_id is not None:
        referral = _lock_linked_referral(
            actor=actor,
            referral_id=referral_id,
            student_id=student.pk,
        )

    revision = _active_call_slip_revision()
    requires_approval = actor.role.code == "GUIDANCE_OFFICE_ASSISTANT"
    try:
        with transaction.atomic():
            item = CallSlip.objects.create(
                student=student,
                student_name_snapshot=student.get_full_name(),
                course_year_snapshot=prepared.course_snapshot,
                referral=referral,
                destination_type=prepared.destination_type,
                other_destination=prepared.other_destination,
                report_at=prepared.report_at,
                issuance_mode=(
                    CallSlipIssuanceMode.LIVE if notify_student else CallSlipIssuanceMode.HISTORICAL
                ),
                issued_by=issuer,
                issued_by_name_snapshot=issuer.get_full_name(),
                form_revision=revision,
                recorded_by=actor,
                approval_status=(
                    CallSlipApprovalStatus.PENDING_APPROVAL if requires_approval else None
                ),
                creation_key_digest=prepared.digest,
                creation_request_fingerprint=prepared.fingerprint,
            )
    except IntegrityError as exc:
        if (
            referral is not None
            and CallSlip.objects.filter(
                referral_id=referral.pk,
                voided_at__isnull=True,
            ).exists()
        ):
            raise CallSlipReferralConflict(
                "The linked Referral already has a non-voided Call Slip."
            ) from exc
        raise CallSlipCreationConflict("Couldn't create the Call Slip. Try again.") from exc

    item_for_audit = _queryset().get(pk=item.pk)
    record_event(
        context=context,
        action=CALL_SLIP_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="callslips.callslip",
        target_id=item.pk,
        metadata=_safe_audit_metadata(item_for_audit),
    )
    if requires_approval:
        create_notification_for_event(
            recipient=issuer,
            event=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED,
            source_type=f"call_slip_approval:{item.updated_at.isoformat()}",
            source_id=item.pk,
            target_type="CALL_SLIP",
            target_id=item.pk,
        )
    elif notify_student:
        create_notification_for_event(
            recipient=student,
            event=NotificationEvent.CALL_SLIP_ISSUED,
            source_type="call_slip",
            source_id=item.pk,
            target_type="CALL_SLIP",
            target_id=item.pk,
        )
    return item_for_audit


def create_call_slip(
    *,
    actor: User,
    student_id: UUID,
    course_year: str,
    destination_type: str | CallSlipDestinationType,
    other_destination: str,
    report_at: datetime,
    referral_id: UUID | None,
    notify_student: bool = True,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
    counseling_case_id: UUID | None = None,
    appointment_id: UUID | None = None,
) -> CallSlip:
    prepared = _prepare_creation_input(
        actor=actor,
        course_year=course_year,
        destination_type=destination_type,
        other_destination=other_destination,
        report_at=report_at,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if appointment_id is not None and counseling_case_id is None:
        raise InvalidCallSlipInput("An Appointment can be linked only together with its case.")
    if counseling_case_id is not None:
        return _create_case_call_slip(
            actor=actor,
            student_id=student_id,
            prepared=prepared,
            referral_id=referral_id,
            notify_student=notify_student,
            counseling_case_id=counseling_case_id,
            appointment_id=appointment_id,
            context=context,
        )

    with transaction.atomic():
        locked_actor = _lock_creation_actor(actor)
        existing = _existing_creation_locked(
            actor=locked_actor,
            digest=prepared.digest,
            fingerprint=prepared.fingerprint,
        )
        if existing is not None:
            return existing
        return _create_new_call_slip_locked(
            actor=locked_actor,
            student_id=student_id,
            prepared=prepared,
            referral_id=referral_id,
            notify_student=notify_student,
            context=context,
        )


def _create_case_call_slip(
    *,
    actor: User,
    student_id: UUID,
    prepared: _CallSlipCreationInput,
    referral_id: UUID | None,
    notify_student: bool,
    counseling_case_id: UUID,
    appointment_id: UUID | None,
    context: AuditContext,
) -> CallSlip:
    """NS-1: an ordinary live Call Slip, also linked to the issuing Counselor's case."""

    from compass.counseling.case_call_slips import (
        CaseCallSlipRefused,
        link_case_call_slip,
        lock_case_call_slip_target,
    )

    if referral_id is not None:
        raise InvalidCallSlipInput("A Call Slip links to a Referral or a case, not both.")
    if not notify_student:
        raise InvalidCallSlipInput("A case Call Slip is issued to the Student.")
    if actor.role.code != "COUNSELOR":
        raise CallSlipNotPermitted("Only a Counselor can issue a Call Slip from a case.")
    with transaction.atomic():
        existing = _existing_creation_locked(
            actor=actor, digest=prepared.digest, fingerprint=prepared.fingerprint
        )
        if existing is not None:
            return existing
        # Lock order: case, Appointment, then users (as every case operation does).
        try:
            case, appointment, proposal = lock_case_call_slip_target(
                actor=actor,
                case_id=counseling_case_id,
                appointment_id=appointment_id,
                student_id=student_id,
            )
        except CaseCallSlipRefused as exc:
            if exc.kind == "not_found":
                raise CallSlipNotFound(str(exc)) from exc
            if exc.kind == "invalid":
                raise InvalidCallSlipInput(str(exc)) from exc
            raise CallSlipCaseConflict(str(exc)) from exc
        locked_actor = _lock_creation_actor(actor)
        item = _create_new_call_slip_locked(
            actor=locked_actor,
            student_id=student_id,
            prepared=prepared,
            referral_id=None,
            notify_student=True,
            context=context,
        )
        link_case_call_slip(
            case=case,
            appointment=appointment,
            proposal=proposal,
            call_slip=item,
            actor=locked_actor,
            context=context,
        )
        return item


def _lock_referral_for_atomic_issuance(*, actor: User, referral_id: UUID) -> Referral:
    referral = Referral.objects.select_for_update().filter(pk=referral_id).first()
    if referral is None or not _student_in_scope(actor, referral.student_id):
        raise CallSlipNotFound("The linked Referral was not found.")
    if referral.voided_at is not None:
        raise CallSlipReferralConflict("A voided Referral cannot receive a new Call Slip.")
    if CallSlip.objects.filter(
        referral_id=referral.pk,
        voided_at__isnull=True,
    ).exists():
        raise CallSlipReferralConflict("The linked Referral already has a non-voided Call Slip.")
    return referral


def _translate_referral_action_error(exc: ReferralError) -> CallSlipError:
    if isinstance(exc, (ReferralNotFound, ReferralNotPermitted)):
        return CallSlipNotFound("The linked Referral was not found.")
    if isinstance(exc, InvalidReferralInput):
        return InvalidCallSlipInput(str(exc))
    if isinstance(exc, (ReferralActionConflict, ReferralVoidConflict)):
        return CallSlipReferralConflict(str(exc))
    return CallSlipReferralConflict("Couldn't prepare the linked Referral action. Try again.")


def create_call_slip_from_referral(
    *,
    actor: User,
    referral_id: UUID,
    course_year: str,
    destination_type: str | CallSlipDestinationType,
    other_destination: str,
    report_at: datetime,
    notify_student: bool,
    action_occurred_at: datetime | None,
    action_remarks: str | None,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> CallSlip:
    prepared = _prepare_creation_input(
        actor=actor,
        course_year=course_year,
        destination_type=destination_type,
        other_destination=other_destination,
        report_at=report_at,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    with transaction.atomic():
        locked_actor = _lock_creation_actor(actor)

        # Persistent Call Slip idempotency is authoritative and must resolve an exact
        # successful retry before source-action uniqueness is considered.
        existing = _existing_creation_locked(
            actor=locked_actor,
            digest=prepared.digest,
            fingerprint=prepared.fingerprint,
        )
        if existing is not None:
            return existing

        referral = _lock_referral_for_atomic_issuance(
            actor=locked_actor,
            referral_id=referral_id,
        )
        try:
            ensure_call_slip_action(
                actor=locked_actor,
                referral_id=referral.pk,
                occurred_at=action_occurred_at,
                remarks=action_remarks,
                context=context,
            )
        except ReferralConfidentialContentUnavailable:
            raise
        except ReferralError as exc:
            raise _translate_referral_action_error(exc) from exc

        return _create_new_call_slip_locked(
            actor=locked_actor,
            student_id=referral.student_id,
            prepared=prepared,
            referral_id=referral.pk,
            notify_student=notify_student,
            context=context,
        )


def list_eligible_students(
    *,
    actor: User,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> OperationalStudentPage:
    _validate_operational_actor(actor)
    try:
        return list_scoped_operational_students(
            college_ids=_scope_college_ids(actor),
            search=search,
            page=page,
            page_size=page_size,
            include_profile_photos=True,
        )
    except InvalidOperationalStudentQuery as exc:
        raise InvalidCallSlipInput(str(exc)) from exc


def count_my_active_call_slips(actor: User) -> int | None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "STUDENT"
        or not actor.has_capability("call_slips.view_self")
    ):
        return None
    return _apply_state_filter(
        CallSlip.objects.filter(student_id=actor.pk),
        CallSlipLifecycleState.ACTIVE,
    ).count()


def _active_operational_queryset(actor: User):
    """Canonical scoped active population, also used by the due work projection."""
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in OPERATIONAL_ROLES
        or not actor.has_capability("call_slips.view")
    ):
        return None
    return _apply_state_filter(
        _scope_queryset(CallSlip.objects.all(), actor),
        CallSlipLifecycleState.ACTIVE,
    )


def count_active_call_slips(actor: User) -> int | None:
    rows = _active_operational_queryset(actor)
    return None if rows is None else rows.count()


def list_call_slips(
    *,
    actor: User,
    student_id: UUID | None = None,
    issued_by_id: UUID | None = None,
    destination_type: str | CallSlipDestinationType | None = None,
    referral_id: UUID | None = None,
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    state: str | CallSlipLifecycleState | None = None,
    form_revision_id: UUID | None = None,
    ordering: str | CallSlipOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CallSlipPage:
    _validate_operational_actor(actor)
    resolved = _call_slip_ordering(ordering, state=state)
    qs = _scope_queryset(_queryset(), actor)
    revisions = represented_form_revisions(qs, family_keys=("call_slip",))
    if form_revision_id is not None:
        qs = qs.filter(form_revision_id=form_revision_id)
    if state is not None:
        qs = _apply_state_filter(qs, state)
    else:
        qs = qs.filter(voided_at__isnull=True)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if issued_by_id is not None:
        waiting_q = Q(
            voided_at__isnull=True,
            approval_status__in=(
                CallSlipApprovalStatus.PENDING_APPROVAL,
                CallSlipApprovalStatus.RETURNED,
            ),
        )
        supervised_staff_ids = StaffSupervision.objects.filter(
            supervisor_id=issued_by_id,
            supervisor__is_active=True,
            supervisor__role__code="COUNSELOR",
        ).values("staff_id")
        qs = qs.filter(
            (~waiting_q & Q(issued_by_id=issued_by_id))
            | (waiting_q & Q(recorded_by_id__in=supervised_staff_ids))
        )
    if destination_type is not None:
        qs = qs.filter(destination_type=_normalize_destination_type(destination_type))
    if referral_id is not None:
        qs = qs.filter(referral_id=referral_id)
    if search is not None:
        if not isinstance(search, str):
            raise InvalidCallSlipInput("search must be text.")
        term = search.strip()
        if len(term) > MAX_SEARCH_LENGTH:
            raise InvalidCallSlipInput(f"search must be at most {MAX_SEARCH_LENGTH} characters.")
        if term:
            qs = qs.filter(
                Q(student__institutional_id__icontains=term)
                | Q(student__first_name__icontains=term)
                | Q(student__middle_name__icontains=term)
                | Q(student__last_name__icontains=term)
                | Q(student_name_snapshot__icontains=term)
                | Q(referral__reference_code__icontains=term)
            )
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    page_result = _page(
        qs,
        page=page,
        page_size=page_size,
        ordering=resolved,
        form_revisions=revisions,
    )
    return CallSlipPage(
        items=tuple(_reconcile_waiting_supervisor(item) for item in page_result.items),
        page=page_result.page,
        page_size=page_result.page_size,
        has_next=page_result.has_next,
        form_revisions=page_result.form_revisions,
        ordering=page_result.ordering,
    )


def list_my_call_slips(
    *,
    actor: User,
    from_date: date | None = None,
    to_date: date | None = None,
    state: str | CallSlipLifecycleState | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CallSlipPage:
    _validate_student_actor(actor)
    if state is not None:
        normalized = state.value if isinstance(state, CallSlipLifecycleState) else str(state)
        if normalized not in {
            CallSlipLifecycleState.ACTIVE,
            CallSlipLifecycleState.COMPLETED,
            CallSlipLifecycleState.VOIDED,
        }:
            raise InvalidCallSlipInput("state must be ACTIVE, COMPLETED, or VOIDED.")
    qs = _queryset().filter(_issued_q(), student_id=actor.pk)
    qs = _apply_state_filter(qs, state)
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    # A Student's own list keeps the population default and offers no other order.
    return _page(
        qs,
        page=page,
        page_size=page_size,
        ordering=_call_slip_ordering(None, state=state),
    )


def current_approver_for_call_slip(item: CallSlip) -> User:
    if (
        item.voided_at is None
        and item.approval_status
        in {
            CallSlipApprovalStatus.PENDING_APPROVAL,
            CallSlipApprovalStatus.RETURNED,
        }
        and item.recorded_by_id is not None
    ):
        supervision = (
            StaffSupervision.objects.select_related("supervisor", "supervisor__role")
            .filter(
                staff_id=item.recorded_by_id,
                supervisor__is_active=True,
                supervisor__role__code="COUNSELOR",
            )
            .first()
        )
        if supervision is not None:
            return supervision.supervisor
    return item.issued_by


def _reconcile_waiting_supervisor(item: CallSlip) -> CallSlip:
    approver = current_approver_for_call_slip(item)
    if approver.pk != item.issued_by_id:
        item.issued_by = approver
        item.issued_by_name_snapshot = approver.get_full_name()
    return item


def get_call_slip(*, actor: User, call_slip_id: UUID) -> CallSlip:
    _validate_operational_actor(actor)
    item = _scope_queryset(_queryset(), actor).filter(pk=call_slip_id).first()
    if item is None:
        raise CallSlipNotFound("The requested Call Slip was not found.")
    return _reconcile_waiting_supervisor(item)


def get_my_call_slip(*, actor: User, call_slip_id: UUID) -> CallSlip:
    _validate_student_actor(actor)
    item = _queryset().filter(_issued_q(), pk=call_slip_id, student_id=actor.pk).first()
    if item is None:
        raise CallSlipNotFound("The requested Call Slip was not found.")
    return item


def build_call_slip_render_context(
    item: CallSlip,
    *,
    access_mode: str,
) -> dict[str, object]:
    if not item.is_issued:
        raise CallSlipDocumentUnavailable(
            "This Call Slip cannot be printed until the supervising Counselor approves "
            "and issues it."
        )
    if item.form_revision.family.key != "call_slip" or not is_supported_form_revision(
        item.form_revision
    ):
        raise CallSlipDocumentUnavailable("The saved controlled-form identity is unsupported.")
    normalized_access = str(access_mode).strip().upper()
    if normalized_access not in {"SELF", "GCO"}:
        raise InvalidCallSlipInput("Call Slip document access mode is invalid.")
    # The controlled form prints UCN civil dates and times. Templates convert aware datetimes to the
    # runtime zone, so only institutional dates and times are handed to them.
    report_at = to_institution_time(item.report_at)
    interview_ended = (
        to_institution_time(item.interview_ended_at)
        if item.interview_ended_at is not None
        else None
    )
    return {
        "call_slip": {
            "student_name": item.student_name_snapshot,
            "course_year": item.course_year_snapshot,
            "destination": (
                "Guidance Office"
                if item.destination_type == CallSlipDestinationType.GUIDANCE_OFFICE
                else item.other_destination
            ),
            "guidance_office_destination": (
                item.destination_type == CallSlipDestinationType.GUIDANCE_OFFICE
            ),
            "report_date": report_at.date(),
            "report_time": report_at.time().replace(second=0, microsecond=0),
            "issued_by_name": item.issued_by_name_snapshot,
            "interview_ended_date": interview_ended.date() if interview_ended else None,
            "interview_ended_time": (
                interview_ended.time().replace(second=0, microsecond=0) if interview_ended else None
            ),
            "state": item.lifecycle_state,
            "is_voided": item.voided_at is not None,
            "void_reason": item.void_reason if normalized_access == "GCO" else "",
            "referral_reference": (
                item.referral.reference_code
                if normalized_access == "GCO" and item.referral_id is not None
                else ""
            ),
            "show_operational_metadata": normalized_access == "GCO",
        },
        "controlled_form": {
            "official_code": item.form_revision.official_code,
            "official_revision": item.form_revision.official_revision,
            "page_label": "Page 1 of 1",
        },
    }


def render_call_slip_pdf(item: CallSlip, *, access_mode: str) -> bytes:
    try:
        result = render_document_pdf(
            "call_slip",
            2 if item.form_revision.official_code == "UCN-OP-GCO-01F2" else 1,
            context=build_call_slip_render_context(item, access_mode=access_mode),
        )
    except DocumentRenderError as exc:
        raise CallSlipDocumentUnavailable(
            "The saved Call Slip presentation version cannot be rendered by this COMPASS build."
        ) from exc
    return result.pdf_bytes


def record_interview_ended(
    *,
    actor: User,
    call_slip_id: UUID,
    interview_ended_at: datetime,
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    _validate_operational_actor(actor)
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("Couldn't process the Call Slip time. Try again.")
    normalized = _normalize_interview_ended_at(
        interview_ended_at,
        now=current,
    )

    with transaction.atomic():
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None or not _student_in_scope(actor, item.student_id):
            raise CallSlipNotFound("The requested Call Slip was not found.")
        if item.voided_at is not None:
            raise CallSlipVoidConflict("A voided Call Slip cannot record interview completion.")
        if not item.is_issued:
            raise CallSlipInterviewEndConflict(
                "A Call Slip waiting for approval cannot record interview completion."
            )
        if item.interview_ended_at is not None:
            if item.interview_ended_at == normalized:
                return _queryset().get(pk=item.pk)
            raise CallSlipInterviewEndConflict(
                "The Interview end time can't be changed once recorded."
            )

        item.interview_ended_at = normalized
        item.save(update_fields=["interview_ended_at", "updated_at"])
        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=CALL_SLIP_INTERVIEW_ENDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata={
                "destination_type": item.destination_type,
                "issued_by_id": str(item.issued_by_id),
            },
        )
        return item_for_audit


def void_call_slip(
    *,
    actor: User,
    call_slip_id: UUID,
    reason: str,
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    _validate_operational_actor(actor)
    cleaned_reason = _clean_required(reason, "reason", MAX_VOID_REASON_LENGTH)
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("The void time must be timezone-aware.")

    with transaction.atomic():
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None or not _student_in_scope(actor, item.student_id):
            raise CallSlipNotFound("The requested Call Slip was not found.")
        if item.voided_at is not None:
            return _queryset().get(pk=item.pk)
        if not item.is_issued:
            raise CallSlipVoidConflict(
                "A Call Slip that has not been issued cannot be voided. Withdraw it instead."
            )
        if item.interview_ended_at is not None:
            raise CallSlipVoidConflict("A completed Call Slip is historical and cannot be voided.")

        item.voided_at = current
        item.voided_by = actor
        item.void_reason = cleaned_reason
        item.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])
        record_event(
            context=context,
            action=CALL_SLIP_VOIDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata={
                "call_slip_id": str(item.pk),
                "transition": "ACTIVE -> VOIDED",
            },
        )
        if item.void_notifies_student:
            create_notification_for_event(
                recipient=item.student,
                event=NotificationEvent.CALL_SLIP_VOIDED,
                source_type="call_slip",
                source_id=item.pk,
                target_type="CALL_SLIP",
                target_id=item.pk,
            )
        return _queryset().get(pk=item.pk)


def _require_current_supervising_counselor_locked(*, actor: User, item: CallSlip) -> User:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability("call_slips.manage")
    ):
        raise CallSlipNotPermitted("Only the supervising Counselor can review this Call Slip.")
    locked_actor = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk=actor.pk, is_active=True, role__code="COUNSELOR")
        .first()
    )
    if locked_actor is None or not locked_actor.has_capability("call_slips.manage"):
        raise CallSlipNotPermitted("Only the supervising Counselor can review this Call Slip.")
    if item.recorded_by_id is None:
        raise CallSlipNotPermitted(
            "This Call Slip was not prepared by a Guidance Office Assistant."
        )
    supervision = (
        StaffSupervision.objects.select_for_update()
        .filter(staff_id=item.recorded_by_id, supervisor_id=locked_actor.pk)
        .first()
    )
    if supervision is None:
        raise CallSlipNotPermitted(
            "Only the Guidance Office Assistant's current supervising Counselor can decide "
            "this Call Slip."
        )
    return locked_actor


def approve_call_slip(
    *,
    actor: User,
    call_slip_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("The approval time must be timezone-aware.")

    with transaction.atomic():
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None:
            raise CallSlipNotFound("The requested Call Slip was not found.")
        locked_actor = _require_current_supervising_counselor_locked(actor=actor, item=item)
        if item.voided_at is not None:
            raise CallSlipVoidConflict("A voided or withdrawn Call Slip cannot be approved.")
        if item.is_issued:
            if item.approved_by_id == locked_actor.pk:
                return _queryset().get(pk=item.pk)
            raise CallSlipCreationConflict("This Call Slip has already been issued.")
        if item.approval_status != CallSlipApprovalStatus.PENDING_APPROVAL:
            raise CallSlipCreationConflict(
                "Only a Call Slip waiting for approval can be approved and issued."
            )

        item.approval_status = CallSlipApprovalStatus.ISSUED
        item.issued_by = locked_actor
        item.issued_by_name_snapshot = locked_actor.get_full_name()
        item.approved_by = locked_actor
        item.approved_at = current
        item.return_note = None
        item.save(
            update_fields=[
                "approval_status",
                "issued_by",
                "issued_by_name_snapshot",
                "approved_by",
                "approved_at",
                "return_note",
                "updated_at",
            ]
        )
        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=CALL_SLIP_APPROVED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata=_safe_audit_metadata(item_for_audit),
        )
        if item_for_audit.issuance_mode == CallSlipIssuanceMode.LIVE:
            create_notification_for_event(
                recipient=item_for_audit.student,
                event=NotificationEvent.CALL_SLIP_ISSUED,
                source_type="call_slip",
                source_id=item.pk,
                target_type="CALL_SLIP",
                target_id=item.pk,
            )
        return item_for_audit


def return_call_slip(
    *,
    actor: User,
    call_slip_id: UUID,
    note: str,
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    cleaned_note = _clean_required(note, "note", MAX_VOID_REASON_LENGTH)
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("The return time must be timezone-aware.")

    with transaction.atomic():
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None:
            raise CallSlipNotFound("The requested Call Slip was not found.")
        locked_actor = _require_current_supervising_counselor_locked(actor=actor, item=item)
        if item.voided_at is not None:
            raise CallSlipVoidConflict("A voided or withdrawn Call Slip cannot be returned.")
        if item.approval_status != CallSlipApprovalStatus.PENDING_APPROVAL:
            raise CallSlipCreationConflict(
                "Only a Call Slip waiting for approval can be returned for changes."
            )

        item.approval_status = CallSlipApprovalStatus.RETURNED
        item.issued_by = locked_actor
        item.issued_by_name_snapshot = locked_actor.get_full_name()
        item.returned_by = locked_actor
        item.returned_at = current
        item.return_note = cleaned_note
        item.save(
            update_fields=[
                "approval_status",
                "issued_by",
                "issued_by_name_snapshot",
                "returned_by",
                "returned_at",
                "return_note",
                "updated_at",
            ]
        )
        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=CALL_SLIP_RETURNED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata=_safe_audit_metadata(item_for_audit),
        )
        if item_for_audit.recorded_by is not None and item_for_audit.recorded_by.is_active:
            create_notification_for_event(
                recipient=item_for_audit.recorded_by,
                event=NotificationEvent.CALL_SLIP_RETURNED,
                source_type=f"call_slip_returned:{current.isoformat()}",
                source_id=item.pk,
                target_type="CALL_SLIP",
                target_id=item.pk,
            )
        return item_for_audit


def resubmit_call_slip(
    *,
    actor: User,
    call_slip_id: UUID,
    course_year: str | None = None,
    destination_type: str | CallSlipDestinationType | None = None,
    other_destination: str | None = None,
    report_at: datetime | None = None,
    notify_student: bool | None = None,
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "GUIDANCE_OFFICE_ASSISTANT"
        or not actor.has_capability("call_slips.manage")
    ):
        raise CallSlipNotPermitted(
            "Only the Guidance Office Assistant who prepared this Call Slip can resubmit it."
        )
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("The resubmission time must be timezone-aware.")

    with transaction.atomic():
        locked_actor = _lock_creation_actor(actor)
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None:
            raise CallSlipNotFound("The requested Call Slip was not found.")
        if item.recorded_by_id != locked_actor.pk:
            if not _student_in_scope(locked_actor, item.student_id):
                raise CallSlipNotFound("The requested Call Slip was not found.")
            raise CallSlipNotPermitted(
                "Only the Guidance Office Assistant who prepared this Call Slip can edit "
                "and resubmit it."
            )
        if item.voided_at is not None or item.approval_status not in {
            CallSlipApprovalStatus.PENDING_APPROVAL,
            CallSlipApprovalStatus.RETURNED,
        }:
            raise CallSlipCreationConflict(
                "Only a waiting or returned Call Slip can be edited and resubmitted."
            )
        issuer = _resolve_issuer_locked(locked_actor)

        course_snapshot = _clean_required(
            course_year if course_year is not None else item.course_year_snapshot,
            "course_year",
            MAX_COURSE_YEAR_LENGTH,
        )
        eff_destination = (
            destination_type if destination_type is not None else item.destination_type
        )
        eff_other = (
            other_destination
            if other_destination is not None
            else (
                ""
                if eff_destination == CallSlipDestinationType.GUIDANCE_OFFICE
                else item.other_destination
            )
        )
        normalized_destination, cleaned_other = _normalize_destination(
            eff_destination,
            eff_other,
        )
        normalized_report_at = (
            _normalize_report_at(report_at) if report_at is not None else item.report_at
        )
        eff_issuance_mode = (
            (CallSlipIssuanceMode.LIVE if notify_student else CallSlipIssuanceMode.HISTORICAL)
            if notify_student is not None
            else item.issuance_mode
        )

        item.course_year_snapshot = course_snapshot
        item.destination_type = normalized_destination
        item.other_destination = cleaned_other
        item.report_at = normalized_report_at
        item.issuance_mode = eff_issuance_mode
        item.issued_by = issuer
        item.issued_by_name_snapshot = issuer.get_full_name()
        item.approval_status = CallSlipApprovalStatus.PENDING_APPROVAL
        item.return_note = None
        item.save(
            update_fields=[
                "course_year_snapshot",
                "destination_type",
                "other_destination",
                "report_at",
                "issuance_mode",
                "issued_by",
                "issued_by_name_snapshot",
                "approval_status",
                "return_note",
                "updated_at",
            ]
        )
        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=CALL_SLIP_RESUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata=_safe_audit_metadata(item_for_audit),
        )
        create_notification_for_event(
            recipient=issuer,
            event=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED,
            source_type=f"call_slip_approval:{item.updated_at.isoformat()}",
            source_id=item.pk,
            target_type="CALL_SLIP",
            target_id=item.pk,
        )
        return item_for_audit


def withdraw_call_slip(
    *,
    actor: User,
    call_slip_id: UUID,
    reason: str = "",
    context: AuditContext,
    now: datetime | None = None,
) -> CallSlip:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "GUIDANCE_OFFICE_ASSISTANT"
        or not actor.has_capability("call_slips.manage")
    ):
        raise CallSlipNotPermitted(
            "Only the Guidance Office Assistant who prepared this Call Slip can withdraw it."
        )
    cleaned_reason = (
        _clean_optional(reason, "reason", MAX_VOID_REASON_LENGTH) or "Withdrawn before issuance."
    )
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidCallSlipInput("The withdrawal time must be timezone-aware.")

    with transaction.atomic():
        item = CallSlip.objects.select_for_update().filter(pk=call_slip_id).first()
        if item is None:
            raise CallSlipNotFound("The requested Call Slip was not found.")
        if item.recorded_by_id != actor.pk:
            if not _student_in_scope(actor, item.student_id):
                raise CallSlipNotFound("The requested Call Slip was not found.")
            raise CallSlipNotPermitted(
                "Only the Guidance Office Assistant who prepared this Call Slip can withdraw it."
            )
        if item.voided_at is not None:
            return _queryset().get(pk=item.pk)
        if item.approval_status not in {
            CallSlipApprovalStatus.PENDING_APPROVAL,
            CallSlipApprovalStatus.RETURNED,
        }:
            raise CallSlipVoidConflict("An issued Call Slip cannot be withdrawn. Void it instead.")

        item.approval_status = CallSlipApprovalStatus.WITHDRAWN
        item.voided_at = current
        item.voided_by = actor
        item.void_reason = cleaned_reason
        item.save(
            update_fields=[
                "approval_status",
                "voided_at",
                "voided_by",
                "void_reason",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=CALL_SLIP_WITHDRAWN,
            outcome=AuditOutcome.SUCCESS,
            target_type="callslips.callslip",
            target_id=item.pk,
            metadata={
                "call_slip_id": str(item.pk),
                "transition": "PENDING_APPROVAL -> VOIDED",
            },
        )
        return _queryset().get(pk=item.pk)


def reassign_waiting_call_slips_for_staff(*, staff: User, supervisor: User) -> None:
    waiting = list(
        CallSlip.objects.select_for_update().filter(
            recorded_by_id=staff.pk,
            voided_at__isnull=True,
            approval_status__in=(
                CallSlipApprovalStatus.PENDING_APPROVAL,
                CallSlipApprovalStatus.RETURNED,
            ),
        )
    )
    for item in waiting:
        if item.issued_by_id != supervisor.pk:
            item.issued_by = supervisor
            item.issued_by_name_snapshot = supervisor.get_full_name()
            item.save(update_fields=["issued_by", "issued_by_name_snapshot", "updated_at"])
        if item.approval_status == CallSlipApprovalStatus.PENDING_APPROVAL:
            create_notification_for_event(
                recipient=supervisor,
                event=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED,
                source_type=f"call_slip_approval:{item.updated_at.isoformat()}",
                source_id=item.pk,
                target_type="CALL_SLIP",
                target_id=item.pk,
            )
