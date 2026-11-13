"""Closed-case responsibility changes use office preparation and independent review."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import Designation, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling import case_transfer_projections as projections
from compass.counseling import case_transfer_services as transfers
from compass.counseling.case_closure_content import encrypt, read
from compass.counseling.case_closure_models import CounselingCaseClosure
from compass.counseling.case_continuity_rules import CaseContinuityError, lock_case
from compass.counseling.case_models import CounselingCaseEvent
from compass.counseling.case_services import CounselingCaseError, CounselingCaseNotFound, get_case
from compass.counseling.case_transfer_models import CounselingCaseResponsibility
from compass.counseling.case_transfer_work import pending_transfer_work
from compass.guidance_followups import services as followups
from compass.notifications.current import notification_is_current
from compass.notifications.models import Notification
from tests.test_counseling import auth_client, context, make_user
from tests.test_counseling_cases_concurrency import fresh, race
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_transfers import ROOT, decide, transfer_world, write

pytestmark = pytest.mark.django_db
NOTE = "Protected attempts and conclusion retained for the case owner."


def record_closure(w):
    w.closure = CounselingCaseClosure(
        case=w.case, closed_by=w.a, reason="STUDENT_DISCONTINUED", outcome="NOT_ASSESSED"
    )
    w.closure.content_ciphertext = encrypt(w.closure, NOTE)
    w.closure.save(force_insert=True)
    w.case.status = "CLOSED"
    w.case.version += 1
    w.case.save(update_fields=["status", "version", "updated_at"])
    return w


def closed_world(settings, prefix="cw4-transfer"):
    return record_closure(transfer_world(settings, prefix))


@pytest.fixture
def cw4(settings):
    return closed_world(settings)


def reopening_values(w, **changes):
    w.case.refresh_from_db()
    values = {
        "expected_case_version": w.case.version,
        "purpose": "REOPEN",
        "receiving_counselor_id": w.b.pk,
        "reason": "UNEXPECTED_ABSENCE",
        "office_preparation_reason": "OWNER_UNAVAILABLE",
        "student_communication": "NO",
        "tasks": [],
        "appointments": [],
    }
    values.update(changes)
    return values


def prepare(w, actor=None, **changes):
    actor = actor or w.goa
    return transfers.prepare_transfer(
        actor=actor,
        case_id=w.case.pk,
        values=reopening_values(w, **changes),
        context=context(actor),
    )


def submit(item, actor):
    return transfers.submit_transfer(
        actor=actor, transfer_id=item.pk, expected_version=item.version, context=context(actor)
    )


def offered(w):
    return decide(submit(prepare(w), w.goa), w.head, "authorize")


def test_office_prepares_minimal_closed_lookup_and_receiver_review_reopens_atomically(cw4):
    w = cw4
    original = {
        name: getattr(w.closure, name)
        for name in ("closed_by_id", "closed_at", "reason", "outcome", "content_ciphertext")
    }
    lookup = projections.lookup_cases(actor=w.goa, status="CLOSED")
    assert [row["id"] for row in lookup["items"]] == [w.case.pk]
    assert projections.lookup_cases(actor=w.goa)["items"] == []
    package = projections.transfer_context(actor=w.goa, case_id=w.case.pk, purpose="REOPEN")
    assert package["purpose"] == "REOPEN" and package["office_prepared"]
    assert package["tasks"] == package["appointments"] == []
    assert package["case"]["status"] == "CLOSED"
    assert set(package["case"]) == {
        "id",
        "reference_code",
        "student",
        "primary_counselor",
        "status",
        "version",
    }
    item = prepare(w)
    assert item.purpose == "REOPEN" and item.handoff_required_at is None
    projection = projections.transfer_detail(item, w.goa)
    assert projection["can_submit"] and not projection["handoff_required"]
    assert not projection["can_write_handoff"] and projection["handoff"] is None
    item = submit(item, w.goa)
    assert item.state == "PREPARED" and item.independent_authorization
    with pytest.raises(CaseContinuityError):
        decide(item, w.b, "accept")
    item = decide(item, w.head, "authorize")
    assert item.authorization_route == "INDEPENDENT_HEAD"
    assert pending_transfer_work(actor=w.b, limit=20, now=timezone.now())[0].source_id == item.pk
    assert all(notification_is_current(row) for row in Notification.objects.filter(recipient=w.b))
    reviewed = projections.transfer_detail(item, w.b)
    assert reviewed["can_accept"] and reviewed["review_accessible"]
    assert reviewed["case"]["status"] == "CLOSED" and reviewed["purpose"] == "REOPEN"
    assert reviewed["tasks"] == reviewed["appointments"] == []
    assert NOTE not in str(reviewed)
    version = w.case.version
    decide(item, w.b, "accept")
    w.case.refresh_from_db()
    w.closure.refresh_from_db()
    assert w.case.status == "ACTIVE" and w.case.primary_counselor_id == w.b.pk
    assert w.case.version == version + 1
    assert w.closure.reopened_by_id == w.b.pk
    assert w.closure.reopen_reason == "FURTHER_SUPPORT_NEEDED"
    assert w.closure.reopened_at and read(w.closure) == NOTE
    assert all(getattr(w.closure, name) == value for name, value in original.items())
    assert CounselingCaseResponsibility.objects.get(case=w.case).counselor_id == w.b.pk
    assert list(CounselingCaseEvent.objects.filter(case=w.case).values_list("kind", flat=True)) == [
        "OPENED"
    ]
    assert AuditEvent.objects.filter(action="counseling.case.reopened").count() == 1
    assert NOTE not in str(list(AuditEvent.objects.values_list("metadata", flat=True)))
    with pytest.raises(CounselingCaseNotFound):
        get_case(actor=w.a, case_id=w.case.pk)


@pytest.mark.parametrize("role", ["a", "b", "faculty", "student", "admin", "officer"])
def test_only_office_preparation_has_access_and_never_grants_case_read(cw4, role):
    w = cw4
    actor = getattr(w, role)
    with pytest.raises(CaseContinuityError):
        prepare(w, actor=actor)
    with pytest.raises(CaseContinuityError):
        projections.transfer_context(actor=actor, case_id=w.case.pk, purpose="REOPEN")
    if role != "a":
        with pytest.raises(CounselingCaseError):
            get_case(actor=actor, case_id=w.case.pk)
    with pytest.raises(CaseContinuityError):
        projections.transfer_context(actor=w.goa, case_id=uuid4(), purpose="REOPEN")


def test_single_head_cannot_receive_an_office_prepared_reopening(cw4):
    w = cw4
    with pytest.raises(CaseContinuityError) as refused:
        prepare(w, receiving_counselor_id=w.head.pk)
    assert refused.value.code == "case_continuity_no_independent_approver"
    package = projections.transfer_context(actor=w.goa, case_id=w.case.pk, purpose="REOPEN")
    head_option = next(
        row for row in package["receiver_options"] if row["person"]["id"] == w.head.pk
    )
    assert head_option["authorization_route"] is None and head_option["blocked_reason"]
    assert not w.case.transfers.exists()


def test_another_independent_head_keeps_the_existing_matrix(cw4):
    w = cw4
    second = make_user("cw4-independent-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=second, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    item = submit(prepare(w, receiving_counselor_id=w.head.pk), w.goa)
    with pytest.raises(CaseContinuityError):
        decide(item, w.head, "authorize")
    item = decide(item, second, "authorize")
    decide(item, w.head, "accept")
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.head.pk and w.case.status == "ACTIVE"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"office_preparation_reason": None}, "office_reason_required"),
        ({"office_preparation_reason": "IMPARTIALITY_CONCERN"}, "office_reason_required"),
        ({"handoff_sections": {}}, "reopening_plan_forbidden"),
        ({"tasks": [{"task_id": uuid4()}]}, "reopening_plan_forbidden"),
        ({"appointments": [{"link_id": uuid4()}]}, "reopening_plan_forbidden"),
        ({"student_communication": "DEFERRED"}, "reopening_task_forbidden"),
    ],
)
def test_reopening_package_cannot_change_retained_work_or_create_new_work(cw4, change, code):
    with pytest.raises(CaseContinuityError) as refused:
        prepare(cw4, **change)
    assert refused.value.code == "case_continuity_" + code
    assert not cw4.case.transfers.exists()


def test_ordinary_transfers_require_active_and_reopening_transfers_require_closed(cw4):
    w = cw4
    with pytest.raises(CaseContinuityError) as refused:
        prepare(w, purpose=None)
    assert refused.value.code == "case_continuity_case_not_active"
    w.case.status = "ACTIVE"
    w.case.save(update_fields=["status"])
    with pytest.raises(CaseContinuityError) as refused:
        prepare(w)
    assert refused.value.code == "case_continuity_case_not_closed"


def test_transfer_purpose_cannot_switch_during_edit(cw4):
    w = cw4
    item = prepare(w)
    with pytest.raises(CaseContinuityError) as refused:
        transfers.prepare_transfer(
            actor=w.goa,
            case_id=w.case.pk,
            transfer_id=item.pk,
            expected_version=item.version,
            values=reopening_values(w, purpose=None),
            context=context(w.goa),
        )
    assert refused.value.code == "case_continuity_purpose_changed"
    item.refresh_from_db()
    assert item.purpose == "REOPEN" and item.version == 1


def test_stale_acceptance_after_owner_reopens_changes_nothing(cw4):
    w = cw4
    item = offered(w)
    from compass.counseling.case_closure_services import reopen_locked_case

    with transaction.atomic():
        case = lock_case(w.case.pk)
        reopen_locked_case(case=case, actor=w.a, context=context(w.a), now=timezone.now())
    with pytest.raises(CaseContinuityError) as refused:
        decide(item, w.b, "accept")
    assert refused.value.code == "case_continuity_case_not_closed"
    w.case.refresh_from_db()
    w.closure.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk and w.closure.reopened_by_id == w.a.pk
    assert not CounselingCaseResponsibility.objects.exists()
    assert all(
        not notification_is_current(row) for row in Notification.objects.filter(recipient=w.b)
    )
    receiver_view = projections.transfer_detail(item, w.b)
    assert receiver_view["can_decline"] and not receiver_view["can_accept"]
    current = projections.transfer_detail(item, w.a)
    assert current["can_cancel"]
    cancelled = decide(item, w.a, "cancel", "REQUEST_WITHDRAWN")
    assert cancelled.state == "CANCELLED"
    w.closure.refresh_from_db()
    assert w.closure.reopened_by_id == w.a.pk


def test_missing_closure_cycle_returns_a_clean_http_conflict(cw4):
    w = cw4
    item = offered(w)
    # Simulate retained inconsistent history without deleting or changing a closure's fixed data.
    w.closure.reopened_by, w.closure.reopened_at, w.closure.reopen_reason = (
        w.a,
        timezone.now(),
        "CLOSED_IN_ERROR",
    )
    w.closure.save(update_fields=["reopened_by", "reopened_at", "reopen_reason"])
    receiver = auth_client(w.b)
    reply = write(
        receiver, "post", f"{ROOT}/transfers/{item.pk}/accept", {"expected_version": item.version}
    )
    assert reply.status_code == 409, reply.content
    assert reply.json()["error"]["code"] == "counseling_case_changed"
    assert not CounselingCaseResponsibility.objects.exists()


def test_failed_acceptance_rolls_back_reopening_and_new_responsibility(cw4):
    w = cw4
    item = offered(w)
    with patch.object(
        transfers, "record_event", side_effect=RuntimeError("Synthetic audit failure")
    ):
        with pytest.raises(RuntimeError):
            decide(item, w.b, "accept")
    w.case.refresh_from_db()
    w.closure.refresh_from_db()
    assert w.case.status == "CLOSED" and w.case.primary_counselor_id == w.a.pk
    assert w.closure.reopened_at is None
    assert not CounselingCaseResponsibility.objects.exists()
    assert not AuditEvent.objects.filter(action="counseling.case.reopened").exists()


def test_after_closure_action_keeps_its_owner_and_remains_manageable_after_reopening(settings):
    w = transfer_world(settings, "cw4-retained-action")
    task = create_task(w, title="File the administrative service receipt")
    record_closure(w)
    task.post_closure_designated_at = w.closure.closed_at
    task.post_closure_closure = w.closure
    task.save(update_fields=["post_closure_designated_at", "post_closure_closure"])
    decide(offered(w), w.b, "accept")
    task.refresh_from_db()
    assert task.assigned_to_id == w.a.pk and task.status == "PENDING"
    completed = followups.complete_followup(
        actor=w.a,
        followup_id=task.pk,
        expected_version=task.version,
        outcome="Administrative service receipt filed.",
        context=context(w.a),
    )
    assert completed.status == "COMPLETED" and completed.assigned_to_id == w.a.pk
    with pytest.raises(CounselingCaseNotFound):
        get_case(actor=w.a, case_id=w.case.pk)


def test_http_closed_lookup_preparation_and_explicit_receiver_acceptance(cw4):
    w = cw4
    office, head, receiver = auth_client(w.goa), auth_client(w.head), auth_client(w.b)
    lookup = office.get(ROOT + "/office-cases?status=CLOSED").json()
    assert lookup["items"][0]["status"] == "CLOSED"
    reply = write(office, "post", f"{ROOT}/cases/{w.case.pk}/transfers", reopening_values(w))
    assert reply.status_code == 201, reply.content
    body = reply.json()
    assert body["purpose"] == "REOPEN" and body["can_submit"]
    path = f"{ROOT}/transfers/{body['id']}"
    body = write(office, "post", path + "/submit", {"expected_version": body["version"]}).json()
    denied = write(receiver, "post", path + "/accept", {"expected_version": body["version"]})
    assert denied.status_code in {403, 404, 409}
    body = write(head, "post", path + "/authorize", {"expected_version": body["version"]}).json()
    accepted = write(receiver, "post", path + "/accept", {"expected_version": body["version"]})
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["case"]["status"] == "ACTIVE" and accepted.json()["can_open_case"]


@pytest.mark.django_db(transaction=True)
def test_two_reopening_receivers_cannot_both_take_a_closed_case(settings):
    w = closed_world(settings, "cw4-transfer-race")
    third = make_user("cw4-transfer-third@example.edu", "COUNSELOR")
    first = offered(w)
    second = decide(submit(prepare(w, receiving_counselor_id=third.pk), w.goa), w.head, "authorize")

    def attempt(item, receiver):
        return lambda: transfers.decide_transfer(
            actor=fresh(receiver.pk),
            transfer_id=item.pk,
            expected_version=item.version,
            action="accept",
            context=context(fresh(receiver.pk)),
        )

    outcomes = race(attempt(first, w.b), attempt(second, third))
    errors = [result for result in outcomes if isinstance(result, Exception)]
    assert len(errors) == 1 and isinstance(errors[0], CaseContinuityError), outcomes
    w.case.refresh_from_db()
    w.closure.refresh_from_db()
    assert w.case.status == "ACTIVE" and w.closure.reopened_by_id == w.case.primary_counselor_id
    assert CounselingCaseResponsibility.objects.count() == 1
    assert AuditEvent.objects.filter(action="counseling.case.reopened").count() == 1
