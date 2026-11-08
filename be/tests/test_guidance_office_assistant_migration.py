"""The GOA role rename migration and its migrate-then-sync deployment contract."""

from __future__ import annotations

import importlib
from io import StringIO
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from compass.accounts.models import Role, User
from compass.accounts.services import effective_capabilities

OLD_CODE = "GUIDANCE_SERVICES_STAFF"
NEW_CODE = "GUIDANCE_OFFICE_ASSISTANT"
BASE = ("accounts", "0002_student_session_summary_capabilities")
TARGET = ("accounts", "0003_rename_guidance_services_staff_role")
MIGRATION = importlib.import_module(
    "compass.accounts.migrations.0003_rename_guidance_services_staff_role"
)

pytestmark = pytest.mark.django_db(transaction=True)


def _migrate(target):
    executor = MigrationExecutor(connection)
    targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != "accounts"] + [
        target
    ]
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def _editor():
    return SimpleNamespace(connection=connection)


@pytest.fixture
def synced_policy():
    call_command("sync_identity_policy", stdout=StringIO())


def test_migrate_then_sync_keeps_one_renamed_role_and_identical_capabilities(synced_policy):
    role = Role.objects.get(code=NEW_CODE)
    role_pk = role.pk
    user = User.objects.create_user(
        email="goa-upgrade@synthetic.invalid",
        password="a-test-password",
        role=role,
        first_name="Synthetic",
        last_name="Assistant",
    )
    before = effective_capabilities(user)
    assert "referrals.manage" in before
    assert "guidance_messages.manage" in before

    # An upgraded database starts from the persisted old role and its user link.
    _migrate(BASE)
    old = Role.objects.get(code=OLD_CODE)
    assert old.pk == role_pk
    assert old.name == "Guidance Services Staff"
    assert not Role.objects.filter(code=NEW_CODE).exists()
    user.refresh_from_db()
    assert user.role_id == role_pk and user.role.code == OLD_CODE

    _migrate(TARGET)
    assert not Role.objects.filter(code=OLD_CODE).exists()
    assert Role.objects.filter(code=NEW_CODE).count() == 1
    assert Role.objects.get(code=NEW_CODE).pk == role_pk
    user.refresh_from_db()
    assert user.role.code == NEW_CODE

    call_command("sync_identity_policy", stdout=StringIO())
    assert not Role.objects.filter(code=OLD_CODE).exists()
    assert Role.objects.filter(code=NEW_CODE).count() == 1
    assert Role.objects.get(code=NEW_CODE).pk == role_pk
    user.refresh_from_db()
    assert user.role.code == NEW_CODE
    assert effective_capabilities(user) == before


def test_forward_and_reverse_stop_when_both_role_identities_exist(synced_policy):
    Role.objects.create(code=OLD_CODE, name="Guidance Services Staff")
    try:
        with transaction.atomic(), pytest.raises(RuntimeError, match="collision"):
            MIGRATION.rename_role(django_apps, _editor())
        with transaction.atomic(), pytest.raises(RuntimeError, match="collision"):
            MIGRATION.reverse_role(django_apps, _editor())
    finally:
        Role.objects.filter(code=OLD_CODE).delete()


def test_forward_is_a_no_op_when_the_old_role_does_not_exist(synced_policy):
    assert not Role.objects.filter(code=OLD_CODE).exists()
    before = list(Role.objects.order_by("pk").values_list("pk", "code", "name"))

    with transaction.atomic():
        MIGRATION.rename_role(django_apps, _editor())

    assert list(Role.objects.order_by("pk").values_list("pk", "code", "name")) == before
