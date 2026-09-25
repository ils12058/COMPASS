"""Upgrade existing capability rows without losing grants or override provenance."""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE = [("accounts", "0005_user_institutional_id")]
AFTER = [("accounts", "0006_rename_reference_capabilities")]
RENAMES = (
    ("organization.view", "organization.structure.view"),
    ("services.view", "services.catalog.view"),
)


@pytest.mark.django_db(transaction=True)
def test_upgrade_preserves_capability_identity_grants_and_both_override_effects():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    Role = old_apps.get_model("accounts", "Role")
    Designation = old_apps.get_model("accounts", "Designation")
    Capability = old_apps.get_model("accounts", "Capability")
    RoleCapability = old_apps.get_model("accounts", "RoleCapability")
    DesignationCapability = old_apps.get_model("accounts", "DesignationCapability")
    User = old_apps.get_model("accounts", "User")
    UserCapabilityOverride = old_apps.get_model("accounts", "UserCapabilityOverride")

    role = Role.objects.create(code="COUNSELOR", name="Counselor")
    designation = Designation.objects.create(code="HEAD_GUIDANCE_COUNSELOR", name="Head")
    creator = User.objects.create(
        email="migration-creator@example.edu",
        password="!",
        role=role,
        first_name="Migration",
        last_name="Creator",
    )
    expiry = timezone.now() + timezone.timedelta(days=7)
    snapshots = []
    try:
        for index, (old_code, new_code) in enumerate(RENAMES):
            capability = Capability.objects.create(code=old_code, name="Legacy read")
            role_grant = RoleCapability.objects.create(role=role, capability=capability)
            designation_grant = DesignationCapability.objects.create(
                designation=designation, capability=capability
            )
            for effect in ("REVOKE", "GRANT"):
                user = User.objects.create(
                    email=f"migration-{index}-{effect.lower()}@example.edu",
                    password="!",
                    role=role,
                    first_name="Migration",
                    last_name=effect,
                )
                override = UserCapabilityOverride.objects.create(
                    user=user,
                    capability=capability,
                    effect=effect,
                    reason=f"Preserve {effect.lower()} reason",
                    expires_at=expiry,
                    created_by=creator,
                )
                snapshots.append(
                    (
                        new_code,
                        capability.pk,
                        role_grant.pk,
                        designation_grant.pk,
                        override.pk,
                        user.pk,
                        effect,
                        override.reason,
                    )
                )

        executor = MigrationExecutor(connection)
        executor.migrate(AFTER)
        new_apps = executor.loader.project_state(AFTER).apps
        NewCapability = new_apps.get_model("accounts", "Capability")
        NewRoleCapability = new_apps.get_model("accounts", "RoleCapability")
        NewDesignationCapability = new_apps.get_model("accounts", "DesignationCapability")
        NewOverride = new_apps.get_model("accounts", "UserCapabilityOverride")
        for (
            new_code,
            capability_id,
            role_grant_id,
            designation_grant_id,
            override_id,
            user_id,
            effect,
            reason,
        ) in snapshots:
            capability = NewCapability.objects.get(pk=capability_id)
            assert capability.code == new_code
            assert NewRoleCapability.objects.get(pk=role_grant_id).capability_id == capability_id
            assert (
                NewDesignationCapability.objects.get(pk=designation_grant_id).capability_id
                == capability_id
            )
            override = NewOverride.objects.get(pk=override_id)
            assert override.capability_id == capability_id
            assert override.user_id == user_id
            assert override.effect == effect
            assert override.reason == reason
            assert override.expires_at == expiry
            assert override.created_by_id == creator.pk
        assert not NewCapability.objects.filter(
            code__in=[old_code for old_code, _ in RENAMES]
        ).exists()

        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        reversed_apps = executor.loader.project_state(BEFORE).apps
        ReversedCapability = reversed_apps.get_model("accounts", "Capability")
        for old_code, new_code in RENAMES:
            assert ReversedCapability.objects.filter(code=old_code).exists()
            assert not ReversedCapability.objects.filter(code=new_code).exists()
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_rename_is_safe_without_bootstrap_and_rejects_duplicate_codes():
    migration = import_module("compass.accounts.migrations.0006_rename_reference_capabilities")
    executor = MigrationExecutor(connection)
    apps = executor.loader.project_state(BEFORE).apps
    Capability = apps.get_model("accounts", "Capability")
    schema_editor = SimpleNamespace(connection=connection)

    migration.forwards(apps, schema_editor)
    for old_code, new_code in RENAMES:
        assert not Capability.objects.filter(code__in=(old_code, new_code)).exists()

    old = Capability.objects.create(code="organization.view", name="Legacy")
    new = Capability.objects.create(code="organization.structure.view", name="Duplicate")
    with pytest.raises(RuntimeError, match="both rows exist"):
        migration.forwards(apps, schema_editor)
    assert Capability.objects.get(pk=old.pk).code == "organization.view"
    assert Capability.objects.get(pk=new.pk).code == "organization.structure.view"
