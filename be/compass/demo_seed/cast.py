"""The deliberate synthetic cast. Names and identifiers are fictional and clearly demo-owned.

Account state, authentication state, and Student lifecycle are declared separately on purpose:
none of them implies another.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class AuthState(StrEnum):
    READY = "READY"  # usable password from DEMO_ACCOUNT_PASSWORD, email verified
    ONBOARDING = "ONBOARDING"  # provisioned only: no usable password, email unverified


class Lifecycle(StrEnum):
    CURRENT = "CURRENT"
    GRADUATED = "GRADUATED"
    FORMER = "FORMER"


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    institutional_id: str
    email_local_part: str
    first_name: str
    middle_name: str
    last_name: str
    role: str
    designations: tuple[str, ...] = ()
    auth_state: AuthState = AuthState.READY
    active: bool = True

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.middle_name, self.last_name))


@dataclass(frozen=True)
class StudentPersona(Persona):
    role: str = "STUDENT"
    sex: str = ""
    date_of_birth: date | None = None
    campus_code: str = ""
    college_code: str = ""
    program_code: str = ""
    # Lifecycle the persona ends with; historical back-entry runs while the Student was CURRENT.
    lifecycle: Lifecycle = Lifecycle.CURRENT
    # Graduated and former Students keep no College affiliation, so they never appear as current
    # classmates in scoped Guidance pickers.
    affiliated: bool = True
    civil_status: str = "Single"
    home_address: str = ""
    # Year level in each Academic Year the Student submitted (or drafted) an Inventory.
    year_levels: tuple[tuple[str, int], ...] = ()


IT_ADMIN = Persona(
    key="it_admin",
    label="IT Administrator",
    institutional_id="DEMO-2026-0001",
    email_local_part="demo-admin",
    first_name="Ramon",
    middle_name="Castillo",
    last_name="Bautista",
    role="IT_ADMIN",
)
HEAD_GUIDANCE = Persona(
    key="head_guidance",
    label="Head Guidance Counselor",
    institutional_id="DEMO-2026-0002",
    email_local_part="demo-head",
    first_name="Ma. Lourdes",
    middle_name="Pascual",
    last_name="Villareal",
    role="COUNSELOR",
    designations=("HEAD_GUIDANCE_COUNSELOR",),
)
COUNSELOR_A = Persona(
    key="counselor_a",
    label="Counselor (CCMS and CAS)",
    institutional_id="DEMO-2026-0003",
    email_local_part="demo-counselor-a",
    first_name="Carlo",
    middle_name="Dizon",
    last_name="Esguerra",
    role="COUNSELOR",
)
COUNSELOR_B = Persona(
    key="counselor_b",
    label="Counselor (CBPA and COED)",
    institutional_id="DEMO-2026-0004",
    email_local_part="demo-counselor-b",
    first_name="Kristine",
    middle_name="Aquino",
    last_name="Manalo",
    role="COUNSELOR",
)
GUIDANCE_STAFF = Persona(
    key="guidance_staff",
    label="Guidance Services Staff",
    institutional_id="DEMO-2026-0005",
    email_local_part="demo-staff",
    first_name="Arnel",
    middle_name="Soriano",
    last_name="Ocampo",
    role="GUIDANCE_SERVICES_STAFF",
)
DPO = Persona(
    key="dpo",
    label="Data Protection Officer",
    institutional_id="DEMO-2026-0006",
    email_local_part="demo-dpo",
    first_name="Grace",
    middle_name="Fernandez",
    last_name="Magbanua",
    role="INSTITUTIONAL_OFFICER",
    designations=("DPO",),
)
FORMER_STAFF = Persona(
    key="former_staff",
    label="Former Guidance Services Staff (disabled)",
    institutional_id="DEMO-2026-0007",
    email_local_part="demo-former-staff",
    first_name="Dennis",
    middle_name="Rivera",
    last_name="Aragon",
    role="GUIDANCE_SERVICES_STAFF",
    # Active while their historical records are entered, then disabled as a departed employee.
    active=False,
)

FIRST_YEAR = StudentPersona(
    key="first_year",
    label="Current first-year Student",
    institutional_id="DEMO-2026-0101",
    email_local_part="demo-student01",
    first_name="Bea Kristel",
    middle_name="Lagman",
    last_name="Abad",
    sex="FEMALE",
    date_of_birth=date(2008, 3, 14),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIT",
    home_address="Purok 2, Barangay Gahonon, Daet, Camarines Norte",
    year_levels=(("2026-2027", 1),),
)
SECOND_YEAR = StudentPersona(
    key="second_year",
    label="Current second-year Student",
    institutional_id="DEMO-2026-0102",
    email_local_part="demo-student02",
    first_name="Mikaela Joy",
    middle_name="Ramos",
    last_name="Serrano",
    sex="FEMALE",
    date_of_birth=date(2007, 6, 2),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSPSYCH",
    home_address="Purok 5, Barangay Camambugan, Daet, Camarines Norte",
    year_levels=(("2025-2026", 1), ("2026-2027", 2)),
)
REFERRED = StudentPersona(
    key="referred",
    label="Current third-year Student (referred)",
    institutional_id="DEMO-2026-0103",
    email_local_part="demo-student03",
    first_name="Jerome Andres",
    middle_name="Salvador",
    last_name="Dela Paz",
    sex="MALE",
    date_of_birth=date(2005, 11, 20),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSHM",
    home_address="Sitio Malatap, Barangay Tulay na Lupa, Labo, Camarines Norte",
    year_levels=(("2024-2025", 1), ("2025-2026", 2), ("2026-2027", 3)),
)
FOURTH_YEAR = StudentPersona(
    key="fourth_year",
    label="Current fourth-year Student",
    institutional_id="DEMO-2026-0104",
    email_local_part="demo-student04",
    first_name="Kevin Luis",
    middle_name="Navales",
    last_name="Pardo",
    sex="MALE",
    date_of_birth=date(2004, 9, 8),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIS",
    home_address="Purok 3, Barangay Talobatib, Labo, Camarines Norte",
    year_levels=(("2024-2025", 2), ("2025-2026", 3), ("2026-2027", 4)),
)
GRADUATING = StudentPersona(
    key="graduating",
    label="Current graduating Student",
    institutional_id="DEMO-2026-0105",
    email_local_part="demo-student05",
    first_name="Rosalie Mae",
    middle_name="Dimaano",
    last_name="Obusan",
    sex="FEMALE",
    date_of_birth=date(2003, 12, 1),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSBA",
    home_address="Purok 1, Barangay Poblacion, Vinzons, Camarines Norte",
    # A one-semester leave of absence moved graduation to the end of this first semester.
    year_levels=(("2024-2025", 3), ("2025-2026", 4), ("2026-2027", 5)),
)
RECENT_GRADUATE = StudentPersona(
    key="recent_graduate",
    label="Recent graduate (June 2026)",
    institutional_id="DEMO-2026-0106",
    email_local_part="demo-student06",
    first_name="Adrian Clyde",
    middle_name="Galang",
    last_name="Rosales",
    sex="MALE",
    date_of_birth=date(2004, 1, 17),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSDEVCOM",
    lifecycle=Lifecycle.GRADUATED,
    affiliated=False,
    home_address="Purok 4, Barangay Bagasbas, Daet, Camarines Norte",
    year_levels=(("2024-2025", 3), ("2025-2026", 4)),
)
ALUMNI = StudentPersona(
    key="alumni",
    label="Alumna (June 2025)",
    institutional_id="DEMO-2026-0107",
    email_local_part="demo-student07",
    first_name="Ellaine Grace",
    middle_name="Moreno",
    last_name="Cabrera",
    sex="FEMALE",
    date_of_birth=date(2003, 4, 25),
    campus_code="ABANO",
    college_code="COED",
    program_code="BSED",
    lifecycle=Lifecycle.GRADUATED,
    affiliated=False,
    home_address="Purok 6, Barangay San Isidro, Talisay, Camarines Norte",
    year_levels=(("2024-2025", 4),),
)
FORMER = StudentPersona(
    key="former",
    label="Former Student (transferred out)",
    institutional_id="DEMO-2026-0108",
    email_local_part="demo-student08",
    first_name="Nathaniel Jose",
    middle_name="Pimentel",
    last_name="Samonte",
    sex="MALE",
    date_of_birth=date(2007, 2, 9),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BSBIOL",
    lifecycle=Lifecycle.FORMER,
    affiliated=False,
    home_address="Purok 2, Barangay Mancruz, Daet, Camarines Norte",
    year_levels=(("2025-2026", 1),),
)
ONBOARDING = StudentPersona(
    key="onboarding",
    label="Onboarding Student (never signed in)",
    institutional_id="DEMO-2026-0109",
    email_local_part="demo-onboarding",
    first_name="Trisha Anne",
    middle_name="Villafuerte",
    last_name="Llamas",
    auth_state=AuthState.ONBOARDING,
    sex="FEMALE",
    date_of_birth=date(2008, 7, 30),
    campus_code="MAIN",
    college_code="CCMS",
    program_code="BSIT",
    home_address="",
)
ACTIVE_REFERRAL = StudentPersona(
    key="active_referral",
    label="Current second-year Student (active referral)",
    institutional_id="DEMO-2026-0110",
    email_local_part="demo-student10",
    first_name="Lance Emmanuel",
    middle_name="Rodrigo",
    last_name="Bernardo",
    sex="MALE",
    date_of_birth=date(2006, 10, 3),
    campus_code="MAIN",
    college_code="CAS",
    program_code="BAELS",
    home_address="Purok 7, Barangay Awitan, Daet, Camarines Norte",
    year_levels=(("2025-2026", 1), ("2026-2027", 2)),
)
GOOD_MORAL = StudentPersona(
    key="good_moral",
    label="Current third-year Student (certificate request)",
    institutional_id="DEMO-2026-0111",
    email_local_part="demo-student11",
    first_name="Princess Joy",
    middle_name="Enriquez",
    last_name="Alcantara",
    sex="FEMALE",
    date_of_birth=date(2005, 5, 11),
    campus_code="MAIN",
    college_code="CBPA",
    program_code="BSA",
    home_address="Purok 3, Barangay Lag-on, Daet, Camarines Norte",
    year_levels=(("2024-2025", 1), ("2025-2026", 2), ("2026-2027", 3)),
)

STAFF = (IT_ADMIN, HEAD_GUIDANCE, COUNSELOR_A, COUNSELOR_B, GUIDANCE_STAFF, DPO, FORMER_STAFF)
STUDENTS = (
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
CAST: tuple[Persona, ...] = (*STAFF, *STUDENTS)
PERSONAS_BY_KEY = {persona.key: persona for persona in CAST}

# Counselor responsibility and staff supervision drive real authorization scope.
COUNSELOR_RESPONSIBILITIES = (
    (COUNSELOR_A.key, "MAIN", "CCMS"),
    (COUNSELOR_A.key, "MAIN", "CAS"),
    (COUNSELOR_B.key, "MAIN", "CBPA"),
    (COUNSELOR_B.key, "ABANO", "COED"),
)
# Supervision by an ordinary Counselor keeps Staff scope identical under ADR-050's wording and the
# current resolver: exactly Counselor A's Colleges.
STAFF_SUPERVISION = (
    (GUIDANCE_STAFF.key, COUNSELOR_A.key),
    (FORMER_STAFF.key, COUNSELOR_A.key),
)


def email_for(persona: Persona, *, domain: str, onboarding_email: str | None) -> str:
    if persona.auth_state == AuthState.ONBOARDING and onboarding_email:
        return onboarding_email
    return f"{persona.email_local_part}@{domain}"


def _validate_cast() -> None:
    keys = [persona.key for persona in CAST]
    ids = [persona.institutional_id for persona in CAST]
    local_parts = [persona.email_local_part for persona in CAST]
    for values, label in ((keys, "key"), (ids, "institutional ID"), (local_parts, "email")):
        if len(set(values)) != len(values):
            raise RuntimeError(f"demo cast {label}s must be unique")
    if [p for p in CAST if p.auth_state == AuthState.ONBOARDING] != [ONBOARDING]:
        raise RuntimeError("exactly one demo persona demonstrates first-time onboarding")
    for persona in STUDENTS:
        if persona.lifecycle != Lifecycle.CURRENT and persona.affiliated:
            raise RuntimeError(f"{persona.key}: only CURRENT demo Students keep an affiliation")
        if persona.lifecycle == Lifecycle.CURRENT and persona.auth_state == AuthState.READY:
            if not any(label == "2026-2027" for label, _ in persona.year_levels):
                raise RuntimeError(
                    f"{persona.key}: ready CURRENT Students have a current Inventory"
                )


_validate_cast()


__all__ = [
    "ACTIVE_REFERRAL",
    "ALUMNI",
    "AuthState",
    "CAST",
    "COUNSELOR_A",
    "COUNSELOR_B",
    "COUNSELOR_RESPONSIBILITIES",
    "DPO",
    "FIRST_YEAR",
    "FORMER",
    "FORMER_STAFF",
    "FOURTH_YEAR",
    "GOOD_MORAL",
    "GRADUATING",
    "GUIDANCE_STAFF",
    "HEAD_GUIDANCE",
    "IT_ADMIN",
    "Lifecycle",
    "ONBOARDING",
    "PERSONAS_BY_KEY",
    "Persona",
    "RECENT_GRADUATE",
    "REFERRED",
    "SECOND_YEAR",
    "STAFF",
    "STAFF_SUPERVISION",
    "STUDENTS",
    "StudentPersona",
    "email_for",
]
