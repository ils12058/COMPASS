"""Real PostgreSQL Handoff races using independent connections; no mocked locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

import pytest
from django.db import transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.models import AuditEvent
from compass.counseling import handoff_content, handoff_services
from compass.counseling.continuity_locks import continuity_policy_change
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.handoff_models import CounselorHandoffSummary as Handoff
from tests import test_handoff as cases
from tests.test_continuity import decide
from tests.test_continuity_access import approved
from tests.test_continuity_release_concurrency import run, wait_for_pg_lock

metadata_case = cases.metadata_case
selected_case = cases.selected_case
workflow_case = cases.workflow_case
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("writer", ["revoke", "deactivate", "ciphertext"])
@pytest.mark.parametrize("operation", ["receive", "submit"])
def test_read_commits_before_waiting_writer(workflow_case, monkeypatch, writer, operation):
    c = workflow_case
    g = approved(c)
    if operation == "submit":
        cases.draft(c, g)
    else:
        cases.submitted(c, g)
    entered, release = Event(), Event()
    real = handoff_content.read

    def slow(item):
        value = real(item)
        entered.set()
        assert release.wait(5)
        return value

    monkeypatch.setattr(handoff_content, "read", slow)

    def write():
        if writer == "revoke":
            return decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
        if writer == "deactivate":
            return User.objects.filter(pk=c.receiver.pk).update(is_active=False)
        return Handoff.objects.filter(grant_id=g["id"]).update(content_ciphertext="corrupt")

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(
            run,
            lambda: cases.op(
                c,
                g,
                operation,
                actor=c.receiver if operation == "receive" else c.author,
                expected_version=1,
            ),
        )
        assert entered.wait(5)
        future = pool.submit(run, write, "cont3-writer")
        wait_for_pg_lock("cont3-writer")
        release.set()
        assert reader.result(timeout=5)[0] == "ok"
        assert future.result(timeout=5)[0] == "ok"
    monkeypatch.setattr(handoff_content, "read", real)
    assert run(lambda: cases.op(c, g, "receive", actor=c.receiver))[0] == "denied"


@pytest.mark.parametrize("operation", ["save", "submit"])
def test_concurrent_draft_update_or_duplicate_submission(workflow_case, operation):
    c = workflow_case
    g = approved(c)
    cases.draft(c, g)
    barrier = Barrier(2)

    def action():
        barrier.wait(3)
        return cases.op(c, g, operation, expected_version=1, body=cases.TEXT)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=5) for f in [pool.submit(run, action), pool.submit(run, action)]
        ]
    assert any(r[0] == "ok" for r in results)
    assert Handoff.objects.get().version == 2
    assert (
        AuditEvent.objects.filter(
            action="counseling.handoff."
            + ("submitted" if operation == "submit" else "draft_updated")
        ).count()
        == 1
    )


@pytest.mark.parametrize("writer", ["grant", "user", "ciphertext", "policy"])
def test_writer_first_denies_without_decrypt(workflow_case, monkeypatch, writer):
    c = workflow_case
    g = approved(c)
    cases.submitted(c, g)
    entered, release = Event(), Event()
    monkeypatch.setattr(handoff_content, "read", lambda *_: pytest.fail("denied decrypt"))

    def write():
        with transaction.atomic():
            if writer == "grant":
                Grant.objects.select_for_update().get(pk=g["id"])
                Grant.objects.filter(pk=g["id"]).update(
                    decision="REVOKED",
                    revoked_by=c.head,
                    revoked_at=timezone.now(),
                    revocation_reason="COVERAGE_ENDED",
                )
            elif writer == "user":
                User.objects.select_for_update().get(pk=c.receiver.pk)
                User.objects.filter(pk=c.receiver.pk).update(is_active=False)
            elif writer == "ciphertext":
                Handoff.objects.select_for_update().get(grant_id=g["id"])
                Handoff.objects.filter(grant_id=g["id"]).update(content_ciphertext="corrupt")
            else:
                with continuity_policy_change():
                    c.workflow_control[0] = None
                    entered.set()
                    assert release.wait(5)
                return
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(run, write)
        assert entered.wait(5)
        if writer == "user":
            reader = pool.submit(
                run, lambda: cases.op(c, g, "receive", actor=c.receiver), "cont3-reader"
            )
            wait_for_pg_lock("cont3-reader")
            release.set()
            result = reader.result(timeout=5)
        else:
            result = run(lambda: cases.op(c, g, "receive", actor=c.receiver))
            release.set()
        assert result[0] == "denied"
        assert future.result(timeout=5)[0] == "ok"


def test_policy_invalidation_cannot_publish_during_read(workflow_case, monkeypatch):
    c = workflow_case
    g = approved(c)
    cases.submitted(c, g)
    entered, release = Event(), Event()
    real = handoff_content.read

    def slow(item):
        value = real(item)
        entered.set()
        assert release.wait(5)
        return value

    monkeypatch.setattr(handoff_content, "read", slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(run, lambda: cases.op(c, g, "receive", actor=c.receiver))
        assert entered.wait(5)

        def invalidate():
            with continuity_policy_change():
                c.workflow_control[0] = None

        assert run(invalidate)[0] == "denied"
        release.set()
        assert reader.result(timeout=5)[0] == "ok"


def test_expiry_after_actual_user_lock_wait(workflow_case, monkeypatch):
    c = workflow_case
    g = approved(c, expires_at=timezone.now() + timedelta(seconds=2))
    cases.submitted(c, g)
    entered, release = Event(), Event()

    def hold():
        with transaction.atomic():
            User.objects.select_for_update().get(pk=c.receiver.pk)
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(run, hold)
        assert entered.wait(5)
        reader = pool.submit(
            run, lambda: cases.op(c, g, "receive", actor=c.receiver), "cont3-expiry"
        )
        wait_for_pg_lock("cont3-expiry")
        # Backend time, rather than a mocked lock, reaches the exact expiry while the row is held.
        monkeypatch.setattr(handoff_services.timezone, "now", lambda: g["expires_at"])
        release.set()
        assert reader.result(timeout=5)[0] == "denied"
        assert holder.result(timeout=5)[0] == "ok"
    assert not AuditEvent.objects.filter(action="counseling.handoff.read").exists()
