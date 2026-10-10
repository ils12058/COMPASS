from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE_SCOPE_REDUCTION = [("privacy_governance", "0002_privacynotice_retentionpolicy_and_more")]
BEFORE_REMOVAL = [("privacy_governance", "0003_simplify_privacy_governance_scope")]
AFTER_REMOVAL = [("privacy_governance", "0004_remove_retention_policy")]


def _synthetic_policy(model):
    return model.objects.create(
        code="MIGRATION-LEGACY",
        name="Legacy synthetic policy",
        scope_summary="Sensitive policy prose must never appear in the error",
        retention_trigger_summary="Synthetic trigger",
        retention_period_summary="Synthetic period",
        disposition_summary="Synthetic disposition",
    )


@pytest.mark.django_db(transaction=True)
def test_prior_scope_migration_preserves_retention_and_removes_empty_legacy_tables():
    MigrationExecutor(connection).migrate(BEFORE_SCOPE_REDUCTION)
    old_apps = MigrationExecutor(connection).loader.project_state(BEFORE_SCOPE_REDUCTION).apps
    policy_model = old_apps.get_model("privacy_governance", "RetentionPolicy")
    policy = _synthetic_policy(policy_model)

    try:
        MigrationExecutor(connection).migrate(BEFORE_REMOVAL)
        new_apps = MigrationExecutor(connection).loader.project_state(BEFORE_REMOVAL).apps
        migrated_model = new_apps.get_model("privacy_governance", "RetentionPolicy")
        assert migrated_model.objects.get(pk=policy.pk).record_categories == []
        for removed_model in ("ProcessingActivity", "PrivacyReview", "PrivacyIncident"):
            with pytest.raises(LookupError):
                new_apps.get_model("privacy_governance", removed_model)
    finally:
        migrated_model.objects.filter(pk=policy.pk).delete()
        MigrationExecutor(connection).migrate(AFTER_REMOVAL)


@pytest.mark.django_db(transaction=True)
def test_prior_scope_migration_refuses_to_destroy_existing_processing_activity_rows():
    MigrationExecutor(connection).migrate(BEFORE_SCOPE_REDUCTION)
    old_apps = MigrationExecutor(connection).loader.project_state(BEFORE_SCOPE_REDUCTION).apps
    processing_model = old_apps.get_model("privacy_governance", "ProcessingActivity")
    legacy = processing_model.objects.create(
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
            MigrationExecutor(connection).migrate(BEFORE_REMOVAL)
        assert processing_model.objects.filter(pk=legacy.pk).exists()
    finally:
        processing_model.objects.filter(pk=legacy.pk).delete()
        MigrationExecutor(connection).migrate(AFTER_REMOVAL)


@pytest.mark.django_db(transaction=True)
def test_empty_retention_table_removal_preserves_notices():
    MigrationExecutor(connection).migrate(BEFORE_REMOVAL)
    old_apps = MigrationExecutor(connection).loader.project_state(BEFORE_REMOVAL).apps
    notice_model = old_apps.get_model("privacy_governance", "PrivacyNotice")
    notice = notice_model.objects.create(code="MIGRATION-NOTICE", name="Synthetic notice")

    try:
        MigrationExecutor(connection).migrate(AFTER_REMOVAL)
        new_apps = MigrationExecutor(connection).loader.project_state(AFTER_REMOVAL).apps
        with pytest.raises(LookupError):
            new_apps.get_model("privacy_governance", "RetentionPolicy")
        assert (
            new_apps.get_model("privacy_governance", "PrivacyNotice")
            .objects.filter(pk=notice.pk)
            .exists()
        )
        assert "privacy_governance_retentionpolicy" not in connection.introspection.table_names()
    finally:
        MigrationExecutor(connection).migrate(AFTER_REMOVAL)


@pytest.mark.django_db(transaction=True)
def test_populated_retention_table_fails_closed_without_exposing_policy_content():
    MigrationExecutor(connection).migrate(BEFORE_REMOVAL)
    old_apps = MigrationExecutor(connection).loader.project_state(BEFORE_REMOVAL).apps
    policy_model = old_apps.get_model("privacy_governance", "RetentionPolicy")
    policy = _synthetic_policy(policy_model)

    try:
        with pytest.raises(RuntimeError, match=r"RetentionPolicy=1") as error:
            MigrationExecutor(connection).migrate(AFTER_REMOVAL)
        assert "Sensitive policy prose" not in str(error.value)
        assert policy_model.objects.filter(pk=policy.pk).exists()
        assert "privacy_governance_retentionpolicy" in connection.introspection.table_names()
    finally:
        policy_model.objects.filter(pk=policy.pk).delete()
        MigrationExecutor(connection).migrate(AFTER_REMOVAL)
