"""Transactional Call Slip issuance, scoped access, and interview-end recording."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import CALL_SLIP_CREATED, CALL_SLIP_INTERVIEW_ENDED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    get_active_supported_form_revision,
)
from compass.organization.models import (
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.referrals.models import Referral, ReferralAction, ReferralActionType

from .models import CallSlip, CallSlipDestinationType

CALL_SLIP_FORM_FAMILY_KEY = "call_slip"
HEAD_DESIGNATION = "HEAD_GUIDANCE_COUNSELOR"
OPERATIONAL_ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_COURSE_YEAR_LENGTH = 255
MAX_OTHER_DESTINATION_LENGTH = 255


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


@dataclass(frozen=True, slots=True)
class CallSlipPage:
    items: tuple[CallSlip, ...]
    page: int
    page_size: int
    has_next: bool


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
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "STUDENT"
    ):
        raise CallSlipNotPermitted("Active Student self-service access is required.")


def _validate_student(student: User | None) -> User:
    if student is None or not student.is_active or student.role.code != "STUDENT":
        raise InvalidCallSlipInput("An active Student account is required.")
    return student


def _is_head(actor: User) -> bool:
    return (
        actor.role.code == "COUNSELOR"
        and actor.designations.filter(code=HEAD_DESIGNATION).exists()
    )


def _counselor_college_ids(counselor_id: UUID) -> tuple[UUID, ...]:
    return tuple(
        CounselorResponsibility.objects.filter(
            counselor_id=counselor_id,
            counselor__is_active=True,
            counselor__role__code="COUNSELOR",
            college__is_active=True,
            college__campus__is_active=True,
        )
        .order_by("college_id")
        .values_list("college_id", flat=True)
    )


def _scope_college_ids(actor: User) -> tuple[UUID, ...] | None:
    """Resolve Call Slip authorization scope; None means institution-wide Head scope."""

    if _is_head(actor):
        return None
    if actor.role.code == "COUNSELOR":
        return _counselor_college_ids(actor.pk)
    if actor.role.code == "GUIDANCE_SERVICES_STAFF":
        supervision = (
            StaffSupervision.objects.select_related("supervisor__role")
            .filter(staff_id=actor.pk)
            .first()
        )
        if (
            supervision is None
            or not supervision.supervisor.is_active
            or supervision.supervisor.role.code != "COUNSELOR"
        ):
            return ()
        if _is_head(supervision.supervisor):
            return None
        return _counselor_college_ids(supervision.supervisor_id)
    return ()


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
            raise InvalidCallSlipInput(
                "other_destination must be empty for GUIDANCE_OFFICE."
            )
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
        raise InvalidCallSlipInput(
            "interview_ended_at must be a timezone-aware datetime."
        )
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
    end = (
        datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone)
        if to_date
        else None
    )
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
        revision = get_active_supported_form_revision(CALL_SLIP_FORM_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        raise CallSlipConfigurationConflict(
            "The active Call Slip Form Revision is not supported by this COMPASS version."
        ) from exc
    if revision is None:
        raise CallSlipConfigurationConflict(
            "No active supported Call Slip Form Revision is configured."
        )
    return revision


def _resolve_issuer_locked(actor: User) -> User:
    if actor.role.code == "COUNSELOR":
        return actor
    if actor.role.code != "GUIDANCE_SERVICES_STAFF":
        raise CallSlipNotPermitted("Only Guidance operational actors may issue Call Slips.")

    supervision = (
        StaffSupervision.objects.select_for_update()
        .filter(staff_id=actor.pk)
        .first()
    )
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
    if (
        supervisor is None
        or not supervisor.is_active
        or supervisor.role.code != "COUNSELOR"
    ):
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
    if referral.student_id != student_id:
        raise CallSlipReferralConflict(
            "The linked Referral belongs to a different Student."
        )
    if not ReferralAction.objects.filter(
        referral_id=referral.pk,
        action_type=ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT,
    ).exists():
        raise CallSlipReferralConflict(
            "The linked Referral does not record SEND_CALL_SLIP_INTERVIEW_PERMIT."
        )
    if CallSlip.objects.filter(referral_id=referral.pk).exists():
        raise CallSlipReferralConflict(
            "The linked Referral already has a Call Slip in this foundation."
        )
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


def create_call_slip(
    *,
    actor: User,
    student_id: UUID,
    course_year: str,
    destination_type: str | CallSlipDestinationType,
    other_destination: str,
    report_at: datetime,
    referral_id: UUID | None,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> CallSlip:
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
    digest = _creation_digest(actor_id=actor.pk, key=key)

    with transaction.atomic():
        locked_actor = (
            User.objects.select_for_update()
            .select_related("role")
            .filter(pk=actor.pk)
            .first()
        )
        if locked_actor is None:
            raise CallSlipNotPermitted(
                "The authenticated Guidance actor no longer exists."
            )
        _validate_operational_actor(locked_actor)

        existing = (
            CallSlip.objects.select_for_update()
            .filter(creation_key_digest=digest)
            .first()
        )
        if existing is not None:
            if existing.creation_request_fingerprint != fingerprint:
                raise CallSlipCreationConflict(
                    "The Idempotency-Key was already used for a different Call Slip request."
                )
            if not _student_in_scope(locked_actor, existing.student_id):
                raise CallSlipNotFound("The requested Call Slip was not found.")
            return _queryset().get(pk=existing.pk)

        issuer = _resolve_issuer_locked(locked_actor)
        student = (
            User.objects.select_for_update()
            .select_related("role")
            .filter(pk=student_id)
            .first()
        )
        student = _validate_student(student)
        if not _student_in_scope(locked_actor, student.pk):
            raise CallSlipNotPermitted(
                "The selected Student is outside the authenticated Guidance actor's Call Slip scope."
            )

        referral = None
        if referral_id is not None:
            referral = _lock_linked_referral(
                actor=locked_actor,
                referral_id=referral_id,
                student_id=student.pk,
            )

        revision = _active_call_slip_revision()
        try:
            with transaction.atomic():
                item = CallSlip.objects.create(
                    student=student,
                    student_name_snapshot=student.get_full_name(),
                    course_year_snapshot=course_snapshot,
                    referral=referral,
                    destination_type=normalized_destination,
                    other_destination=cleaned_other,
                    report_at=normalized_report_at,
                    issued_by=issuer,
                    issued_by_name_snapshot=issuer.get_full_name(),
                    form_revision=revision,
                    recorded_by=locked_actor,
                    creation_key_digest=digest,
                    creation_request_fingerprint=fingerprint,
                )
        except IntegrityError as exc:
            if referral is not None and CallSlip.objects.filter(
                referral_id=referral.pk
            ).exists():
                raise CallSlipReferralConflict(
                    "The linked Referral already has a Call Slip in this foundation."
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
        return item_for_audit


def list_call_slips(
    *,
    actor: User,
    student_id: UUID | None = None,
    issued_by_id: UUID | None = None,
    destination_type: str | CallSlipDestinationType | None = None,
    referral_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CallSlipPage:
    _validate_operational_actor(actor)
    qs = _scope_queryset(_queryset(), actor)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if issued_by_id is not None:
        qs = qs.filter(issued_by_id=issued_by_id)
    if destination_type is not None:
        normalized, _ = _normalize_destination(
            destination_type,
            "" if str(destination_type) != str(CallSlipDestinationType.OTHER) else "placeholder",
        )
        qs = qs.filter(destination_type=normalized)
    if referral_id is not None:
        qs = qs.filter(referral_id=referral_id)
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
        if item.interview_ended_at is not None:
            if item.interview_ended_at == normalized:
                return _queryset().get(pk=item.pk)
            raise CallSlipInterviewEndConflict(
                "interview_ended_at is immutable once recorded."
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
