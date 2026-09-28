"""Announcement, Resource, and Privacy Governance content for the demo (data only).

Publications describe ordinary Guidance and Counseling Office work. Privacy artifacts are
explicitly labelled as staging demonstration material so they cannot be mistaken for approved
University policy. The single external link points at a stable public WHO fact sheet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnnouncementSpec:
    key: str
    author: str  # persona key
    title: str
    body_markdown: str
    audience: str
    state: str  # DRAFT, PUBLISHED, or ARCHIVED
    is_pinned: bool = False
    # Business days before the anchor it was published, or a fixed (y, m, d, h, min) moment.
    published_days_ago: int | None = None
    published_on: tuple[int, int, int, int, int] | None = None
    expires_in_business_days: int | None = None


@dataclass(frozen=True)
class ResourceSpec:
    key: str
    author: str
    title: str
    body_markdown: str
    category: str
    kind: str
    audience: str
    state: str
    display_order: int
    external_url: str = ""
    published_days_ago: int | None = None
    published_on: tuple[int, int, int, int, int] | None = None


ANNOUNCEMENTS = (
    AnnouncementSpec(
        key="consultation_hours",
        author="head_guidance",
        title="Guidance consultation hours for the first semester",
        body_markdown=(
            "The Guidance and Counseling Office is open for consultations **Monday to Friday, "
            "8:00 AM to 12:00 NN and 1:00 PM to 5:00 PM**.\n\n"
            "- Book a counseling appointment in COMPASS under **Appointments**.\n"
            "- Walk-ins are welcome, but booked students are served first.\n"
            "- Online sessions are available for booked counseling appointments.\n\n"
            "Please complete your Individual Inventory for this Academic Year before your first "
            "session so your counselor can prepare."
        ),
        audience="STUDENTS",
        state="PUBLISHED",
        is_pinned=True,
        published_days_ago=14,
    ),
    AnnouncementSpec(
        key="wellness_week",
        author="counselor_a",
        title="Student Wellness Week: short sessions on sleep, study habits, and stress",
        body_markdown=(
            "Join the Guidance and Counseling Office for short, drop-in sessions during Student "
            "Wellness Week.\n\n"
            "1. **Sleep and study routines** - practical tips for exam weeks\n"
            "2. **Managing academic stress** - planning a realistic week\n"
            "3. **Asking for help** - how to approach instructors and the Guidance Office\n\n"
            "Sessions are held at the GCO conference room. No registration is needed."
        ),
        audience="ALL_AUTHENTICATED",
        state="PUBLISHED",
        published_days_ago=6,
        expires_in_business_days=15,
    ),
    AnnouncementSpec(
        key="midterm_schedule",
        author="guidance_staff",
        title="Office schedule during the midterm examination week",
        body_markdown=(
            "During the midterm examination week, the Guidance and Counseling Office will "
            "prioritize scheduled appointments and certificate releases in the morning. "
            "Afternoon walk-in consultations continue as usual."
        ),
        audience="PUBLIC",
        state="PUBLISHED",
        published_days_ago=3,
        expires_in_business_days=12,
    ),
    AnnouncementSpec(
        key="evaluation_reminder",
        author="head_guidance",
        title="Reminder: finalize pending Routine Interview evaluations",
        body_markdown=(
            "Counselors, please finalize Counselor Evaluations for completed Routine Interviews "
            "within the week the session took place. Linked Counseling Encounters must be "
            "recorded first."
        ),
        audience="GCO_PERSONNEL",
        state="PUBLISHED",
        published_days_ago=2,
    ),
    AnnouncementSpec(
        key="career_seminar_draft",
        author="guidance_staff",
        title="Career planning seminar for graduating students",
        body_markdown=(
            "The Guidance and Counseling Office will hold a half-day career planning seminar for "
            "graduating students. Topics: writing a résumé, preparing for interviews, and "
            "planning for licensure examinations. Date and venue to follow."
        ),
        audience="STUDENTS",
        state="DRAFT",
    ),
    AnnouncementSpec(
        key="inventory_reminder_2025",
        author="former_staff",
        title="Reminder: submit your Individual Inventory for AY 2025-2026",
        body_markdown=(
            "All enrolled students are reminded to submit their Individual Inventory for "
            "Academic Year 2025-2026 in COMPASS within the first two weeks of the semester."
        ),
        audience="STUDENTS",
        state="ARCHIVED",
        published_on=(2025, 8, 11, 8, 30),
    ),
)

RESOURCES = (
    ResourceSpec(
        key="academic_stress",
        author="counselor_a",
        title="Managing Academic Stress",
        body_markdown=(
            "Stress is common when several deadlines fall in the same week. A few habits help:\n\n"
            "- **Plan the week on one page.** List deadlines and exams, then block study time.\n"
            "- **Break large tasks down.** Start with a 25-minute session on the first step.\n"
            "- **Protect sleep.** Late-night cramming lowers recall the next day.\n"
            "- **Talk to someone.** Classmates, family, instructors, or the Guidance Office.\n\n"
            "If stress keeps you from attending class or finishing requirements, book an "
            "appointment with your counselor."
        ),
        category="MENTAL_HEALTH",
        kind="ARTICLE",
        audience="STUDENTS",
        state="PUBLISHED",
        display_order=10,
        published_days_ago=20,
    ),
    ResourceSpec(
        key="consultation_guide",
        author="head_guidance",
        title="Preparing for a Guidance Consultation",
        body_markdown=(
            "A consultation is a private conversation with a counselor about anything affecting "
            "your studies or well-being.\n\n"
            "**Before your session**\n\n"
            "1. Submit your Individual Inventory for the current Academic Year.\n"
            "2. Complete the Routine Interview intake if COMPASS asks you to.\n"
            "3. Note two or three things you want to talk about.\n\n"
            "**During your session**, you decide what to share. Your counselor may suggest next "
            "steps and a follow-up schedule."
        ),
        category="COUNSELING",
        kind="ARTICLE",
        audience="PUBLIC",
        state="PUBLISHED",
        display_order=20,
        published_days_ago=20,
    ),
    ResourceSpec(
        key="time_management",
        author="counselor_b",
        title="Study and Time-Management Resources",
        body_markdown=(
            "Useful routines shared by students and counselors:\n\n"
            "- **Weekly review block:** one fixed hour per major subject each week.\n"
            "- **Two-list method:** a *must finish today* list and a *can wait* list.\n"
            "- **Group-work agreements:** write down who does what and by when.\n"
            "- **Exam-week plan:** start reviewing five days before, not the night before."
        ),
        category="ACADEMIC_SUPPORT",
        kind="ARTICLE",
        audience="STUDENTS",
        state="PUBLISHED",
        display_order=30,
        published_days_ago=12,
    ),
    ResourceSpec(
        key="who_mental_health",
        author="counselor_a",
        title="World Health Organization: Mental health fact sheet",
        body_markdown=(
            "An overview from the World Health Organization of what mental health is, what "
            "affects it, and how communities can support it."
        ),
        category="WELLNESS",
        kind="EXTERNAL_LINK",
        audience="ALL_AUTHENTICATED",
        state="PUBLISHED",
        display_order=40,
        external_url=(
            "https://www.who.int/news-room/fact-sheets/detail/"
            "mental-health-strengthening-our-response"
        ),
        published_days_ago=9,
    ),
    ResourceSpec(
        key="career_checklist_draft",
        author="guidance_staff",
        title="Career Readiness Checklist for Graduating Students",
        body_markdown=(
            "- Update your résumé and ask a faculty member to review it.\n"
            "- Request your Good Moral certificate early if an employer needs it.\n"
            "- Complete your Exit Interview before graduation."
        ),
        category="CAREER",
        kind="ARTICLE",
        audience="STUDENTS",
        state="DRAFT",
        display_order=50,
    ),
    ResourceSpec(
        key="orientation_2025",
        author="head_guidance",
        title="First-Semester Guidance Orientation Notes, AY 2025-2026",
        body_markdown=(
            "Notes from the AY 2025-2026 first-semester orientation: office hours, how to book "
            "appointments, and how to submit the Individual Inventory."
        ),
        category="GENERAL",
        kind="ARTICLE",
        audience="STUDENTS",
        state="ARCHIVED",
        display_order=90,
        published_on=(2025, 8, 12, 9, 0),
    ),
)

# --- Privacy Governance ----------------------------------------------------------------------

DEMO_POLICY_REFERENCE = "Staging demonstration only - not an approved UCN retention schedule"

RETENTION_POLICIES = (
    {
        "code": "DEMO-RET-COUNSELING",
        "name": "Staging demo: counseling and interview records",
        "record_categories": ["COUNSELING", "ROUTINE_INTERVIEW", "REFERRAL", "CALL_SLIP"],
        "scope_summary": (
            "Staging demonstration policy covering Counseling Encounters, Routine Interviews, "
            "Referrals, and Call Slips recorded in COMPASS."
        ),
        "retention_trigger_summary": "The Student's last recorded Guidance interaction.",
        "retention_period_summary": "Illustrative only: five years after the trigger.",
        "disposition_summary": (
            "Illustrative only: review by the Data Protection Officer before secure disposal. "
            "COMPASS does not execute retention actions."
        ),
        "policy_reference": DEMO_POLICY_REFERENCE,
        "effective_on": (2026, 8, 3),
        "review_due_on": (2027, 8, 3),
    },
    {
        "code": "DEMO-RET-PROFILING",
        "name": "Staging demo: student profiling and outcome records",
        "record_categories": [
            "INDIVIDUAL_INVENTORY",
            "EXIT_INTERVIEW",
            "GRADUATE_TRACER",
            "CUSTOMER_FEEDBACK",
        ],
        "scope_summary": (
            "Staging demonstration policy covering Individual Inventories, Exit Interviews, "
            "Graduate Tracer responses, and Customer Feedback/CSM responses."
        ),
        "retention_trigger_summary": "Graduation or separation from the University.",
        "retention_period_summary": "Illustrative only: three years after the trigger.",
        "disposition_summary": (
            "Illustrative only: aggregate reports may be kept; identifiable responses are "
            "reviewed for disposal. COMPASS does not execute retention actions."
        ),
        "policy_reference": DEMO_POLICY_REFERENCE,
        "effective_on": (2026, 8, 3),
        "review_due_on": (2027, 8, 3),
    },
)

PRIVACY_NOTICE = {
    "code": "DEMO-GCO-STUDENT-SERVICES",
    "name": "Guidance Services Privacy Notice (staging demo)",
}
PRIVACY_NOTICE_PUBLISHED = {
    "title": "Guidance Services Privacy Notice (staging demonstration)",
    "audiences": ["PUBLIC", "STUDENT"],
    "summary": (
        "Staging demonstration notice describing how the Guidance and Counseling Office uses "
        "student information in COMPASS. It is not an official University privacy notice."
    ),
    "body": (
        "**Staging demonstration content.** This notice illustrates the Privacy Notice workflow "
        "in COMPASS and has not been approved by the University.\n\n"
        "**What we collect.** Information you provide in your Individual Inventory, Routine "
        "Interview intake, appointment requests, and feedback forms.\n\n"
        "**Why we use it.** To provide counseling, referral follow-up, certification, and "
        "student support services, and to produce aggregate reports without identifying you.\n\n"
        "**Who can see it.** Only authorized Guidance personnel within their assigned scope. "
        "Counseling content is limited to your assigned counselor.\n\n"
        "**Your choices.** You may ask the Guidance and Counseling Office about your records at "
        "any time."
    ),
    "requires_acknowledgment": True,
    "effective_on": (2026, 8, 3),
}
PRIVACY_NOTICE_DRAFT = {
    "title": "Guidance Services Privacy Notice (staging demonstration, revision 2 draft)",
    "audiences": ["PUBLIC", "STUDENT"],
    "summary": (
        "Draft revision clarifying online counseling sessions. Staging demonstration content; not "
        "an official University privacy notice."
    ),
    "body": (
        "**Staging demonstration content.** Draft revision for review.\n\n"
        "Adds a section on **online counseling sessions**: COMPASS uses a video provider only "
        "for scheduled online appointments, and recordings are never made without your "
        "session-specific consent."
    ),
    "requires_acknowledgment": True,
    "effective_on": None,
}


__all__ = [
    "ANNOUNCEMENTS",
    "AnnouncementSpec",
    "PRIVACY_NOTICE",
    "PRIVACY_NOTICE_DRAFT",
    "PRIVACY_NOTICE_PUBLISHED",
    "RESOURCES",
    "RETENTION_POLICIES",
    "ResourceSpec",
]
