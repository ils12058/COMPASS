"""Transactional Call Slip issuance, scoped access, and interview-end recording."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    CALL_SLIP_CREATED,
    CALL_SLIP_INTERVIEW_ENDED,
    CALL_SLIP_VOIDED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.documents.rendering import DocumentRenderError, render_document_pdf
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.operational_students import (
    InvalidOperationalStudentQuery,
    OperationalStudentPage,
    list_scoped_operational_students,
)
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import StaffSupervision, StudentAffiliation
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

from .models import CallSlip, CallSlipDestinationType

CALL_SLIP_FORM_FAMILY_KEY = "call_slip"
OPERATIONAL_ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})
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


class CallSlipDocumentUnavailable(CallSlipError):
    pass


@dataclass(frozen=True, slots=True)
class CallSlipPage:
    items: tuple[CallSlip, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class _CallSlipCreationInput:
    fingerprint: str
    course_snapshot: str
    destination_type: str
    other_destination: str
    report_at: datetime
    digest: str


def _institution_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise CallSlipConfigurationConflict(
            "The configured institutional timezone is unavailable."
        ) from exc


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
        raise CallSlipNotPermitted("Active Guidance operational access is required.")


def _validate_student_actor(actor: User) -> None:
    if not getattr(actor, "pk", None) or not actor.is_active or actor.role.code != "STUDENT":
        raise CallSlipNotPermitted("Active Student self-service access is required.")


def _validate_student(student: User | None) -> User:
    if student is None or not student.is_active or student.role.code != "STUDENT":
        raise InvalidCallSlipInput("An active Student account is required.")
    return student


def _scope_college_ids(actor: User) -> tuple[UUID, ...] | None:
    scope = resolve_organizational_access_scope(actor)
    return None if scope.institution_wide else scope.college_ids


def _student_in_scope(actor: User, student_id: UUID) -> bool:
    college_ids = _scope_college_ids(actor)
    if college_ids is None:
        return True
    if not college_ids:
        return False
    return StudentAffiliation.objects.filter(
        student_id=student_id,
        college_id__in=college_ids,
        college__is_active=True,
        college__campus__is_active=True,
    ).exists()


def _scope_queryset(queryset, actor: User):
    college_ids = _scope_college_ids(actor)
    if college_ids is None:
        return queryset
    if not college_ids:
        return queryset.none()
    return queryset.filter(
        student__organization_student_affiliation__college_id__in=college_ids,
        student__organization_student_affiliation__college__is_active=True,
        student__organization_student_affiliation__college__campus__is_active=True,
    )


def _queryset():
    return CallSlip.objects.select_related(
        "student",
        "student__role",
        "issued_by",
        "issued_by__role",
        "form_revision",
        "form_revision__family",
        "recorded_by",
        "referral",
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
        raise InvalidCallSlipInput("destination_type is not supported.")
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
        raise InvalidCallSlipInput("destination_type is not supported.")
    cleaned_other = _clean_optional(
        other_destination,
        "other_destination",
        MAX_OTHER_DESTINATION_LENGTH,
    )
    if normalized == CallSlipDestinationType.GUIDANCE_OFFICE:
        if cleaned_other:
            raise InvalidCallSlipInput("other_destination must be empty for GUIDANCE_OFFICE.")
        return normalized, ""
    if not cleaned_other:
        raise InvalidCallSlipInput("other_destination is required for OTHER.")
    return normalized, cleaned_other


def _normalize_report_at(value: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidCallSlipInput("report_at must be a timezone-aware datetime.")
    return value.astimezone(_institution_zone())


def _normalize_interview_ended_at(value: datetime, *, now: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidCallSlipInput("interview_ended_at must be a timezone-aware datetime.")
    normalized = value.astimezone(_institution_zone())
    current = now.astimezone(_institution_zone())
    if normalized > current:
        raise InvalidCallSlipInput("interview_ended_at cannot be in the future.")
    return normalized


def _date_bounds(
    from_date: date | None,
    to_date: date | None,
) -> tuple[datetime | None, datetime | None]:
    if from_date is not None and not isinstance(from_date, date):
        raise InvalidCallSlipInput("from_date must be a date.")
    if to_date is not None and not isinstance(to_date, date):
        raise InvalidCallSlipInput("to_date must be a date.")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvalidCallSlipInput("from_date must not be after to_date.")
    zone = _institution_zone()
    start = datetime.combine(from_date, time.min, tzinfo=zone) if from_date else None
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone) if to_date else None
    return start, end


def _apply_date_filters(queryset, *, from_date: date | None, to_date: date | None):
    start, end = _date_bounds(from_date, to_date)
    if start is not None:
        queryset = queryset.filter(report_at__gte=start)
    if end is not None:
        queryset = queryset.filter(report_at__lt=end)
    return queryset


def _page(queryset, *, page: int, page_size: int) -> CallSlipPage:
    page, page_size = _pagination(page, page_size)
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return CallSlipPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def _active_call_slip_revision():
    try:
        return require_active_supported_form_revision(CALL_SLIP_FORM_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        if "does not support" in str(exc):
            raise CallSlipConfigurationConflict(
                "The active Call Slip Form Revision is not supported by this COMPASS version."
            ) from exc
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
    return _CallSlipCreationInput(
        fingerprint=fingerprint,
        course_snapshot=_clean_required(
            course_year,
            "course_year",
            MAX_COURSE_YEAR_LENGTH,
        ),
        destination_type=_normalize_destination(destination_type, other_destination)[0],
        other_destination=_normalize_destination(destination_type, other_destination)[1],
        report_at=_normalize_report_at(report_at),
        digest=_creation_digest(actor_id=actor.pk, key=key),
    )


def _lock_creation_actor(actor: User) -> User:
    locked_actor = (
        User.objects.select_for_update().select_related("role").filter(pk=actor.pk).first()
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
    if actor.role.code != "GUIDANCE_SERVICES_STAFF":
        raise CallSlipNotPermitted("Only Guidance operational actors may issue Call Slips.")

    supervision = StaffSupervision.objects.select_for_update().filter(staff_id=actor.pk).first()
    if supervision is None:
        raise CallSlipNotPermitted(
            "Guidance Services Staff requires a current supervising Counselor."
        )
    supervisor = (
        User.objects.select_for_update()
        .select_related("role")
        .filter(pk=supervision.supervisor_id)
        .first()
    )
    if supervisor is None or not supervisor.is_active or supervisor.role.code != "COUNSELOR":
        raise CallSlipNotPermitted(
            "Guidance Services Staff requires an active supervising Counselor."
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
            "The linked Referral does not record SEND_CALL_SLIP_INTERVIEW_PERMIT."
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
        User.objects.select_for_update().select_related("role").filter(pk=student_id).first()
    )
    student = _validate_student(student)
    if not _student_in_scope(actor, student.pk):
        raise CallSlipNotPermitted(
            "The selected Student is outside the authenticated Guidance actor's Call Slip scope."
        )

    referral = None
    if referral_id is not None:
        referral = _lock_linked_referral(
            actor=actor,
            referral_id=referral_id,
            student_id=student.pk,
        )

    revision = _active_call_slip_revision()
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
                issued_by=issuer,
                issued_by_name_snapshot=issuer.get_full_name(),
                form_revision=revision,
                recorded_by=actor,
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
        raise CallSlipCreationConflict(
            "The Call Slip could not be created because its creation identity conflicted."
        ) from exc

    item_for_audit = _queryset().get(pk=item.pk)
    record_event(
        context=context,
        action=CALL_SLIP_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="callslips.callslip",
        target_id=item.pk,
        metadata=_safe_audit_metadata(item_for_audit),
    )
    if notify_student:
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
        raise CallSlipReferralConflict(
            "The linked Referral already has a non-voided Call Slip."
        )
    return referral


def _translate_referral_action_error(exc: ReferralError) -> CallSlipError:
    if isinstance(exc, (ReferralNotFound, ReferralNotPermitted)):
        return CallSlipNotFound("The linked Referral was not found.")
    if isinstance(exc, InvalidReferralInput):
        return InvalidCallSlipInput(str(exc))
    if isinstance(exc, (ReferralActionConflict, ReferralVoidConflict)):
        return CallSlipReferralConflict(str(exc))
    return CallSlipReferralConflict("The linked Referral source action could not be ensured.")


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
            actor=actor,
            search=search,
            page=page,
            page_size=page_size,
        )
    except InvalidOperationalStudentQuery as exc:
        raise InvalidCallSlipInput(str(exc)) from exc


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
    include_voided: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CallSlipPage:
    _validate_operational_actor(actor)
    qs = _scope_queryset(_queryset(), actor)
    if not include_voided:
        qs = qs.filter(voided_at__isnull=True)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if issued_by_id is not None:
        qs = qs.filter(issued_by_id=issued_by_id)
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
    return _page(
        qs.order_by("-report_at", "-created_at", "id"),
        page=page,
        page_size=page_size,
    )


def list_my_call_slips(
    *,
    actor: User,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CallSlipPage:
    _validate_student_actor(actor)
    qs = _queryset().filter(student_id=actor.pk)
    qs = _apply_date_filters(qs, from_date=from_date, to_date=to_date)
    return _page(
        qs.order_by("-report_at", "-created_at", "id"),
        page=page,
        page_size=page_size,
    )


def get_call_slip(*, actor: User, call_slip_id: UUID) -> CallSlip:
    _validate_operational_actor(actor)
    item = _scope_queryset(_queryset(), actor).filter(pk=call_slip_id).first()
    if item is None:
        raise CallSlipNotFound("The requested Call Slip was not found.")
    return item


def get_my_call_slip(*, actor: User, call_slip_id: UUID) -> CallSlip:
    _validate_student_actor(actor)
    item = _queryset().filter(pk=call_slip_id, student_id=actor.pk).first()
    if item is None:
        raise CallSlipNotFound("The requested Call Slip was not found.")
    return item


def build_call_slip_render_context(
    item: CallSlip,
    *,
    access_mode: str,
) -> dict[str, object]:
    normalized_access = str(access_mode).strip().upper()
    if normalized_access not in {"SELF", "GCO"}:
        raise InvalidCallSlipInput("Call Slip document access mode is invalid.")
    report_at = timezone.localtime(item.report_at)
    interview_ended = (
        timezone.localtime(item.interview_ended_at) if item.interview_ended_at is not None else None
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
            "report_date": report_at.date(),
            "report_time": report_at.time().replace(second=0, microsecond=0),
            "issued_by_name": item.issued_by_name_snapshot,
            "interview_ended_at": interview_ended,
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
            item.form_revision.internal_schema_version,
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
        raise InvalidCallSlipInput("The server time must be timezone-aware.")
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
        if item.interview_ended_at is not None:
            if item.interview_ended_at == normalized:
                return _queryset().get(pk=item.pk)
            raise CallSlipInterviewEndConflict("interview_ended_at is immutable once recorded.")

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
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.CALL_SLIP_VOIDED,
            source_type="call_slip",
            source_id=item.pk,
            target_type="CALL_SLIP",
            target_id=item.pk,
        )
        return _queryset().get(pk=item.pk)
