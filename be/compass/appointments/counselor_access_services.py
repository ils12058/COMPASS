"""Permitted Counselor resolution and Head-approved Counselor booking exceptions (ADR-120)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    APPOINTMENT_COUNSELOR_APPROVAL_CHANGED,
    APPOINTMENT_COUNSELOR_APPROVAL_ENDED,
    APPOINTMENT_COUNSELOR_REQUEST_APPROVED,
    APPOINTMENT_COUNSELOR_REQUEST_CREATED,
    APPOINTMENT_COUNSELOR_REQUEST_DECLINED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling.case_coverage_models import CaseCoverageState, CounselingCaseCoverage
from compass.counseling.case_models import CounselingCase, CounselingCaseStatus
from compass.notifications.policy import NotificationEvent, NotificationTargetType
from compass.notifications.services import create_notification_for_event
from compass.organization.access_scope import (
    active_head_guidance_counselors,
    is_head_guidance,
)
from compass.organization.services import resolve_default_counselor_for_student
from compass.service_catalog.scheduling import lock_schedule_users
from compass.service_catalog.services import (
    service_counselor_eligible,
    service_eligible_counselors,
)
from compass.student_academics.reads import get_current_placement

from .counselor_access_content import (
    CounselorBookingReasonInvalid,
    CounselorBookingReasonUnavailable,
    encrypt_reason,
    read_reason,
    validate_reason,
)
from .counselor_access_models import (
    MAX_DECISION_NOTE_LENGTH,
    CounselorBookingRequest,
    CounselorBookingRequestState,
    StudentCounselorApproval,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class CounselorBookingAccessError(RuntimeError):
    pass


class CounselorBookingAccessDenied(CounselorBookingAccessError):
    pass


class CounselorBookingAccessNotFound(CounselorBookingAccessError):
    pass


class CounselorBookingAccessInvalid(CounselorBookingAccessError):
    pass


class CounselorBookingAccessConflict(CounselorBookingAccessError):
    pass


class CounselorBookingHeadUnavailable(CounselorBookingAccessConflict):
    pass


class CounselorBookingRequestPendingConflict(CounselorBookingAccessConflict):
    pass


class CounselorBookingVersionConflict(CounselorBookingAccessConflict):
    pass


class CounselorBookingContentUnavailable(CounselorBookingAccessError):
    pass


class CounselorPermissionBasis(StrEnum):
    DEFAULT = "DEFAULT"
    ACTIVE_CASE = "ACTIVE_CASE"
    ACTIVE_CASE_COVERAGE = "ACTIVE_CASE_COVERAGE"
    HEAD_APPROVED = "HEAD_APPROVED"


class CounselorRequestDecisionAction(StrEnum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"


@dataclass(frozen=True, slots=True)
class PermittedCounselor:
    user: User
    is_default: bool
    is_head_approved: bool
    is_case_counselor: bool
    bases: frozenset[CounselorPermissionBasis]


@dataclass(frozen=True, slots=True)
class StudentCounselorRequestState:
    default_counselor: User | None
    active_approval: StudentCounselorApproval | None
    pending_request: CounselorBookingRequest | None
    latest_decision: CounselorBookingRequest | None
    head_available: bool
    requestable_counselors: tuple[User, ...]


@dataclass(frozen=True, slots=True)
class HeadStudentContext:
    student: User
    college_name: str | None
    campus_name: str | None
    default_counselor: User | None


@dataclass(frozen=True, slots=True)
class HeadCounselorRequestEntry:
    request: CounselorBookingRequest
    student_context: HeadStudentContext


@dataclass(frozen=True, slots=True)
class HeadCounselorRequestDetailData:
    request: CounselorBookingRequest
    student_context: HeadStudentContext
    reason: str | None
    current_approval: StudentCounselorApproval | None
    available_counselors: tuple[User, ...]
    can_decide: bool


@dataclass(frozen=True, slots=True)
class HeadCounselorRequestPage:
    items: tuple[HeadCounselorRequestEntry, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class HeadCounselorApprovalEntry:
    approval: StudentCounselorApproval
    student_context: HeadStudentContext
    counselor_is_active: bool


@dataclass(frozen=True, slots=True)
class HeadCounselorApprovalPage:
    items: tuple[HeadCounselorApprovalEntry, ...]
    page: int
    page_size: int
    has_next: bool
    available_counselors: tuple[User, ...]
    can_manage: bool


# ---------------------------------------------------------------------------
# Shared authority and permitted-counselor helpers


def resolve_unique_active_head() -> User | None:
    """Return the single active Head Guidance Counselor, or None if 0 or >=2 are active."""

    heads = list(active_head_guidance_counselors()[:2])
    if len(heads) != 1:
        return None
    return heads[0]


def is_head_booking_override(actor: User | None, *, now: datetime | None = None) -> bool:
    """The Head Guidance Counselor may book or arrange Appointments with any qualified Counselor."""

    if actor is None or not getattr(actor, "pk", None):
        return False
    return bool(
        is_head_guidance(actor)
        and actor.has_capability("appointments.manage", at=now or timezone.now())
    )


def _counseling_service():
    from compass.counseling.services import CounselingConfigurationConflict, get_counseling_service

    try:
        return get_counseling_service()
    except CounselingConfigurationConflict as exc:
        raise CounselorBookingAccessConflict(str(exc)) from exc


def list_counseling_counselor_options() -> tuple[User, ...]:
    """Active Counselors currently qualified to provide the canonical Counseling Service."""

    from compass.counseling.services import CounselingConfigurationConflict, get_counseling_service

    try:
        counseling_service = get_counseling_service()
    except CounselingConfigurationConflict:
        return ()
    return tuple(
        service_eligible_counselors(counseling_service).order_by("last_name", "first_name", "id")
    )


def _validate_counseling_counselor(counselor: User | None) -> User:
    if counselor is None or not counselor.is_active or counselor.role.code != "COUNSELOR":
        raise CounselorBookingAccessInvalid("Choose an active Counselor who provides counseling.")
    counseling_service = _counseling_service()
    if not service_counselor_eligible(counseling_service, counselor):
        raise CounselorBookingAccessInvalid("Choose an active Counselor who provides counseling.")
    return counselor


def resolve_permitted_counselors_for_student(
    student: User, *, now: datetime | None = None
) -> dict[UUID, PermittedCounselor]:
    """Counselors a Student may book with (ADR-120):

    1. Default Counselor (College Counselor, or single active Head fallback when unassigned).
    2. Current primary Counselor and active temporary coverage Counselor of the Student's own
       ACTIVE Counseling Case(s).
    3. An active Counselor currently approved for this Student by the Head Guidance Counselor.

    Service qualification is layered separately on top of this set.
    """

    if not getattr(student, "pk", None) or not student.is_active or student.role.code != "STUDENT":
        return {}

    current = now or timezone.now()
    users: dict[UUID, User] = {}
    bases: dict[UUID, set[CounselorPermissionBasis]] = {}

    def _add(counselor: User, basis: CounselorPermissionBasis) -> None:
        if not counselor.is_active or counselor.role.code != "COUNSELOR":
            return
        users[counselor.pk] = counselor
        bases.setdefault(counselor.pk, set()).add(basis)

    default_resolution = resolve_default_counselor_for_student(student)
    if default_resolution.counselor is not None:
        _add(default_resolution.counselor, CounselorPermissionBasis.DEFAULT)

    active_cases = CounselingCase.objects.select_related("primary_counselor__role").filter(
        student_id=student.pk,
        status=CounselingCaseStatus.ACTIVE,
        primary_counselor__is_active=True,
        primary_counselor__role__code="COUNSELOR",
    )
    for case in active_cases:
        _add(case.primary_counselor, CounselorPermissionBasis.ACTIVE_CASE)

    active_coverages = CounselingCaseCoverage.objects.select_related(
        "receiving_counselor__role"
    ).filter(
        case__student_id=student.pk,
        case__status=CounselingCaseStatus.ACTIVE,
        primary_counselor_id=F("case__primary_counselor_id"),
        state=CaseCoverageState.ACCEPTED,
        starts_at__lte=current,
        expires_at__gt=current,
        receiving_counselor__is_active=True,
        receiving_counselor__role__code="COUNSELOR",
    )
    for coverage in active_coverages:
        _add(coverage.receiving_counselor, CounselorPermissionBasis.ACTIVE_CASE_COVERAGE)

    active_approval = (
        StudentCounselorApproval.objects.select_related("counselor__role")
        .filter(
            student_id=student.pk,
            ended_at__isnull=True,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
        )
        .first()
    )
    if active_approval is not None:
        _add(active_approval.counselor, CounselorPermissionBasis.HEAD_APPROVED)

    return {
        counselor_id: PermittedCounselor(
            user=user,
            is_default=CounselorPermissionBasis.DEFAULT in bases[counselor_id],
            is_head_approved=CounselorPermissionBasis.HEAD_APPROVED in bases[counselor_id],
            is_case_counselor=bool(
                bases[counselor_id]
                & {
                    CounselorPermissionBasis.ACTIVE_CASE,
                    CounselorPermissionBasis.ACTIVE_CASE_COVERAGE,
                }
            ),
            bases=frozenset(bases[counselor_id]),
        )
        for counselor_id, user in users.items()
    }


def lock_student_active_counselor_approval(student_id: UUID) -> StudentCounselorApproval | None:
    """Lock the Student's active approval row (if any) inside an already user-locked transaction."""

    return (
        StudentCounselorApproval.objects.select_for_update(of=("self",))
        .select_related("counselor__role")
        .filter(student_id=student_id, ended_at__isnull=True)
        .first()
    )


# ---------------------------------------------------------------------------
# Internal helpers for requests and approvals


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise CounselorBookingAccessInvalid("Page must be a positive number.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise CounselorBookingAccessInvalid(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _clean_note(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or "\x00" in value:
        raise CounselorBookingAccessInvalid("Enter a plain-text note.")
    cleaned = value.strip()
    if len(cleaned) > MAX_DECISION_NOTE_LENGTH:
        raise CounselorBookingAccessInvalid(
            f"The note must be {MAX_DECISION_NOTE_LENGTH} characters or fewer."
        )
    return cleaned


def _require_head_reader(actor: User, *, now: datetime) -> User:
    current = (
        User.objects.select_related("role")
        .filter(pk=getattr(actor, "pk", None), is_active=True)
        .first()
    )
    if (
        current is None
        or not is_head_guidance(current)
        or not current.has_capability("appointments.manage", at=now)
    ):
        raise CounselorBookingAccessDenied(
            "Only the Head Guidance Counselor can review counselor requests and approvals."
        )
    return current


def _require_unique_head_actor(actor: User, *, now: datetime) -> User:
    current = _require_head_reader(actor, now=now)
    unique = resolve_unique_active_head()
    if unique is None or unique.pk != current.pk:
        raise CounselorBookingHeadUnavailable(
            "This action needs exactly one active Head Guidance Counselor. "
            "Contact the Guidance Office."
        )
    return current


def _request_queryset():
    return CounselorBookingRequest.objects.select_related(
        "student__role",
        "preferred_counselor__role",
        "approved_counselor__role",
        "decided_by__role",
    )


def _approval_queryset():
    return StudentCounselorApproval.objects.select_related(
        "student__role",
        "counselor__role",
        "approved_by__role",
        "updated_by__role",
        "ended_by__role",
        "source_request",
    )


def _student_context(student: User) -> HeadStudentContext:
    placement = get_current_placement(student_id=student.pk)
    default_resolution = resolve_default_counselor_for_student(student)
    return HeadStudentContext(
        student=student,
        college_name=placement.college.name if placement is not None else None,
        campus_name=placement.college.campus_name if placement is not None else None,
        default_counselor=default_resolution.counselor,
    )


def _notify_student_update(*, student: User, source_type: str, source_id: UUID) -> None:
    create_notification_for_event(
        recipient=student,
        event=NotificationEvent.COUNSELOR_BOOKING_REQUEST_DECIDED,
        source_type=source_type,
        source_id=source_id,
        target_type=NotificationTargetType.APPOINTMENT_BOOKING,
        target_id=None,
    )


# ---------------------------------------------------------------------------
# Student flows


def get_student_counselor_request_state(
    *, student: User, now: datetime | None = None
) -> StudentCounselorRequestState:
    if not getattr(student, "pk", None) or not student.is_active or student.role.code != "STUDENT":
        raise CounselorBookingAccessDenied(
            "Only a Student can view their counselor request status."
        )
    default_resolution = resolve_default_counselor_for_student(student)
    active_approval = (
        _approval_queryset()
        .filter(
            student_id=student.pk,
            ended_at__isnull=True,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
        )
        .first()
    )
    pending_request = (
        _request_queryset()
        .filter(student_id=student.pk, state=CounselorBookingRequestState.PENDING)
        .first()
    )
    latest_decision = (
        _request_queryset()
        .filter(
            student_id=student.pk,
            state__in=[
                CounselorBookingRequestState.APPROVED,
                CounselorBookingRequestState.DECLINED,
            ],
        )
        .order_by("-decided_at", "-id")
        .first()
    )
    return StudentCounselorRequestState(
        default_counselor=default_resolution.counselor,
        active_approval=active_approval,
        pending_request=pending_request,
        latest_decision=latest_decision,
        head_available=resolve_unique_active_head() is not None,
        requestable_counselors=list_counseling_counselor_options(),
    )


def submit_counselor_booking_request(
    *,
    student: User,
    preferred_counselor_id: UUID | None,
    reason: str | None,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselorBookingRequest:
    current = now or timezone.now()
    if (
        not getattr(student, "pk", None)
        or not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability("appointments.manage_self", at=current)
    ):
        raise CounselorBookingAccessDenied(
            "You don't have permission to ask for a different counselor."
        )
    if not is_current_student(student):
        raise CounselorBookingAccessConflict(
            "Only current Students can ask for a different counselor."
        )

    try:
        cleaned_reason = validate_reason(reason)
    except CounselorBookingReasonInvalid as exc:
        raise CounselorBookingAccessInvalid(str(exc)) from exc

    lock_ids: list[UUID] = [student.pk]
    if preferred_counselor_id is not None:
        lock_ids.append(preferred_counselor_id)

    try:
        with transaction.atomic():
            try:
                locked_users = lock_schedule_users(*lock_ids)
            except ValueError as exc:
                raise CounselorBookingAccessInvalid(
                    "Choose an active Counselor who provides counseling."
                ) from exc

            locked_student = locked_users[student.pk]
            if (
                not locked_student.is_active
                or locked_student.role.code != "STUDENT"
                or not is_current_student(locked_student)
                or not locked_student.has_capability("appointments.manage_self", at=current)
            ):
                raise CounselorBookingAccessConflict(
                    "Only current Students can ask for a different counselor."
                )

            head = resolve_unique_active_head()
            if head is None:
                raise CounselorBookingHeadUnavailable(
                    "Requests for a different counselor aren't available right now. "
                    "Please contact the Guidance Office."
                )

            preferred: User | None = None
            if preferred_counselor_id is not None:
                preferred = _validate_counseling_counselor(locked_users.get(preferred_counselor_id))

            if (
                CounselorBookingRequest.objects.select_for_update()
                .filter(student_id=locked_student.pk, state=CounselorBookingRequestState.PENDING)
                .exists()
            ):
                raise CounselorBookingRequestPendingConflict(
                    "You already have a request waiting for the Head Guidance Counselor."
                )

            item = CounselorBookingRequest(
                student=locked_student,
                preferred_counselor=preferred,
                state=CounselorBookingRequestState.PENDING,
                created_at=current,
            )
            try:
                item.reason_ciphertext = encrypt_reason(item, cleaned_reason)
            except CounselorBookingReasonUnavailable as exc:
                raise CounselorBookingContentUnavailable(str(exc)) from exc
            item.save()

            record_event(
                context=context,
                action=APPOINTMENT_COUNSELOR_REQUEST_CREATED,
                outcome=AuditOutcome.SUCCESS,
                target_type="appointments.counselor_booking_request",
                target_id=item.pk,
                metadata={
                    "student_id": str(locked_student.pk),
                    "preferred_counselor_id": str(preferred.pk) if preferred is not None else None,
                    "has_reason": cleaned_reason is not None,
                },
            )
            create_notification_for_event(
                recipient=head,
                event=NotificationEvent.COUNSELOR_BOOKING_REQUEST_SUBMITTED,
                source_type="counselor_booking_request_submitted",
                source_id=item.pk,
                target_type=NotificationTargetType.COUNSELOR_BOOKING_REQUEST,
                target_id=item.pk,
            )
            return _request_queryset().get(pk=item.pk)
    except IntegrityError as exc:
        raise CounselorBookingRequestPendingConflict(
            "You already have a request waiting for the Head Guidance Counselor."
        ) from exc


# ---------------------------------------------------------------------------
# Head Guidance Counselor flows


def list_head_counselor_requests(
    *,
    actor: User,
    state: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> HeadCounselorRequestPage:
    current = now or timezone.now()
    _require_head_reader(actor, now=current)
    page, page_size = _pagination(page, page_size)
    qs = _request_queryset()
    if state is not None:
        normalized = state.value if isinstance(state, CounselorBookingRequestState) else state
        if normalized not in CounselorBookingRequestState.values:
            raise CounselorBookingAccessInvalid("Choose a valid request status.")
        qs = qs.filter(state=normalized)
    qs = (
        qs.order_by("created_at", "id")
        if state == CounselorBookingRequestState.PENDING
        else qs.order_by("-created_at", "id")
    )
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    entries = tuple(
        HeadCounselorRequestEntry(request=row, student_context=_student_context(row.student))
        for row in rows[:page_size]
    )
    return HeadCounselorRequestPage(
        items=entries,
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def get_head_counselor_request(
    *,
    actor: User,
    request_id: UUID,
    now: datetime | None = None,
) -> HeadCounselorRequestDetailData:
    current = now or timezone.now()
    head = _require_head_reader(actor, now=current)
    item = _request_queryset().filter(pk=request_id).first()
    if item is None:
        raise CounselorBookingAccessNotFound("The counselor request was not found.")
    try:
        decrypted_reason = read_reason(item)
    except CounselorBookingReasonUnavailable as exc:
        raise CounselorBookingContentUnavailable(str(exc)) from exc
    current_approval = (
        _approval_queryset().filter(student_id=item.student_id, ended_at__isnull=True).first()
    )
    unique_head = resolve_unique_active_head()
    can_decide = bool(
        item.state == CounselorBookingRequestState.PENDING
        and unique_head is not None
        and unique_head.pk == head.pk
    )
    return HeadCounselorRequestDetailData(
        request=item,
        student_context=_student_context(item.student),
        reason=decrypted_reason,
        current_approval=current_approval,
        available_counselors=list_counseling_counselor_options(),
        can_decide=can_decide,
    )


def decide_counselor_booking_request(
    *,
    actor: User,
    request_id: UUID,
    action: str | CounselorRequestDecisionAction,
    approved_counselor_id: UUID | None,
    note: str | None,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> HeadCounselorRequestDetailData:
    current = now or timezone.now()
    _require_unique_head_actor(actor, now=current)
    normalized_action = (
        action.value if isinstance(action, CounselorRequestDecisionAction) else action
    )
    if normalized_action not in {
        CounselorRequestDecisionAction.APPROVE.value,
        CounselorRequestDecisionAction.DECLINE.value,
    }:
        raise CounselorBookingAccessInvalid("Choose whether to approve or decline this request.")
    if type(expected_version) is not int or expected_version < 1:
        raise CounselorBookingAccessInvalid("An expected version is required.")
    cleaned_note = _clean_note(note)

    if normalized_action == CounselorRequestDecisionAction.APPROVE:
        if approved_counselor_id is None:
            raise CounselorBookingAccessInvalid("Choose a Counselor to approve.")
    elif approved_counselor_id is not None:
        raise CounselorBookingAccessInvalid(
            "A Counselor should only be chosen when approving a request."
        )

    snapshot = CounselorBookingRequest.objects.filter(pk=request_id).values("student_id").first()
    if snapshot is None:
        raise CounselorBookingAccessNotFound("The counselor request was not found.")

    lock_ids: list[UUID] = [actor.pk, snapshot["student_id"]]
    if approved_counselor_id is not None:
        lock_ids.append(approved_counselor_id)

    with transaction.atomic():
        try:
            locked_users = lock_schedule_users(*lock_ids)
        except ValueError as exc:
            raise CounselorBookingAccessInvalid(
                "Choose an active Counselor who provides counseling."
            ) from exc

        locked_head = _require_unique_head_actor(locked_users[actor.pk], now=current)
        locked_student = locked_users[snapshot["student_id"]]
        item = _request_queryset().select_for_update(of=("self",)).filter(pk=request_id).first()
        if item is None:
            raise CounselorBookingAccessNotFound("The counselor request was not found.")
        if item.version != expected_version:
            raise CounselorBookingVersionConflict(
                "This request changed. Review the latest details before deciding."
            )
        if item.state != CounselorBookingRequestState.PENDING:
            raise CounselorBookingAccessConflict("This request has already been decided.")

        if normalized_action == CounselorRequestDecisionAction.APPROVE:
            chosen = _validate_counseling_counselor(locked_users.get(approved_counselor_id))
            existing_approval = lock_student_active_counselor_approval(locked_student.pk)
            if existing_approval is not None:
                previous_counselor_id = str(existing_approval.counselor_id)
                existing_approval.counselor = chosen
                existing_approval.source_request = item
                existing_approval.approved_by = locked_head
                existing_approval.approved_at = current
                existing_approval.updated_by = locked_head
                existing_approval.version += 1
                existing_approval.save(
                    update_fields=[
                        "counselor",
                        "source_request",
                        "approved_by",
                        "approved_at",
                        "updated_by",
                        "version",
                        "updated_at",
                    ]
                )
                approval = existing_approval
            else:
                previous_counselor_id = None
                approval = StudentCounselorApproval.objects.create(
                    student=locked_student,
                    counselor=chosen,
                    source_request=item,
                    approved_by=locked_head,
                    approved_at=current,
                    updated_by=locked_head,
                    created_at=current,
                )

            item.state = CounselorBookingRequestState.APPROVED
            item.approved_counselor = chosen
            item.decided_by = locked_head
            item.decided_at = current
            item.decision_note = cleaned_note
            item.version += 1
            item.save(
                update_fields=[
                    "state",
                    "approved_counselor",
                    "decided_by",
                    "decided_at",
                    "decision_note",
                    "version",
                    "updated_at",
                ]
            )
            record_event(
                context=context,
                action=APPOINTMENT_COUNSELOR_REQUEST_APPROVED,
                outcome=AuditOutcome.SUCCESS,
                target_type="appointments.counselor_booking_request",
                target_id=item.pk,
                metadata={
                    "student_id": str(locked_student.pk),
                    "approval_id": str(approval.pk),
                    "previous_counselor_id": previous_counselor_id,
                    "approved_counselor_id": str(chosen.pk),
                    "has_decision_note": bool(cleaned_note),
                },
            )
        else:
            item.state = CounselorBookingRequestState.DECLINED
            item.decided_by = locked_head
            item.decided_at = current
            item.decision_note = cleaned_note
            item.version += 1
            item.save(
                update_fields=[
                    "state",
                    "decided_by",
                    "decided_at",
                    "decision_note",
                    "version",
                    "updated_at",
                ]
            )
            record_event(
                context=context,
                action=APPOINTMENT_COUNSELOR_REQUEST_DECLINED,
                outcome=AuditOutcome.SUCCESS,
                target_type="appointments.counselor_booking_request",
                target_id=item.pk,
                metadata={
                    "student_id": str(locked_student.pk),
                    "has_decision_note": bool(cleaned_note),
                },
            )

        _notify_student_update(
            student=locked_student,
            source_type=f"counselor_booking_request_decision_v{item.version}",
            source_id=item.pk,
        )

    return get_head_counselor_request(actor=actor, request_id=request_id, now=current)


def list_head_counselor_approvals(
    *,
    actor: User,
    include_ended: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    now: datetime | None = None,
) -> HeadCounselorApprovalPage:
    current = now or timezone.now()
    head = _require_head_reader(actor, now=current)
    page, page_size = _pagination(page, page_size)
    qs = _approval_queryset()
    if not include_ended:
        qs = qs.filter(ended_at__isnull=True)
    qs = qs.order_by("-approved_at", "id")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    entries = tuple(
        HeadCounselorApprovalEntry(
            approval=row,
            student_context=_student_context(row.student),
            counselor_is_active=bool(
                row.counselor.is_active and row.counselor.role.code == "COUNSELOR"
            ),
        )
        for row in rows[:page_size]
    )
    unique_head = resolve_unique_active_head()
    return HeadCounselorApprovalPage(
        items=entries,
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
        available_counselors=list_counseling_counselor_options(),
        can_manage=bool(unique_head is not None and unique_head.pk == head.pk),
    )


def change_counselor_approval(
    *,
    actor: User,
    approval_id: UUID,
    counselor_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> HeadCounselorApprovalEntry:
    current = now or timezone.now()
    _require_unique_head_actor(actor, now=current)
    if type(expected_version) is not int or expected_version < 1:
        raise CounselorBookingAccessInvalid("An expected version is required.")

    snapshot = StudentCounselorApproval.objects.filter(pk=approval_id).values("student_id").first()
    if snapshot is None:
        raise CounselorBookingAccessNotFound("The counselor approval was not found.")

    with transaction.atomic():
        try:
            locked_users = lock_schedule_users(actor.pk, snapshot["student_id"], counselor_id)
        except ValueError as exc:
            raise CounselorBookingAccessInvalid(
                "Choose an active Counselor who provides counseling."
            ) from exc

        locked_head = _require_unique_head_actor(locked_users[actor.pk], now=current)
        locked_student = locked_users[snapshot["student_id"]]
        new_counselor = _validate_counseling_counselor(locked_users.get(counselor_id))
        approval = (
            _approval_queryset().select_for_update(of=("self",)).filter(pk=approval_id).first()
        )
        if approval is None:
            raise CounselorBookingAccessNotFound("The counselor approval was not found.")
        if approval.version != expected_version:
            raise CounselorBookingVersionConflict(
                "This approval changed. Review the latest details before updating."
            )
        if approval.ended_at is not None:
            raise CounselorBookingAccessConflict("This approval has already ended.")
        if approval.counselor_id == new_counselor.pk:
            raise CounselorBookingAccessInvalid("Choose a different Counselor for this approval.")

        previous_counselor_id = str(approval.counselor_id)
        approval.counselor = new_counselor
        approval.updated_by = locked_head
        approval.version += 1
        approval.save(update_fields=["counselor", "updated_by", "version", "updated_at"])

        record_event(
            context=context,
            action=APPOINTMENT_COUNSELOR_APPROVAL_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.student_counselor_approval",
            target_id=approval.pk,
            metadata={
                "student_id": str(locked_student.pk),
                "previous_counselor_id": previous_counselor_id,
                "new_counselor_id": str(new_counselor.pk),
            },
        )
        _notify_student_update(
            student=locked_student,
            source_type=f"counselor_booking_approval_update_v{approval.version}",
            source_id=approval.pk,
        )
        updated = _approval_queryset().get(pk=approval.pk)
        return HeadCounselorApprovalEntry(
            approval=updated,
            student_context=_student_context(updated.student),
            counselor_is_active=True,
        )


def end_counselor_approval(
    *,
    actor: User,
    approval_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> HeadCounselorApprovalEntry:
    current = now or timezone.now()
    _require_unique_head_actor(actor, now=current)
    if type(expected_version) is not int or expected_version < 1:
        raise CounselorBookingAccessInvalid("An expected version is required.")

    snapshot = StudentCounselorApproval.objects.filter(pk=approval_id).values("student_id").first()
    if snapshot is None:
        raise CounselorBookingAccessNotFound("The counselor approval was not found.")

    with transaction.atomic():
        locked_users = lock_schedule_users(actor.pk, snapshot["student_id"])
        locked_head = _require_unique_head_actor(locked_users[actor.pk], now=current)
        locked_student = locked_users[snapshot["student_id"]]
        approval = (
            _approval_queryset().select_for_update(of=("self",)).filter(pk=approval_id).first()
        )
        if approval is None:
            raise CounselorBookingAccessNotFound("The counselor approval was not found.")
        if approval.version != expected_version:
            raise CounselorBookingVersionConflict(
                "This approval changed. Review the latest details before ending it."
            )
        if approval.ended_at is not None:
            raise CounselorBookingAccessConflict("This approval has already ended.")

        approval.ended_at = current
        approval.ended_by = locked_head
        approval.updated_by = locked_head
        approval.version += 1
        approval.save(update_fields=["ended_at", "ended_by", "updated_by", "version", "updated_at"])
        record_event(
            context=context,
            action=APPOINTMENT_COUNSELOR_APPROVAL_ENDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="appointments.student_counselor_approval",
            target_id=approval.pk,
            metadata={
                "student_id": str(locked_student.pk),
                "counselor_id": str(approval.counselor_id),
            },
        )
        _notify_student_update(
            student=locked_student,
            source_type=f"counselor_booking_approval_update_v{approval.version}",
            source_id=approval.pk,
        )
        updated = _approval_queryset().get(pk=approval.pk)
        return HeadCounselorApprovalEntry(
            approval=updated,
            student_context=_student_context(updated.student),
            counselor_is_active=bool(
                updated.counselor.is_active and updated.counselor.role.code == "COUNSELOR"
            ),
        )


# ---------------------------------------------------------------------------
# Work Queue, Overview, and Notification currentness hooks


def pending_counselor_booking_requests(*, actor: User, limit: int, now: datetime):
    """Head Work Queue items: pending counselor-change requests when actor is the unique Head."""

    from compass.work_queue.schemas import WorkItem, WorkKind, WorkPriority, WorkStudent

    if not (is_head_guidance(actor) and actor.has_capability("appointments.manage", at=now)):
        return ()
    unique_head = resolve_unique_active_head()
    if unique_head is None or unique_head.pk != actor.pk:
        return ()
    rows = (
        CounselorBookingRequest.objects.select_related("student")
        .filter(state=CounselorBookingRequestState.PENDING)
        .order_by("created_at", "id")[:limit]
    )
    return tuple(
        WorkItem(
            id=f"counselor-booking-request:{row.pk}",
            kind=WorkKind.COUNSELOR_BOOKING_REQUEST,
            priority=WorkPriority.ACTION_REQUIRED,
            source_id=row.pk,
            student=WorkStudent(id=row.student_id, display_name=row.student.get_full_name()),
            conversation_kind=None,
            due_at=None,
            waiting_since=row.created_at,
        )
        for row in rows
    )


def count_pending_counselor_booking_requests(
    *, actor: User, now: datetime | None = None
) -> int | None:
    """Overview count for the unique active Head Guidance Counselor; None for all others."""

    current = now or timezone.now()
    if not (
        getattr(actor, "pk", None)
        and actor.is_active
        and is_head_guidance(actor)
        and actor.has_capability("appointments.manage", at=current)
    ):
        return None
    unique_head = resolve_unique_active_head()
    if unique_head is None or unique_head.pk != actor.pk:
        return None
    return CounselorBookingRequest.objects.filter(
        state=CounselorBookingRequestState.PENDING
    ).count()


def counselor_request_submitted_notice_is_current(notification) -> bool:
    """True while the recipient is the unique active Head and the request is still pending."""

    recipient = User.objects.select_related("role").filter(pk=notification.recipient_id).first()
    if (
        recipient is None
        or not recipient.is_active
        or not is_head_guidance(recipient)
        or not recipient.has_capability("appointments.manage")
    ):
        return False
    unique_head = resolve_unique_active_head()
    if unique_head is None or unique_head.pk != recipient.pk:
        return False
    return (
        notification.event_code == NotificationEvent.COUNSELOR_BOOKING_REQUEST_SUBMITTED
        and notification.target_type == NotificationTargetType.COUNSELOR_BOOKING_REQUEST
        and notification.target_id is not None
        and CounselorBookingRequest.objects.filter(
            pk=notification.target_id,
            state=CounselorBookingRequestState.PENDING,
        ).exists()
    )


def counselor_request_decided_notice_is_current(notification) -> bool:
    """True while the recipient is an active Student."""

    recipient = User.objects.select_related("role").filter(pk=notification.recipient_id).first()
    return bool(
        recipient is not None
        and recipient.is_active
        and recipient.role.code == "STUDENT"
        and notification.event_code == NotificationEvent.COUNSELOR_BOOKING_REQUEST_DECIDED
        and notification.target_type == NotificationTargetType.APPOINTMENT_BOOKING
    )
