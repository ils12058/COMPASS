"""Additive resource-version migration preserves populated historical identity/policy."""

import pytest
from django.db import IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor

from tests.test_organization_policy_migration import upgrade_database  # noqa: F401


@pytest.mark.django_db(transaction=True)
def test_populated_org1_upgrade_adds_positive_versions_only(upgrade_database):  # noqa: F811
    db, apps = upgrade_database
    c = (
        apps.get_model("organization", "Campus")
        .objects.using(db.alias)
        .create(code="CUSTOM", name="Retained name", is_active=False)
    )
    k = (
        apps.get_model("organization", "College")
        .objects.using(db.alias)
        .create(campus_id=c.pk, code="UNIT", name="Retained unit", is_active=False)
    )
    p = (
        apps.get_model("organization", "Program")
        .objects.using(db.alias)
        .create(college_id=k.pk, code="DEGREE", name="Retained degree", is_active=False)
    )
    old = ("organization", "0002_program_policy_and_catalog_initialization")
    target = ("organization", "0003_catalog_resource_versions")
    executor = MigrationExecutor(db)
    executor.migrate([old])
    old_apps = executor.loader.project_state([old]).apps
    snapshots = {}
    for model in ("Campus", "College", "Program"):
        snapshots[model] = list(
            old_apps.get_model("organization", model).objects.using(db.alias).values()
        )
    executor = MigrationExecutor(db)
    executor.migrate([target])
    new_apps = executor.loader.project_state([target]).apps
    for model in snapshots:
        cls = new_apps.get_model("organization", model)
        values = list(cls.objects.using(db.alias).values())
        assert values == [{**row, "resource_version": 1} for row in snapshots[model]]
        with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
            cls.objects.using(db.alias).update(resource_version=0)
    assert p.pk and k.pk
    MigrationExecutor(db).migrate([target])
