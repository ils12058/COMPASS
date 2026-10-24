"""Transactional Good Moral request, correction, issuance, and PDF services."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Case, F, Q, When
from django.db.models.functions import Coalesce, Lower
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.accounts.profiles import get_person_profile_context
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    GOOD_MORAL_ISSUED,
    GOOD_MORAL_PREPARED,
    GOOD_MORAL_REQUEST_CANCELLED,
    GOOD_MORAL_REQUEST_CREATED,
    GOOD_MORAL_REQUEST_UPDATED,
    GOOD_MORAL_RETURNED_TO_PREPARATION,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_date, institution_today
from compass.common.ordering import parse_ordering
from compass.documents.rendering import DocumentRenderError, render_document_pdf
from compass.documents.template_specs import (
    LayoutFamily,
    UnknownDocumentTemplate,
    get_template_spec,
)
from compass.exit_interviews.models import (
    ExitInterview,
    ExitInterviewOpportunity,
    ExitInterviewOpportunitySource,
    ExitInterviewStatus,
)
from compass.feedback.models import CustomerFeedbackService, FeedbackOpportunitySourceType
from compass.feedback.services import ensure_feedback_opportunity
from compass.institutional_forms.filter_options import represented_form_revisions
from compass.institutional_forms.models import FormRevision
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    is_supported_form_revision,
    require_active_supported_form_revision,
)
from compass.inventory.models import StudentInventory
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.academic_years import get_current_academic_year
from compass.organization.models import StudentAffiliation
from compass.organization.program_policy import AcademicClassification, get_program_policy

from .models import (
    CANONICAL_SEMESTERS,
    CANONICAL_YEAR_LEVELS,
    GoodMoralInitiationOrigin,
    GoodMoralRequest,
    GoodMoralStatus,
    GoodMoralVariant,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = 160
MAX_CANCELLATION_REASON_LENGTH = 1000
CURRENT_STUDENT_FAMILY_KEY = "good_moral_current_student"
GRADUATE_FAMILY_KEY = "good_moral_graduate"
TEMPLATE_BY_VARIANT = {
    GoodMoralVariant.CURRENT_STUDENT: ("good_moral_current_student", 1),
    GoodMoralVariant.GRADUATE: ("good_moral_graduate", 1),
}


class GoodMoralError(RuntimeError):
    pass


class GoodMoralNotFound(GoodMoralError):
    pass


class GoodMoralNotPermitted(GoodMoralError):
    pass


class GoodMoralCurrentStudentRequired(GoodMoralError):
    pass


class GoodMoralInventoryRequired(GoodMoralError):
    pass


class GoodMoralF4AcademicEligibilityRequired(GoodMoralError):
    pass


class F4AcademicEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_CURRENT = "NOT_CURRENT"
    INVENTORY_REQUIRED = "INVENTORY_REQUIRED"
    UNCLASSIFIED_PROGRAM = "UNCLASSIFIED_PROGRAM"
    POSTGRADUATE_PROGRAM = "POSTGRADUATE_PROGRAM"
    UNSUPPORTED_YEAR_LEVEL = "UNSUPPORTED_YEAR_LEVEL"


@dataclass(frozen=True, slots=True)
class F4AcademicContext:
    status: F4AcademicEligibility
    academic_classification: AcademicClassification | None = None
    year_level: int | None = None


F4_YEAR_LEVEL_LABELS = {
    1: "1st Year",
    2: "2nd Year",
    3: "3rd Year",
    4: "4th Year",
}


class GoodMoralExitInterviewRequired(GoodMoralError):
    pass


class GoodMoralAffiliationRequired(GoodMoralError):
    pass


class GoodMoralConfigurationConflict(GoodMoralError):
    pass


class GoodMoralConflict(GoodMoralError):
    pass


class GoodMoralCreationConflict(GoodMoralConflict):
    pass


class GoodMoralNotReady(GoodMoralConflict):
    pass


class GoodMoralPreparationChanged(GoodMoralConflict):
    pass


class GoodMoralCertificateDateInFuture(GoodMoralConflict):
    """A stored certificate date is after the institutional date of preparation or issuance."""


class GoodMoralDocumentUnavailable(GoodMoralError):
    pass


class InvalidGoodMoralInput(GoodMoralError):
    pass


class GoodMoralOrdering(StrEnum):
    """Closed operational Good Moral orderings (ADR-090).

    Chronology is the time a request reached its current status: requested, ready for issuance,
    issued, or cancelled. Requested and ready requests are queues and default to the oldest
    waiting; issued and cancelled ones are history and default to the newest.
    """

    OLDEST_FIRST = "OLDEST_FIRST"
    NEWEST_FIRST = "NEWEST_FIRST"
    APPLICANT_ASC = "APPLICANT_ASC"
    APPLICANT_DESC = "APPLICANT_DESC"


_GOOD_MORAL_QUEUE_STATUSES = frozenset(
    {GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE}
)


def _good_moral_status_since():
    """When each request reached its current status, falling back to the request time."""

    return Coalesce(
        Case(
            When(status=GoodMoralStatus.READY_FOR_ISSUANCE, then=F("prepared_at")),
            When(status=GoodMoralStatus.ISSUED, then=F("issued_at")),
            When(status=GoodMoralStatus.CANCELLED, then=F("cancelled_at")),
            default=F("created_at"),
        ),
        F("created_at"),
    )


_GOOD_MORAL_ORDER_BY: dict[GoodMoralOrdering, tuple] = {
    GoodMoralOrdering.OLDEST_FIRST: ("status_since", "created_at", "id"),
    GoodMoralOrdering.NEWEST_FIRST: ("-status_since", "-created_at", "-id"),
    GoodMoralOrdering.APPLICANT_ASC: (Lower("applicant_name_snapshot"), "id"),
    GoodMoralOrdering.APPLICANT_DESC: (Lower("applicant_name_snapshot").desc(), "-id"),
}


def _good_moral_ordering(
    value: str | GoodMoralOrdering | None, *, status: str | None
) -> GoodMoralOrdering:
    default = (
        GoodMoralOrdering.OLDEST_FIRST
        if status in _GOOD_MORAL_QUEUE_STATUSES
        else GoodMoralOrdering.NEWEST_FIRST
    )
    return parse_ordering(value, GoodMoralOrdering, default=default, error=InvalidGoodMoralInput)


@dataclass(frozen=True, slots=True)
class GoodMoralPage:
    items: tuple[GoodMoralRequest, ...]
    page: int
    page_size: int
    has_next: bool
    form_revisions: tuple[FormRevision, ...] = ()
    ordering: GoodMoralOrdering | None = None


def _queryset():
    return GoodMoralRequest.objects.select_related(
        "student",
        "student__role",
        "inventory",
        "inventory__academic_year",
        "academic_year",
        "form_revision",
        "form_revision__family",
        "initiated_by",
        "issued_by",
        "prepared_by",
        "cancelled_by",
    )


def _validate_student(student: User, capability: str) -> None:
    if (
        not getattr(student, "pk", None)
        or not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability(capability)
    ):
        raise GoodMoralNotPermitted("Active Student Good Moral self-service access is required.")


def _validate_counselor(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability(capability)
    ):
        raise GoodMoralNotPermitted("Authorized Counselor Good Moral access is required.")


def _validate_operational(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not actor.has_capability(capability)
    ):
        raise GoodMoralNotPermitted("Authorized Guidance Good Moral access is required.")


def _validate_idempotency_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or value.strip() != value
        or not value.isprintable()
    ):
        raise InvalidGoodMoralInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    return value


def _validate_fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise InvalidGoodMoralInput("The Good Moral creation request fingerprint is invalid.")
    return value


def _creation_digest(*, student_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{student_id}\0{key}".encode()).hexdigest()


def _existing_creation_locked(
    *,
    student: User,
    digest: str,
    fingerprint: str,
    initiator: User | None = None,
) -> GoodMoralRequest | None:
    existing = (
        GoodMoralRequest.objects.select_for_update().filter(creation_key_digest=digest).first()
    )
    if existing is None:
        return None
    if existing.student_id != student.pk:
        raise GoodMoralCreationConflict(
            "The Good Moral creation identity belongs to a different Student."
        )
    if initiator is not None and (
        existing.initiated_by_id != initiator.pk
        or existing.initiation_origin != GoodMoralInitiationOrigin.GCO_ASSISTED
    ):
        raise GoodMoralCreationConflict("The creation identity belongs to another initiator.")
    if existing.creation_request_fingerprint != fingerprint:
        raise GoodMoralCreationConflict(
            "The Idempotency-Key was already used for a different Good Moral request."
        )
    return _queryset().get(pk=existing.pk)


def _recover_creation_conflict(
    *,
    student: User,
    digest: str,
    fingerprint: str,
    initiator: User | None = None,
) -> GoodMoralRequest:
    existing = _existing_creation_locked(
        student=student,
        digest=digest,
        fingerprint=fingerprint,
        initiator=initiator,
    )
    if existing is not None:
        return existing
    raise GoodMoralCreationConflict(
        "The Good Moral request could not be created because its creation identity conflicted."
    )


def _clean_required(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidGoodMoralInput(f"{label} is required.")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise InvalidGoodMoralInput(f"{label} is too long.")
    return cleaned


def _clean_optional(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidGoodMoralInput(f"{label} must be text.")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise InvalidGoodMoralInput(f"{label} is too long.")
    return cleaned


def _clean_receipt_number(value: object) -> str:
    if value is None:
        return ""
    return _clean_optional(value, "official_receipt_number", 96)


def _clean_date(value: object, label: str, *, allow_none: bool) -> date | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise InvalidGoodMoralInput(f"{label} must be a date.")
    return value


# Dates of facts that must already have happened: a Graduate's graduation and an Official
# Receipt. Historical dates stay valid; created_at and issued_at are never derived from them.
OCCURRED_DATE_FIELDS = frozenset({"graduation_date", "official_receipt_date"})


def _reject_future_occurred_date(value: object, label: str) -> None:
    if isinstance(value, date) and value > institution_today():
        raise InvalidGoodMoralInput(f"{label} must not be in the future.")


def _clean_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise InvalidGoodMoralInput("official_receipt_amount must be a nonnegative decimal.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidGoodMoralInput(
            "official_receipt_amount must be a nonnegative decimal."
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise InvalidGoodMoralInput("official_receipt_amount must be nonnegative.")
    if amount.as_tuple().exponent < -2:
        raise InvalidGoodMoralInput("official_receipt_amount supports at most two decimal places.")
    if amount >= Decimal("10000000000"):
        raise InvalidGoodMoralInput("official_receipt_amount is too large.")
    return amount


def _require_submitted_inventory(student: User):
    current_year = get_current_academic_year()
    if current_year is None:
        raise GoodMoralInventoryRequired(
            "A submitted Individual Inventory for the current Academic Year is required."
        )
    # Good Moral needs only these submitted academic facts. Avoid hydrating the Inventory's
    # confidential answer graph when creating or summarizing a certificate request.
    inventory = (
        StudentInventory.objects.select_related("academic_year", "program__college__campus")
        .only(
            "id",
            "student_id",
            "academic_year_id",
            "academic_year__label",
            "submitted_at",
            "program_id",
            "program__academic_classification",
            "program__year_level_policy_status",
            "program__applicable_year_levels",
            "program__college__code",
            "program__college__campus__code",
            "year_level",
            "course_currently_enrolled",
            "major",
        )
        .filter(student_id=student.pk, academic_year_id=current_year.pk)
        .first()
    )
    if inventory is None or inventory.submitted_at is None:
        raise GoodMoralInventoryRequired(
            "A submitted Individual Inventory for the current Academic Year is required."
        )
    return inventory


def _f4_academic_context(*, program, year_level: int | None) -> F4AcademicContext:
    if program is None:
        return F4AcademicContext(F4AcademicEligibility.UNCLASSIFIED_PROGRAM)
    metadata = get_program_policy(program)
    if metadata.academic_classification is None:
        return F4AcademicContext(F4AcademicEligibility.UNCLASSIFIED_PROGRAM)
    if metadata.academic_classification != AcademicClassification.BACHELORS:
        return F4AcademicContext(
            F4AcademicEligibility.POSTGRADUATE_PROGRAM,
            academic_classification=metadata.academic_classification,
        )
    if (
        year_level is None
        or metadata.applicable_year_levels is None
        or year_level not in metadata.applicable_year_levels
        or year_level not in F4_YEAR_LEVEL_LABELS
    ):
        return F4AcademicContext(
            F4AcademicEligibility.UNSUPPORTED_YEAR_LEVEL,
            academic_classification=metadata.academic_classification,
        )
    return F4AcademicContext(
        F4AcademicEligibility.ELIGIBLE,
        academic_classification=metadata.academic_classification,
        year_level=year_level,
    )


def get_f4_academic_context(student: User) -> F4AcademicContext:
    if not is_current_student(student):
        return F4AcademicContext(F4AcademicEligibility.NOT_CURRENT)
    current_year = get_current_academic_year()
    if current_year is None:
        return F4AcademicContext(F4AcademicEligibility.INVENTORY_REQUIRED)
    inventory = (
        StudentInventory.objects.select_related("program__college__campus")
        .only(
            "submitted_at",
            "program_id",
            "program__academic_classification",
            "program__year_level_policy_status",
            "program__applicable_year_levels",
            "program__college__code",
            "program__college__campus__code",
            "year_level",
        )
        .filter(student_id=student.pk, academic_year_id=current_year.pk)
        .first()
    )
    if inventory is None or inventory.submitted_at is None:
        return F4AcademicContext(F4AcademicEligibility.INVENTORY_REQUIRED)
    return _f4_academic_context(program=inventory.program, year_level=inventory.year_level)


def _require_f4_bachelors_inventory(inventory) -> str:
    academic = _f4_academic_context(program=inventory.program, year_level=inventory.year_level)
    if academic.status == F4AcademicEligibility.UNCLASSIFIED_PROGRAM:
        raise GoodMoralF4AcademicEligibilityRequired(
            "The submitted Individual Inventory Program is not classified for a Good Moral form. "
            "Contact the Guidance Office to confirm the Program record."
        )
    if academic.status == F4AcademicEligibility.POSTGRADUATE_PROGRAM:
        raise GoodMoralF4AcademicEligibilityRequired(
            "F4 is available for current Bachelor's students. COMPASS does not currently offer an "
            "approved postgraduate Good Moral form."
        )
    if academic.status == F4AcademicEligibility.UNSUPPORTED_YEAR_LEVEL:
        raise GoodMoralF4AcademicEligibilityRequired(
            "F4 supports 1st through 4th Year for the submitted Bachelor's Program. "
            "Correct the submitted Inventory or contact the Guidance Office."
        )
    assert academic.year_level is not None
    return F4_YEAR_LEVEL_LABELS[academic.year_level]


def _current_affiliation(student: User) -> StudentAffiliation:
    affiliation = (
        StudentAffiliation.objects.select_related("college__campus")
        .filter(student_id=student.pk)
        .first()
    )
    if (
        affiliation is None
        or not affiliation.college.is_active
        or not affiliation.college.campus.is_active
    ):
        raise GoodMoralAffiliationRequired(
            "A current active College affiliation is required for Current Student Good Moral."
        )
    return affiliation


def _graduation_prerequisite(student: User, academic_year_id: UUID):
    # Caller already holds the Student fence. Reopen, submission, and opportunity
    # transitions use the same fence, including the absent-opportunity case.
    opportunity = (
        ExitInterviewOpportunity.objects.select_for_update()
        .filter(
            student_id=student.pk,
            academic_year_id=academic_year_id,
            source=ExitInterviewOpportunitySource.GRADUATION,
        )
        .first()
    )
    if opportunity is None:
        return None, None
    interview = (
        ExitInterview.objects.select_for_update()
        .filter(
            student_id=student.pk,
            academic_year_id=academic_year_id,
            status=ExitInterviewStatus.SUBMITTED,
            last_submitted_at__isnull=False,
        )
        .first()
    )
    if interview is None:
        raise GoodMoralExitInterviewRequired(
            "Complete and submit your Exit Interview before requesting your graduation "
            "Good Moral certificate."
        )
    return opportunity, interview


def _validate_initiator(actor: User) -> None:
    _validate_operational(actor, "good_moral.initiate")
    _validate_operational(actor, "good_moral.view")


def _validate_creation_student(student: User, *, initiator: User | None) -> None:
    if initiator is None:
        _validate_student(student, "good_moral.request_self")
    elif not student.is_active or student.role.code != "STUDENT":
        raise GoodMoralNotFound("The Student was not found or is not eligible for this request.")


def _reject_assisted_pending(student: User, *, initiator: User | None) -> None:
    # All creation paths hold the Student row fence. Self-service's existing policy is unchanged.
    if (
        initiator is not None
        and GoodMoralRequest.objects.filter(
            student=student,
            status__in=_GOOD_MORAL_QUEUE_STATUSES,
        ).exists()
    ):
        raise GoodMoralConflict(
            "This Student already has a pending Good Moral request. Open it in the request queue."
        )


def _notify_assisted_creation(item: GoodMoralRequest) -> None:
    if item.initiation_origin == GoodMoralInitiationOrigin.GCO_ASSISTED:
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.GOOD_MORAL_REQUEST_INITIATED,
            source_type="good_moral_request",
            source_id=item.pk,
            target_type="GOOD_MORAL",
            target_id=item.pk,
        )


def create_my_current_student(
    *,
    student: User,
    year_level: str | None = None,
    semester: str,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> GoodMoralRequest:
    return _create_current_student(
        student=student,
        year_level=year_level,
        semester=semester,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        context=context,
    )


def create_my_graduate(
    *,
    student: User,
    degree: str,
    major: str,
    graduation_date: date,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> GoodMoralRequest:
    return _create_graduate(
        student=student,
        degree=degree,
        major=major,
        graduation_date=graduation_date,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        context=context,
    )


def create_assisted_request(
    *,
    actor: User,
    student_id: UUID,
    variant: GoodMoralVariant,
    details: dict[str, object],
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> GoodMoralRequest:
    _validate_initiator(actor)
    _validate_fingerprint(request_fingerprint)
    if getattr(context.actor, "pk", None) != actor.pk:
        raise GoodMoralNotPermitted("The audit actor must be the initiating staff member.")
    with transaction.atomic():
        # Serialize keys across target Students, then recheck both sources.
        locked_actor = (
            User.objects.select_for_update(of=("self",)).select_related("role").get(pk=actor.pk)
        )
        _validate_initiator(locked_actor)
        student = User.objects.select_related("role").filter(pk=student_id).first()
        if student is None:
            raise GoodMoralNotFound(
                "The Student was not found or is not eligible for this request."
            )
        if variant == GoodMoralVariant.CURRENT_STUDENT:
            create = _create_current_student
        elif variant == GoodMoralVariant.GRADUATE:
            create = _create_graduate
        else:
            raise InvalidGoodMoralInput("The Good Moral variant is not supported.")
        # Bind the source and variant even for service callers, independently of the wire hash.
        bound = hashlib.sha256(
            f"{actor.pk}\0{student_id}\0{variant}\0{request_fingerprint}\0".encode()
            + json.dumps(details, sort_keys=True, default=str).encode()
        ).hexdigest()
        return create(
            student=student,
            initiator=locked_actor,
            context=context,
            idempotency_key=idempotency_key,
            request_fingerprint=bound,
            **details,
        )


def list_eligible_students(
    *, actor: User, search: str | None = None, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
):
    _validate_initiator(actor)
    page, page_size = _pagination(page, page_size)
    term = _clean_optional(search if search is not None else "", "search", MAX_SEARCH_LENGTH)
    # Good Moral has office-wide authority, including Graduates. Other workflow selectors are
    # CURRENT-only and governed by their own scope; do not broaden those endpoints.
    rows = User.objects.filter(
        is_active=True,
        role__code="STUDENT",
        student_lifecycle_status__in=(
            StudentLifecycleStatus.CURRENT,
            StudentLifecycleStatus.GRADUATED,
            StudentLifecycleStatus.FORMER,
        ),
    ).select_related("organization_student_affiliation__college__campus")
    if term:
        rows = rows.filter(
            Q(institutional_id__icontains=term)
            | Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
        )
    offset = (page - 1) * page_size
    rows = list(
        rows.order_by("last_name", "first_name", "institutional_id", "id")[
            offset : offset + page_size + 1
        ]
    )
    return rows[:page_size], len(rows) > page_size


def _create_current_student(
    *,
    student: User,
    year_level: str | None = None,
    semester: str,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
    initiator: User | None = None,
) -> GoodMoralRequest:
    _validate_creation_student(student, initiator=initiator)
    key = _validate_idempotency_key(idempotency_key)
    fingerprint = _validate_fingerprint(request_fingerprint)
    year = "" if year_level is None else _clean_optional(year_level, "year_level", 64)
    term = _clean_required(semester, "semester", 80)
    digest = (
        hashlib.sha256(f"gco_assisted\0{initiator.pk}\0{key}".encode()).hexdigest()
        if initiator
        else _creation_digest(student_id=student.pk, key=key)
    )

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=student.pk)
            .first()
        )
        if locked_student is None:
            raise GoodMoralNotFound("The Student account was not found.")
        _validate_creation_student(locked_student, initiator=initiator)

        existing = _existing_creation_locked(
            student=locked_student,
            digest=digest,
            fingerprint=fingerprint,
            initiator=initiator,
        )
        if existing is not None:
            return existing

        _reject_assisted_pending(locked_student, initiator=initiator)
        if not is_current_student(locked_student):
            raise GoodMoralCurrentStudentRequired(
                "Current Student lifecycle is required to request the F4 Good Moral certificate."
            )

        inventory = _require_submitted_inventory(locked_student)
        if year and year not in CANONICAL_YEAR_LEVELS:
            raise InvalidGoodMoralInput("year_level must be between 1st and 4th Year.")
        if term not in CANONICAL_SEMESTERS:
            raise InvalidGoodMoralInput("semester is not supported.")
        inventory_year = _require_f4_bachelors_inventory(inventory)
        if year and year != inventory_year:
            raise InvalidGoodMoralInput(
                "year_level must match the Year Level on the submitted Individual Inventory."
            )
        graduation_opportunity, exit_interview = _graduation_prerequisite(
            locked_student, inventory.academic_year_id
        )
        affiliation = _current_affiliation(locked_student)
        profile = get_person_profile_context(locked_student)

        try:
            with transaction.atomic():
                item = GoodMoralRequest.objects.create(
                    student=locked_student,
                    initiated_by=initiator or locked_student,
                    initiation_origin=(
                        GoodMoralInitiationOrigin.GCO_ASSISTED
                        if initiator
                        else GoodMoralInitiationOrigin.STUDENT_SELF
                    ),
                    variant=GoodMoralVariant.CURRENT_STUDENT,
                    inventory=inventory,
                    academic_year=inventory.academic_year,
                    graduation_opportunity=graduation_opportunity,
                    exit_interview=exit_interview,
                    exit_interview_submitted_at=exit_interview.last_submitted_at
                    if exit_interview
                    else None,
                    applicant_name_snapshot=profile.full_name.strip(),
                    year_level_snapshot=inventory_year,
                    college_snapshot=affiliation.college.name.strip(),
                    course_snapshot=inventory.course_currently_enrolled.strip(),
                    major_snapshot=inventory.major.strip(),
                    semester_snapshot=term,
                    creation_key_digest=digest,
                    creation_request_fingerprint=fingerprint,
                )
        except IntegrityError:
            return _recover_creation_conflict(
                student=locked_student,
                digest=digest,
                fingerprint=fingerprint,
                initiator=initiator,
            )

        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "variant": item.variant,
                "transition": "NONE -> REQUESTED",
                **({"initiation_origin": item.initiation_origin} if initiator else {}),
            },
        )
        _notify_assisted_creation(item)
        return _queryset().get(pk=item.pk)


def _create_graduate(
    *,
    student: User,
    degree: str,
    major: str,
    graduation_date: date,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
    initiator: User | None = None,
) -> GoodMoralRequest:
    _validate_creation_student(student, initiator=initiator)
    key = _validate_idempotency_key(idempotency_key)
    fingerprint = _validate_fingerprint(request_fingerprint)
    degree_value = _clean_required(degree, "degree", 255)
    major_value = _clean_optional(major, "major", 180)
    graduation_value = _clean_date(graduation_date, "graduation_date", allow_none=False)
    assert graduation_value is not None
    _reject_future_occurred_date(graduation_value, "graduation_date")
    digest = (
        hashlib.sha256(f"gco_assisted\0{initiator.pk}\0{key}".encode()).hexdigest()
        if initiator
        else _creation_digest(student_id=student.pk, key=key)
    )

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=student.pk)
            .first()
        )
        if locked_student is None:
            raise GoodMoralNotFound("The Student account was not found.")
        _validate_creation_student(locked_student, initiator=initiator)

        existing = _existing_creation_locked(
            student=locked_student,
            digest=digest,
            fingerprint=fingerprint,
            initiator=initiator,
        )
        if existing is not None:
            return existing

        if locked_student.student_lifecycle_status not in StudentLifecycleStatus.values:
            raise InvalidGoodMoralInput(
                "A recorded Student lifecycle status is required to request F6."
            )

        _reject_assisted_pending(locked_student, initiator=initiator)
        profile = get_person_profile_context(locked_student)
        try:
            with transaction.atomic():
                item = GoodMoralRequest.objects.create(
                    student=locked_student,
                    initiated_by=initiator or locked_student,
                    initiation_origin=(
                        GoodMoralInitiationOrigin.GCO_ASSISTED
                        if initiator
                        else GoodMoralInitiationOrigin.STUDENT_SELF
                    ),
                    variant=GoodMoralVariant.GRADUATE,
                    applicant_name_snapshot=profile.full_name.strip(),
                    degree_snapshot=degree_value,
                    major_snapshot=major_value,
                    graduation_date=graduation_value,
                    creation_key_digest=digest,
                    creation_request_fingerprint=fingerprint,
                )
        except IntegrityError:
            return _recover_creation_conflict(
                student=locked_student,
                digest=digest,
                fingerprint=fingerprint,
                initiator=initiator,
            )

        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "variant": item.variant,
                "transition": "NONE -> REQUESTED",
                **({"initiation_origin": item.initiation_origin} if initiator else {}),
            },
        )
        _notify_assisted_creation(item)
        return _queryset().get(pk=item.pk)


def count_my_requested_requests(student: User) -> int | None:
    if (
        not getattr(student, "pk", None)
        or not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability("good_moral.view_self")
    ):
        return None
    return GoodMoralRequest.objects.filter(
        student_id=student.pk,
        status__in=(GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE),
    ).count()


def count_requested_requests(actor: User) -> int | None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not actor.has_capability("good_moral.view")
    ):
        return None
    return GoodMoralRequest.objects.filter(status=GoodMoralStatus.REQUESTED).count()


def count_ready_requests(actor: User) -> int | None:
    try:
        _validate_operational(actor, "good_moral.view")
    except GoodMoralNotPermitted:
        return None
    return GoodMoralRequest.objects.filter(status=GoodMoralStatus.READY_FOR_ISSUANCE).count()


def list_mine(student: User) -> tuple[GoodMoralRequest, ...]:
    _validate_student(student, "good_moral.view_self")
    return tuple(_queryset().filter(student_id=student.pk).order_by("-created_at", "id"))


def get_mine(*, student: User, request_id: UUID) -> GoodMoralRequest:
    _validate_student(student, "good_moral.view_self")
    item = _queryset().filter(pk=request_id, student_id=student.pk).first()
    if item is None:
        raise GoodMoralNotFound("The requested Good Moral record was not found.")
    return item


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidGoodMoralInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidGoodMoralInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def list_requests(
    *,
    actor: User,
    variant: str | None = None,
    status: str | None = None,
    student_id: UUID | None = None,
    search: str | None = None,
    form_revision_id: UUID | None = None,
    academic_year_id: UUID | None = None,
    ordering: str | GoodMoralOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> GoodMoralPage:
    _validate_operational(actor, "good_moral.view")
    page, page_size = _pagination(page, page_size)
    queryset = _queryset()
    revisions = represented_form_revisions(
        queryset, family_keys=("good_moral_current_student", "good_moral_graduate")
    )
    if form_revision_id is not None:
        queryset = queryset.filter(form_revision_id=form_revision_id)
    if academic_year_id is not None:
        queryset = queryset.filter(academic_year_id=academic_year_id)
    if variant is not None:
        if variant not in GoodMoralVariant.values:
            raise InvalidGoodMoralInput("variant is not supported.")
        queryset = queryset.filter(variant=variant)
    if status is not None:
        if status not in GoodMoralStatus.values:
            raise InvalidGoodMoralInput("status is not supported.")
        queryset = queryset.filter(status=status)
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    if search is not None:
        if not isinstance(search, str):
            raise InvalidGoodMoralInput("search must be text.")
        term = search.strip()
        if len(term) > MAX_SEARCH_LENGTH:
            raise InvalidGoodMoralInput(f"search must be at most {MAX_SEARCH_LENGTH} characters.")
        if term:
            identity = Q()
            for token in term.split():
                identity &= (
                    Q(student__institutional_id__icontains=token)
                    | Q(student__first_name__icontains=token)
                    | Q(student__middle_name__icontains=token)
                    | Q(student__last_name__icontains=token)
                    | Q(applicant_name_snapshot__icontains=token)
                )
            queryset = queryset.filter(identity | Q(official_receipt_number__icontains=term))
    resolved = _good_moral_ordering(ordering, status=status)
    queryset = queryset.annotate(status_since=_good_moral_status_since()).order_by(
        *_GOOD_MORAL_ORDER_BY[resolved]
    )
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return GoodMoralPage(
        tuple(rows[:page_size]), page, page_size, len(rows) > page_size, revisions, resolved
    )


def get_request(*, actor: User, request_id: UUID) -> GoodMoralRequest:
    _validate_operational(actor, "good_moral.view")
    item = _queryset().filter(pk=request_id).first()
    if item is None:
        raise GoodMoralNotFound("The requested Good Moral record was not found.")
    return item


CURRENT_EDITABLE_FIELDS = frozenset(
    {
        "applicant_name_snapshot",
        "year_level_snapshot",
        "college_snapshot",
        "course_snapshot",
        "major_snapshot",
        "semester_snapshot",
        "official_receipt_number",
        "official_receipt_date",
        "official_receipt_amount",
    }
)
GRADUATE_EDITABLE_FIELDS = frozenset(
    {
        "applicant_name_snapshot",
        "degree_snapshot",
        "major_snapshot",
        "graduation_date",
        "official_receipt_number",
        "official_receipt_date",
        "official_receipt_amount",
    }
)


CLERICAL_FIELDS = frozenset(
    {
        "year_level_snapshot",
        "course_snapshot",
        "major_snapshot",
        "semester_snapshot",
        "official_receipt_number",
        "official_receipt_date",
        "official_receipt_amount",
    }
)


def correction_fields(actor: User, item: GoodMoralRequest) -> frozenset[str]:
    allowed = (
        CURRENT_EDITABLE_FIELDS
        if item.variant == GoodMoralVariant.CURRENT_STUDENT
        else GRADUATE_EDITABLE_FIELDS
    )
    if actor.role.code != "COUNSELOR" or not actor.has_capability("good_moral.manage"):
        return allowed & CLERICAL_FIELDS
    return allowed


def _normalize_update(field_name: str, value: object) -> object:
    if field_name == "applicant_name_snapshot":
        return _clean_optional(value, "applicant_name", 200)
    if field_name == "year_level_snapshot":
        return _clean_optional(value, "year_level", 64)
    if field_name == "college_snapshot":
        return _clean_optional(value, "college", 160)
    if field_name == "course_snapshot":
        return _clean_optional(value, "course", 180)
    if field_name == "major_snapshot":
        return _clean_optional(value, "major", 180)
    if field_name == "semester_snapshot":
        return _clean_optional(value, "semester", 80)
    if field_name == "degree_snapshot":
        return _clean_optional(value, "degree", 255)
    if field_name == "graduation_date":
        return _clean_date(value, "graduation_date", allow_none=True)
    if field_name == "official_receipt_number":
        return _clean_receipt_number(value)
    if field_name == "official_receipt_date":
        return _clean_date(value, "official_receipt_date", allow_none=True)
    if field_name == "official_receipt_amount":
        return _clean_amount(value)
    raise InvalidGoodMoralInput(f"{field_name} cannot be changed through Good Moral correction.")


def update_request(
    *,
    actor: User,
    request_id: UUID,
    changes: dict[str, object],
    context: AuditContext,
    expected_resource_version: str | None = None,
    expected_receipt_revision: object = ...,
    operation_id: UUID | None = None,
) -> GoodMoralRequest:
    from . import receipt_identity as receipts

    _validate_operational(actor, "good_moral.prepare")
    with transaction.atomic():
        item = GoodMoralRequest.objects.select_for_update().filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        intent = receipts.begin_edit(
            item=item,
            actor=actor,
            changes=changes,
            context=context,
            expected_resource_version=expected_resource_version,
            expected_receipt_revision=receipts.UNSET
            if expected_receipt_revision is ...
            else expected_receipt_revision,
            operation_id=operation_id,
        )
        if intent and intent.replay:
            result = _queryset().get(pk=item.pk)
            result.receipt_mutation_result = intent.replay
            return result
        if item.status not in {GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE}:
            raise GoodMoralConflict("Issued and cancelled Good Moral requests cannot be corrected.")

        allowed = correction_fields(actor, item)
        unknown = set(changes) - allowed
        if unknown:
            raise InvalidGoodMoralInput(
                "Unsupported correction fields for this Good Moral variant: "
                + ", ".join(sorted(unknown))
                + "."
            )

        normalized = {
            name: (
                receipts.receipt_display(value)
                if intent and name == "official_receipt_number"
                else _normalize_update(name, value)
            )
            for name, value in changes.items()
        }
        if intent:
            normalized.setdefault(
                "official_receipt_number", receipts.receipt_display(item.official_receipt_number)
            )
        changed = sorted(name for name, value in normalized.items() if getattr(item, name) != value)
        if not changed:
            operation = receipts.finish_edit(item=item, actor=actor, intent=intent)
            result = _queryset().get(pk=item.pk)
            result.receipt_mutation_result = operation
            return result
        # Only a changed value is checked, so an unrelated correction never fails on a stored date.
        for name in OCCURRED_DATE_FIELDS.intersection(changed):
            _reject_future_occurred_date(normalized[name], name)

        if item.variant == GoodMoralVariant.CURRENT_STUDENT:
            if (
                "year_level_snapshot" in changed
                and normalized["year_level_snapshot"] not in CANONICAL_YEAR_LEVELS
            ):
                raise InvalidGoodMoralInput("year_level is not supported.")
            if "year_level_snapshot" in changed:
                linked_inventory = (
                    StudentInventory.objects.select_related("program__college__campus")
                    .only(
                        "submitted_at",
                        "program_id",
                        "program__academic_classification",
                        "program__year_level_policy_status",
                        "program__applicable_year_levels",
                        "program__college__code",
                        "program__college__campus__code",
                        "year_level",
                    )
                    .filter(pk=item.inventory_id)
                    .first()
                    if item.inventory_id
                    else None
                )
                linked_context = (
                    _f4_academic_context(
                        program=linked_inventory.program,
                        year_level=linked_inventory.year_level,
                    )
                    if linked_inventory is not None and linked_inventory.submitted_at is not None
                    else None
                )
                expected_year = (
                    F4_YEAR_LEVEL_LABELS[linked_context.year_level]
                    if linked_context is not None
                    and linked_context.status == F4AcademicEligibility.ELIGIBLE
                    and linked_context.year_level is not None
                    else None
                )
                if expected_year is None or normalized["year_level_snapshot"] != expected_year:
                    raise InvalidGoodMoralInput(
                        "Corrected year_level must match the linked submitted Inventory's "
                        "classified Bachelor's Program and Year Level."
                    )
            if (
                "semester_snapshot" in changed
                and normalized["semester_snapshot"] not in CANONICAL_SEMESTERS
            ):
                raise InvalidGoodMoralInput("semester is not supported.")

        if intent:
            receipts.append_revision(
                item=item, actor=actor, normalized=normalized, intent=intent, context=context
            )
        for name in changed:
            setattr(item, name, normalized[name])
        returned = item.status == GoodMoralStatus.READY_FOR_ISSUANCE
        if returned:
            item.status = GoodMoralStatus.REQUESTED
            item.prepared_at = None
            item.prepared_by = None
            item.prepared_receipt_verification = None
        item.save(
            update_fields=[
                *changed,
                "status",
                "prepared_at",
                "prepared_by",
                "prepared_receipt_verification",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={"variant": item.variant, "changed_fields": changed},
        )
        if returned:
            record_event(
                context=context,
                action=GOOD_MORAL_RETURNED_TO_PREPARATION,
                outcome=AuditOutcome.SUCCESS,
                target_type="goodmoral.request",
                target_id=item.pk,
                metadata={"variant": item.variant, "transition": "READY_FOR_ISSUANCE -> REQUESTED"},
            )
        operation = receipts.finish_edit(item=item, actor=actor, intent=intent)
        result = _queryset().get(pk=item.pk)
        result.receipt_mutation_result = operation
        return result


def prepare_request(
    *,
    actor: User,
    request_id: UUID,
    context: AuditContext,
    expected_resource_version: str | None = None,
    now: datetime | None = None,
) -> GoodMoralRequest:
    from . import receipt_verification as inspection

    _validate_operational(actor, "good_moral.prepare")
    prepared_at = now or timezone.now()
    if timezone.is_naive(prepared_at):
        raise InvalidGoodMoralInput("The preparation time must be timezone-aware.")
    with transaction.atomic():
        item = GoodMoralRequest.objects.select_for_update().filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        if (
            expected_resource_version is not None
            and item.updated_at.isoformat() != expected_resource_version
        ):
            raise GoodMoralPreparationChanged(
                "This request changed. Review its latest details first."
            )
        evidence = inspection.gate(
            item, expected_resource_version=expected_resource_version, lock=True
        )
        if evidence:
            actor = inspection.authority(actor, "good_moral.prepare", context, lock=True)
        if item.status == GoodMoralStatus.READY_FOR_ISSUANCE:
            return _queryset().get(pk=item.pk)
        if item.status != GoodMoralStatus.REQUESTED:
            raise GoodMoralConflict("Only a requested Good Moral certificate can be prepared.")
        _validate_issuance_completeness(item, on=institution_date(prepared_at))
        item.status = GoodMoralStatus.READY_FOR_ISSUANCE
        item.prepared_by = actor
        item.prepared_at = prepared_at
        item.prepared_receipt_verification = evidence[1] if evidence else None
        item.save(
            update_fields=[
                "status",
                "prepared_by",
                "prepared_at",
                "prepared_receipt_verification",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=GOOD_MORAL_PREPARED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={"variant": item.variant, "transition": "REQUESTED -> READY_FOR_ISSUANCE"},
        )
        if evidence:
            inspection.authority(actor, "good_moral.prepare", context)
            if inspection.decision_for(item, evidence[0]).snapshot() != evidence[2].snapshot():
                raise inspection.ReceiptBlocked(
                    "policy_unresolved", "The approved fee decision changed during preparation."
                )
        return _queryset().get(pk=item.pk)


def _require_meaningful(value: str, label: str) -> None:
    if not value.strip():
        raise GoodMoralConflict(f"{label} must be completed before issuance.")


def _validate_issuance_completeness(item: GoodMoralRequest, *, on: date) -> None:
    """Check what the certificate will state, as of the institutional date ``on``.

    The date checks repeat the write-time rules for rows saved before them (ADR-096); a stored date
    is never changed here, only refused until corrected.
    """

    _require_meaningful(item.applicant_name_snapshot, "Applicant name")
    if item.official_receipt_date is not None and item.official_receipt_date > on:
        raise GoodMoralCertificateDateInFuture(
            "Official Receipt date cannot be in the future. "
            "Correct the certificate details before issuance."
        )
    if item.variant == GoodMoralVariant.CURRENT_STUDENT:
        if item.inventory_id is None or item.academic_year_id is None:
            raise GoodMoralConflict("Current Student Good Moral provenance is incomplete.")
        _require_meaningful(item.year_level_snapshot, "Year level")
        _require_meaningful(item.college_snapshot, "College")
        _require_meaningful(item.course_snapshot, "Course")
        _require_meaningful(item.semester_snapshot, "Semester")
        return
    if item.variant == GoodMoralVariant.GRADUATE:
        _require_meaningful(item.degree_snapshot, "Degree")
        if item.graduation_date is None:
            raise GoodMoralConflict("Graduation date must be completed before issuance.")
        if item.graduation_date > on:
            raise GoodMoralCertificateDateInFuture(
                "Graduation date cannot be in the future. "
                "Correct the certificate details before issuance."
            )
        return
    raise GoodMoralConfigurationConflict("The Good Moral variant is not supported.")


def _family_for_variant(variant: str) -> str:
    if variant == GoodMoralVariant.CURRENT_STUDENT:
        return CURRENT_STUDENT_FAMILY_KEY
    if variant == GoodMoralVariant.GRADUATE:
        return GRADUATE_FAMILY_KEY
    raise GoodMoralConfigurationConflict("The Good Moral variant is not supported.")


def _template_for_variant(variant: str) -> tuple[str, int]:
    try:
        return TEMPLATE_BY_VARIANT[GoodMoralVariant(variant)]
    except (KeyError, ValueError) as exc:
        raise GoodMoralConfigurationConflict(
            "The Good Moral presentation template is not configured."
        ) from exc


def issue_request(
    *,
    actor: User,
    request_id: UUID,
    context: AuditContext,
    now: datetime | None = None,
    expected_preparation_version: str | None = None,
    expected_resource_version: str | None = None,
    expected_receipt_revision: UUID | None = None,
    expected_receipt_verification: UUID | None = None,
) -> GoodMoralRequest:
    from . import receipt_verification as inspection

    _validate_counselor(actor, "good_moral.issue")
    issued_at = now or timezone.now()
    if timezone.is_naive(issued_at):
        raise InvalidGoodMoralInput("The issuance time must be timezone-aware.")

    with transaction.atomic():
        item = GoodMoralRequest.objects.select_for_update().filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        if item.status == GoodMoralStatus.ISSUED:
            return _queryset().get(pk=item.pk)
        if item.status != GoodMoralStatus.READY_FOR_ISSUANCE:
            raise GoodMoralNotReady(
                "Mark this request ready after reviewing its certificate details."
            )
        if (
            expected_preparation_version is not None
            and item.prepared_at.isoformat() != expected_preparation_version
        ):
            raise GoodMoralPreparationChanged(
                "This request was prepared again. Review its latest details before issuing."
            )

        evidence = inspection.gate(
            item,
            expected_resource_version=expected_resource_version,
            expected_receipt_revision=expected_receipt_revision,
            expected_verification=expected_receipt_verification,
            issuing=True,
            lock=True,
        )
        if evidence:
            if not expected_preparation_version:
                raise GoodMoralPreparationChanged("Review the current preparation before issuing.")
            actor = inspection.authority(
                actor,
                "good_moral.issue",
                context,
                lock=True,
                student_id=item.student_id
                if item.variant == GoodMoralVariant.CURRENT_STUDENT
                else None,
            )

        if item.variant == GoodMoralVariant.CURRENT_STUDENT:
            locked_student = (
                User.objects.select_for_update(of=("self",))
                .select_related("role")
                .filter(pk=item.student_id)
                .first()
            )
            if locked_student is None or not is_current_student(locked_student):
                raise GoodMoralCurrentStudentRequired(
                    "The Student must still be CURRENT before an F4 certificate can be issued."
                )

        _validate_issuance_completeness(item, on=institution_date(issued_at))
        family_key = _family_for_variant(item.variant)
        try:
            revision = require_active_supported_form_revision(family_key)
        except InstitutionalFormConflict as exc:
            raise GoodMoralConfigurationConflict(
                "No active supported Good Moral Form Revision is configured for this variant."
            ) from exc

        template_key, template_version = _template_for_variant(item.variant)
        if (
            family_key == "good_moral_current_student"
            and revision.official_code == "UCN-OP-GCO-01F4"
        ):
            template_version = 2
        try:
            spec = get_template_spec(template_key, template_version)
        except UnknownDocumentTemplate as exc:
            raise GoodMoralConfigurationConflict(
                "The Good Moral presentation template is not available."
            ) from exc
        if spec.layout_family is not LayoutFamily.CERTIFICATE:
            raise GoodMoralConfigurationConflict(
                "The Good Moral presentation template is not a certificate layout."
            )

        issuer_name = actor.get_full_name().strip()
        if not issuer_name:
            raise GoodMoralConflict("Issuer name is required before issuance.")

        item.issued_receipt_assignment = evidence[0] if evidence else None
        item.issued_receipt_verification = evidence[1] if evidence else None
        item.form_revision = revision
        item.document_template_key = template_key
        item.document_template_version = template_version
        item.issued_at = issued_at
        item.issued_by = actor
        item.issued_by_name_snapshot = issuer_name
        item.status = GoodMoralStatus.ISSUED
        item.save(
            update_fields=[
                "issued_receipt_assignment",
                "issued_receipt_verification",
                "form_revision",
                "document_template_key",
                "document_template_version",
                "issued_at",
                "issued_by",
                "issued_by_name_snapshot",
                "status",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=GOOD_MORAL_ISSUED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "variant": item.variant,
                "transition": "READY_FOR_ISSUANCE -> ISSUED",
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "document_template_key": template_key,
                "document_template_version": template_version,
            },
        )
        opportunity = ensure_feedback_opportunity(
            student=item.student,
            source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
            source_id=item.pk,
            service_kind=CustomerFeedbackService.REQUEST_FOR_CERTIFICATION,
            service_label_snapshot=(
                "Issuance of Good Moral Certificate"
                if item.variant == GoodMoralVariant.CURRENT_STUDENT
                else "Issuance of Good Moral Certificate (graduate)"
            ),
            service_completed_at=issued_at,
        )
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.GOOD_MORAL_ISSUED,
            source_type="good_moral_request",
            source_id=item.pk,
            target_type="GOOD_MORAL",
            target_id=item.pk,
        )
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.FEEDBACK_INVITATION,
            source_type="feedback_opportunity",
            source_id=opportunity.pk,
            target_type="FEEDBACK",
            target_id=opportunity.pk,
        )
        if evidence:
            inspection.authority(actor, "good_moral.issue", context)
            if inspection.decision_for(item, evidence[0]).snapshot() != evidence[2].snapshot():
                raise inspection.ReceiptBlocked(
                    "policy_unresolved", "The approved fee decision changed during issuance."
                )
        return _queryset().get(pk=item.pk)


def cancel_request(
    *,
    actor: User,
    request_id: UUID,
    reason: str,
    self_service: bool,
    context: AuditContext,
    now: datetime | None = None,
) -> GoodMoralRequest:
    if self_service:
        _validate_student(actor, "good_moral.request_self")
    else:
        _validate_counselor(actor, "good_moral.manage")
    cleaned_reason = _clean_required(
        reason,
        "reason",
        MAX_CANCELLATION_REASON_LENGTH,
    )
    cancelled_at = now or timezone.now()
    if timezone.is_naive(cancelled_at):
        raise InvalidGoodMoralInput("The cancellation time must be timezone-aware.")

    with transaction.atomic():
        queryset = GoodMoralRequest.objects.select_for_update()
        if self_service:
            queryset = queryset.filter(student_id=actor.pk)
        item = queryset.filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        if item.status == GoodMoralStatus.CANCELLED:
            return _queryset().get(pk=item.pk)
        if item.status not in {GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE}:
            raise GoodMoralConflict("An ISSUED Good Moral request cannot be cancelled.")

        from . import receipt_verification as inspection

        if inspection.active_mode(lock=True):
            inspection.invalidate(item=item, actor=actor, context=context, reason="CANCELLED")
        previous_status = item.status
        item.status = GoodMoralStatus.CANCELLED
        item.cancelled_at = cancelled_at
        item.cancelled_by = actor
        item.cancellation_reason = cleaned_reason
        item.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_CANCELLED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "variant": item.variant,
                "transition": f"{previous_status} -> CANCELLED",
                "self_service": self_service,
            },
        )
        return _queryset().get(pk=item.pk)


def _certificate_fragment(value: str, wrapper: str) -> str:
    """Remove one template-supplied wrapper without changing the saved snapshot."""

    original = value.strip()
    fragment = re.sub(wrapper, "", original, count=1, flags=re.IGNORECASE).strip()
    return fragment or original


def build_certificate_render_context(item: GoodMoralRequest) -> dict[str, object]:
    """Build an issued certificate only from frozen request/QMS provenance."""

    if item.status != GoodMoralStatus.ISSUED:
        raise GoodMoralConflict("Only an issued Good Moral request has a final certificate PDF.")
    if (
        item.form_revision_id is None
        or item.issued_at is None
        or not item.issued_by_name_snapshot.strip()
        or not item.document_template_key
        or item.document_template_version is None
    ):
        raise GoodMoralConfigurationConflict("Issued Good Moral provenance is incomplete.")

    expected_family = (
        "good_moral_current_student"
        if item.variant == GoodMoralVariant.CURRENT_STUDENT
        else "good_moral_graduate"
    )
    if item.form_revision.family.key != expected_family or not is_supported_form_revision(
        item.form_revision
    ):
        raise GoodMoralDocumentUnavailable("The saved Good Moral form identity is unsupported.")

    year_level = item.year_level_snapshot
    college = item.college_snapshot
    semester = item.semester_snapshot
    if item.variant == GoodMoralVariant.CURRENT_STUDENT:
        year_level = _certificate_fragment(year_level, r"\s+year$")
        college = _certificate_fragment(college, r"^college\s+of\s+")
        semester = _certificate_fragment(semester, r"\s+semester$")

    return {
        "certificate": {
            "applicant_name": item.applicant_name_snapshot,
            "year_level": year_level,
            "college": college,
            "course": item.course_snapshot,
            "major": item.major_snapshot,
            "semester": semester,
            "academic_year": item.academic_year.label if item.academic_year_id else "",
            "degree": item.degree_snapshot,
            "graduation_date": item.graduation_date,
            "issued_on": institution_date(item.issued_at),
            "issuer_name": item.issued_by_name_snapshot,
            "official_receipt_number": item.official_receipt_number,
            "official_receipt_date": item.official_receipt_date,
            "official_receipt_amount": item.official_receipt_amount,
        },
        "controlled_form": {
            "official_code": item.form_revision.official_code,
            "official_revision": item.form_revision.official_revision,
            "page_label": "Page 1 of 1",
        },
    }


def render_certificate_pdf(item: GoodMoralRequest) -> bytes:
    context = build_certificate_render_context(item)
    try:
        result = render_document_pdf(
            item.document_template_key,
            item.document_template_version,
            context=context,
        )
    except DocumentRenderError as exc:
        raise GoodMoralDocumentUnavailable(
            "The saved Good Moral presentation version cannot be rendered by this COMPASS build."
        ) from exc
    return result.pdf_bytes
