"""The structured Staging Dataset v1 manifest: every account and every UAT scenario.

The account catalog, selection guide, scenario matrix and summary are generated from this module
and verified against the seeded database (``verify``, ``reports``). Change the population or a
scenario here, rerun ``seed_staging_dataset report``, and the documentation follows. Nothing here
names a real evaluator or contains a credential.

Each executable scenario lists ``checks``: ``(account key, predicate)`` pairs that ``verify``
evaluates against the database to prove the documented initial state. A scenario whose feature is
not implemented is ``PENDING_IMPLEMENTATION`` and is never counted as executable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from compass.accounts.policy import (
    DESIGNATION_DEFINITIONS,
    ROLE_DEFINITIONS,
    designation_role_compatible,
)

from .identities import AccountSpec, AuthPlan, Lifecycle, StudentSpec, Suitability
from .staff import STAFF
from .students import STUDENTS

ACCOUNTS: tuple[AccountSpec, ...] = (*STAFF, *STUDENTS)
ACCOUNTS_BY_KEY = {account.key: account for account in ACCOUNTS}

# The finalized 40-person UAT: participants per stakeholder category, and the 25 current Students
# per College / academic unit (Entienza is the Entienza Campus academic unit).
UAT_40_STAKEHOLDER_COUNTS = {
    "Head Guidance Counselor": 1,
    "Guidance Counselor": 3,
    "Guidance Services Staff": 2,
    "Current Student": 25,
    "Alumni": 5,
    "ITSO Personnel": 3,
    "Data Protection Officer": 1,
}
UAT_40_STUDENT_QUOTA = {
    "CCMS": 3,
    "CAS": 3,
    "CBPA": 3,
    "COENG": 3,
    "COED": 3,
    "CFAST": 3,
    "CANR": 3,
    "COTT": 2,
    "ENTIENZA": 2,
}
# Each key is a current Student seeded in that College. bg_… accounts are promoted background
# Students (see students.PROMOTED_BACKGROUND); the other UAT-ready Students stay reserves.
UAT_40_STUDENT_COLLEGES = {
    "CCMS": ("ar_01", "ar_05", "ar_14"),
    "CAS": ("ar_03", "ar_09", "ar_12"),
    "CBPA": ("ar_02", "ar_10", "ar_22"),
    "COENG": ("ar_07", "ar_19", "bg_47"),
    "COED": ("ar_04", "ar_15", "ar_20"),
    "CFAST": ("ar_23", "bg_54", "bg_55"),
    "CANR": ("ar_08", "ar_16", "bg_56"),
    "COTT": ("bg_58", "bg_59"),
    "ENTIENZA": ("ar_24", "bg_60"),
}

# Proposed ownership only: no evaluator identities, credential issuance or live assignment.
# Alumni retain the canonical STUDENT role; ITSO participants retain IT_ADMIN.
UAT_40_ALLOCATION = {
    "Head Guidance Counselor": ("head_guidance",),
    "Guidance Counselor": ("counselor_a", "counselor_b", "counselor_c"),
    "Guidance Services Staff": ("gss_a", "gss_b"),
    "Current Student": tuple(key for keys in UAT_40_STUDENT_COLLEGES.values() for key in keys),
    "Alumni": ("recent_graduate", "alumni", "ar_13", "ar_25", "ar_26"),
    "ITSO Personnel": ("it_admin", "it_admin_2", "it_admin_3"),
    "Data Protection Officer": ("dpo",),
}

ROLE_LABELS = {
    "IT_ADMIN": "IT Administrator",
    "COUNSELOR": "Guidance Counselor",
    "GUIDANCE_SERVICES_STAFF": "Guidance Services Staff",
    "INSTITUTIONAL_OFFICER": "Institutional Officer",
    "STUDENT": "Student",
}


def email_for(account: AccountSpec, *, domain: str, onboarding_email: str | None) -> str:
    if account.auth == AuthPlan.ONBOARDING and onboarding_email:
        return onboarding_email
    return f"{account.email_local_part}@{domain}"


def stakeholder(account: AccountSpec) -> str:
    """The UAT stakeholder category an account represents."""

    if "HEAD_GUIDANCE_COUNSELOR" in account.designations:
        return "Head Guidance Counselor"
    if "DPO" in account.designations:
        return "Data Protection Officer"
    return ROLE_LABELS[account.role]


class Readiness(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    PENDING_IMPLEMENTATION = "PENDING_IMPLEMENTATION"


@dataclass(frozen=True)
class Scenario:
    id: str
    domain: str
    title: str
    role: str
    account: str
    route: str
    initial_state: str
    action: str
    expected: str
    preconditions: str = "Signed in with the recommended account."
    related: tuple[str, ...] = ()
    mutating: bool = True
    # Rerunning the same scenario needs a fresh dataset (or a different prepared account).
    fresh_state: bool = True
    readiness: Readiness = Readiness.EXECUTABLE
    restrictions: str = ""
    checks: tuple[tuple[str, str], ...] = ()


def _s(*args, **kwargs) -> Scenario:
    return Scenario(*args, **kwargs)


_LIVE_EMAIL = (
    "Sends normal staging email to the dataset address; use an operator-approved email plan."
)
_ONE_EVALUATOR = "Assign this account to one evaluator; a second evaluator would see the change."

SCENARIOS: tuple[Scenario, ...] = (
    # --- Student ------------------------------------------------------------------------------
    _s(
        "STU-PRF-01",
        "Profile and account",
        "Update own profile and review security activity",
        "Student",
        "ar_02",
        "/portal/account/profile",
        "Current Student with a synthetic profile.",
        "Edit the contact number and current address, save, then open Account > Activity.",
        "The profile saves; My Activity lists the profile change; no other Student's data appears.",
        fresh_state=False,
        checks=(("ar_02", "lifecycle:CURRENT"),),
    ),
    _s(
        "STU-INV-01",
        "Individual Inventory",
        "Finish and submit a nearly complete Inventory",
        "Student",
        "ar_07",
        "/portal/inventory/current",
        "Current-year Inventory saved as a nearly complete draft.",
        "Review each section, complete the remaining answers and submit.",
        "The Inventory is submitted for 2026-2027; counselor_a sees it in the Inventory roster.",
        related=("counselor_a",),
        checks=(("ar_07", "inventory:draft"),),
    ),
    _s(
        "STU-INV-02",
        "Individual Inventory",
        "Start an Individual Inventory",
        "Student",
        "ar_08",
        "/portal/inventory/current",
        "Current Student with no current-year Inventory.",
        "Start the Inventory, save a draft, return later and submit.",
        "A draft is kept between visits; submission records the 2026-2027 Inventory.",
        related=("counselor_c",),
        checks=(("ar_08", "inventory:missing"),),
    ),
    _s(
        "STU-INV-03",
        "Individual Inventory",
        "Review own Inventory history",
        "Student",
        "second_year",
        "/portal/inventory",
        "Submitted Inventories for 2025-2026 and 2026-2027.",
        "Open the Inventory history and each year's record.",
        "Both annual Inventories are listed read-only with their own year levels.",
        mutating=False,
        fresh_state=False,
        checks=(("second_year", "inventory:submitted"),),
    ),
    _s(
        "STU-APT-01",
        "Appointments",
        "Book a Counseling Appointment",
        "Student",
        "ar_01",
        "/portal/appointments/book",
        "Submitted Inventory; no Appointments.",
        "Choose Counseling, counselor_a, a delivery mode and an available slot; confirm.",
        "The Appointment is SCHEDULED, appears under My appointments and on counselor_a's list; an "
        "in-app notification is created.",
        related=("counselor_a",),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_01", "appointment:none"), ("ar_01", "inventory:submitted")),
    ),
    _s(
        "STU-APT-02",
        "Appointments",
        "Book a Counseling Appointment (second caseload)",
        "Student",
        "ar_02",
        "/portal/appointments/book",
        "Submitted Inventory; no Appointments.",
        "Book Counseling with counselor_b.",
        "The Appointment is SCHEDULED for counselor_b and visible to gss_b.",
        related=("counselor_b", "gss_b"),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_02", "appointment:none"),),
    ),
    _s(
        "STU-APT-03",
        "Appointments",
        "Reschedule an upcoming Appointment",
        "Student",
        "ar_03",
        "/portal/appointments/my",
        "An upcoming in-person Counseling Appointment with counselor_a.",
        "Open the Appointment and reschedule it to another available slot.",
        "The Appointment moves to the new time; its history records the change.",
        related=("counselor_a",),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_03", "appointment:upcoming:IN_PERSON"),),
    ),
    _s(
        "STU-APT-04",
        "Appointments",
        "Cancel an upcoming Appointment",
        "Student",
        "ar_04",
        "/portal/appointments/my",
        "An upcoming in-person Counseling Appointment with counselor_b.",
        "Open the Appointment and cancel it with a reason.",
        "The Appointment becomes CANCELLED and its slot becomes available again.",
        related=("counselor_b",),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_04", "appointment:upcoming:IN_PERSON"),),
    ),
    _s(
        "STU-APT-05",
        "Appointments",
        "A FORMER Student cannot book",
        "Student",
        "former",
        "/portal/appointments/book",
        "FORMER lifecycle with one historical Inventory.",
        "Sign in and try to book Counseling.",
        "Booking is unavailable and explains that current enrollment is required; past records "
        "remain readable.",
        mutating=False,
        fresh_state=False,
        checks=(("former", "lifecycle:FORMER"),),
    ),
    _s(
        "STU-RI-01",
        "Routine Interview",
        "Prepare the Routine Interview intake",
        "Student",
        "ar_09",
        "/portal/routine-interviews",
        "An upcoming Appointment with counselor_a and a saved intake draft.",
        "Open the intake, complete the remaining answers and submit before the session.",
        "The intake is submitted; counselor_a can read it from the Counseling context.",
        related=("counselor_a",),
        checks=(("ar_09", "routine:intake_draft"), ("ar_09", "appointment:upcoming:ANY")),
    ),
    _s(
        "STU-EC-01",
        "E-Counseling",
        "Decide on E-Counseling recording consent",
        "Student",
        "ar_05",
        "/portal/appointments/my",
        "An upcoming ONLINE Appointment with counselor_a; no consent requested yet.",
        "After counselor_a requests consent (CNS-EC-01), open the E-Counseling page and approve "
        "or decline.",
        "The decision is recorded and shown to the Counselor; declining blocks recording only.",
        preconditions="CNS-EC-01 has been performed first.",
        related=("counselor_a",),
        restrictions="Joining the call itself needs Daily enabled on staging (operator-approved).",
        checks=(("ar_05", "appointment:upcoming:ONLINE"), ("ar_05", "ecounseling:no_room")),
    ),
    _s(
        "STU-EXIT-01",
        "Exit Interview",
        "Complete an Exit Interview",
        "Student",
        "ar_10",
        "/portal/exit-interviews",
        "Graduating; Exit Interview opportunity open; no interview started.",
        "Start the Exit Interview, save, return and submit.",
        "The interview is submitted for 2026-2027 and becomes readable by Head Guidance.",
        related=("head_guidance",),
        checks=(("ar_10", "exit:opportunity_open"),),
    ),
    _s(
        "STU-EXIT-02",
        "Exit Interview",
        "Complete an Exit Interview (second evaluator)",
        "Student",
        "ar_11",
        "/portal/exit-interviews",
        "Graduating; Exit Interview opportunity open; no interview started.",
        "Start and submit the Exit Interview.",
        "The interview is submitted for 2026-2027.",
        checks=(("ar_11", "exit:opportunity_open"),),
    ),
    _s(
        "STU-EXIT-03",
        "Exit Interview",
        "Continue an Exit Interview draft",
        "Student",
        "graduating",
        "/portal/exit-interviews",
        "Exit Interview saved as a draft; Good Moral request pending.",
        "Open the draft, review the saved answers and submit.",
        "The interview is submitted; earlier answers were preserved.",
        checks=(("graduating", "exit:draft"),),
    ),
    _s(
        "STU-GM-01",
        "Good Moral",
        "Request a current-Student Good Moral certificate",
        "Student",
        "ar_12",
        "/portal/good-moral/request",
        "Current Student with a submitted Inventory and no request.",
        "Request a certificate for the current semester.",
        "A REQUESTED request appears for counselor_a; the Student can follow its status.",
        related=("counselor_a",),
        checks=(("ar_12", "good_moral:none"),),
    ),
    _s(
        "STU-GM-02",
        "Good Moral",
        "Request Good Moral after submitting the Exit Interview",
        "Student",
        "ar_24",
        "/portal/good-moral/request",
        "Graduating with a submitted 2026-2027 Exit Interview; no request.",
        "Request a current-Student certificate.",
        "The request links the submitted Exit Interview and is REQUESTED for counselor_c.",
        related=("counselor_c",),
        checks=(("ar_24", "exit:submitted"), ("ar_24", "good_moral:none")),
    ),
    _s(
        "STU-GT-01",
        "Graduate Tracer",
        "Complete the Graduate Tracer",
        "Student",
        "ar_13",
        "/portal/graduate-tracer",
        "GRADUATED (June 2026); Tracer not started.",
        "Start the Tracer, save a draft, then submit.",
        "The response is submitted and counted in the Graduate Tracer report.",
        related=("head_guidance",),
        checks=(("ar_13", "lifecycle:GRADUATED"), ("ar_13", "tracer:none")),
    ),
    _s(
        "STU-GT-02",
        "Graduate Tracer",
        "Continue a Graduate Tracer draft",
        "Student",
        "recent_graduate",
        "/portal/graduate-tracer",
        "GRADUATED; Tracer saved as a draft; issued graduate certificate.",
        "Review the draft and submit it.",
        "The response is submitted; the issued certificate remains available.",
        checks=(("recent_graduate", "tracer:draft"),),
    ),
    _s(
        "STU-MSG-01",
        "Guidance Messages",
        "Read and reply to a Counselor's message",
        "Student",
        "ar_14",
        "/portal/messages",
        "counselor_a started the Appointment conversation; unread by the Student.",
        "Open Messages, read the conversation and reply.",
        "The unread badge clears; counselor_a sees the reply in the same thread.",
        related=("counselor_a",),
        checks=(("ar_14", "messages:unread"),),
    ),
    _s(
        "STU-MSG-02",
        "Guidance Messages",
        "Start a conversation with the Guidance Office",
        "Student",
        "ar_12",
        "/portal/messages/new",
        "Current Student in counselor_a's caseload; no Office conversation.",
        "Send a new message to the Guidance Office.",
        "An Office thread is created and routed to counselor_a.",
        related=("counselor_a",),
        checks=(("ar_12", "messages:no_office_thread"),),
    ),
    _s(
        "STU-SUM-01",
        "Counseling",
        "Read a published Student Session Summary and give feedback",
        "Student",
        "ar_15",
        "/portal/notifications",
        (
            "Completed session with counselor_b; published Student Session Summary;"
            " feedback invitation."
        ),
        (
            "Open the Student Session Summary from the notification, then submit "
            "the Customer Feedback form."
        ),
        "The summary is readable by the Student only; feedback is recorded once.",
        related=("counselor_b",),
        checks=(("ar_15", "summary:published"),),
    ),
    _s(
        "STU-CS-01",
        "Call Slips",
        "View an issued Call Slip",
        "Student",
        "ar_16",
        "/portal/call-slips",
        "A Call Slip issued by counselor_c for an interview this week.",
        "Open the Call Slip from the notification.",
        "The Student sees the date, time and destination; no referral content is shown.",
        mutating=False,
        fresh_state=False,
        related=("counselor_c",),
        checks=(("ar_16", "call_slip:live"),),
    ),
    _s(
        "STU-NOT-01",
        "Notifications",
        "Review read and unread notifications",
        "Student",
        "second_year",
        "/portal/notifications",
        (
            "Read Appointment and feedback notifications; an unread Student Session"
            " Summary notification."
        ),
        "Open Notifications, then mark the unread item as read.",
        "Unread and read items are distinguished; the unread count updates.",
        fresh_state=False,
        checks=(("second_year", "notifications:unread"),),
    ),
    _s(
        "STU-PUB-01",
        "Announcements and Resources",
        "Read Student-facing publications",
        "Student",
        "ar_02",
        "/portal/announcements",
        "Published Student announcements and resources exist; archived ones are hidden.",
        "Open Announcements and Resources.",
        "Only published items for the Student audience are listed.",
        mutating=False,
        fresh_state=False,
        checks=(("ar_02", "publications:published"),),
    ),
    _s(
        "STU-ONB-01",
        "Onboarding",
        "First-time sign-in and password setup",
        "Student",
        "onboarding",
        "/login",
        "Provisioned account; never signed in; email unverified; no password.",
        "Start Password Access with the account email, enter the emailed one-time code and set a "
        "password.",
        "The email becomes verified and normal sign-in works afterwards.",
        restrictions="Needs STAGING_SEED_ONBOARDING_EMAIL set to an operator-controlled mailbox.",
        checks=(("onboarding", "account:onboarding"),),
    ),
    _s(
        "STU-RI-02",
        "Routine Interview",
        "Finish the intake for an upcoming online session",
        "Student",
        "first_year",
        "/portal/routine-interviews",
        "An upcoming ONLINE Appointment with counselor_a and a saved intake draft.",
        "Complete the intake and submit it, then open the Appointment's E-Counseling page.",
        "The intake is submitted; the E-Counseling page shows the scheduled session.",
        related=("counselor_a",),
        checks=(
            ("first_year", "routine:intake_draft"),
            ("first_year", "appointment:upcoming:ONLINE"),
        ),
    ),
    _s(
        "STU-EC-02",
        "E-Counseling",
        "Decide on consent for an online session (second caseload)",
        "Student",
        "ar_06",
        "/portal/appointments/my",
        "An upcoming ONLINE Appointment with counselor_b; no consent requested yet.",
        "After counselor_b requests consent, approve or decline it on the E-Counseling page.",
        "The decision is recorded for counselor_b's session.",
        preconditions="counselor_b has requested consent for this Appointment.",
        related=("counselor_b",),
        restrictions="Joining the call itself needs Daily enabled on staging (operator-approved).",
        checks=(("ar_06", "appointment:upcoming:ONLINE"),),
    ),
    _s(
        "STU-SUM-02",
        "Counseling",
        "An unpublished Student Session Summary stays hidden",
        "Student",
        "fourth_year",
        "/portal/appointments/my",
        (
            "A walk-in Encounter with an unpublished Student Session Summary draft;"
            " an upcoming follow-up."
        ),
        "Open Appointments and notifications; look for the walk-in summary.",
        "The upcoming follow-up is listed; the draft summary is not visible until counselor_a "
        "publishes it (CNS-ENC-01).",
        mutating=False,
        fresh_state=False,
        checks=(("fourth_year", "summary:draft"), ("fourth_year", "appointment:upcoming:ANY")),
    ),
    _s(
        "STU-HIS-01",
        "Counseling",
        "Review a referred Student's history",
        "Student",
        "referred",
        "/portal/call-slips",
        "A completed Call Slip interview and a published follow-up Student Session Summary.",
        "Open Call Slips and the published Student Session Summary.",
        "The completed Call Slip and the summary are readable; referral reasons and the "
        "Counselor's evaluation are not shown.",
        mutating=False,
        fresh_state=False,
        checks=(("referred", "call_slip:completed"), ("referred", "summary:published")),
    ),
    _s(
        "STU-GM-03",
        "Good Moral",
        "Follow an issued certificate",
        "Student",
        "good_moral",
        "/portal/good-moral",
        "An ISSUED current-Student certificate and a self-cancelled duplicate.",
        "Open Good Moral requests and the issued request.",
        "The issued request shows its issuance; the cancelled duplicate keeps its reason.",
        mutating=False,
        fresh_state=False,
        checks=(("good_moral", "good_moral:ISSUED"),),
    ),
    _s(
        "STU-GM-04",
        "Good Moral",
        "Follow a pending graduate request",
        "Student",
        "alumni",
        "/portal/good-moral",
        "GRADUATED; a pending graduate request; a submitted Graduate Tracer.",
        "Open Good Moral requests and the Graduate Tracer.",
        "The graduate request is REQUESTED; the submitted Tracer is read-only.",
        mutating=False,
        fresh_state=False,
        checks=(("alumni", "good_moral:REQUESTED"), ("alumni", "tracer:submitted")),
    ),
    _s(
        "STU-GM-05",
        "Good Moral",
        "Receive a certificate the Counselor issues",
        "Student",
        "ar_17",
        "/portal/good-moral",
        "A REQUESTED request awaiting counselor_b.",
        "After CNS-GM-01, open the notification and the request.",
        "The request shows ISSUED with its issuance date.",
        preconditions="CNS-GM-01 has been performed.",
        related=("counselor_b",),
        mutating=False,
        checks=(("ar_17", "good_moral:REQUESTED"),),
    ),
    _s(
        "STU-GM-06",
        "Good Moral",
        "Follow a request through issuance",
        "Student",
        "ar_18",
        "/portal/good-moral",
        "A READY_FOR_ISSUANCE request awaiting counselor_a.",
        "Open the request before and after CNS-GM-02.",
        "The status moves from Ready for issuance to Issued.",
        related=("counselor_a",),
        mutating=False,
        checks=(("ar_18", "good_moral:READY_FOR_ISSUANCE"),),
    ),
    _s(
        "STU-CS-02",
        "Call Slips",
        "Receive a Call Slip issued from a referral",
        "Student",
        "ar_19",
        "/portal/call-slips",
        "A referral exists; no Call Slip yet.",
        "After CNS-REF-01, open the notification and the Call Slip.",
        "The Call Slip shows the report time; no referral content is visible.",
        preconditions="CNS-REF-01 has been performed.",
        related=("counselor_a",),
        mutating=False,
        checks=(("ar_19", "referral:no_action"),),
    ),
    _s(
        "STU-CS-03",
        "Call Slips",
        "Receive a Call Slip issued by staff",
        "Student",
        "ar_20",
        "/portal/call-slips",
        "A referral exists; no Call Slip yet.",
        "After GSS-REF-01, open the notification and the Call Slip.",
        "The Call Slip issued by gss_b is visible to the Student.",
        preconditions="GSS-REF-01 has been performed.",
        related=("gss_b",),
        mutating=False,
        checks=(("ar_20", "referral:no_action"),),
    ),
    _s(
        "STU-RI-03",
        "Routine Interview",
        "The Counselor's evaluation is never shown to the Student",
        "Student",
        "ar_21",
        "/portal/routine-interviews",
        "A submitted intake with the evaluation pending.",
        "Open the Routine Interview before and after CNS-RI-01.",
        "The Student sees the submitted intake only; the evaluation never appears.",
        related=("counselor_a",),
        mutating=False,
        fresh_state=False,
        checks=(("ar_21", "routine:evaluation_pending"),),
    ),
    _s(
        "STU-FB-01",
        "Feedback",
        "Give feedback after a completed session",
        "Student",
        "ar_22",
        "/portal/feedback",
        "A past Appointment still SCHEDULED with counselor_b.",
        "After CNS-APT-02, open the feedback invitation and submit the form.",
        "One Customer Feedback response is recorded for the completed session.",
        preconditions="CNS-APT-02 has been performed.",
        related=("counselor_b",),
        checks=(("ar_22", "appointment:past_scheduled"),),
    ),
    _s(
        "STU-APT-06",
        "Appointments",
        "See a missed session recorded as no-show",
        "Student",
        "ar_23",
        "/portal/appointments/my",
        "A past Appointment still SCHEDULED with counselor_c.",
        "After CNS-APT-03, open the Appointment.",
        "The Appointment shows No-show; the Student can book again.",
        preconditions="CNS-APT-03 has been performed.",
        related=("counselor_c",),
        mutating=False,
        checks=(("ar_23", "appointment:past_scheduled"),),
    ),
    _s(
        "STU-INV-04",
        "Individual Inventory",
        "Finish an Inventory draft while a Call Slip is open",
        "Student",
        "active_referral",
        "/portal/inventory/current",
        "Current Inventory draft; a referral and a LIVE Call Slip from gss_a.",
        "Open the Call Slip, then complete and submit the Inventory.",
        "The Inventory is submitted; the Call Slip is unaffected.",
        related=("gss_a",),
        checks=(("active_referral", "inventory:draft"), ("active_referral", "call_slip:live")),
    ),
    # --- Guidance Counselor -------------------------------------------------------------------
    _s(
        "CNS-APT-01",
        "Appointments",
        "Review the Counselor's upcoming Appointments",
        "Guidance Counselor",
        "counselor_a",
        "/portal/appointments/manage",
        "Upcoming in-person and ONLINE Appointments in counselor_a's caseload.",
        "Filter and open upcoming Appointments.",
        "Only counselor_a's caseload is listed, with Student, mode and time.",
        mutating=False,
        fresh_state=False,
        checks=(("counselor_a", "provider:upcoming_appointments"),),
    ),
    _s(
        "CNS-APT-02",
        "Appointments",
        "Complete a past Appointment and record the Encounter",
        "Guidance Counselor",
        "counselor_b",
        "/portal/appointments/manage",
        "ar_22 has a past Appointment with counselor_b that is still SCHEDULED.",
        "Mark the Appointment completed, then record its Counseling Encounter.",
        "The Appointment becomes COMPLETED and the Encounter is linked to it; ar_22 gets a "
        "feedback invitation.",
        related=("ar_22",),
        checks=(("ar_22", "appointment:past_scheduled"),),
    ),
    _s(
        "CNS-APT-03",
        "Appointments",
        "Mark a past Appointment as no-show",
        "Guidance Counselor",
        "counselor_c",
        "/portal/appointments/manage",
        "ar_23 has a past Appointment with counselor_c that is still SCHEDULED.",
        "Mark the Appointment as no-show.",
        "The Appointment becomes NO_SHOW; no Encounter is created.",
        related=("ar_23",),
        checks=(("ar_23", "appointment:past_scheduled"),),
    ),
    _s(
        "CNS-ENC-01",
        "Counseling",
        "Publish an unpublished Student Session Summary draft",
        "Guidance Counselor",
        "counselor_a",
        "/portal/counseling",
        "fourth_year has a walk-in Encounter with an unpublished Student Session Summary draft.",
        "Open the Encounter, edit the draft and publish it.",
        "The summary is published and fourth_year receives an in-app notification.",
        related=("fourth_year",),
        restrictions=_LIVE_EMAIL,
        checks=(("fourth_year", "summary:draft"),),
    ),
    _s(
        "CNS-RI-01",
        "Routine Interview",
        "Finalize a pending Routine Interview evaluation",
        "Guidance Counselor",
        "counselor_a",
        "/portal/routine-interviews",
        "ar_21 has a walk-in Encounter with a submitted intake and no evaluation.",
        "Open the Routine Interview, complete the evaluation and finalize it.",
        "The evaluation is finalized and linked to the existing Encounter.",
        related=("ar_21",),
        checks=(("ar_21", "routine:evaluation_pending"),),
    ),
    _s(
        "CNS-RI-02",
        "Routine Interview",
        "Evaluate a referred Student's Routine Interview",
        "Guidance Counselor",
        "counselor_b",
        "/portal/routine-interviews",
        "referred has a REFERRED Routine Interview with a submitted intake awaiting evaluation.",
        "Review the intake and finalize the evaluation.",
        "The evaluation is finalized; the Student never sees the Counselor's evaluation.",
        related=("referred",),
        checks=(("referred", "routine:evaluation_pending"),),
    ),
    _s(
        "CNS-REF-01",
        "Referrals and Call Slips",
        "Issue a Call Slip from a new referral",
        "Guidance Counselor",
        "counselor_a",
        "/portal/referrals",
        "ar_19 has a referral recorded by gss_a with no action yet.",
        "Open the referral and issue a Call Slip with a report time.",
        "A LIVE Call Slip is issued and ar_19 receives an in-app notification.",
        related=("ar_19", "gss_a"),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_19", "referral:no_action"),),
    ),
    _s(
        "CNS-REF-02",
        "Referrals and Call Slips",
        "Record a new referral",
        "Guidance Counselor",
        "counselor_c",
        "/portal/referrals/new",
        "Current satellite-campus Students in counselor_c's caseload.",
        "Record a referral for bg_57 (Una Nepomuceno) from a class adviser.",
        "The referral is saved with a reference code and appears in counselor_c's Work Queue.",
        related=("bg_57",),
        fresh_state=False,
        checks=(("bg_57", "lifecycle:CURRENT"),),
    ),
    _s(
        "CNS-INV-01",
        "Individual Inventory",
        "Review the Inventory roster and a submitted record",
        "Guidance Counselor",
        "counselor_a",
        "/portal/inventory",
        "Submitted, draft and missing current Inventories in counselor_a's caseload.",
        "Filter the roster by program and status; open a submitted Inventory.",
        "Drafts stay private to Students; submitted records open read-only.",
        mutating=False,
        fresh_state=False,
        checks=(("second_year", "inventory:submitted"), ("ar_07", "inventory:draft")),
    ),
    _s(
        "CNS-INV-02",
        "Individual Inventory",
        "Reopen a submitted Inventory for correction",
        "Guidance Counselor",
        "counselor_b",
        "/portal/inventory",
        "bg_03 (Camille Santos) has a submitted 2026-2027 Inventory.",
        "Reopen the Inventory, choosing the sections the Student must correct.",
        "The Inventory reopens for those sections; bg_03 is notified.",
        related=("bg_03",),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_03", "inventory:submitted"),),
    ),
    _s(
        "CNS-GM-01",
        "Good Moral",
        "Record the receipt, prepare and issue a certificate",
        "Guidance Counselor",
        "counselor_b",
        "/portal/good-moral",
        "ar_17 has a REQUESTED Good Moral request.",
        "Record the official receipt, prepare the certificate, issue it and print.",
        "The request becomes ISSUED; the certificate renders with the issuance date; ar_17 is "
        "notified.",
        related=("ar_17",),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_17", "good_moral:REQUESTED"),),
    ),
    _s(
        "CNS-GM-02",
        "Good Moral",
        "Issue and print a prepared certificate",
        "Guidance Counselor",
        "counselor_a",
        "/portal/good-moral",
        "ar_18 has a READY_FOR_ISSUANCE request with a recorded receipt.",
        "Issue the certificate and print it.",
        "The request becomes ISSUED and the printable certificate opens.",
        related=("ar_18",),
        checks=(("ar_18", "good_moral:READY_FOR_ISSUANCE"),),
    ),
    _s(
        "CNS-GM-03",
        "Good Moral",
        "Reprint an issued certificate",
        "Guidance Counselor",
        "counselor_b",
        "/portal/good-moral",
        "good_moral has an ISSUED current-Student certificate.",
        "Open the issued request and print the certificate again.",
        "The same issued certificate renders; nothing about the issuance changes.",
        mutating=False,
        fresh_state=False,
        related=("good_moral",),
        checks=(("good_moral", "good_moral:ISSUED"),),
    ),
    _s(
        "CNS-GM-04",
        "Good Moral",
        "Start an assisted Good Moral request for a Student",
        "Guidance Counselor",
        "counselor_c",
        "/portal/good-moral/start",
        "bg_54 (Paul Hernandez) is a current Student with a submitted Inventory and no request.",
        "Start a GCO-assisted request on the Student's behalf.",
        "A request with assisted initiation provenance appears for the Student.",
        related=("bg_54",),
        checks=(("bg_54", "good_moral:none"),),
    ),
    _s(
        "CNS-EC-01",
        "E-Counseling",
        "Request E-Counseling recording consent",
        "Guidance Counselor",
        "counselor_a",
        "/portal/appointments/manage",
        "ar_05 has an upcoming ONLINE Appointment with counselor_a; no consent requested.",
        "Open the Appointment's E-Counseling workspace and request recording consent.",
        "The request is recorded locally and ar_05 is asked to decide (STU-EC-01).",
        related=("ar_05",),
        restrictions="Starting or joining the call needs Daily enabled (operator-approved plan).",
        checks=(("ar_05", "appointment:upcoming:ONLINE"),),
    ),
    _s(
        "CNS-WQ-01",
        "Guidance Work Queue",
        "Work through the Guidance Work Queue",
        "Guidance Counselor",
        "counselor_a",
        "/portal/work",
        "Pending Good Moral, referral, Routine evaluation and Appointment items in caseload.",
        "Open the Work Queue and follow items to their records.",
        "Caseload items (Routine evaluations, referrals, Appointments) are limited to "
        "counselor_a's Colleges; Good Moral preparation and issuance are office-wide by design.",
        mutating=False,
        fresh_state=False,
        checks=(("counselor_a", "work_queue:items"),),
    ),
    _s(
        "CNS-MSG-01",
        "Guidance Messages",
        "Converse with a Student",
        "Guidance Counselor",
        "counselor_a",
        "/portal/messages",
        "An Appointment conversation with ar_14 started by counselor_a.",
        "Open the conversation, send a follow-up and resolve it when done.",
        "Messages appear in order; resolving keeps the thread readable.",
        related=("ar_14",),
        checks=(("ar_14", "messages:unread"),),
    ),
    _s(
        "CNS-ACT-01",
        "My Activity",
        "Review My Activity",
        "Guidance Counselor",
        "counselor_b",
        "/portal/account/activity",
        "counselor_b recorded referrals, Encounters, summaries and certificates during seeding.",
        "Open My Activity and filter by domain.",
        "Domain-rich activity items appear for counselor_b's own actions only.",
        mutating=False,
        fresh_state=False,
        checks=(("counselor_b", "activity:present"),),
    ),
    _s(
        "CNS-REP-01",
        "Reports",
        "Student Profiling report with academic filters",
        "Guidance Counselor",
        "counselor_a",
        "/portal/reports/student-profile",
        "Submitted Inventories across programs and year levels.",
        "Run the report, filter by College, Program and year level, and export it.",
        "Aggregated counts change with filters and stay within counselor_a's authorized scope.",
        mutating=False,
        fresh_state=False,
        checks=(("counselor_a", "reports:inventory_data"),),
    ),
    _s(
        "CNS-AVL-01",
        "Availability",
        "Maintain own availability",
        "Guidance Counselor",
        "counselor_c",
        "/portal/availability/me",
        "counselor_c has a weekday schedule.",
        "Add a dated unavailability in a future week without Appointments.",
        "The exception saves and removes those slots from Student booking.",
        fresh_state=False,
        checks=(("counselor_c", "availability:weekly"),),
    ),
    # --- Guidance Services Staff --------------------------------------------------------------
    _s(
        "GSS-REF-01",
        "Referrals and Call Slips",
        "Issue a Call Slip from a referral",
        "Guidance Services Staff",
        "gss_b",
        "/portal/referrals",
        "ar_20 has a referral recorded by counselor_b with no action yet.",
        "Open the referral and issue a Call Slip.",
        "A LIVE Call Slip is issued within gss_b's supervised scope.",
        related=("ar_20", "counselor_b"),
        restrictions=_LIVE_EMAIL,
        checks=(("ar_20", "referral:no_action"),),
    ),
    _s(
        "GSS-REF-02",
        "Referrals and Call Slips",
        "Record a new referral",
        "Guidance Services Staff",
        "gss_a",
        "/portal/referrals/new",
        "Current Students in counselor_a's caseload.",
        "Record a referral for bg_48 (Gerald Bonifacio).",
        "The referral is saved and visible to counselor_a.",
        related=("bg_48", "counselor_a"),
        fresh_state=False,
        checks=(("bg_48", "lifecycle:CURRENT"),),
    ),
    _s(
        "GSS-GM-01",
        "Good Moral",
        "Start an assisted Good Moral request",
        "Guidance Services Staff",
        "gss_a",
        "/portal/good-moral/start",
        "bg_17 (Bianca Marquez) has a submitted Inventory and no request.",
        "Start a GCO-assisted request and prepare it.",
        "The request is prepared; only a Counselor can issue it.",
        related=("bg_17",),
        checks=(("bg_17", "good_moral:none"),),
    ),
    _s(
        "GSS-EXIT-01",
        "Exit Interview",
        "Open an Exit Interview opportunity",
        "Guidance Services Staff",
        "gss_b",
        "/portal/exit-interviews",
        "bg_24 (Vincent Alvarez) is a fourth-year COED Student without an opportunity.",
        "Open a manual Exit Interview opportunity for the Student.",
        "The opportunity is OPEN; the Student can start the interview.",
        related=("bg_24",),
        checks=(("bg_24", "exit:none"),),
    ),
    _s(
        "GSS-WQ-01",
        "Guidance Work Queue",
        "Work Queue for supervised staff",
        "Guidance Services Staff",
        "gss_a",
        "/portal/work",
        "Referral and Appointment items in counselor_a's caseload.",
        "Open the Work Queue and follow an item.",
        "Items are limited to gss_a's supervised scope and operational records.",
        mutating=False,
        fresh_state=False,
        checks=(("gss_a", "work_queue:items"),),
    ),
    _s(
        "GSS-NEG-01",
        "Restricted content",
        "Staff cannot open confidential counseling content",
        "Guidance Services Staff",
        "gss_a",
        "/portal/routine-interviews",
        "Routine Interviews and Student Session Summaries exist in counselor_a's caseload.",
        "Try to open Routine Interviews, Counseling and Student Session Summaries.",
        "The workspaces are unavailable to Guidance Services Staff.",
        mutating=False,
        fresh_state=False,
        checks=(("gss_a", "capabilities:no_counseling"),),
    ),
    # --- Head Guidance Counselor --------------------------------------------------------------
    _s(
        "HGC-SUP-01",
        "Supervision",
        "Institution-wide Guidance Operations",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/operations",
        "Activity across every Counselor's caseload.",
        "Open Guidance Operations and review workload by Counselor.",
        "Counts cover all Colleges; Student content is not exposed in the overview.",
        mutating=False,
        fresh_state=False,
        checks=(("head_guidance", "designation:HEAD"),),
    ),
    _s(
        "HGC-ASN-01",
        "Supervision",
        "Reassign an upcoming Appointment",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/appointments/manage",
        "bg_02 (Marco Dizon) has an upcoming Appointment with counselor_a.",
        "Reassign the Appointment to another qualified Counselor.",
        "The Appointment's provider changes and both Counselors see the update.",
        related=("bg_02", "counselor_a"),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_02", "appointment:upcoming:ANY"),),
    ),
    _s(
        "HGC-EXIT-01",
        "Exit Interview",
        "Reopen a submitted Exit Interview for correction",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/exit-interviews",
        "ar_24 has a submitted 2026-2027 Exit Interview.",
        "Reopen the interview, choosing the sections to correct.",
        "The interview reopens for those sections; ar_24 is notified.",
        related=("ar_24",),
        restrictions=_LIVE_EMAIL + " Conflicts with STU-GM-02 on ar_24.",
        checks=(("ar_24", "exit:submitted"),),
    ),
    _s(
        "HGC-EXIT-02",
        "Exit Interview",
        "Open an Exit Interview opportunity",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/exit-interviews",
        "bg_28 (Noel Gonzales) is a fourth-year Student without an opportunity.",
        "Open a manual opportunity.",
        "The opportunity is OPEN for the Student.",
        related=("bg_28",),
        checks=(("bg_28", "exit:none"),),
    ),
    _s(
        "HGC-REP-01",
        "Reports",
        "Reports and exports across the institution",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/reports",
        "Inventory, Exit Interview and Graduate Tracer data across campuses.",
        "Run the Student Profiling and Graduate Tracer reports with filters; export each.",
        "Aggregates include every campus; exports match the on-screen totals.",
        mutating=False,
        fresh_state=False,
        checks=(
            ("head_guidance", "reports:inventory_data"),
            ("head_guidance", "reports:tracer_data"),
        ),
    ),
    _s(
        "HGC-FB-01",
        "Feedback",
        "Customer Feedback and CSM results",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/feedback",
        "Synthetic Customer Feedback and CSM responses with different score patterns.",
        "Open both result lists and a response.",
        "Responses are readable with their scores; optional text may be empty.",
        mutating=False,
        fresh_state=False,
        checks=(("head_guidance", "feedback:responses"),),
    ),
    _s(
        "HGC-AY-01",
        "Academic Years",
        "Review Academic Year configuration",
        "Head Guidance Counselor",
        "head_guidance",
        "/portal/academic-years",
        "2024-2025, 2025-2026 and the current 2026-2027.",
        "Open Academic Years and review the current year.",
        "2026-2027 is current; historical years remain listed.",
        mutating=False,
        fresh_state=False,
        restrictions="Do not change the current Academic Year during UAT: every scenario uses it.",
        checks=(("head_guidance", "academic_year:current"),),
    ),
    # --- IT Administrator ---------------------------------------------------------------------
    _s(
        "ITA-ACC-01",
        "Account management",
        "Create, disable and re-enable an account",
        "IT Administrator",
        "it_admin",
        "/portal/accounts/new",
        "IT Administrator with step-up authentication available.",
        "Create a new synthetic Student account, disable it, then enable it again.",
        "Each change is recorded; the new account appears in the account list.",
        restrictions="Uses an evaluator-chosen synthetic email; do not modify dataset accounts.",
        fresh_state=False,
        checks=(("it_admin", "role:IT_ADMIN"),),
    ),
    _s(
        "ITA-POL-01",
        "Access policy",
        "Grant and revoke a capability override",
        "IT Administrator",
        "it_admin_2",
        "/portal/accounts",
        "officer_no_designation has no effective capabilities.",
        "Open the officer's access page, grant one capability with a reason, then revoke it.",
        "The effective access shows the override while active; the audit trail records both.",
        related=("officer_no_designation",),
        fresh_state=False,
        checks=(("officer_no_designation", "capabilities:none"),),
    ),
    _s(
        "ITA-ORG-01",
        "Organization",
        "Review Counselor responsibilities and affiliations",
        "IT Administrator",
        "it_admin",
        "/portal/organization/responsibilities",
        "Nine College responsibilities across three Counselors.",
        "Review responsibilities and Student affiliations.",
        "Every College except Graduate School has exactly one Counselor.",
        mutating=False,
        fresh_state=False,
        restrictions="Do not reassign responsibilities: Counselor caseloads drive most scenarios.",
        checks=(("counselor_a", "responsibility:3"), ("counselor_c", "responsibility:4")),
    ),
    _s(
        "ITA-PLT-01",
        "Platform Operations",
        "Platform health and email delivery",
        "IT Administrator",
        "it_admin",
        "/portal/platform",
        "Platform Operations available to IT Administrators.",
        "Open Health, Email delivery and Environment.",
        "Dependency status and delivery history display without Student content.",
        mutating=False,
        fresh_state=False,
        restrictions="Maintenance mode affects every evaluator; schedule it separately.",
        checks=(("it_admin", "role:IT_ADMIN"),),
    ),
    _s(
        "ITA-NEG-01",
        "Restricted content",
        "IT Administrators cannot read guidance records",
        "IT Administrator",
        "it_admin_2",
        "/portal/counseling",
        "Confidential guidance records exist.",
        "Try to open Counseling, Inventory and Routine Interview workspaces.",
        "The workspaces are unavailable to IT Administrators.",
        mutating=False,
        fresh_state=False,
        checks=(("it_admin_2", "capabilities:no_counseling"),),
    ),
    # --- Data Protection Officer --------------------------------------------------------------
    _s(
        "DPO-RET-01",
        "Privacy governance",
        "Read-only retention oversight",
        "Data Protection Officer",
        "dpo",
        "/portal/privacy/retention",
        "Code-owned retention register with three NOT_ADOPTED categories.",
        "Open Retention Policies.",
        "Three categories show 'Not adopted' with no period; no rule, case or hold controls exist.",
        mutating=False,
        fresh_state=False,
        checks=(("dpo", "capability:retention_view"),),
    ),
    _s(
        "DPO-NOT-01",
        "Privacy governance",
        "Review and publish a Privacy Notice revision",
        "Data Protection Officer",
        "dpo",
        "/portal/privacy/notices",
        "A published staging Privacy Notice and an unpublished draft revision.",
        "Review the draft revision and publish it.",
        "The revision becomes current; users are asked to acknowledge it.",
        restrictions="Publishing prompts every signed-in user; schedule it with the UAT lead.",
        checks=(("dpo", "privacy:draft_revision"),),
    ),
    _s(
        "DPO-ACT-01",
        "Privacy governance",
        "Privacy activity and export",
        "Data Protection Officer",
        "dpo_2",
        "/portal/privacy/activity",
        "Account and privacy activity recorded during seeding.",
        "Filter privacy activity and export it.",
        "The export contains activity metadata, never confidential content.",
        mutating=False,
        fresh_state=False,
        checks=(("dpo_2", "capability:activity_export"),),
    ),
    _s(
        "DPO-NEG-01",
        "Privacy governance",
        "Retired disposition operations are unavailable",
        "Data Protection Officer",
        "dpo_2",
        "/portal/privacy/retention",
        "The disposition engine is absent from the canonical system.",
        "Try the old /portal/privacy/retention/rules and /cases links.",
        "Both return Not Found; no rule, case, hold or approval action exists.",
        mutating=False,
        fresh_state=False,
        checks=(("dpo_2", "capability:no_retention_manage"),),
    ),
    _s(
        "DPO-NEG-02",
        "Restricted content",
        "The DPO cannot read guidance records",
        "Data Protection Officer",
        "dpo",
        "/portal/counseling",
        "Confidential guidance records exist.",
        "Try to open Counseling, Inventory and Graduate Tracer responses.",
        "The workspaces are unavailable to the DPO.",
        mutating=False,
        fresh_state=False,
        checks=(("dpo", "capabilities:no_counseling"),),
    ),
    # --- Negative authorization and lifecycle -------------------------------------------------
    _s(
        "NEG-01",
        "Negative authorization",
        "A disabled staff account cannot sign in",
        "Guidance Services Staff",
        "former_staff",
        "/login",
        "former_staff is disabled.",
        "Attempt Password Access with the account email.",
        "Sign-in does not proceed; no session is created.",
        mutating=False,
        fresh_state=False,
        checks=(("former_staff", "account:disabled"),),
    ),
    _s(
        "NEG-02",
        "Negative authorization",
        "A disabled Student account cannot sign in",
        "Student",
        "bg_65",
        "/login",
        "bg_65 is disabled.",
        "Attempt Password Access with the account email.",
        "Sign-in does not proceed; no session is created.",
        mutating=False,
        fresh_state=False,
        checks=(("bg_65", "account:disabled"),),
    ),
    _s(
        "NEG-03",
        "Negative authorization",
        "An undesignated Institutional Officer is refused",
        "Institutional Officer",
        "officer_no_designation",
        "/portal",
        "INSTITUTIONAL_OFFICER with no designation and no capabilities.",
        "Sign in and try Privacy, Accounts and Reports.",
        "Only the account's own pages are available; protected workspaces are refused.",
        mutating=False,
        fresh_state=False,
        preconditions="Credential issued explicitly with --account officer_no_designation.",
        checks=(("officer_no_designation", "capabilities:none"),),
    ),
    _s(
        "NEG-04",
        "Negative authorization",
        "A Counselor without responsibility sees no Students",
        "Guidance Counselor",
        "unassigned_counselor",
        "/portal/inventory",
        "COUNSELOR with no College responsibility.",
        "Open the Inventory roster, Appointments and referrals.",
        "No Student is listed in the roster, Appointments or referrals; only office-wide Good "
        "Moral work appears, by design.",
        mutating=False,
        fresh_state=False,
        preconditions="Credential issued explicitly with --account unassigned_counselor.",
        checks=(("unassigned_counselor", "responsibility:0"),),
    ),
    _s(
        "NEG-05",
        "Negative authorization",
        "A Student cannot open another Student's record",
        "Student",
        "ar_01",
        "/portal/appointments/my",
        "ar_03 has an upcoming Appointment; ar_01 has none.",
        "Open ar_03's Appointment URL (provided by the UAT lead) while signed in as ar_01.",
        "The record is not found; nothing about ar_03 is disclosed.",
        mutating=False,
        fresh_state=False,
        related=("ar_03",),
        checks=(("ar_03", "appointment:upcoming:ANY"),),
    ),
    _s(
        "NEG-06",
        "Negative authorization",
        "Counselors cannot see another caseload",
        "Guidance Counselor",
        "counselor_c",
        "/portal/inventory",
        "counselor_a's Students (for example ar_07) are outside counselor_c's scope.",
        "Search the roster for ar_07 and open counselor_a's Students' records by URL.",
        "Out-of-scope Students are not listed and their records are not found.",
        mutating=False,
        fresh_state=False,
        related=("ar_07",),
        checks=(("counselor_c", "responsibility:4"),),
    ),
    # --- Independent participants added for the 40-person UAT allocation --------------------
    _s(
        "STU-GT-03",
        "Graduate Tracer",
        "Complete an independent Alumni Tracer draft",
        "Student",
        "ar_25",
        "/portal/graduate-tracer",
        "GRADUATED; historical Inventory and submitted Exit Interview; Tracer draft.",
        "Complete the remaining Tracer fields, save, then submit.",
        "The response becomes SUBMITTED and appears in the Head's Graduate Tracer report.",
        related=("head_guidance",),
        checks=(
            ("ar_25", "lifecycle:GRADUATED"),
            ("ar_25", "exit:historical_submitted"),
            ("ar_25", "tracer:draft"),
        ),
    ),
    _s(
        "STU-GM-07",
        "Good Moral",
        "Request an independent Alumni Good Moral certificate",
        "Student",
        "ar_26",
        "/portal/good-moral/request",
        "GRADUATED; submitted historical Exit Interview and Tracer; no Good Moral request.",
        "Request a graduate Good Moral certificate and review its status.",
        "A graduate request is REQUESTED; the submitted Tracer and history remain unchanged.",
        checks=(
            ("ar_26", "lifecycle:GRADUATED"),
            ("ar_26", "exit:historical_submitted"),
            ("ar_26", "tracer:submitted"),
            ("ar_26", "good_moral:none"),
        ),
    ),
    _s(
        "ITA-PLT-02",
        "Platform Operations",
        "Review platform readiness as the third ITSO evaluator",
        "IT Administrator",
        "it_admin_3",
        "/portal/platform",
        "Canonical IT_ADMIN authority; no confidential guidance access.",
        "Review Health, Email delivery and Environment without changing maintenance mode.",
        "Operational status is visible; confidential guidance workspaces remain unavailable.",
        mutating=False,
        fresh_state=False,
        restrictions="Do not toggle maintenance mode or edit seeded accounts or shared policy.",
        checks=(("it_admin_3", "role:IT_ADMIN"), ("it_admin_3", "capabilities:no_counseling")),
    ),
    # --- Promoted background Students completing the College distribution -------------------
    _s(
        "STU-APT-07",
        "Appointments",
        "Book a Counseling Appointment (COENG)",
        "Student",
        "bg_47",
        "/portal/appointments/book",
        "COENG Student with a submitted Inventory; no Appointments.",
        "Choose Counseling, counselor_a, a delivery mode and an available slot; confirm.",
        "The Appointment is SCHEDULED for counselor_a and appears under My appointments.",
        related=("counselor_a",),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_47", "appointment:none"), ("bg_47", "inventory:submitted")),
    ),
    _s(
        "STU-GM-08",
        "Good Moral",
        "Follow a GCO-assisted Good Moral request",
        "Student",
        "bg_54",
        "/portal/good-moral",
        "CFAST Student with a submitted Inventory and no Good Moral request.",
        "After CNS-GM-04, open the notification and the request counselor_c started.",
        "The request shows that the Guidance Office started it on the Student's behalf; the "
        "Student can follow its status.",
        preconditions="CNS-GM-04 has been performed; do not request a certificate before it.",
        related=("counselor_c",),
        mutating=False,
        checks=(("bg_54", "good_moral:none"),),
    ),
    _s(
        "STU-MSG-03",
        "Guidance Messages",
        "Start a conversation with the Guidance Office (satellite caseload)",
        "Student",
        "bg_54",
        "/portal/messages/new",
        "CFAST Student in counselor_c's caseload; no Office conversation.",
        "Send a new message to the Guidance Office.",
        "An Office thread is created and routed to counselor_c.",
        related=("counselor_c",),
        checks=(("bg_54", "messages:no_office_thread"),),
    ),
    _s(
        "STU-FB-02",
        "Feedback",
        "Give feedback after a completed session (satellite caseload)",
        "Student",
        "bg_55",
        "/portal/feedback",
        "A completed in-person session with counselor_c and an open feedback invitation.",
        "Open the feedback invitation and submit the Customer Feedback form.",
        "One Customer Feedback response is recorded for the completed session.",
        related=("counselor_c",),
        checks=(("bg_55", "feedback:invitation_pending"),),
    ),
    _s(
        "STU-APT-08",
        "Appointments",
        "Book a Counseling Appointment (CANR)",
        "Student",
        "bg_56",
        "/portal/appointments/book",
        "CANR Student with a submitted Inventory; no Appointments.",
        "Choose Counseling, counselor_c, a delivery mode and an available slot; confirm.",
        "The Appointment is SCHEDULED for counselor_c and appears under My appointments.",
        related=("counselor_c",),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_56", "appointment:none"), ("bg_56", "inventory:submitted")),
    ),
    _s(
        "STU-GM-09",
        "Good Moral",
        "Request a current-Student Good Moral certificate (COTT)",
        "Student",
        "bg_58",
        "/portal/good-moral/request",
        "COTT Student with a submitted Inventory and no request.",
        "Request a certificate for the current semester.",
        "A REQUESTED request appears in the office-wide Good Moral queue; the Student can follow "
        "its status.",
        checks=(("bg_58", "good_moral:none"), ("bg_58", "inventory:submitted")),
    ),
    _s(
        "STU-APT-09",
        "Appointments",
        "Reschedule an upcoming Appointment (satellite caseload)",
        "Student",
        "bg_59",
        "/portal/appointments/my",
        "An upcoming in-person Counseling Appointment with counselor_c.",
        "Open the Appointment and reschedule it to another available slot.",
        "The Appointment moves to the new time; its history records the change.",
        related=("counselor_c",),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_59", "appointment:upcoming:IN_PERSON"),),
    ),
    _s(
        "STU-APT-10",
        "Appointments",
        "Book a Counseling Appointment (Entienza)",
        "Student",
        "bg_60",
        "/portal/appointments/book",
        "Entienza Student with a submitted Inventory; no Appointments.",
        "Choose Counseling, counselor_c, a delivery mode and an available slot; confirm.",
        "The Appointment is SCHEDULED for counselor_c and appears under My appointments.",
        related=("counselor_c",),
        restrictions=_LIVE_EMAIL,
        checks=(("bg_60", "appointment:none"), ("bg_60", "inventory:submitted")),
    ),
    # --- Pending pre-defense features -------------------------------------------------------
    _s(
        "PND-REM-01",
        "Appointment Reminders",
        "Receive a reminder before an upcoming Appointment",
        "Student",
        "ar_03",
        "/portal/notifications",
        "Upcoming Appointment.",
        "Wait for the reminder window.",
        "Defined when the Appointment Reminders feature is merged.",
        readiness=Readiness.PENDING_IMPLEMENTATION,
        restrictions="Feature not implemented on this baseline; no API, model or schedule exists.",
    ),
    _s(
        "PND-SVC-01",
        "Service Catalog Expansion",
        "Book a non-Counseling guidance service",
        "Student",
        "ar_02",
        "/portal/appointments/book",
        "Only the canonical Counseling Service is bookable today.",
        "Book an expanded catalog service.",
        "Defined when the Service Catalog Expansion feature is merged.",
        readiness=Readiness.PENDING_IMPLEMENTATION,
        restrictions="Feature not implemented on this baseline; no additional services exist.",
    ),
    _s(
        "PND-FUP-01",
        "Shared Guidance Follow-Up",
        "Manage a shared follow-up between staff",
        "Guidance Counselor",
        "counselor_a",
        "/portal/work",
        "Completed sessions with follow-up needs.",
        "Create and hand over a shared follow-up.",
        "Defined when the Shared Guidance Follow-Up Management feature is merged.",
        readiness=Readiness.PENDING_IMPLEMENTATION,
        restrictions="Feature not implemented on this baseline; no model or workspace exists.",
    ),
)
SCENARIOS_BY_ID = {scenario.id: scenario for scenario in SCENARIOS}


class ManifestError(RuntimeError):
    """The manifest contradicts itself or the canonical identity policy."""


def scenarios_for(account_key: str) -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS if s.account == account_key)


def validate_manifest() -> None:
    """Static consistency rules; verification against the database lives in ``verify``."""

    roles = {definition.code for definition in ROLE_DEFINITIONS}
    designations = {definition.code for definition in DESIGNATION_DEFINITIONS}
    for attribute, label in (
        ("key", "account key"),
        ("institutional_id", "institutional ID"),
        ("email_local_part", "email"),
    ):
        values = [getattr(account, attribute) for account in ACCOUNTS]
        if len(values) != len(set(values)):
            raise ManifestError(f"Every {label} must be unique.")
    if len({s.id for s in SCENARIOS}) != len(SCENARIOS):
        raise ManifestError("Every scenario ID must be unique.")
    for account in ACCOUNTS:
        if account.role not in roles:
            raise ManifestError(f"{account.key}: unknown canonical role {account.role}.")
        for code in account.designations:
            if code not in designations or not designation_role_compatible(
                designation_code=code, role_code=account.role
            ):
                raise ManifestError(f"{account.key}: designation {code} is not valid for its role.")
        if account.auth == AuthPlan.DISABLED and account.suitability != Suitability.RESTRICTED:
            raise ManifestError(f"{account.key}: a disabled account must be RESTRICTED.")
        if isinstance(account, StudentSpec) != account.is_student:
            raise ManifestError(
                f"{account.key}: only Student specifications have the STUDENT role."
            )
    for scenario in SCENARIOS:
        account = ACCOUNTS_BY_KEY.get(scenario.account)
        if account is None:
            raise ManifestError(f"{scenario.id}: unknown account {scenario.account}.")
        if stakeholder(account) != scenario.role:
            raise ManifestError(f"{scenario.id}: {scenario.account} is not a {scenario.role}.")
        for key in (*scenario.related, *(check[0] for check in scenario.checks)):
            if key not in ACCOUNTS_BY_KEY:
                raise ManifestError(f"{scenario.id}: unknown related account {key}.")
        executable = scenario.readiness == Readiness.EXECUTABLE
        if executable and not scenario.checks:
            raise ManifestError(
                f"{scenario.id}: an executable scenario needs initial-state checks."
            )
        if not executable and scenario.checks:
            raise ManifestError(f"{scenario.id}: a pending scenario cannot claim a verified state.")
        if account.suitability == Suitability.RESTRICTED and not scenario.id.startswith("NEG-"):
            raise ManifestError(f"{scenario.id}: restricted accounts support negative tests only.")
        if account.suitability == Suitability.BACKGROUND:
            raise ManifestError(f"{scenario.id}: background accounts are never the actor.")
    actors = {scenario.account for scenario in SCENARIOS}
    for account in ACCOUNTS:
        if account.suitability == Suitability.PARTICIPANT and account.key not in actors:
            raise ManifestError(f"{account.key}: a UAT-ready account needs at least one scenario.")
    allocated = [key for keys in UAT_40_ALLOCATION.values() for key in keys]
    if len(allocated) != 40 or len(set(allocated)) != 40:
        raise ManifestError("The 40-person allocation requires 40 distinct accounts.")
    if {category: len(keys) for category, keys in UAT_40_ALLOCATION.items()} != (
        UAT_40_STAKEHOLDER_COUNTS
    ):
        raise ManifestError("The 40-person allocation must match the stakeholder distribution.")
    if {college: len(keys) for college, keys in UAT_40_STUDENT_COLLEGES.items()} != (
        UAT_40_STUDENT_QUOTA
    ):
        raise ManifestError("The current-Student allocation must match the College distribution.")
    for college, keys in UAT_40_STUDENT_COLLEGES.items():
        for key in keys:
            account = ACCOUNTS_BY_KEY.get(key)
            if (
                not isinstance(account, StudentSpec)
                or account.college_code != college
                or not account.affiliated
            ):
                raise ManifestError(f"{key}: not a current {college} Student.")
    for category, keys in UAT_40_ALLOCATION.items():
        for key in keys:
            account = ACCOUNTS_BY_KEY.get(key)
            if (
                account is None
                or account.suitability != Suitability.PARTICIPANT
                or account.auth != AuthPlan.CREDENTIAL
            ):
                raise ManifestError(f"{key}: allocation requires a credential-ready participant.")
            if not any(
                scenario.readiness == Readiness.EXECUTABLE for scenario in scenarios_for(key)
            ):
                raise ManifestError(f"{key}: an allocated participant needs a scenario.")
            if category in {"Current Student", "Alumni"}:
                expected = (
                    Lifecycle.CURRENT if category == "Current Student" else Lifecycle.GRADUATED
                )
                if not isinstance(account, StudentSpec) or account.lifecycle != expected:
                    raise ManifestError(f"{key}: incorrect lifecycle for {category} allocation.")
            elif stakeholder(account) != (
                "IT Administrator" if category == "ITSO Personnel" else category
            ):
                raise ManifestError(f"{key}: incorrect stakeholder for {category} allocation.")


validate_manifest()

__all__ = [
    "ACCOUNTS",
    "ACCOUNTS_BY_KEY",
    "ManifestError",
    "Readiness",
    "SCENARIOS",
    "SCENARIOS_BY_ID",
    "UAT_40_ALLOCATION",
    "UAT_40_STAKEHOLDER_COUNTS",
    "UAT_40_STUDENT_COLLEGES",
    "UAT_40_STUDENT_QUOTA",
    "Scenario",
    "email_for",
    "scenarios_for",
    "stakeholder",
    "validate_manifest",
]
