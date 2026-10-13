"""Disposable PostgreSQL: preserve historical receipts, capture/custody and recovery evidence."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from tests.test_ecounseling_reconciliation import fake_only_boundaries as fake_only_boundaries
from tests.test_ecounseling_reconciliation import pending_capture

pytestmark = pytest.mark.django_db(transaction=True)


def test_additive_webhook_upgrade_reapply_and_disposable_reversal_preserve_history():
    *_, capture = pending_capture(kind="RECORDING", state="STOP_REQUESTED", bound=True)
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    before = [("ecounseling", "0005_capture_reconciliation")]
    after = [("ecounseling", "0006_webhook_provenance")]
    try:
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        Capture = old.get_model("ecounseling", "ECounselingMediaCapture")
        Receipt = old.get_model("ecounseling", "DailyWebhookReceipt")
        Recovery = old.get_model("ecounseling", "ECounselingCaptureReconciliation")
        Artifact = old.get_model("ecounseling", "ECounselingMediaArtifact")
        Receipt.objects.create(
            provider_event_id="historical-unresolved",
            event_type="recording.ready-to-download",
            ecounseling_room_id=capture.room_id,
            provider_session_id="historical-session",
            provider_occurred_at=timezone.now(),
        )
        Recovery.objects.create(
            capture_id=capture.pk,
            uncertainty_since=timezone.now(),
            attempts=3,
            state="ESCALATED",
            outcome_code="RECONCILIATION_EXHAUSTED",
            escalation_code="RECONCILIATION_EXHAUSTED",
            escalated_at=timezone.now(),
        )
        Artifact.objects.create(
            capture_id=capture.pk,
            status="FAILED",
            attempts=2,
            error_code="PROVIDER_IDENTITY_UNVERIFIED",
        )
        snapshots = {
            "capture": list(Capture.objects.values()),
            "receipts": list(Receipt.objects.values()),
            "recovery": list(Recovery.objects.values()),
            "artifacts": list(Artifact.objects.values()),
        }
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        new = executor.loader.project_state(after).apps
        NewReceipt = new.get_model("ecounseling", "DailyWebhookReceipt")
        NewCapture = new.get_model("ecounseling", "ECounselingMediaCapture")
        assert NewReceipt.objects.filter(
            processing_outcome="HISTORICAL_UNVERIFIED",
            identity_verified=False,
            processing_attempts=0,
            applied_at__isnull=True,
            next_attempt_at__isnull=True,
        ).count() == len(snapshots["receipts"])
        assert not NewCapture.objects.filter(provider_binding_quarantined_at__isnull=False).exists()
        fields = [field.attname for field in Receipt._meta.fields]
        assert list(NewReceipt.objects.values(*fields)) == snapshots["receipts"]
        fields = [field.attname for field in Capture._meta.fields]
        assert list(NewCapture.objects.values(*fields)) == snapshots["capture"]
        assert (
            list(new.get_model("ecounseling", "ECounselingCaptureReconciliation").objects.values())
            == snapshots["recovery"]
        )
        assert (
            list(new.get_model("ecounseling", "ECounselingMediaArtifact").objects.values())
            == snapshots["artifacts"]
        )
        row = NewReceipt.objects.get(provider_event_id="historical-unresolved")
        row.processing_outcome = "ANOMALY"
        row.anomaly_code = "UNKNOWN_ROOM"
        row.operator_review_required = True
        row.save()
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        row.refresh_from_db()
        assert row.anomaly_code == "UNKNOWN_ROOM" and row.operator_review_required
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        assert (
            list(old.get_model("ecounseling", "DailyWebhookReceipt").objects.values())
            == snapshots["receipts"]
        )
        assert (
            list(old.get_model("ecounseling", "ECounselingMediaCapture").objects.values())
            == snapshots["capture"]
        )
        assert (
            list(old.get_model("ecounseling", "ECounselingCaptureReconciliation").objects.values())
            == snapshots["recovery"]
        )
        assert (
            list(old.get_model("ecounseling", "ECounselingMediaArtifact").objects.values())
            == snapshots["artifacts"]
        )
        executor = MigrationExecutor(connection)
        executor.migrate(after)
    finally:
        MigrationExecutor(connection).migrate(leaves)
