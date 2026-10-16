"""Action-ready Students: one clear, evaluator-owned pending state each (``ar_01`` … ``ar_24``).

Each unit prepares exactly the state its UAT scenario starts from, through the owning domain
services, inside one transaction. The unit's marker is the record it creates (an Appointment,
referral, request, opportunity, …) in any status, so a rerun never restores a state an evaluator
already consumed (a cancelled booking stays cancelled; an issued certificate stays issued).

Students whose scenario starts from "nothing yet" (``ar_01``, ``ar_02``, ``ar_07``, ``ar_08``,
``ar_12``, ``ar_13``) need no unit: their Inventory and history come from the population units.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

from compass.appointments.models import Appointment
from compass.exit_interviews.models import ExitInterview, ExitInterviewOpportunity
from compass.exit_interviews.opportunities import open_opportunity
from compass.good_moral.models import CANONICAL_YEAR_LEVELS, GoodMoralRequest
from compass.good_moral.services import create_my_current_student, prepare_request, update_request
from compass.guidance_messages.models import GuidanceThread
from compass.guidance_messages.services import open_counseling_thread
from compass.organization.academic_years import get_current_academic_year
from compass.referrals.models import Referral
from compass.routine_interviews.models import RoutineInterview

from .. import DATASET_NAMESPACE
from .. import workflows as wf
from ..content import forms, narratives
from ..history import seed_exit_interview
from ..staff import COUNSELOR_A, COUNSELOR_B, COUNSELOR_C, GSS_A, HEAD_GUIDANCE
from ..students import STUDENTS_BY_KEY
from ..support import SeedSession, align_timestamps, idempotency_key, request_fingerprint
from ..timeline import academic_semester

_MESSAGE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:compass:{DATASET_NAMESPACE}:messages")
COUNSELOR_GREETING = (
    "Good afternoon! Thank you for booking a session. Before we meet, is there anything you "
    "would like me to know or any time that works better for you?"
)


@dataclass(frozen=True)
class ActionUnit:
    key: str
    run: Callable[[SeedSession], None]
    is_seeded: Callable[[SeedSession], bool]


def _student(key: str):
    return STUDENTS_BY_KEY[key]


def _has(model, field: str = "student", **filters) -> Callable[[SeedSession], bool]:
    def check(session: SeedSession, key: str) -> bool:
        return model.objects.filter(**{field: session.users[key]}, **filters).exists()

    return check


def _upcoming(key: str, provider: str, *, days: int, hour: int, mode: str = "IN_PERSON"):
    def run(session: SeedSession) -> None:
        t = session.timeline
        wf.book(
            session,
            _student(key),
            provider,
            starts_at=t.future(days, hour),
            booked_at=t.past(2, 16, 10 + days),
            mode=mode,
        )

    return run


def _awaiting_outcome(key: str, provider: str):
    """A past Appointment the Counselor has not closed: still SCHEDULED."""

    def run(session: SeedSession) -> None:
        t = session.timeline
        wf.book(session, _student(key), provider, starts_at=t.past(2, 10), booked_at=t.past(7, 15))

    return run


def _routine_intake_draft(session: SeedSession) -> None:
    t = session.timeline
    student = _student("ar_09")
    appointment = wf.book(
        session, student, COUNSELOR_A.key, starts_at=t.future(6, 11), booked_at=t.past(1, 14, 5)
    )
    routine = wf.appointment_routine(session, student, appointment, created=t.past(1, 14, 8))
    wf.student_intake(
        session,
        student,
        routine,
        {
            "college_experience": "Busy but manageable. I joined the campus writing guild.",
            "reason_for_choosing_institution": "The English program and it is close to home.",
        },
        saved=t.past(1, 14, 30),
        submit=False,
    )


def _exit_opportunity(key: str):
    def run(session: SeedSession) -> None:
        opened_at = session.timeline.past(3, 9, 30)
        opportunity = open_opportunity(
            actor=session.user(HEAD_GUIDANCE.key),
            student_id=session.users[key].pk,
            academic_year_id=get_current_academic_year().pk,
            source="MANUAL",
            note="",
            context=session.as_user(HEAD_GUIDANCE.key),
        )
        align_timestamps(
            opportunity, created_at=opened_at, updated_at=opened_at, opened_at=opened_at
        )
        session.record("Exit Interview opportunities", created=True)

    return run


def _unread_message(session: SeedSession) -> None:
    t = session.timeline
    student = _student("ar_14")
    appointment = wf.book(
        session, student, COUNSELOR_A.key, starts_at=t.future(7, 10), booked_at=t.past(3, 11)
    )
    open_counseling_thread(
        actor=session.user(COUNSELOR_A.key),
        appointment_id=appointment.pk,
        client_message_id=uuid.uuid5(_MESSAGE_NAMESPACE, "ar_14:greeting"),
        body=COUNSELOR_GREETING,
        context=session.as_user(COUNSELOR_A.key),
    )
    session.record("Guidance Message threads", created=True)


def _published_summary(session: SeedSession) -> None:
    t = session.timeline
    student = _student("ar_15")
    appointment = wf.book(
        session, student, COUNSELOR_B.key, starts_at=t.past(6, 10), booked_at=t.past(9, 14)
    )
    wf.complete(session, COUNSELOR_B.key, appointment, at=t.past(6, 11))
    encounter = wf.encounter(
        session,
        COUNSELOR_B.key,
        student,
        entry_mode="APPOINTMENT",
        started=t.past(6, 10),
        ended=t.past(6, 10, 50),
        recorded=t.past(6, 11, 15),
        appointment=appointment,
    )
    wf.shared_summary(
        session,
        COUNSELOR_B.key,
        encounter,
        narratives.ADJUSTMENT_SHARED_SUMMARY,
        drafted=t.past(5, 9, 10),
        published=t.past(5, 9, 30),
    )


def _referral(key: str, actor: str, *, call_slip: bool):
    def run(session: SeedSession) -> None:
        t = session.timeline
        student = _student(key)
        referral = wf.referral(
            session,
            actor,
            student,
            narratives.ACTIVE_REFERRAL,
            record_key="class-adviser",
            referred_on=t.business_day(-2),
            received_at=t.past(1, 8, 30),
            recorded_at=t.past(1, 8, 40),
        )
        if call_slip:
            wf.call_slip_for_referral(
                session,
                actor,
                student,
                referral,
                record_key="class-adviser",
                course_year=f"{student.program_code} {student.current_year_level}-A",
                report_at=t.future(2, 10),
                action_at=session.started_at,
                issued_at=None,
            )

    return run


def _good_moral(key: str, counselor: str | None):
    """A REQUESTED request, optionally with a recorded receipt and prepared certificate."""

    def run(session: SeedSession) -> None:
        t = session.timeline
        requested = t.past(2, 9, 20)
        request = create_my_current_student(
            student=session.user(key),
            year_level=CANONICAL_YEAR_LEVELS[_student(key).current_year_level - 1],
            semester=academic_semester(requested.date()),
            idempotency_key=idempotency_key("good-moral", key),
            request_fingerprint=request_fingerprint(record="good-moral", student=key),
            context=session.as_user(key),
        )
        if counselor is not None:
            prepared = t.past(1, 10, 15)
            update_request(
                actor=session.user(counselor),
                request_id=request.pk,
                changes={
                    "official_receipt_number": f"STG-OR-{_student(key).ordinal:04d}",
                    "official_receipt_date": t.business_day(-1),
                    "official_receipt_amount": Decimal("50.00"),
                },
                context=session.as_user(counselor),
            )
            prepare_request(
                actor=session.user(counselor),
                request_id=request.pk,
                context=session.as_user(counselor),
                now=prepared,
            )
            align_timestamps(request, created_at=requested, updated_at=prepared)
        else:
            align_timestamps(request, created_at=requested, updated_at=requested)
        session.record("Good Moral Requests", created=True)

    return run


def _routine_evaluation_pending(session: SeedSession) -> None:
    t = session.timeline
    student = _student("ar_21")
    routine = wf.direct_routine(
        session, COUNSELOR_A.key, student, entry_mode="WALK_IN", created=t.past(3, 13, 30)
    )
    wf.student_intake(
        session, student, routine, forms.CAREER_INTAKE, saved=t.past(3, 13, 50), submit=True
    )
    wf.encounter(
        session,
        COUNSELOR_A.key,
        student,
        entry_mode="WALK_IN",
        started=t.past(3, 13, 30),
        ended=t.past(3, 14, 15),
        recorded=t.past(3, 14, 30),
        routine=routine,
    )


def _submitted_exit(session: SeedSession) -> None:
    t = session.timeline
    student = _student("ar_24")
    started = t.past(5, 18, 10)
    seed_exit_interview(
        session,
        student,
        started=started,
        saved=started + timedelta(minutes=30),
        submitted=started + timedelta(minutes=30),
        narrative=forms.exit_answers(student.ordinal),
    )


def _current_exit(key: str):
    def check(session: SeedSession) -> bool:
        current = get_current_academic_year()
        return (
            ExitInterviewOpportunity.objects.filter(
                student=session.users[key], academic_year=current
            ).exists()
            or ExitInterview.objects.filter(
                student=session.users[key], academic_year=current
            ).exists()
        )

    return check


def _unit(key: str, run, model, **filters) -> ActionUnit:
    check = _has(model, **filters)
    return ActionUnit(key, run, lambda session, key=key: check(session, key))


ACTION_UNITS = (
    _unit("ar_03", _upcoming("ar_03", COUNSELOR_A.key, days=3, hour=10), Appointment),
    _unit("ar_04", _upcoming("ar_04", COUNSELOR_B.key, days=4, hour=13), Appointment),
    _unit("ar_05", _upcoming("ar_05", COUNSELOR_A.key, days=5, hour=9, mode="ONLINE"), Appointment),
    _unit(
        "ar_06", _upcoming("ar_06", COUNSELOR_B.key, days=5, hour=14, mode="ONLINE"), Appointment
    ),
    _unit("ar_09", _routine_intake_draft, RoutineInterview),
    ActionUnit("ar_10", _exit_opportunity("ar_10"), _current_exit("ar_10")),
    ActionUnit("ar_11", _exit_opportunity("ar_11"), _current_exit("ar_11")),
    _unit("ar_14", _unread_message, GuidanceThread),
    _unit("ar_15", _published_summary, Appointment),
    _unit("ar_16", _referral("ar_16", COUNSELOR_C.key, call_slip=True), Referral),
    _unit("ar_17", _good_moral("ar_17", None), GoodMoralRequest),
    _unit("ar_18", _good_moral("ar_18", COUNSELOR_A.key), GoodMoralRequest),
    _unit("ar_19", _referral("ar_19", GSS_A.key, call_slip=False), Referral),
    _unit("ar_20", _referral("ar_20", COUNSELOR_B.key, call_slip=False), Referral),
    _unit("ar_21", _routine_evaluation_pending, RoutineInterview),
    _unit("ar_22", _awaiting_outcome("ar_22", COUNSELOR_B.key), Appointment),
    _unit("ar_23", _awaiting_outcome("ar_23", COUNSELOR_C.key), Appointment),
    ActionUnit("ar_24", _submitted_exit, _current_exit("ar_24")),
)


def run_action_unit(session: SeedSession, unit: ActionUnit) -> bool:
    if unit.is_seeded(session):
        session.record("Action-ready units", created=False)
        return False
    with transaction.atomic():
        unit.run(session)
    session.record("Action-ready units", created=True)
    return True


__all__ = ["ACTION_UNITS", "ActionUnit", "COUNSELOR_GREETING", "run_action_unit"]
