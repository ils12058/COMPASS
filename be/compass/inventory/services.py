"""Annual Student Individual Inventory workflows and prerequisite status resolver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    INVENTORY_CREATED,
    INVENTORY_REOPENED,
    INVENTORY_RESUBMITTED,
    INVENTORY_SUBMITTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.academic_years import get_current_academic_year
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import AcademicYear, College, Program
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    StudentSupportProfile,
)

from .models import (
    AnnualIncomeStatus,
    CivilStatusCategory,
    CourseChoiceReason,
    CurrentReligionCategory,
    FamilyMemberKind,
    GeographicLocationKind,
    ImmunizationType,
    InventoryEducationEntry,
    InventoryFamilyMember,
    InventoryGeographicLocation,
    InventoryOrganizationMembership,
    InventoryReopenEvent,
    InventorySibling,
    InventoryTransportationEntry,
    LivingArrangement,
    OccupationCategory,
    PostGraduationField,
    PWDStatus,
    StudentInventory,
    TransportationFrequencyCategory,
)

INVENTORY_FAMILY_KEY = "individual_inventory"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = 160
MAX_REOPEN_REASON_LENGTH = 1000


class InventoryStatus(StrEnum):
    MISSING = "MISSING"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class CombinedParentIncomeStatus(StrEnum):
    REPORTED = "REPORTED"
    NOT_SPECIFIED = "NOT_SPECIFIED"


class ParentIncomeBand(StrEnum):
    NONE = "NONE"
    POOR = "POOR"
    LOW_INCOME = "LOW_INCOME"
    LOWER_MIDDLE_INCOME = "LOWER_MIDDLE_INCOME"
    MIDDLE_MIDDLE_INCOME = "MIDDLE_MIDDLE_INCOME"
    UPPER_MIDDLE_INCOME = "UPPER_MIDDLE_INCOME"
    UPPER_INCOME = "UPPER_INCOME"
    RICH = "RICH"
    NOT_SPECIFIED = "NOT_SPECIFIED"


@dataclass(frozen=True, slots=True)
class CombinedParentIncome:
    status: CombinedParentIncomeStatus
    amount: Decimal | None


def combine_parent_annual_income(
    *,
    father_status: str,
    father_amount: Decimal | None,
    mother_status: str,
    mother_amount: Decimal | None,
) -> CombinedParentIncome:
    pairs = ((father_status, father_amount), (mother_status, mother_amount))
    if any(status == AnnualIncomeStatus.NOT_SPECIFIED for status, _ in pairs):
        return CombinedParentIncome(CombinedParentIncomeStatus.NOT_SPECIFIED, None)

    total = Decimal("0")
    for status, amount in pairs:
        if status == AnnualIncomeStatus.NONE:
            continue
        if status != AnnualIncomeStatus.REPORTED or amount is None or amount <= 0:
            raise InvalidInventoryInput(
                "Parent annual-income values are not internally consistent."
            )
        total += amount
    return CombinedParentIncome(CombinedParentIncomeStatus.REPORTED, total)


def classify_parent_annual_income(combined: CombinedParentIncome) -> ParentIncomeBand:
    if combined.status == CombinedParentIncomeStatus.NOT_SPECIFIED or combined.amount is None:
        return ParentIncomeBand.NOT_SPECIFIED
    amount = combined.amount
    if amount == 0:
        return ParentIncomeBand.NONE
    if amount < Decimal("131484"):
        return ParentIncomeBand.POOR
    if amount < Decimal("262968"):
        return ParentIncomeBand.LOW_INCOME
    if amount < Decimal("525936"):
        return ParentIncomeBand.LOWER_MIDDLE_INCOME
    if amount < Decimal("920388"):
        return ParentIncomeBand.MIDDLE_MIDDLE_INCOME
    if amount < Decimal("1577808"):
        return ParentIncomeBand.UPPER_MIDDLE_INCOME
    if amount <= Decimal("2626680"):
        return ParentIncomeBand.UPPER_INCOME
    return ParentIncomeBand.RICH


def derive_age_on(*, date_of_birth: date, on_date: date) -> int:
    return (
        on_date.year
        - date_of_birth.year
        - ((on_date.month, on_date.day) < (date_of_birth.month, date_of_birth.day))
    )


class InventoryError(RuntimeError):
    pass


class InventoryNotFound(InventoryError):
    pass


class InventoryConflict(InventoryError):
    pass


class InventoryCurrentStudentRequired(InventoryError):
    pass


class InvalidInventoryInput(InventoryError):
    pass


class CurrentAcademicYearNotConfigured(InventoryError):
    pass


class InventoryFormRevisionNotConfigured(InventoryError):
    pass


class InventoryNotPermitted(InventoryError):
    pass


class InventoryNotSubmitted(InventoryConflict):
    pass


@dataclass(frozen=True, slots=True)
class CurrentInventoryStatus:
    academic_year: AcademicYear
    status: InventoryStatus
    inventory: StudentInventory | None


@dataclass(frozen=True, slots=True)
class InventoryRosterRow:
    student: User
    academic_year: AcademicYear
    inventory: StudentInventory | None


@dataclass(frozen=True, slots=True)
class InventoryRosterPage:
    items: tuple[InventoryRosterRow, ...]
    page: int
    page_size: int
    has_next: bool


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
    "civil_status_category",
    "current_address",
    "permanent_address",
    "contact_number",
    "email_address",
    "languages_spoken_at_home",
    "languages_most_fluent",
    "religion_from_birth",
    "current_religion",
    "current_religion_category",
    "parent_statuses",
    "parent_status_category",
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
    "pwd_status",
    "illness_this_year",
    "previous_illness",
    "course_currently_enrolled",
    "year_level",
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
    "geographic_locations",
)

SUPPORT_FIELDS = (
    "four_ps_status",
    "indigenous_peoples_status",
    "mother_life_status",
    "father_life_status",
)


def _inventory_queryset():
    return StudentInventory.objects.select_related(
        "student",
        "student__role",
        "academic_year",
        "program",
        "program__college",
        "program__college__campus",
        "form_revision",
        "form_revision__family",
        "support_profile",
    ).prefetch_related(
        "family_members",
        "siblings",
        "education_entries",
        "organization_memberships",
        "transportation_entries",
        "geographic_locations",
        "reopen_events",
    )


def _validate_counselor(actor: User, capability: str) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability(capability)
    ):
        raise InventoryNotPermitted("Active Counselor Inventory authority is required.")


def _counselor_college_ids(actor: User) -> tuple[UUID, ...] | None:
    scope = resolve_organizational_access_scope(actor)
    return None if scope.institution_wide else scope.college_ids


def _scoped_students(actor: User):
    college_ids = _counselor_college_ids(actor)
    queryset = User.objects.filter(
        is_active=True,
        role__code="STUDENT",
        organization_student_affiliation__college__is_active=True,
        organization_student_affiliation__college__campus__is_active=True,
    ).select_related("role", "organization_student_affiliation__college__campus")
    if college_ids is None:
        return queryset
    if not college_ids:
        return queryset.none()
    return queryset.filter(organization_student_affiliation__college_id__in=college_ids)


def _student_in_scope(actor: User, student_id: UUID) -> bool:
    return _scoped_students(actor).filter(pk=student_id).exists()


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidInventoryInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidInventoryInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidInventoryInput("search must be text.")
    cleaned = search.strip()
    if len(cleaned) > MAX_SEARCH_LENGTH:
        raise InvalidInventoryInput(f"search must be at most {MAX_SEARCH_LENGTH} characters.")
    return cleaned


def _identity_search(queryset, term: str, *, prefix: str = ""):
    if not term:
        return queryset
    return queryset.filter(
        Q(**{f"{prefix}institutional_id__icontains": term})
        | Q(**{f"{prefix}first_name__icontains": term})
        | Q(**{f"{prefix}middle_name__icontains": term})
        | Q(**{f"{prefix}last_name__icontains": term})
    )


def _resolve_roster_year(academic_year_id: UUID | None) -> AcademicYear:
    if academic_year_id is None:
        return _current_year()
    year = AcademicYear.objects.filter(pk=academic_year_id).first()
    if year is None:
        raise InvalidInventoryInput("The selected Academic Year was not found.")
    return year


def _validate_roster_filters(
    *,
    actor: User,
    college_id: UUID | None,
    program_id: UUID | None,
    year_level: int | None,
) -> Program | None:
    college_ids = _counselor_college_ids(actor)
    if year_level is not None and not 1 <= year_level <= 10:
        raise InvalidInventoryInput("year_level must be between 1 and 10.")
    if college_id is not None:
        college = College.objects.select_related("campus").filter(pk=college_id).first()
        if college is None:
            raise InvalidInventoryInput("The selected College was not found.")
        if college_ids is not None and college.pk not in set(college_ids):
            raise InventoryNotPermitted(
                "The selected College is outside Counselor Inventory scope."
            )
    program = None
    if program_id is not None:
        program = Program.objects.select_related("college__campus").filter(pk=program_id).first()
        if program is None:
            raise InvalidInventoryInput("The selected Program was not found.")
        if college_ids is not None and program.college_id not in set(college_ids):
            raise InventoryNotPermitted(
                "The selected Program is outside Counselor Inventory scope."
            )
        if college_id is not None and program.college_id != college_id:
            raise InvalidInventoryInput(
                "The selected Program does not belong to the selected College."
            )
    return program


def _correction_pending(item: StudentInventory | None) -> bool:
    return bool(
        item is not None
        and item.submitted_at is None
        and item.first_submitted_at is not None
        and item.reopen_events.exists()
    )


def _require_current_student(student: User) -> None:
    if not is_current_student(student):
        raise InventoryCurrentStudentRequired(
            "Current Student lifecycle is required to initiate or change an Inventory."
        )


def _current_year() -> AcademicYear:
    current = get_current_academic_year()
    if current is None:
        raise CurrentAcademicYearNotConfigured("No current Academic Year is configured.")
    return current


def _require_active_program(program_id: UUID) -> Program:
    program = (
        Program.objects.select_for_update()
        .select_related("college__campus")
        .filter(pk=program_id)
        .first()
    )
    if program is None:
        raise InvalidInventoryInput("The selected Program was not found.")
    if (
        not program.is_active
        or not program.college.is_active
        or not program.college.campus.is_active
    ):
        raise InventoryConflict("The selected Program, College, and Campus must all be active.")
    return program


def _choice_label(choice_class, value: str) -> str:
    return choice_class(value).label


def _normalize_snapshot_categories(values: dict[str, object]) -> dict[str, object]:
    normalized = dict(values)

    civil = normalized.get("civil_status_category")
    if civil is not None:
        civil = str(civil)
        normalized["civil_status_category"] = civil
        if civil == CivilStatusCategory.OTHER:
            if not str(normalized.get("civil_status", "")).strip():
                raise InvalidInventoryInput(
                    "civil_status detail is required when category is OTHER."
                )
        elif civil == CivilStatusCategory.NOT_SPECIFIED:
            normalized["civil_status"] = ""
        else:
            normalized["civil_status"] = _choice_label(CivilStatusCategory, civil)

    religion = normalized.get("current_religion_category")
    if religion is not None:
        religion = str(religion)
        normalized["current_religion_category"] = religion
        if religion == CurrentReligionCategory.OTHER:
            if not str(normalized.get("current_religion", "")).strip():
                raise InvalidInventoryInput(
                    "current_religion detail is required when category is OTHER."
                )
        elif religion == CurrentReligionCategory.NOT_SPECIFIED:
            normalized["current_religion"] = ""
        else:
            normalized["current_religion"] = _choice_label(CurrentReligionCategory, religion)

    pwd_status = normalized.get("pwd_status")
    if pwd_status is not None:
        pwd_status = str(pwd_status)
        normalized["pwd_status"] = pwd_status
        detail = str(normalized.get("physical_disadvantage", "")).strip()
        if pwd_status == PWDStatus.PWD and not detail:
            raise InvalidInventoryInput(
                "physical_disadvantage detail is required when pwd_status is PWD."
            )
        if pwd_status in {PWDStatus.NON_PWD, PWDStatus.NOT_SPECIFIED}:
            normalized["physical_disadvantage"] = ""

    parent_status = normalized.get("parent_status_category")
    if parent_status is not None:
        normalized["parent_status_category"] = str(parent_status)

    return normalized


def _normalize_family_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        raise InvalidInventoryInput("family_members must be a list.")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in rows:
        row = dict(raw)
        kind = str(row.get("kind", ""))
        if kind in seen:
            raise InvalidInventoryInput("Only one family-member row per kind is allowed.")
        seen.add(kind)
        status = row.get("annual_income_status")
        if status is not None:
            status = str(status)
            if status not in AnnualIncomeStatus.values:
                raise InvalidInventoryInput("Unsupported annual_income_status.")
            row["annual_income_status"] = status
            amount = row.get("annual_income_previous_year")
            if status == AnnualIncomeStatus.REPORTED:
                if amount is None or Decimal(amount) <= 0:
                    raise InvalidInventoryInput(
                        "REPORTED parent annual income requires a positive amount."
                    )
            elif status == AnnualIncomeStatus.NONE:
                row["annual_income_previous_year"] = Decimal("0")
            elif status == AnnualIncomeStatus.NOT_SPECIFIED:
                row["annual_income_previous_year"] = None

        occupation_category = row.get("occupation_category")
        if occupation_category is not None:
            occupation_category = str(occupation_category)
            if occupation_category not in OccupationCategory.values:
                raise InvalidInventoryInput("Unsupported occupation_category.")
            row["occupation_category"] = occupation_category
            if (
                occupation_category == OccupationCategory.OTHER
                and not str(row.get("occupation", "")).strip()
            ):
                raise InvalidInventoryInput(
                    "occupation detail is required when occupation_category is OTHER."
                )
            if occupation_category in {
                OccupationCategory.NONE,
                OccupationCategory.NOT_SPECIFIED,
            }:
                row["occupation"] = ""

        normalized.append(row)
    return normalized


def _normalize_support_profile(values: object) -> dict[str, object]:
    if not isinstance(values, dict):
        raise InvalidInventoryInput("support_profile must be an object.")
    unknown = set(values) - set(SUPPORT_FIELDS)
    if unknown:
        raise InvalidInventoryInput("The support_profile contains unsupported fields.")

    normalized = dict(values)
    choices = {
        "four_ps_status": FourPsStatus,
        "indigenous_peoples_status": IndigenousPeoplesStatus,
        "mother_life_status": ParentLifeStatus,
        "father_life_status": ParentLifeStatus,
    }
    for field, choice_class in choices.items():
        value = normalized.get(field)
        if value is None:
            continue
        value = str(value)
        if value not in choice_class.values:
            raise InvalidInventoryInput(f"Unsupported support_profile {field}.")
        normalized[field] = value
    return normalized


def _lock_or_create_support_profile(item: StudentInventory) -> StudentSupportProfile:
    profile = StudentSupportProfile.objects.select_for_update().filter(inventory_id=item.pk).first()
    if profile is None:
        profile = StudentSupportProfile.objects.create(inventory=item)
    return profile


def _apply_support_profile(
    profile: StudentSupportProfile,
    values: dict[str, object],
) -> None:
    for field in SUPPORT_FIELDS:
        if field in values:
            setattr(profile, field, values[field])
    try:
        profile.full_clean(exclude=("inventory",))
    except ValidationError as exc:
        raise InvalidInventoryInput("The support_profile contains invalid typed values.") from exc
    profile.save(update_fields=[*SUPPORT_FIELDS, "updated_at"])


def _pair(code: str, name: str, label: str, *, required: bool) -> tuple[str, str]:
    code = code.strip()
    name = name.strip()
    if bool(code) != bool(name):
        raise InvalidInventoryInput(f"{label} PSGC code and name must be supplied together.")
    if required and not code:
        raise InvalidInventoryInput(f"{label} PSGC code and name are required.")
    if len(code) > 32 or len(name) > 160:
        raise InvalidInventoryInput(f"{label} PSGC code or display name is too long.")
    return code, name


def _normalize_geographic_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        raise InvalidInventoryInput("geographic_locations must be a list.")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in rows:
        row = dict(raw)
        kind = str(row.get("kind", ""))
        if kind not in GeographicLocationKind.values or kind in seen:
            raise InvalidInventoryInput("Geographic location kind must be unique and supported.")
        seen.add(kind)
        not_specified = bool(row.get("not_specified", False))
        row["kind"] = kind
        row["not_specified"] = not_specified
        field_pairs = (
            ("region_psgc_code", "region_name_snapshot", "Region"),
            ("province_psgc_code", "province_name_snapshot", "Province"),
            (
                "city_municipality_psgc_code",
                "city_municipality_name_snapshot",
                "City/Municipality",
            ),
            ("barangay_psgc_code", "barangay_name_snapshot", "Barangay"),
        )
        if not_specified:
            for code_field, name_field, _ in field_pairs:
                if str(row.get(code_field, "")).strip() or str(row.get(name_field, "")).strip():
                    raise InvalidInventoryInput(
                        "A not-specified geographic location cannot contain PSGC values."
                    )
                row[code_field] = ""
                row[name_field] = ""
        else:
            for code_field, name_field, label in field_pairs:
                code, name = _pair(
                    str(row.get(code_field, "")),
                    str(row.get(name_field, "")),
                    label,
                    required=label in {"Region", "City/Municipality"},
                )
                row[code_field] = code
                row[name_field] = name
        normalized.append(row)
    return normalized


def _normalize_transportation_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        raise InvalidInventoryInput("transportation_entries must be a list.")
    normalized: list[dict[str, object]] = []
    for raw in rows:
        row = dict(raw)
        category = row.get("frequency_category")
        if category is not None:
            category = str(category)
            if category not in TransportationFrequencyCategory.values:
                raise InvalidInventoryInput("Unsupported transportation frequency_category.")
            row["frequency_category"] = category
            detail = str(row.get("frequency", "")).strip()
            if category == TransportationFrequencyCategory.OTHER:
                if not detail:
                    raise InvalidInventoryInput(
                        "frequency detail is required when frequency_category is OTHER."
                    )
                row["frequency"] = detail
            elif category == TransportationFrequencyCategory.NOT_SPECIFIED:
                row["frequency"] = ""
            else:
                row["frequency"] = _choice_label(TransportationFrequencyCategory, category)
        fare = row.get("fare")
        if fare is not None and Decimal(fare) < 0:
            raise InvalidInventoryInput("Transportation fare must be non-negative.")
        normalized.append(row)
    return normalized


def _active_inventory_revision():
    try:
        return require_active_supported_form_revision(INVENTORY_FAMILY_KEY)
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


def require_current_submitted_inventory(student: User) -> StudentInventory:
    """Resolve the current annual Inventory and require its submitted state."""

    status = get_current_inventory_status(student)
    if status.status != InventoryStatus.SUBMITTED or status.inventory is None:
        raise InventoryConflict(
            "A submitted Individual Inventory for the current Academic Year is required."
        )
    return status.inventory


def get_current_inventory(student: User) -> StudentInventory:
    status = get_current_inventory_status(student)
    if status.inventory is None:
        raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
    return status.inventory


def ensure_current_inventory(*, student: User, context: AuditContext) -> StudentInventory:
    _require_current_student(student)
    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise InventoryNotFound("The Student account was not found.")
        _require_current_student(locked_student)
        current = _current_year()
        existing = StudentInventory.objects.filter(
            student_id=locked_student.pk,
            academic_year_id=current.pk,
        ).first()
        if existing is not None:
            StudentSupportProfile.objects.get_or_create(inventory=existing)
            return _inventory_queryset().get(pk=existing.pk)
        revision = _active_inventory_revision()
        try:
            item = StudentInventory.objects.create(
                student=locked_student,
                academic_year=current,
                form_revision=revision,
                student_number=locked_student.institutional_id or "",
            )
            StudentSupportProfile.objects.create(inventory=item)
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
            StudentSupportProfile.objects.get_or_create(inventory=item)
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


def _validate_submission(
    item: StudentInventory,
    profile: StudentSupportProfile,
) -> None:
    _validate_draft_consistency(item)
    required_scalars = (
        ("sex", item.sex),
        ("date_of_birth", item.date_of_birth),
        ("civil_status_category", item.civil_status_category),
        ("current_religion_category", item.current_religion_category),
        ("pwd_status", item.pwd_status),
        ("parent_status_category", item.parent_status_category),
        ("living_arrangement", item.living_arrangement),
    )
    missing = [name for name, value in required_scalars if value in {None, ""}]
    if missing:
        raise InvalidInventoryInput(
            "Inventory submission requires normalized fields: " + ", ".join(missing) + "."
        )

    normalized_root = _normalize_snapshot_categories(
        {
            "civil_status_category": item.civil_status_category,
            "civil_status": item.civil_status,
            "current_religion_category": item.current_religion_category,
            "current_religion": item.current_religion,
            "pwd_status": item.pwd_status,
            "physical_disadvantage": item.physical_disadvantage,
            "parent_status_category": item.parent_status_category,
        }
    )
    for field in (
        "civil_status",
        "current_religion",
        "physical_disadvantage",
    ):
        setattr(item, field, normalized_root[field])

    required_support = (
        ("four_ps_status", profile.four_ps_status),
        ("indigenous_peoples_status", profile.indigenous_peoples_status),
        ("mother_life_status", profile.mother_life_status),
        ("father_life_status", profile.father_life_status),
    )
    missing_support = [name for name, value in required_support if value in {None, ""}]
    if missing_support:
        raise InvalidInventoryInput(
            "Inventory submission requires Student Support fields: "
            + ", ".join(missing_support)
            + "."
        )

    current_location = next(
        (
            row
            for row in item.geographic_locations.all()
            if row.kind == GeographicLocationKind.CURRENT
        ),
        None,
    )
    if current_location is None:
        raise InvalidInventoryInput(
            "A deliberate CURRENT structured geographic location response is required."
        )
    _normalize_geographic_rows(
        [
            {
                "kind": current_location.kind,
                "not_specified": current_location.not_specified,
                "region_psgc_code": current_location.region_psgc_code,
                "region_name_snapshot": current_location.region_name_snapshot,
                "province_psgc_code": current_location.province_psgc_code,
                "province_name_snapshot": current_location.province_name_snapshot,
                "city_municipality_psgc_code": current_location.city_municipality_psgc_code,
                "city_municipality_name_snapshot": current_location.city_municipality_name_snapshot,
                "barangay_psgc_code": current_location.barangay_psgc_code,
                "barangay_name_snapshot": current_location.barangay_name_snapshot,
            }
        ]
    )

    parents = {row.kind: row for row in item.family_members.all()}
    for kind in (FamilyMemberKind.FATHER, FamilyMemberKind.MOTHER):
        parent = parents.get(kind)
        if parent is None:
            raise InvalidInventoryInput(f"{kind.label} family-member row is required.")
        if parent.occupation_category in {None, ""}:
            raise InvalidInventoryInput(f"{kind.label} occupation_category is required.")
        if parent.annual_income_status in {None, ""}:
            raise InvalidInventoryInput(f"{kind.label} annual_income_status is required.")
        _normalize_family_rows(
            [
                {
                    "kind": parent.kind,
                    "occupation_category": parent.occupation_category,
                    "occupation": parent.occupation,
                    "annual_income_status": parent.annual_income_status,
                    "annual_income_previous_year": parent.annual_income_previous_year,
                }
            ]
        )
    for row in item.transportation_entries.all():
        if row.frequency_category in {None, ""}:
            raise InvalidInventoryInput(
                "Each transportation entry requires a frequency_category before submission."
            )
        _normalize_transportation_rows(
            [
                {
                    "mode": row.mode,
                    "frequency": row.frequency,
                    "frequency_category": row.frequency_category,
                    "fare": row.fare,
                }
            ]
        )

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


def _normalize_sibling_rows(rows: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows if isinstance(rows, list) else []:
        item = dict(row)
        if item.get("sex") is None:
            item["sex"] = ""
        normalized.append(item)
    return normalized


def _replace_children(item: StudentInventory, values: dict[str, object]) -> None:
    family_rows = _normalize_family_rows(values.get("family_members", []))
    sibling_rows = _normalize_sibling_rows(values.get("siblings", []))
    education_rows = values.get("education_entries", [])
    organization_rows = values.get("organization_memberships", [])
    transportation_rows = _normalize_transportation_rows(values.get("transportation_entries", []))
    geographic_rows = _normalize_geographic_rows(values.get("geographic_locations", []))

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
    item.geographic_locations.all().delete()
    InventoryGeographicLocation.objects.bulk_create(
        [InventoryGeographicLocation(inventory=item, **row) for row in geographic_rows]
    )


def replace_current_inventory(
    *,
    student: User,
    values: dict[str, object],
) -> StudentInventory:
    _require_current_student(student)
    unsupported = (
        set(values)
        - set(SCALAR_FIELDS)
        - set(CHILD_COLLECTIONS)
        - {"program_id", "support_profile"}
    )
    if unsupported:
        raise InvalidInventoryInput("The Inventory update contains unsupported fields.")
    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise InventoryNotFound("The Student account was not found.")
        _require_current_student(locked_student)
        current = _current_year()
        item = (
            StudentInventory.objects.select_for_update()
            .filter(student_id=locked_student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
        if item.submitted_at is not None:
            raise InventoryConflict("A submitted Individual Inventory is locked.")
        normalized_values = _normalize_snapshot_categories(values)
        support_values = None
        if "support_profile" in normalized_values:
            support_values = _normalize_support_profile(normalized_values.pop("support_profile"))
        profile = _lock_or_create_support_profile(item)
        if "program_id" in normalized_values:
            program_id = normalized_values.pop("program_id")
            item.program = None if program_id is None else _require_active_program(program_id)
        if item.program_id is not None:
            item.program = _require_active_program(item.program_id)
            normalized_values["course_currently_enrolled"] = item.program.name
        canonical_institutional_id = locked_student.institutional_id
        if canonical_institutional_id is not None:
            normalized_values["student_number"] = canonical_institutional_id
        _apply_scalar_values(item, normalized_values)
        item.save(update_fields=["program", *SCALAR_FIELDS, "updated_at"])
        _replace_children(item, normalized_values)
        if support_values is not None:
            _apply_support_profile(profile, support_values)
        return _inventory_queryset().get(pk=item.pk)


def submit_current_inventory(
    *,
    student: User,
    context: AuditContext,
) -> StudentInventory:
    _require_current_student(student)
    with transaction.atomic():
        locked_student = (
            User.objects.select_for_update().select_related("role").filter(pk=student.pk).first()
        )
        if locked_student is None:
            raise InventoryNotFound("The Student account was not found.")
        _require_current_student(locked_student)
        current = _current_year()
        item = (
            StudentInventory.objects.select_for_update()
            .filter(student_id=locked_student.pk, academic_year_id=current.pk)
            .first()
        )
        if item is None:
            raise InventoryNotFound("The current academic-year Individual Inventory was not found.")
        if item.submitted_at is not None:
            return _inventory_queryset().get(pk=item.pk)
        if item.program_id is None:
            raise InventoryConflict("Program is required before Inventory submission.")
        if item.year_level is None:
            raise InventoryConflict("Year Level is required before Inventory submission.")
        item.program = _require_active_program(item.program_id)
        item.course_currently_enrolled = item.program.name
        profile = _lock_or_create_support_profile(item)
        if locked_student.institutional_id is not None:
            item.student_number = locked_student.institutional_id
        _validate_submission(item, profile)
        submitted_at = timezone.now()
        is_resubmission = item.first_submitted_at is not None
        if item.first_submitted_at is None:
            item.first_submitted_at = submitted_at
        item.last_submitted_at = submitted_at
        item.submitted_at = submitted_at
        item.save(
            update_fields=[
                "student_number",
                "course_currently_enrolled",
                "civil_status",
                "current_religion",
                "physical_disadvantage",
                "first_submitted_at",
                "last_submitted_at",
                "submitted_at",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=INVENTORY_RESUBMITTED if is_resubmission else INVENTORY_SUBMITTED,
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


def list_inventory_students(
    *,
    actor: User,
    academic_year_id: UUID | None = None,
    status: str | InventoryStatus | None = None,
    college_id: UUID | None = None,
    program_id: UUID | None = None,
    year_level: int | None = None,
    search: str | None = None,
    student_id: UUID | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> InventoryRosterPage:
    _validate_counselor(actor, "inventory.view")
    page, page_size = _pagination(page, page_size)
    year = _resolve_roster_year(academic_year_id)
    term = _clean_search(search)
    _validate_roster_filters(
        actor=actor,
        college_id=college_id,
        program_id=program_id,
        year_level=year_level,
    )

    normalized_status = None
    if status is not None:
        normalized_status = status.value if isinstance(status, InventoryStatus) else str(status)
        if normalized_status not in {item.value for item in InventoryStatus}:
            raise InvalidInventoryInput("status must be MISSING, DRAFT, or SUBMITTED.")

    if not year.is_current and normalized_status == InventoryStatus.MISSING:
        raise InventoryConflict(
            "Historical MISSING coverage cannot be reconstructed from authoritative COMPASS data."
        )

    if year.is_current:
        queryset = _scoped_students(actor).filter(student_lifecycle_status="CURRENT")
        if student_id is not None:
            queryset = queryset.filter(pk=student_id)
        if college_id is not None:
            queryset = queryset.filter(organization_student_affiliation__college_id=college_id)
        queryset = _identity_search(queryset, term)

        annual = "individual_inventories"
        if normalized_status == InventoryStatus.MISSING:
            queryset = queryset.exclude(**{f"{annual}__academic_year_id": year.pk})
        elif normalized_status == InventoryStatus.DRAFT:
            queryset = queryset.filter(
                **{
                    f"{annual}__academic_year_id": year.pk,
                    f"{annual}__submitted_at__isnull": True,
                }
            )
        elif normalized_status == InventoryStatus.SUBMITTED:
            queryset = queryset.filter(
                **{
                    f"{annual}__academic_year_id": year.pk,
                    f"{annual}__submitted_at__isnull": False,
                }
            )

        if program_id is not None:
            queryset = queryset.filter(
                individual_inventories__academic_year_id=year.pk,
                individual_inventories__program_id=program_id,
            )
        if year_level is not None:
            queryset = queryset.filter(
                individual_inventories__academic_year_id=year.pk,
                individual_inventories__year_level=year_level,
            )

        queryset = queryset.order_by("last_name", "first_name", "id").distinct()
        offset = (page - 1) * page_size
        students = list(queryset[offset : offset + page_size + 1])
        selected = students[:page_size]
        inventory_by_student = {
            item.student_id: item
            for item in _inventory_queryset().filter(
                academic_year_id=year.pk,
                student_id__in=[student.pk for student in selected],
            )
        }
        rows = tuple(
            InventoryRosterRow(student, year, inventory_by_student.get(student.pk))
            for student in selected
        )
        return InventoryRosterPage(rows, page, page_size, len(students) > page_size)

    scoped_student_ids = _scoped_students(actor).values("pk")
    queryset = _inventory_queryset().filter(
        academic_year_id=year.pk,
        student_id__in=scoped_student_ids,
    )
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    if college_id is not None:
        queryset = queryset.filter(student__organization_student_affiliation__college_id=college_id)
    if program_id is not None:
        queryset = queryset.filter(program_id=program_id)
    if year_level is not None:
        queryset = queryset.filter(year_level=year_level)
    if normalized_status == InventoryStatus.DRAFT:
        queryset = queryset.filter(submitted_at__isnull=True)
    elif normalized_status == InventoryStatus.SUBMITTED:
        queryset = queryset.filter(submitted_at__isnull=False)
    queryset = _identity_search(queryset, term, prefix="student__")
    queryset = queryset.order_by("student__last_name", "student__first_name", "student_id", "id")
    offset = (page - 1) * page_size
    items = list(queryset[offset : offset + page_size + 1])
    rows = tuple(InventoryRosterRow(item.student, year, item) for item in items[:page_size])
    return InventoryRosterPage(rows, page, page_size, len(items) > page_size)


def get_inventory_for_counselor(*, actor: User, inventory_id: UUID) -> StudentInventory:
    _validate_counselor(actor, "inventory.view")
    item = _inventory_queryset().filter(pk=inventory_id).first()
    if item is None or not _student_in_scope(actor, item.student_id):
        raise InventoryNotFound("The requested Individual Inventory was not found.")
    if item.submitted_at is None:
        raise InventoryNotSubmitted(
            "Only a currently submitted Individual Inventory is available for Counselor review."
        )
    return item


def list_student_inventory_history(
    *,
    actor: User,
    student_id: UUID,
) -> tuple[StudentInventory, ...]:
    _validate_counselor(actor, "inventory.view")
    if not _student_in_scope(actor, student_id):
        raise InventoryNotFound("The Student Inventory history was not found.")
    return tuple(
        _inventory_queryset()
        .filter(student_id=student_id)
        .order_by("-academic_year__label", "-created_at", "id")
    )


def reopen_inventory_for_correction(
    *,
    actor: User,
    inventory_id: UUID,
    reason: str,
    context: AuditContext,
    now: datetime | None = None,
) -> StudentInventory:
    _validate_counselor(actor, "inventory.reopen")
    if not isinstance(reason, str):
        raise InvalidInventoryInput("reason must be text.")
    cleaned_reason = reason.strip()
    if not cleaned_reason:
        raise InvalidInventoryInput("reason is required to reopen an Individual Inventory.")
    if len(cleaned_reason) > MAX_REOPEN_REASON_LENGTH:
        raise InvalidInventoryInput(
            f"reason must be at most {MAX_REOPEN_REASON_LENGTH} characters."
        )
    reopened_at = now or timezone.now()
    if timezone.is_naive(reopened_at):
        raise InvalidInventoryInput("The reopen time must be timezone-aware.")

    with transaction.atomic():
        item = (
            StudentInventory.objects.select_for_update()
            .select_related("student__role", "academic_year", "form_revision")
            .filter(pk=inventory_id)
            .first()
        )
        if item is None or not _student_in_scope(actor, item.student_id):
            raise InventoryNotFound("The requested Individual Inventory was not found.")

        current = _current_year()
        if item.academic_year_id != current.pk:
            raise InventoryConflict(
                "Only the current Academic Year submitted Individual Inventory may be reopened."
            )
        if item.submitted_at is None:
            raise InventoryConflict("Only a submitted Individual Inventory may be reopened.")
        if not is_current_student(item.student):
            raise InventoryCurrentStudentRequired(
                "Current Student lifecycle is required before reopening for Student correction."
            )

        event = InventoryReopenEvent.objects.create(
            inventory=item,
            reopened_by=actor,
            reopened_at=reopened_at,
            reason=cleaned_reason,
        )
        item.submitted_at = None
        item.save(update_fields=["submitted_at", "updated_at"])
        record_event(
            context=context,
            action=INVENTORY_REOPENED,
            outcome=AuditOutcome.SUCCESS,
            target_type="inventory.studentinventory",
            target_id=item.pk,
            metadata={
                "academic_year": item.academic_year.label,
                "form_code": item.form_revision.official_code,
                "form_revision": item.form_revision.official_revision,
                "transition": "SUBMITTED -> DRAFT",
                "reopen_event_id": str(event.pk),
            },
        )
        create_notification_for_event(
            recipient=item.student,
            event=NotificationEvent.INVENTORY_REOPENED,
            source_type="inventory_reopen_event",
            source_id=event.pk,
            target_type="INVENTORY",
            target_id=item.pk,
        )
        return _inventory_queryset().get(pk=item.pk)
