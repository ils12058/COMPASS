"""Real PostgreSQL canonical install, scoped cleanup and populated upgrade rehearsals."""

from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.bootstrap import IdentityPolicySyncError, sync_identity_policy
from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session, create_trusted_session
from compass.counseling.management.commands.preflight_student_session_summary_cutover import (
    historical_models,
)
from compass.counseling.models import CounselingEncounter, StudentSessionSummary
from compass.counseling.student_session_summaries import (
    publish_assigned_student_session_summary,
    put_assigned_student_session_summary,
)
from compass.counseling.student_session_summary_content import read_student_session_summary_content
from compass.notifications.models import Notification
from compass.service_catalog.models import Service
from tests.test_student_session_summaries import context

pytestmark = pytest.mark.django_db(transaction=True)
BASE = "0001_canonical_baseline"


@pytest.fixture
def canonical_before_cutover():
    import psycopg
    from psycopg import sql

    original = connection.settings_dict["NAME"]
    assert original.startswith("test_")
    database = "cont1b_rehearsal_" + uuid4().hex
    params = connection.get_connection_params()
    params["dbname"] = "postgres"
    with psycopg.connect(**params, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    connection.close()
    connection.settings_dict["NAME"] = database
    try:
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [
            (app, BASE if app in {"accounts", "counseling"} else name) for app, name in latest
        ]
        executor.migrate(before)
        yield latest
    finally:
        connection.close()
        connection.settings_dict["NAME"] = original
        with psycopg.connect(**params, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


def user(code, role="COUNSELOR"):
    kind, _ = Role.objects.get_or_create(code=role, defaults={"name": role})
    return User.objects.create_user(
        email=f"{code}@example.test",
        role=kind,
        password=None,
        first_name="Synthetic",
        last_name="Rehearsal",
    )


def legacy_world():
    models = historical_models()
    author, student = user("author"), user("student", "STUDENT")
    service = Service.objects.create(code="CONT1B", name="Synthetic", is_active=True)
    records = []
    for published in (False, True):
        encounter = CounselingEncounter.objects.create(
            student=student,
            counselor=author,
            service=service,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now() - timedelta(hours=1),
            created_by=author,
        )
        records.append(
            models[0].objects.create(
                encounter_id=encounter.pk,
                content_ciphertext="synthetic-old-binding-token",
                published_at=timezone.now() if published else None,
            )
        )
    notification = models[1].objects.create(
        recipient_id=student.pk,
        event_code="counseling.shared_summary.published",
        policy="OPTIONAL_INFORMATIONAL",
        title="Synthetic",
        message="Generic record link",
        source_type="counseling_shared_summary",
        source_id=records[1].pk,
        target_type="COUNSELING_SHARED_SUMMARY",
        target_id=records[1].pk,
    )
    email = models[2].objects.create(notification_id=notification.pk)
    subscription = (
        models[3]
        ._meta.apps.get_model("notifications", "PushSubscription")
        .objects.create(
            user_id=student.pk,
            session_id=create_auth_session(student).session.pk,
            endpoint_digest="synthetic-digest",
            encrypted_endpoint="synthetic",
            encrypted_p256dh="synthetic",
            encrypted_auth="synthetic",
        )
    )
    models[3].objects.create(notification_id=notification.pk, subscription_id=subscription.pk)
    unrelated = models[1].objects.create(
        recipient_id=student.pk,
        event_code="unrelated.synthetic",
        policy="OPTIONAL_INFORMATIONAL",
        title="Keep",
        message="Keep",
        source_type="unrelated",
        source_id=uuid4(),
    )
    return models, author, student, records, notification, email, unrelated


def preflight(tmp_path):
    plan, approval = tmp_path / "plan.json", tmp_path / "approval.json"
    call_command("preflight_student_session_summary_cutover", plan_file=plan, stdout=StringIO())
    data = json.loads(plan.read_text())
    approval.write_text(
        json.dumps(
            {
                "disposable_synthetic": True,
                "consumers_stopped": True,
                "approved_by": "isolated-local-test",
                "scope_digest": data["scope_digest"],
            }
        )
    )
    return plan, approval, data


def execute(plan, approval):
    call_command(
        "preflight_student_session_summary_cutover",
        plan_file=plan,
        approval_file=approval,
        execute=True,
        stdout=StringIO(),
    )


def test_populated_upgrade_and_scoped_cleanup(canonical_before_cutover, tmp_path, monkeypatch):
    models, author, student, rows, notification, email, unrelated = legacy_world()
    before_encounters = list(CounselingEncounter.objects.order_by("pk").values())
    audit = AuditEvent.objects.create(
        actor_type="SYSTEM",
        action="counseling.shared_summary.published",
        outcome="SUCCESS",
        target_type="counseling.sharedsummary",
        target_id=str(rows[1].pk),
        metadata={},
    )
    before_audit = AuditEvent.objects.filter(pk=audit.pk).values().get()
    with pytest.raises(RuntimeError, match="legacy resource rows remain"):
        MigrationExecutor(connection).migrate(canonical_before_cutover)
    assert models[0].objects.count() == 2
    plan, approval, data = preflight(tmp_path)
    assert len(data["summary_ids"]) == 2 and len(data["notification_ids"]) == 1
    assert "synthetic-old-binding-token" not in plan.read_text()
    execute(plan, approval)
    assert not models[0].objects.exists()
    assert not models[1].objects.filter(pk=notification.pk).exists()
    assert not models[2].objects.filter(pk=email.pk).exists()
    assert not models[3].objects.filter(notification_id=notification.pk).exists()
    assert models[1].objects.filter(pk=unrelated.pk).exists()
    assert list(CounselingEncounter.objects.order_by("pk").values()) == before_encounters
    assert AuditEvent.objects.filter(pk=audit.pk).values().get() == before_audit
    from django.contrib.contenttypes.models import ContentType

    legacy_type = ContentType.objects.create(
        app_label="counseling", model="counselingsharedsummary"
    )
    call_command("migrate", interactive=False, verbosity=0, stdout=StringIO())
    legacy_type.refresh_from_db()
    assert legacy_type.model == "studentsessionsummary"
    assert StudentSessionSummary._meta.db_table == "counseling_studentsessionsummary"
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(
            cursor, StudentSessionSummary._meta.db_table
        )
    assert set(constraints) == {
        "student_session_summary_pkey",
        "student_session_summary_encounter_fk",
        "student_session_summary_encounter_uniq",
        "student_session_summary_ciphertext_present",
    }

    assert "counseling_counselingsharedsummary" not in connection.introspection.table_names()
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda *_: None)
    item = put_assigned_student_session_summary(
        encounter_id=rows[1].encounter_id,
        counselor=author,
        content="Synthetic regenerated takeaways.",
    )
    assert read_student_session_summary_content(item) == "Synthetic regenerated takeaways."
    for _ in range(2):
        publish_assigned_student_session_summary(
            encounter_id=item.encounter_id, counselor=author, context=context(author)
        )
    assert StudentSessionSummary.objects.count() == 1
    assert (
        Notification.objects.filter(
            event_code="counseling.student_session_summary.published"
        ).count()
        == 1
    )
    assert AuditEvent.objects.filter(
        pk=audit.pk, action="counseling.shared_summary.published"
    ).exists()
    with pytest.raises(CommandError, match="already applied"):
        execute(plan, approval)
    assert not MigrationExecutor(connection).migration_plan(canonical_before_cutover)


@pytest.mark.parametrize(
    "failure",
    ["no-approval", "not-disposable", "changed-scope", "claimed", "push-claimed", "interrupt"],
)
def test_cleanup_refusals_are_atomic(canonical_before_cutover, tmp_path, monkeypatch, failure):
    models, _, _, rows, notification, email, _ = legacy_world()
    if failure == "claimed":
        models[2].objects.filter(pk=email.pk).update(status="PROCESSING", claim_token=uuid4())
    if failure == "push-claimed":
        models[3].objects.filter(notification_id=notification.pk).update(
            status="PROCESSING", claim_token=uuid4()
        )
    plan, approval, _ = preflight(tmp_path)
    if failure == "no-approval":
        with pytest.raises(CommandError, match="approval"):
            call_command("preflight_student_session_summary_cutover", plan_file=plan, execute=True)
    else:
        if failure == "not-disposable":
            data = json.loads(approval.read_text())
            data["disposable_synthetic"] = False
            approval.write_text(json.dumps(data))
        elif failure == "changed-scope":
            models[2].objects.filter(pk=email.pk).update(status="SENT")
        elif failure == "interrupt":
            from django.db.models.query import QuerySet

            original = QuerySet.delete

            def interrupted(query):
                if query.model._meta.label_lower == "counseling.counselingsharedsummary":
                    raise RuntimeError("synthetic interruption")
                return original(query)

            monkeypatch.setattr(QuerySet, "delete", interrupted)
        with pytest.raises((CommandError, RuntimeError)):
            execute(plan, approval)
    assert models[0].objects.count() == 2
    assert models[1].objects.filter(pk=notification.pk).exists()
    assert models[2].objects.filter(pk=email.pk).exists()
    assert models[3].objects.filter(notification_id=notification.pk).exists()


def test_capability_conversion_preserves_denials_expiry_and_sessions(canonical_before_cutover):
    actor, expired = user("revoked"), user("expired")
    cap = Capability.objects.create(code="shared_summaries.view_assigned", name="Shared Summaries")
    RoleCapability.objects.create(role=actor.role, capability=cap)
    designation = Designation.objects.create(code="CONT1B", name="Synthetic")
    DesignationCapability.objects.create(designation=designation, capability=cap)
    UserDesignation.objects.create(user=actor, designation=designation)
    for person, expires in (
        (actor, timezone.now() + timedelta(days=2)),
        (expired, timezone.now() - timedelta(days=2)),
    ):
        UserCapabilityOverride.objects.create(
            user=person,
            capability=cap,
            effect="REVOKE",
            reason="Synthetic deny",
            expires_at=expires,
        )
    overrides = list(UserCapabilityOverride.objects.order_by("pk").values())
    session = create_auth_session(actor).session
    trusted = create_trusted_session(actor).session
    with pytest.raises(IdentityPolicySyncError, match="0002_student_session_summary"):
        sync_identity_policy()
    MigrationExecutor(connection).migrate(canonical_before_cutover)
    cap.refresh_from_db()
    session.refresh_from_db()
    trusted.refresh_from_db()
    assert cap.code == "student_session_summaries.view_assigned"
    assert list(UserCapabilityOverride.objects.order_by("pk").values()) == overrides
    assert not actor.has_capability(cap.code) and expired.has_capability(cap.code)
    assert not actor.has_capability("shared_summaries.view_assigned")
    assert session.revoked_at and trusted.revoked_at
    assert RoleCapability.objects.filter(role=actor.role, capability_id=cap.pk).exists()
    assert DesignationCapability.objects.filter(
        designation=designation, capability_id=cap.pk
    ).exists()


def test_mixed_capability_collision_aborts(canonical_before_cutover):
    for code in ("shared_summaries.view_self", "student_session_summaries.view_self"):
        Capability.objects.create(code=code, name="Synthetic")
    before = list(Capability.objects.order_by("pk").values())
    with pytest.raises(RuntimeError, match="collision"):
        MigrationExecutor(connection).migrate(canonical_before_cutover)
    assert list(Capability.objects.order_by("pk").values()) == before


def test_orphan_legacy_notification_blocks_cutover(canonical_before_cutover):
    recipient = user("orphan", "STUDENT")
    Notification.objects.create(
        recipient=recipient,
        event_code="counseling.shared_summary.published",
        policy="OPTIONAL_INFORMATIONAL",
        title="Synthetic",
        message="Generic",
        source_type="counseling_shared_summary",
        source_id=uuid4(),
    )
    with pytest.raises(RuntimeError, match="legacy resource rows remain"):
        MigrationExecutor(connection).migrate(canonical_before_cutover)
