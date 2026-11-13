"""Case-first locking keeps ownership, responsibility and tasks one atomic decision."""

from unittest.mock import patch

import pytest
from django.db import transaction

from compass.accounts.models import User
from compass.audit.models import AuditEvent
from compass.counseling import case_transfer_services as transfers
from compass.counseling.case_continuity_rules import CaseContinuityError, lock_case
from compass.counseling.case_transfer_models import CounselingCaseResponsibility
from compass.guidance_followups.models import GuidanceFollowUp
from tests.test_counseling import context
from tests.test_counseling_cases_concurrency import fresh, race
from tests.test_cw3_transfers import create_task, decide, offer, transfer_world

pytestmark = pytest.mark.django_db(transaction=True)


def attempt(item, actor_id, action, reason=None):
    def call():
        actor = fresh(actor_id)
        return transfers.decide_transfer(
            actor=actor,
            transfer_id=item.pk,
            expected_version=item.version,
            action=action,
            reason=reason,
            context=context(actor),
        )

    return call


def assert_atomic(w, tasks):
    w.case.refresh_from_db()
    accepted = w.case.primary_counselor_id != w.a.pk
    assert CounselingCaseResponsibility.objects.filter(case=w.case).count() == int(accepted)
    assert AuditEvent.objects.filter(action="counseling.case_transfer.accepted").count() == int(
        accepted
    )
    for task in tasks:
        task.refresh_from_db()
        assert task.assigned_to_id == w.case.primary_counselor_id
        assert task.events.filter(case_transfer__isnull=False).count() == int(accepted)
    return accepted


def test_two_receivers_cannot_both_take_the_same_case(settings):
    w = transfer_world(settings, "cw3-race-two")
    tasks = [create_task(w), create_task(w)]
    first, second = offer(w), offer(w, receiver=w.head)
    outcomes = race(attempt(first, w.b.pk, "accept"), attempt(second, w.head.pk, "accept"))
    successes = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(successes) == len(failures) == 1, outcomes
    assert isinstance(failures[0], CaseContinuityError), outcomes
    assert_atomic(w, tasks)


@pytest.mark.parametrize(
    "action,reason", [("cancel", "REQUEST_WITHDRAWN"), ("decline", "NO_CAPACITY")]
)
def test_accept_against_a_terminal_decision_has_no_partial_task_set(settings, action, reason):
    w = transfer_world(settings, "cw3-race-" + action)
    tasks = [create_task(w), create_task(w)]
    item = offer(w)
    actor_id = w.a.pk if action == "cancel" else w.b.pk
    outcomes = race(attempt(item, w.b.pk, "accept"), attempt(item, actor_id, action, reason))
    failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(failures) == 1 and isinstance(failures[0], CaseContinuityError), outcomes
    accepted = assert_atomic(w, tasks)
    item.refresh_from_db()
    assert item.state == (
        "ACCEPTED" if accepted else action.upper() + "LED" if action == "cancel" else "DECLINED"
    )


@pytest.mark.parametrize("change", ["owner", "case_status", "eligibility"])
def test_accept_rechecks_current_owner_status_and_eligibility_under_locks(settings, change):
    w = transfer_world(settings, "cw3-race-" + change)
    task = create_task(w)
    item = offer(w)

    def writer():
        with transaction.atomic():
            if change == "eligibility":
                User.objects.select_for_update().get(pk=w.b.pk)
                User.objects.filter(pk=w.b.pk).update(is_active=False)
            else:
                case = lock_case(w.case.pk)
                if case.primary_counselor_id == w.a.pk:
                    if change == "owner":
                        case.primary_counselor_id = w.head.pk
                    else:
                        case.status = "CLOSED"
                    case.save(update_fields=["primary_counselor", "status"])
        return "writer"

    outcomes = race(attempt(item, w.b.pk, "accept"), writer)
    assert all(
        not isinstance(value, Exception) or isinstance(value, CaseContinuityError)
        for value in outcomes
    ), outcomes
    item.refresh_from_db()
    task.refresh_from_db()
    assert task.assigned_to_id == (w.b.pk if item.state == "ACCEPTED" else w.a.pk)
    assert CounselingCaseResponsibility.objects.count() == int(item.state == "ACCEPTED")
    assert task.events.filter(case_transfer__isnull=False).count() == int(item.state == "ACCEPTED")


def test_audit_failure_rolls_back_owner_every_task_and_responsibility(settings):
    w = transfer_world(settings, "cw3-rollback")
    tasks = [create_task(w), create_task(w)]
    item = offer(w)
    with patch.object(
        transfers, "record_event", side_effect=RuntimeError("Synthetic audit failure")
    ):
        with pytest.raises(RuntimeError):
            decide(item, w.b, "accept")
    assert not assert_atomic(w, tasks)
    assert GuidanceFollowUp.objects.count() == 2
