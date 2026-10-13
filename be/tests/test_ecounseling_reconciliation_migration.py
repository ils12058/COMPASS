"""Disposable PostgreSQL upgrade/reapply/reversal; historical capture/custody stays intact."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.ecounseling.models import (
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
)
from compass.service_catalog.models import Service
from tests import test_ecounseling_media as media_fixtures
from tests.test_ecounseling_media import setup_session

BEFORE = [("ecounseling", "0004_ecounselingmediaartifact_and_more")]
AFTER = [("ecounseling", "0005_capture_reconciliation")]


@pytest.mark.django_db(transaction=True)
def test_additive_upgrade_reapplication_and_disposable_reversal_preserve_old_evidence(monkeypatch):
    factory = media_fixtures.make_user
    service_factory = media_fixtures.create_counseling_service
    monkeypatch.setattr(
        media_fixtures,
        "create_counseling_service",
        lambda admin: Service.objects.filter(code="COUNSELING").first() or service_factory(admin),
    )
    monkeypatch.setattr(
        media_fixtures,
        "make_user",
        lambda email, role: factory(email.replace("@", f"+{uuid4().hex}@"), role),
    )
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    now = timezone.now()
    try:
        for state in (
            "NOT_STARTED",
            "START_REQUESTED",
            "ACTIVE",
            "STOP_REQUESTED",
            "ERROR",
            "STOPPED",
            "READY",
        ):
            *_, appointment = setup_session()
            room = ECounselingRoom.objects.get(appointment=appointment)
            for kind in ("RECORDING", "TRANSCRIPTION"):
                capture = ECounselingMediaCapture.objects.create(
                    room=room,
                    kind=kind,
                    status=state,
                    media_authorized_at=now - timedelta(days=1),
                    provider_instance_id="synthetic-reserved-instance",
                    provider_artifact_id="synthetic-bound-artifact",
                    provider_session_id="synthetic-session",
                    transcript_storage_enabled=kind == "TRANSCRIPTION",
                    transcript_storage_authorized=kind == "TRANSCRIPTION",
                    stop_requested_at=now if state in ("STOP_REQUESTED", "STOPPED") else None,
                    ready_at=now if state == "READY" else None,
                    error_code="PROVIDER_ERROR" if state == "ERROR" else None,
                )
                if state == "READY":
                    ECounselingMediaArtifact.objects.create(
                        capture=capture,
                        status="STORED",
                        object_key="synthetic-key",
                        storage_binding="a" * 64,
                        content_type="video/mp4" if kind == "RECORDING" else "text/vtt",
                        size=10,
                        sha256="b" * 64,
                        stored_at=now,
                        provider_deleted_at=now,
                        attempts=4,
                    )
        models = (
            ECounselingRoom,
            ECounselingConsent,
            ECounselingMediaCapture,
            ECounselingMediaArtifact,
        )
        snapshots = {model: list(model.objects.values().order_by("pk")) for model in models}
        audit_count = AuditEvent.objects.count()
        MigrationExecutor(connection).migrate(AFTER)
        executor = MigrationExecutor(connection)
        Recovery = executor.loader.project_state(AFTER).apps.get_model(
            "ecounseling", "ECounselingCaptureReconciliation"
        )
        assert Recovery.objects.count() == 0  # No backfill, invented authorization or media state.
        source = ECounselingMediaCapture.objects.filter(status="STOP_REQUESTED").first()
        row = Recovery.objects.create(
            capture_id=source.pk,
            uncertainty_since=now,
            attempts=3,
            next_attempt_at=now + timedelta(seconds=240),
            outcome_code="PROVIDER_METADATA_UNAVAILABLE",
            provider_failure_code="RATE_LIMITED",
        )
        recorded = Recovery.objects.values().get(pk=row.pk)
        MigrationExecutor(connection).migrate(AFTER)
        assert Recovery.objects.values().get(pk=row.pk) == recorded
        for model, rows in snapshots.items():
            assert list(model.objects.values().order_by("pk")) == rows
        assert AuditEvent.objects.count() == audit_count
        # Schema reversal intentionally deletes only the new evidence table: NEVER a live code
        # rollback recipe. Production rollback keeps the table; this DB is task-owned/disposable.
        MigrationExecutor(connection).migrate(BEFORE)
        assert (
            "ecounseling_ecounselingcapturereconciliation"
            not in connection.introspection.table_names()
        )
        for model, rows in snapshots.items():
            assert list(model.objects.values().order_by("pk")) == rows
        assert AuditEvent.objects.count() == audit_count
        MigrationExecutor(connection).migrate(AFTER)
        assert Recovery.objects.count() == 0
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
