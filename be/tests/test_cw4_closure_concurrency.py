"""Close serializes with accepted responsibility and each concurrent work-creation path."""

import threading
from unittest.mock import patch

import pytest

from compass.audit.models import AuditEvent
from compass.counseling import case_closure_services as closure
from compass.counseling.case_appointment_services import link_appointment
from compass.counseling.case_closure_models import CounselingCaseClosure
from compass.counseling.case_continuity_rules import CaseContinuityError
from compass.counseling.case_services import CounselingCaseError
from compass.guidance_followups import policy
from compass.guidance_followups import services as followups
from compass.guidance_followups.errors import FollowUpConflict
from compass.guidance_followups.models import GuidanceFollowUp
from tests.test_counseling import context
from tests.test_counseling_cases_concurrency import fresh, race
from tests.test_cw2_next_actions import create as create_task
from tests.test_cw3_case_coverage import decide as decide_coverage
from tests.test_cw3_case_coverage import offer as offer_coverage
from tests.test_cw3_transfers import decide as decide_transfer
from tests.test_cw3_transfers import future_appointment, transfer_world
from tests.test_cw3_transfers import offer as offer_transfer

pytestmark = pytest.mark.django_db(transaction=True)


def attempt_close(w, version):
    def execute():
        actor = fresh(w.a.pk)
        return closure.close_case(
            actor=actor,
            case_id=w.case.pk,
            expected_version=version,
            reason="PLANNED_SUPPORT_CONCLUDED",
            outcome="GOALS_MET",
            context=context(actor),
        )

    return execute


def split(outcomes):
    failures = [value for value in outcomes if isinstance(value, Exception)]
    assert all(
        isinstance(error, (CounselingCaseError, CaseContinuityError, FollowUpConflict))
        for error in failures
    ), outcomes
    return [value for value in outcomes if not isinstance(value, Exception)], failures


@pytest.mark.parametrize("arrangement", ["transfer", "coverage"])
def test_close_against_acceptance_cannot_discard_pending_or_accepted_responsibility(
    settings, arrangement
):
    w = transfer_world(settings, "cw4-race-" + arrangement)
    offer = (offer_transfer if arrangement == "transfer" else offer_coverage)(w)
    w.case.refresh_from_db()
    version = w.case.version

    def accept():
        actor = fresh(w.b.pk)
        return (decide_transfer if arrangement == "transfer" else decide_coverage)(
            offer, actor, "accept"
        )

    done, failed = split(race(attempt_close(w, version), accept))
    assert len(done) == len(failed) == 1
    w.case.refresh_from_db()
    offer.refresh_from_db()
    assert w.case.status == "ACTIVE" and offer.state == "ACCEPTED"
    assert w.case.primary_counselor_id == (w.b.pk if arrangement == "transfer" else w.a.pk)
    assert not CounselingCaseClosure.objects.exists()


def test_close_against_appointment_link_leaves_either_active_link_or_closed_unlinked_case(settings):
    w = transfer_world(settings, "cw4-race-appointment")
    appointment = future_appointment(w)

    def link():
        actor = fresh(w.a.pk)
        return link_appointment(
            actor=actor,
            case_id=w.case.pk,
            appointment_id=appointment.pk,
            expected_version=w.case.version,
            context=context(actor),
        )

    done, failed = split(race(attempt_close(w, w.case.version), link))
    assert len(done) == len(failed) == 1
    w.case.refresh_from_db()
    linked = w.case.appointment_links.filter(removed_at__isnull=True).exists()
    assert linked == (w.case.status == "ACTIVE")
    assert w.case.closures.count() == int(w.case.status == "CLOSED")


def test_close_against_task_creation_never_creates_an_unmarked_task_on_closed_case(settings):
    w = transfer_world(settings, "cw4-race-task")

    def create():
        return create_task(w, actor=fresh(w.a.pk))

    done, failed = split(race(attempt_close(w, w.case.version), create))
    assert len(done) == len(failed) == 1
    w.case.refresh_from_db()
    assert GuidanceFollowUp.objects.filter(case=w.case).exists() == (w.case.status == "ACTIVE")
    assert w.case.closures.count() == int(w.case.status == "CLOSED")


def test_second_close_cannot_create_two_closure_rows_or_audits(settings):
    w = transfer_world(settings, "cw4-race-double")
    done, failed = split(race(attempt_close(w, w.case.version), attempt_close(w, w.case.version)))
    assert len(done) == len(failed) == 1
    w.case.refresh_from_db()
    assert w.case.status == "CLOSED" and w.case.version == 2
    assert w.case.closures.count() == 1
    assert AuditEvent.objects.filter(action="counseling.case.closed").count() == 1


def test_task_writer_holding_user_lock_cannot_deadlock_case_closure(settings):
    w = transfer_world(settings, "cw4-race-task-complete")
    task = create_task(w)
    writer_locked = threading.Event()
    close_reached_users = threading.Event()
    original_actor = policy.current_actor
    original_people = closure.rules.lock_people

    def current_actor(actor, **kwargs):
        result = original_actor(actor, **kwargs)
        if kwargs.get("lock"):
            writer_locked.set()
            assert close_reached_users.wait(timeout=10)
        return result

    def lock_people(ids):
        close_reached_users.set()
        return original_people(ids)

    def complete():
        actor = fresh(w.a.pk)
        return followups.complete_followup(
            actor=actor,
            followup_id=task.pk,
            expected_version=task.version,
            outcome="Completed through its normal workflow.",
            context=context(actor),
        )

    def close_after_writer():
        assert writer_locked.wait(timeout=10)
        return attempt_close(w, w.case.version)()

    with (
        patch.object(policy, "current_actor", side_effect=current_actor),
        patch.object(closure.rules, "lock_people", side_effect=lock_people),
    ):
        done, failed = split(race(complete, close_after_writer))
    assert len(done) == 2 and not failed
    task.refresh_from_db()
    w.case.refresh_from_db()
    assert task.status == "COMPLETED" and w.case.status == "CLOSED"
