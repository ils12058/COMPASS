from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.inventory.confidential_content import read_confidential_content
from compass.inventory.models import (
    AnnualIncomeStatus,
    CivilStatusCategory,
    CurrentReligionCategory,
    GeographicLocationKind,
    InventoryFamilyMember,
    InventoryGeographicLocation,
    InventoryTransportationEntry,
    OccupationCategory,
    ParentStatus,
    PWDStatus,
    StudentInventory,
    TransportationFrequencyCategory,
)
from compass.inventory.services import (
    CombinedParentIncomeStatus,
    InvalidInventoryInput,
    ParentIncomeBand,
    classify_parent_annual_income,
    combine_parent_annual_income,
    derive_age_on,
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import Campus, College, Program
from compass.student_support.models import ParentLifeStatus
from tests.inventory_encryption_helpers import create_inventory_row
from tests.inventory_test_helpers import minimum_normalized_inventory_values

pytestmark = pytest.mark.usefixtures("inventory_psgc")


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str = "STUDENT") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Profile",
        last_name="Student",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def configure_year(actor: User, label: str = "2026-2027"):
    year = create_academic_year(label=label, context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def make_program(*, suffix: str = "A") -> Program:
    campus = Campus.objects.create(code=f"CAMP-{suffix}", name=f"Campus {suffix}")
    college = College.objects.create(
        campus=campus,
        code=f"COL-{suffix}",
        name=f"College {suffix}",
    )
    return Program.objects.create(
        college=college,
        code=f"PROG-{suffix}",
        name=f"Program {suffix}",
    )


def make_draft(email: str = "profiling@example.edu") -> tuple[User, Program, StudentInventory]:
    sync_policy()
    admin = make_user(f"admin-{email}", role="IT_ADMIN")
    student = make_user(email)
    configure_year(admin)
    program = make_program(suffix=str(StudentInventory.objects.count() + 1))
    draft = ensure_current_inventory(student=student, context=context(student))
    return student, program, draft


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "expected_text"),
    [
        (CivilStatusCategory.SINGLE, "Single"),
        (CivilStatusCategory.MARRIED, "Married"),
        (CivilStatusCategory.SOLO_PARENT, "Solo Parent"),
    ],
)
def test_civil_status_fixed_categories_normalize_text_snapshot(category, expected_text):
    student, _, _ = make_draft(f"civil-{category.lower()}@example.edu")
    item = replace_current_inventory(
        student=student,
        values={
            "civil_status_category": category,
            "civil_status": "Contradictory client text",
        },
    )
    assert item.civil_status_category == category
    assert read_confidential_content(item).civil_status == expected_text


@pytest.mark.django_db
def test_civil_status_other_requires_detail_and_preserves_custom_text():
    student, _, _ = make_draft("civil-other@example.edu")
    with pytest.raises(InvalidInventoryInput, match="civil_status detail"):
        replace_current_inventory(
            student=student,
            values={"civil_status_category": CivilStatusCategory.OTHER, "civil_status": "  "},
        )

    other = replace_current_inventory(
        student=student,
        values={
            "civil_status_category": CivilStatusCategory.OTHER,
            "civil_status": "Custom status",
        },
    )
    assert read_confidential_content(other).civil_status == "Custom status"


@pytest.mark.django_db
@pytest.mark.parametrize("category", CurrentReligionCategory.values)
def test_current_religion_categories_are_explicit_without_fuzzy_classification(category):
    student, _, _ = make_draft(f"religion-{category.lower()}@example.edu")
    detail = "Custom faith" if category == CurrentReligionCategory.OTHER else "Wrong text"
    item = replace_current_inventory(
        student=student,
        values={
            "current_religion_category": category,
            "current_religion": detail,
        },
    )
    assert item.current_religion_category == category
    if category == CurrentReligionCategory.OTHER:
        assert read_confidential_content(item).current_religion == "Custom faith"
    else:
        assert (
            read_confidential_content(item).current_religion
            == CurrentReligionCategory(category).label
        )


@pytest.mark.django_db
def test_current_religion_other_requires_detail_and_none_is_explicit():
    student, _, _ = make_draft("religion-other@example.edu")
    with pytest.raises(InvalidInventoryInput, match="current_religion detail"):
        replace_current_inventory(
            student=student,
            values={
                "current_religion_category": CurrentReligionCategory.OTHER,
                "current_religion": "",
            },
        )

    none_value = replace_current_inventory(
        student=student,
        values={"current_religion_category": CurrentReligionCategory.NONE},
    )
    assert read_confidential_content(none_value).current_religion == "None"


@pytest.mark.django_db
def test_pwd_status_requires_detail_when_pwd_and_keeps_the_answered_physical_disadvantage():
    student, _, _ = make_draft("physical@example.edu")
    with pytest.raises(InvalidInventoryInput, match="physical_disadvantage detail"):
        replace_current_inventory(
            student=student,
            values={
                "pwd_status": (PWDStatus.PWD),
                "physical_disadvantage": "",
            },
        )

    reported = replace_current_inventory(
        student=student,
        values={
            "pwd_status": (PWDStatus.PWD),
            "physical_disadvantage": "Mobility limitation",
        },
    )
    assert read_confidential_content(reported).physical_disadvantage == "Mobility limitation"

    # The F5 physical-disadvantage answer is required even for a non-PWD Student, and a truthful
    # answer such as "None" is kept rather than cleared.
    none_value = replace_current_inventory(
        student=student,
        values={
            "pwd_status": PWDStatus.NON_PWD,
            "physical_disadvantage": "None",
        },
    )
    assert read_confidential_content(none_value).physical_disadvantage == "None"


@pytest.mark.django_db
@pytest.mark.parametrize("status", ParentStatus.values)
def test_parent_status_checklist_values_are_stored_verbatim(status):
    student, _, _ = make_draft(f"parent-status-{status.lower()}@example.edu")
    item = replace_current_inventory(
        student=student,
        values={"parent_statuses": [status]},
    )
    assert item.parent_statuses == [status]


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["father_life_status", "mother_life_status"])
@pytest.mark.parametrize(
    "life_status",
    [ParentLifeStatus.LIVING, ParentLifeStatus.DECEASED, ParentLifeStatus.UNKNOWN],
)
def test_parent_life_status_is_explicit_support_data_and_not_inferred(field, life_status):
    student, _, _ = make_draft(f"parent-life-{field}-{life_status.lower()}@example.edu")
    item = replace_current_inventory(
        student=student,
        values={"support_profile": {field: life_status}},
    )
    assert getattr(item.support_profile, field) == life_status


@pytest.mark.django_db
def test_spouse_row_is_not_forced_to_have_parent_profiling_statuses():
    student, _, _ = make_draft("spouse@example.edu")
    item = replace_current_inventory(
        student=student,
        values={
            "family_members": [
                {
                    "kind": "SPOUSE",
                    "name": "Spouse Snapshot",
                    "occupation": "Narrative occupation",
                }
            ]
        },
    )
    spouse = item.family_members.get(kind="SPOUSE")
    assert not hasattr(spouse, "life_status")
    assert spouse.occupation_category is None
    assert spouse.annual_income_status is None


@pytest.mark.django_db
@pytest.mark.parametrize("category", OccupationCategory.values)
def test_parent_occupation_category_requires_detail_only_for_other(category):
    student, _, _ = make_draft(f"occupation-{category.lower()}@example.edu")
    detail = "Custom occupation" if category == OccupationCategory.OTHER else "Narrative detail"
    item = replace_current_inventory(
        student=student,
        values={
            "family_members": [
                {
                    "kind": "MOTHER",
                    "occupation_category": category,
                    "occupation": detail,
                }
            ]
        },
    )
    mother = item.family_members.get(kind="MOTHER")
    assert mother.occupation_category == category
    if category == OccupationCategory.OTHER:
        assert read_confidential_content(mother).occupation == "Custom occupation"
    elif category == OccupationCategory.NONE:
        assert read_confidential_content(mother).occupation == ""
    else:
        assert read_confidential_content(mother).occupation == "Narrative detail"


@pytest.mark.django_db
def test_parent_occupation_other_rejects_blank_detail_and_does_not_keyword_classify():
    student, _, _ = make_draft("occupation-other@example.edu")
    with pytest.raises(InvalidInventoryInput, match="occupation detail"):
        replace_current_inventory(
            student=student,
            values={
                "family_members": [
                    {
                        "kind": "FATHER",
                        "occupation_category": OccupationCategory.OTHER,
                        "occupation": "",
                    }
                ]
            },
        )

    item = replace_current_inventory(
        student=student,
        values={
            "family_members": [{"kind": "FATHER", "occupation": "Farmer"}],
        },
    )
    assert item.family_members.get(kind="FATHER").occupation_category is None


@pytest.mark.django_db
def test_parent_income_status_distinguishes_reported_none_and_unknown():
    student, _, _ = make_draft("income-status@example.edu")

    reported = replace_current_inventory(
        student=student,
        values={
            "family_members": [
                {
                    "kind": "FATHER",
                    "annual_income_status": AnnualIncomeStatus.REPORTED,
                    "annual_income_previous_year": Decimal("120000.00"),
                }
            ]
        },
    ).family_members.get(kind="FATHER")
    assert reported.annual_income_previous_year == Decimal("120000.00")

    none_value = replace_current_inventory(
        student=student,
        values={
            "family_members": [
                {
                    "kind": "FATHER",
                    "annual_income_status": AnnualIncomeStatus.NONE,
                    "annual_income_previous_year": Decimal("999.00"),
                }
            ]
        },
    ).family_members.get(kind="FATHER")
    assert none_value.annual_income_previous_year == Decimal("0")

    unknown = replace_current_inventory(
        student=student,
        values={
            "family_members": [
                {
                    "kind": "FATHER",
                    "annual_income_status": AnnualIncomeStatus.UNKNOWN,
                    "annual_income_previous_year": Decimal("999.00"),
                }
            ]
        },
    ).family_members.get(kind="FATHER")
    assert unknown.annual_income_previous_year is None

    with pytest.raises(InvalidInventoryInput, match="positive amount"):
        replace_current_inventory(
            student=student,
            values={
                "family_members": [
                    {
                        "kind": "FATHER",
                        "annual_income_status": AnnualIncomeStatus.REPORTED,
                        "annual_income_previous_year": Decimal("0"),
                    }
                ]
            },
        )


def test_combined_parent_income_excludes_spouse_and_preserves_unknown_semantics():
    combined = combine_parent_annual_income(
        father_status=AnnualIncomeStatus.REPORTED,
        father_amount=Decimal("100000"),
        mother_status=AnnualIncomeStatus.NONE,
        mother_amount=Decimal("0"),
    )
    assert combined.status == CombinedParentIncomeStatus.REPORTED
    assert combined.amount == Decimal("100000")

    unknown = combine_parent_annual_income(
        father_status=AnnualIncomeStatus.REPORTED,
        father_amount=Decimal("100000"),
        mother_status=AnnualIncomeStatus.UNKNOWN,
        mother_amount=None,
    )
    assert unknown.status == CombinedParentIncomeStatus.UNKNOWN
    assert unknown.amount is None
    assert classify_parent_annual_income(unknown) == ParentIncomeBand.UNKNOWN


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("0"), ParentIncomeBand.NONE),
        (Decimal("131483.99"), ParentIncomeBand.POOR),
        (Decimal("131484"), ParentIncomeBand.LOW_INCOME),
        (Decimal("262968"), ParentIncomeBand.LOWER_MIDDLE_INCOME),
        (Decimal("525936"), ParentIncomeBand.MIDDLE_MIDDLE_INCOME),
        (Decimal("920388"), ParentIncomeBand.UPPER_MIDDLE_INCOME),
        (Decimal("1577808"), ParentIncomeBand.UPPER_INCOME),
        (Decimal("2626680"), ParentIncomeBand.UPPER_INCOME),
        (Decimal("2626680.01"), ParentIncomeBand.RICH),
    ],
)
def test_parent_income_band_boundaries_have_no_overlap_or_gap(amount, expected):
    combined = combine_parent_annual_income(
        father_status=AnnualIncomeStatus.REPORTED if amount > 0 else AnnualIncomeStatus.NONE,
        father_amount=amount,
        mother_status=AnnualIncomeStatus.NONE,
        mother_amount=Decimal("0"),
    )
    assert classify_parent_annual_income(combined) == expected


def test_historical_age_helper_uses_supplied_snapshot_date_not_today():
    birthday = date(2005, 8, 30)
    assert derive_age_on(date_of_birth=birthday, on_date=date(2026, 8, 29)) == 20
    assert derive_age_on(date_of_birth=birthday, on_date=date(2026, 8, 30)) == 21


@pytest.mark.django_db
def test_psgc_snapshot_pairs_are_trimmed_provider_agnostic_and_allow_province_less_city():
    student, _, _ = make_draft("geo@example.edu")
    item = replace_current_inventory(
        student=student,
        values={
            "current_address": "Full descriptive current address",
            "permanent_address": "Full descriptive permanent address",
            "geographic_locations": [
                {
                    "kind": GeographicLocationKind.CURRENT,
                    "region_psgc_code": " 1300000000 ",
                    "region_name_snapshot": " National Capital Region ",
                    "province_psgc_code": "",
                    "province_name_snapshot": "",
                    "city_municipality_psgc_code": " 1374040000 ",
                    "city_municipality_name_snapshot": " Synthetic City ",
                },
                {
                    "kind": GeographicLocationKind.PERMANENT,
                    "region_psgc_code": " 0500000000 ",
                    "region_name_snapshot": " Bicol Region ",
                    "province_psgc_code": " 0516000000 ",
                    "province_name_snapshot": " Synthetic Province ",
                    "city_municipality_psgc_code": " 0516010000 ",
                    "city_municipality_name_snapshot": " Synthetic Municipality ",
                    "barangay_psgc_code": " 0516010001 ",
                    "barangay_name_snapshot": " Synthetic Barangay ",
                },
            ],
        },
    )
    current = item.geographic_locations.get(kind=GeographicLocationKind.CURRENT)
    assert current.region_psgc_code == "1300000000"
    assert current.region_name_snapshot == "National Capital Region"
    assert current.province_psgc_code == ""
    assert current.city_municipality_name_snapshot == "Synthetic City"
    assert read_confidential_content(item).current_address == "Full descriptive current address"
    assert read_confidential_content(item).permanent_address == "Full descriptive permanent address"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_row",
    [
        {
            "kind": "CURRENT",
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "",
            "city_municipality_psgc_code": "0516010000",
            "city_municipality_name_snapshot": "Synthetic Municipality",
        },
        {
            "kind": "CURRENT",
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "Bicol Region",
            "province_psgc_code": "0516000000",
            "province_name_snapshot": "",
            "city_municipality_psgc_code": "0516010000",
            "city_municipality_name_snapshot": "Synthetic Municipality",
        },
        {
            "kind": "CURRENT",
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "Bicol Region",
            "city_municipality_psgc_code": "",
            "city_municipality_name_snapshot": "",
        },
    ],
)
def test_psgc_snapshot_rejects_half_pairs_and_missing_required_region_or_city(bad_row):
    student, _, _ = make_draft("geo-invalid@example.edu")
    with pytest.raises(InvalidInventoryInput, match="PSGC"):
        replace_current_inventory(
            student=student,
            values={"geographic_locations": [bad_row]},
        )


@pytest.mark.django_db
def test_geographic_location_kind_is_unique():
    student, _, _ = make_draft("geo-unique@example.edu")
    with pytest.raises(InvalidInventoryInput, match="unique"):
        replace_current_inventory(
            student=student,
            values={
                "geographic_locations": [
                    {
                        "kind": "CURRENT",
                        "region_psgc_code": "1300000000",
                        "region_name_snapshot": "National Capital Region",
                        "city_municipality_psgc_code": "1380600000",
                        "city_municipality_name_snapshot": "City of Manila",
                    },
                    {
                        "kind": "CURRENT",
                        "region_psgc_code": "1300000000",
                        "region_name_snapshot": "National Capital Region",
                        "city_municipality_psgc_code": "1380600000",
                        "city_municipality_name_snapshot": "City of Manila",
                    },
                ]
            },
        )


@pytest.mark.django_db
def test_geographic_location_db_uniqueness_protects_one_snapshot_per_kind():
    student, _, draft = make_draft("geo-db@example.edu")
    InventoryGeographicLocation.objects.create(
        inventory=draft,
        kind=GeographicLocationKind.CURRENT,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            InventoryGeographicLocation.objects.create(
                inventory=draft,
                kind=GeographicLocationKind.CURRENT,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "expected_frequency"),
    [
        (TransportationFrequencyCategory.DAILY, "Daily"),
        (TransportationFrequencyCategory.SEVERAL_TIMES_A_WEEK, "Several times a week"),
        (TransportationFrequencyCategory.WEEKLY, "Weekly"),
        (TransportationFrequencyCategory.OCCASIONAL, "Occasional"),
    ],
)
def test_transportation_frequency_fixed_categories_normalize_legacy_snapshot(
    category, expected_frequency
):
    student, _, _ = make_draft(f"transport-{category.lower()}@example.edu")
    item = replace_current_inventory(
        student=student,
        values={
            "transportation_entries": [
                {
                    "mode": "TRICYCLE",
                    "frequency_category": category,
                    "frequency": "Wrong text",
                    "fare": Decimal("20.00"),
                }
            ]
        },
    )
    row = item.transportation_entries.get()
    assert read_confidential_content(row).frequency == expected_frequency
    assert row.fare == Decimal("20.00")


@pytest.mark.django_db
@pytest.mark.parametrize("living_arrangement", ["OWN_HOUSE", "WITH_RELATIVES", "BOARDING_HOUSE"])
def test_living_arrangement_reuses_existing_controlled_f5_choices(living_arrangement):
    student, _, _ = make_draft(f"living-{living_arrangement.lower()}@example.edu")
    values = {"living_arrangement": living_arrangement}
    if living_arrangement == "BOARDING_HOUSE":
        values.update(
            {
                "boarding_exclusive": True,
                "boarding_landlord_name": "Landlord",
                "boarding_address": "Boarding address",
            }
        )
    item = replace_current_inventory(student=student, values=values)
    assert item.living_arrangement == living_arrangement


@pytest.mark.django_db
def test_transportation_frequency_other_requires_detail_and_fare_is_not_an_enum():
    student, _, _ = make_draft("transport-other@example.edu")
    with pytest.raises(InvalidInventoryInput, match="frequency detail"):
        replace_current_inventory(
            student=student,
            values={
                "transportation_entries": [
                    {
                        "mode": "BUS",
                        "frequency_category": TransportationFrequencyCategory.OTHER,
                        "frequency": "",
                    }
                ]
            },
        )

    item = replace_current_inventory(
        student=student,
        values={
            "transportation_entries": [
                {
                    "mode": "BUS",
                    "frequency_category": TransportationFrequencyCategory.OTHER,
                    "frequency": "Twice monthly",
                    "fare": Decimal("37.50"),
                }
            ]
        },
    )
    row = item.transportation_entries.get()
    assert read_confidential_content(row).frequency == "Twice monthly"
    assert row.fare == Decimal("37.50")


@pytest.mark.django_db
def test_negative_transport_fare_and_parent_income_have_database_protection():
    student, _, draft = make_draft("db-nonnegative@example.edu")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_inventory_row(
                InventoryTransportationEntry,
                inventory=draft,
                mode="BUS",
                fare=Decimal("-1"),
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_inventory_row(
                InventoryFamilyMember,
                inventory=draft,
                kind="FATHER",
                annual_income_previous_year=Decimal("-1"),
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("missing_field", "message"),
    [
        ("sex", "Choose your sex."),
        ("date_of_birth", "Add your date of birth."),
        ("civil_status_category", "Choose your civil status."),
        ("current_religion_category", "Choose your current religion."),
        ("pwd_status", "Choose your PWD status."),
        ("living_arrangement", "Choose your living arrangement."),
    ],
)
def test_new_submission_rejects_missing_root_profiling_fields(missing_field, message):
    student, program, _ = make_draft(f"missing-{missing_field}@example.edu")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.pop(missing_field)
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match=message):
        submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_new_submission_requires_current_location_and_both_parent_rows_with_explicit_statuses():
    student, program, _ = make_draft("submission-structure@example.edu")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["geographic_locations"] = []
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Choose your current region"):
        submit_current_inventory(student=student, context=context(student))

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["family_members"] = values["family_members"][:1]
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Add your mother's details."):
        submit_current_inventory(student=student, context=context(student))

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["family_members"][0]["occupation_category"] = None
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Choose your father's occupation."):
        submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_existing_transportation_entry_requires_explicit_frequency_category_at_submission():
    student, program, _ = make_draft("transport-submit@example.edu")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["transportation_entries"] = [
        {
            "mode": "BUS",
            "frequency": "legacy-style draft text",
            "fare": Decimal("20"),
        }
    ]
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Choose how often you use each selected mode"):
        submit_current_inventory(student=student, context=context(student))


@pytest.mark.django_db
def test_valid_normalized_inventory_submits_and_freezes_all_snapshots():
    student, program, _ = make_draft("valid-submit@example.edu")
    values = minimum_normalized_inventory_values(program_id=program.pk, year_level=1)
    values.update(
        {
            "civil_status_category": CivilStatusCategory.SINGLE,
            "civil_status": "Bad client text",
            "current_religion_category": CurrentReligionCategory.ROMAN_CATHOLIC,
            "current_religion": "Bad client text",
            "pwd_status": PWDStatus.NON_PWD,
            "physical_disadvantage": "None",
            "transportation_entries": [
                {
                    "mode": "JEEPNEY",
                    "frequency_category": TransportationFrequencyCategory.DAILY,
                    "frequency": "Anything",
                    "fare": Decimal("15.00"),
                }
            ],
        }
    )
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None
    assert read_confidential_content(submitted).civil_status == "Single"
    assert read_confidential_content(submitted).current_religion == "Roman Catholic"
    assert read_confidential_content(submitted).physical_disadvantage == "None"
    assert submitted.course_currently_enrolled == program.name
    assert read_confidential_content(submitted.transportation_entries.get()).frequency == "Daily"


@pytest.mark.django_db
def test_normalization_foundation_does_not_create_reference_or_reporting_engines():
    forbidden = [
        ("inventory", "Religion"),
        ("inventory", "ReligionCatalog"),
        ("inventory", "Region"),
        ("inventory", "Province"),
        ("inventory", "Municipality"),
        ("inventory", "Barangay"),
        ("inventory", "IncomeBand"),
        ("inventory", "ProfilingAttribute"),
        ("inventory", "Report"),
        ("organization", "StudentAcademicClassification"),
        ("organization", "Enrollment"),
    ]
    for app_label, model_name in forbidden:
        with pytest.raises(LookupError):
            apps.get_model(app_label, model_name)
