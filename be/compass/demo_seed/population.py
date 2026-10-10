"""Source-controlled lightweight cohort. Ordinal identity and composition never depend on RNG.

Rows declare name, catalog program, year, Inventory state/depth, and background variation.
Year is enrollment intent; missing Inventory cannot supply Program/year to Inventory reports.
"""

from dataclasses import dataclass, replace
from datetime import date

from .personas import Lifecycle, StudentPersona

PROGRAMS = (
    ("MAIN", "CCMS", "BSIT"),
    ("MAIN", "CAS", "BSPSYCH"),
    ("MAIN", "CBPA", "BSBA"),
    ("ABANO", "COED", "BSED"),
    ("MAIN", "CCMS", "BSIS"),
    ("MAIN", "CAS", "BSBIOL"),
    ("MAIN", "CBPA", "BSA"),
    ("ABANO", "COED", "BEED"),
)
# 38 CURRENT: 28 submissions, 7 drafts with three depths, 3 missing.
# Six graduates (five submitted Tracers and one not started); two former Students.
CURRENT_ROWS = (
    ("Althea", "Reyes", 0, 1, "SUBMITTED", "ordinary"),
    ("Marco", "Dizon", 1, 2, "SUBMITTED", "ordinary"),
    ("Camille", "Santos", 2, 3, "SUBMITTED", "ordinary"),
    ("Paolo", "Mercado", 3, 4, "SUBMITTED", "ordinary"),
    ("Danica", "Flores", 4, 2, "SUBMITTED", "working"),
    ("Luis", "Torres", 5, 3, "SUBMITTED", "ordinary"),
    ("Jasmine", "Mendoza", 6, 4, "SUBMITTED", "ordinary"),
    ("Rafael", "Lim", 7, 1, "SUBMITTED", "guardian"),
    ("Nicole", "Cruz", 0, 2, "SUBMITTED", "four_ps"),
    ("Gabriel", "Vega", 1, 3, "SUBMITTED", "ordinary"),
    ("Andrea", "Lopez", 2, 4, "SUBMITTED", "commute"),
    ("Miguel", "Salcedo", 3, 1, "SUBMITTED", "ordinary"),
    ("Sofia", "Tan", 4, 3, "SUBMITTED", "pwd"),
    ("Daniel", "Roxas", 5, 4, "SUBMITTED", "ordinary"),
    ("Isabel", "Lazaro", 6, 1, "SUBMITTED", "ordinary"),
    ("Ethan", "Valdez", 7, 2, "SUBMITTED", "indigenous"),
    ("Bianca", "Marquez", 0, 4, "SUBMITTED", "ordinary"),
    ("Joshua", "Velasco", 1, 1, "SUBMITTED", "ordinary"),
    ("Claire", "Tolentino", 2, 2, "SUBMITTED", "deceased_parent"),
    ("Francis", "Natividad", 3, 3, "SUBMITTED", "ordinary"),
    ("Patricia", "Castro", 4, 1, "SUBMITTED", "ordinary"),
    ("Aaron", "Buenaventura", 5, 2, "SUBMITTED", "ordinary"),
    ("Mariel", "Panganiban", 6, 3, "SUBMITTED", "four_ps"),
    ("Vincent", "Alvarez", 7, 4, "SUBMITTED", "ordinary"),
    ("Leah", "Ignacio", 0, 1, "SUBMITTED", "ordinary"),
    ("Adrian", "De Leon", 1, 2, "SUBMITTED", "working"),
    ("Chloe", "Villanueva", 2, 3, "SUBMITTED", "ordinary"),
    ("Noel", "Gonzales", 3, 4, "SUBMITTED", "ordinary"),
    ("Katrina", "Basilio", 4, 1, "EARLY", "ordinary"),
    ("Patrick", "Bernal", 5, 2, "PARTIAL", "commute"),
    ("Angelica", "Cordero", 6, 3, "NEARLY", "guardian"),
    ("Joseph", "Del Rosario", 7, 4, "EARLY", "ordinary"),
    ("Diana", "Estrella", 0, 2, "PARTIAL", "ordinary"),
    ("Mark", "Fajardo", 1, 3, "NEARLY", "ordinary"),
    ("Vanessa", "Hilario", 2, 4, "NEARLY", "ordinary"),
    ("Ryan", "Jimenez", 3, 1, "MISSING", "ordinary"),
    ("Elena", "Lucero", 4, 2, "MISSING", "ordinary"),
    ("Oliver", "Montes", 5, 3, "MISSING", "ordinary"),
)
GRADUATE_ROWS = (
    ("Angela", "Navarro", 0, "related"),
    ("Christian", "Ortega", 1, "unrelated"),
    ("Irene", "Padilla", 2, "self_employed"),
    ("Martin", "Quintana", 3, "job_seeking"),
    ("Rica", "Robles", 4, "further_study"),
    ("Samuel", "Tuazon", 5, "missing"),
)
FORMER_ROWS = (("Julia", "Umali", 6), ("Warren", "Yap", 7))


@dataclass(frozen=True)
class PopulationMember:
    persona: StudentPersona
    inventory_state: str
    background: str
    tracer: str = "missing"


def _persona(index, first, last, program_index, year, lifecycle=Lifecycle.CURRENT):
    campus, college, program = PROGRAMS[program_index]
    label = "2026-2027" if lifecycle == Lifecycle.CURRENT else "2025-2026"
    return StudentPersona(
        key=f"population_{index:02d}",
        label=f"Population Student {index:02d}",
        institutional_id=f"DEMO-2026-{200 + index:04d}",
        email_local_part=f"demo-population{index:02d}",
        first_name=first,
        middle_name="",
        last_name=last,
        sex="FEMALE" if index % 2 else "MALE",
        date_of_birth=date(2009 - year, 1 + index % 12, 1 + index % 27),
        campus_code=campus,
        college_code=college,
        program_code=program,
        lifecycle=lifecycle,
        affiliated=lifecycle == Lifecycle.CURRENT,
        home_address=f"Demo household {index}, Barangay Bagasbas, Daet, Camarines Norte",
        year_levels=((label, year),),
    )


_members = [
    PopulationMember(_persona(i, first, last, program, year), state, background)
    for i, (first, last, program, year, state, background) in enumerate(CURRENT_ROWS, 1)
]
_members = [
    replace(member, persona=replace(member.persona, year_levels=()))
    if member.inventory_state == "MISSING"
    else member
    for member in _members
]
# Three older-year current Students also have a previous-year Inventory. The upgrade enters
# these missing histories through the current-year service in a bounded transaction.

for index in (5, 10, 15):
    member = _members[index]
    persona = member.persona
    year = dict(persona.year_levels)["2026-2027"]
    _members[index] = replace(
        member,
        persona=replace(persona, year_levels=(("2025-2026", year - 1), *persona.year_levels)),
    )
for index, (first, last, program, tracer) in enumerate(GRADUATE_ROWS, 39):
    _members.append(
        PopulationMember(
            _persona(index, first, last, program, 4, Lifecycle.GRADUATED),
            "SUBMITTED",
            "ordinary",
            tracer,
        )
    )
for index, (first, last, program) in enumerate(FORMER_ROWS, 45):
    _members.append(
        PopulationMember(
            _persona(index, first, last, program, 2, Lifecycle.FORMER), "SUBMITTED", "ordinary"
        )
    )
POPULATION = tuple(_members)
POPULATION_STUDENTS = tuple(member.persona for member in POPULATION)
MEMBERS_BY_KEY = {member.persona.key: member for member in POPULATION}
