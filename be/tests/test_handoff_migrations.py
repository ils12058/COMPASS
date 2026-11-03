"""Current integration -> additive Handoff -> isolated rollback/reapply, preserving old rows."""

import json
from pathlib import Path

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from compass.counseling.handoff_models import CounselorHandoffSummary as Handoff
from compass.counseling.models import CounselingEncounter
from tests import test_handoff as cases
from tests.test_continuity_access import approved

metadata_case = cases.metadata_case
selected_case = cases.selected_case
workflow_case = cases.workflow_case
pytestmark = pytest.mark.django_db(transaction=True)


def _grant_row(grant_id, marker_column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, student_id, receiving_counselor_id, policy_digest, "
            f"{marker_column} FROM counseling_counselorcasecontinuitygrant WHERE id = %s",
            [grant_id],
        )
        return cursor.fetchone()


def test_populated_integration_upgrade_and_disposable_rollback_reapply(workflow_case):
    c = workflow_case
    g = approved(c)
    # The 0005 rename means the pre-0004 row is only readable through its old column name.
    before = _grant_row(g["id"], "student_placement_marker")
    encounter = CounselingEncounter.objects.values().get(pk=c.encounter.pk)
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"].startswith(
        "test_"
    )
    old = [("counseling", "0003_case_continuity_foundation")]
    new = [("counseling", "0005_student_placement_marker")]
    try:
        MigrationExecutor(connection).migrate(old)
        assert Handoff._meta.db_table not in connection.introspection.table_names()
        assert _grant_row(g["id"], "student_affiliation_marker") == before
        MigrationExecutor(connection).migrate(new)
        cases.submitted(c, g)
        assert cases.op(c, g, "receive", actor=c.receiver)["content"] == cases.TEXT
        assert _grant_row(g["id"], "student_placement_marker") == before
        assert CounselingEncounter.objects.values().get(pk=c.encounter.pk) == encounter
        MigrationExecutor(connection).migrate(old)
        assert Handoff._meta.db_table not in connection.introspection.table_names()
        MigrationExecutor(connection).migrate(new)
        assert not Handoff.objects.exists()
        assert _grant_row(g["id"], "student_placement_marker") == before
    finally:
        MigrationExecutor(connection).migrate(new)
    inventory = json.loads(
        (Path(__file__).parents[1] / "compass/common/canonical_migrations.json").read_text()
    )
    assert (
        "counseling/migrations/0004_counselor_handoff_summary.py"
        in inventory["additive_migrations"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"state": "UNKNOWN"},
        {"state": "SUBMITTED"},
        {"version": 0},
        {"content_ciphertext": ""},
    ],
)
def test_database_constraints(workflow_case, bad):
    c = workflow_case
    g = approved(c)
    cases.draft(c, g)
    with pytest.raises(IntegrityError), transaction.atomic():
        Handoff.objects.all().update(**bad)
    assert Handoff.objects.get().state == "DRAFT"
