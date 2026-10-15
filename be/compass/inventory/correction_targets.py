"""Backend-owned Individual Inventory correction-target catalog (FORM-CORR-1).

A correction target names the part of an Inventory that an authorized Counselor asks the Student
to review again. It is advisory: it never blocks saving or resubmission, and it does not mean the
answer is wrong. The required written reason stays the primary instruction.

Compatibility rules:

- Codes are stable and append-only. Never rename, reuse, or remove a released code: encrypted
  correction events may reference it after the code leaves the catalog.
- A code identifies a section, a question, or a question on a naturally keyed row (family member
  kind, education level, transportation mode, location kind). It never contains an answer value,
  an array position, a database row id, or a frontend element id.
- Siblings and organization memberships are recreated on every save and renumbered by the editor,
  so they are targeted only as whole lists.
- Account-owned and derived values are not targetable (``EXCLUDED_ANSWERS``).
- Enum order is the canonical order; stored lists are normalized to it.
- Every Inventory form revision shares answer schema 1, so one catalog serves all of them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from .errors import InvalidInventoryInput

MAX_CORRECTION_TARGETS = 30


class InventoryCorrectionTarget(StrEnum):
    SECTION_PERSONAL = "section.personal"
    PERSONAL_FULL_NAME = "personal.full_name"
    PERSONAL_NICKNAME = "personal.nickname"
    PERSONAL_DATE_OF_BIRTH = "personal.date_of_birth"
    PERSONAL_PLACE_OF_BIRTH = "personal.place_of_birth"
    PERSONAL_NATIONALITY = "personal.nationality"
    PERSONAL_SEX = "personal.sex"
    PERSONAL_BIRTH_ORDER = "personal.birth_order"
    PERSONAL_CIVIL_STATUS = "personal.civil_status"
    PERSONAL_CURRENT_ADDRESS = "personal.current_address"
    PERSONAL_PERMANENT_ADDRESS = "personal.permanent_address"
    PERSONAL_CONTACT_NUMBER = "personal.contact_number"
    PERSONAL_EMAIL_ADDRESS = "personal.email_address"
    PERSONAL_LANGUAGES_SPOKEN_AT_HOME = "personal.languages_spoken_at_home"
    PERSONAL_LANGUAGES_MOST_FLUENT = "personal.languages_most_fluent"
    PERSONAL_RELIGION_FROM_BIRTH = "personal.religion_from_birth"
    PERSONAL_CURRENT_RELIGION = "personal.current_religion"
    PERSONAL_CURRENT_LOCATION = "personal.current_location"
    PERSONAL_PERMANENT_LOCATION = "personal.permanent_location"

    SECTION_FAMILY = "section.family"
    FAMILY_FATHER_NAME = "family.father.name"
    FAMILY_FATHER_OCCUPATION = "family.father.occupation"
    FAMILY_FATHER_ANNUAL_INCOME = "family.father.annual_income"
    FAMILY_FATHER_DATE_OF_BIRTH = "family.father.date_of_birth"
    FAMILY_FATHER_PLACE_OF_BIRTH = "family.father.place_of_birth"
    FAMILY_FATHER_CURRENT_ADDRESS = "family.father.current_address"
    FAMILY_FATHER_PERMANENT_ADDRESS = "family.father.permanent_address"
    FAMILY_FATHER_CONTACT_NUMBER = "family.father.contact_number"
    FAMILY_FATHER_EMAIL_ADDRESS = "family.father.email_address"
    FAMILY_FATHER_EDUCATIONAL_ATTAINMENT = "family.father.educational_attainment"
    FAMILY_FATHER_BUSINESS_ADDRESS = "family.father.business_address"
    FAMILY_FATHER_BUSINESS_TELEPHONE = "family.father.business_telephone"
    FAMILY_FATHER_LANGUAGES_SPOKEN = "family.father.languages_spoken"
    FAMILY_FATHER_RELIGION_RAISED_WITH = "family.father.religion_raised_with"
    FAMILY_FATHER_CURRENT_RELIGION = "family.father.current_religion"
    FAMILY_MOTHER_NAME = "family.mother.name"
    FAMILY_MOTHER_OCCUPATION = "family.mother.occupation"
    FAMILY_MOTHER_ANNUAL_INCOME = "family.mother.annual_income"
    FAMILY_MOTHER_DATE_OF_BIRTH = "family.mother.date_of_birth"
    FAMILY_MOTHER_PLACE_OF_BIRTH = "family.mother.place_of_birth"
    FAMILY_MOTHER_CURRENT_ADDRESS = "family.mother.current_address"
    FAMILY_MOTHER_PERMANENT_ADDRESS = "family.mother.permanent_address"
    FAMILY_MOTHER_CONTACT_NUMBER = "family.mother.contact_number"
    FAMILY_MOTHER_EMAIL_ADDRESS = "family.mother.email_address"
    FAMILY_MOTHER_EDUCATIONAL_ATTAINMENT = "family.mother.educational_attainment"
    FAMILY_MOTHER_BUSINESS_ADDRESS = "family.mother.business_address"
    FAMILY_MOTHER_BUSINESS_TELEPHONE = "family.mother.business_telephone"
    FAMILY_MOTHER_LANGUAGES_SPOKEN = "family.mother.languages_spoken"
    FAMILY_MOTHER_RELIGION_RAISED_WITH = "family.mother.religion_raised_with"
    FAMILY_MOTHER_CURRENT_RELIGION = "family.mother.current_religion"
    FAMILY_SPOUSE_NAME = "family.spouse.name"
    FAMILY_SPOUSE_OCCUPATION = "family.spouse.occupation"
    FAMILY_SPOUSE_ANNUAL_INCOME = "family.spouse.annual_income"
    FAMILY_SPOUSE_DATE_OF_BIRTH = "family.spouse.date_of_birth"
    FAMILY_SPOUSE_PLACE_OF_BIRTH = "family.spouse.place_of_birth"
    FAMILY_SPOUSE_CURRENT_ADDRESS = "family.spouse.current_address"
    FAMILY_SPOUSE_PERMANENT_ADDRESS = "family.spouse.permanent_address"
    FAMILY_SPOUSE_CONTACT_NUMBER = "family.spouse.contact_number"
    FAMILY_SPOUSE_EMAIL_ADDRESS = "family.spouse.email_address"
    FAMILY_SPOUSE_EDUCATIONAL_ATTAINMENT = "family.spouse.educational_attainment"
    FAMILY_SPOUSE_BUSINESS_ADDRESS = "family.spouse.business_address"
    FAMILY_SPOUSE_BUSINESS_TELEPHONE = "family.spouse.business_telephone"
    FAMILY_SPOUSE_LANGUAGES_SPOKEN = "family.spouse.languages_spoken"
    FAMILY_SPOUSE_RELIGION_RAISED_WITH = "family.spouse.religion_raised_with"
    FAMILY_SPOUSE_CURRENT_RELIGION = "family.spouse.current_religion"
    FAMILY_PARENT_STATUS_CATEGORY = "family.parent_status_category"
    FAMILY_PARENT_STATUSES = "family.parent_statuses"
    FAMILY_GUARDIAN_NAME = "family.guardian_name"
    FAMILY_GUARDIAN_RELATIONSHIP = "family.guardian_relationship"
    FAMILY_GUARDIAN_ADDRESS = "family.guardian_address"
    FAMILY_GUARDIAN_CONTACT_NUMBER = "family.guardian_contact_number"
    FAMILY_EMERGENCY_CONTACT_NAME = "family.emergency_contact_name"
    FAMILY_EMERGENCY_CONTACT_NUMBER = "family.emergency_contact_number"
    FAMILY_FOUR_PS_STATUS = "family.four_ps_status"
    FAMILY_INDIGENOUS_PEOPLES_STATUS = "family.indigenous_peoples_status"
    FAMILY_MOTHER_LIFE_STATUS = "family.mother_life_status"
    FAMILY_FATHER_LIFE_STATUS = "family.father_life_status"

    SECTION_BACKGROUND = "section.background"
    BACKGROUND_SIBLINGS = "background.siblings"
    BACKGROUND_FRIENDS_IN_SCHOOL = "background.friends_in_school"
    BACKGROUND_FRIENDS_OUTSIDE_SCHOOL = "background.friends_outside_school"
    BACKGROUND_SPECIAL_INTEREST = "background.special_interest"
    BACKGROUND_SPECIAL_SKILLS_TALENTS = "background.special_skills_talents"
    BACKGROUND_HOBBIES_RECREATION = "background.hobbies_recreation"
    BACKGROUND_AMBITION_GOAL = "background.ambition_goal"
    BACKGROUND_CHARACTERISTICS = "background.characteristics"

    SECTION_HEALTH = "section.health"
    HEALTH_LIVING_ARRANGEMENT = "health.living_arrangement"
    HEALTH_PRESENT_PLACE_PEOPLE_COUNT = "health.present_place_people_count"
    HEALTH_ROOM_SHARING_PEOPLE_COUNT = "health.room_sharing_people_count"
    HEALTH_BOARDING_EXCLUSIVE = "health.boarding_exclusive"
    HEALTH_BOARDING_LANDLORD_NAME = "health.boarding_landlord_name"
    HEALTH_BOARDING_ADDRESS = "health.boarding_address"
    HEALTH_ACCIDENTS_EXPERIENCED = "health.accidents_experienced"
    HEALTH_ACCIDENTS_EFFECT = "health.accidents_effect"
    HEALTH_OPERATIONS_EXPERIENCED = "health.operations_experienced"
    HEALTH_OPERATIONS_EFFECT = "health.operations_effect"
    HEALTH_IMMUNIZATIONS = "health.immunizations"
    HEALTH_HEIGHT = "health.height"
    HEALTH_WEIGHT = "health.weight"
    HEALTH_PWD_STATUS = "health.pwd_status"
    HEALTH_ILLNESS_THIS_YEAR = "health.illness_this_year"
    HEALTH_PREVIOUS_ILLNESS = "health.previous_illness"

    SECTION_EDUCATION = "section.education"
    EDUCATION_HISTORY_PREPARATORY = "education.history.preparatory"
    EDUCATION_HISTORY_ELEMENTARY = "education.history.elementary"
    EDUCATION_HISTORY_JUNIOR_HIGH = "education.history.junior_high"
    EDUCATION_HISTORY_SENIOR_HIGH = "education.history.senior_high"
    EDUCATION_HISTORY_TECHNICAL_VOCATIONAL = "education.history.technical_vocational"
    EDUCATION_HISTORY_COLLEGIATE = "education.history.collegiate"
    EDUCATION_PROGRAM = "education.program"
    EDUCATION_YEAR_LEVEL = "education.year_level"
    EDUCATION_MAJOR = "education.major"
    EDUCATION_SCHEDULE_SATISFACTION = "education.schedule_satisfaction"

    SECTION_INTERESTS = "section.interests"
    INTERESTS_COURSE_FIRST_CHOICE = "interests.course_first_choice"
    INTERESTS_COURSE_CHOICE_REASONS = "interests.course_choice_reasons"
    INTERESTS_LOWEST_SUBJECTS_GRADES = "interests.lowest_subjects_grades"
    INTERESTS_HIGHEST_SUBJECTS_GRADES = "interests.highest_subjects_grades"
    INTERESTS_INCLINATION_PERFORMING_ARTS = "interests.inclination_performing_arts"
    INTERESTS_INCLINATION_SPORTS = "interests.inclination_sports"
    INTERESTS_INCLINATION_LEADERSHIP = "interests.inclination_leadership"
    INTERESTS_INTERESTS = "interests.interests"
    INTERESTS_OTHER_SKILLS_HOBBIES = "interests.other_skills_hobbies"
    INTERESTS_DESIRED_EXTRACURRICULAR_ACTIVITIES = "interests.desired_extracurricular_activities"
    INTERESTS_READING_PREFERENCES = "interests.reading_preferences"
    INTERESTS_HANDEDNESS = "interests.handedness"
    INTERESTS_DAILY_HOURS_CLASS = "interests.daily_hours_class"
    INTERESTS_DAILY_HOURS_LIBRARY = "interests.daily_hours_library"
    INTERESTS_DAILY_HOURS_STUDYING = "interests.daily_hours_studying"
    INTERESTS_DAILY_HOURS_REST = "interests.daily_hours_rest"
    INTERESTS_DAILY_HOURS_RECREATION = "interests.daily_hours_recreation"
    INTERESTS_DAILY_HOURS_OTHER = "interests.daily_hours_other"

    SECTION_ORGANIZATIONS = "section.organizations"
    ORGANIZATIONS_INSIDE_SCHOOL = "organizations.inside_school"
    ORGANIZATIONS_OUTSIDE_SCHOOL = "organizations.outside_school"
    ORGANIZATIONS_TRANSPORTATION_MODES = "organizations.transportation_modes"
    ORGANIZATIONS_TRANSPORTATION_TRICYCLE = "organizations.transportation.tricycle"
    ORGANIZATIONS_TRANSPORTATION_BUS = "organizations.transportation.bus"
    ORGANIZATIONS_TRANSPORTATION_JEEPNEY = "organizations.transportation.jeepney"
    ORGANIZATIONS_TRANSPORTATION_VAN = "organizations.transportation.van"
    ORGANIZATIONS_TRANSPORTATION_BOAT = "organizations.transportation.boat"

    SECTION_PLANS = "section.plans"
    PLANS_IDEAL_MONTHLY_ALLOWANCE = "plans.ideal_monthly_allowance"
    PLANS_INTENDED_WORK_FIELD = "plans.intended_work_field"
    PLANS_PRIOR_COUNSELING = "plans.prior_counseling"
    PLANS_CURRENT_CONCERNS = "plans.current_concerns"
    PLANS_CURRENT_FEARS = "plans.current_fears"


_T = InventoryCorrectionTarget

# Payload keys excluded from targeting, with the reason. Corrections to them go elsewhere.
EXCLUDED_ANSWERS: Mapping[str, str] = MappingProxyType(
    {
        "student_number": "Account-owned Institutional ID; copied from the account on every save.",
        "course_currently_enrolled": "Derived from the selected Program; see education.program.",
    }
)

_FAMILY_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "name": ("name",),
        "occupation": ("occupation_category", "occupation"),
        "annual_income": ("annual_income_status", "annual_income_previous_year"),
        "date_of_birth": ("date_of_birth",),
        "place_of_birth": ("place_of_birth",),
        "current_address": ("current_address",),
        "permanent_address": ("permanent_address",),
        "contact_number": ("contact_number",),
        "email_address": ("email_address",),
        "educational_attainment": ("educational_attainment",),
        "business_address": ("business_address",),
        "business_telephone": ("business_telephone",),
        "languages_spoken": ("languages_spoken",),
        "religion_raised_with": ("religion_raised_with",),
        "current_religion": ("current_religion",),
    }
)
_EDUCATION_FIELDS = ("school_attended_address", "inclusive_years", "awards_received")
_ORGANIZATION_FIELDS = ("sort_order", "organization_name", "position_title")
_TRANSPORTATION_FIELDS = ("frequency_category", "frequency", "fare")
_LOCATION_FIELDS = (
    "not_specified",
    "region_psgc_code",
    "region_name_snapshot",
    "province_psgc_code",
    "province_name_snapshot",
    "city_municipality_psgc_code",
    "city_municipality_name_snapshot",
    "barangay_psgc_code",
    "barangay_name_snapshot",
)
_SIBLING_FIELDS = (
    "sort_order",
    "name",
    "sex",
    "age",
    "educational_attainment",
    "occupation",
    "is_self",
)


def _keyed(collection: str, key: str, fields: Iterable[str]) -> frozenset[str]:
    return frozenset(f"{collection}.{key}.{field}" for field in fields)


def _root(*keys: str) -> frozenset[str]:
    return frozenset(keys)


def _coverage() -> dict[InventoryCorrectionTarget, frozenset[str]]:
    coverage: dict[InventoryCorrectionTarget, frozenset[str]] = {
        target: frozenset() for target in _T if target.value.startswith("section.")
    }
    simple_prefixes = ("personal.", "background.", "health.", "interests.", "plans.")
    for target in _T:
        if target in coverage or not target.value.startswith(simple_prefixes):
            continue
        coverage[target] = _root(target.value.split(".", 1)[1])
    coverage.update(
        {
            _T.PERSONAL_FULL_NAME: _root("full_name"),
            _T.PERSONAL_BIRTH_ORDER: _root("birth_order_among_siblings"),
            _T.PERSONAL_CIVIL_STATUS: _root("civil_status_category", "civil_status"),
            _T.PERSONAL_CURRENT_RELIGION: _root("current_religion_category", "current_religion"),
            _T.PERSONAL_CURRENT_LOCATION: _keyed(
                "geographic_locations", "CURRENT", _LOCATION_FIELDS
            ),
            _T.PERSONAL_PERMANENT_LOCATION: _keyed(
                "geographic_locations", "PERMANENT", _LOCATION_FIELDS
            ),
            _T.BACKGROUND_SIBLINGS: frozenset(f"siblings.{field}" for field in _SIBLING_FIELDS),
            _T.HEALTH_IMMUNIZATIONS: _root("immunizations", "immunization_other"),
            _T.HEALTH_PWD_STATUS: _root("pwd_status", "physical_disadvantage"),
            _T.INTERESTS_COURSE_CHOICE_REASONS: _root(
                "course_choice_reasons", "course_choice_other"
            ),
            _T.PLANS_INTENDED_WORK_FIELD: _root("intended_work_field", "intended_work_other"),
            _T.PLANS_PRIOR_COUNSELING: _root(
                "prior_counseling_experience",
                "prior_counselor_name",
                "prior_counseling_when",
                "prior_counseling_where",
            ),
            _T.EDUCATION_PROGRAM: _root("program_id"),
            _T.EDUCATION_YEAR_LEVEL: _root("year_level"),
            _T.EDUCATION_MAJOR: _root("major"),
            _T.EDUCATION_SCHEDULE_SATISFACTION: _root(
                "schedule_satisfied", "schedule_satisfaction_reason"
            ),
            _T.ORGANIZATIONS_INSIDE_SCHOOL: _keyed(
                "organization_memberships", "INSIDE_SCHOOL", _ORGANIZATION_FIELDS
            ),
            _T.ORGANIZATIONS_OUTSIDE_SCHOOL: _keyed(
                "organization_memberships", "OUTSIDE_SCHOOL", _ORGANIZATION_FIELDS
            ),
            _T.ORGANIZATIONS_TRANSPORTATION_MODES: _root("transportation_entries.mode"),
        }
    )
    for kind in ("FATHER", "MOTHER", "SPOUSE"):
        for name, fields in _FAMILY_FIELDS.items():
            coverage[_T(f"family.{kind.lower()}.{name}")] = _keyed("family_members", kind, fields)
    for name in (
        "parent_status_category",
        "parent_statuses",
        "guardian_name",
        "guardian_relationship",
        "guardian_address",
        "guardian_contact_number",
        "emergency_contact_name",
        "emergency_contact_number",
    ):
        coverage[_T(f"family.{name}")] = _root(name)
    for name in (
        "four_ps_status",
        "indigenous_peoples_status",
        "mother_life_status",
        "father_life_status",
    ):
        coverage[_T(f"family.{name}")] = _root(f"support_profile.{name}")
    for level in (
        "PREPARATORY",
        "ELEMENTARY",
        "JUNIOR_HIGH",
        "SENIOR_HIGH",
        "TECHNICAL_VOCATIONAL",
        "COLLEGIATE",
    ):
        coverage[_T(f"education.history.{level.lower()}")] = _keyed(
            "education_entries", level, _EDUCATION_FIELDS
        )
    for mode in ("TRICYCLE", "BUS", "JEEPNEY", "VAN", "BOAT"):
        coverage[_T(f"organizations.transportation.{mode.lower()}")] = _keyed(
            "transportation_entries", mode, _TRANSPORTATION_FIELDS
        )
    return coverage


# The payload answers each code stands for. Section codes cover a whole section rather than keys.
# Keys use the update payload names; keyed rows use ``collection.KEY.field``.
TARGET_COVERAGE: Mapping[InventoryCorrectionTarget, frozenset[str]] = MappingProxyType(_coverage())

_ORDER = {target: index for index, target in enumerate(InventoryCorrectionTarget)}


def normalize_correction_targets(values: object) -> tuple[InventoryCorrectionTarget, ...]:
    """Validate submitted codes, drop repeats, and return them in catalog order.

    Messages never repeat a submitted value.
    """

    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise InvalidInventoryInput("Correction targets must be a list.")
    if len(values) > MAX_CORRECTION_TARGETS:
        raise InvalidInventoryInput(
            f"Select at most {MAX_CORRECTION_TARGETS} parts of the Inventory to review."
        )
    selected: set[InventoryCorrectionTarget] = set()
    for value in values:
        try:
            selected.add(InventoryCorrectionTarget(value))
        except (ValueError, TypeError):
            raise InvalidInventoryInput(
                "One or more selected parts are not part of the Individual Inventory."
            ) from None
    return tuple(sorted(selected, key=_ORDER.__getitem__))


def project_stored_targets(
    codes: Iterable[str],
) -> tuple[tuple[InventoryCorrectionTarget, ...], int]:
    """Keep stored codes this build recognizes, in stored order, and count the others."""

    known: list[InventoryCorrectionTarget] = []
    omitted = 0
    for code in codes:
        try:
            known.append(InventoryCorrectionTarget(code))
        except ValueError:
            omitted += 1
    return tuple(known), omitted
