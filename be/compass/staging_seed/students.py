"""The synthetic Student population of Staging Dataset v1 (100 Students by default).

Three groups, all source-controlled and deterministic (no RNG):

* RICH_SCENARIO (11): multi-domain stories across three Academic Years.
* ACTION_READY (24): one clear, evaluator-owned pending action each, so two evaluators never
  need the same Student.
* BACKGROUND (65): a mostly quiet population that gives reports, rosters and filters realistic
  variety across every campus. One background account is disabled for negative tests.

Every name, ``STG-S-…`` identifier and address is fictional. Programs come from the canonical
Organization catalog; nothing here invents an academic option.
"""

from __future__ import annotations

from datetime import date

from .identities import AuthPlan, Lifecycle, StudentGroup, StudentSpec, Suitability

CURRENT_YEAR = "2026-2027"
PREVIOUS_YEAR = "2025-2026"

TOWNS = {
    "MAIN": "Daet",
    "ABANO": "Daet",
    "MERCEDES": "Mercedes",
    "LABO": "Labo",
    "PANGANIBAN": "Jose Panganiban",
    "ENTIENZA": "Santa Elena",
}
COLLEGE_OF_PROGRAM = {
    "BSIT": ("MAIN", "CCMS"),
    "BSIS": ("MAIN", "CCMS"),
    "BSPSYCH": ("MAIN", "CAS"),
    "BSBIOL": ("MAIN", "CAS"),
    "BSDEVCOM": ("MAIN", "CAS"),
    "BSAM": ("MAIN", "CAS"),
    "BAELS": ("MAIN", "CAS"),
    "BASOC": ("MAIN", "CAS"),
    "BSBA": ("MAIN", "CBPA"),
    "BSA": ("MAIN", "CBPA"),
    "BSHM": ("MAIN", "CBPA"),
    "BPA": ("MAIN", "CBPA"),
    "BSOA": ("MAIN", "CBPA"),
    "BSENTREP": ("MAIN", "CBPA"),
    "BSCE": ("MAIN", "COENG"),
    "BSEE": ("MAIN", "COENG"),
    "BSME": ("MAIN", "COENG"),
    "BSED": ("ABANO", "COED"),
    "BEED": ("ABANO", "COED"),
    "BTLED": ("ABANO", "COED"),
    "BPED": ("ABANO", "COED"),
    "BSF": ("MERCEDES", "CFAST"),
    "BSAGRI": ("LABO", "CANR"),
    "BSES": ("LABO", "CANR"),
    "BSABE": ("LABO", "CANR"),
    "BTVTED": ("PANGANIBAN", "COTT"),
    "BSINDTECH": ("PANGANIBAN", "COTT"),
    "ENT-BSED": ("ENTIENZA", "ENTIENZA"),
    "ENT-BEED": ("ENTIENZA", "ENTIENZA"),
    "ENT-BSENTREP": ("ENTIENZA", "ENTIENZA"),
}


def _placement(program: str) -> tuple[str, str, str]:
    campus, college = COLLEGE_OF_PROGRAM[program]
    return campus, college, program.removeprefix("ENT-")


# --- Rich scenario Students --------------------------------------------------------------------

FIRST_YEAR = StudentSpec(
    key="first_year",
    label="Current first-year Student (upcoming online session)",
    institutional_id="STG-S-0001",
    email_local_part="stg-student-first-year",
    first_name="Bea Kristel",
    middle_name="Lagman",
    last_name="Abad",
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2008, 3, 14),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIT",
    home_address="Purok 2, Barangay Gahonon, Daet, Camarines Norte",
    year_levels=((CURRENT_YEAR, 1),),
    summary=(
        "Submitted Inventory (4Ps household), a cancelled booking and an upcoming ONLINE "
        "Counseling Appointment whose Routine Interview intake is a draft."
    ),
)
SECOND_YEAR = StudentSpec(
    key="second_year",
    label="Current second-year Student (completed counseling)",
    institutional_id="STG-S-0002",
    email_local_part="stg-student-second-year",
    first_name="Mikaela Joy",
    middle_name="Ramos",
    last_name="Serrano",
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2007, 6, 2),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSPSYCH",
    home_address="Purok 5, Barangay Camambugan, Daet, Camarines Norte",
    year_levels=((PREVIOUS_YEAR, 1), (CURRENT_YEAR, 2)),
    summary=(
        "Two annual Inventories; completed session with finalized Routine evaluation and a "
        "published Shared Summary; scheduled follow-up; a withdrawn Call Slip; feedback."
    ),
)
REFERRED = StudentSpec(
    key="referred",
    label="Current third-year Student (referred)",
    institutional_id="STG-S-0003",
    email_local_part="stg-student-referred",
    first_name="Jerome Andres",
    middle_name="Salvador",
    last_name="Dela Paz",
    group=StudentGroup.RICH,
    sex="MALE",
    date_of_birth=date(2005, 11, 20),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSHM",
    home_address="Sitio Malatap, Barangay Tulay na Lupa, Labo, Camarines Norte",
    year_levels=(("2024-2025", 1), (PREVIOUS_YEAR, 2), (CURRENT_YEAR, 3)),
    summary=(
        "Program Chair referral (plus a voided duplicate), Call Slip interview, REFERRED "
        "Encounter, Routine Interview awaiting evaluation, published follow-up summary."
    ),
)
FOURTH_YEAR = StudentSpec(
    key="fourth_year",
    label="Current fourth-year Student (walk-in and no-show)",
    institutional_id="STG-S-0004",
    email_local_part="stg-student-fourth-year",
    first_name="Kevin Luis",
    middle_name="Navales",
    last_name="Pardo",
    group=StudentGroup.RICH,
    sex="MALE",
    date_of_birth=date(2004, 9, 8),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIS",
    home_address="Purok 3, Barangay Talobatib, Labo, Camarines Norte",
    year_levels=(("2024-2025", 2), (PREVIOUS_YEAR, 3), (CURRENT_YEAR, 4)),
    summary=(
        "Last year's referral by departed staff, a no-show, a walk-in Encounter with a "
        "finalized Routine Interview and an unpublished Shared Summary draft, a follow-up."
    ),
)
GRADUATING = StudentSpec(
    key="graduating",
    label="Current graduating Student (Exit Interview draft)",
    institutional_id="STG-S-0005",
    email_local_part="stg-student-graduating",
    first_name="Rosalie Mae",
    middle_name="Dimaano",
    last_name="Obusan",
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2003, 12, 1),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSBA",
    home_address="Purok 1, Barangay Poblacion, Vinzons, Camarines Norte",
    # A one-semester leave of absence moved graduation to the end of this first semester.
    year_levels=(("2024-2025", 3), (PREVIOUS_YEAR, 4), (CURRENT_YEAR, 5)),
    summary=(
        "Delayed final year: Exit Interview draft, pending Good Moral request and a career "
        "consultation booked with the Head Guidance Counselor."
    ),
)
RECENT_GRADUATE = StudentSpec(
    key="recent_graduate",
    label="Recent graduate (June 2026)",
    institutional_id="STG-S-0006",
    email_local_part="stg-student-recent-graduate",
    first_name="Adrian Clyde",
    middle_name="Galang",
    last_name="Rosales",
    group=StudentGroup.RICH,
    sex="MALE",
    date_of_birth=date(2004, 1, 17),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSDEVCOM",
    lifecycle=Lifecycle.GRADUATED,
    affiliated=False,
    home_address="Purok 4, Barangay Bagasbas, Daet, Camarines Norte",
    year_levels=(("2024-2025", 3), (PREVIOUS_YEAR, 4)),
    summary="Historical Inventories and Exit Interview, issued graduate certificate, Tracer draft.",
    limitations="Graduated: no current College affiliation or current-year Inventory.",
)
ALUMNI = StudentSpec(
    key="alumni",
    label="Alumna (June 2025)",
    institutional_id="STG-S-0007",
    email_local_part="stg-student-alumni",
    first_name="Ellaine Grace",
    middle_name="Moreno",
    last_name="Cabrera",
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2003, 4, 25),
    campus_code="ABANO",
    college_code="COED",
    program_code="BSED",
    lifecycle=Lifecycle.GRADUATED,
    affiliated=False,
    home_address="Purok 6, Barangay San Isidro, Talisay, Camarines Norte",
    year_levels=(("2024-2025", 4),),
    summary="Historical Inventory and Exit Interview, submitted Tracer, pending graduate request.",
    limitations="Graduated: no current College affiliation or current-year Inventory.",
)
FORMER = StudentSpec(
    key="former",
    label="Former Student (transferred out)",
    institutional_id="STG-S-0008",
    email_local_part="stg-student-former",
    first_name="Nathaniel Jose",
    middle_name="Pimentel",
    last_name="Samonte",
    group=StudentGroup.RICH,
    sex="MALE",
    date_of_birth=date(2007, 2, 9),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSBIOL",
    lifecycle=Lifecycle.FORMER,
    affiliated=False,
    home_address="Purok 2, Barangay Mancruz, Daet, Camarines Norte",
    year_levels=((PREVIOUS_YEAR, 1),),
    summary="One historical Inventory, then FORMER: a working account with limited workflows.",
    limitations="Former Student: excluded from current operational pickers and rosters.",
)
ONBOARDING = StudentSpec(
    key="onboarding",
    label="Onboarding Student (never signed in)",
    institutional_id="STG-S-0009",
    email_local_part="stg-student-onboarding",
    first_name="Trisha Anne",
    middle_name="Villafuerte",
    last_name="Llamas",
    auth=AuthPlan.ONBOARDING,
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2008, 7, 30),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIT",
    home_address="",
    enrolled_year_level=1,
    summary="Provisioned account that has never signed in: first-time Password Access onboarding.",
    limitations=(
        "Needs an operator-controlled mailbox (STAGING_SEED_ONBOARDING_EMAIL) for the "
        "one-time code; no credential is issued for it."
    ),
)
ACTIVE_REFERRAL = StudentSpec(
    key="active_referral",
    label="Current second-year Student (active referral)",
    institutional_id="STG-S-0010",
    email_local_part="stg-student-active-referral",
    first_name="Lance Emmanuel",
    middle_name="Rodrigo",
    last_name="Bernardo",
    group=StudentGroup.RICH,
    sex="MALE",
    date_of_birth=date(2006, 10, 3),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BAELS",
    home_address="Purok 7, Barangay Awitan, Daet, Camarines Norte",
    year_levels=((PREVIOUS_YEAR, 1), (CURRENT_YEAR, 2)),
    summary="Inventory draft, a new adviser referral and a Call Slip issued live by gss_a.",
)
GOOD_MORAL = StudentSpec(
    key="good_moral",
    label="Current third-year Student (issued certificate)",
    institutional_id="STG-S-0011",
    email_local_part="stg-student-good-moral",
    first_name="Princess Joy",
    middle_name="Enriquez",
    last_name="Alcantara",
    group=StudentGroup.RICH,
    sex="FEMALE",
    date_of_birth=date(2005, 5, 11),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSA",
    home_address="Purok 3, Barangay Lag-on, Daet, Camarines Norte",
    year_levels=(("2024-2025", 1), (PREVIOUS_YEAR, 2), (CURRENT_YEAR, 3)),
    summary="Issued, printable current-Student Good Moral certificate and a cancelled duplicate.",
)

RICH_STUDENTS = (
    FIRST_YEAR,
    SECOND_YEAR,
    REFERRED,
    FOURTH_YEAR,
    GRADUATING,
    RECENT_GRADUATE,
    ALUMNI,
    FORMER,
    ONBOARDING,
    ACTIVE_REFERRAL,
    GOOD_MORAL,
)

# --- Action-ready Students ---------------------------------------------------------------------
# (first, last, sex, program, year, inventory state, background, lifecycle, label, summary)
ACTION_READY_ROWS = (
    (
        "Hannah",
        "Aguilar",
        "FEMALE",
        "BSIT",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Ready to book a first Counseling session",
        "Submitted Inventory and no Appointment: books Counseling with counselor_a.",
    ),
    (
        "Ronald",
        "Cayabyab",
        "MALE",
        "BSA",
        1,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Ready to book a first Counseling session",
        "Submitted Inventory and no Appointment: books Counseling with counselor_b.",
    ),
    (
        "Kimberly",
        "Dumalo",
        "FEMALE",
        "BSPSYCH",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Upcoming in-person session to reschedule",
        "Upcoming in-person Appointment with counselor_a that can be rescheduled.",
    ),
    (
        "Jericho",
        "Espiritu",
        "MALE",
        "BEED",
        2,
        "SUBMITTED",
        "commute",
        Lifecycle.CURRENT,
        "Upcoming in-person session to cancel",
        "Upcoming in-person Appointment with counselor_b that can be cancelled.",
    ),
    (
        "Lovely",
        "Fajardo",
        "FEMALE",
        "BSIS",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Upcoming online session (E-Counseling consent)",
        "Upcoming ONLINE Appointment with counselor_a; no consent requested yet.",
    ),
    (
        "Marvin",
        "Gatchalian",
        "MALE",
        "BSBA",
        2,
        "SUBMITTED",
        "working",
        Lifecycle.CURRENT,
        "Upcoming online session (E-Counseling consent)",
        "Upcoming ONLINE Appointment with counselor_b; no consent requested yet.",
    ),
    (
        "Nicole",
        "Herrera",
        "FEMALE",
        "BSCE",
        1,
        "NEARLY",
        "ordinary",
        Lifecycle.CURRENT,
        "Individual Inventory nearly complete",
        "Current Inventory saved as a nearly complete draft, ready to finish and submit.",
    ),
    (
        "Oscar",
        "Ilustre",
        "MALE",
        "BSAGRI",
        1,
        "MISSING",
        "ordinary",
        Lifecycle.CURRENT,
        "No Individual Inventory yet",
        "No current Inventory: starts one; Counseling booking requires it first.",
    ),
    (
        "Pia",
        "Javier",
        "FEMALE",
        "BAELS",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Routine Interview intake to prepare",
        "Upcoming Appointment with counselor_a and a Routine Interview intake draft.",
    ),
    (
        "Quentin",
        "Katigbak",
        "MALE",
        "BSHM",
        4,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Graduating: Exit Interview open",
        "Graduating; Exit Interview opportunity opened by Head Guidance, not started.",
    ),
    (
        "Rhea",
        "Lacson",
        "FEMALE",
        "BSIT",
        4,
        "SUBMITTED",
        "guardian",
        Lifecycle.CURRENT,
        "Graduating: Exit Interview open",
        "Graduating; Exit Interview opportunity opened by Head Guidance, not started.",
    ),
    (
        "Samantha",
        "Macaraeg",
        "FEMALE",
        "BSBIOL",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Eligible to request a Good Moral certificate",
        "Submitted Inventory and no Good Moral request: requests a current-Student certificate.",
    ),
    (
        "Tristan",
        "Nolasco",
        "MALE",
        "BSOA",
        4,
        "SUBMITTED",
        "ordinary",
        Lifecycle.GRADUATED,
        "Graduate: Graduate Tracer not started",
        "Graduated June 2026 with Exit Interview; Graduate Tracer not started.",
    ),
    (
        "Ursula",
        "Panlilio",
        "FEMALE",
        "BSIS",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Unread Guidance Message",
        "counselor_a started the Appointment conversation; the Student has not read it.",
    ),
    (
        "Victor",
        "Quiambao",
        "MALE",
        "BSED",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Published Shared Summary to read",
        "Completed session with counselor_b; published Shared Summary and feedback invitation.",
    ),
    (
        "Wendy",
        "Rosario",
        "FEMALE",
        "BSES",
        2,
        "SUBMITTED",
        "four_ps",
        Lifecycle.CURRENT,
        "Call Slip issued",
        "Referral and a Call Slip issued live by counselor_c for an interview this week.",
    ),
    (
        "Xavier",
        "Sabado",
        "MALE",
        "BPA",
        4,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Good Moral request awaiting processing",
        "Good Moral request REQUESTED: counselor_b records the receipt, prepares and issues.",
    ),
    (
        "Yolanda",
        "Tamayo",
        "FEMALE",
        "BSIT",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Good Moral request ready for issuance",
        "Good Moral request READY_FOR_ISSUANCE: counselor_a issues and prints it.",
    ),
    (
        "Zandro",
        "Uy",
        "MALE",
        "BSEE",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "New referral awaiting a Call Slip",
        "Referral recorded by gss_a; no action yet: issue a Call Slip from it.",
    ),
    (
        "Abigail",
        "Villamor",
        "FEMALE",
        "BTLED",
        1,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "New referral awaiting a Call Slip",
        "Referral recorded by counselor_b; no action yet: gss_b issues a Call Slip.",
    ),
    (
        "Benedict",
        "Wenceslao",
        "MALE",
        "BASOC",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Routine Interview evaluation pending",
        "Walk-in Encounter with a submitted intake: counselor_a finalizes the evaluation.",
    ),
    (
        "Cristina",
        "Yabut",
        "FEMALE",
        "BSENTREP",
        3,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Past Appointment awaiting an outcome",
        "A past Appointment with counselor_b still SCHEDULED: complete it or mark no-show.",
    ),
    (
        "Dominic",
        "Zamora",
        "MALE",
        "BSF",
        2,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Past Appointment awaiting an outcome",
        "A past Appointment with counselor_c still SCHEDULED: complete it or mark no-show.",
    ),
    (
        "Erika",
        "Abrenica",
        "FEMALE",
        "ENT-BSED",
        4,
        "SUBMITTED",
        "ordinary",
        Lifecycle.CURRENT,
        "Graduating: Exit Interview submitted",
        "Exit Interview submitted: Head Guidance may reopen it; Good Moral can be requested.",
    ),
)

# --- Background Students -----------------------------------------------------------------------
# (first, last, program, year, inventory state, background, lifecycle, tracer)
_C, _G, _F = Lifecycle.CURRENT, Lifecycle.GRADUATED, Lifecycle.FORMER
BACKGROUND_ROWS = (
    ("Althea", "Reyes", "BSIT", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Marco", "Dizon", "BSPSYCH", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Camille", "Santos", "BSBA", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Paolo", "Mercado", "BSED", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Danica", "Flores", "BSIS", 2, "SUBMITTED", "working", _C, ""),
    ("Luis", "Torres", "BSBIOL", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Jasmine", "Mendoza", "BSA", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Rafael", "Lim", "BEED", 1, "SUBMITTED", "guardian", _C, ""),
    ("Nicole", "Cruz", "BSIT", 2, "SUBMITTED", "four_ps", _C, ""),
    ("Gabriel", "Vega", "BSPSYCH", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Andrea", "Lopez", "BSBA", 4, "SUBMITTED", "commute", _C, ""),
    ("Miguel", "Salcedo", "BSED", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Sofia", "Tan", "BSIS", 3, "SUBMITTED", "pwd", _C, ""),
    ("Daniel", "Roxas", "BSBIOL", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Isabel", "Lazaro", "BSA", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Ethan", "Valdez", "BEED", 2, "SUBMITTED", "indigenous", _C, ""),
    ("Bianca", "Marquez", "BSIT", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Joshua", "Velasco", "BSPSYCH", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Claire", "Tolentino", "BSBA", 2, "SUBMITTED", "deceased_parent", _C, ""),
    ("Francis", "Natividad", "BSED", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Patricia", "Castro", "BSIS", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Aaron", "Buenaventura", "BSBIOL", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Mariel", "Panganiban", "BSA", 3, "SUBMITTED", "four_ps", _C, ""),
    ("Vincent", "Alvarez", "BEED", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Leah", "Ignacio", "BSIT", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Adrian", "De Leon", "BSPSYCH", 2, "SUBMITTED", "working", _C, ""),
    ("Chloe", "Villanueva", "BSBA", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Noel", "Gonzales", "BSED", 4, "SUBMITTED", "ordinary", _C, ""),
    ("Katrina", "Basilio", "BSIS", 1, "EARLY", "ordinary", _C, ""),
    ("Patrick", "Bernal", "BSBIOL", 2, "PARTIAL", "commute", _C, ""),
    ("Angelica", "Cordero", "BSA", 3, "NEARLY", "guardian", _C, ""),
    ("Joseph", "Del Rosario", "BEED", 4, "EARLY", "ordinary", _C, ""),
    ("Diana", "Estrella", "BSIT", 2, "PARTIAL", "ordinary", _C, ""),
    ("Mark", "Fajardo", "BSPSYCH", 3, "NEARLY", "ordinary", _C, ""),
    ("Vanessa", "Hilario", "BSBA", 4, "NEARLY", "ordinary", _C, ""),
    ("Ryan", "Jimenez", "BSED", 1, "MISSING", "ordinary", _C, ""),
    ("Elena", "Lucero", "BSIS", 2, "MISSING", "ordinary", _C, ""),
    ("Oliver", "Montes", "BSBIOL", 3, "MISSING", "ordinary", _C, ""),
    ("Angela", "Navarro", "BSIT", 4, "SUBMITTED", "ordinary", _G, "related"),
    ("Christian", "Ortega", "BSPSYCH", 4, "SUBMITTED", "ordinary", _G, "unrelated"),
    ("Irene", "Padilla", "BSBA", 4, "SUBMITTED", "ordinary", _G, "self_employed"),
    ("Martin", "Quintana", "BSED", 4, "SUBMITTED", "ordinary", _G, "job_seeking"),
    ("Rica", "Robles", "BSIS", 4, "SUBMITTED", "ordinary", _G, "further_study"),
    ("Samuel", "Tuazon", "BSBIOL", 4, "SUBMITTED", "ordinary", _G, "missing"),
    ("Julia", "Umali", "BSA", 2, "SUBMITTED", "ordinary", _F, ""),
    ("Warren", "Yap", "BEED", 2, "SUBMITTED", "ordinary", _F, ""),
    ("Ivy", "Castaneda", "BSME", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Gerald", "Bonifacio", "BSCE", 3, "SUBMITTED", "commute", _C, ""),
    ("Mae", "Evangelista", "BSEE", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Karl", "Domingo", "BSDEVCOM", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Olivia", "Garcia", "BSAM", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Neil", "Ferrer", "BSHM", 2, "PARTIAL", "working", _C, ""),
    ("Queenie", "Ibanez", "BPED", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Paul", "Hernandez", "BSF", 3, "SUBMITTED", "four_ps", _C, ""),
    ("Sheila", "Legaspi", "BSF", 1, "SUBMITTED", "commute", _C, ""),
    ("Rodel", "Jacinto", "BSABE", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Una", "Nepomuceno", "BSAGRI", 3, "SUBMITTED", "indigenous", _C, ""),
    ("Tomas", "Manalastas", "BTVTED", 2, "SUBMITTED", "ordinary", _C, ""),
    ("Wilma", "Pascua", "BSINDTECH", 4, "SUBMITTED", "guardian", _C, ""),
    ("Vince", "Orbeta", "ENT-BEED", 1, "SUBMITTED", "ordinary", _C, ""),
    ("Xyza", "Quinto", "ENT-BSENTREP", 3, "SUBMITTED", "ordinary", _C, ""),
    ("Yuri", "Rivera", "ENT-BSED", 2, "MISSING", "ordinary", _C, ""),
    ("Zenaida", "Salazar", "BSAGRI", 4, "SUBMITTED", "ordinary", _G, "related"),
    ("Alvin", "Tabora", "BTVTED", 2, "SUBMITTED", "ordinary", _F, ""),
    ("Bernadette", "Umbao", "BSIT", 2, "MISSING", "ordinary", _C, ""),
)
DISABLED_STUDENT_KEY = "bg_65"
# Current Students who also completed last year's Inventory (one annual record per year).
PREVIOUS_YEAR_ORDINALS = frozenset({6, 11, 16, 48, 51})


def _year_levels(year: int, state: str, lifecycle: Lifecycle, ordinal: int):
    if lifecycle == Lifecycle.GRADUATED:
        return ((PREVIOUS_YEAR, year),)
    if lifecycle == Lifecycle.FORMER:
        return ((PREVIOUS_YEAR, year),)
    if state == "MISSING":
        return ()
    levels = ((CURRENT_YEAR, year),)
    if year > 1 and ordinal in PREVIOUS_YEAR_ORDINALS:
        levels = ((PREVIOUS_YEAR, year - 1), *levels)
    return levels


def _address(campus: str, number: int) -> str:
    return f"Synthetic household {number}, Barangay Poblacion, {TOWNS[campus]}, Camarines Norte"


def _action_ready() -> tuple[StudentSpec, ...]:
    specs = []
    for ordinal, row in enumerate(ACTION_READY_ROWS, 1):
        first, last, sex, program, year, state, background, lifecycle, label, summary = row
        campus, college, code = _placement(program)
        specs.append(
            StudentSpec(
                key=f"ar_{ordinal:02d}",
                label=label,
                institutional_id=f"STG-S-{100 + ordinal:04d}",
                email_local_part=f"stg-ar-{ordinal:02d}",
                first_name=first,
                middle_name="",
                last_name=last,
                group=StudentGroup.ACTION_READY,
                sex=sex,
                date_of_birth=date(2008 - year, 1 + ordinal % 12, 1 + ordinal % 27),
                campus_code=campus,
                college_code=college,
                program_code=code,
                lifecycle=lifecycle,
                affiliated=lifecycle == Lifecycle.CURRENT,
                home_address=_address(campus, 100 + ordinal),
                year_levels=_year_levels(year, state, lifecycle, 0),
                inventory_state=state,
                background=background,
                tracer="missing",
                ordinal=100 + ordinal,
                enrolled_year_level=year,
                summary=summary,
                limitations=(
                    "Single-use action: once performed, a rerun does not restore the initial state."
                ),
            )
        )
    return tuple(specs)


def _background() -> tuple[StudentSpec, ...]:
    specs = []
    for ordinal, row in enumerate(BACKGROUND_ROWS, 1):
        first, last, program, year, state, background, lifecycle, tracer = row
        campus, college, code = _placement(program)
        key = f"bg_{ordinal:02d}"
        disabled = key == DISABLED_STUDENT_KEY
        specs.append(
            StudentSpec(
                key=key,
                label="Disabled Student account" if disabled else "Background Student",
                institutional_id=f"STG-S-{200 + ordinal:04d}",
                email_local_part=f"stg-bg-{ordinal:02d}",
                first_name=first,
                middle_name="",
                last_name=last,
                auth=AuthPlan.DISABLED if disabled else AuthPlan.CREDENTIAL,
                suitability=Suitability.RESTRICTED if disabled else Suitability.BACKGROUND,
                group=StudentGroup.BACKGROUND,
                sex="FEMALE" if ordinal % 2 else "MALE",
                date_of_birth=date(2009 - year, 1 + ordinal % 12, 1 + ordinal % 27),
                campus_code=campus,
                college_code=college,
                program_code=code,
                lifecycle=lifecycle,
                affiliated=lifecycle == Lifecycle.CURRENT,
                home_address=_address(campus, ordinal),
                year_levels=_year_levels(year, state, lifecycle, ordinal),
                inventory_state=state,
                background=background,
                tracer=tracer or "missing",
                ordinal=ordinal,
                enrolled_year_level=year,
                summary=(
                    "Disabled Student account (duplicate record closed by an administrator)."
                    if disabled
                    else "Quiet population record for rosters, filters and reports."
                ),
                limitations=(
                    "Disabled: cannot sign in."
                    if disabled
                    else "Background only; not prepared for an evaluator's actions."
                ),
            )
        )
    return tuple(specs)


ACTION_READY_STUDENTS = _action_ready()
BACKGROUND_STUDENTS = _background()
POPULATION_STUDENTS = (*ACTION_READY_STUDENTS, *BACKGROUND_STUDENTS)
STUDENTS = (*RICH_STUDENTS, *POPULATION_STUDENTS)
STUDENTS_BY_KEY = {student.key: student for student in STUDENTS}

__all__ = [
    "ACTIVE_REFERRAL",
    "ACTION_READY_STUDENTS",
    "ALUMNI",
    "BACKGROUND_STUDENTS",
    "CURRENT_YEAR",
    "DISABLED_STUDENT_KEY",
    "FIRST_YEAR",
    "FORMER",
    "FOURTH_YEAR",
    "GOOD_MORAL",
    "GRADUATING",
    "ONBOARDING",
    "POPULATION_STUDENTS",
    "PREVIOUS_YEAR",
    "RECENT_GRADUATE",
    "REFERRED",
    "RICH_STUDENTS",
    "SECOND_YEAR",
    "STUDENTS",
    "STUDENTS_BY_KEY",
]
