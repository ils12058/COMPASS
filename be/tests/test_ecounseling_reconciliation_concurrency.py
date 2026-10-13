"""Separate PostgreSQL sessions and event barriers; no timing-based ordering assumptions."""

from copy import deepcopy
from datetime import timedelta
from threading import Barrier, Event

import pytest
from django.db import OperationalError, connection, transaction
from django.db.models.query import QuerySet
from django.utils import timezone

from compass.ecounseling.diagnostics import CaptureReconciliationTaskError
from compass.ecounseling.media import withdraw_my_consent
from compass.ecounseling.models import ECounselingConsent, ECounselingMediaArtifact
from compass.ecounseling.reconciliation import (
    apply_observation,
    claim_capture,
    discover_captures,
    observe_metadata,
    reconcile_captures,
)
from compass.ecounseling.tasks import reconcile_media_captures, recover_media_artifacts
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent
from tests.test_ecounseling_media import context
from tests.test_ecounseling_reconciliation import (
    MetadataOnlyDaily,
    Recovery,
    metadata,
    pending_capture,
)
from tests.test_ecounseling_reconciliation import fake_only_boundaries as fake_only_boundaries
from tests.test_ecounseling_state_correctness import deliver, run_thread, stop

pytestmark = pytest.mark.django_db(transaction=True)


def blocked_client(capture, *, active=False):
    entered, release = Event(), Event()

    def wait():
        assert not connection.in_atomic_block  # Real connection: no transaction/row locks at IO.
        entered.set()
        assert release.wait(20)

    return MetadataOnlyDaily(metadata(capture, active=active), callback=wait), entered, release


def test_concurrent_workers_and_duplicate_dispatch_perform_one_get_for_a_live_claim():
    *_, capture = pending_capture()
    client, entered, release = blocked_client(capture)
    errors = []
    thread = run_thread(lambda: reconcile_captures(client=client), errors)
    try:
        assert entered.wait(20)
        assert Recovery.objects.get(capture=capture).state == "CLAIMED"
        second = reconcile_captures(client=client)
        assert second["claimed"] == 0 and second["metadata_checks"] == 0
        assert len(client.calls) == 1
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    capture.refresh_from_db()
    assert capture.status == "READY" and Recovery.objects.get(capture=capture).attempts == 1


def test_concurrent_discovery_is_unique_without_rewriting_source_capture(monkeypatch):
    *_, capture = pending_capture()
    barrier = Barrier(2)
    original = QuerySet.bulk_create

    def synchronized(self, *args, **kwargs):
        if self.model is Recovery:
            barrier.wait(timeout=20)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "bulk_create", synchronized)
    errors = []
    threads = [run_thread(lambda: discover_captures(limit=1), errors) for _ in range(2)]
    for thread in threads:
        thread.join(20)
    assert not any(t.is_alive() for t in threads) and not errors
    assert Recovery.objects.count() == 1 and Recovery.objects.get(capture=capture).attempts == 0
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED"


@pytest.mark.parametrize(
    "race",
    [
        "webhook_ready",
        "withdrawal",
        "stop",
        "identity",
        "capture_disposition",
        "artifact_disposition",
        "provider_cleanup",
        "custody",
        "authorization_revoked",
    ],
)
def test_new_domain_evidence_wins_while_worker_is_outside_database_locks(race):
    student, counselor, appointment, original, capture = pending_capture(
        state="START_REQUESTED" if race in ("stop", "authorization_revoked") else "STOP_REQUESTED",
        storage=True,
    )
    active = race in ("webhook_ready", "withdrawal", "stop", "authorization_revoked")
    client, entered, release = blocked_client(capture, active=active)
    errors = []
    thread = run_thread(lambda: reconcile_captures(client=client), errors)
    expected_stop = capture.stop_requested_at
    try:
        assert entered.wait(20)
        if race == "webhook_ready":
            deliver(capture, "ready-to-download", mtg_session_id=capture.provider_session_id)
            terminal_at = capture.ready_at
        elif race == "withdrawal":
            withdraw_my_consent(
                student=student,
                appointment_id=appointment.pk,
                consent_id=ECounselingConsent.objects.get(
                    room=capture.room, scope="SESSION_MEDIA_CAPTURE"
                ).pk,
                context=context(student),
                daily_client=original,
            )
        elif race == "stop":
            stop(capture, counselor, appointment, original)
            capture.refresh_from_db()
            expected_stop = capture.stop_requested_at
        elif race == "identity":
            capture.provider_artifact_id = "new-binding-never-overwritten"
            capture.save(update_fields=["provider_artifact_id"])
        elif race == "capture_disposition":
            capture.artifact_disposed_at = timezone.now()
            capture.provider_artifact_id = None
            capture.save(update_fields=["artifact_disposed_at", "provider_artifact_id"])
        elif race == "artifact_disposition":
            ECounselingMediaArtifact.objects.create(
                capture=capture, status="DISPOSED", disposed_at=timezone.now()
            )
        elif race == "provider_cleanup":
            ECounselingMediaArtifact.objects.create(
                capture=capture, provider_deleted_at=timezone.now()
            )
        elif race == "custody":
            ECounselingMediaArtifact.objects.create(
                capture=capture,
                status="STORED",
                object_key="synthetic-key",
                storage_binding="a" * 64,
                sha256="b" * 64,
                content_type="text/vtt",
                size=10,
                stored_at=timezone.now(),
            )
        else:
            ECounselingConsent.objects.filter(
                room=capture.room, scope="SESSION_MEDIA_CAPTURE"
            ).update(decision="DENIED")
        commands_after_domain_action = deepcopy(original.transcription_stops)
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    capture.refresh_from_db()
    row = Recovery.objects.get(capture=capture)
    assert original.transcription_stops == commands_after_domain_action
    assert capture.stop_requested_at == expected_stop
    if race == "webhook_ready":
        assert capture.status == "READY" and capture.ready_at == terminal_at
        assert row.state == "SUPERSEDED" and row.completion_confirmed_at is None
    elif race in ("withdrawal", "authorization_revoked"):
        assert row.state == "ESCALATED" and row.escalation_code == "PRIVACY_REVIEW_REQUIRED"
        assert capture.status == (
            "START_REQUESTED" if race == "authorization_revoked" else "STOP_REQUESTED"
        )
        assert not ECounselingMediaArtifact.objects.exists()
        if race == "withdrawal":
            assert capture.transcript_storage_authorized and not capture.transcript_storage_enabled
            assert (
                ECounselingConsent.objects.get(
                    room=capture.room, scope="SESSION_MEDIA_CAPTURE"
                ).withdrawn_at
                is not None
            )
    elif race == "stop":
        assert capture.status == "STOP_REQUESTED" and row.state == "PENDING"
        assert row.uncertainty_since == expected_stop
    elif race == "identity":
        assert capture.provider_artifact_id == "new-binding-never-overwritten"
        assert row.state == "PENDING" and row.outcome_code == "RECONCILIATION_SUPERSEDED"
        assert capture.status == "STOP_REQUESTED"
    else:
        assert row.state == "SUPERSEDED" and capture.status == "STOP_REQUESTED"
        if race == "capture_disposition":
            assert capture.provider_artifact_id is None and capture.artifact_disposed_at is not None


def test_late_response_cannot_overwrite_a_newer_worker_completion_after_lease_reclaim(monkeypatch):
    *_, capture = pending_capture()
    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    old, entered, release = blocked_client(capture, active=True)
    errors = []
    thread = run_thread(lambda: reconcile_captures(client=old), errors)
    try:
        assert entered.wait(20)
        lease = Recovery.objects.get(capture=capture).claim_expires_at
        clock[0] = lease + timedelta(seconds=1)
        new = MetadataOnlyDaily(metadata(capture))
        assert reconcile_captures(client=new)["metadata_checks"] == 1
        completed = Recovery.objects.values().get(capture=capture)
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    assert Recovery.objects.values().get(capture=capture) == completed
    capture.refresh_from_db()
    assert capture.status == "READY" and completed["attempts"] == 2


def test_crashed_claim_is_bounded_and_old_owner_is_fenced_when_redelivered(monkeypatch):
    *_, capture = pending_capture()
    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    discover_captures(limit=1)
    lost = claim_capture(capture.pk)
    row = Recovery.objects.get(capture=capture)
    client = MetadataOnlyDaily(metadata(capture, active=True))
    assert reconcile_captures(client=client)["metadata_checks"] == 0
    clock[0] = row.claim_expires_at + timedelta(seconds=1)
    assert reconcile_captures(client=client)["metadata_checks"] == 1
    current = Recovery.objects.values().get(capture=capture)
    apply_observation(lost, observe_metadata(lost, metadata(capture)))
    assert Recovery.objects.values().get(capture=capture) == current
    assert current["attempts"] == 2 and current["state"] == "PENDING"
    assert len(client.calls) == 1


def test_expired_claim_without_a_new_owner_cannot_apply_late_completion(monkeypatch):
    *_, capture = pending_capture()
    discover_captures(limit=1)
    claim = claim_capture(capture.pk)
    row = Recovery.objects.get(capture=capture)
    now = row.claim_expires_at + timedelta(seconds=1)
    monkeypatch.setattr(timezone, "now", lambda: now)
    apply_observation(claim, observe_metadata(claim, metadata(capture)))
    capture.refresh_from_db()
    row.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and row.outcome_code == "RECONCILIATION_SUPERSEDED"
    assert row.state == "PENDING" and row.attempts == 1 and row.next_attempt_at > now


def test_stop_after_active_confirmation_reopens_with_remaining_lifetime_budget(monkeypatch):
    _, counselor, appointment, original, capture = pending_capture(state="START_REQUESTED")
    client = MetadataOnlyDaily(metadata(capture, active=True))
    reconcile_captures(client=client)
    row = Recovery.objects.get(capture=capture)
    assert row.state == "RESOLVED" and row.attempts == 1
    stop(capture, counselor, appointment, original)
    capture.refresh_from_db()
    requested = capture.stop_requested_at
    assert reconcile_captures(client=client)["metadata_checks"] == 0  # New intent's grace.
    monkeypatch.setattr(timezone, "now", lambda: requested + timedelta(seconds=61))
    client.item = metadata(capture)
    assert reconcile_captures(client=client)["metadata_checks"] == 1
    row.refresh_from_db()
    capture.refresh_from_db()
    assert row.state == "RESOLVED" and row.attempts == 2 and row.uncertainty_since == requested
    assert capture.status == "READY" and capture.stop_requested_at == requested


def test_new_stop_after_a_crashed_old_claim_clears_the_lease_and_preserves_its_charge(monkeypatch):
    _, counselor, appointment, original, capture = pending_capture(state="START_REQUESTED")
    discover_captures(limit=1)
    claim_capture(capture.pk)
    row = Recovery.objects.get(capture=capture)
    now = row.claim_expires_at + timedelta(seconds=1)
    monkeypatch.setattr(timezone, "now", lambda: now)
    stop(capture, counselor, appointment, original)
    client = MetadataOnlyDaily(metadata(capture))
    assert reconcile_captures(client=client)["metadata_checks"] == 0
    row.refresh_from_db()
    assert row.state == "PENDING" and row.claim_token is None and row.claim_expires_at is None
    assert row.attempts == 1 and row.next_attempt_at == now + timedelta(seconds=60)


@pytest.mark.parametrize("committed", [False, True])
def test_apply_commit_failure_or_lost_ack_cannot_replay_commands_or_erase_the_claim_budget(
    committed, monkeypatch
):
    *_, capture = pending_capture(kind="RECORDING")
    armed = [False]
    original_commit = connection.commit

    def fail_once():
        if armed[0]:
            armed[0] = False
            if committed:
                original_commit()
            raise OperationalError(PRIVATE_TEXT)
        original_commit()

    client = MetadataOnlyDaily(metadata(capture), callback=lambda: armed.__setitem__(0, True))
    monkeypatch.setattr(
        "compass.ecounseling.reconciliation.DailyClient.from_settings", lambda: client
    )
    monkeypatch.setattr(connection, "commit", fail_once)
    result = reconcile_media_captures.apply(throw=False)
    assert result.failed() and isinstance(result.result, CaptureReconciliationTaskError)
    assert_private_absent(str(result.result))
    monkeypatch.setattr(connection, "commit", original_commit)
    capture.refresh_from_db()
    row = Recovery.objects.get(capture=capture)
    assert row.attempts == 1 and len(client.calls) == 1
    if committed:
        assert capture.status == "READY" and row.state == "RESOLVED"
        artifact = ECounselingMediaArtifact.objects.get(capture=capture)
        assert artifact.status == "PENDING" and artifact.attempts == 0
        dispatched = []
        monkeypatch.setattr("compass.ecounseling.tasks.enqueue_artifact", dispatched.append)
        assert recover_media_artifacts() == 1 and dispatched == [artifact.pk]
        assert reconcile_captures(client=client)["metadata_checks"] == 0
    else:
        assert capture.status == "STOP_REQUESTED" and row.state == "CLAIMED"
        assert not ECounselingMediaArtifact.objects.exists()
        assert reconcile_captures(client=client)["metadata_checks"] == 0
        later = row.claim_expires_at + timedelta(seconds=1)
        monkeypatch.setattr(timezone, "now", lambda: later)
        client.callback = None
        assert reconcile_captures(client=client)["metadata_checks"] == 1
        assert Recovery.objects.get(capture=capture).attempts == 2


def test_success_with_lost_task_ack_is_idempotent_on_a_fresh_delivery():
    *_, capture = pending_capture(kind="RECORDING")
    client = MetadataOnlyDaily(metadata(capture))
    reconcile_captures(client=client)
    row = Recovery.objects.values().get(capture=capture)
    artifact = ECounselingMediaArtifact.objects.values().get(capture=capture)
    assert reconcile_captures(client=client)["claimed"] == 0
    assert Recovery.objects.values().get(capture=capture) == row
    assert ECounselingMediaArtifact.objects.values().get(capture=capture) == artifact
    assert len(client.calls) == 1


def test_enclosing_application_transaction_is_rejected_before_provider_io_or_discovery():
    *_, capture = pending_capture()
    client = MetadataOnlyDaily(metadata(capture))
    with transaction.atomic(), pytest.raises(RuntimeError, match="autocommit"):
        reconcile_captures(client=client)
    assert not client.calls and not Recovery.objects.exists()


@pytest.mark.parametrize("committed", [False, True])
def test_claim_commit_failure_or_lost_ack_prevents_http_and_preserves_the_reserved_budget(
    committed, monkeypatch
):
    *_, capture = pending_capture()
    armed = [False]
    original_save, original_commit = Recovery.save, connection.commit

    def arm_claim(self, *args, **kwargs):
        result = original_save(self, *args, **kwargs)
        if self.state == "CLAIMED":
            armed[0] = True
        return result

    def fail_once():
        if armed[0]:
            armed[0] = False
            if committed:
                original_commit()
            raise OperationalError(PRIVATE_TEXT)
        original_commit()

    client = MetadataOnlyDaily(metadata(capture))
    monkeypatch.setattr(Recovery, "save", arm_claim)
    monkeypatch.setattr(connection, "commit", fail_once)
    monkeypatch.setattr(
        "compass.ecounseling.reconciliation.DailyClient.from_settings", lambda: client
    )
    result = reconcile_media_captures.apply(throw=False)
    assert result.failed() and isinstance(result.result, CaptureReconciliationTaskError)
    assert_private_absent(str(result.result))
    assert not client.calls
    monkeypatch.setattr(connection, "commit", original_commit)
    row = Recovery.objects.get(capture=capture)
    assert row.attempts == (1 if committed else 0)
    assert row.state == ("CLAIMED" if committed else "PENDING")
    if committed:
        assert reconcile_captures(client=client)["metadata_checks"] == 0
        now = row.claim_expires_at + timedelta(seconds=1)
        monkeypatch.setattr(timezone, "now", lambda: now)
    assert reconcile_captures(client=client)["metadata_checks"] == 1
    assert Recovery.objects.get(capture=capture).attempts == (2 if committed else 1)
