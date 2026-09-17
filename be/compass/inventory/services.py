"""Annual Student Individual Inventory workflows and prerequisite status resolver."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import INVENTORY_CREATED, INVENTORY_SUBMITTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_form_revision,
)
from compass.organization.academic_years import get_current_academic_year
from compass.organization.models import AcademicYear

from .models import (
    CourseChoiceReason,
    ImmunizationType,
    InventoryEducationEntry,
    InventoryFamilyMember,
    InventoryOrganizationMembership,
    InventorySibling,
    InventoryTransportationEntry,
    LivingArrangement,
    PostGraduationField,
    StudentInventory,
)

INVENTORY_FAMILY_KEY = "individual_inventory"


class InventoryStatus(StrEnum):
    MISSING = "MISSING"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class InventoryError(RuntimeError):
    pass


class InventoryNotFound(InventoryError):
    pass


class InventoryConflict(InventoryError):
    pass


class InvalidInventoryInput(InventoryError):
    pass


class CurrentAcademicYearNotConfigured(InventoryError):
    pass


class InventoryFormRevisionNotConfigured(InventoryError):
    pass


@dataclass(frozen=True, slots=True)
class CurrentInventoryStatus:
    academic_year: AcademicYear
    status: InventoryStatus
    inventory: StudentInventory | None


SCALAR_FIELDS = (
    "full_name_snapshot",
    "nickname",
    "student_number",
    "date_of_birth",
    "place_of_birth",
    "nationality",
    "sex",
    "birth_order_among_siblings",
    "civil_status",
    "current_address",
    "permanent_address",
    "contact_number",
    "email_address",
    "languages_spoken_at_home",
    "languages_most_fluent",
    "religion_from_birth",
    "current_religion",
    "parent_statuses",
    "guardian_name",
    "guardian_relationship",
    "guardian_address",
    "guardian_contact_number",
    "emergency_contact_name",
    "emergency_contact_number",
    "friends_in_school",
    "friends_outside_school",
    "special_interest",
    "special_skills_talents",
    "hobbies_recreation",
    "ambition_goal",
    "characteristics",
    "living_arrangement",
    "boarding_exclusive",
    "boarding_landlord_name",
    "boarding_address",
    "present_place_people_count",
    "room_sharing_people_count",
    "accidents_experienced",
    "accidents_effect",
    "operations_experienced",
    "operations_effect",
    "immunizations",
    "immunization_other",
    "height",
    "weight",
    "physical_disadvantage",
    "illness_this_year",
    "previous_illness",
    "course_currently_enrolled",
    "major",
    "schedule_satisfied",
    "schedule_satisfaction_reason",
    "course_first_choice",
    "course_choice_reasons",
    "course_choice_other",
    "lowest_subjects_grades",
    "highest_subjects_grades",
    "inclination_performing_arts",
    "inclination_sports",
    "inclination_leadership",
    "interests",
    "other_skills_hobbies",
    "desired_extracurricular_activities",
    "reading_preferences",
    "handedness",
    "daily_hours_class",
    "daily_hours_library",
    "daily_hours_studying",
    "daily_hours_rest",
    "daily_hours_recreation",
    "daily_hours_other",
    "ideal_monthly_allowance",
    "intended_work_field",
    "intended_work_other",
    "prior_counseling_experience",
    "prior_counselor_name",
    "prior_counseling_when",
    "prior_counseling_where",
    "current_concerns",
    "current_fears",
)

CHILD_COLLECTIONS = (
    "family_members",
    "siblings",
    "education_entries",
    "organization_memberships",
    "transportation_entries",
)


def _inventory_queryset():
    return StudentInventory.objects.select_related(
        "student",
        "student__role",
        "academic_year",
        "form_revision",
        "form_revision__family",
    ).prefetch_related(
        "family_members",
        "siblings",
        "education_entries",
        "organization_memberships",
        "transportation_entries",
    )


def _require_active_student(student: User) -> None:
    if not getattr(student, "pk", None) or not student.is_active or student.role.code != "STUDENT":
        raise InventoryConflict("Only an active Student may initiate or change an Inventory.")


def _current_year() -> AcademicYear:
    current = get_current_academic_year()
    if current is None:
        raise CurrentAcademicYearNotConfigured("No current Academic Year is configured.")
    return current


def _active_inventory_revision():
    try:
        return require_active_form_revision(INVENTORY_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        raise InventoryFormRevisionNotConfigured(
            "No active supported Individual Inventory Form Revision is configured."
        ) from exc


def get_current_inventory_status(student: User) -> CurrentInventoryStatus:
    current = _current_year()
    item = _inventory_queryset().filter(student_id=student.pk, academic_year_id=current.pk).first()
    if item is None:
        return CurrentInventoryStatus(current, InventoryStatus.MISSING, None)
    status = InventoryStatus.SUBMITTED if item.submitted_at is not None else InventoryStatus.DRAFT
    return CurrentInventoryStatus(current, status, item)


def has_current_submitted_inventory(student: User) -> bool:
    return get_current_inventory_status(student).status == InventoryStatus.SUBMITTED


def get_current_inventory(student: User) -> StudentInventory:
    status = get_current_inventory_status(student)
    if status.inventory is None:
        raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
    return status.inventory


def ensure_current_inventory(*, student: User, context: AuditContext) -> StudentInventory:
    _require_active_student(student)
    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise InventoryNotFound("The Student account was not found.")
        _require_active_student(locked_student)
        current = _current_year()
        existing = StudentInventory.objects.filter(
            student_id=locked_student.pk,
            academic_year_id=current.pk,
        ).first()
        if existing is not None:
            return _inventory_queryset().get(pk=existing.pk)
        revision = _active_inventory_revision()
        try:
            item = StudentInventory.objects.create(
                student=locked_student,
                academic_year=current,
                form_revision=revision,
            )
        except IntegrityError:
            item = StudentInventory.objects.filter(
                student_id=locked_student.pk,
                academic_year_id=current.pk,
            ).first()
            if item is None:
                raise InventoryConflict(
                    "The current Individual Inventory could not be created safely; "
                    "retry the request."
                ) from None
            return _inventory_queryset().get(pk=item.pk)
        record_event(
            context=context,
            action=INVENTORY_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="inventory.studentinventory",
            target_id=item.pk,
            metadata={
                "academic_year": current.label,
                "form_code": revision.official_code,
                "form_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            },
        )
        return _inventory_queryset().get(pk=item.pk)


def _validate_draft_consistency(item: StudentInventory) -> None:
    if item.prior_counseling_experience is False and any(
        value.strip()
        for value in (
            item.prior_counselor_name,
            item.prior_counseling_when,
            item.prior_counseling_where,
        )
    ):
        raise InvalidInventoryInput(
            "Prior Counselor details must be empty when prior_counseling_experience is false."
        )
    if item.living_arrangement != LivingArrangement.BOARDING_HOUSE and (
        item.boarding_exclusive is not None
        or item.boarding_landlord_name.strip()
        or item.boarding_address.strip()
    ):
        raise InvalidInventoryInput(
            "Boarding-house details may only be supplied for BOARDING_HOUSE living arrangement."
        )


def _validate_submission(item: StudentInventory) -> None:
    _validate_draft_consistency(item)
    if ImmunizationType.OTHER in item.immunizations and not item.immunization_other.strip():
        raise InvalidInventoryInput(
            "immunization_other is required when OTHER immunization is selected."
        )
    if (
        CourseChoiceReason.OTHER in item.course_choice_reasons
        and not item.course_choice_other.strip()
    ):
        raise InvalidInventoryInput(
            "course_choice_other is required when OTHER course-choice reason is selected."
        )
    if (
        item.intended_work_field == PostGraduationField.OTHER
        and not item.intended_work_other.strip()
    ):
        raise InvalidInventoryInput(
            "intended_work_other is required when intended_work_field is OTHER."
        )


def _apply_scalar_values(item: StudentInventory, values: dict[str, object]) -> None:
    for field in SCALAR_FIELDS:
        if field in values:
            setattr(item, field, values[field])
    try:
        item.full_clean(exclude=("student", "academic_year", "form_revision"))
    except ValidationError as exc:
        raise InvalidInventoryInput("The Inventory contains invalid typed values.") from exc
    _validate_draft_consistency(item)


def _replace_children(item: StudentInventory, values: dict[str, object]) -> None:
    family_rows = values.get("family_members", [])
    sibling_rows = values.get("siblings", [])
    education_rows = values.get("education_entries", [])
    organization_rows = values.get("organization_memberships", [])
    transportation_rows = values.get("transportation_entries", [])

    item.family_members.all().delete()
    InventoryFamilyMember.objects.bulk_create(
        [InventoryFamilyMember(inventory=item, **row) for row in family_rows]
    )
    item.siblings.all().delete()
    InventorySibling.objects.bulk_create(
        [InventorySibling(inventory=item, **row) for row in sibling_rows]
    )
    item.education_entries.all().delete()
    InventoryEducationEntry.objects.bulk_create(
        [InventoryEducationEntry(inventory=item, **row) for row in education_rows]
    )
    item.organization_memberships.all().delete()
    InventoryOrganizationMembership.objects.bulk_create(
        [InventoryOrganizationMembership(inventory=item, **row) for row in organization_rows]
    )
    item.transportation_entries.all().delete()
    InventoryTransportationEntry.objects.bulk_create(
        [InventoryTransportationEntry(inventory=item, **row) for row in transportation_rows]
    )


def replace_current_inventory(
    *,
    student: User,
    values: dict[str, object],
) -> StudentInventory:
    _require_active_student(student)
    unsupported = set(values) - set(SCALAR_FIELDS) - set(CHILD_COLLECTIONS)
    if unsupported:
        raise InvalidInventoryInput("The Inventory update contains unsupported fields.")
    with transaction.atomic():
        current = _current_year()
        item = (
            StudentInventory.objects.select_for_update()
            .filter(student_id=student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
        if item.submitted_at is not None:
            raise InventoryConflict("A submitted Individual Inventory is locked.")
        _apply_scalar_values(item, values)
        item.save(update_fields=[*SCALAR_FIELDS, "updated_at"])
        _replace_children(item, values)
        return _inventory_queryset().get(pk=item.pk)


def submit_current_inventory(
    *,
    student: User,
    context: AuditContext,
) -> StudentInventory:
    _require_active_student(student)
    with transaction.atomic():
        current = _current_year()
        item = (
            StudentInventory.objects.select_for_update()
            .filter(student_id=student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
        if item.submitted_at is not None:
            return _inventory_queryset().get(pk=item.pk)
        _validate_submission(item)
        item.submitted_at = timezone.now()
        item.save(update_fields=["submitted_at", "updated_at"])
        record_event(
            context=context,
            action=INVENTORY_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="inventory.studentinventory",
            target_id=item.pk,
            metadata={
                "academic_year": current.label,
                "form_code": item.form_revision.official_code,
                "form_revision": item.form_revision.official_revision,
            },
        )
        return _inventory_queryset().get(pk=item.pk)


def list_my_inventory_history(student: User) -> tuple[StudentInventory, ...]:
    return tuple(
        _inventory_queryset()
        .filter(student_id=student.pk)
        .order_by("-academic_year__label", "-created_at")
    )


def get_my_inventory_history_item(*, student: User, inventory_id: UUID) -> StudentInventory:
    item = _inventory_queryset().filter(pk=inventory_id, student_id=student.pk).first()
    if item is None:
        raise InventoryNotFound("The requested Individual Inventory was not found.")
    return item
