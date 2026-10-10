"""Answer fixtures for the lightweight cohort, using the existing Inventory value builder."""

from .inventory_fixtures import (
    _COMMON_BASE,
    InventoryProfile,
    InventoryYear,
    Sibling,
    _hours,
    _parent,
)
from .population import POPULATION

INTERESTS = (
    ("Reading novels", "Community library", "READING", "Public service"),
    ("Cycling and fitness", "Campus sports club", "SPORTS", "A stable local career"),
    ("Drawing and design", "Student arts circle", "PAINTING", "Creative work"),
    ("Music and singing", "Campus choir", "SINGING", "Teaching and community work"),
)


def population_profiles():
    profiles = {}
    for index, member in enumerate(POPULATION, 1):
        p = member.persona
        if member.inventory_state == "MISSING":
            continue
        hobby, organization, _interest, ambition = INTERESTS[(index - 1) % len(INTERESTS)]
        background = member.background
        base = {
            **_COMMON_BASE,
            "nickname": p.first_name,
            "place_of_birth": "Daet, Camarines Norte",
            "birth_order_among_siblings": "Eldest of three" if index % 3 else "Only child",
            "emergency_contact_name": f"Teresa {p.last_name}",
            "special_interest": hobby,
            "hobbies_recreation": hobby,
            "special_skills_talents": "Planning group activities"
            if index % 2
            else "Digital editing",
            "characteristics": "I work well with classmates and keep a weekly study plan.",
            "immunizations": ["MEASLES_MMR", "HEPATITIS_B"],
            "course_first_choice": True,
            "course_choice_reasons": ["INTEREST_APTITUDE", "JOB_OPPORTUNITIES"],
            "pwd_status": "PWD" if background == "pwd" else "NON_PWD",
        }
        if background == "pwd":
            base["physical_disadvantage"] = "Uses a mobility aid; accessible classroom routes help."
        if background == "deceased_parent":
            base.update(
                parent_status_category="WIDOWED", parent_statuses=["WIDOW_WIDOWER_LIVING_TOGETHER"]
            )
        if background == "guardian":
            base.update(
                guardian_name=f"Teresa {p.last_name}",
                guardian_relationship="Aunt",
                guardian_address=p.home_address,
            )
        single_income = background in {"guardian", "deceased_parent", "four_ps"}
        father = _parent(
            f"Roberto {p.last_name}",
            attainment="High school graduate",
            occupation="None" if single_income else "Maintenance technician",
            category="NONE" if single_income else "PRIVATE_EMPLOYEE",
            income="180000.00" if not single_income else None,
        )
        mother = _parent(
            f"Teresa {p.last_name}",
            attainment="College graduate",
            occupation="Market vendor" if single_income else "Office clerk",
            category="SELF_EMPLOYED" if single_income else "PRIVATE_EMPLOYEE",
            income="96000.00" if single_income else "192000.00",
        )
        years = {}
        for label, _year_level in p.year_levels:
            draft = label == "2026-2027" and member.inventory_state != "SUBMITTED"
            fields = {
                "friends_in_school": "Blockmates and the campus study group.",
                "friends_outside_school": "Neighbors and former classmates.",
                "ambition_goal": ambition,
                "living_arrangement": "WITH_RELATIVES" if background == "guardian" else "OWN_HOUSE",
                "present_place_people_count": 4 if index % 3 else 3,
                "schedule_satisfied": background != "working",
                "schedule_satisfaction_reason": "Balancing classes with weekend shop shifts."
                if background == "working"
                else "",
                "lowest_subjects_grades": "Statistics: 2.25",
                "highest_subjects_grades": "Communication: 1.50",
                "desired_extracurricular_activities": organization,
                "ideal_monthly_allowance": "ABOVE_1000",
                "current_concerns": {
                    "working": "I work weekend shifts to contribute to tuition and transport.",
                    "commute": "Two rides take about ninety minutes each way.",
                    "guardian": "My aunt supports my school expenses while my parents work away.",
                    "deceased_parent": "Adjusting family responsibilities after my father's death.",
                }.get(background, "No major concern; keeping a regular study routine."),
                "current_fears": "None at present."
                if background == "ordinary"
                else "Maintaining attendance while managing household responsibilities.",
                **_hours(
                    class_="6.00",
                    library="1.00",
                    studying="2.00",
                    rest="8.00",
                    recreation="2.00",
                    other="3.00",
                ),
            }
            if draft and member.inventory_state == "EARLY":
                fields = {"nickname": p.first_name}
            elif draft and member.inventory_state == "PARTIAL":
                fields = {
                    key: fields[key]
                    for key in ("friends_in_school", "living_arrangement", "ambition_goal")
                }
            years[label] = InventoryYear(
                saved_at=(int(label[:4]), 8, 14 + index % 7, 18, index % 60),
                fields=fields,
                organizations=(("INSIDE_SCHOOL", organization, "Member"),) if index % 3 else (),
                transportation=(("BUS", "DAILY", "65.00"), ("TRICYCLE", "DAILY", "20.00"))
                if background == "commute"
                else (("JEEPNEY", "DAILY", "20.00"),),
                draft=draft,
            )
        admission = int(p.year_levels[-1][0][:4]) - p.year_levels[-1][1] + 1
        profiles[p.key] = InventoryProfile(
            base=base,
            father=father,
            mother=mother,
            siblings=()
            if index % 3 == 0
            else (
                Sibling(f"Jaime {p.last_name}", "MALE", 2012),
                Sibling(f"Liza {p.last_name}", "FEMALE", 2015),
            ),
            sibling_position=1,
            education=(
                (
                    "ELEMENTARY",
                    "Demo community elementary school, Daet",
                    f"{admission - 12}-{admission - 6}",
                    "",
                ),
                (
                    "JUNIOR_HIGH",
                    "Demo national high school, Daet",
                    f"{admission - 6}-{admission - 2}",
                    "",
                ),
                (
                    "SENIOR_HIGH",
                    "Demo senior high school, Daet",
                    f"{admission - 2}-{admission}",
                    "With Honors" if index % 4 == 0 else "",
                ),
            ),
            support={
                "four_ps_status": "BENEFICIARY" if background == "four_ps" else "NOT_BENEFICIARY",
                "indigenous_peoples_status": "MEMBER"
                if background == "indigenous"
                else "NOT_MEMBER",
                "mother_life_status": "LIVING",
                "father_life_status": "DECEASED" if background == "deceased_parent" else "LIVING",
            },
            years=years,
        )
    return profiles
