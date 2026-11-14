"""RA-1: reassigning a session of an Active case follows the case-transfer authorization route."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from compass.accounts.models import Designation, UserDesignation
from compass.appointments.models import Appointment
from compass.appointments.services import reassign_appointment
from compass.audit.models import AuditEvent
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.counseling.case_appointment_services import link_appointment
from compass.counseling.case_continuity_rules import CaseContinuityError
from compass.counseling.case_reassignment_models import CaseAppointmentReassignment
from compass.counseling.case_reassignment_services import (
    decide_reassignment,
    pending_reassignment_work,
    request_reassignment,
)
from compass.notifications.models import Notification
from tests.test_appointments import future_local_start, weekly
from tests.test_counseling import auth_client, context, make_appointment
from tests.test_counseling_cases import intake, world


def csrf(client):
    return {"HTTP_X_CSRFTOKEN": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


@pytest.fixture
def ra():
    w = world("ra1")
    replace_office_weekly(windows=[weekly()], context=context(w.admin))
    for counselor in (w.a, w.b, w.head):
        replace_provider_weekly(
            provider_id=counselor.pk, windows=[weekly()], context=context(w.admin)
        )
    w.case = intake(w.a, w.student)
    w.appointment = session(w, provider=w.a)
    w.case.refresh_from_db()
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=w.appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    return w


def session(w, *, provider, hour=10):
    row = make_appointment(student=w.student, provider=provider, service=w.service)
    start = future_local_start(hour=hour)
    Appointment.objects.filter(pk=row.pk).update(
        starts_at=start, ends_at=start + timedelta(hours=1)
    )
    row.refresh_from_db()
    return row


def ask(w, actor, receiver, *, acknowledged=True, reason="Counselor on leave that day"):
    return request_reassignment(
        actor=actor,
        appointment_id=w.appointment.pk,
        provider_id=receiver.pk,
        reason=reason,
        acknowledged=acknowledged,
        context=context(actor),
    )


def decide(item, actor, action, reason=None):
    item.refresh_from_db()
    return decide_reassignment(
        actor=actor,
        reassignment_id=item.pk,
        action=action,
        expected_version=item.version,
        reason=reason,
        context=context(actor),
    )


def provider_of(w):
    return Appointment.objects.get(pk=w.appointment.pk).provider_id


@pytest.mark.django_db
def test_ordinary_appointments_still_reassign_directly(ra):
    w = ra
    plain = session(w, provider=w.a, hour=13)
    reassign_appointment(
        appointment_id=plain.pk, actor=w.a, provider_id=w.b.pk, reason="Leave", context=context(w.a)
    )
    assert Appointment.objects.get(pk=plain.pk).provider_id == w.b.pk
    assert not CaseAppointmentReassignment.objects.exists()


@pytest.mark.django_db
def test_direct_reassign_of_a_case_session_is_refused_except_back_to_the_case_owner(ra):
    w = ra
    client = auth_client(w.a)
    refused = client.post(
        f"/api/v1/appointments/{w.appointment.pk}/reassign",
        data=json.dumps({"provider_id": str(w.b.pk), "reason": "Leave"}),
        content_type="application/json",
        **csrf(client),
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "case_continuity_reassignment_request_required"
    assert provider_of(w) == w.a.pk

    # A session that drifted to another Counselor may always return to the case owner.
    Appointment.objects.filter(pk=w.appointment.pk).update(provider=w.b)
    reassign_appointment(
        appointment_id=w.appointment.pk,
        actor=w.b,
        provider_id=w.a.pk,
        reason="Back",
        context=context(w.b),
    )
    assert provider_of(w) == w.a.pk


@pytest.mark.django_db
def test_owner_request_waits_for_an_independent_head_then_applies(ra):
    w = ra
    item = ask(w, w.a, w.b)
    assert (item.state, item.route) == ("PENDING", "INDEPENDENT_HEAD")
    assert provider_of(w) == w.a.pk, "the session stays put until the Head approves"
    assert (
        Notification.objects.filter(
            recipient=w.head, event_code="counseling.case_reassignment.review"
        ).count()
        == 1
    )
    work = pending_reassignment_work(actor=w.head, limit=5, now=timezone.now())
    assert [row.kind for row in work] == ["CASE_REASSIGNMENT_APPROVAL"]
    assert work[0].due_at == w.appointment.starts_at
    assert pending_reassignment_work(actor=w.a, limit=5, now=timezone.now()) == ()

    with pytest.raises(CaseContinuityError) as denied:
        decide(item, w.a, "approve")
    assert denied.value.code == "case_continuity_reassignment_approval_denied"
    with pytest.raises(CaseContinuityError):
        decide(item, w.b, "approve")

    approved = decide(item, w.head, "approve", reason="OK for one session")
    assert approved.state == "APPROVED" and approved.decided_by_id == w.head.pk
    assert provider_of(w) == w.b.pk
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk, "the case itself never moves"
    applied = AuditEvent.objects.get(action="appointment.reassigned")
    assert applied.metadata["case_reassignment_id"] == str(item.pk)
    assert applied.metadata["case_route"] == "INDEPENDENT_HEAD"
    assert set(
        AuditEvent.objects.filter(action__startswith="counseling.case_reassignment.").values_list(
            "action", flat=True
        )
    ) == {"counseling.case_reassignment.requested", "counseling.case_reassignment.approved"}
    assert Notification.objects.filter(
        recipient=w.a, event_code="counseling.case_reassignment.decided"
    ).exists()
    assert Notification.objects.filter(recipient=w.b, event_code="appointment.reassigned").exists()


@pytest.mark.django_db
def test_office_request_decline_and_withdraw_never_move_the_session(ra):
    w = ra
    item = ask(w, w.a, w.b)
    declined = decide(item, w.head, "decline", reason="Keep continuity with the case owner")
    assert declined.state == "DECLINED" and declined.decision_reason.startswith("Keep")
    assert provider_of(w) == w.a.pk

    again = ask(w, w.a, w.b)
    with pytest.raises(CaseContinuityError):
        decide(again, w.head, "withdraw")
    withdrawn = decide(again, w.a, "withdraw")
    assert withdrawn.state == "WITHDRAWN" and provider_of(w) == w.a.pk


@pytest.mark.django_db
def test_a_changed_appointment_makes_the_request_no_longer_current(ra):
    w = ra
    item = ask(w, w.a, w.b)
    moved = w.appointment.starts_at + timedelta(hours=2)
    Appointment.objects.filter(pk=w.appointment.pk).update(
        starts_at=moved, ends_at=moved + timedelta(hours=1)
    )
    result = decide(item, w.head, "approve")
    assert result.state == "EXPIRED"
    assert provider_of(w) == w.a.pk
    assert AuditEvent.objects.filter(action="counseling.case_reassignment.expired").count() == 1
    # A fresh request replaces it.
    assert ask(w, w.a, w.b).state == "PENDING"


@pytest.mark.django_db
def test_request_rules(ra):
    w = ra
    with pytest.raises(CaseContinuityError) as no_ack:
        ask(w, w.a, w.b, acknowledged=False)
    assert no_ack.value.status == 422
    with pytest.raises(CaseContinuityError):
        ask(w, w.a, w.b, reason="  ")
    with pytest.raises(CaseContinuityError) as direct:
        ask(w, w.a, w.a)
    assert direct.value.code == "case_continuity_reassignment_direct"
    ask(w, w.a, w.b)
    with pytest.raises(CaseContinuityError) as pending:
        ask(w, w.a, w.b)
    assert pending.value.code == "case_continuity_reassignment_pending"
    with pytest.raises(CaseContinuityError) as hidden:
        ask(w, w.b, w.head)
    assert hidden.value.status == 404, "only someone who manages the Appointment may ask"


@pytest.mark.django_db
def test_the_head_owner_moves_their_own_case_session_directly_with_the_route_recorded(ra):
    w = ra
    head_case_student = w.other
    case = intake(w.head, head_case_student)
    row = make_appointment(student=head_case_student, provider=w.head, service=w.service)
    start = future_local_start(hour=14)
    Appointment.objects.filter(pk=row.pk).update(
        starts_at=start, ends_at=start + timedelta(hours=1)
    )
    case.refresh_from_db()
    link_appointment(
        actor=w.head,
        case_id=case.pk,
        appointment_id=row.pk,
        expected_version=case.version,
        context=context(w.head),
    )
    item = request_reassignment(
        actor=w.head,
        appointment_id=row.pk,
        provider_id=w.b.pk,
        reason="Head's schedule conflict",
        acknowledged=True,
        context=context(w.head),
    )
    assert (item.state, item.route) == ("APPROVED", "DIRECT_OUTGOING_HEAD")
    assert Appointment.objects.get(pk=row.pk).provider_id == w.b.pk


@pytest.mark.django_db
def test_without_any_independent_head_the_request_is_refused_like_a_transfer(ra):
    w = ra
    UserDesignation.objects.filter(
        user=w.head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    ).delete()
    with pytest.raises(CaseContinuityError) as refused:
        ask(w, w.a, w.b)
    assert refused.value.code == "case_continuity_no_independent_approver"
    assert provider_of(w) == w.a.pk


@pytest.mark.django_db
def test_api_context_request_review_and_decision(ra):
    w = ra
    owner = auth_client(w.a)
    context_response = owner.get(f"/api/v1/counseling/appointments/{w.appointment.pk}/reassignment")
    assert context_response.status_code == 200
    assert context_response.json()["case_owner"]["id"] == str(w.a.pk)
    assert context_response.json()["pending"] is None

    created = owner.post(
        f"/api/v1/counseling/appointments/{w.appointment.pk}/reassignment-requests",
        data=json.dumps({"provider_id": str(w.b.pk), "reason": "Leave", "acknowledged": True}),
        content_type="application/json",
        **csrf(owner),
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert (
        body["state"] == "PENDING" and body["can_withdraw"] is True and body["can_approve"] is False
    )
    assert "note" not in json.dumps(body).lower(), "no case narrative reaches the response"

    head = auth_client(w.head)
    review = head.get(f"/api/v1/counseling/appointment-reassignments/{body['id']}").json()
    assert review["can_approve"] is True
    assert (
        auth_client(w.b)
        .get(f"/api/v1/counseling/appointment-reassignments/{body['id']}")
        .status_code
        == 404
    )
    decided = head.post(
        f"/api/v1/counseling/appointment-reassignments/{body['id']}/decision",
        data=json.dumps({"action": "approve", "expected_version": review["version"]}),
        content_type="application/json",
        **csrf(head),
    )
    assert decided.status_code == 200, decided.content
    assert decided.json()["state"] == "APPROVED"
    assert (
        auth_client(w.b)
        .get(f"/api/v1/counseling/appointment-reassignments/{body['id']}")
        .status_code
        == 200
    )

    plain = session(w, provider=w.a, hour=15)
    assert owner.get(f"/api/v1/counseling/appointments/{plain.pk}/reassignment").json() == {
        "case_owner": None,
        "pending": None,
    }
