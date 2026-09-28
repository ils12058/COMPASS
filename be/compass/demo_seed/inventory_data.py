"""Individual Inventory content for the demo cast (data only).

Each Student has one stable background profile plus per-Academic-Year answers, so a Student's
Inventories change believably from year to year (year level, living arrangement, organizations,
concerns) without contradicting each other. Every choice value is an existing Inventory enum.
Geography stays ``not_specified``: structured locations need live PSGC validation, and the seeder
never invents PSGC codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .cast import (
    ACTIVE_REFERRAL,
    ALUMNI,
    FIRST_YEAR,
    FORMER,
    FOURTH_YEAR,
    GOOD_MORAL,
    GRADUATING,
    RECENT_GRADUATE,
    REFERRED,
    SECOND_YEAR,
    StudentPersona,
)

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


@dataclass(frozen=True)
class Sibling:
    name: str
    sex: str
    birth_year: int
    # Explicit attainment for adults; school-age siblings derive their grade from age.
    attainment: str = ""
    occupation: str = ""


@dataclass(frozen=True)
class InventoryYear:
    # (year, month, day, hour, minute) of submission, or of the last draft save for a draft.
    saved_at: tuple[int, int, int, int, int]
    fields: dict[str, object]
    organizations: tuple[tuple[str, str, str], ...] = ()
    transportation: tuple[tuple[str, str, str], ...] = ()
    draft: bool = False


@dataclass(frozen=True)
class InventoryProfile:
    base: dict[str, object]
    father: dict[str, object]
    mother: dict[str, object]
    siblings: tuple[Sibling, ...]
    sibling_position: int
    education: tuple[tuple[str, str, str, str], ...]
    support: dict[str, str]
    years: dict[str, InventoryYear] = field(default_factory=dict)


def _hours(**values: str) -> dict[str, Decimal]:
    # ``class_`` avoids the keyword; the Inventory field is ``daily_hours_class``.
    return {f"daily_hours_{name.rstrip('_')}": Decimal(value) for name, value in values.items()}


def _parent(
    name: str,
    *,
    attainment: str,
    occupation: str,
    category: str,
    income: str | None,
    religion: str = "Roman Catholic",
) -> dict[str, object]:
    return {
        "name": name,
        "educational_attainment": attainment,
        "occupation": occupation,
        "occupation_category": category,
        "annual_income_status": "REPORTED" if income else "NONE",
        "annual_income_previous_year": Decimal(income) if income else None,
        "languages_spoken": "Bikol, Tagalog",
        "religion_raised_with": religion,
        "current_religion": religion,
    }


_COMMON_BASE = {
    "nationality": "Filipino",
    "civil_status_category": "SINGLE",
    "languages_spoken_at_home": "Bikol, Tagalog",
    "languages_most_fluent": "Tagalog, English",
    "religion_from_birth": "Roman Catholic",
    "current_religion_category": "ROMAN_CATHOLIC",
    "parent_statuses": ["MARRIED_ANNULLED_LEGALLY_SEPARATED"],
    "parent_status_category": "MARRIED",
    "pwd_status": "NON_PWD",
    "illness_this_year": "None",
    "previous_illness": "None",
    "accidents_experienced": "None",
    "operations_experienced": "None",
    "handedness": "RIGHT",
    "prior_counseling_experience": False,
}


PROFILES: dict[str, InventoryProfile] = {
    FIRST_YEAR.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Bea",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Eldest of three",
            "emergency_contact_name": "Rogelio Abad (father)",
            "special_interest": "Drawing and page layout",
            "special_skills_talents": "Basic graphic design; plays the keyboard",
            "hobbies_recreation": "Sketching, watching programming tutorials",
            "characteristics": "Quiet at first but friendly; I keep my notes organized.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B", "BOOSTER"],
            "height": "157 cm",
            "weight": "48 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "JOB_OPPORTUNITIES"],
            "interests": ["PAINTING", "PLAYING_INSTRUMENTS"],
            "intended_work_field": "TECHNICAL",
        },
        father=_parent(
            "Rogelio Abad",
            attainment="High school graduate",
            occupation="Tricycle driver",
            category="SELF_EMPLOYED",
            income="108000.00",
        ),
        mother=_parent(
            "Maricel Lagman Abad",
            attainment="High school graduate",
            occupation="Sari-sari store operator",
            category="SELF_EMPLOYED",
            income="54000.00",
        ),
        siblings=(Sibling("Jansen Abad", "MALE", 2011), Sibling("Alyssa Abad", "FEMALE", 2017)),
        sibling_position=1,
        education=(
            ("ELEMENTARY", "Gahonon Elementary School, Daet", "2014-2020", "With Honors"),
            ("JUNIOR_HIGH", "Camarines Norte National High School, Daet", "2020-2024", ""),
            (
                "SENIOR_HIGH",
                "Camarines Norte National High School - Senior High (TVL-ICT), Daet",
                "2024-2026",
                "With Honors",
            ),
        ),
        support={
            "four_ps_status": "BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 12, 19, 40),
                fields={
                    "friends_in_school": "A few classmates from BSIT 1-A; we review together.",
                    "friends_outside_school": "Two senior high friends now studying in Naga.",
                    "ambition_goal": "To become a web developer and help my younger siblings.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "General Chemistry (Grade 11)",
                    "highest_subjects_grades": "Empowerment Technologies; General Mathematics",
                    "inclination_sports": "Badminton, casually",
                    "inclination_leadership": "Class secretary in Grade 12",
                    "desired_extracurricular_activities": "A campus coding or design club",
                    "reading_preferences": "Short web development guides and comics",
                    **_hours(
                        class_="6.00",
                        library="1.00",
                        studying="2.00",
                        rest="7.00",
                        recreation="1.50",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Getting used to programming subjects and long days.",
                    "current_fears": "Falling behind in Computer Programming 1.",
                },
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
        },
    ),
    SECOND_YEAR.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Mika",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Eldest of two",
            "emergency_contact_name": "Jocelyn Serrano (mother)",
            "special_interest": "Reading about child development",
            "special_skills_talents": "Public speaking; event hosting",
            "hobbies_recreation": "Journaling, baking with my mother",
            "characteristics": "Responsible and sociable; tends to take on too many tasks.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B", "INFLUENZA"],
            "height": "160 cm",
            "weight": "52 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "PARENT_CHOICE"],
            "interests": ["SINGING", "COOKING"],
            "intended_work_field": "PROFESSIONAL",
        },
        father=_parent(
            "Arturo Serrano",
            attainment="College graduate (BS Accountancy)",
            occupation="Administrative officer, municipal treasurer's office",
            category="GOVERNMENT_EMPLOYEE",
            income="312000.00",
        ),
        mother=_parent(
            "Jocelyn Ramos Serrano",
            attainment="College level",
            occupation="Home bakery owner",
            category="SELF_EMPLOYED",
            income="144000.00",
        ),
        siblings=(Sibling("Enzo Serrano", "MALE", 2012),),
        sibling_position=1,
        education=(
            ("ELEMENTARY", "Camambugan Elementary School, Daet", "2013-2019", "With Honors"),
            ("JUNIOR_HIGH", "Daet National High School, Daet", "2019-2023", "With Honors"),
            ("SENIOR_HIGH", "Daet National High School - Senior High (HUMSS)", "2023-2025", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 21, 20, 5),
                fields={
                    "friends_in_school": "New blockmates in BS Psychology 1-B.",
                    "friends_outside_school": "Church youth group friends.",
                    "ambition_goal": "To become a registered psychometrician.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 4,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Statistics and Probability (Grade 11)",
                    "highest_subjects_grades": "Oral Communication; Understanding Culture",
                    "inclination_performing_arts": "School choir in senior high",
                    "inclination_leadership": "Grade 12 class president",
                    "desired_extracurricular_activities": "Psychology Society",
                    "reading_preferences": "Popular psychology books",
                    **_hours(
                        class_="6.00",
                        library="1.00",
                        studying="2.50",
                        rest="7.00",
                        recreation="1.00",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Adjusting to college workload.",
                    "current_fears": "Not keeping my academic scholarship.",
                },
                organizations=(("INSIDE_SCHOOL", "Psychology Society", "Member"),),
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 14, 21, 10),
                fields={
                    "friends_in_school": "A small barkada from BS Psychology 2-B.",
                    "friends_outside_school": "Church youth group friends.",
                    "ambition_goal": "To pass the Psychometrician Licensure Examination.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 4,
                    "schedule_satisfied": False,
                    "schedule_satisfaction_reason": "Two major subjects fall on the same long day.",
                    "lowest_subjects_grades": "Psychological Statistics",
                    "highest_subjects_grades": "Developmental Psychology; Purposive Communication",
                    "inclination_performing_arts": "Hosts org events",
                    "inclination_leadership": "Secretary, Psychology Society",
                    "desired_extracurricular_activities": "Peer tutoring",
                    "reading_preferences": "Case studies and journal summaries",
                    **_hours(
                        class_="6.50",
                        library="1.00",
                        studying="3.00",
                        rest="6.00",
                        recreation="0.50",
                        other="2.00",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Keeping up with major subjects and org duties.",
                    "current_fears": "Losing my academic scholarship.",
                },
                organizations=(("INSIDE_SCHOOL", "Psychology Society", "Secretary"),),
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
        },
    ),
    REFERRED.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Rome",
            "place_of_birth": "Labo, Camarines Norte",
            "birth_order_among_siblings": "Second of four",
            "emergency_contact_name": "Jennylyn Dela Paz (sister)",
            "special_interest": "Cooking regional dishes",
            "special_skills_talents": "Food plating; basic carpentry",
            "hobbies_recreation": "Cooking for family gatherings, volleyball",
            "characteristics": "Hardworking and polite; hesitant to ask for help.",
            "immunizations": ["MEASLES_MMR", "BOOSTER"],
            "height": "165 cm",
            "weight": "56 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "MINIMAL_COST"],
            "interests": ["COOKING"],
            "intended_work_field": "BUSINESS",
            "languages_spoken_at_home": "Bikol, Tagalog, and the community's own language",
        },
        father=_parent(
            "Ramil Dela Paz",
            attainment="Elementary graduate",
            occupation="Farmer (abaca and root crops)",
            category="FARMER",
            income="72000.00",
        ),
        mother=_parent(
            "Nenita Salvador Dela Paz",
            attainment="High school level",
            occupation="Farmer",
            category="FARMER",
            income="36000.00",
        ),
        siblings=(
            Sibling(
                "Jennylyn Dela Paz",
                "FEMALE",
                2003,
                attainment="High school graduate",
                occupation="Bakery helper",
            ),
            Sibling("Reymart Dela Paz", "MALE", 2010),
            Sibling("Joven Dela Paz", "MALE", 2014),
        ),
        sibling_position=2,
        education=(
            ("ELEMENTARY", "Tulay na Lupa Elementary School, Labo", "2012-2018", ""),
            ("JUNIOR_HIGH", "Labo National High School, Labo", "2018-2022", ""),
            ("SENIOR_HIGH", "Labo National High School - Senior High (TVL-HE)", "2022-2024", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 22, 18, 30),
                fields={
                    "friends_in_school": "Classmates from BSHM 1-B.",
                    "friends_outside_school": "Youth volunteers in our barangay.",
                    "ambition_goal": "To work in a resort kitchen.",
                    "living_arrangement": "WITH_RELATIVES",
                    "present_place_people_count": 6,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "General Mathematics",
                    "highest_subjects_grades": "Cookery NC II",
                    "inclination_sports": "Volleyball",
                    "desired_extracurricular_activities": "Culinary competitions",
                    **_hours(
                        class_="6.00",
                        library="0.50",
                        studying="1.50",
                        rest="7.00",
                        recreation="1.00",
                        other="2.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Travel expenses between Labo and Daet.",
                    "current_fears": "Being unable to buy laboratory ingredients.",
                },
                transportation=(("VAN", "SEVERAL_TIMES_A_WEEK", "70.00"),),
            ),
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 26, 19, 15),
                fields={
                    "friends_in_school": "BSHM 2-B classmates; a few from the culinary team.",
                    "friends_outside_school": "Youth volunteers in our barangay.",
                    "ambition_goal": "To work in a resort kitchen, then open a small restaurant.",
                    "living_arrangement": "BOARDING_HOUSE",
                    "boarding_exclusive": True,
                    "boarding_landlord_name": "Mrs. Aida Cruz",
                    "boarding_address": "Purok 1, Barangay Lag-on, Daet, Camarines Norte",
                    "present_place_people_count": 8,
                    "room_sharing_people_count": 2,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Principles of Accounting",
                    "highest_subjects_grades": "Kitchen Essentials and Basic Food Preparation",
                    "inclination_sports": "Volleyball",
                    "desired_extracurricular_activities": "Culinary team",
                    **_hours(
                        class_="6.50",
                        library="0.50",
                        studying="1.50",
                        rest="7.00",
                        recreation="1.00",
                        other="1.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Boarding and food expenses.",
                    "current_fears": "Laboratory costs this year.",
                },
                organizations=(("INSIDE_SCHOOL", "HM Culinary Team", "Member"),),
                transportation=(("VAN", "WEEKLY", "80.00"),),
            ),
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 18, 20, 20),
                fields={
                    "friends_in_school": "BSHM 3-B classmates and the culinary team.",
                    "friends_outside_school": "Youth volunteers in our barangay.",
                    "ambition_goal": "Resort or hotel work in Bicol, then a small restaurant.",
                    "living_arrangement": "BOARDING_HOUSE",
                    "boarding_exclusive": True,
                    "boarding_landlord_name": "Mr. Ronaldo Villa",
                    "boarding_address": "Purok 4, Barangay Borabod, Daet, Camarines Norte",
                    "present_place_people_count": 10,
                    "room_sharing_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Food and Beverage Cost Control",
                    "highest_subjects_grades": "Bread and Pastry Production",
                    "inclination_sports": "Volleyball",
                    "desired_extracurricular_activities": "Culinary team",
                    **_hours(
                        class_="7.00",
                        library="0.50",
                        studying="1.50",
                        rest="6.00",
                        recreation="0.50",
                        other="2.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Laboratory expenses and a new boarding house.",
                    "current_fears": "Missing practical requirements when I go home.",
                },
                organizations=(("INSIDE_SCHOOL", "HM Culinary Team", "Member"),),
                transportation=(("VAN", "WEEKLY", "80.00"),),
            ),
        },
    ),
    FOURTH_YEAR.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Kev",
            "place_of_birth": "Labo, Camarines Norte",
            "birth_order_among_siblings": "Youngest of two",
            "emergency_contact_name": "Lorna Pardo (mother)",
            "special_interest": "Database design and small office networks",
            "special_skills_talents": "Spreadsheet automation; basketball",
            "hobbies_recreation": "Basketball on weekends, music",
            "characteristics": "Easygoing and dependable; prefers written instructions.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B"],
            "height": "170 cm",
            "weight": "63 kg",
            "pwd_status": "PWD",
            "physical_disadvantage": (
                "Mild hearing loss in the left ear; prefers a front seat and written copies "
                "of instructions."
            ),
            "course_first_choice": False,
            "course_choice_reasons": ["JOB_OPPORTUNITIES", "FRIENDS"],
            "interests": ["PLAYING_INSTRUMENTS"],
            "intended_work_field": "TECHNICAL",
        },
        father=_parent(
            "Rodel Pardo",
            attainment="High school graduate",
            occupation="Rice farmer",
            category="FARMER",
            income="96000.00",
        ),
        mother=_parent(
            "Lorna Navales Pardo",
            attainment="College level",
            occupation="Barangay day-care worker",
            category="GOVERNMENT_EMPLOYEE",
            income="96000.00",
        ),
        siblings=(
            Sibling(
                "Maricar Pardo",
                "FEMALE",
                1999,
                attainment="College graduate",
                occupation="Customer service representative, Manila",
            ),
        ),
        sibling_position=2,
        education=(
            ("ELEMENTARY", "Talobatib Elementary School, Labo", "2011-2017", ""),
            ("JUNIOR_HIGH", "Labo National High School, Labo", "2017-2021", ""),
            ("SENIOR_HIGH", "Labo National High School - Senior High (STEM)", "2021-2023", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 27, 20, 45),
                fields={
                    "friends_in_school": "BSIS 2-A classmates and teammates.",
                    "friends_outside_school": "Neighborhood basketball friends.",
                    "ambition_goal": "To work in IT support.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Discrete Structures",
                    "highest_subjects_grades": "Fundamentals of Database Systems",
                    "inclination_sports": "Basketball",
                    "desired_extracurricular_activities": "Intramurals",
                    **_hours(
                        class_="6.00",
                        library="0.50",
                        studying="2.00",
                        rest="7.00",
                        recreation="1.50",
                        other="2.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Daily travel from Labo.",
                    "current_fears": "Math-heavy subjects.",
                },
                organizations=(("INSIDE_SCHOOL", "CCMS Varsity Basketball", "Player"),),
                transportation=(("VAN", "DAILY", "60.00"),),
            ),
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 19, 21, 0),
                fields={
                    "friends_in_school": "BSIS 3-A classmates and teammates.",
                    "friends_outside_school": "Neighborhood basketball friends.",
                    "ambition_goal": "To become a systems analyst.",
                    "living_arrangement": "BOARDING_HOUSE",
                    "boarding_exclusive": True,
                    "boarding_landlord_name": "Mrs. Celia Ramos",
                    "boarding_address": "Purok 2, Barangay Bibirao, Daet, Camarines Norte",
                    "present_place_people_count": 6,
                    "room_sharing_people_count": 2,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Quantitative Methods",
                    "highest_subjects_grades": "Systems Analysis and Design",
                    "inclination_sports": "Basketball",
                    "inclination_leadership": "Team captain",
                    "desired_extracurricular_activities": "Intramurals",
                    **_hours(
                        class_="6.00",
                        library="1.00",
                        studying="2.00",
                        rest="7.00",
                        recreation="1.00",
                        other="1.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Boarding costs.",
                    "current_fears": "Group projects with uneven work.",
                },
                organizations=(("INSIDE_SCHOOL", "CCMS Varsity Basketball", "Team captain"),),
                transportation=(("VAN", "WEEKLY", "60.00"),),
            ),
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 11, 20, 15),
                fields={
                    "friends_in_school": "BSIS 4-A classmates; capstone groupmates.",
                    "friends_outside_school": "Neighborhood basketball friends.",
                    "ambition_goal": "To work as a systems analyst in the province.",
                    "living_arrangement": "BOARDING_HOUSE",
                    "boarding_exclusive": True,
                    "boarding_landlord_name": "Mrs. Celia Ramos",
                    "boarding_address": "Purok 2, Barangay Bibirao, Daet, Camarines Norte",
                    "present_place_people_count": 6,
                    "room_sharing_people_count": 2,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "IT Project Management",
                    "highest_subjects_grades": "Enterprise Architecture",
                    "inclination_sports": "Basketball",
                    "desired_extracurricular_activities": "Capstone exhibit",
                    **_hours(
                        class_="5.00",
                        library="1.00",
                        studying="3.00",
                        rest="6.50",
                        recreation="1.00",
                        other="1.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "prior_counseling_experience": True,
                    "prior_counselor_name": "Guidance and Counseling Office",
                    "prior_counseling_when": "February 2026",
                    "prior_counseling_where": "UCN Guidance and Counseling Office",
                    "current_concerns": "Capstone deadlines and group coordination.",
                    "current_fears": "Not finishing the capstone on time.",
                },
                organizations=(("INSIDE_SCHOOL", "CCMS Varsity Basketball", "Player"),),
                transportation=(("VAN", "WEEKLY", "60.00"),),
            ),
        },
    ),
    GRADUATING.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Rose",
            "place_of_birth": "Vinzons, Camarines Norte",
            "birth_order_among_siblings": "Eldest of three",
            "emergency_contact_name": "Teresa Obusan (mother)",
            "special_interest": "Social media marketing for small shops",
            "special_skills_talents": "Product photography; bookkeeping",
            "hobbies_recreation": "Photography, helping at the family store",
            "characteristics": "Practical and organized; responsible for younger siblings.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B", "CHICKEN_POX"],
            "height": "155 cm",
            "weight": "50 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "PARENT_CHOICE"],
            "interests": ["DANCING"],
            "intended_work_field": "BUSINESS",
        },
        father=_parent(
            "Eduardo Obusan",
            attainment="College level",
            occupation="Owner, general merchandise store",
            category="SELF_EMPLOYED",
            income="420000.00",
        ),
        mother=_parent(
            "Teresa Dimaano Obusan",
            attainment="College graduate (BS Commerce)",
            occupation="Co-manages the family store",
            category="SELF_EMPLOYED",
            income="180000.00",
        ),
        siblings=(
            Sibling("Jasmine Obusan", "FEMALE", 2008, attainment="College (1st year)"),
            Sibling("Nico Obusan", "MALE", 2012),
        ),
        sibling_position=1,
        education=(
            ("ELEMENTARY", "Vinzons Pilot Elementary School, Vinzons", "2010-2016", "With Honors"),
            ("JUNIOR_HIGH", "Vinzons National High School, Vinzons", "2016-2020", ""),
            ("SENIOR_HIGH", "Vinzons National High School - Senior High (ABM)", "2020-2022", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 20, 19, 50),
                fields={
                    "major": "Marketing Management",
                    "friends_in_school": "BSBA 3-A marketing majors.",
                    "friends_outside_school": "Former ABM classmates.",
                    "ambition_goal": "To grow the family store online.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Business Statistics",
                    "highest_subjects_grades": "Marketing Research",
                    "inclination_leadership": "Treasurer, Junior Marketing Association",
                    "desired_extracurricular_activities": "Business plan competitions",
                    **_hours(
                        class_="5.50",
                        library="0.50",
                        studying="2.00",
                        rest="7.00",
                        recreation="1.00",
                        other="3.00",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Helping at the store while studying.",
                    "current_fears": "Family business pressure.",
                },
                organizations=(("INSIDE_SCHOOL", "Junior Marketing Association", "Treasurer"),),
                transportation=(("JEEPNEY", "DAILY", "25.00"),),
            ),
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 28, 20, 30),
                fields={
                    "major": "Marketing Management",
                    "friends_in_school": "Irregular classmates across BSBA sections.",
                    "friends_outside_school": "Former ABM classmates.",
                    "ambition_goal": "To finish my degree after my leave of absence.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                    "schedule_satisfied": False,
                    "schedule_satisfaction_reason": "Irregular load spread across five days.",
                    "lowest_subjects_grades": "Operations Management",
                    "highest_subjects_grades": "Consumer Behavior",
                    "desired_extracurricular_activities": "Business plan competitions",
                    **_hours(
                        class_="5.00",
                        library="0.50",
                        studying="2.00",
                        rest="7.00",
                        recreation="0.50",
                        other="4.00",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Completing back subjects after my leave.",
                    "current_fears": "Graduating later than my batch.",
                },
                transportation=(("JEEPNEY", "DAILY", "25.00"),),
            ),
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 10, 18, 55),
                fields={
                    "major": "Marketing Management",
                    "friends_in_school": "A small group of graduating irregular students.",
                    "friends_outside_school": "Former ABM classmates.",
                    "ambition_goal": "To work in marketing, then expand the family store.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Strategic Management",
                    "highest_subjects_grades": "Marketing Research",
                    "desired_extracurricular_activities": "Job fair participation",
                    **_hours(
                        class_="4.00",
                        library="1.00",
                        studying="2.50",
                        rest="7.00",
                        recreation="1.00",
                        other="3.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Final requirements and job applications.",
                    "current_fears": "Finding work related to my course.",
                },
                transportation=(("JEEPNEY", "DAILY", "25.00"),),
            ),
        },
    ),
    RECENT_GRADUATE.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Clyde",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Only child",
            "emergency_contact_name": "Remedios Rosales (mother)",
            "special_interest": "Community radio and video storytelling",
            "special_skills_talents": "Video editing; radio scriptwriting",
            "hobbies_recreation": "Surfing at Bagasbas, making short documentaries",
            "characteristics": "Creative and outgoing; sometimes procrastinates.",
            "immunizations": ["MEASLES_MMR", "BOOSTER"],
            "height": "168 cm",
            "weight": "60 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE"],
            "interests": ["STAGE_ACT", "POEM_WRITING"],
            "intended_work_field": "PUBLIC_SERVICE",
        },
        father=_parent(
            "Joselito Rosales",
            attainment="High school graduate",
            occupation="Fisherman (small boat operator)",
            category="SELF_EMPLOYED",
            income="120000.00",
        ),
        mother=_parent(
            "Remedios Galang Rosales",
            attainment="High school graduate",
            occupation="Market vendor (dried fish)",
            category="SELF_EMPLOYED",
            income="72000.00",
        ),
        siblings=(),
        sibling_position=1,
        education=(
            ("ELEMENTARY", "Bagasbas Elementary School, Daet", "2010-2016", ""),
            ("JUNIOR_HIGH", "Daet National High School, Daet", "2016-2020", ""),
            ("SENIOR_HIGH", "Daet National High School - Senior High (HUMSS)", "2020-2022", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 23, 21, 25),
                fields={
                    "friends_in_school": "DevCom 3-A classmates; campus radio volunteers.",
                    "friends_outside_school": "Local surfing group.",
                    "ambition_goal": "To produce community information programs.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Statistics for Development Communication",
                    "highest_subjects_grades": "Community Broadcasting",
                    "inclination_performing_arts": "Campus theater productions",
                    "desired_extracurricular_activities": "Campus radio",
                    **_hours(
                        class_="6.00",
                        library="1.00",
                        studying="2.00",
                        rest="7.00",
                        recreation="2.00",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Field production costs.",
                    "current_fears": "Delays in my thesis data gathering.",
                },
                organizations=(("INSIDE_SCHOOL", "Campus Radio Guild", "Scriptwriter"),),
                transportation=(("TRICYCLE", "DAILY", "20.00"),),
            ),
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 20, 19, 35),
                fields={
                    "friends_in_school": "Thesis groupmates and campus radio volunteers.",
                    "friends_outside_school": "Local surfing group.",
                    "ambition_goal": "To work in development communication for an LGU or NGO.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Development Communication Research 2",
                    "highest_subjects_grades": "Participatory Video Production",
                    "inclination_performing_arts": "Campus theater productions",
                    "inclination_leadership": "Station manager, Campus Radio Guild",
                    "desired_extracurricular_activities": "Campus radio",
                    **_hours(
                        class_="5.00",
                        library="1.50",
                        studying="2.50",
                        rest="7.00",
                        recreation="1.50",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Finishing my thesis and internship.",
                    "current_fears": "Job hunting after graduation.",
                },
                organizations=(("INSIDE_SCHOOL", "Campus Radio Guild", "Station manager"),),
                transportation=(("TRICYCLE", "DAILY", "20.00"),),
            ),
        },
    ),
    ALUMNI.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Ella",
            "place_of_birth": "Talisay, Camarines Norte",
            "birth_order_among_siblings": "Second of two",
            "emergency_contact_name": "Bernardo Cabrera (father)",
            "special_interest": "Children's literature",
            "special_skills_talents": "Storytelling; lesson materials design",
            "hobbies_recreation": "Reading novels, choir",
            "characteristics": "Patient and articulate.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B", "INFLUENZA"],
            "height": "158 cm",
            "weight": "51 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "JOB_OPPORTUNITIES"],
            "interests": ["SINGING", "DECLAMATION_ORATION"],
            "intended_work_field": "PROFESSIONAL",
        },
        father=_parent(
            "Bernardo Cabrera",
            attainment="College graduate",
            occupation="Senior bookkeeper, rural bank",
            category="PRIVATE_EMPLOYEE",
            income="264000.00",
        ),
        mother=_parent(
            "Liza Moreno Cabrera",
            attainment="College graduate (BSEd)",
            occupation="Public high school teacher",
            category="GOVERNMENT_EMPLOYEE",
            income="348000.00",
        ),
        siblings=(
            Sibling(
                "Carl Cabrera",
                "MALE",
                1999,
                attainment="College graduate",
                occupation="Nurse",
            ),
        ),
        sibling_position=2,
        education=(
            ("ELEMENTARY", "Talisay Central Elementary School, Talisay", "2009-2015", ""),
            ("JUNIOR_HIGH", "Talisay National High School, Talisay", "2015-2019", "With Honors"),
            ("SENIOR_HIGH", "Talisay National High School - Senior High (HUMSS)", "2019-2021", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 19, 20, 0),
                fields={
                    "major": "English",
                    "friends_in_school": "BSED English 4-A classmates.",
                    "friends_outside_school": "Church choir members.",
                    "ambition_goal": "To teach English in a public high school.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 4,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Assessment in Learning 2",
                    "highest_subjects_grades": "Teaching and Assessment of Literature Studies",
                    "inclination_performing_arts": "Choir",
                    "inclination_leadership": "Class mayor",
                    "desired_extracurricular_activities": "Reading program volunteering",
                    **_hours(
                        class_="5.00",
                        library="1.50",
                        studying="2.50",
                        rest="7.00",
                        recreation="1.00",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Practice teaching deployment.",
                    "current_fears": "Handling large classes during practice teaching.",
                },
                organizations=(("INSIDE_SCHOOL", "English Majors' Guild", "Vice President"),),
                transportation=(("JEEPNEY", "DAILY", "30.00"),),
            ),
        },
    ),
    FORMER.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Nate",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Eldest of two",
            "parent_statuses": ["FATHER_OFW"],
            "parent_status_category": "FATHER_OFW",
            "emergency_contact_name": "Mylene Samonte (mother)",
            "special_interest": "Marine life",
            "special_skills_talents": "Swimming; biology illustrations",
            "hobbies_recreation": "Swimming, drawing",
            "characteristics": "Curious and independent.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B"],
            "height": "171 cm",
            "weight": "62 kg",
            "course_first_choice": False,
            "course_choice_reasons": ["PARENT_CHOICE"],
            "interests": ["PLANTING"],
            "intended_work_field": "PROFESSIONAL",
        },
        father=_parent(
            "Ricardo Samonte",
            attainment="College graduate (Marine Transportation)",
            occupation="Seafarer (able seaman)",
            category="OFW",
            income="840000.00",
        ),
        mother=_parent(
            "Mylene Pimentel Samonte",
            attainment="College graduate",
            occupation="",
            category="NONE",
            income=None,
        ),
        siblings=(Sibling("Nina Samonte", "FEMALE", 2013),),
        sibling_position=1,
        education=(
            ("ELEMENTARY", "Mancruz Elementary School, Daet", "2013-2019", ""),
            ("JUNIOR_HIGH", "Daet National High School, Daet", "2019-2023", ""),
            ("SENIOR_HIGH", "Daet National High School - Senior High (STEM)", "2023-2025", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 25, 20, 40),
                fields={
                    "friends_in_school": "A few BS Biology 1-A classmates.",
                    "friends_outside_school": "Senior high friends now in nursing programs.",
                    "ambition_goal": "Still deciding between biology and nursing.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "General Chemistry 2 (Grade 12)",
                    "highest_subjects_grades": "General Biology 2 (Grade 12)",
                    "desired_extracurricular_activities": "Biology Society",
                    **_hours(
                        class_="6.00",
                        library="1.00",
                        studying="2.00",
                        rest="7.50",
                        recreation="1.50",
                        other="0.50",
                    ),
                    "ideal_monthly_allowance": "ABOVE_1000",
                    "current_concerns": "Whether this program is the right fit.",
                    "current_fears": "Disappointing my parents if I shift.",
                },
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
        },
    ),
    ACTIVE_REFERRAL.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Lance",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Second of three",
            "emergency_contact_name": "Gina Bernardo (mother)",
            "special_interest": "Spoken word poetry",
            "special_skills_talents": "Essay writing; guitar",
            "hobbies_recreation": "Writing, online games, guitar",
            "characteristics": "Reserved in class; expressive in writing.",
            "immunizations": ["MEASLES_MMR"],
            "height": "167 cm",
            "weight": "58 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "MINIMAL_COST"],
            "interests": ["POEM_WRITING", "PLAYING_INSTRUMENTS"],
            "intended_work_field": "PROFESSIONAL",
        },
        father=_parent(
            "Rodrigo Bernardo",
            attainment="High school graduate",
            occupation="Jeepney driver",
            category="SELF_EMPLOYED",
            income="132000.00",
        ),
        mother=_parent(
            "Gina Rodrigo Bernardo",
            attainment="High school level",
            occupation="Laundry worker",
            category="LABORER",
            income="48000.00",
        ),
        siblings=(
            Sibling(
                "Marvin Bernardo",
                "MALE",
                2002,
                attainment="Vocational graduate",
                occupation="Welder",
            ),
            Sibling("Kaye Bernardo", "FEMALE", 2012),
        ),
        sibling_position=2,
        education=(
            ("ELEMENTARY", "Awitan Elementary School, Daet", "2012-2018", ""),
            ("JUNIOR_HIGH", "Daet National High School, Daet", "2018-2022", ""),
            ("SENIOR_HIGH", "Daet National High School - Senior High (HUMSS)", "2022-2024", ""),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "LIVING",
        },
        years={
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 27, 22, 10),
                fields={
                    "friends_in_school": "A few BAELS 1-A classmates.",
                    "friends_outside_school": "Online gaming friends.",
                    "ambition_goal": "To become a writer or an English teacher.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Mathematics in the Modern World",
                    "highest_subjects_grades": "Creative Writing (Grade 12)",
                    "desired_extracurricular_activities": "Campus literary folio",
                    **_hours(
                        class_="6.00",
                        library="0.50",
                        studying="1.50",
                        rest="7.00",
                        recreation="3.00",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Speaking in front of the class.",
                    "current_fears": "Recitations.",
                },
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
            # Started in August, never submitted: the roster and coverage show one real draft.
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 24, 21, 30),
                draft=True,
                fields={
                    "friends_in_school": "A few BAELS 2-A classmates.",
                    "ambition_goal": "To become a writer or an English teacher.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 5,
                },
            ),
        },
    ),
    GOOD_MORAL.key: InventoryProfile(
        base={
            **_COMMON_BASE,
            "nickname": "Cess",
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Youngest of two",
            "parent_statuses": ["WIDOW_WIDOWER_LIVING_TOGETHER"],
            "parent_status_category": "WIDOWED",
            "emergency_contact_name": "Rowena Alcantara (mother)",
            "special_interest": "Accounting and small-business bookkeeping",
            "special_skills_talents": "Accounting software; calligraphy",
            "hobbies_recreation": "Calligraphy, K-drama",
            "characteristics": "Diligent and detail-oriented.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B", "BOOSTER"],
            "height": "154 cm",
            "weight": "47 kg",
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "JOB_OPPORTUNITIES"],
            "interests": ["PAINTING"],
            "intended_work_field": "BUSINESS",
        },
        father=_parent(
            "Ernesto Alcantara (deceased, 2019)",
            attainment="College graduate",
            occupation="",
            category="NONE",
            income=None,
        ),
        mother=_parent(
            "Rowena Enriquez Alcantara",
            attainment="College graduate (BS Commerce)",
            occupation="Clerk, provincial government office",
            category="GOVERNMENT_EMPLOYEE",
            income="276000.00",
        ),
        siblings=(
            Sibling(
                "Kristofer Alcantara",
                "MALE",
                2001,
                attainment="College graduate",
                occupation="Office staff, cooperative",
            ),
        ),
        sibling_position=2,
        education=(
            ("ELEMENTARY", "Lag-on Elementary School, Daet", "2011-2017", "With High Honors"),
            (
                "JUNIOR_HIGH",
                "Camarines Norte National High School, Daet",
                "2017-2021",
                "With Honors",
            ),
            (
                "SENIOR_HIGH",
                "Camarines Norte National High School - Senior High (ABM)",
                "2021-2023",
                "With Honors",
            ),
        ),
        support={
            "four_ps_status": "NOT_BENEFICIARY",
            "indigenous_peoples_status": "NOT_MEMBER",
            "mother_life_status": "LIVING",
            "father_life_status": "DECEASED",
        },
        years={
            "2024-2025": InventoryYear(
                saved_at=(2024, 8, 21, 19, 30),
                fields={
                    "friends_in_school": "BSA 1-A classmates.",
                    "friends_outside_school": "Senior high ABM friends.",
                    "ambition_goal": "To become a Certified Public Accountant.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Physical Education 1",
                    "highest_subjects_grades": "Financial Accounting and Reporting",
                    "inclination_leadership": "Class treasurer",
                    "desired_extracurricular_activities": "Junior Philippine Institute of "
                    "Accountants chapter",
                    **_hours(
                        class_="6.00",
                        library="1.50",
                        studying="3.00",
                        rest="7.00",
                        recreation="0.50",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Retention grade requirements.",
                    "current_fears": "Not meeting the program's retention policy.",
                },
                organizations=(("INSIDE_SCHOOL", "Accountancy Students' Society", "Member"),),
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
            "2025-2026": InventoryYear(
                saved_at=(2025, 8, 22, 20, 50),
                fields={
                    "friends_in_school": "BSA 2-A study group.",
                    "friends_outside_school": "Senior high ABM friends.",
                    "ambition_goal": "To pass the CPA Licensure Examination.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Law on Obligations and Contracts",
                    "highest_subjects_grades": "Intermediate Accounting 1",
                    "inclination_leadership": "Auditor, Accountancy Students' Society",
                    "desired_extracurricular_activities": "Accounting quiz bowl",
                    **_hours(
                        class_="6.00",
                        library="2.00",
                        studying="3.00",
                        rest="6.50",
                        recreation="0.50",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Scholarship requirements.",
                    "current_fears": "Heavy accounting load.",
                },
                organizations=(("INSIDE_SCHOOL", "Accountancy Students' Society", "Auditor"),),
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
            "2026-2027": InventoryYear(
                saved_at=(2026, 8, 13, 20, 25),
                fields={
                    "friends_in_school": "BSA 3-A study group.",
                    "friends_outside_school": "Senior high ABM friends.",
                    "ambition_goal": "To pass the CPA Licensure Examination.",
                    "living_arrangement": "OWN_HOUSE",
                    "present_place_people_count": 3,
                    "schedule_satisfied": True,
                    "lowest_subjects_grades": "Income Taxation",
                    "highest_subjects_grades": "Intermediate Accounting 3",
                    "inclination_leadership": "Vice President, Accountancy Students' Society",
                    "desired_extracurricular_activities": "Scholarship mentoring",
                    **_hours(
                        class_="6.00",
                        library="2.00",
                        studying="3.00",
                        rest="6.50",
                        recreation="0.50",
                        other="1.00",
                    ),
                    "ideal_monthly_allowance": "FROM_500_TO_1000",
                    "current_concerns": "Scholarship renewal documents.",
                    "current_fears": "The qualifying examination next year.",
                },
                organizations=(
                    ("INSIDE_SCHOOL", "Accountancy Students' Society", "Vice President"),
                ),
                transportation=(("TRICYCLE", "DAILY", "15.00"),),
            ),
        },
    ),
}


def _age_on(birth_year: int, on: date, *, month: int = 6, day: int = 15) -> int:
    return on.year - birth_year - ((on.month, on.day) < (month, day))


def _school_stage(age: int) -> str:
    if age < 6:
        return "Not yet in school"
    if age <= 17:
        return f"Grade {min(age - 5, 12)}"
    return "College"


def _sibling_rows(
    persona: StudentPersona,
    profile: InventoryProfile,
    *,
    year_level: int,
    as_of: date,
) -> list[dict[str, object]]:
    assert persona.date_of_birth is not None
    self_row = {
        "name": persona.full_name,
        "sex": persona.sex,
        "age": _age_on(
            persona.date_of_birth.year,
            as_of,
            month=persona.date_of_birth.month,
            day=persona.date_of_birth.day,
        ),
        "educational_attainment": f"College ({ORDINALS[year_level]} year)",
        "occupation": "Student",
        "is_self": True,
    }
    others = [
        {
            "name": sibling.name,
            "sex": sibling.sex,
            "age": _age_on(sibling.birth_year, as_of),
            "educational_attainment": sibling.attainment
            or _school_stage(_age_on(sibling.birth_year, as_of)),
            "occupation": sibling.occupation or "Student",
            "is_self": False,
        }
        for sibling in profile.siblings
    ]
    ordered = [*others[: profile.sibling_position - 1], self_row]
    ordered.extend(others[profile.sibling_position - 1 :])
    return [{"sort_order": index, **row} for index, row in enumerate(ordered, start=1)]


def inventory_values(
    persona: StudentPersona,
    academic_year: str,
    *,
    email: str,
) -> dict[str, object]:
    """Build ``replace_current_inventory`` values (without ``program_id``) for one year."""

    profile = PROFILES[persona.key]
    year = profile.years[academic_year]
    year_level = dict(persona.year_levels)[academic_year]
    as_of = date(*year.saved_at[:3])
    if year.draft:
        return {
            "full_name_snapshot": persona.full_name,
            "date_of_birth": persona.date_of_birth,
            "sex": persona.sex,
            "email_address": email,
            "current_address": persona.home_address,
            "permanent_address": persona.home_address,
            "year_level": year_level,
            **year.fields,
            "family_members": [],
            "siblings": [],
            "education_entries": [],
            "organization_memberships": [],
            "transportation_entries": [],
            "geographic_locations": [],
        }

    boarding = year.fields.get("living_arrangement") == "BOARDING_HOUSE"
    current_address = str(year.fields["boarding_address"]) if boarding else persona.home_address
    return {
        **profile.base,
        **year.fields,
        "full_name_snapshot": persona.full_name,
        "date_of_birth": persona.date_of_birth,
        "sex": persona.sex,
        "email_address": email,
        "current_address": current_address,
        "permanent_address": persona.home_address,
        "year_level": year_level,
        "family_members": [
            {"kind": "FATHER", **profile.father},
            {"kind": "MOTHER", **profile.mother},
        ],
        "siblings": _sibling_rows(persona, profile, year_level=year_level, as_of=as_of),
        "education_entries": [
            {
                "level": level,
                "school_attended_address": school,
                "inclusive_years": years,
                "awards_received": awards,
            }
            for level, school, years, awards in profile.education
        ],
        "organization_memberships": [
            {
                "scope": scope,
                "sort_order": index,
                "organization_name": name,
                "position_title": position,
            }
            for index, (scope, name, position) in enumerate(year.organizations, start=1)
        ],
        "transportation_entries": [
            {"mode": mode, "frequency_category": frequency, "fare": Decimal(fare)}
            for mode, frequency, fare in year.transportation
        ],
        "geographic_locations": [{"kind": "CURRENT", "not_specified": True}],
        "support_profile": dict(profile.support),
    }


def inventory_years(persona: StudentPersona) -> tuple[str, ...]:
    profile = PROFILES.get(persona.key)
    return tuple(profile.years) if profile is not None else ()


def inventory_year(persona: StudentPersona, academic_year: str) -> InventoryYear:
    return PROFILES[persona.key].years[academic_year]


def _validate() -> None:
    from .cast import STUDENTS

    for persona in STUDENTS:
        declared = {label for label, _ in persona.year_levels}
        profile = PROFILES.get(persona.key)
        if profile is None:
            if declared:
                raise RuntimeError(f"{persona.key} declares Inventories but has no profile")
            continue
        if set(profile.years) != declared:
            raise RuntimeError(f"{persona.key} Inventory years do not match its year levels")


_validate()


__all__ = [
    "InventoryYear",
    "PROFILES",
    "inventory_values",
    "inventory_year",
    "inventory_years",
]
