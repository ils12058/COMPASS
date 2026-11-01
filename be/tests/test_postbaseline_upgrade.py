"""Disposable PostgreSQL forward-upgrade and compatible-column recovery rehearsal.

Irreversible policy/cutover migrations and immutable Faculty history are never reversed.
"""

import copy
from datetime import timedelta
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.confidential_profile import (
    AccountProfileConfidentialContent,
    write_account_profile_confidential_content,
)
from compass.common.canonical_baseline import pre_canonical_history


@pytest.mark.django_db(transaction=True)
def test_postbaseline_upgrade_preserves_records_and_supports_forward_recovery(django_db_blocker):
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["NAME"].startswith("test_")
    alias = "test_fac5_upgrade_" + uuid4().hex
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE "{alias}"')
    config = copy.deepcopy(connection.settings_dict)
    config["NAME"] = alias
    connections.databases[alias] = config
    db = connections[alias]
    try:
        # Explicitly open only our newly created disposable alias; Django blocks late aliases.
        with django_db_blocker.unblock():
            db.ensure_connection()
        executor = MigrationExecutor(db)
        full = executor.loader.graph.leaf_nodes()
        compass_labels = {
            config.label for config in apps.get_app_configs() if config.name.startswith("compass.")
        }
        # The empty-resource summary cutover is a permanent floor, not a reversible addition.
        floor = {
            "accounts": "0002_student_session_summary_capabilities",
            "counseling": "0002_student_session_summary_contract",
        }
        baseline = []
        for label, leaf in full:
            if label not in compass_labels:
                baseline.append((label, leaf))
            elif label in floor:
                baseline.append((label, floor[label]))
            elif (label, "0001_canonical_baseline") in executor.loader.disk_migrations:
                baseline.append((label, "0001_canonical_baseline"))
            else:
                baseline.append((label, None))
        # A new owned database starts at this schema; no installed migration is rolled back.
        executor.migrate(baseline)
        historical = executor.loader.project_state([node for node in baseline if node[1]]).apps

        def manager(app, model):
            return historical.get_model(app, model).objects.using(alias)

        student_role = manager("accounts", "Role").create(code="STUDENT", name="Student")
        counselor_role = manager("accounts", "Role").create(code="COUNSELOR", name="Counselor")
        people = []
        for role, name in ((student_role, "Student"), (counselor_role, "Counselor")):
            user = historical.get_model("accounts", "User")(
                email=f"upgrade-{name}@synthetic.invalid",
                password="!",
                role_id=role.pk,
                first_name="Synthetic",
                last_name=name,
                is_active=True,
            )
            write_account_profile_confidential_content(user, AccountProfileConfidentialContent())
            user.save(using=alias)
            people.append(user)
        student, counselor = people
        service = manager("service_catalog", "Service").create(
            code="UPGRADE_FIXTURE",
            name="Synthetic upgrade service",
            is_active=True,
            appointment_booking_enabled=True,
            default_appointment_duration_minutes=60,
        )
        starts = timezone.now() + timedelta(days=2)
        item = manager("appointments", "Appointment").create(
            reference_code="UPGRADE-FIXTURE",
            student_id=student.pk,
            provider_id=counselor.pk,
            service_id=service.pk,
            service_name_snapshot=service.name,
            delivery_mode="IN_PERSON",
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            status="SCHEDULED",
            created_by_id=student.pk,
        )
        models = [
            ("accounts", "User"),
            ("service_catalog", "Service"),
            ("appointments", "Appointment"),
        ]
        original = {key: list(manager(*key).order_by("pk").values()) for key in models}
        executor = MigrationExecutor(db)
        executor.migrate(full)
        current = executor.loader.project_state(full).apps
        for key, rows in original.items():
            after = list(current.get_model(*key).objects.using(alias).order_by("pk").values())
            assert [
                {name: row[name] for name in old} for old, row in zip(rows, after, strict=True)
            ] == rows
        pathway = current.get_model("service_catalog", "ServiceBookingPathway")
        assert (
            pathway.objects.using(alias)
            .filter(service_id=service.pk, code="FLEXIBLE_APPOINTMENT")
            .count()
            == 1
        )
        assert pre_canonical_history(db) == []
        # Compatible code can read retained columns. A failed transaction rolls back data,
        # then an idempotent forward migrate recovers without dropping schema or history.
        with pytest.raises(RuntimeError, match="Synthetic component failure"):
            with transaction.atomic(using=alias):
                manager("appointments", "Appointment").filter(pk=item.pk).update(
                    service_name_snapshot="Uncommitted recovery probe"
                )
                raise RuntimeError("Synthetic component failure")
        MigrationExecutor(db).migrate(full)
        for key, rows in original.items():
            assert list(manager(*key).order_by("pk").values()) == rows
        assert (
            current.get_model("appointments", "Appointment")
            .objects.using(alias)
            .get(pk=item.pk)
            .reminder_revision
            == 1
        )
    finally:
        db.close()
        del connections[alias]
        del connections.databases[alias]
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE "{alias}"')
