"""Case coverage grants selected work, never ownership or ordinary source access."""

import io
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Designation, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling import case_coverage_projections as projections
from compass.counseling import case_coverage_services as coverage
from compass.counseling.case_continuity_rules import CaseContinuityError
from compass.counseling.case_coverage_models import (
    CounselingCaseCoverage,
    CounselingCaseCoverageTask,
)
from compass.counseling.case_coverage_tasks import reconcile_returns
from compass.counseling.case_coverage_work import pending_coverage_work
from compass.counseling.case_services import CounselingCaseNotFound, get_case
from compass.guidance_followups import policy
from compass.guidance_followups import services as followups
from compass.guidance_followups.errors import FollowUpConflict, FollowUpNotFound
from compass.guidance_followups.models import GuidanceFollowUp
from compass.guidance_followups.recovery import recoverable_queryset
from compass.notifications.current import notification_is_current
from compass.notifications.models import Notification
from compass.privacy_governance.activity import list_privacy_activity
from tests.test_appointment_management_scope import auth_client, csrf
from tests.test_counseling import context, make_user
from tests.test_counseling_cases import link, record
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_transfers import decide as transfer_decide
from tests.test_cw3_transfers import offer as transfer_offer
from tests.test_cw3_transfers import transfer_world

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/counseling/continuity"
FUP = "/api/v1/guidance-followups"


@pytest.fixture
def cw3c(settings):
    return transfer_world(settings, "cw3c")


def values(w, *, actor=None, receiver=None, tasks=(), **changes):
    actor = actor or w.a
    w.case.refresh_from_db()
    now = timezone.now()
    result = {
        "expected_case_version": w.case.version,
        "receiving_counselor_id": (receiver or w.b).pk,
        "reason": "TEMPORARY_SUPPORT",
        "starts_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(days=3),
        "tasks": [
            {
                "task_id": task.pk,
                "expected_version": task.version,
                "return_plan": "RETURN_TO_PRIMARY",
            }
            for task in tasks
        ],
        "student_communication": "NO",
    }
    if actor.pk != w.case.primary_counselor_id:
        result["office_preparation_reason"] = "OWNER_UNAVAILABLE"
    result.update(changes)
    return result


def prepare(w, *, actor=None, receiver=None, tasks=(), **changes):
    actor = actor or w.a
    return coverage.prepare_coverage(
        actor=actor,
        case_id=w.case.pk,
        values=values(w, actor=actor, receiver=receiver, tasks=tasks, **changes),
        context=context(actor),
    )


def decide(item, actor, action, reason=None, expected_version=None):
    return coverage.decide_coverage(
        actor=actor,
        coverage_id=item.pk,
        expected_version=item.version if expected_version is None else expected_version,
        action=action,
        reason=reason,
        context=context(actor),
    )


def offer(w, *, actor=None, receiver=None, authorizer=None, **changes):
    actor = actor or w.a
    item = prepare(w, actor=actor, receiver=receiver, **changes)
    item = coverage.submit_coverage(
        actor=actor, coverage_id=item.pk, expected_version=item.version, context=context(actor)
    )
    if item.state == "PREPARED":
        item = decide(item, authorizer or w.head, "authorize")
    return item


@pytest.mark.parametrize(
    "route", ["ordinary", "owner_to_head", "outgoing_head", "two_heads", "office"]
)
def test_authorization_routes_require_explicit_acceptance_and_keep_primary(cw3c, route):
    w = cw3c
    actor, receiver, authorizer = w.a, w.b, w.head
    if route == "outgoing_head":
        w.case.primary_counselor = w.head
        w.case.save(update_fields=["primary_counselor"])
        actor = w.head
    elif route in {"owner_to_head", "two_heads"}:
        receiver = w.head
        if route == "two_heads":
            authorizer = make_user("cw3c-second-head@example.edu", "COUNSELOR")
            UserDesignation.objects.create(
                user=authorizer,
                designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
            )
    elif route == "office":
        actor = w.goa
    original = w.case.primary_counselor_id
    item = prepare(w, actor=actor, receiver=receiver)
    with pytest.raises(CaseContinuityError):
        decide(item, receiver, "accept")
    item = coverage.submit_coverage(
        actor=actor, coverage_id=item.pk, expected_version=item.version, context=context(actor)
    )
    assert w.case.primary_counselor_id == original
    direct = route in {"owner_to_head", "outgoing_head"}
    assert (item.state == "AUTHORIZED") == direct
    if not direct:
        item = decide(item, authorizer, "authorize")
    assert item.independent_authorization is (not direct)
    assert item.review_expires_at == min(item.authorized_at + timedelta(days=7), item.expires_at)
    package = projections.coverage_detail(actor=receiver, coverage_id=item.pk)
    assert package["can_accept"] and not package["can_open_case"]
    with pytest.raises(CounselingCaseNotFound):
        get_case(actor=receiver, case_id=w.case.pk)
    item = decide(item, receiver, "accept")
    w.case.refresh_from_db()
    assert item.state == "ACCEPTED" and w.case.primary_counselor_id == original
    assert item.history.filter(kind="accepted", actor=receiver).count() == 1
    if route == "owner_to_head":
        events = AuditEvent.objects.filter(action__startswith="counseling.case_coverage.")
        assert all(
            event.metadata["independent_authorization"] is False
            for event in events.exclude(action__endswith="prepared")
        )
        assert any(
            "no independent" in row.description.lower()
            for row in list_privacy_activity(event_type="counseling.case_coverage.accepted").items
        )


@pytest.mark.parametrize("actor_name", ["goa", "head"])
def test_office_incoming_to_only_head_is_blocked_before_writes(cw3c, actor_name):
    w = cw3c
    with pytest.raises(CaseContinuityError) as failure:
        prepare(w, actor=getattr(w, actor_name), receiver=w.head)
    assert failure.value.code in {
        "case_continuity_no_independent_approver",
        "case_continuity_receiver_ineligible",
    }
    assert not CounselingCaseCoverage.objects.exists()
    w.case.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk


@pytest.mark.parametrize("fault", ["duration", "advance", "naive", "end"])
def test_interval_limits_are_enforced_without_touching_case(cw3c, fault):
    w = cw3c
    now = timezone.now()
    changes = {
        "duration": {"starts_at": now, "expires_at": now + timedelta(days=31)},
        "advance": {"starts_at": now + timedelta(days=15), "expires_at": now + timedelta(days=16)},
        "naive": {"starts_at": now.replace(tzinfo=None)},
        "end": {"expires_at": now - timedelta(days=1)},
    }[fault]
    with pytest.raises(CaseContinuityError, match="at most 30 days"):
        prepare(w, **changes)
    assert not CounselingCaseCoverage.objects.exists()


def test_only_selected_tasks_are_temporally_assigned_without_source_or_case_access(cw3c):
    w = cw3c
    selected = create_task(w, title="Selected confidential work")
    unselected = create_task(w, title="Unselected confidential work")
    source = record(w.a, w.student)
    link(w.a, w.case, source)
    sourced = create_task(w, source_kind="COUNSELING_ENCOUNTER", source_id=source.pk)
    descriptions = {
        task.pk: task.description_ciphertext for task in (selected, unselected, sourced)
    }
    item = offer(w, tasks=(selected, sourced))
    assert not policy.scope(w.b, GuidanceFollowUp.objects.all()).exists()
    review = projections.coverage_detail(actor=w.b, coverage_id=item.pk)
    assert len(review["tasks"]) == 2 and all(row["title"] is None for row in review["tasks"])
    assert all(not row["record_accessible"] for row in review["tasks"])
    item = decide(item, w.b, "accept")
    visible = set(policy.scope(w.b, GuidanceFollowUp.objects.all()).values_list("pk", flat=True))
    assert visible == {selected.pk, sourced.pk}
    assert not policy.scope(
        w.a, GuidanceFollowUp.objects.filter(pk=selected.pk), manage=True
    ).exists()
    assert policy.authorized(w.a, selected) and not policy.authorized(w.a, selected, manage=True)
    assert all(row.assigned_to_id == w.a.pk for row in GuidanceFollowUp.objects.all())
    client = auth_client(w.b, recent_mfa=True)
    body = client.get(f"{FUP}/{sourced.pk}")
    assert body.status_code == 200, body.content
    assert body.json()["description"] == "Protected action instructions"
    assert body.json()["assigned_to_id"] == str(w.b.pk)
    assert body.json()["source"] is None and body.json()["case"] is None
    assert client.get(f"/api/v1/counseling/encounters/{source.pk}").status_code == 404
    assert client.get(f"/api/v1/counseling/cases/{w.case.pk}").status_code == 404
    assert client.get(f"{FUP}/{unselected.pk}").status_code == 404
    with pytest.raises(FollowUpConflict, match="End the accepted coverage"):
        followups.reassign_followup(
            actor=w.b,
            followup_id=selected.pk,
            expected_version=2,
            assigned_to_id=w.a.pk,
            context=context(w.b),
        )
    sourced.refresh_from_db()
    followups.complete_followup(
        actor=w.b,
        followup_id=sourced.pk,
        expected_version=sourced.version,
        outcome="Selected action completed",
        context=context(w.b),
    )
    item = decide(item, w.a, "revoke", "ARRANGEMENT_NOT_SUITABLE")
    assert client.get(f"{FUP}/{selected.pk}").status_code == 404
    for task in (selected, unselected, sourced):
        task.refresh_from_db()
        assert task.description_ciphertext == descriptions[task.pk]
    assert sourced.status == "COMPLETED" and selected.status == "PENDING"
    assert selected.events.filter(case_coverage=item, kind="REASSIGNED").count() == 2
    assert sourced.events.filter(case_coverage=item, kind="REASSIGNED").count() == 1


def test_future_acceptance_and_expiry_use_half_open_authority_and_idempotent_return(cw3c):
    w = cw3c
    task = create_task(w)
    start = timezone.now() + timedelta(hours=1)
    end = start + timedelta(days=1)
    item = decide(offer(w, tasks=(task,), starts_at=start, expires_at=end), w.b, "accept")
    assert coverage.state_at(item) == "SCHEDULED"
    assert not policy.authorized(w.b, task)
    assert policy.authorized(w.a, task, manage=True)
    with patch("django.utils.timezone.now", return_value=start):
        assert policy.authorized(w.b, task, manage=True)
        assert not policy.authorized(w.a, task, manage=True)
    with patch("django.utils.timezone.now", return_value=end):
        assert not policy.authorized(w.b, task)
        assert policy.authorized(w.a, task, manage=True)
        get_case(actor=w.a, case_id=w.case.pk)
        task.refresh_from_db()
        assert task.status == "PENDING" and task.assigned_to_id == w.a.pk
        event = task.events.filter(case_coverage=item).latest("revision")
        assert event.actor_id == w.a.pk and event.coverage_effective_at == end
        version = task.version
        output = io.StringIO()
        call_command("return_case_coverage_tasks", stdout=output)
        call_command("return_case_coverage_tasks", stdout=output)
        assert "Returned: 0" in output.getvalue()
        task.refresh_from_db()
        assert task.version == version
        assert task.events.filter(case_coverage=item).count() == 2


def test_ineligible_primary_is_flagged_only_for_case_continuity_recovery(cw3c):
    w = cw3c
    task = create_task(w)
    item = decide(offer(w, tasks=(task,)), w.b, "accept")
    w.a.is_active = False
    w.a.save(update_fields=["is_active"])
    with patch("django.utils.timezone.now", return_value=item.expires_at):
        reconcile_returns(actor=w.head, case_id=w.case.pk)
        plan = CounselingCaseCoverageTask.objects.get(coverage=item, task=task)
        assert plan.recovery_required and plan.returned_at
        assert not recoverable_queryset(actor=w.head).filter(pk=task.pk).exists()
        work = pending_coverage_work(actor=w.head, limit=20, now=item.expires_at)
        assert any(row.kind == "CASE_COVERAGE_RECOVERY" for row in work)
        review = projections.coverage_detail(actor=w.head, coverage_id=item.pk)
        assert review["can_arrange_transfer"] and all(
            row["title"] is None for row in review["tasks"]
        )
        w.a.is_active = True
        w.a.save(update_fields=["is_active"])
        get_case(actor=w.a, case_id=w.case.pk)
        plan.refresh_from_db()
        assert not plan.recovery_required and plan.recovered_by_id == w.a.pk


@pytest.mark.parametrize("ending", ["decline", "cancel", "expire"])
def test_terminal_offer_ends_review_without_changing_owner_or_work(cw3c, ending):
    w = cw3c
    task = create_task(w)
    item = offer(w, tasks=(task,))
    if ending == "expire":
        with patch("django.utils.timezone.now", return_value=item.review_expires_at):
            package = projections.coverage_detail(actor=w.b, coverage_id=item.pk)
            assert package["state"] == "EXPIRED" and not package["tasks"]
            with pytest.raises(CaseContinuityError):
                decide(item, w.b, "accept")
    else:
        item = decide(item, w.b if ending == "decline" else w.a, ending, "NO_CAPACITY")
        package = projections.coverage_detail(actor=w.b, coverage_id=item.pk)
        assert not package["review_accessible"] and not package["tasks"]
    w.case.refresh_from_db()
    task.refresh_from_db()
    assert w.case.primary_counselor_id == w.a.pk and task.version == 1
    assert not item.task_plans.filter(delegated_at__isnull=False).exists()


def test_stale_task_and_late_expiry_roll_back_all_delegation_effects(cw3c):
    w = cw3c
    task = create_task(w)
    item = offer(w, tasks=(task,))
    followups.record_activity(
        actor=w.a,
        followup_id=task.pk,
        expected_version=task.version,
        remarks="Progress recorded",
        context=context(w.a),
    )
    with pytest.raises(CaseContinuityError) as failure:
        decide(item, w.b, "accept")
    assert failure.value.code == "case_continuity_task_changed"
    assert not AuditEvent.objects.filter(action="counseling.case_coverage.accepted").exists()
    assert not item.task_plans.filter(delegated_at__isnull=False).exists()


def test_covered_task_change_rechecks_time_after_audit_and_rolls_back(cw3c):
    w = cw3c
    task = create_task(w)
    item = decide(offer(w, tasks=(task,)), w.b, "accept")
    task.refresh_from_db()
    clock = [timezone.now()]
    original = followups._audit

    def finish(*args, **kwargs):
        original(*args, **kwargs)
        clock[0] = item.expires_at

    with (
        patch("django.utils.timezone.now", side_effect=lambda: clock[0]),
        patch.object(followups, "_audit", side_effect=finish),
    ):
        with pytest.raises(FollowUpNotFound):
            followups.complete_followup(
                actor=w.b,
                followup_id=task.pk,
                expected_version=task.version,
                outcome="Must roll back",
                context=context(w.b),
                mutation_key=str(uuid4()),
                mutation_fingerprint="d" * 64,
            )
    task.refresh_from_db()
    assert task.status == "PENDING" and task.outcome_ciphertext is None and task.version == 2
    assert not task.events.filter(kind="COMPLETED").exists()
    assert not AuditEvent.objects.filter(action="guidance_followup.completed").exists()


@pytest.mark.parametrize("scheduled", [False, True])
def test_accepted_coverage_blocks_transfer_and_second_coverage(cw3c, scheduled):
    w = cw3c
    transfer = transfer_offer(w)
    changes = {"starts_at": timezone.now() + timedelta(days=1)} if scheduled else {}
    first = decide(offer(w, **changes), w.b, "accept")
    with pytest.raises(CaseContinuityError) as failure:
        transfer_decide(transfer, w.b, "accept")
    assert failure.value.code == "case_continuity_coverage_conflict"
    another = offer(w)
    with pytest.raises(CaseContinuityError) as failure:
        decide(another, w.b, "accept")
    assert failure.value.code == "case_continuity_coverage_conflict"
    decide(first, w.a, "revoke", "REQUEST_WITHDRAWN")
    accepted = transfer_decide(transfer, w.b, "accept")
    assert accepted.state == "ACCEPTED"


def test_office_and_head_packages_and_notifications_never_contain_task_text(cw3c):
    w = cw3c
    task = create_task(w, title="Private task title", description="Private task narrative")
    with patch.object(projections, "decrypt_text", side_effect=AssertionError("Office decrypted")):
        package = projections.coverage_context(actor=w.goa, case_id=w.case.pk)
        assert package["tasks"][0]["title"] is None
        item = offer(w, actor=w.goa, tasks=(task,))
        body = projections.coverage_detail(actor=w.head, coverage_id=item.pk)
        assert body["tasks"][0]["title"] is None
    current = Notification.objects.filter(target_id=item.pk).latest("created_at")
    assert notification_is_current(current)
    for row in AuditEvent.objects.filter(action__startswith="counseling.case_coverage."):
        metadata = json.dumps(row.metadata)
        assert "Private task" not in metadata and w.student.get_full_name() not in metadata
    for row in Notification.objects.filter(target_id=item.pk):
        text = f"{row.title} {row.message}"
        assert "Private task" not in text and w.student.get_full_name() not in text
    client = auth_client(w.b)
    response = client.get(f"{ROOT}/coverages/{item.pk}")
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"] and response["Pragma"] == "no-cache"
    item = decide(item, w.b, "decline", "NO_CAPACITY")
    assert not notification_is_current(current)
    data = {"expected_version": item.version - 1}
    stale = client.post(
        f"{ROOT}/coverages/{item.pk}/accept",
        data=json.dumps(data),
        content_type="application/json",
        **csrf(client),
    )
    assert stale.status_code == 409 and "no-store" in stale["Cache-Control"]
