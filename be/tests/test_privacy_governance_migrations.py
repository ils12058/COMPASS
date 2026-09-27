from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("privacy_governance", "0002_privacynotice_retentionpolicy_and_more")]
AFTER = [("privacy_governance", "0003_simplify_privacy_governance_scope")]


@pytest.mark.django_db(transaction=True)
def test_privacy_scope_migration_preserves_retention_and_removes_empty_legacy_tables():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    LegacyRetentionPolicy = old_apps.get_model("privacy_governance", "RetentionPolicy")

    legacy_policy = LegacyRetentionPolicy.objects.create(
        code="MIGRATION-LEGACY",
        name="Legacy synthetic policy",
        scope_summary="Synthetic legacy scope",
        retention_trigger_summary="Synthetic trigger",
        retention_period_summary="Synthetic period",
        disposition_summary="Synthetic disposition",
    )

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(AFTER)
        new_apps = executor.loader.project_state(AFTER).apps
        NewRetentionPolicy = new_apps.get_model("privacy_governance", "RetentionPolicy")

        migrated = NewRetentionPolicy.objects.get(pk=legacy_policy.pk)
        assert migrated.code == "MIGRATION-LEGACY"
        assert migrated.record_categories == []

        for removed_model in ("ProcessingActivity", "PrivacyReview", "PrivacyIncident"):
            with pytest.raises(LookupError):
                new_apps.get_model("privacy_governance", removed_model)
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_privacy_scope_migration_refuses_to_destroy_existing_processing_activity_rows():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    LegacyProcessingActivity = old_apps.get_model(
        "privacy_governance",
        "ProcessingActivity",
    )

    legacy = LegacyProcessingActivity.objects.create(
        code="LEGACY-PROCESSING",
        name="Legacy synthetic processing row",
        purpose="Synthetic purpose",
        data_subject_categories=["Synthetic subjects"],
        personal_data_categories=["Synthetic data"],
        authorized_access_summary="Synthetic access",
        safeguards_summary="Synthetic safeguards",
    )

    try:
        with pytest.raises(RuntimeError, match=r"ProcessingActivity=1"):
            MigrationExecutor(connection).migrate(AFTER)

        assert LegacyProcessingActivity.objects.filter(pk=legacy.pk).exists()
    finally:
        LegacyProcessingActivity.objects.filter(pk=legacy.pk).delete()
        MigrationExecutor(connection).migrate(AFTER)
