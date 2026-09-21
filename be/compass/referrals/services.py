"""Transactional Referral intake, scoped access, status, and source-action services."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    REFERRAL_ACTION_RECORDED,
    REFERRAL_CREATED,
    REFERRAL_STATUS_UPDATED,
    REFERRAL_VOIDED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.documents.rendering import DocumentRenderError, render_document_pdf
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.operational_students import (
    InvalidOperationalStudentQuery,
    OperationalStudentPage,
    list_scoped_operational_students,
)
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import StudentAffiliation

from .models import Referral, ReferralAction, ReferralActionType, ReferralReferenceCounter

REFERRAL_FORM_FAMILY_KEY = "referral_slip"
OPERATIONAL_ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_REFERENCE_SEQUENCE = 999_999
MAX_REASON_LENGTH = 10_000
MAX_REMARKS_LENGTH = 4_000
MAX_STATUS_NOTE_LENGTH = 1_000
MAX_VOID_REASON_LENGTH = 1_000
MAX_SEARCH_LENGTH = 160


class ReferralError(RuntimeError):
    pass


class ReferralNotFound(ReferralError):
    pass


class ReferralNotPermitted(ReferralError):
    pass


class InvalidReferralInput(ReferralError):
    pass


class ReferralConfigurationConflict(ReferralError):
    pass


class ReferralReferenceConflict(ReferralError):
    pass


class ReferralCreationConflict(ReferralError):
    pass


class ReferralActionConflict(ReferralError):
    pass


class ReferralVoidConflict(ReferralError):
    pass


class ReferralDocumentUnavailable(ReferralError):
    pass


@dataclass(frozen=True, slots=True)
class ReferralPage:
    items: tuple[Referral, ...]
    page: int
    page_size: int
    has_next: bool


def _institution_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIME_ZONE)
    except ZoneInfoNotFoundError as exc:
        raise ReferralConfigurationConflict(
            "The configured institutional timezone is unavailable."
        ) from exc


def _clean_required(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidReferralInput(f"{label} is required.")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise InvalidReferralInput(f"{label} is too long.")
    return cleaned


def _clean_optional(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise InvalidReferralInput(f"{label} must be text.")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise InvalidReferralInput(f"{label} is too long.")
    return cleaned


def _validate_idempotency_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or value.strip() != value
        or not value.isprintable()
    ):
        raise InvalidReferralInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    return value


def _validate_fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise InvalidReferralInput("The Referral creation request fingerprint is invalid.")
    return value


def _creation_digest(*, actor_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{actor_id}\0{key}".encode()).hexdigest()


def _validate_operational_actor(actor: User) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in OPERATIONAL_ROLES
    ):
        raise ReferralNotPermitted("Active Guidance operational access is required.")


def _validate_student(student: User | None) -> User:
    if student is None or not student.is_active or student.role.code != "STUDENT":
        raise InvalidReferralInput("An active Student account is required.")
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


def _queryset():
    return Referral.objects.select_related(
        "student",
        "student__role",
        "form_revision",
        "form_revision__family",
        "recorded_by",
    )


def _detail_queryset():
    return _queryset().prefetch_related("actions", "actions__recorded_by")


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


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidReferralInput("page must be a positive integer.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidReferralInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _validate_date(value: date, label: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidReferralInput(f"{label} must be a date.")
    return value


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidReferralInput("search must be text.")
    cleaned = search.strip()
    if len(cleaned) > MAX_SEARCH_LENGTH:
        raise InvalidReferralInput(
            f"search must be at most {MAX_SEARCH_LENGTH} characters."
        )
    return cleaned


def _normalize_received_at(
    value: datetime | None,
    *,
    referred_on: date,
    now: datetime,
) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidReferralInput("received_at must be a timezone-aware datetime.")
    zone = _institution_zone()
    normalized = value.astimezone(zone)
    current = now.astimezone(zone)
    if normalized > current:
        raise InvalidReferralInput("received_at cannot be in the future.")
    if normalized.date() < referred_on:
        raise InvalidReferralInput("received_at cannot be earlier than referred_on.")
    return normalized


def _normalize_occurred_at(
    value: datetime,
    *,
    referral: Referral,
    now: datetime,
) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise InvalidReferralInput("occurred_at must be a timezone-aware datetime.")
    zone = _institution_zone()
    normalized = value.astimezone(zone)
    if normalized > now.astimezone(zone):
        raise InvalidReferralInput("occurred_at cannot be in the future.")
    if referral.received_at is not None and normalized < referral.received_at.astimezone(zone):
        raise InvalidReferralInput("occurred_at cannot be earlier than received_at.")
    if referral.received_at is None and normalized.date() < referral.referred_on:
        raise InvalidReferralInput("occurred_at cannot be earlier than referred_on.")
    return normalized


def _active_referral_revision():
    try:
        return require_active_supported_form_revision(REFERRAL_FORM_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        if "does not support" in str(exc):
            raise ReferralConfigurationConflict(
                "The active Referral Slip Form Revision is not supported by this COMPASS version."
            ) from exc
        raise ReferralConfigurationConflict(
            "No active supported Referral Slip Form Revision is configured."
        ) from exc


def _reference_year(at: datetime) -> int:
    return at.astimezone(_institution_zone()).year


def _allocate_reference(*, at: datetime) -> str:
    year = _reference_year(at)
    counter = ReferralReferenceCounter.objects.select_for_update().filter(year=year).first()
    if counter is None:
        try:
            with transaction.atomic():
                ReferralReferenceCounter.objects.create(year=year, next_value=2)
            number = 1
        except IntegrityError:
            counter = ReferralReferenceCounter.objects.select_for_update().get(year=year)
            number = counter.next_value
            if number > MAX_REFERENCE_SEQUENCE:
                raise ReferralReferenceConflict(
                    "The Referral reference sequence is exhausted for this year."
                ) from None
            counter.next_value = number + 1
            counter.save(update_fields=["next_value"])
    else:
        number = counter.next_value
        if number > MAX_REFERENCE_SEQUENCE:
            raise ReferralReferenceConflict(
                "The Referral reference sequence is exhausted for this year."
            )
        counter.next_value = number + 1
        counter.save(update_fields=["next_value"])
    return f"REF-{year:04d}-{number:06d}"


def _safe_form_metadata(referral: Referral) -> dict[str, object]:
    revision = referral.form_revision
    return {
        "reference_code": referral.reference_code,
        "form_revision_id": str(revision.pk),
        "official_code": revision.official_code,
        "official_revision": revision.official_revision,
    }


def create_referral(
    *,
    actor: User,
    student_id: UUID,
    course_year_block: str,
    reason: str,
    referrer_name: str,
    referred_on: date,
    received_at: datetime | None,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
    now: datetime | None = None,
) -> Referral:
    _validate_operational_actor(actor)
    key = _validate_idempotency_key(idempotency_key)
    fingerprint = _validate_fingerprint(request_fingerprint)
    source_date = _validate_date(referred_on, "referred_on")
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidReferralInput("The server creation time must be timezone-aware.")
    if source_date > current.astimezone(_institution_zone()).date():
        raise InvalidReferralInput("referred_on cannot be in the future.")
    normalized_received_at = _normalize_received_at(
        received_at,
        referred_on=source_date,
        now=current,
    )
    course_snapshot = _clean_required(course_year_block, "course_year_block", 255)
    cleaned_reason = _clean_required(reason, "reason", MAX_REASON_LENGTH)
    cleaned_referrer = _clean_required(referrer_name, "referrer_name", 255)
    digest = _creation_digest(actor_id=actor.pk, key=key)

    with transaction.atomic():
        locked_actor = (
            User.objects.select_for_update().select_related("role").filter(pk=actor.pk).first()
        )
        if locked_actor is None:
            raise ReferralNotPermitted("The authenticated Guidance actor no longer exists.")
        _validate_operational_actor(locked_actor)

        existing = Referral.objects.select_for_update().filter(creation_key_digest=digest).first()
        if existing is not None:
            if existing.creation_request_fingerprint != fingerprint:
                raise ReferralCreationConflict(
                    "The Idempotency-Key was already used for a different Referral request."
                )
            if not _student_in_scope(locked_actor, existing.student_id):
                raise ReferralNotFound("The requested Referral was not found.")
            return _detail_queryset().get(pk=existing.pk)

        student = (
            User.objects.select_for_update().select_related("role").filter(pk=student_id).first()
        )
        student = _validate_student(student)
        if not _student_in_scope(locked_actor, student.pk):
            raise ReferralNotPermitted(
                "The selected Student is outside the authenticated Guidance actor's Referral scope."
            )

        revision = _active_referral_revision()
        reference_code = _allocate_reference(at=current)
        item = Referral.objects.create(
            reference_code=reference_code,
            student=student,
            student_name_snapshot=student.get_full_name(),
            course_year_block_snapshot=course_snapshot,
            reason=cleaned_reason,
            referrer_name=cleaned_referrer,
            referred_on=source_date,
            received_at=normalized_received_at,
            form_revision=revision,
            recorded_by=locked_actor,
            creation_key_digest=digest,
            creation_request_fingerprint=fingerprint,
        )
        item_for_audit = _queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=REFERRAL_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="referrals.referral",
            target_id=item.pk,
            metadata=_safe_form_metadata(item_for_audit),
        )
        return _detail_queryset().get(pk=item.pk)


def list_referrals(
    *,
    actor: User,
    search: str | None = None,
    student_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_voided: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ReferralPage:
    _validate_operational_actor(actor)
    page, page_size = _pagination(page, page_size)
    if from_date is not None:
        _validate_date(from_date, "from_date")
    if to_date is not None:
        _validate_date(to_date, "to_date")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvalidReferralInput("from_date must not be after to_date.")
    term = _clean_search(search)

    qs = _scope_queryset(_queryset(), actor)
    if not include_voided:
        qs = qs.filter(voided_at__isnull=True)
    if term:
        qs = qs.filter(
            Q(reference_code__icontains=term)
            | Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
            | Q(student_name_snapshot__icontains=term)
        )
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if from_date is not None:
        qs = qs.filter(referred_on__gte=from_date)
    if to_date is not None:
        qs = qs.filter(referred_on__lte=to_date)
    qs = qs.order_by("-created_at", "reference_code", "id")
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size + 1])
    return ReferralPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


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
        raise InvalidReferralInput(str(exc)) from exc


def get_referral(*, actor: User, referral_id: UUID) -> Referral:
    _validate_operational_actor(actor)
    item = _scope_queryset(_detail_queryset(), actor).filter(pk=referral_id).first()
    if item is None:
        raise ReferralNotFound("The requested Referral was not found.")
    return item


_REFERRAL_ACTION_LABELS = {
    ReferralActionType.CALL_PARENT_GUARDIAN: "Call the Parent/Guardian",
    ReferralActionType.SEND_PARENT_NOTIFICATION_LETTER: ('Send "Parent Notification Letter"'),
    ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT: ('Send "Call Slip/Interview Permit"'),
}


def build_referral_render_context(item: Referral) -> dict[str, object]:
    recorded = {action.action_type: action for action in item.actions.all()}
    action_rows: list[dict[str, object]] = []
    for action_type in ReferralActionType.values:
        action = recorded.get(action_type)
        occurred_at = timezone.localtime(action.occurred_at) if action is not None else None
        action_rows.append(
            {
                "label": _REFERRAL_ACTION_LABELS[action_type],
                "recorded": action is not None,
                "date": occurred_at.date() if occurred_at is not None else None,
                "time": (
                    occurred_at.time().replace(second=0, microsecond=0)
                    if occurred_at is not None
                    else None
                ),
                "remarks": action.remarks if action is not None else "",
            }
        )

    received_at = timezone.localtime(item.received_at) if item.received_at is not None else None
    return {
        "referral": {
            "reference_code": item.reference_code,
            "student_name": item.student_name_snapshot,
            "course_year_block": item.course_year_block_snapshot,
            "referrer_name": item.referrer_name,
            "referred_on": item.referred_on,
            "received_date": (received_at.date() if received_at is not None else None),
            "received_time": (
                received_at.time().replace(second=0, microsecond=0)
                if received_at is not None
                else None
            ),
            "reason": item.reason,
            "actions": action_rows,
            "status_note": item.status_note,
            "is_voided": item.voided_at is not None,
            "void_reason": item.void_reason,
        },
        "controlled_form": {
            "official_code": item.form_revision.official_code,
            "official_revision": item.form_revision.official_revision,
            "page_label": "Page 1 of 1",
        },
    }


def render_referral_pdf(item: Referral) -> bytes:
    try:
        result = render_document_pdf(
            "referral_slip",
            item.form_revision.internal_schema_version,
            context=build_referral_render_context(item),
        )
    except DocumentRenderError as exc:
        raise ReferralDocumentUnavailable(
            "The saved Referral Slip presentation version cannot be rendered by this COMPASS build."
        ) from exc
    return result.pdf_bytes


def _lock_scoped_referral(*, actor: User, referral_id: UUID) -> Referral:
    item = Referral.objects.select_for_update().filter(pk=referral_id).first()
    if item is None or not _student_in_scope(actor, item.student_id):
        raise ReferralNotFound("The requested Referral was not found.")
    return item


def update_status_note(
    *,
    actor: User,
    referral_id: UUID,
    status_note: str,
    context: AuditContext,
) -> Referral:
    _validate_operational_actor(actor)
    cleaned = _clean_optional(status_note, "status_note", MAX_STATUS_NOTE_LENGTH)
    with transaction.atomic():
        item = _lock_scoped_referral(actor=actor, referral_id=referral_id)
        if item.voided_at is not None:
            raise ReferralVoidConflict("A voided Referral cannot be changed.")
        if item.status_note == cleaned:
            return _detail_queryset().get(pk=item.pk)
        item.status_note = cleaned
        item.save(update_fields=["status_note", "updated_at"])
        record_event(
            context=context,
            action=REFERRAL_STATUS_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="referrals.referral",
            target_id=item.pk,
            metadata={"reference_code": item.reference_code},
        )
        return _detail_queryset().get(pk=item.pk)


def record_action(
    *,
    actor: User,
    referral_id: UUID,
    action_type: str | ReferralActionType,
    occurred_at: datetime,
    remarks: str,
    context: AuditContext,
    now: datetime | None = None,
) -> ReferralAction:
    _validate_operational_actor(actor)
    normalized_type = (
        action_type.value if isinstance(action_type, ReferralActionType) else action_type
    )
    if normalized_type not in ReferralActionType.values:
        raise InvalidReferralInput("action_type is not supported.")
    cleaned_remarks = _clean_optional(remarks, "remarks", MAX_REMARKS_LENGTH)
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidReferralInput("The server action time must be timezone-aware.")

    with transaction.atomic():
        referral = _lock_scoped_referral(actor=actor, referral_id=referral_id)
        if referral.voided_at is not None:
            raise ReferralVoidConflict("A voided Referral cannot receive new actions.")
        normalized_occurred = _normalize_occurred_at(
            occurred_at,
            referral=referral,
            now=current,
        )
        if ReferralAction.objects.filter(
            referral_id=referral.pk,
            action_type=normalized_type,
        ).exists():
            raise ReferralActionConflict(
                "This Referral action type has already been recorded for the source Referral."
            )
        try:
            with transaction.atomic():
                action = ReferralAction.objects.create(
                    referral=referral,
                    action_type=normalized_type,
                    occurred_at=normalized_occurred,
                    remarks=cleaned_remarks,
                    recorded_by=actor,
                )
        except IntegrityError as exc:
            raise ReferralActionConflict(
                "This Referral action type has already been recorded for the source Referral."
            ) from exc
        record_event(
            context=context,
            action=REFERRAL_ACTION_RECORDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="referrals.referralaction",
            target_id=action.pk,
            metadata={
                "reference_code": referral.reference_code,
                "action_type": normalized_type,
            },
        )
        return ReferralAction.objects.select_related("referral", "recorded_by").get(pk=action.pk)


def void_referral(
    *,
    actor: User,
    referral_id: UUID,
    reason: str,
    context: AuditContext,
    now: datetime | None = None,
) -> Referral:
    _validate_operational_actor(actor)
    cleaned_reason = _clean_required(reason, "reason", MAX_VOID_REASON_LENGTH)
    current = now or timezone.now()
    if timezone.is_naive(current):
        raise InvalidReferralInput("The void time must be timezone-aware.")

    with transaction.atomic():
        item = _lock_scoped_referral(actor=actor, referral_id=referral_id)
        if item.voided_at is not None:
            return _detail_queryset().get(pk=item.pk)

        from compass.call_slips.models import CallSlip

        if CallSlip.objects.filter(
            referral_id=item.pk,
            voided_at__isnull=True,
        ).exists():
            raise ReferralVoidConflict(
                "Void the active linked Call Slip before voiding this Referral."
            )

        item.voided_at = current
        item.voided_by = actor
        item.void_reason = cleaned_reason
        item.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])
        record_event(
            context=context,
            action=REFERRAL_VOIDED,
            outcome=AuditOutcome.SUCCESS,
            target_type="referrals.referral",
            target_id=item.pk,
            metadata={
                "reference_code": item.reference_code,
                "transition": "ACTIVE -> VOIDED",
            },
        )
        return _detail_queryset().get(pk=item.pk)
