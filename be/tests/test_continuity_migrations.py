"""Real PostgreSQL integration-graph upgrade/empty-foundation rollback rehearsal."""

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent, AuditOutcome
from compass.audit.services import record_event
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
        from datetime import timedelta

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
