"""Fresh reset schema keeps receipt guards without cutover or import controls."""

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

from compass.good_moral.models import GoodMoralRequest
from tests.test_good_moral import sync_policy
from tests.test_good_moral_receipts import edit, person, request_for

TARGET = ("good_moral", "0004_permanently_active_receipts")
pytestmark = pytest.mark.django_db(transaction=True)


def test_fresh_schema_has_unconditional_guards_and_required_origin():
    tables = connection.introspection.table_names()
    assert "good_moral_goodmoralreceiptledger" not in tables
    assert "good_moral_goodmoralreceiptimportbatch" not in tables
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.proname, pg_get_functiondef(p.oid) FROM pg_proc p "
            "WHERE p.proname LIKE 'gm_receipt_%' OR p.proname LIKE 'gm_inspection_%'"
        )
        definitions = dict(cursor.fetchall())
        for definition in definitions.values():
            assert "goodmoralreceiptledger" not in definition
            assert "LEGACY_" not in definition
        assert {
            "gm_receipt_identity_guard",
            "gm_receipt_projection_guard",
            "gm_inspection_request_guard",
        } <= definitions.keys()
        cursor.execute(
            "SELECT column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name='good_moral_goodmoralrequest' AND column_name='initiation_origin'"
        )
        assert cursor.fetchone() == (None, "NO")
    assert not GoodMoralRequest._meta.get_field("initiation_origin").has_default()


def test_receipt_history_cannot_downgrade_to_a_weaker_writer():
    sync_policy()
    actor = person("recorder", "COUNSELOR")
    item = edit(request_for(), actor, {"official_receipt_number": "OR-PERMANENT"})
    with pytest.raises(IrreversibleError):
        MigrationExecutor(connection).migrate([("good_moral", "0003_receipt_verification")])
    assert TARGET in MigrationExecutor(connection).loader.applied_migrations
    assert GoodMoralRequest.objects.get(pk=item.pk).official_receipt_number == "OR-PERMANENT"
