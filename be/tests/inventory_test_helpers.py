from __future__ import annotations

from datetime import date
from uuid import UUID


def ensure_inventory_form_revision() -> None:
    """Restore the migration-seeded Individual Inventory revision after transactional flushes."""

    from compass.institutional_forms.bootstrap import sync_institutional_forms

    sync_institutional_forms()


def minimum_normalized_inventory_values(
    *,
    program_id: UUID,
    year_level: int = 1,
) -> dict[str, object]:
    """A complete, truthful F5 submission baseline for tests.

    Every answer the official form requires is present so a test can change one value and observe
    exactly that rule. Geography uses the canonical PSGC stub installed by ``tests/conftest.py``.
    """

    return {
        "program_id": program_id,
        "year_level": year_level,
        "full_name_snapshot": "Inventory Test Student",
        "nickname": "Test",
        "student_number": "INV-TEST-0001",
        "date_of_birth": date(2007, 1, 1),
        "place_of_birth": "Daet, Camarines Norte",
        "nationality": "Filipino",
        "sex": "MALE",
        "birth_order_among_siblings": "First",
        "civil_status_category": "SINGLE",
        "current_address": "Synthetic current address",
        "permanent_address": "Synthetic permanent address",
        "contact_number": "0917 000 0000",
        "email_address": "inventory.student@example.edu",
        "languages_spoken_at_home": "Filipino, English",
        "languages_most_fluent": "Filipino, English",
        "religion_from_birth": "Roman Catholic",
        "current_religion_category": "ROMAN_CATHOLIC",
        "parent_statuses": ["MARRIED_ANNULLED_LEGALLY_SEPARATED"],
        "guardian_name": "Synthetic Guardian",
        "guardian_relationship": "Parent",
        "guardian_address": "Synthetic guardian address",
        "guardian_contact_number": "0917 000 0001",
        "emergency_contact_name": "Synthetic Emergency Contact",
        "emergency_contact_number": "0917 000 0002",
        "siblings": [
            {
                "sort_order": 0,
                "is_self": True,
                "name": "Inventory Test Student",
                "sex": "MALE",
                "age": 19,
            }
        ],
        "friends_in_school": "Synthetic school friends",
        "friends_outside_school": "Synthetic friends outside school",
        "special_interest": "Synthetic special interest",
        "special_skills_talents": "Synthetic special skill",
        "hobbies_recreation": "Synthetic hobby",
        "ambition_goal": "Synthetic ambition",
        "characteristics": "Synthetic characteristic",
        "living_arrangement": "OWN_HOUSE",
        "present_place_people_count": 4,
        "room_sharing_people_count": 1,
        "accidents_experienced": "None",
        "operations_experienced": "None",
        "immunizations": [],
        "height": "170 cm",
        "weight": "60 kg",
        "physical_disadvantage": "None",
        "pwd_status": "NON_PWD",
        "illness_this_year": "None",
        "previous_illness": "None",
        "education_entries": [
            {
                "level": "ELEMENTARY",
                "school_attended_address": "Synthetic Elementary School, Daet",
                "inclusive_years": "2013-2019",
            },
            {
                "level": "JUNIOR_HIGH",
                "school_attended_address": "Synthetic Junior High School, Daet",
                "inclusive_years": "2019-2023",
            },
            {
                "level": "SENIOR_HIGH",
                "school_attended_address": "Synthetic Senior High School, Daet",
                "inclusive_years": "2023-2025",
            },
        ],
        "schedule_satisfied": True,
        "course_first_choice": True,
        "course_choice_reasons": ["INTEREST_APTITUDE"],
        "lowest_subjects_grades": "None",
        "highest_subjects_grades": "None",
        "inclination_performing_arts": "None",
        "inclination_sports": "None",
        "inclination_leadership": "None",
        "other_skills_hobbies": "None",
        "desired_extracurricular_activities": "None",
        "reading_preferences": "None",
        "handedness": "RIGHT",
        "daily_hours_class": "4",
        "daily_hours_library": "1",
        "daily_hours_studying": "2",
        "daily_hours_rest": "8",
        "daily_hours_recreation": "2",
        "daily_hours_other": "1",
        "ideal_monthly_allowance": "FROM_100_TO_499",
        "intended_work_field": "PROFESSIONAL",
        "prior_counseling_experience": False,
        "current_concerns": "None",
        "current_fears": "None",
        "family_members": [
            {
                "kind": "FATHER",
                "name": "Synthetic Father",
                "date_of_birth": date(1975, 1, 1),
                "place_of_birth": "Daet, Camarines Norte",
                "current_address": "Synthetic father current address",
                "permanent_address": "Synthetic father permanent address",
                "contact_number": "0917 000 0003",
                "email_address": "father@example.edu",
                "educational_attainment": "College graduate",
                "occupation_category": "NONE",
                "annual_income_status": "NONE",
                "business_address": "None",
                "business_telephone": "None",
                "languages_spoken": "Filipino, English",
                "religion_raised_with": "Roman Catholic",
                "current_religion": "Roman Catholic",
            },
            {
                "kind": "MOTHER",
                "name": "Synthetic Mother",
                "date_of_birth": date(1977, 1, 1),
                "place_of_birth": "Daet, Camarines Norte",
                "current_address": "Synthetic mother current address",
                "permanent_address": "Synthetic mother permanent address",
                "contact_number": "0917 000 0004",
                "email_address": "mother@example.edu",
                "educational_attainment": "College graduate",
                "occupation_category": "NONE",
                "annual_income_status": "NONE",
                "business_address": "None",
                "business_telephone": "None",
                "languages_spoken": "Filipino, English",
                "religion_raised_with": "Roman Catholic",
                "current_religion": "Roman Catholic",
            },
        ],
        "support_profile": {
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        "geographic_locations": [
            {
                "kind": "CURRENT",
                "region_psgc_code": "1300000000",
                "region_name_snapshot": "National Capital Region",
                "province_psgc_code": "",
                "province_name_snapshot": "",
                "city_municipality_psgc_code": "1380600000",
                "city_municipality_name_snapshot": "City of Manila",
            }
        ],
    }
