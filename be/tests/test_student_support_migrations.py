from __future__ import annotations

from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from compass.accounts.models import Role, User
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.organization.models import AcademicYear


@pytest.mark.django_db(transaction=True)
def test_student_support_migration_preserves_legacy_pwd_and_parent_life_status():
    executor = MigrationExecutor(connection)
    migrate_from = [
        ("inventory", "0003_inventory_profiling_normalization"),
        ("student_support", "0001_initial"),
    ]
    migrate_to = [
        ("inventory", "0004_student_support_profile_context"),
        ("student_support", "0001_initial"),
    ]
    executor.migrate(migrate_from)
    old_apps = executor.loader.project_state(migrate_from).apps

    role, _ = Role.objects.get_or_create(
        code="STUDENT",
        defaults={"name": "Student", "description": ""},
    )
    year = AcademicYear.objects.create(label="2099-2100")
    family = FormFamily.objects.create(key="migration-f5", title="Migration F5")
    revision = FormRevision.objects.create(
        family=family,
        official_code="MIG-F5",
        official_revision="0",
        internal_schema_version=1,
    )

    LegacyInventory = old_apps.get_model("inventory", "StudentInventory")
    LegacyFamilyMember = old_apps.get_model("inventory", "InventoryFamilyMember")

    cases = (
        ("HAS_PHYSICAL_DISADVANTAGE", "PWD", "LIVING", "DECEASED"),
        ("NONE", "NON_PWD", "DECEASED", "LIVING"),
        ("NOT_SPECIFIED", "NOT_SPECIFIED", "NOT_SPECIFIED", None),
        (None, None, None, None),
    )
    inventory_ids: list[tuple[object, str | None, str | None, str | None]] = []

    for index, (legacy_pwd, expected_pwd, father_status, mother_status) in enumerate(cases):
        student = User.objects.create(
            email=f"migration-support-{index}@example.edu",
            password="!",
            role=role,
            student_lifecycle_status="CURRENT",
            first_name="Migration",
            last_name=f"Student{index}",
            is_active=True,
        )
        inventory = LegacyInventory.objects.create(
            student_id=student.pk,
            academic_year_id=year.pk,
            form_revision_id=revision.pk,
            physical_disadvantage_status=legacy_pwd,
            physical_disadvantage=(
                "Legacy narrative" if legacy_pwd == "HAS_PHYSICAL_DISADVANTAGE" else ""
            ),
        )
        if father_status is not None:
            LegacyFamilyMember.objects.create(
                inventory_id=inventory.pk,
                kind="FATHER",
                life_status=father_status,
            )
        if mother_status is not None:
            LegacyFamilyMember.objects.create(
                inventory_id=inventory.pk,
                kind="MOTHER",
                life_status=mother_status,
            )
        inventory_ids.append((inventory.pk, expected_pwd, father_status, mother_status))

    support_migration = import_module("compass.student_support.migrations.0001_initial")
    support_migration.copy_legacy_parent_life_status(old_apps, None)

    LegacySupportProfile = old_apps.get_model(
        "student_support",
        "StudentSupportProfile",
    )
    for inventory_id, _expected_pwd, father_status, mother_status in inventory_ids:
        profile = LegacySupportProfile.objects.get(inventory_id=inventory_id)
        assert profile.father_life_status == father_status
        assert profile.mother_life_status == mother_status
        assert profile.four_ps_status is None
        assert profile.indigenous_peoples_status is None

    executor = MigrationExecutor(connection)
    executor.migrate(migrate_to)
    new_apps = executor.loader.project_state(migrate_to).apps
    NewInventory = new_apps.get_model("inventory", "StudentInventory")
    NewSupportProfile = new_apps.get_model(
        "student_support",
        "StudentSupportProfile",
    )
    NewFamilyMember = new_apps.get_model("inventory", "InventoryFamilyMember")

    assert "life_status" not in {field.name for field in NewFamilyMember._meta.get_fields()}
    for inventory_id, expected_pwd, father_status, mother_status in inventory_ids:
        inventory = NewInventory.objects.get(pk=inventory_id)
        profile = NewSupportProfile.objects.get(inventory_id=inventory_id)
        assert inventory.pwd_status == expected_pwd
        assert profile.father_life_status == father_status
        assert profile.mother_life_status == mother_status
        assert profile.four_ps_status is None
        assert profile.indigenous_peoples_status is None
