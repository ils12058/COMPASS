"""Announcement, Resource, and Privacy Governance content for the dataset (data only).

Publications describe ordinary Guidance and Counseling Office work. Privacy artifacts are
explicitly labelled as staging dataset material so they cannot be mistaken for approved
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
        title="Guidance consultation hours for Academic Year 2026-2027",
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
        author="goa_a",
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
        author="goa_a",
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
        author="goa_a",
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

# Plain text: the Privacy Notice field preserves paragraph and line breaks but does not render
# Markdown. Provisional wording until the University approves the official notice.
_NOTICE_INTRO = (
    "The University of Camarines Norte Guidance and Counseling Office uses COMPASS to provide "
    "guidance and counseling services. We handle your personal information in line with the "
    "Data Privacy Act of 2012 (Republic Act No. 10173)."
)
_NOTICE_SECTIONS = (
    "What we collect\n"
    "- Your name, student number, College, Program, year level and contact details.\n"
    "- What you share in your Individual Inventory, Routine Interview, Exit Interview and "
    "Graduate Tracer forms.\n"
    "- Your appointments, counseling records, referrals, certificate requests and feedback.",
    "Why we use it\n"
    "- To schedule and provide counseling and other guidance services.\n"
    "- To act on referrals and follow up on your concerns.\n"
    "- To issue certificates, such as the Good Moral Certificate.\n"
    "- To prepare summary reports that don't identify you.",
    "Who can see it\n"
    "Only authorized Guidance and Counseling Office personnel, and only what their role needs. "
    "What you discuss in counseling is limited to your counselor, and to another counselor only "
    "when the Head Guidance Counselor approves it for the continuity of your care. Service "
    "providers that run parts of COMPASS for us, such as email, handle your information only on "
    "our instructions. We don't disclose it to anyone else unless the law requires it or you "
    "agree.",
    "How long we keep it\n"
    "We keep your records only as long as the University's records retention schedule requires, "
    "then delete or anonymize them.",
    "Your rights\n"
    "You can ask to see or correct your information, object to how it is used, or ask how it was "
    "handled. Contact the Guidance and Counseling Office or the University's Data Protection "
    "Officer. You can also file a complaint with the National Privacy Commission.",
)
_NOTICE_ONLINE_SECTION = (
    "Online counseling\n"
    "For online appointments, COMPASS connects you and your counselor through a video service "
    "provider. A session is recorded only if you give permission for that session, and you can "
    "withdraw it while the session is running. Recordings are kept and protected like your other "
    "counseling records."
)
_NOTICE_PROVISIONAL = (
    "This notice is provisional. The University's approved wording will replace it."
)

PRIVACY_NOTICE = {
    "code": "STG-GCO-STUDENT-SERVICES",
    "name": "Guidance and Counseling Office Privacy Notice",
}
PRIVACY_NOTICE_PUBLISHED = {
    "title": "Guidance and Counseling Office Privacy Notice",
    "audiences": ["PUBLIC", "STUDENT"],
    "summary": (
        "How the UCN Guidance and Counseling Office collects, uses, protects and keeps your "
        "personal information in COMPASS."
    ),
    "body": "\n\n".join((_NOTICE_INTRO, *_NOTICE_SECTIONS, _NOTICE_PROVISIONAL)),
    "requires_acknowledgment": True,
    "effective_on": (2026, 8, 3),
}
# The next revision is a complete notice: publishing it replaces the whole text.
PRIVACY_NOTICE_DRAFT = {
    "title": "Guidance and Counseling Office Privacy Notice",
    "audiences": ["PUBLIC", "STUDENT"],
    "summary": (
        "How the UCN Guidance and Counseling Office collects, uses, protects and keeps your "
        "personal information in COMPASS, including online counseling sessions."
    ),
    "body": "\n\n".join(
        (
            _NOTICE_INTRO,
            *_NOTICE_SECTIONS[:3],
            _NOTICE_ONLINE_SECTION,
            *_NOTICE_SECTIONS[3:],
            _NOTICE_PROVISIONAL,
        )
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
    "ResourceSpec",
]
