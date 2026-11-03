"""Rehearse additive FAC-1 schema on empty and populated disposable databases."""

import pytest
from django.db.migrations.executor import MigrationExecutor

from tests.test_organization_policy_migration import upgrade_database  # noqa: F401


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("populated", [False, True])
def test_faculty_additive_migration_preserves_catalog(
    upgrade_database,  # noqa: F811
    populated,
):
    db, _ = upgrade_database
    before_target = ("organization", "0003_catalog_resource_versions")
    target = ("organization", "0004_facultyaffiliation")
    executor = MigrationExecutor(db)
    executor.migrate([before_target])
    apps = executor.loader.project_state([before_target]).apps
    names = ["Campus", "College", "Program"]
    if populated:
        campus = (
            apps.get_model("organization", "Campus")
            .objects.using(db.alias)
            .create(
                code="FAC",
                name="Preserved campus",
                is_active=False,
            )
        )
        apps.get_model("organization", "College").objects.using(db.alias).create(
            campus_id=campus.pk,
            code="FAC",
            name="Preserved College",
            is_active=False,
        )
    snapshots = {
        name: list(apps.get_model("organization", name).objects.using(db.alias).values())
        for name in names
    }
    executor = MigrationExecutor(db)
    executor.migrate([target])
    apps = executor.loader.project_state([target]).apps
    for name in names:
        assert (
            list(apps.get_model("organization", name).objects.using(db.alias).values())
            == snapshots[name]
        )
    assert not apps.get_model("organization", "FacultyAffiliation").objects.using(db.alias).exists()
    MigrationExecutor(db).migrate([target])
