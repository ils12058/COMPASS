"""Student-only API for annual Individual Inventory self-service."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from ninja import Router, Schema
from pydantic import ConfigDict, Field

from compass.audit.context import AuditContext
from compass.authentication.api import session_auth
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .models import (
    CourseChoiceReason,
    EducationLevel,
    FamilyMemberKind,
    Handedness,
    IdealAllowanceBand,
    ImmunizationType,
    InterestType,
    LivingArrangement,
    OrganizationScope,
    ParentStatus,
    PostGraduationField,
    Sex,
    TransportationMode,
)
from .services import (
    CurrentAcademicYearNotConfigured,
    InvalidInventoryInput,
    InventoryConflict,
    InventoryCurrentStudentRequired,
    InventoryError,
    InventoryFormRevisionNotConfigured,
    InventoryNotFound,
    InventoryStatus,
    ensure_current_inventory,
    get_current_inventory,
    get_current_inventory_status,
    get_my_inventory_history_item,
    list_my_inventory_history,
    replace_current_inventory,
    submit_current_inventory,
)

router = Router(tags=["inventory"])


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class SexValue(StrEnum):
    MALE = Sex.MALE
    FEMALE = Sex.FEMALE


class FamilyMemberKindValue(StrEnum):
    FATHER = FamilyMemberKind.FATHER
    MOTHER = FamilyMemberKind.MOTHER
    SPOUSE = FamilyMemberKind.SPOUSE


class ParentStatusValue(StrEnum):
    MARRIED_ANNULLED_LEGALLY_SEPARATED = ParentStatus.MARRIED_ANNULLED_LEGALLY_SEPARATED
    TEMPORARILY_SEPARATED = ParentStatus.TEMPORARILY_SEPARATED
    PERMANENTLY_SEPARATED = ParentStatus.PERMANENTLY_SEPARATED
    MOTHER_WITH_OTHER_PARTNER = ParentStatus.MOTHER_WITH_OTHER_PARTNER
    FATHER_WITH_OTHER_PARTNER = ParentStatus.FATHER_WITH_OTHER_PARTNER
    WIDOW_WIDOWER_LIVING_TOGETHER = ParentStatus.WIDOW_WIDOWER_LIVING_TOGETHER
    MOTHER_OFW = ParentStatus.MOTHER_OFW
    FATHER_OFW = ParentStatus.FATHER_OFW


class LivingArrangementValue(StrEnum):
    OWN_HOUSE = LivingArrangement.OWN_HOUSE
    BOARDING_HOUSE = LivingArrangement.BOARDING_HOUSE
    WITH_RELATIVES = LivingArrangement.WITH_RELATIVES


class ImmunizationValue(StrEnum):
    CHICKEN_POX = ImmunizationType.CHICKEN_POX
    BOOSTER = ImmunizationType.BOOSTER
    MEASLES_MMR = ImmunizationType.MEASLES_MMR
    HEPATITIS_B = ImmunizationType.HEPATITIS_B
    MUMPS = ImmunizationType.MUMPS
    INFLUENZA = ImmunizationType.INFLUENZA
    SMALL_POX = ImmunizationType.SMALL_POX
    OTHER = ImmunizationType.OTHER


class EducationLevelValue(StrEnum):
    PREPARATORY = EducationLevel.PREPARATORY
    ELEMENTARY = EducationLevel.ELEMENTARY
    JUNIOR_HIGH = EducationLevel.JUNIOR_HIGH
    SENIOR_HIGH = EducationLevel.SENIOR_HIGH
    TECHNICAL_VOCATIONAL = EducationLevel.TECHNICAL_VOCATIONAL
    COLLEGIATE = EducationLevel.COLLEGIATE


class CourseChoiceReasonValue(StrEnum):
    INTEREST_APTITUDE = CourseChoiceReason.INTEREST_APTITUDE
    MINIMAL_COST = CourseChoiceReason.MINIMAL_COST
    FRIENDS = CourseChoiceReason.FRIENDS
    PARENT_CHOICE = CourseChoiceReason.PARENT_CHOICE
    JOB_OPPORTUNITIES = CourseChoiceReason.JOB_OPPORTUNITIES
    OTHER = CourseChoiceReason.OTHER


class InterestValue(StrEnum):
    PAINTING = InterestType.PAINTING
    SINGING = InterestType.SINGING
    POEM_WRITING = InterestType.POEM_WRITING
    PLAYING_INSTRUMENTS = InterestType.PLAYING_INSTRUMENTS
    PLANTING = InterestType.PLANTING
    DECLAMATION_ORATION = InterestType.DECLAMATION_ORATION
    DANCING = InterestType.DANCING
    COMPOSING = InterestType.COMPOSING
    STAGE_ACT = InterestType.STAGE_ACT
    COOKING = InterestType.COOKING


class HandednessValue(StrEnum):
    RIGHT = Handedness.RIGHT
    LEFT = Handedness.LEFT


class OrganizationScopeValue(StrEnum):
    INSIDE_SCHOOL = OrganizationScope.INSIDE_SCHOOL
    OUTSIDE_SCHOOL = OrganizationScope.OUTSIDE_SCHOOL


class TransportationModeValue(StrEnum):
    TRICYCLE = TransportationMode.TRICYCLE
    BUS = TransportationMode.BUS
    JEEPNEY = TransportationMode.JEEPNEY
    VAN = TransportationMode.VAN
    BOAT = TransportationMode.BOAT


class IdealAllowanceBandValue(StrEnum):
    BELOW_100 = IdealAllowanceBand.BELOW_100
    FROM_100_TO_499 = IdealAllowanceBand.FROM_100_TO_499
    FROM_500_TO_1000 = IdealAllowanceBand.FROM_500_TO_1000
    ABOVE_1000 = IdealAllowanceBand.ABOVE_1000


class PostGraduationFieldValue(StrEnum):
    PROFESSIONAL = PostGraduationField.PROFESSIONAL
    AGRICULTURE = PostGraduationField.AGRICULTURE
    BUSINESS = PostGraduationField.BUSINESS
    TECHNICAL = PostGraduationField.TECHNICAL
    OVERSEAS_WORKER = PostGraduationField.OVERSEAS_WORKER
    RELIGIOUS = PostGraduationField.RELIGIOUS
    PUBLIC_SERVICE = PostGraduationField.PUBLIC_SERVICE
    OTHER = PostGraduationField.OTHER


class InventoryStatusValue(StrEnum):
    MISSING = InventoryStatus.MISSING
    DRAFT = InventoryStatus.DRAFT
    SUBMITTED = InventoryStatus.SUBMITTED


class FamilyMemberPayload(StrictSchema):
    kind: FamilyMemberKindValue
    name: str = ""
    date_of_birth: date | None = None
    place_of_birth: str = ""
    current_address: str = ""
    permanent_address: str = ""
    contact_number: str = ""
    email_address: str = ""
    educational_attainment: str = ""
    occupation: str = ""
    business_address: str = ""
    business_telephone: str = ""
    annual_income_previous_year: Decimal | None = Field(default=None, ge=0)
    languages_spoken: str = ""
    religion_raised_with: str = ""
    current_religion: str = ""


class SiblingPayload(StrictSchema):
    sort_order: int = Field(ge=0)
    name: str = ""
    sex: SexValue | None = None
    age: int | None = Field(default=None, ge=0)
    educational_attainment: str = ""
    occupation: str = ""
    is_self: bool = False


class EducationEntryPayload(StrictSchema):
    level: EducationLevelValue
    school_attended_address: str = ""
    inclusive_years: str = ""
    awards_received: str = ""


class OrganizationMembershipPayload(StrictSchema):
    scope: OrganizationScopeValue
    sort_order: int = Field(ge=0)
    organization_name: str = ""
    position_title: str = ""


class TransportationEntryPayload(StrictSchema):
    mode: TransportationModeValue
    frequency: str = ""
    fare: Decimal | None = Field(default=None, ge=0)


class InventoryPayload(StrictSchema):
    full_name: str = ""
    nickname: str = ""
    student_number: str = ""
    date_of_birth: date | None = None
    place_of_birth: str = ""
    nationality: str = ""
    sex: SexValue | None = None
    birth_order_among_siblings: str = ""
    civil_status: str = ""
    current_address: str = ""
    permanent_address: str = ""
    contact_number: str = ""
    email_address: str = ""
    languages_spoken_at_home: str = ""
    languages_most_fluent: str = ""
    religion_from_birth: str = ""
    current_religion: str = ""
    parent_statuses: list[ParentStatusValue] = Field(default_factory=list)
    family_members: list[FamilyMemberPayload] = Field(default_factory=list)
    guardian_name: str = ""
    guardian_relationship: str = ""
    guardian_address: str = ""
    guardian_contact_number: str = ""
    emergency_contact_name: str = ""
    emergency_contact_number: str = ""
    siblings: list[SiblingPayload] = Field(default_factory=list)
    friends_in_school: str = ""
    friends_outside_school: str = ""
    special_interest: str = ""
    special_skills_talents: str = ""
    hobbies_recreation: str = ""
    ambition_goal: str = ""
    characteristics: str = ""
    living_arrangement: LivingArrangementValue | None = None
    boarding_exclusive: bool | None = None
    boarding_landlord_name: str = ""
    boarding_address: str = ""
    present_place_people_count: int | None = Field(default=None, ge=0)
    room_sharing_people_count: int | None = Field(default=None, ge=0)
    accidents_experienced: str = ""
    accidents_effect: str = ""
    operations_experienced: str = ""
    operations_effect: str = ""
    immunizations: list[ImmunizationValue] = Field(default_factory=list)
    immunization_other: str = ""
    height: str = ""
    weight: str = ""
    physical_disadvantage: str = ""
    illness_this_year: str = ""
    previous_illness: str = ""
    education_entries: list[EducationEntryPayload] = Field(default_factory=list)
    program_id: UUID | None = None
    year_level: int | None = Field(default=None, ge=1, le=10)
    course_currently_enrolled: str = ""
    major: str = ""
    schedule_satisfied: bool | None = None
    schedule_satisfaction_reason: str = ""
    course_first_choice: bool | None = None
    course_choice_reasons: list[CourseChoiceReasonValue] = Field(default_factory=list)
    course_choice_other: str = ""
    lowest_subjects_grades: str = ""
    highest_subjects_grades: str = ""
    inclination_performing_arts: str = ""
    inclination_sports: str = ""
    inclination_leadership: str = ""
    interests: list[InterestValue] = Field(default_factory=list)
    other_skills_hobbies: str = ""
    desired_extracurricular_activities: str = ""
    reading_preferences: str = ""
    handedness: HandednessValue | None = None
    daily_hours_class: Decimal | None = Field(default=None, ge=0, le=24)
    daily_hours_library: Decimal | None = Field(default=None, ge=0, le=24)
    daily_hours_studying: Decimal | None = Field(default=None, ge=0, le=24)
    daily_hours_rest: Decimal | None = Field(default=None, ge=0, le=24)
    daily_hours_recreation: Decimal | None = Field(default=None, ge=0, le=24)
    daily_hours_other: Decimal | None = Field(default=None, ge=0, le=24)
    organization_memberships: list[OrganizationMembershipPayload] = Field(default_factory=list)
    transportation_entries: list[TransportationEntryPayload] = Field(default_factory=list)
    ideal_monthly_allowance: IdealAllowanceBandValue | None = None
    intended_work_field: PostGraduationFieldValue | None = None
    intended_work_other: str = ""
    prior_counseling_experience: bool | None = None
    prior_counselor_name: str = ""
    prior_counseling_when: str = ""
    prior_counseling_where: str = ""
    current_concerns: str = ""
    current_fears: str = ""


class AcademicYearSummary(StrictSchema):
    id: UUID
    label: str


class InventoryProgramSummary(StrictSchema):
    id: UUID
    code: str
    name: str
    college_id: UUID


class FormRevisionSummary(StrictSchema):
    id: UUID
    official_code: str | None
    official_revision: str | None
    internal_schema_version: int


class InventoryStatusResponse(StrictSchema):
    academic_year: AcademicYearSummary
    status: InventoryStatusValue
    submitted_at: datetime | None
    form_revision: FormRevisionSummary | None


class InventorySummaryResponse(StrictSchema):
    id: UUID
    academic_year: AcademicYearSummary
    status: InventoryStatusValue
    submitted_at: datetime | None
    form_revision: FormRevisionSummary


class InventoryResponse(InventoryPayload):
    id: UUID
    academic_year: AcademicYearSummary
    program: InventoryProgramSummary | None
    status: InventoryStatusValue
    submitted_at: datetime | None
    form_revision: FormRevisionSummary


class InventoryHistoryResponse(StrictSchema):
    items: list[InventorySummaryResponse]


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _require_student(request, capability: str) -> None:
    user = request.auth_user
    if user.role.code != "STUDENT" or not user.has_capability(capability):
        raise APIError(
            403, "permission_denied", "Student Inventory self-service access is required."
        )


def _raise(exc: InventoryError) -> NoReturn:
    if isinstance(exc, InventoryCurrentStudentRequired):
        raise APIError(409, "current_student_required", str(exc)) from exc
    if isinstance(exc, InventoryNotFound):
        raise APIError(404, "inventory_not_found", str(exc)) from exc
    if isinstance(exc, CurrentAcademicYearNotConfigured):
        raise APIError(409, "current_academic_year_not_configured", str(exc)) from exc
    if isinstance(exc, InventoryFormRevisionNotConfigured):
        raise APIError(409, "inventory_form_revision_not_configured", str(exc)) from exc
    if isinstance(exc, InventoryConflict):
        raise APIError(409, "inventory_conflict", str(exc)) from exc
    if isinstance(exc, InvalidInventoryInput):
        raise APIError(422, "inventory_invalid", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The Inventory operation could not be completed."
    ) from exc


def _revision(item) -> dict[str, object]:
    return {
        "id": item.pk,
        "official_code": item.official_code,
        "official_revision": item.official_revision,
        "internal_schema_version": item.internal_schema_version,
    }


def _academic_year(item) -> dict[str, object]:
    return {"id": item.pk, "label": item.label}


def _status(item) -> str:
    return InventoryStatus.SUBMITTED if item.submitted_at is not None else InventoryStatus.DRAFT


def _optional_choice(value):
    return value or None


def _child_rows(item, relation: str, fields: tuple[str, ...]) -> list[dict[str, object]]:
    return [
        {field: getattr(row, field) for field in fields} for row in getattr(item, relation).all()
    ]


def _inventory(item) -> dict[str, object]:
    data: dict[str, object] = {
        "id": item.pk,
        "academic_year": _academic_year(item.academic_year),
        "status": _status(item),
        "submitted_at": item.submitted_at,
        "form_revision": _revision(item.form_revision),
        "full_name": item.full_name_snapshot,
    }
    for field in (
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
        "year_level",
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
    ):
        data[field] = getattr(item, field)
    data["program_id"] = item.program_id
    data["program"] = (
        {
            "id": item.program.pk,
            "code": item.program.code,
            "name": item.program.name,
            "college_id": item.program.college_id,
        }
        if item.program is not None
        else None
    )
    for field in (
        "sex",
        "living_arrangement",
        "handedness",
        "ideal_monthly_allowance",
        "intended_work_field",
    ):
        data[field] = _optional_choice(data[field])
    data["family_members"] = _child_rows(
        item,
        "family_members",
        (
            "kind",
            "name",
            "date_of_birth",
            "place_of_birth",
            "current_address",
            "permanent_address",
            "contact_number",
            "email_address",
            "educational_attainment",
            "occupation",
            "business_address",
            "business_telephone",
            "annual_income_previous_year",
            "languages_spoken",
            "religion_raised_with",
            "current_religion",
        ),
    )
    data["siblings"] = _child_rows(
        item,
        "siblings",
        ("sort_order", "name", "sex", "age", "educational_attainment", "occupation", "is_self"),
    )
    data["education_entries"] = _child_rows(
        item,
        "education_entries",
        ("level", "school_attended_address", "inclusive_years", "awards_received"),
    )
    data["organization_memberships"] = _child_rows(
        item,
        "organization_memberships",
        ("scope", "sort_order", "organization_name", "position_title"),
    )
    data["transportation_entries"] = _child_rows(
        item,
        "transportation_entries",
        ("mode", "frequency", "fare"),
    )
    return data


def _payload_values(payload: InventoryPayload) -> dict[str, object]:
    values = payload.model_dump(mode="python")
    values["full_name_snapshot"] = values.pop("full_name")
    return values


@router.get(
    "/me/status",
    response=response_with_errors(InventoryStatusResponse, 401, 403, 409),
    auth=session_auth,
    operation_id="inventoryGetMyStatus",
)
def inventory_get_my_status(request):
    _require_student(request, "inventory.view_self")
    try:
        result = get_current_inventory_status(request.auth_user)
    except InventoryError as exc:
        _raise(exc)
    item = result.inventory
    return {
        "academic_year": _academic_year(result.academic_year),
        "status": result.status,
        "submitted_at": item.submitted_at if item is not None else None,
        "form_revision": _revision(item.form_revision) if item is not None else None,
    }


@router.get(
    "/me/current",
    response=response_with_errors(InventoryResponse, 401, 403, 404, 409),
    auth=session_auth,
    operation_id="inventoryGetMyCurrent",
)
def inventory_get_my_current(request):
    _require_student(request, "inventory.view_self")
    try:
        return _inventory(get_current_inventory(request.auth_user))
    except InventoryError as exc:
        _raise(exc)


@router.post(
    "/me/current",
    response=response_with_errors(InventoryResponse, 401, 403, 409, 422),
    auth=session_auth,
    operation_id="inventoryEnsureMyCurrent",
)
def inventory_ensure_my_current(request):
    _require_student(request, "inventory.manage_self")
    try:
        return _inventory(
            ensure_current_inventory(student=request.auth_user, context=_context(request))
        )
    except InventoryError as exc:
        _raise(exc)


@router.put(
    "/me/current",
    response=response_with_errors(InventoryResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="inventoryUpdateMyCurrent",
)
def inventory_update_my_current(request, payload: InventoryPayload):
    _require_student(request, "inventory.manage_self")
    try:
        return _inventory(
            replace_current_inventory(student=request.auth_user, values=_payload_values(payload))
        )
    except InventoryError as exc:
        _raise(exc)


@router.post(
    "/me/current/submit",
    response=response_with_errors(InventoryResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="inventorySubmitMyCurrent",
)
def inventory_submit_my_current(request):
    _require_student(request, "inventory.manage_self")
    try:
        return _inventory(
            submit_current_inventory(student=request.auth_user, context=_context(request))
        )
    except InventoryError as exc:
        _raise(exc)


@router.get(
    "/me/history",
    response=response_with_errors(InventoryHistoryResponse, 401, 403),
    auth=session_auth,
    operation_id="inventoryListMyHistory",
)
def inventory_list_my_history(request):
    _require_student(request, "inventory.view_self")
    return {
        "items": [
            {
                "id": item.pk,
                "academic_year": _academic_year(item.academic_year),
                "status": _status(item),
                "submitted_at": item.submitted_at,
                "form_revision": _revision(item.form_revision),
            }
            for item in list_my_inventory_history(request.auth_user)
        ]
    }


@router.get(
    "/me/{inventory_id}",
    response=response_with_errors(InventoryResponse, 401, 403, 404),
    auth=session_auth,
    operation_id="inventoryGetMyHistoryItem",
)
def inventory_get_my_history_item(request, inventory_id: UUID):
    _require_student(request, "inventory.view_self")
    try:
        return _inventory(
            get_my_inventory_history_item(student=request.auth_user, inventory_id=inventory_id)
        )
    except InventoryError as exc:
        _raise(exc)
