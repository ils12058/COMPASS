"""NS-1: Counselor-proposed next sessions, case Call Slips and Follow-up shortcuts."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.test import override_settings
from django.utils import timezone

from compass.appointments.models import Appointment
from compass.appointments.services import create_student_appointment, list_bookable_slots
from compass.audit.models import AuditEvent
from compass.call_slips.models import CallSlip
from compass.counseling.case_models import CounselingCase, CounselingCaseAppointment
from compass.counseling.case_services import (
    CounselingCaseChanged,
    CounselingCaseClosed,
    CounselingCaseNotFound,
    get_case,
)
from compass.counseling.session_proposal_models import (
    CounselingCaseCallSlip,
    CounselingSessionProposal,
)
from compass.counseling.session_proposal_services import (
    SessionProposalClosed,
    SessionProposalOpen,
    SessionProposalTimeUnavailable,
    accept_proposal,
    decline_proposal,
    propose_session,
    withdraw_proposal,
)
from compass.guidance_messages.models import GuidanceThread
from compass.notifications.models import Notification
from compass.student_actions.services import list_actions
from tests.test_appointments import configure_availability, future_local_start
from tests.test_counseling import auth_client, context, csrf
from tests.test_counseling_cases import link, record
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_transfers import transfer_world

ROOT = "/api/v1/counseling/session-proposals"
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("manila")]


@pytest.fixture
def manila():
    with override_settings(TIME_ZONE="Asia/Manila"):
        yield


@pytest.fixture
def ns(settings):
    w = transfer_world(settings, "ns1")
    configure_availability(w.admin, w.a)
    configure_availability(w.admin, w.b)
    w.start = future_local_start(hour=10)
    return w


def option(start, mode="IN_PERSON"):
    return SimpleNamespace(delivery_mode=mode, starts_at=start)


def propose(w, *, actor=None, starts=None, modes=None, call_slip=False, follow_up=None, **extra):
    actor = actor or w.a
    starts = starts or [w.start]
    modes = modes or ["IN_PERSON"] * len(starts)
    return propose_session(
        actor=actor,
        case_id=w.case.pk,
        purpose=extra.pop("purpose", "FOLLOW_UP_SESSION"),
        options=[option(s, m) for s, m in zip(starts, modes, strict=True)],
        call_slip_requested=call_slip,
        follow_up_id=follow_up.pk if follow_up else None,
        expected_version=extra.pop("expected_version", None),
        context=context(actor),
        now=extra.pop("now", None),
    )


def accept(w, proposal, position=1, *, now=None, student=None):
    proposal.refresh_from_db()
    chosen = proposal.options.get(position=position)
    return accept_proposal(
        actor=student or w.student,
        proposal_id=proposal.pk,
        option_id=chosen.pk,
        expected_version=proposal.version,
        context=context(student or w.student),
        now=now,
    )


def post(client, path, payload, **headers):
    return client.post(
        path, data=json.dumps(payload), content_type="application/json", **csrf(client), **headers
    )


def test_proposal_reserves_nothing_and_notifies_without_narrative(ns):
    w = ns
    before = w.case.version
    proposal = propose(
        w, starts=[w.start, w.start + timedelta(hours=2)], modes=["IN_PERSON", "ONLINE"]
    )
    assert proposal.state == "PENDING" and proposal.options.count() == 2
    assert not Appointment.objects.exists()
    # Another Student still sees the proposed time: no slot was reserved.
    offered = list_bookable_slots(
        student=w.other,
        service_id=proposal.service_id,
        provider_id=w.a.pk,
        delivery_mode="IN_PERSON",
        target_date=w.start.date(),
    )
    assert w.start in [slot.starts_at for slot in offered.items]
    w.case.refresh_from_db()
    assert w.case.version == before + 1
    note = Notification.objects.get(recipient=w.student)
    assert note.message == "Your Counselor proposed a session time. Please choose one."
    assert (note.target_type, note.target_id) == ("SESSION_PROPOSAL", proposal.pk)
    audit = AuditEvent.objects.get(action="counseling.session_proposal.created")
    assert set(audit.metadata) == {
        "case_id",
        "authority",
        "purpose",
        "option_count",
        "delivery_modes",
        "call_slip_requested",
        "from_follow_up",
    }
    assert w.case.reference_code not in json.dumps(audit.metadata)
    assert not Notification.objects.filter(recipient=w.student, message__icontains="case").exists()


def test_accept_books_through_booking_rules_links_case_and_is_idempotent(ns):
    w = ns
    proposal = propose(w, starts=[w.start, w.start + timedelta(hours=2)])
    accepted = accept(w, proposal, 2)
    appointment = accepted.appointment
    assert accepted.state == "ACCEPTED" and accepted.accepted_position == 2
    assert appointment.provider_id == w.a.pk and appointment.student_id == w.student.pk
    assert appointment.starts_at == w.start + timedelta(hours=2)
    assert appointment.created_by_id == w.student.pk
    assert CounselingCaseAppointment.objects.get(appointment=appointment).case_id == w.case.pk
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment.pk == appointment.pk
    # The same answer again keeps the one Appointment; a different answer is refused.
    again = accept_proposal(
        actor=w.student,
        proposal_id=proposal.pk,
        option_id=proposal.options.get(position=2).pk,
        expected_version=1,
        context=context(w.student),
    )
    assert again.appointment_id == appointment.pk
    with pytest.raises(SessionProposalClosed):
        accept(w, proposal, 1)
    with pytest.raises(SessionProposalClosed):
        decline_proposal(
            actor=w.student,
            proposal_id=proposal.pk,
            expected_version=accepted.version,
            context=context(w.student),
        )
    assert Appointment.objects.count() == 1
    staff = Notification.objects.get(
        recipient=w.a, event_code="counseling.session_proposal.decided"
    )
    assert (staff.target_type, staff.target_id) == ("COUNSELING_CASE", w.case.pk)


def test_accept_of_a_taken_time_books_nothing_and_leaves_other_options(ns):
    w = ns
    proposal = propose(w, starts=[w.start, w.start + timedelta(hours=2)])
    create_student_appointment(
        student=w.other,
        service_id=proposal.service_id,
        provider_id=w.a.pk,
        delivery_mode="IN_PERSON",
        starts_at=w.start,
        context=context(w.other),
    )
    with pytest.raises(SessionProposalTimeUnavailable):
        accept(w, proposal, 1)
    proposal.refresh_from_db()
    assert proposal.state == "PENDING" and proposal.appointment_id is None
    assert Appointment.objects.filter(student=w.student).count() == 0
    assert accept(w, proposal, 2).state == "ACCEPTED"


def test_proposing_a_taken_or_unavailable_time_is_refused(ns):
    w = ns
    with pytest.raises(SessionProposalTimeUnavailable) as caught:
        propose(w, starts=[w.start.replace(hour=20)])
    assert caught.value.option == 1
    assert not CounselingSessionProposal.objects.exists()


def test_decline_withdraw_one_open_proposal_and_expiry(ns):
    w = ns
    first = propose(w)
    with pytest.raises(SessionProposalOpen):
        propose(w, starts=[w.start + timedelta(hours=3)])
    declined = decline_proposal(
        actor=w.student, proposal_id=first.pk, expected_version=1, context=context(w.student)
    )
    assert declined.state == "DECLINED" and not Appointment.objects.exists()
    second = propose(w, starts=[w.start + timedelta(hours=3)])
    withdrawn = withdraw_proposal(
        actor=w.a, proposal_id=second.pk, expected_version=1, context=context(w.a)
    )
    assert withdrawn.state == "WITHDRAWN" and withdrawn.withdrawn_by_id == w.a.pk
    with pytest.raises(SessionProposalClosed):
        accept(w, second)
    third = propose(w, starts=[w.start + timedelta(hours=4)])
    assert third.expires_at <= timezone.now() + timedelta(days=7)
    assert third.pk in [item.source_id for item in list_actions(actor=w.student).items]
    CounselingSessionProposal.objects.filter(pk=third.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    with pytest.raises(SessionProposalClosed):
        accept(w, third)
    assert third.pk not in [item.source_id for item in list_actions(actor=w.student).items]
    body = auth_client(w.student).get(f"{ROOT}/me/{third.pk}").json()
    assert (body["state"], body["can_respond"]) == ("EXPIRED", False)
    # An expired proposal no longer blocks a new one; it is closed when the next is made.
    propose(w, starts=[w.start + timedelta(hours=5)])
    third.refresh_from_db()
    assert third.state == "EXPIRED"
    assert not Appointment.objects.exists()


def test_closed_case_and_other_staff_are_refused(ns):
    w = ns
    with pytest.raises(CounselingCaseNotFound):
        propose(w, actor=w.b)
    with pytest.raises(CounselingCaseChanged):
        propose(w, expected_version=w.case.version + 5)
    proposal = propose(w)
    CounselingCase.objects.filter(pk=w.case.pk).update(status="CLOSED")
    with pytest.raises(CounselingCaseClosed):
        propose(w, starts=[w.start + timedelta(hours=3)])
    from compass.counseling.session_proposal_services import SessionProposalUnavailable

    with pytest.raises((SessionProposalUnavailable, SessionProposalClosed)):
        accept(w, proposal)
    body = auth_client(w.student).get(f"{ROOT}/me/{proposal.pk}").json()
    assert (body["state"], body["can_respond"]) == ("EXPIRED", False)
    assert proposal.pk not in [item.source_id for item in list_actions(actor=w.student).items]
    assert not Appointment.objects.exists()


def test_http_boundaries_student_sees_only_own_and_no_case_details(ns):
    w = ns
    proposal = propose(w, call_slip=True)
    student = auth_client(w.student)
    body = student.get(f"{ROOT}/me/{proposal.pk}").json()
    assert body["state"] == "PENDING" and body["can_respond"] is True
    assert "case" not in body and w.case.reference_code not in json.dumps(body)
    assert "call_slip_requested" not in body
    assert auth_client(w.other).get(f"{ROOT}/me/{proposal.pk}").status_code == 404
    for user in (w.b, w.goa, w.faculty):
        assert auth_client(user).get(f"{ROOT}/{proposal.pk}").status_code in {403, 404}
    assert auth_client(w.a).get(f"{ROOT}/{proposal.pk}").json()["case"]["id"] == str(w.case.pk)
    assert auth_client(w.a).get(f"{ROOT}/me").status_code == 403
    kinds = [item.kind for item in list_actions(actor=w.student).items]
    assert "SESSION_PROPOSAL_RESPONSE" in kinds
    accepted = post(
        student,
        f"{ROOT}/me/{proposal.pk}/accept",
        {"option_id": body["options"][0]["id"], "expected_version": body["version"]},
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["appointment"]["status"] == "SCHEDULED"
    detail = auth_client(w.a).get(f"/api/v1/counseling/cases/{w.case.pk}").json()
    assert detail["session_proposals"][0]["state"] == "ACCEPTED"
    assert detail["session_proposals"][0]["can_issue_call_slip"] is True


def test_slots_endpoint_and_propose_endpoint(ns):
    w = ns
    client = auth_client(w.a)
    slots = client.get(
        f"{ROOT}/slots",
        {"case_id": str(w.case.pk), "delivery_mode": "ONLINE", "date": w.start.date().isoformat()},
    )
    assert slots.status_code == 200 and slots.json()["items"]
    created = post(
        client,
        ROOT,
        {
            "case_id": str(w.case.pk),
            "purpose": "CHECK_IN",
            "options": [
                {"delivery_mode": "ONLINE", "starts_at": slots.json()["items"][0]["starts_at"]}
            ],
            "expected_case_version": w.case.version,
        },
    )
    assert created.status_code == 201, created.content
    assert created.json()["state"] == "PENDING"
    context_body = client.get(f"{ROOT}/context", {"case_id": str(w.case.pk)}).json()
    assert context_body["authority"] == "OWNER"
    assert context_body["open_proposal"]["id"] == created.json()["id"]
    assert context_body["student"]["id"] == str(w.student.pk)
    assert auth_client(w.b).get(f"{ROOT}/context", {"case_id": str(w.case.pk)}).status_code == 404
    refused = auth_client(w.b).get(
        f"{ROOT}/slots",
        {"case_id": str(w.case.pk), "delivery_mode": "ONLINE", "date": w.start.date().isoformat()},
    )
    assert refused.status_code == 404


def test_case_call_slip_after_acceptance_and_session_ends_it(ns):
    w = ns
    proposal = propose(w, call_slip=True)
    appointment = accept(w, proposal).appointment
    client = auth_client(w.a)
    payload = {
        "student_id": str(w.student.pk),
        "course_year": "BSIT 2",
        "destination_type": "GUIDANCE_OFFICE",
        "report_at": appointment.starts_at.isoformat(),
        "counseling_case_id": str(w.case.pk),
        "appointment_id": str(appointment.pk),
    }
    issued = post(client, "/api/v1/call-slips", payload, HTTP_IDEMPOTENCY_KEY=str(uuid4()))
    assert issued.status_code == 201, issued.content
    assert issued.json()["counseling_case"]["id"] == str(w.case.pk)
    link_row = CounselingCaseCallSlip.objects.get()
    assert (link_row.appointment_id, link_row.proposal_id) == (appointment.pk, proposal.pk)
    duplicate = post(client, "/api/v1/call-slips", payload, HTTP_IDEMPOTENCY_KEY=str(uuid4()))
    assert duplicate.status_code == 409
    # The office assistant's view never names the case.
    seen = auth_client(w.goa).get(f"/api/v1/call-slips/{link_row.call_slip_id}").json()
    assert seen["counseling_case"] is None
    # A Referral and a case at once is refused; an ordinary Call Slip is unchanged.
    both = post(
        client,
        "/api/v1/call-slips",
        {**payload, "appointment_id": None, "referral_id": str(uuid4())},
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert both.status_code == 422
    plain = post(
        client,
        "/api/v1/call-slips",
        {k: v for k, v in payload.items() if k not in {"counseling_case_id", "appointment_id"}},
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert plain.status_code == 201 and plain.json()["counseling_case"] is None
    assert CounselingCaseCallSlip.objects.count() == 1
    # Recording the session and adding it to the case ends the linked Call Slip only.
    Appointment.objects.filter(pk=appointment.pk).update(
        starts_at=timezone.now() - timedelta(hours=5),
        ends_at=timezone.now() - timedelta(hours=4),
    )
    appointment.refresh_from_db()
    encounter = record(w.a, w.student, appointment=appointment)
    link(w.a, w.case, encounter)
    linked = CallSlip.objects.get(pk=link_row.call_slip_id)
    assert linked.interview_ended_at == encounter.ended_at
    assert CallSlip.objects.get(pk=plain.json()["id"]).interview_ended_at is None


def test_followup_shortcuts_point_at_existing_work_and_prompt_only(ns):
    w = ns
    task = create_task(w)
    client = auth_client(w.a)
    detail = client.get(f"/api/v1/guidance-followups/{task.pk}").json()
    shortcuts = detail["shortcuts"]
    assert shortcuts["message_thread_id"] is None
    assert shortcuts["propose_session_case_id"] == str(w.case.pk)
    assert shortcuts["call_slip_case_id"] == str(w.case.pk)
    assert shortcuts["completion_prompt"] is None
    assert not GuidanceThread.objects.exists()
    appointment = create_student_appointment(
        student=w.student,
        service_id=CounselingSessionProposal._meta.get_field("service")
        .related_model.objects.get(code="COUNSELING")
        .pk,
        provider_id=w.a.pk,
        delivery_mode="ONLINE",
        starts_at=w.start + timedelta(hours=5),
        context=context(w.student),
    )
    thread = GuidanceThread.objects.create(
        kind="COUNSELING",
        student=w.student,
        counselor=w.a,
        relationship_appointment=appointment,
        created_by=w.student,
    )
    proposal = propose(w, follow_up=task)
    accept(w, proposal)
    shortcuts = client.get(f"/api/v1/guidance-followups/{task.pk}").json()["shortcuts"]
    assert shortcuts["message_thread_id"] == str(thread.pk)
    assert shortcuts["completion_prompt"]["reason"] == "SESSION_ACCEPTED"
    task.refresh_from_db()
    assert task.status == "PENDING"
    assert GuidanceThread.objects.count() == 1
    # Another Counselor gets neither the task nor its shortcuts.
    assert auth_client(w.b).get(f"/api/v1/guidance-followups/{task.pk}").status_code == 404


def test_covering_counselor_may_propose_only_while_coverage_is_active(ns):
    from tests.test_cw3_case_coverage import decide, offer

    w = ns
    task = create_task(w)
    end = timezone.now() + timedelta(days=3)
    decide(offer(w, tasks=(task,), expires_at=end), w.b, "accept")
    proposal = propose(w, actor=w.b, follow_up=task)
    assert proposal.proposed_by_id == w.b.pk
    appointment = accept(w, proposal).appointment
    assert appointment.provider_id == w.b.pk
    assert CounselingCaseAppointment.objects.get(appointment=appointment).case_id == w.case.pk
    with pytest.raises(CounselingCaseNotFound):
        propose(w, actor=w.b, starts=[w.start + timedelta(hours=3)], now=end + timedelta(minutes=1))
