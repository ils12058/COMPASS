"""Synthetic staff and negative-test accounts for Staging Dataset v1.

Every name and ``STG-E-…`` identifier is fictional. Roles and designations are the canonical
identity policy; there is no UAT-only role. Counselor responsibility and staff supervision drive
real authorization scope, so each Counselor evaluator gets a separate caseload.
"""

from .identities import AccountSpec, AuthPlan, Suitability

IT_ADMIN = AccountSpec(
    key="it_admin",
    label="IT Administrator",
    institutional_id="STG-E-0001",
    email_local_part="stg-it-admin",
    first_name="Ramon",
    middle_name="Castillo",
    last_name="Bautista",
    role="IT_ADMIN",
    summary="Primary IT Administrator: accounts, access policy, organization, Platform Operations.",
    limitations="No access to confidential guidance records.",
)
IT_ADMIN_2 = AccountSpec(
    key="it_admin_2",
    label="IT Administrator (second evaluator)",
    institutional_id="STG-E-0002",
    email_local_part="stg-it-admin-2",
    first_name="Jocelyn",
    middle_name="Bernal",
    last_name="Arevalo",
    role="IT_ADMIN",
    summary="Second IT Administrator for a parallel evaluator; manages approved Privacy Notices.",
    limitations="No access to confidential guidance records.",
)
HEAD_GUIDANCE = AccountSpec(
    key="head_guidance",
    label="Head Guidance Counselor",
    institutional_id="STG-E-0003",
    email_local_part="stg-head-guidance",
    first_name="Ma. Lourdes",
    middle_name="Pascual",
    last_name="Villareal",
    role="COUNSELOR",
    designations=("HEAD_GUIDANCE_COUNSELOR",),
    summary=(
        "Institution-wide supervision, Academic Years, Exit Interview opportunities and "
        "corrections, Services, reports and feedback results; has a consultation schedule."
    ),
    limitations="One Head account exists; evaluators sharing it see each other's changes.",
)
COUNSELOR_A = AccountSpec(
    key="counselor_a",
    label="Guidance Counselor (Main: CCMS, CAS, COENG)",
    institutional_id="STG-E-0004",
    email_local_part="stg-counselor-a",
    first_name="Carlo",
    middle_name="Dizon",
    last_name="Esguerra",
    role="COUNSELOR",
    summary="Counselor for the Main Campus CCMS, CAS and COENG caseload; supervises goa_a.",
    limitations="Sees only Students in CCMS, CAS and COENG.",
)
COUNSELOR_B = AccountSpec(
    key="counselor_b",
    label="Guidance Counselor (Main CBPA, Abaño COED)",
    institutional_id="STG-E-0005",
    email_local_part="stg-counselor-b",
    first_name="Kristine",
    middle_name="Aquino",
    last_name="Manalo",
    role="COUNSELOR",
    summary="Counselor for the CBPA and COED caseload; supervises goa_b.",
    limitations="Sees only Students in CBPA and COED.",
)
COUNSELOR_C = AccountSpec(
    key="counselor_c",
    label="Guidance Counselor (satellite campuses)",
    institutional_id="STG-E-0006",
    email_local_part="stg-counselor-c",
    first_name="Edgardo",
    middle_name="Lim",
    last_name="Fuentes",
    role="COUNSELOR",
    summary=(
        "Counselor for Mercedes (CFAST), Labo (CANR), Jose Panganiban (COTT) and Entienza campuses."
    ),
    limitations="Sees only satellite-campus Students; has no supervised staff.",
)
GOA_A = AccountSpec(
    key="goa_a",
    label="Guidance Office Assistant (supervised by counselor_a)",
    institutional_id="STG-E-0007",
    email_local_part="stg-goa-a",
    first_name="Arnel",
    middle_name="Soriano",
    last_name="Ocampo",
    role="GUIDANCE_OFFICE_ASSISTANT",
    summary="Operational assistance within counselor_a's caseload: referrals, Call Slips, queue.",
    limitations="No counseling, Routine Interview or Student Session Summary content.",
)
GOA_B = AccountSpec(
    key="goa_b",
    label="Guidance Office Assistant (supervised by counselor_b)",
    institutional_id="STG-E-0008",
    email_local_part="stg-goa-b",
    first_name="Rowena",
    middle_name="Tan",
    last_name="Galvez",
    role="GUIDANCE_OFFICE_ASSISTANT",
    summary="Operational assistance within counselor_b's caseload: referrals, Call Slips, queue.",
    limitations="No counseling, Routine Interview or Student Session Summary content.",
)
FORMER_STAFF = AccountSpec(
    key="former_staff",
    label="Former Guidance Office Assistant (disabled)",
    institutional_id="STG-E-0011",
    email_local_part="stg-former-staff",
    first_name="Dennis",
    middle_name="Rivera",
    last_name="Aragon",
    role="GUIDANCE_OFFICE_ASSISTANT",
    # Active while their historical records are entered, then disabled as a departed employee.
    auth=AuthPlan.DISABLED,
    suitability=Suitability.RESTRICTED,
    summary="Departed staff member; authored last year's referral and Call Slip.",
    limitations="Disabled: cannot sign in. Used to prove disabled accounts are refused.",
)
UNASSIGNED_COUNSELOR = AccountSpec(
    key="unassigned_counselor",
    label="Guidance Counselor without College responsibility",
    institutional_id="STG-E-0012",
    email_local_part="stg-unassigned-counselor",
    first_name="Patricia",
    middle_name="Mendez",
    last_name="Ilagan",
    role="COUNSELOR",
    suitability=Suitability.RESTRICTED,
    summary="A Counselor with no College responsibility: an empty assigned caseload.",
    limitations="Negative-scope testing only: sees no Student records.",
)
IT_ADMIN_3 = AccountSpec(
    key="it_admin_3",
    label="IT Administrator (third evaluator)",
    institutional_id="STG-E-0014",
    email_local_part="stg-it-admin-3",
    first_name="Denise",
    middle_name="Alonzo",
    last_name="Villanueva",
    role="IT_ADMIN",
    summary="Third IT Administrator for independent ITSO UAT; reviews platform health and access.",
    limitations="No access to confidential guidance records; do not modify dataset accounts.",
)
OFFICER_NO_DESIGNATION = AccountSpec(
    key="officer_no_designation",
    label="Institutional Officer",
    institutional_id="STG-E-0013",
    email_local_part="stg-officer",
    first_name="Leonardo",
    middle_name="Cruz",
    last_name="Salonga",
    role="INSTITUTIONAL_OFFICER",
    summary="Generic Institutional Officer: own account and published Privacy Notice readership.",
    limitations="Zero default domain capabilities; administrative workspaces are refused.",
)

STAFF = (
    IT_ADMIN,
    IT_ADMIN_2,
    HEAD_GUIDANCE,
    COUNSELOR_A,
    COUNSELOR_B,
    COUNSELOR_C,
    GOA_A,
    GOA_B,
    FORMER_STAFF,
    UNASSIGNED_COUNSELOR,
    OFFICER_NO_DESIGNATION,
    IT_ADMIN_3,
)

COUNSELOR_RESPONSIBILITIES = (
    (COUNSELOR_A.key, "MAIN", "CCMS"),
    (COUNSELOR_A.key, "MAIN", "CAS"),
    (COUNSELOR_A.key, "MAIN", "COENG"),
    (COUNSELOR_B.key, "MAIN", "CBPA"),
    (COUNSELOR_B.key, "ABANO", "COED"),
    (COUNSELOR_C.key, "MERCEDES", "CFAST"),
    (COUNSELOR_C.key, "LABO", "CANR"),
    (COUNSELOR_C.key, "PANGANIBAN", "COTT"),
    (COUNSELOR_C.key, "ENTIENZA", "ENTIENZA"),
)
# Supervision by an ordinary Counselor keeps each Staff scope identical to that Counselor's.
STAFF_SUPERVISION = (
    (GOA_A.key, COUNSELOR_A.key),
    (GOA_B.key, COUNSELOR_B.key),
    (FORMER_STAFF.key, COUNSELOR_A.key),
)


def counselor_for(campus_code: str, college_code: str) -> str:
    for counselor, campus, college in COUNSELOR_RESPONSIBILITIES:
        if (campus, college) == (campus_code, college_code):
            return counselor
    raise KeyError(f"{campus_code}/{college_code} has no dataset Counselor")


def supervised_staff(counselor_key: str) -> str | None:
    for staff, supervisor in STAFF_SUPERVISION:
        if supervisor == counselor_key and staff != FORMER_STAFF.key:
            return staff
    return None


__all__ = [
    "COUNSELOR_A",
    "COUNSELOR_B",
    "COUNSELOR_C",
    "COUNSELOR_RESPONSIBILITIES",
    "FORMER_STAFF",
    "GOA_A",
    "GOA_B",
    "HEAD_GUIDANCE",
    "IT_ADMIN",
    "IT_ADMIN_2",
    "IT_ADMIN_3",
    "OFFICER_NO_DESIGNATION",
    "STAFF",
    "STAFF_SUPERVISION",
    "UNASSIGNED_COUNSELOR",
    "counselor_for",
    "supervised_staff",
]
