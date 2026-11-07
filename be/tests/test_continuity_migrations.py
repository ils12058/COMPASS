"""Real PostgreSQL integration-graph upgrade/empty-foundation rollback rehearsal."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent, AuditOutcome
from compass.audit.services import record_event
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.models import CounselingEncounter, StudentSessionSummary
from compass.service_catalog.models import Service


@pytest.mark.django_db(transaction=True)
def test_existing_graph_upgrade_preserves_sources_identity_and_audit():
    assert connection.vendor == "postgresql"
    executor = MigrationExecutor(connection)
    final = executor.loader.graph.leaf_nodes()
    before = [("counseling", "0002_student_session_summary_contract")]
    executor.migrate(before)
    try:
        tables = connection.introspection.table_names()
        assert "counseling_counselorcasecontinuitygrant" not in tables
        call_command("sync_identity_policy", verbosity=0)
        student = User.objects.create_user(
            email="migration-student@synthetic.test",
            role="STUDENT",
            first_name="Synthetic",
            last_name="Student",
            password=None,
        )
        counselor = User.objects.create_user(
            email="migration-counselor@synthetic.test",
            role="COUNSELOR",
            first_name="Synthetic",
            last_name="Counselor",
            password=None,
        )
        service = Service.objects.create(code="MIGRATION-SYNTHETIC", name="Synthetic")
        now = timezone.now()
        encounter = CounselingEncounter.objects.create(
            student=student,
            counselor=counselor,
            service=service,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=now - timedelta(hours=1),
            ended_at=now,
        )
        StudentSessionSummary.objects.create(
            encounter=encounter, content_ciphertext="SYNTHETIC-DO-NOT-DECRYPT"
        )
        record_event(
            context=AuditContext.user(counselor),
            action="counseling.encounter.created",
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.counselingencounter",
            target_id=encounter.pk,
            metadata={"test_only": True},
        )
        models = [User, CounselingEncounter, StudentSessionSummary, AuditEvent]
        saved = [list(model.objects.order_by("pk").values()) for model in models]
        MigrationExecutor(connection).migrate(final)
        assert [list(model.objects.order_by("pk").values()) for model in models] == saved
        tables = connection.introspection.table_names()
        assert "counseling_counselorcasecontinuitygrant" in tables
        assert "counseling_counselorcasecontinuityscope" in tables
        # New tables are empty in this rehearsal; never prescribe rollback for retained grants.
        MigrationExecutor(connection).migrate(before)
        MigrationExecutor(connection).migrate(final)
        assert [list(model.objects.order_by("pk").values()) for model in models] == saved
    finally:
        MigrationExecutor(connection).migrate(final)


def _columns(table):
    with connection.cursor() as cursor:
        return {
            column.name for column in connection.introspection.get_table_description(cursor, table)
        }


def _constraints(table):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table)


@pytest.mark.django_db(transaction=True)
def test_communication_scope_upgrade_historical_rows_constraint_and_rollback():
    assert connection.vendor == "postgresql"
    executor = MigrationExecutor(connection)
    final = executor.loader.graph.leaf_nodes()
    before = [("counseling", "0005_student_placement_marker")]
    target = [("counseling", "0006_case_communication_scope")]
    table = "counseling_counselorcasecontinuitygrant"
    executor.migrate(before)
    try:
        call_command("sync_identity_policy", verbosity=0)
        student = User.objects.create_user(
            email="migration-comm-student@synthetic.test",
            role="STUDENT",
            first_name="Synthetic",
            last_name="Student",
            password=None,
        )
        author = User.objects.create_user(
            email="migration-comm-author@synthetic.test",
            role="COUNSELOR",
            first_name="Synthetic",
            last_name="Author",
            password=None,
        )
        receiver = User.objects.create_user(
            email="migration-comm-receiver@synthetic.test",
            role="COUNSELOR",
            first_name="Synthetic",
            last_name="Receiver",
            password=None,
        )
        now = timezone.now()
        historical = (
            MigrationExecutor(connection)
            .loader.project_state(before)
            .apps.get_model("counseling", "CounselorCaseContinuityGrant")
        )
        grant_id = uuid4()
        historical.objects.create(
            id=grant_id,
            student_id=student.pk,
            original_counselor_id=author.pk,
            receiving_counselor_id=receiver.pk,
            coverage_kind="PLANNED_HANDOFF",
            reason_category="PLANNED_ABSENCE",
            requested_by_id=author.pk,
            requested_at=now,
            starts_at=now,
            expires_at=now + timedelta(hours=1),
            decision="REQUESTED",
            policy_version="synthetic-v1",
            policy_evidence="TEST-ONLY-MIGRATION",
            policy_digest="a" * 64,
            student_placement_marker="SYNTHETIC-MARKER",
            snapshot_digest="b" * 64,
            request_id=uuid4(),
        )
        assert "communication_purpose" not in _columns(table)
        assert "counseling_grant_communication_scope" not in _constraints(table)

        MigrationExecutor(connection).migrate(target)
        assert {"communication_purpose", "communication_policy_digest"} <= _columns(table)
        assert _constraints(table)["counseling_grant_communication_scope"]["check"] is True
        row = Grant.objects.get(pk=grant_id)
        assert row.communication_purpose is None
        assert row.communication_policy_digest == ""
        assert row.snapshot_digest == "b" * 64

        def reject(purpose, digest, original_id):
            with pytest.raises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE "
                        + table
                        + " SET communication_purpose=%s, communication_policy_digest=%s,"
                        " original_counselor_id=%s WHERE id=%s",
                        [purpose, digest, original_id, grant_id],
                    )

        reject("CASE_COORDINATION", "", author.pk)
        reject("CASE_COORDINATION", "0" * 64, None)
        reject(None, "0" * 64, author.pk)

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE " + table + " SET communication_purpose='CASE_COORDINATION',"
                " communication_policy_digest=%s WHERE id=%s",
                ["0" * 64, grant_id],
            )
        assert Grant.objects.get(pk=grant_id).communication_purpose == "CASE_COORDINATION"

        # Rollback drops the additive columns; reapply restores NULL/"" and keeps the row.
        MigrationExecutor(connection).migrate(before)
        assert "communication_purpose" not in _columns(table)
        assert "counseling_grant_communication_scope" not in _constraints(table)
        MigrationExecutor(connection).migrate(target)
        row = Grant.objects.get(pk=grant_id)
        assert row.communication_purpose is None
        assert row.communication_policy_digest == ""
        assert row.student_id == student.pk
        assert row.original_counselor_id == author.pk
        assert row.snapshot_digest == "b" * 64
    finally:
        MigrationExecutor(connection).migrate(final)
