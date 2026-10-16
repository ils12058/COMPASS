"""Shared workflow steps for Staging Dataset v1 scenarios.

Every step calls the owning domain service as the acting user and then moves only allowlisted
business timestamps onto the dataset timeline (``support.align_timestamps``). In-app
Notifications are kept; never-attempted email intents created by seeding are dropped
(``support.settle_notifications``), so a bulk seed never emails anyone.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from compass.appointments.models import Appointment
from compass.appointments.services import (
    complete_appointment,
    create_student_appointment,
)
from compass.call_slips.models import CallSlip
from compass.call_slips.services import (
    create_call_slip_from_referral,
    record_interview_ended,
)
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import create_encounter
from compass.counseling.shared_summaries import (
    publish_assigned_shared_summary,
    put_assigned_shared_summary,
)
from compass.feedback.models import FeedbackOpportunity, FeedbackOpportunitySourceType
from compass.inventory.models import StudentInventory
from compass.notifications.models import Notification
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import mark_my_notification_read
from compass.referrals.models import Referral, ReferralAction, ReferralActionType
from compass.referrals.services import create_referral
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    create_direct,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import Service

from .content import narratives
from .identities import StudentSpec
from .slots import choose_slot
from .support import (
    SeedSession,
    align_timestamps,
    idempotency_key,
    request_fingerprint,
    settle_notifications,
)
from .timeline import CURRENT_ACADEMIC_YEAR

# --- Workflow steps --------------------------------------------------------------------------


def counseling_service() -> Service:
    return Service.objects.get(code=COUNSELING_SERVICE_CODE)


def book(
    session: SeedSession,
    student: StudentSpec,
    provider_key: str,
    *,
    starts_at: datetime,
    booked_at: datetime,
    mode: str = "IN_PERSON",
) -> Appointment:
    service = counseling_service()
    slot = choose_slot(
        session,
        student,
        provider_key,
        service_id=service.pk,
        mode=mode,
        desired=starts_at,
        booked_at=booked_at,
    )
    appointment = create_student_appointment(
        student=session.user(student.key),
        service_id=service.pk,
        provider_id=session.users[provider_key].pk,
        delivery_mode=mode,
        starts_at=slot.starts_at,
        context=session.as_user(student.key),
        now=booked_at,
    )
    align_timestamps(appointment, created_at=booked_at, updated_at=booked_at)
    settle_notifications(
        source_id=appointment.pk,
        event_code=NotificationEvent.APPOINTMENT_SCHEDULED,
        occurred_at=booked_at,
    )
    session.record("Appointments", created=True)
    return appointment


def complete(session: SeedSession, provider_key: str, appointment: Appointment, *, at) -> None:
    at = max(at, appointment.ends_at + timedelta(minutes=20))
    complete_appointment(
        appointment_id=appointment.pk,
        actor=session.user(provider_key),
        context=session.as_user(provider_key),
        now=at,
    )
    align_timestamps(appointment, updated_at=at)


def encounter(
    session: SeedSession,
    counselor_key: str,
    student: StudentSpec,
    *,
    entry_mode: str,
    started: datetime,
    ended: datetime,
    recorded: datetime,
    appointment: Appointment | None = None,
    routine: RoutineInterview | None = None,
) -> CounselingEncounter:
    """``routine`` records the interaction from that Routine Interview's Counseling context."""

    if appointment is not None:
        padding = min(timedelta(minutes=2), (appointment.ends_at - appointment.starts_at) / 10)
        started = appointment.starts_at + padding
        ended = appointment.ends_at - padding
        recorded = max(recorded, appointment.ends_at + timedelta(minutes=25))
    encounter = create_encounter(
        counselor=session.user(counselor_key),
        entry_mode=entry_mode,
        started_at=started,
        ended_at=ended,
        student_id=session.users[student.key].pk,
        delivery_mode=None if appointment is not None else "IN_PERSON",
        appointment_id=appointment.pk if appointment is not None else None,
        routine_interview_id=routine.pk if routine is not None else None,
        context=session.as_user(counselor_key),
        now=recorded,
    )
    align_timestamps(encounter, created_at=recorded, updated_at=recorded)
    settle_feedback_invitation(
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
        occurred_at=recorded,
    )
    session.record("Counseling Encounters", created=True)
    return encounter


def shared_summary(
    session: SeedSession,
    counselor_key: str,
    encounter: CounselingEncounter,
    content: str,
    *,
    drafted: datetime,
    published: datetime | None,
) -> None:
    drafted = max(drafted, encounter.ended_at + timedelta(minutes=30))
    if published is not None:
        published = max(published, drafted + timedelta(minutes=15))
    counselor = session.user(counselor_key)
    item = put_assigned_shared_summary(
        encounter_id=encounter.pk, counselor=counselor, content=content
    )
    if published is None:
        align_timestamps(item, created_at=drafted, updated_at=drafted)
    else:
        publish_assigned_shared_summary(
            encounter_id=encounter.pk,
            counselor=counselor,
            context=session.as_user(counselor_key),
        )
        align_timestamps(item, created_at=drafted, updated_at=published, published_at=published)
        settle_notifications(source_id=item.pk, occurred_at=published)
    session.record("Shared Summaries", created=True)


def student_intake(
    session: SeedSession,
    student: StudentSpec,
    routine: RoutineInterview,
    values: dict[str, object],
    *,
    saved: datetime,
    submit: bool,
) -> None:
    user = session.user(student.key)
    replace_my_intake(student=user, routine_interview_id=routine.pk, values=values)
    if submit:
        submit_my_intake(
            student=user,
            routine_interview_id=routine.pk,
            context=session.as_user(student.key),
        )
        align_timestamps(routine, updated_at=saved, intake_submitted_at=saved)
    else:
        align_timestamps(routine, updated_at=saved)


def finalize_evaluation(
    session: SeedSession,
    counselor_key: str,
    routine: RoutineInterview,
    values: dict[str, object],
    *,
    at: datetime,
) -> None:
    """Finalize against the Encounter COMPASS already linked to ``routine``."""

    linked = RoutineInterview.objects.select_related("counseling_encounter").get(pk=routine.pk)
    if linked.counseling_encounter is not None:
        at = max(at, linked.counseling_encounter.created_at + timedelta(minutes=20))
    counselor = session.user(counselor_key)
    replace_assigned_evaluation(counselor=counselor, routine_interview_id=routine.pk, values=values)
    finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=routine.pk,
        encounter_id=None,
        context=session.as_user(counselor_key),
    )
    align_timestamps(routine, updated_at=at, evaluation_finalized_at=at)


def appointment_routine(
    session: SeedSession, student: StudentSpec, appointment: Appointment, *, created: datetime
) -> RoutineInterview:
    routine = ensure_for_appointment(
        student=session.user(student.key),
        appointment_id=appointment.pk,
        context=session.as_user(student.key),
    )
    align_timestamps(routine, created_at=created, updated_at=created)
    session.record("Routine Interviews", created=True)
    return routine


def direct_routine(
    session: SeedSession,
    counselor_key: str,
    student: StudentSpec,
    *,
    entry_mode: str,
    created: datetime,
) -> RoutineInterview:
    routine = create_direct(
        counselor=session.user(counselor_key),
        student_id=session.users[student.key].pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        idempotency_key=idempotency_key("routine", student.key, entry_mode.lower()),
        request_fingerprint=request_fingerprint(
            record="routine", student=student.key, entry_mode=entry_mode
        ),
        context=session.as_user(counselor_key),
    )
    align_timestamps(routine, created_at=created, updated_at=created)
    settle_notifications(source_id=routine.pk, occurred_at=created)
    session.record("Routine Interviews", created=True)
    return routine


def referral(
    session: SeedSession,
    actor_key: str,
    student: StudentSpec,
    content: dict[str, str],
    *,
    record_key: str,
    referred_on,
    received_at: datetime,
    recorded_at: datetime,
) -> Referral:
    referral = create_referral(
        actor=session.user(actor_key),
        student_id=session.users[student.key].pk,
        course_year_block=content["course_year_block"],
        reason=content["reason"],
        referrer_name=content["referrer_name"],
        referred_on=referred_on,
        received_at=received_at,
        idempotency_key=idempotency_key("referral", student.key, record_key),
        request_fingerprint=request_fingerprint(
            record="referral", student=student.key, key=record_key
        ),
        context=session.as_user(actor_key),
        now=recorded_at,
    )
    align_timestamps(referral, created_at=recorded_at, updated_at=recorded_at)
    session.record("Referrals", created=True)
    return referral


def call_slip_for_referral(
    session: SeedSession,
    actor_key: str,
    student: StudentSpec,
    referral: Referral,
    *,
    record_key: str,
    course_year: str,
    report_at: datetime,
    action_at: datetime,
    issued_at: datetime | None,
) -> CallSlip:
    """Issue the referral's Call Slip; ``issued_at=None`` means live issuance right now."""

    live = issued_at is None
    item = create_call_slip_from_referral(
        actor=session.user(actor_key),
        referral_id=referral.pk,
        course_year=course_year,
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=report_at,
        # Back-entered slips use the quiet HISTORICAL provenance; only a slip issued now is LIVE.
        notify_student=live,
        action_occurred_at=action_at,
        action_remarks=narratives.CALL_SLIP_ACTION_REMARKS,
        idempotency_key=idempotency_key("call-slip", student.key, record_key),
        request_fingerprint=request_fingerprint(
            record="call-slip", student=student.key, key=record_key
        ),
        context=session.as_user(actor_key),
    )
    action = ReferralAction.objects.get(
        referral=referral, action_type=ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT
    )
    if not live:
        align_timestamps(action, created_at=action_at)
        align_timestamps(item, created_at=issued_at, updated_at=issued_at)
        align_timestamps(referral, updated_at=action_at)
    settle_notifications(source_id=item.pk, occurred_at=issued_at or item.created_at)
    session.record("Call Slips", created=True)
    return item


def end_interview(
    session: SeedSession, actor_key: str, call_slip: CallSlip, *, ended_at: datetime
) -> None:
    record_interview_ended(
        actor=session.user(actor_key),
        call_slip_id=call_slip.pk,
        interview_ended_at=ended_at,
        context=session.as_user(actor_key),
        now=ended_at,
    )
    align_timestamps(call_slip, updated_at=ended_at)


def feedback_opportunity_for_source(
    source_type: str,
    source_id,
) -> FeedbackOpportunity:
    return FeedbackOpportunity.objects.get(source_type=source_type, source_id=source_id)


def settle_feedback_invitation(
    *,
    source_type: str,
    source_id,
    occurred_at: datetime,
) -> FeedbackOpportunity:
    opportunity = feedback_opportunity_for_source(source_type, source_id)
    settle_notifications(
        source_id=opportunity.pk,
        event_code=NotificationEvent.FEEDBACK_INVITATION,
        occurred_at=occurred_at,
    )
    return opportunity


def mark_read(
    session: SeedSession, student: StudentSpec, *, source_id, event: str, at: datetime
) -> None:
    user = session.user(student.key)
    notification = Notification.objects.get(recipient=user, source_id=source_id, event_code=event)
    mark_my_notification_read(actor=user, notification_id=notification.pk)
    align_timestamps(notification, read_at=at)


def current_inventory_exists(session: SeedSession, student: StudentSpec) -> bool:
    return StudentInventory.objects.filter(
        student=session.users[student.key], academic_year__label=CURRENT_ACADEMIC_YEAR
    ).exists()
