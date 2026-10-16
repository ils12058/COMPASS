"""Rich scenario Students: multi-domain stories, each one coherent unit in its own transaction.

A story owns one Student's recent history across domains: Inventory, Appointments, Counseling,
Routine Interviews, Referrals, Call Slips, Good Moral, Exit Interview and Graduate Tracer. Every
step calls the owning domain service as the acting user; dates come from the dataset timeline. A
story whose marker record already exists is skipped as a whole, so reruns never duplicate or
rewrite it, and never restore a state an evaluator already changed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

from compass.appointments.services import (
    cancel_appointment,
    mark_appointment_no_show,
)
from compass.call_slips.services import (
    create_call_slip,
    void_call_slip,
)
from compass.feedback.models import FeedbackOpportunitySourceType
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import (
    cancel_request,
    create_my_current_student,
    create_my_graduate,
    issue_request,
    prepare_request,
    update_request,
)
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.services import (
    ensure_my_response,
    replace_my_draft,
    submit_my_response,
)
from compass.notifications.policy import NotificationEvent
from compass.referrals.services import void_referral

from .. import workflows as wf
from ..content import narratives
from ..history import seed_annual_inventory, seed_exit_interview
from ..identities import StudentSpec
from ..organization import program_for
from ..staff import COUNSELOR_A, COUNSELOR_B, FORMER_STAFF, GSS_A, HEAD_GUIDANCE
from ..students import (
    ACTIVE_REFERRAL,
    ALUMNI,
    FIRST_YEAR,
    FOURTH_YEAR,
    GOOD_MORAL,
    GRADUATING,
    RECENT_GRADUATE,
    REFERRED,
    SECOND_YEAR,
)
from ..support import (
    SeedSession,
    align_timestamps,
    idempotency_key,
    request_fingerprint,
    settle_notifications,
)
from ..timeline import CURRENT_ACADEMIC_YEAR, academic_semester

# --- Scenarios -------------------------------------------------------------------------------


def current_regular(session: SeedSession) -> None:
    """First-year BSIT Student: submitted Inventory, a cancelled booking, and an upcoming ONLINE
    session whose Routine Interview intake is still a draft (the E-Counseling starting point)."""

    t = session.timeline
    seed_annual_inventory(session, FIRST_YEAR, CURRENT_ACADEMIC_YEAR)

    cancelled = wf.book(
        session, FIRST_YEAR, COUNSELOR_A.key, starts_at=t.past(4, 11), booked_at=t.past(7, 16, 10)
    )
    cancel_at = t.past(6, 18, 45)
    cancel_appointment(
        appointment_id=cancelled.pk,
        actor=session.user(FIRST_YEAR.key),
        administrative=False,
        context=session.as_user(FIRST_YEAR.key),
        now=cancel_at,
    )
    align_timestamps(cancelled, updated_at=cancel_at)
    settle_notifications(
        source_id=cancelled.pk,
        event_code=NotificationEvent.APPOINTMENT_CANCELLED,
        occurred_at=cancel_at,
    )

    online = wf.book(
        session,
        FIRST_YEAR,
        COUNSELOR_A.key,
        starts_at=t.future(2, 14),
        booked_at=t.past(1, 15, 20),
        mode="ONLINE",
    )
    routine = wf.appointment_routine(session, FIRST_YEAR, online, created=t.past(1, 15, 25))
    wf.student_intake(
        session,
        FIRST_YEAR,
        routine,
        {
            "coping_with_college_challenges": (
                "Still adjusting. Programming classes are hard but I like them."
            ),
            "college_experience": "Good so far. My blockmates are friendly.",
            "reason_for_choosing_institution": "It is near home and has an IT program.",
        },
        saved=t.past(1, 15, 40),
        submit=False,
    )


def academic_adjustment(session: SeedSession) -> None:
    """Second-year Psychology Student: booked session, submitted intake, completed Counseling
    Encounter, finalized evaluation, published Shared Summary, and a scheduled follow-up."""

    t = session.timeline
    seed_annual_inventory(session, SECOND_YEAR, CURRENT_ACADEMIC_YEAR)

    first = wf.book(
        session, SECOND_YEAR, COUNSELOR_A.key, starts_at=t.past(10, 9), booked_at=t.past(13, 19, 5)
    )
    routine = wf.appointment_routine(session, SECOND_YEAR, first, created=t.past(13, 19, 8))
    wf.student_intake(
        session,
        SECOND_YEAR,
        routine,
        narratives.ADJUSTMENT_INTAKE,
        saved=t.past(12, 20, 32),
        submit=True,
    )

    # A Call Slip requested by the class adviser was withdrawn once staff saw the booking.
    slip = create_call_slip(
        actor=session.user(GSS_A.key),
        student_id=session.users[SECOND_YEAR.key].pk,
        course_year="BS Psychology 2-B",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=t.past(8, 10),
        referral_id=None,
        notify_student=False,
        idempotency_key=idempotency_key("call-slip", SECOND_YEAR.key, "adviser-request"),
        request_fingerprint=request_fingerprint(record="call-slip", student=SECOND_YEAR.key),
        context=session.as_user(GSS_A.key),
    )
    void_at = t.past(11, 14, 40)
    void_call_slip(
        actor=session.user(GSS_A.key),
        call_slip_id=slip.pk,
        reason=narratives.VOIDED_CALL_SLIP_REASON,
        context=session.as_user(GSS_A.key),
        now=void_at,
    )
    align_timestamps(slip, created_at=t.past(11, 10, 15), updated_at=void_at)
    session.record("Call Slips", created=True)

    wf.complete(session, COUNSELOR_A.key, first, at=t.past(10, 9, 58))
    encounter = wf.encounter(
        session,
        COUNSELOR_A.key,
        SECOND_YEAR,
        entry_mode="APPOINTMENT",
        started=t.past(10, 9, 3),
        ended=t.past(10, 9, 55),
        recorded=t.past(10, 10, 20),
        appointment=first,
    )
    wf.finalize_evaluation(
        session, COUNSELOR_A.key, routine, narratives.ADJUSTMENT_EVALUATION, at=t.past(10, 16, 30)
    )
    wf.shared_summary(
        session,
        COUNSELOR_A.key,
        encounter,
        narratives.ADJUSTMENT_SHARED_SUMMARY,
        drafted=t.past(9, 10, 50),
        published=t.past(9, 11),
    )
    wf.book(
        session,
        SECOND_YEAR,
        COUNSELOR_A.key,
        starts_at=t.future(4, 9),
        booked_at=max(t.past(9, 11, 5), encounter.created_at + timedelta(minutes=45)),
    )

    # Read and unread Notifications: the earlier ones were opened, the Shared Summary was not.
    wf.mark_read(
        session,
        SECOND_YEAR,
        source_id=first.pk,
        event=NotificationEvent.APPOINTMENT_SCHEDULED,
        at=t.past(13, 19, 10),
    )
    wf.mark_read(
        session,
        SECOND_YEAR,
        source_id=wf.feedback_opportunity_for_source(
            FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
            encounter.pk,
        ).pk,
        event=NotificationEvent.FEEDBACK_INVITATION,
        at=t.past(9, 18, 15),
    )


def referred_student(session: SeedSession) -> None:
    """Third-year HM Student referred by a Program Chair: Referral (plus a voided duplicate),
    Call Slip action, completed interview recorded as a Counseling Encounter, a direct Routine
    Interview awaiting evaluation, and a completed follow-up with a published Shared Summary."""

    t = session.timeline
    seed_annual_inventory(session, REFERRED, CURRENT_ACADEMIC_YEAR)

    referral = wf.referral(
        session,
        COUNSELOR_B.key,
        REFERRED,
        narratives.REFERRED_REFERRAL,
        record_key="program-chair",
        referred_on=t.business_day(-16),
        received_at=t.past(15, 8, 45),
        recorded_at=t.past(15, 8, 50),
    )
    duplicate = wf.referral(
        session,
        COUNSELOR_B.key,
        REFERRED,
        narratives.REFERRED_REFERRAL,
        record_key="program-chair-duplicate",
        referred_on=t.business_day(-16),
        received_at=t.past(15, 8, 45),
        recorded_at=t.past(15, 8, 52),
    )
    void_at = t.past(15, 9, 5)
    void_referral(
        actor=session.user(COUNSELOR_B.key),
        referral_id=duplicate.pk,
        reason=narratives.REFERRED_DUPLICATE_VOID_REASON.format(code=referral.reference_code),
        context=session.as_user(COUNSELOR_B.key),
        now=void_at,
    )
    align_timestamps(duplicate, updated_at=void_at)

    slip = wf.call_slip_for_referral(
        session,
        COUNSELOR_B.key,
        REFERRED,
        referral,
        record_key="program-chair",
        course_year="BSHM 3-B",
        report_at=t.past(12, 9),
        action_at=t.past(14, 10),
        issued_at=t.past(14, 10, 5),
    )
    wf.end_interview(session, COUNSELOR_B.key, slip, ended_at=t.past(12, 9, 50))
    wf.encounter(
        session,
        COUNSELOR_B.key,
        REFERRED,
        entry_mode="REFERRED",
        started=t.past(12, 9, 5),
        ended=t.past(12, 9, 50),
        recorded=t.past(12, 10, 10),
    )
    routine = wf.direct_routine(
        session, COUNSELOR_B.key, REFERRED, entry_mode="REFERRED", created=t.past(12, 10, 15)
    )
    wf.student_intake(
        session,
        REFERRED,
        routine,
        narratives.REFERRED_INTAKE,
        saved=t.past(11, 19, 40),
        submit=True,
    )

    follow_up = wf.book(
        session, REFERRED, COUNSELOR_B.key, starts_at=t.past(5, 13), booked_at=t.past(12, 16)
    )
    wf.complete(session, COUNSELOR_B.key, follow_up, at=t.past(5, 13, 55))
    follow_up_encounter = wf.encounter(
        session,
        COUNSELOR_B.key,
        REFERRED,
        entry_mode="APPOINTMENT",
        started=t.past(5, 13, 2),
        ended=t.past(5, 13, 50),
        recorded=t.past(5, 14, 10),
        appointment=follow_up,
    )
    wf.shared_summary(
        session,
        COUNSELOR_B.key,
        follow_up_encounter,
        narratives.REFERRED_FOLLOW_UP_SUMMARY,
        drafted=t.past(4, 9, 15),
        published=t.past(4, 9, 30),
    )


def completed_counseling(session: SeedSession) -> None:
    """Fourth-year IS Student: last year's Referral and Call Slip recorded by staff who have
    since left, a no-show, a walk-in Counseling Encounter with a finalized direct Routine
    Interview and an unpublished Shared Summary draft, and a scheduled follow-up."""

    t = session.timeline
    seed_annual_inventory(session, FOURTH_YEAR, CURRENT_ACADEMIC_YEAR)

    historical = wf.referral(
        session,
        FORMER_STAFF.key,
        FOURTH_YEAR,
        narratives.HISTORICAL_REFERRAL,
        record_key="systems-analysis-instructor",
        referred_on=t.on(2026, 2, 9).date(),
        received_at=t.on(2026, 2, 10, 8, 40),
        recorded_at=t.on(2026, 2, 10, 8, 45),
    )
    slip = wf.call_slip_for_referral(
        session,
        FORMER_STAFF.key,
        FOURTH_YEAR,
        historical,
        record_key="systems-analysis-instructor",
        course_year="BSIS 3-A",
        report_at=t.on(2026, 2, 12, 9),
        action_at=t.on(2026, 2, 10, 9, 15),
        issued_at=t.on(2026, 2, 10, 9, 20),
    )
    wf.end_interview(session, COUNSELOR_A.key, slip, ended_at=t.on(2026, 2, 12, 9, 40))

    missed = wf.book(
        session,
        FOURTH_YEAR,
        COUNSELOR_A.key,
        starts_at=t.past(16, 10),
        booked_at=t.past(18, 14, 20),
    )
    no_show_at = missed.ends_at + timedelta(minutes=10)
    mark_appointment_no_show(
        appointment_id=missed.pk,
        actor=session.user(COUNSELOR_A.key),
        context=session.as_user(COUNSELOR_A.key),
        now=no_show_at,
    )
    align_timestamps(missed, updated_at=no_show_at)

    routine = wf.direct_routine(
        session, COUNSELOR_A.key, FOURTH_YEAR, entry_mode="WALK_IN", created=t.past(8, 14, 15)
    )
    wf.student_intake(
        session,
        FOURTH_YEAR,
        routine,
        narratives.WALK_IN_INTAKE,
        saved=t.past(8, 14, 40),
        submit=True,
    )
    walk_in = wf.encounter(
        session,
        COUNSELOR_A.key,
        FOURTH_YEAR,
        entry_mode="WALK_IN",
        started=t.past(8, 14, 10),
        ended=t.past(8, 14, 55),
        recorded=t.past(8, 15, 10),
        routine=routine,
    )
    wf.finalize_evaluation(
        session,
        COUNSELOR_A.key,
        routine,
        narratives.WALK_IN_EVALUATION,
        at=t.past(8, 16, 20),
    )
    wf.shared_summary(
        session,
        COUNSELOR_A.key,
        walk_in,
        narratives.WALK_IN_SUMMARY_DRAFT,
        drafted=t.past(8, 16, 30),
        published=None,
    )
    wf.book(
        session, FOURTH_YEAR, COUNSELOR_A.key, starts_at=t.future(3, 10), booked_at=t.past(7, 9, 30)
    )


def graduating(session: SeedSession) -> None:
    """Graduating BSBA Student in a delayed final year: Exit Interview in progress, a pending
    Good Moral request, and a career consultation booked with Head Guidance."""

    t = session.timeline
    seed_annual_inventory(session, GRADUATING, CURRENT_ACADEMIC_YEAR)
    seed_exit_interview(
        session,
        GRADUATING,
        started=t.past(6, 19),
        saved=t.past(6, 19, 25),
        submitted=None,
        narrative=narratives.GRADUATING_EXIT_INTERVIEW_DRAFT,
    )
    requested = t.past(3, 10, 40)
    request = create_my_current_student(
        student=session.user(GRADUATING.key),
        year_level=narratives.GRADUATING_GOOD_MORAL["year_level"],
        semester=academic_semester(requested.date()),
        idempotency_key=idempotency_key("good-moral", GRADUATING.key),
        request_fingerprint=request_fingerprint(record="good-moral", student=GRADUATING.key),
        context=session.as_user(GRADUATING.key),
    )
    align_timestamps(request, created_at=requested, updated_at=requested)
    session.record("Good Moral Requests", created=True)
    wf.book(
        session,
        GRADUATING,
        HEAD_GUIDANCE.key,
        starts_at=t.future(6, 14),
        booked_at=t.past(2, 17, 5),
    )


def active_referral(session: SeedSession) -> None:
    """Second-year English Language Studies Student: Inventory still in draft, a new adviser
    referral, and a Call Slip issued live today for an interview later this week."""

    t = session.timeline
    seed_annual_inventory(session, ACTIVE_REFERRAL, CURRENT_ACADEMIC_YEAR)
    referral = wf.referral(
        session,
        GSS_A.key,
        ACTIVE_REFERRAL,
        narratives.ACTIVE_REFERRAL,
        record_key="class-adviser",
        referred_on=t.business_day(-3),
        received_at=t.past(2, 8, 30),
        recorded_at=t.past(2, 8, 35),
    )
    wf.call_slip_for_referral(
        session,
        GSS_A.key,
        ACTIVE_REFERRAL,
        referral,
        record_key="class-adviser",
        course_year="BAELS 2-A",
        report_at=t.future(2, 10),
        action_at=session.started_at,
        issued_at=None,
    )


def good_moral_student(session: SeedSession) -> None:
    """Third-year Accountancy Student: an issued Good Moral certificate (renderable) and a
    duplicate request the Student cancelled."""

    t = session.timeline
    seed_annual_inventory(session, GOOD_MORAL, CURRENT_ACADEMIC_YEAR)
    student = session.user(GOOD_MORAL.key)
    requested = t.past(10, 9, 15)
    semester = academic_semester(requested.date())
    request = create_my_current_student(
        student=student,
        year_level=narratives.GOOD_MORAL_CURRENT["year_level"],
        semester=semester,
        idempotency_key=idempotency_key("good-moral", GOOD_MORAL.key),
        request_fingerprint=request_fingerprint(record="good-moral", student=GOOD_MORAL.key),
        context=session.as_user(GOOD_MORAL.key),
    )
    duplicate = create_my_current_student(
        student=student,
        year_level=narratives.GOOD_MORAL_CURRENT["year_level"],
        semester=semester,
        idempotency_key=idempotency_key("good-moral", GOOD_MORAL.key, "duplicate"),
        request_fingerprint=request_fingerprint(
            record="good-moral", student=GOOD_MORAL.key, duplicate=True
        ),
        context=session.as_user(GOOD_MORAL.key),
    )
    cancelled_at = t.past(10, 9, 25)
    cancel_request(
        actor=session.user(GOOD_MORAL.key),
        request_id=duplicate.pk,
        reason=narratives.GOOD_MORAL_DUPLICATE_CANCEL_REASON,
        self_service=True,
        context=session.as_user(GOOD_MORAL.key),
        now=cancelled_at,
    )
    align_timestamps(duplicate, created_at=t.past(10, 9, 17), updated_at=cancelled_at)

    # Before issuing, the Counselor records the receipt.
    receipt = narratives.GOOD_MORAL_CURRENT_RECEIPT
    update_request(
        actor=session.user(COUNSELOR_B.key),
        request_id=request.pk,
        changes={
            "official_receipt_number": receipt["official_receipt_number"],
            "official_receipt_date": t.business_day(-9),
            "official_receipt_amount": Decimal(receipt["amount"]),
        },
        context=session.as_user(COUNSELOR_B.key),
    )
    issued_at = t.past(7, 15, 30)
    prepare_request(
        actor=session.user(COUNSELOR_B.key),
        request_id=request.pk,
        context=session.as_user(COUNSELOR_B.key),
        now=issued_at,
    )
    issue_request(
        actor=session.user(COUNSELOR_B.key),
        request_id=request.pk,
        context=session.as_user(COUNSELOR_B.key),
        now=issued_at,
    )
    align_timestamps(request, created_at=requested, updated_at=issued_at)
    settle_notifications(source_id=request.pk, occurred_at=issued_at)
    wf.settle_feedback_invitation(
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=request.pk,
        occurred_at=issued_at,
    )
    session.record("Good Moral Requests", created=True, count=2)
    wf.mark_read(
        session,
        GOOD_MORAL,
        source_id=request.pk,
        event=NotificationEvent.GOOD_MORAL_ISSUED,
        at=t.past(7, 18),
    )


def tracer_values(
    response: GraduateTracerResponse, persona: StudentSpec, answers, *, graduation_year: int
) -> dict:
    from compass.graduate_tracer.confidential_content import read_confidential_content

    private = read_confidential_content(response)
    program = program_for(persona)
    return {
        "name_snapshot": response.name_snapshot,
        "permanent_address_snapshot": private.permanent_address_snapshot,
        "email_snapshot": private.email_snapshot,
        "telephone_contact_numbers_snapshot": private.telephone_contact_numbers_snapshot,
        "mobile_number_snapshot": private.mobile_number_snapshot,
        "birth_date": persona.date_of_birth,
        **answers,
        "graduated_college_id": program.college_id,
        "graduated_program_id": program.pk,
        "graduation_year": graduation_year,
    }


def recent_graduate(session: SeedSession) -> None:
    """June 2026 graduate: an issued graduate Good Moral certificate and a Graduate Tracer
    response started this week."""

    t = session.timeline
    student = session.user(RECENT_GRADUATE.key)
    details = narratives.RECENT_GRADUATE_GOOD_MORAL
    request = create_my_graduate(
        student=student,
        degree=details["degree"],
        major=details["major"],
        graduation_date=details["graduation_date"],
        idempotency_key=idempotency_key("good-moral", RECENT_GRADUATE.key),
        request_fingerprint=request_fingerprint(record="good-moral", student=RECENT_GRADUATE.key),
        context=session.as_user(RECENT_GRADUATE.key),
    )
    update_request(
        actor=session.user(COUNSELOR_A.key),
        request_id=request.pk,
        changes={
            "official_receipt_number": details["official_receipt_number"],
            "official_receipt_date": t.on(2026, 7, 13).date(),
            "official_receipt_amount": Decimal(details["amount"]),
        },
        context=session.as_user(COUNSELOR_A.key),
    )
    issued_at = t.on(2026, 7, 15, 14)
    prepare_request(
        actor=session.user(COUNSELOR_A.key),
        request_id=request.pk,
        context=session.as_user(COUNSELOR_A.key),
        now=issued_at,
    )
    issue_request(
        actor=session.user(COUNSELOR_A.key),
        request_id=request.pk,
        context=session.as_user(COUNSELOR_A.key),
        now=issued_at,
    )
    align_timestamps(request, created_at=t.on(2026, 7, 13, 10, 20), updated_at=issued_at)
    settle_notifications(source_id=request.pk, occurred_at=issued_at)
    wf.settle_feedback_invitation(
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=request.pk,
        occurred_at=issued_at,
    )
    session.record("Good Moral Requests", created=True)

    response = ensure_my_response(student=student, context=session.as_user(RECENT_GRADUATE.key))
    replace_my_draft(
        student=session.user(RECENT_GRADUATE.key),
        values=tracer_values(
            response,
            RECENT_GRADUATE,
            narratives.RECENT_GRADUATE_TRACER_DRAFT,
            graduation_year=details["graduation_date"].year,
        ),
    )
    align_timestamps(response, created_at=t.past(4, 20, 10), updated_at=t.past(4, 20, 35))
    session.record("Graduate Tracer responses", created=True)


def alumni(session: SeedSession) -> None:
    """June 2025 graduate: a submitted Graduate Tracer response and a pending graduate Good
    Moral request."""

    t = session.timeline
    student = session.user(ALUMNI.key)
    context = session.as_user(ALUMNI.key)
    response = ensure_my_response(student=student, context=context)
    replace_my_draft(
        student=student,
        values=tracer_values(
            response,
            ALUMNI,
            narratives.ALUMNI_TRACER,
            graduation_year=narratives.ALUMNI_GOOD_MORAL["graduation_date"].year,
        ),
    )
    submitted_at = t.on(2026, 2, 9, 20, 15)
    submit_my_response(student=session.user(ALUMNI.key), context=context, now=submitted_at)
    align_timestamps(response, created_at=t.on(2026, 2, 2, 19, 30), updated_at=submitted_at)
    session.record("Graduate Tracer responses", created=True)

    details = narratives.ALUMNI_GOOD_MORAL
    request = create_my_graduate(
        student=session.user(ALUMNI.key),
        degree=details["degree"],
        major=details["major"],
        graduation_date=details["graduation_date"],
        idempotency_key=idempotency_key("good-moral", ALUMNI.key),
        request_fingerprint=request_fingerprint(record="good-moral", student=ALUMNI.key),
        context=context,
    )
    align_timestamps(request, created_at=t.past(2, 9, 40), updated_at=t.past(2, 9, 40))
    session.record("Good Moral Requests", created=True)


@dataclass(frozen=True)
class StoryUnit:
    key: str
    persona: StudentSpec
    run: Callable[[SeedSession], None]
    is_seeded: Callable[[SeedSession], bool]


def _inventory_marker(persona: StudentSpec) -> Callable[[SeedSession], bool]:
    return lambda session: wf.current_inventory_exists(session, persona)


# Stories are entered roughly oldest first, so allocated reference numbers (REF-..., APT-...)
# follow the narrative order instead of contradicting it.
RICH_STORIES = (
    StoryUnit(
        "RICH_COMPLETED_COUNSELING",
        FOURTH_YEAR,
        completed_counseling,
        _inventory_marker(FOURTH_YEAR),
    ),
    StoryUnit("RICH_REFERRED_STUDENT", REFERRED, referred_student, _inventory_marker(REFERRED)),
    StoryUnit(
        "RICH_ACADEMIC_ADJUSTMENT",
        SECOND_YEAR,
        academic_adjustment,
        _inventory_marker(SECOND_YEAR),
    ),
    StoryUnit("RICH_GOOD_MORAL", GOOD_MORAL, good_moral_student, _inventory_marker(GOOD_MORAL)),
    StoryUnit("RICH_CURRENT_REGULAR", FIRST_YEAR, current_regular, _inventory_marker(FIRST_YEAR)),
    StoryUnit("RICH_GRADUATING", GRADUATING, graduating, _inventory_marker(GRADUATING)),
    StoryUnit(
        "RICH_ACTIVE_REFERRAL",
        ACTIVE_REFERRAL,
        active_referral,
        _inventory_marker(ACTIVE_REFERRAL),
    ),
    StoryUnit(
        "RICH_ALUMNI",
        ALUMNI,
        alumni,
        lambda session: GraduateTracerResponse.objects.filter(
            student=session.users[ALUMNI.key]
        ).exists(),
    ),
    StoryUnit(
        "RICH_RECENT_GRADUATE",
        RECENT_GRADUATE,
        recent_graduate,
        lambda session: GoodMoralRequest.objects.filter(
            student=session.users[RECENT_GRADUATE.key]
        ).exists(),
    ),
)


def run_story(session: SeedSession, scenario: StoryUnit) -> bool:
    """Run one scenario atomically; return False when it was already seeded."""

    if scenario.is_seeded(session):
        session.record("Rich scenario stories", created=False)
        return False
    with transaction.atomic():
        scenario.run(session)
    session.record("Rich scenario stories", created=True)
    return True


__all__ = [
    "RICH_STORIES",
    "StoryUnit",
    "run_story",
    "tracer_values",
]
