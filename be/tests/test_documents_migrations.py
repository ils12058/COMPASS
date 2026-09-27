from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("documents", "0001_initial")]
AFTER = [("documents", "0002_remove_documentbrandingprofile")]


@pytest.mark.django_db(transaction=True)
def test_branding_removal_migration_drops_matching_default_profile():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    LegacyProfile = old_apps.get_model("documents", "DocumentBrandingProfile")
    assert LegacyProfile.objects.filter(key="default").count() == 1

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(AFTER)
        new_apps = executor.loader.project_state(AFTER).apps
        with pytest.raises(LookupError):
            new_apps.get_model("documents", "DocumentBrandingProfile")
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_branding_removal_migration_refuses_divergent_persisted_values_without_leaking_them():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    LegacyProfile = old_apps.get_model("documents", "DocumentBrandingProfile")
    profile = LegacyProfile.objects.get(key="default")
    secret_value = "private-branding-contact@example.invalid"
    profile.institution_contact_email = secret_value
    profile.save(update_fields=["institution_contact_email"])

    try:
        with pytest.raises(RuntimeError) as exc_info:
            MigrationExecutor(connection).migrate(AFTER)
        message = str(exc_info.value)
        assert "profile 'default'" in message
        assert "institution_contact_email" in message
        assert secret_value not in message
    finally:
        profile = LegacyProfile.objects.get(key="default")
        profile.institution_contact_email = None
        profile.save(update_fields=["institution_contact_email"])
        MigrationExecutor(connection).migrate(AFTER)
