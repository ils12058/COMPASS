"""Transactional Good Moral request, correction, issuance, and PDF services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.accounts.profiles import get_person_profile_context
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    GOOD_MORAL_ISSUED,
    GOOD_MORAL_REQUEST_CREATED,
    GOOD_MORAL_REQUEST_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.documents.rendering import DocumentRenderError, render_document_pdf
from compass.documents.template_specs import (
    LayoutFamily,
    UnknownDocumentTemplate,
    get_template_spec,
)
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.inventory.services import (
    CurrentAcademicYearNotConfigured,
    InventoryConflict,
    require_current_submitted_inventory,
)
from compass.organization.models import StudentAffiliation

from .models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
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


class GoodMoralGraduatedStudentRequired(GoodMoralError):
    pass


class GoodMoralInventoryRequired(GoodMoralError):
    pass


class GoodMoralAffiliationRequired(GoodMoralError):
    pass


class GoodMoralConfigurationConflict(GoodMoralError):
    pass


class GoodMoralConflict(GoodMoralError):
    pass


class GoodMoralDocumentUnavailable(GoodMoralError):
    pass


class InvalidGoodMoralInput(GoodMoralError):
    pass


@dataclass(frozen=True, slots=True)
class GoodMoralPage:
    items: tuple[GoodMoralRequest, ...]
    page: int
    page_size: int
    has_next: bool


def _queryset():
    return GoodMoralRequest.objects.select_related(
        "student",
        "student__role",
        "inventory",
        "inventory__academic_year",
        "academic_year",
        "form_revision",
        "form_revision__family",
        "issued_by",
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
    try:
        return require_current_submitted_inventory(student)
    except (CurrentAcademicYearNotConfigured, InventoryConflict) as exc:
        raise GoodMoralInventoryRequired(
            "A submitted Individual Inventory for the current Academic Year is required."
        ) from exc


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


def create_my_current_student(
    *,
    student: User,
    year_level: str,
    semester: str,
    context: AuditContext,
) -> GoodMoralRequest:
    _validate_student(student, "good_moral.request_self")
    year = _clean_required(year_level, "year_level", 64)
    term = _clean_required(semester, "semester", 80)

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise GoodMoralNotFound("The Student account was not found.")
        _validate_student(locked_student, "good_moral.request_self")
        if not is_current_student(locked_student):
            raise GoodMoralCurrentStudentRequired(
                "Current Student lifecycle is required to request the F4 Good Moral certificate."
            )

        inventory = _require_submitted_inventory(locked_student)
        affiliation = _current_affiliation(locked_student)
        profile = get_person_profile_context(locked_student)

        item = GoodMoralRequest.objects.create(
            student=locked_student,
            variant=GoodMoralVariant.CURRENT_STUDENT,
            inventory=inventory,
            academic_year=inventory.academic_year,
            applicant_name_snapshot=profile.full_name.strip(),
            year_level_snapshot=year,
            college_snapshot=affiliation.college.name.strip(),
            course_snapshot=inventory.course_currently_enrolled.strip(),
            major_snapshot=inventory.major.strip(),
            semester_snapshot=term,
        )
        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={"variant": item.variant, "transition": "NONE -> REQUESTED"},
        )
        return _queryset().get(pk=item.pk)


def create_my_graduate(
    *,
    student: User,
    degree: str,
    major: str,
    graduation_date: date,
    context: AuditContext,
) -> GoodMoralRequest:
    _validate_student(student, "good_moral.request_self")
    degree_value = _clean_required(degree, "degree", 255)
    major_value = _clean_optional(major, "major", 180)
    graduation_value = _clean_date(graduation_date, "graduation_date", allow_none=False)
    assert graduation_value is not None

    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise GoodMoralNotFound("The Student account was not found.")
        _validate_student(locked_student, "good_moral.request_self")
        if locked_student.student_lifecycle_status != StudentLifecycleStatus.GRADUATED:
            raise GoodMoralGraduatedStudentRequired(
                "Graduated Student lifecycle is required to request the F6 Good Moral certificate."
            )

        profile = get_person_profile_context(locked_student)
        item = GoodMoralRequest.objects.create(
            student=locked_student,
            variant=GoodMoralVariant.GRADUATE,
            applicant_name_snapshot=profile.full_name.strip(),
            degree_snapshot=degree_value,
            major_snapshot=major_value,
            graduation_date=graduation_value,
        )
        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={"variant": item.variant, "transition": "NONE -> REQUESTED"},
        )
        return _queryset().get(pk=item.pk)


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
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> GoodMoralPage:
    _validate_counselor(actor, "good_moral.view")
    page, page_size = _pagination(page, page_size)
    queryset = _queryset()
    if variant is not None:
        if variant not in GoodMoralVariant.values:
            raise InvalidGoodMoralInput("variant is not supported.")
        queryset = queryset.filter(variant=variant)
    if status is not None:
        if status not in GoodMoralStatus.values:
            raise InvalidGoodMoralInput("status is not supported.")
        queryset = queryset.filter(status=status)
    queryset = queryset.order_by("-created_at", "id")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return GoodMoralPage(tuple(rows[:page_size]), page, page_size, len(rows) > page_size)


def get_request(*, actor: User, request_id: UUID) -> GoodMoralRequest:
    _validate_counselor(actor, "good_moral.view")
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
) -> GoodMoralRequest:
    _validate_counselor(actor, "good_moral.manage")
    with transaction.atomic():
        item = GoodMoralRequest.objects.select_for_update().filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        if item.status != GoodMoralStatus.REQUESTED:
            raise GoodMoralConflict("An issued Good Moral request is immutable.")

        allowed = (
            CURRENT_EDITABLE_FIELDS
            if item.variant == GoodMoralVariant.CURRENT_STUDENT
            else GRADUATE_EDITABLE_FIELDS
        )
        unknown = set(changes) - allowed
        if unknown:
            raise InvalidGoodMoralInput(
                "Unsupported correction fields for this Good Moral variant: "
                + ", ".join(sorted(unknown))
                + "."
            )

        normalized = {name: _normalize_update(name, value) for name, value in changes.items()}
        changed = sorted(name for name, value in normalized.items() if getattr(item, name) != value)
        if not changed:
            return _queryset().get(pk=item.pk)

        for name in changed:
            setattr(item, name, normalized[name])
        item.save(update_fields=[*changed, "updated_at"])
        record_event(
            context=context,
            action=GOOD_MORAL_REQUEST_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={"variant": item.variant, "changed_fields": changed},
        )
        return _queryset().get(pk=item.pk)


def _require_meaningful(value: str, label: str) -> None:
    if not value.strip():
        raise GoodMoralConflict(f"{label} must be completed before issuance.")


def _validate_issuance_completeness(item: GoodMoralRequest) -> None:
    _require_meaningful(item.applicant_name_snapshot, "Applicant name")
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
) -> GoodMoralRequest:
    _validate_counselor(actor, "good_moral.issue")
    issued_at = now or timezone.now()
    if timezone.is_naive(issued_at):
        raise InvalidGoodMoralInput("The issuance time must be timezone-aware.")

    with transaction.atomic():
        item = (
            GoodMoralRequest.objects.select_for_update()
            .select_related("student__role", "inventory", "academic_year")
            .filter(pk=request_id)
            .first()
        )
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        if item.status == GoodMoralStatus.ISSUED:
            return _queryset().get(pk=item.pk)

        if item.variant == GoodMoralVariant.CURRENT_STUDENT:
            locked_student = (
                User.objects.select_for_update()
                .select_related("role")
                .filter(pk=item.student_id)
                .first()
            )
            if locked_student is None or not is_current_student(locked_student):
                raise GoodMoralCurrentStudentRequired(
                    "The Student must still be CURRENT before an F4 certificate can be issued."
                )

        _validate_issuance_completeness(item)
        family_key = _family_for_variant(item.variant)
        try:
            revision = require_active_supported_form_revision(family_key)
        except InstitutionalFormConflict as exc:
            raise GoodMoralConfigurationConflict(
                "No active supported Good Moral Form Revision is configured for this variant."
            ) from exc

        template_key, template_version = _template_for_variant(item.variant)
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

        item.form_revision = revision
        item.document_template_key = template_key
        item.document_template_version = template_version
        item.issued_at = issued_at
        item.issued_by = actor
        item.issued_by_name_snapshot = issuer_name
        item.status = GoodMoralStatus.ISSUED
        item.save(
            update_fields=[
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
                "transition": "REQUESTED -> ISSUED",
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "document_template_key": template_key,
                "document_template_version": template_version,
            },
        )
        return _queryset().get(pk=item.pk)


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

    return {
        "certificate": {
            "applicant_name": item.applicant_name_snapshot,
            "year_level": item.year_level_snapshot,
            "college": item.college_snapshot,
            "course": item.course_snapshot,
            "major": item.major_snapshot,
            "semester": item.semester_snapshot,
            "academic_year": item.academic_year.label if item.academic_year_id else "",
            "degree": item.degree_snapshot,
            "graduation_date": item.graduation_date,
            "issued_on": timezone.localtime(item.issued_at).date(),
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
