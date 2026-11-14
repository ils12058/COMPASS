"""CW-3a responsibility, audience, task and Appointment boundaries on real PostgreSQL."""

import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from compass.accounts.models import Designation, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling import case_transfer_projections as projections
from compass.counseling import case_transfer_services as transfers
from compass.counseling.case_continuity_rules import CaseContinuityError, state_at
from compass.counseling.case_models import CounselingCaseEvent
from compass.counseling.case_services import CounselingCaseNotFound, get_case
from compass.counseling.case_transfer_models import (
    CounselingCaseResponsibility,
    CounselingCaseTransfer,
    CounselingCaseTransferEvent,
)
from compass.guidance_followups import services as followups
from compass.guidance_followups.content import decrypt_text
from compass.guidance_followups.errors import FollowUpNotFound
from compass.guidance_followups.models import GuidanceFollowUp
from compass.notifications.current import notification_is_current
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.privacy_governance.activity import list_privacy_activity
from tests.test_appointment_management_scope import affiliate, auth_client, csrf, make_college
from tests.test_counseling import context, make_appointment, make_user
from tests.test_counseling_cases import intake, link, record, world
from tests.test_cw2_next_actions import create as create_task

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/counseling/continuity"


def future_appointment(w):
    appointment = make_appointment(student=w.student, provider=w.a, service=w.service)
    appointment.starts_at = timezone.now() + timedelta(days=2)
    appointment.ends_at = appointment.starts_at + timedelta(hours=1)
    appointment.save(update_fields=["starts_at", "ends_at"])
    return appointment


def transfer_world(settings, prefix="cw3"):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    w = world(prefix)
    w.case = intake(w.a, w.student)
    college = make_college(prefix)
    affiliate(w.student, college)
    CounselorResponsibility.objects.create(college=college, counselor=w.a)
    StaffSupervision.objects.create(staff=w.goa, supervisor=w.a)
    return w


@pytest.fixture
def cw3(settings):
    return transfer_world(settings)


def values(w, *, actor=None, receiver=None, reason="SERVICE_RESPONSIBILITY_CHANGE", **changes):
    actor, receiver = actor or w.a, receiver or w.b
    w.case.refresh_from_db()
    package = projections.transfer_context(actor=actor, case_id=w.case.pk, reason=reason)
    result = {
        "expected_case_version": w.case.version,
        "receiving_counselor_id": receiver.pk,
        "reason": reason,
        "tasks": [
            {
                "task_id": task["task_id"],
                "expected_version": task["version"],
                "disposition": "TRANSFER"
                if task["source_kind"] is None
                else "RESOLVE_FIRST"
                if actor.pk != w.case.primary_counselor_id or reason == "IMPARTIALITY_CONCERN"
                else "RETAIN",
            }
            for task in package["tasks"]
        ],
        "appointments": [
            {
                "link_id": appointment["link_id"],
                "disposition": "RETAIN_WITH_PROVIDER",
                "retention_reason": "CONTINUING_SUPPORT",
            }
            for appointment in package["appointments"]
        ],
        "student_communication": "NO",
    }
    if actor.pk != w.case.primary_counselor_id:
        result["office_preparation_reason"] = "OWNER_UNAVAILABLE"
    result.update(changes)
    return result


def prepare(w, *, actor=None, receiver=None, **changes):
    actor = actor or w.a
    return transfers.prepare_transfer(
        actor=actor,
        case_id=w.case.pk,
        values=values(w, actor=actor, receiver=receiver, **changes),
        context=context(actor),
    )


def ensure_handoff(item, actor):
    """Supply the real CW-3b prerequisite for existing transfer-boundary scenarios."""
    from compass.counseling.case_continuity_rules import eligible_authorizers
    from compass.counseling.case_handoff_services import operate

    if item.case_handoff_id or item.handoff_exception_id:
        return item
    if actor.pk == item.outgoing_counselor_id:
        body = operate(
            actor=actor,
            transfer_id=item.pk,
            operation="save",
            expected_transfer_version=item.version,
            sections={
                "context_and_purpose": "Continuing student support.",
                "support_and_progress": "Support reviewed.",
                "continuing_considerations": "Review the current plan.",
                "receiver_next_steps": "Review and handle the specified actions.",
            },
        )
        operate(
            actor=actor,
            transfer_id=item.pk,
            operation="submit",
            expected_transfer_version=body["transfer_version"],
            expected_handoff_version=body["version"],
        )
    else:
        head = eligible_authorizers(
            requester_id=actor.pk, receiver_id=item.receiving_counselor_id, now=timezone.now()
        )[0]
        operate(
            actor=head,
            transfer_id=item.pk,
            operation="exception",
            expected_transfer_version=item.version,
            exception_reason="OWNER_UNAVAILABLE",
        )
    item.refresh_from_db()
    return item


def submit(item, actor):
    item = ensure_handoff(item, actor)
    return transfers.submit_transfer(
        actor=actor, transfer_id=item.pk, expected_version=item.version, context=context(actor)
    )


def decide(item, actor, action, reason=None):
    return transfers.decide_transfer(
        actor=actor,
        transfer_id=item.pk,
        expected_version=item.version,
        action=action,
        reason=reason,
        context=context(actor),
    )


def offer(w, *, actor=None, receiver=None, **changes):
    actor = actor or w.a
    item = submit(prepare(w, actor=actor, receiver=receiver, **changes), actor)
    return decide(item, w.head, "authorize") if item.state == "PREPARED" else item


def write(client, method, path, data):
    return getattr(client, method)(
        path,
        data=json.dumps(data, default=str),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(client),
    )


def test_current_owner_can_review_earlier_transfer_history_after_two_transfers(cw3):
    w = cw3
    first = decide(offer(w), w.b, "accept")
    third = make_user("cw3-third@example.edu", "COUNSELOR")
    second = offer(w, actor=w.b, receiver=third)
    decide(second, third, "accept")
    earlier = transfers.get_transfer(actor=third, transfer_id=first.pk)
    projection = projections.transfer_detail(earlier, third)
    assert projection["can_open_case"] and projection["state"] == "ACCEPTED"
    assert projection["tasks"] == projection["appointments"] == []
    w.case.refresh_from_db()
    periods = projections.case_continuity(w.case, third)["responsibility"]
    assert [period["counselor"]["id"] for period in periods] == [w.a.pk, w.b.pk, third.pk]
    assert periods[0]["derived_opening"] and periods[0]["ended_at"]
    assert periods[1]["ended_at"] and periods[2]["ended_at"] is None
    with pytest.raises(CounselingCaseNotFound):
        get_case(actor=w.a, case_id=w.case.pk)


@pytest.mark.parametrize("route", ["ordinary", "outgoing_head", "owner_to_head", "second_head"])
def test_approval_matrix_and_explicit_acceptance(cw3, route):
    w = cw3
    actor, receiver = w.a, w.b
    if route == "outgoing_head":
        w.case = intake(w.head, w.student)
        actor = w.head
    elif route in {"owner_to_head", "second_head"}:
        receiver = w.head
    if route == "second_head":
        second = make_user("cw3-head2@example.edu", "COUNSELOR")
        UserDesignation.objects.create(
            user=second, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
    item = submit(prepare(w, actor=actor, receiver=receiver), actor)
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == actor.pk
    assert item.independent_authorization is (route in {"ordinary", "second_head"})
    if route in {"ordinary", "second_head"}:
        assert item.state == "PREPARED" and item.review_expires_at is None
        with pytest.raises(CaseContinuityError):
            decide(item, receiver, "accept")
        item = decide(item, second if route == "second_head" else w.head, "authorize")
    else:
        assert item.state == "AUTHORIZED"
        assert item.authorization_route == (
            "OWNER_TO_HEAD" if route == "owner_to_head" else "DIRECT_OUTGOING_HEAD"
        )
    assert item.review_expires_at == item.authorized_at + timedelta(days=7)
    item = decide(item, receiver, "accept")
    w.case.refresh_from_db()
    assert item.state == "ACCEPTED" and w.case.primary_counselor_id == receiver.pk
    assert (
        CounselingCaseResponsibility.objects.filter(
            case=w.case, counselor=receiver, ended_at__isnull=True
        ).count()
        == 1
    )
    assert list(CounselingCaseEvent.objects.filter(case=w.case).values_list("kind", flat=True)) == [
        "OPENED"
    ]
    assert CounselingCaseTransferEvent.objects.filter(transfer=item, kind="accepted").count() == 1
    if route == "owner_to_head":
        audit = AuditEvent.objects.get(action="counseling.case_transfer.accepted")
        assert audit.metadata["independent_authorization"] is False
        activity = list_privacy_activity(event_type="counseling.case_transfer.accepted")
        assert (
            len(activity.items) == 1
            and "no independent Head authorization" in activity.items[0].description
        )
        assert (
            projections.case_continuity(w.case, receiver)["history"][0]["independent_authorization"]
            is False
        )


def test_office_to_only_head_and_head_as_requester_receiver_are_blocked_before_writes(cw3):
    w = cw3
    for actor in (w.goa, w.head):
        with pytest.raises(
            CaseContinuityError, match="No independent approver|another active Counselor"
        ):
            prepare(
                w,
                actor=actor,
                receiver=w.head,
                student_communication="DEFERRED",
                communication_deferral_reason="CONTACT_PENDING",
                communication_next_action="Inform the Student",
                communication_due_at=timezone.now() + timedelta(days=1),
            )
    assert CounselingCaseTransfer.objects.count() == GuidanceFollowUp.objects.count() == 0
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk


def test_office_prepares_unavailable_owner_without_clinical_impersonation(cw3):
    w = cw3
    task = create_task(w)
    w.a.is_active = False
    w.a.save(update_fields=["is_active"])
    # Keep legitimate office routing via the current Head while the owner is unavailable.
    StaffSupervision.objects.filter(staff=w.goa).update(supervisor=w.head)
    with patch.object(
        projections,
        "decrypt_text",
        side_effect=AssertionError("Office must never decrypt task titles"),
    ):
        package = projections.transfer_context(actor=w.goa, case_id=w.case.pk)
        assert package["tasks"][0]["title"] is None
        item = prepare(w, actor=w.goa)
        detail = projections.transfer_detail(item, w.goa)
        assert detail["tasks"][0]["title"] is None
    assert item.prepared_by_id == w.goa.pk and item.outgoing_counselor_id == w.a.pk
    item = decide(submit(item, w.goa), w.head, "authorize")
    decide(item, w.b, "accept")
    task.refresh_from_db()
    assert task.assigned_to_id == w.b.pk and task.created_by_id == w.a.pk


@pytest.mark.parametrize("decision", ["pending", "decline", "cancel", "expire"])
def test_terminal_or_pending_offer_leaves_owner_and_ends_review(cw3, decision):
    w = cw3
    task = create_task(w)
    item = offer(w)
    if decision == "decline":
        item = decide(item, w.b, "decline", "NO_CAPACITY")
    elif decision == "cancel":
        item = decide(item, w.a, "cancel", "REQUEST_WITHDRAWN")
    elif decision == "expire":
        CounselingCaseTransfer.objects.filter(pk=item.pk).update(
            review_expires_at=timezone.now() - timedelta(seconds=1)
        )
        item.refresh_from_db()
        assert state_at(item) == "EXPIRED" and item.state == "AUTHORIZED"
    w.case.refresh_from_db()
    task.refresh_from_db()
    assert w.case.primary_counselor_id == task.assigned_to_id == w.a.pk
    assert not CounselingCaseResponsibility.objects.exists()
    detail = projections.transfer_detail(item, w.b)
    assert detail["review_accessible"] is (decision == "pending")
    if decision != "pending":
        assert detail["tasks"] == detail["appointments"] == []
        assert projections.transfer_summary(item)["needs_new_arrangement"]
        with pytest.raises(CaseContinuityError):
            decide(item, w.b, "accept")


def test_accepted_receiver_gets_case_tasks_but_no_authored_sources_and_old_owner_keeps_sources(cw3):
    w = cw3
    session = record(w.a, w.student)
    link(w.a, w.case, session)
    task = create_task(w)
    item = decide(offer(w), w.b, "accept")
    with pytest.raises(CounselingCaseNotFound):
        get_case(actor=w.a, case_id=w.case.pk)
    with pytest.raises(FollowUpNotFound):
        followups.get_followup(actor=w.a, followup_id=task.pk)
    assert followups.get_followup(actor=w.b, followup_id=task.pk).assigned_to_id == w.b.pk
    overview = get_case(actor=w.b, case_id=w.case.pk)
    assert overview.summary.session_count == 1 and not overview.sessions[0].record_accessible
    from compass.counseling.services import get_encounter_for_actor

    assert get_encounter_for_actor(actor=w.a, encounter_id=session.pk).pk == session.pk
    for actor in (w.b, w.head, w.goa, w.student, w.admin, w.faculty, w.officer):
        response = auth_client(actor).get(f"/api/v1/counseling/encounters/{session.pk}")
        assert response.status_code in {403, 404}
    event = task.events.get(kind="REASSIGNED")
    assert event.case_transfer_id == item.pk
    assert not projections.transfer_detail(item, w.a)["can_open_case"]


@pytest.mark.parametrize("disposition", ["RETAIN", "HAND_OVER_AS_NEW", "RESOLVE_FIRST"])
def test_confidential_source_tasks_preserve_independent_source_authority(cw3, disposition):
    w = cw3
    session = record(w.a, w.student)
    link(w.a, w.case, session)
    task = create_task(w, source_kind="COUNSELING_ENCOUNTER", source_id=session.pk)
    task_plan = {"task_id": task.pk, "expected_version": task.version, "disposition": disposition}
    if disposition == "HAND_OVER_AS_NEW":
        task_plan.update(
            successor_title="Continue the agreed next action",
            successor_due_at=timezone.now() + timedelta(days=3),
        )
    item = offer(w, tasks=[task_plan])
    if disposition == "RESOLVE_FIRST":
        with pytest.raises(CaseContinuityError, match="Complete or cancel"):
            decide(item, w.b, "accept")
        response = write(
            auth_client(w.a, recent_mfa=True),
            "post",
            f"/api/v1/guidance-followups/{task.pk}/complete",
            {
                "expected_version": task.version,
                "outcome": "Completed through the ordinary Follow-up workflow",
            },
        )
        assert response.status_code == 200, response.content
    decide(item, w.b, "accept")
    task.refresh_from_db()
    if disposition == "RETAIN":
        assert task.assigned_to_id == w.a.pk and task.status == "PENDING"
        assert followups.get_followup(actor=w.a, followup_id=task.pk).pk == task.pk
    elif disposition == "HAND_OVER_AS_NEW":
        successor = task.successors.get()
        assert successor.assigned_to_id == w.b.pk and successor.created_by_id == w.a.pk
        assert (
            successor.case_id == w.case.pk
            and successor.source_kind is None
            and successor.source_id is None
        )
        assert successor.description_ciphertext is None and task.status == "CANCELLED"
        assert (
            decrypt_text(successor.pk, "title", successor.title_ciphertext)
            == "Continue the agreed next action"
        )
        assert task.events.get(kind="CANCELLED").case_transfer_id == item.pk
    else:
        assert task.status == "COMPLETED"
    with pytest.raises(FollowUpNotFound):
        followups.get_followup(actor=w.b, followup_id=task.pk)


def test_conflict_retain_and_case_only_retain_and_office_successor_are_refused(cw3):
    w = cw3
    case_task = create_task(w)
    with pytest.raises(CaseContinuityError):
        prepare(
            w, tasks=[{"task_id": case_task.pk, "expected_version": 1, "disposition": "RETAIN"}]
        )
    session = record(w.a, w.student)
    source_task = create_task(w, source_kind="COUNSELING_ENCOUNTER", source_id=session.pk)
    plans = [
        {"task_id": case_task.pk, "expected_version": 1, "disposition": "TRANSFER"},
        {"task_id": source_task.pk, "expected_version": 1, "disposition": "RETAIN"},
    ]
    with pytest.raises(CaseContinuityError):
        prepare(w, reason="IMPARTIALITY_CONCERN", tasks=plans)
    plans[1].update(
        disposition="HAND_OVER_AS_NEW",
        successor_title="Unsafe office invention",
        successor_due_at=timezone.now() + timedelta(days=1),
    )
    with pytest.raises(CaseContinuityError):
        prepare(w, actor=w.goa, tasks=plans)


@pytest.mark.parametrize(
    "change", ["new_task", "task_version", "owner", "closed", "receiver_inactive"]
)
def test_stale_acceptance_has_no_partial_task_or_responsibility_effects(cw3, change):
    w = cw3
    task = create_task(w)
    item = offer(w)
    if change == "new_task":
        create_task(w)
    elif change == "task_version":
        GuidanceFollowUp.objects.filter(pk=task.pk).update(version=2)
    elif change == "owner":
        type(w.case).objects.filter(pk=w.case.pk).update(primary_counselor=w.head)
    elif change == "closed":
        type(w.case).objects.filter(pk=w.case.pk).update(status="CLOSED")
    else:
        type(w.b).objects.filter(pk=w.b.pk).update(is_active=False)
    with pytest.raises(CaseContinuityError):
        decide(item, w.b, "accept")
    task.refresh_from_db()
    assert task.assigned_to_id == w.a.pk and task.events.count() == 1
    assert not CounselingCaseResponsibility.objects.exists()
    item.refresh_from_db()
    assert item.state == "AUTHORIZED"


def test_editing_an_authorized_plan_invalidates_review_and_preserves_previous_history(cw3):
    w = cw3
    item = offer(w)
    stale_version = item.version
    item = transfers.prepare_transfer(
        actor=w.a,
        case_id=w.case.pk,
        transfer_id=item.pk,
        expected_version=stale_version,
        values=values(w, reason="PLANNED_ABSENCE"),
        context=context(w.a),
    )
    assert (
        item.state == "PREPARED" and item.authorized_at is None and item.authorized_version is None
    )
    assert item.history.filter(kind="authorized").count() == 1
    with pytest.raises(CaseContinuityError):
        transfers.decide_transfer(
            actor=w.b,
            transfer_id=item.pk,
            expected_version=stale_version,
            action="accept",
            context=context(w.b),
        )
    with pytest.raises(CaseContinuityError):
        projections.transfer_context(actor=w.b, case_id=w.case.pk)


def test_deferred_communication_creates_an_attributed_case_task_and_transfers_it(cw3):
    w = cw3
    with pytest.raises(CaseContinuityError):
        prepare(w, student_communication="DEFERRED")
    item = offer(
        w,
        student_communication="DEFERRED",
        communication_deferral_reason="CONTACT_PENDING",
        communication_next_action="Inform the Student about the new Counselor",
        communication_due_at=timezone.now() + timedelta(days=2),
    )
    task = item.communication_task
    assert (
        task.case_id == w.case.pk and task.assigned_to_id == w.a.pk and task.created_by_id == w.a.pk
    )
    assert item.task_plans.get(task=task).disposition == "TRANSFER"
    decide(item, w.b, "accept")
    task.refresh_from_db()
    assert task.assigned_to_id == w.b.pk and task.status == "PENDING"
    assert not Notification.objects.filter(recipient=w.student).exists()


def test_retained_appointment_remains_next_with_provider_and_no_new_link_bypass(cw3):
    from compass.counseling.case_appointment_services import (
        link_appointment,
        list_appointment_candidates,
    )

    w = cw3
    appointment = future_appointment(w)
    w.case.refresh_from_db()
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    decide(offer(w), w.b, "accept")
    overview = get_case(actor=w.b, case_id=w.case.pk)
    assert (
        overview.next_appointment.pk == appointment.pk
        and overview.next_appointment.provider_id == w.a.pk
    )
    assert list_appointment_candidates(actor=w.b, case_id=w.case.pk).items == ()
    response = auth_client(w.b).get(f"/api/v1/counseling/cases/{w.case.pk}")
    assert response.status_code == 200, response.content
    row = response.json()["next_appointment"]
    assert row["provider"]["id"] == str(w.a.pk) and row["record_accessible"] is False


@pytest.mark.parametrize("disposition", ["REASSIGN", "CANCEL", "RESCHEDULE"])
def test_appointment_action_must_be_completed_before_acceptance(cw3, disposition):
    from compass.counseling.case_appointment_services import link_appointment

    w = cw3
    appointment = future_appointment(w)
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    plan = {"link_id": w.case.appointment_links.get().pk, "disposition": disposition}
    item = offer(w, appointments=[plan])
    with pytest.raises(CaseContinuityError, match="through Appointments"):
        decide(item, w.b, "accept")
    # This tests the acceptance predicate independently of the Appointment action suites.
    if disposition == "REASSIGN":
        type(appointment).objects.filter(pk=appointment.pk).update(provider=w.b)
    elif disposition == "CANCEL":
        type(appointment).objects.filter(pk=appointment.pk).update(
            status="CANCELLED", cancelled_at=timezone.now(), cancelled_by=w.head
        )
    else:
        type(appointment).objects.filter(pk=appointment.pk).update(
            starts_at=appointment.starts_at + timedelta(days=1),
            ends_at=appointment.ends_at + timedelta(days=1),
        )
    decide(item, w.b, "accept")
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.b.pk


def test_impartiality_transfer_cannot_retain_outgoing_appointment_provider(cw3):
    from compass.counseling.case_appointment_services import link_appointment

    w = cw3
    appointment = future_appointment(w)
    link_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=appointment.pk,
        expected_version=w.case.version,
        context=context(w.a),
    )
    with pytest.raises(CaseContinuityError, match="cannot retain"):
        prepare(w, reason="IMPARTIALITY_CONCERN")


def test_http_roles_review_work_queue_and_content_free_notifications(cw3):
    w = cw3
    task = create_task(w)
    actor = auth_client(w.a)
    response = write(actor, "post", f"{ROOT}/cases/{w.case.pk}/transfers", values(w))
    assert response.status_code == 201, response.content
    item = response.json()
    for other in (w.student, w.faculty, w.admin, w.officer, w.b):
        denied = auth_client(other).get(f"{ROOT}/transfers/{item['id']}")
        assert denied.status_code in {403, 404}, denied.content
    ready = ensure_handoff(CounselingCaseTransfer.objects.get(pk=item["id"]), w.a)
    item["version"] = ready.version
    response = write(
        actor,
        "post",
        f"{ROOT}/transfers/{item['id']}/submit",
        {"expected_version": item["version"]},
    )
    assert response.status_code == 200, response.content
    queue = auth_client(w.head).get("/api/v1/work").json()["items"]
    assert any(row["kind"] == "CASE_TRANSFER_AUTHORIZATION" for row in queue)
    head_client = auth_client(w.head)
    response = write(
        head_client,
        "post",
        f"{ROOT}/transfers/{item['id']}/authorize",
        {"expected_version": response.json()["version"]},
    )
    assert response.status_code == 200, response.content
    receiver_client = auth_client(w.b)
    review = receiver_client.get(f"{ROOT}/transfers/{item['id']}").json()
    assert review["review_accessible"] and review["tasks"][0]["title"] is None
    assert auth_client(w.b).get(f"/api/v1/counseling/cases/{w.case.pk}").status_code == 404
    response = write(
        receiver_client,
        "post",
        f"{ROOT}/transfers/{item['id']}/accept",
        {"expected_version": review["version"]},
    )
    assert response.status_code == 200 and response.json()["state"] == "ACCEPTED"
    notices = list(Notification.objects.filter(event_code="counseling.case_transfer.review"))
    assert {notice.recipient_id for notice in notices} == {w.head.pk, w.b.pk}
    assert all(not notification_is_current(notice) for notice in notices)
    assert not EmailDelivery.objects.filter(notification__in=notices).exists()
    for notice in notices:
        assert w.student.get_full_name() not in notice.message + notice.title
        assert "support exercise" not in notice.message + notice.title
    audits = list(
        AuditEvent.objects.filter(action__startswith="counseling.case_transfer.").values_list(
            "metadata", flat=True
        )
    )
    assert all(
        w.student.get_full_name() not in json.dumps(metadata)
        and "support exercise" not in json.dumps(metadata)
        for metadata in audits
    )
    task.refresh_from_db()
    assert task.assigned_to_id == w.b.pk
