"""Upgrade historical truth without fabricating consent, custody, rules or approval."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.ecounseling.models import ECounselingRoom
from tests.test_ecounseling_media import setup_session

BEFORE = [
    ("ecounseling", "0003_ecounselingmediacapture_artifact_disposed_at"),
    ("privacy_governance", "0005_operationalretentionrule_dispositioncase_and_more"),
]
AFTER = [
    ("ecounseling", "0004_ecounselingmediaartifact_and_more"),
    (
        "privacy_governance",
        "0006_remove_operationalretentionrule_one_active_retention_category_and_more",
    ),
]


@pytest.mark.django_db(transaction=True)
def test_upgrade_preserves_mixed_consent_capture_and_frozen_case_truth():
    admin, student, counselor, appointment = setup_session()
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    apps = executor.loader.project_state(BEFORE).apps
    Room = apps.get_model("ecounseling", "ECounselingRoom")
    Consent = apps.get_model("ecounseling", "ECounselingConsent")
    Capture = apps.get_model("ecounseling", "ECounselingMediaCapture")
    Rule = apps.get_model("privacy_governance", "OperationalRetentionRule")
    Case = apps.get_model("privacy_governance", "DispositionCase")
    now = timezone.now()
    try:
        room = Room.objects.get(appointment_id=appointment.pk)
        for scope, decision, withdrawn in (
            ("AUDIO_VIDEO_RECORDING", "APPROVED", None),
            ("LIVE_TRANSCRIPTION", "DENIED", None),
            ("TRANSCRIPT_STORAGE", "APPROVED", now),
        ):
            Consent.objects.create(
                room=room,
                scope=scope,
                decision=decision,
                requested_by_id=counselor.pk,
                decided_at=now,
                withdrawn_at=withdrawn,
            )
        for kind, disposed, state in (
            ("RECORDING", now, "COMPLETED"),
            ("TRANSCRIPTION", None, "PROCESSING"),
        ):
            capture = Capture.objects.create(
                room=room,
                kind=kind,
                status="READY",
                ready_at=now - timedelta(days=31),
                provider_artifact_id=None if disposed else "historical-provider-artifact",
                transcript_storage_enabled=kind == "TRANSCRIPTION",
                artifact_disposed_at=disposed,
            )
            rule = Rule.objects.create(
                code=kind,
                label="Historical policy",
                category="ECOUNSELING_RECORDING"
                if kind == "RECORDING"
                else "ECOUNSELING_TRANSCRIPT",
                trigger="MEDIA_READY_AT",
                action="DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE",
                duration_days=30,
                policy_reference="Existing approved reference",
                effective_on=now.date(),
                status="ACTIVE",
                created_by_id=admin.pk,
                updated_by_id=admin.pk,
                activated_by_id=admin.pk,
                activated_at=now,
            )
            Case.objects.create(
                rule=rule,
                rule_revision=rule.revision,
                category=rule.category,
                source_id=capture.pk,
                source_updated_at=capture.updated_at,
                eligible_at=now,
                state=state,
                approved_by_id=admin.pk,
                approved_at=now,
                started_at=now,
                completed_at=disposed,
                claim_token=uuid.uuid4() if state == "PROCESSING" else None,
            )
        snapshots = {
            name: list(model.objects.values().order_by("id"))
            for name, model in (
                ("ECounselingRoom", Room),
                ("ECounselingConsent", Consent),
                ("ECounselingMediaCapture", Capture),
                ("OperationalRetentionRule", Rule),
                ("DispositionCase", Case),
            )
        }
        audit_count = AuditEvent.objects.count()
        MigrationExecutor(connection).migrate(AFTER)
        upgraded = MigrationExecutor(connection).loader.project_state(AFTER).apps
        for name, rows in snapshots.items():
            app = "ecounseling" if name.startswith("ECounseling") else "privacy_governance"
            model = upgraded.get_model(app, name)
            for row in rows:
                current = model.objects.values().get(pk=row["id"])
                assert {key: current[key] for key in row} == row
                if "media_policy_version" in current:
                    assert current["media_policy_version"] == 1
                if "contract_version" in current:
                    assert current["contract_version"] == 1
        assert upgraded.get_model("ecounseling", "ECounselingMediaArtifact").objects.count() == 0
        assert (
            upgraded.get_model("privacy_governance", "OperationalRetentionRule")
            .objects.filter(contract_version=2)
            .count()
            == 0
        )
        assert AuditEvent.objects.count() == audit_count
        assert ECounselingRoom._meta.get_field("media_policy_version").default == 2
        # A new binding uses the application default; historical rows stayed V1.
        assert (
            ECounselingRoom(
                appointment_id=uuid.uuid4(), daily_room_name="new-room"
            ).media_policy_version
            == 2
        )
    finally:
        MigrationExecutor(connection).migrate(AFTER)
