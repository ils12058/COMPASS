"""Real PostgreSQL rehearsal: fresh schema, canonical upgrade, and additive rollback.

Only pytest's disposable database is touched. Applied canonical files remain immutable.
"""

from datetime import timedelta

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.confidential_profile import (
    AccountProfileConfidentialContent,
    write_account_profile_confidential_content,
)
from compass.common.canonical_baseline import pre_canonical_history


@pytest.mark.django_db(transaction=True)
def test_postbaseline_upgrade_preserves_canonical_records_and_reverses_only_additions():
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["NAME"].startswith("test_")
    executor = MigrationExecutor(connection)
    full = executor.loader.graph.leaf_nodes()
    compass_labels = {
        config.label for config in apps.get_app_configs() if config.name.startswith("compass.")
    }
    baseline = []
    for label, leaf in full:
        if label not in compass_labels:
            baseline.append((label, leaf))
        elif (label, "0001_canonical_baseline") in executor.loader.disk_migrations:
            baseline.append((label, "0001_canonical_baseline"))
        else:
            baseline.append((label, None))
    try:
        executor.migrate(baseline)
        historical = executor.loader.project_state([node for node in baseline if node[1]]).apps
        Role = historical.get_model("accounts", "Role")
        User = historical.get_model("accounts", "User")
        Service = historical.get_model("service_catalog", "Service")
        Appointment = historical.get_model("appointments", "Appointment")
        student_role = Role.objects.create(code="STUDENT", name="Student")
        counselor_role = Role.objects.create(code="COUNSELOR", name="Counselor")
        student = User(
            email="upgrade-student@example.test",
            password="!",
            role_id=student_role.pk,
            first_name="Synthetic",
            last_name="Student",
            is_active=True,
        )
        counselor = User(
            email="upgrade-counselor@example.test",
            password="!",
            role_id=counselor_role.pk,
            first_name="Synthetic",
            last_name="Counselor",
            is_active=True,
        )
        for user in (student, counselor):
            write_account_profile_confidential_content(user, AccountProfileConfidentialContent())
            user.save()
        service = Service.objects.create(
            code="UPGRADE_FIXTURE",
            name="Synthetic upgrade service",
            is_active=True,
            appointment_booking_enabled=True,
            default_appointment_duration_minutes=60,
        )
        starts = timezone.now() + timedelta(days=2)
        item = Appointment.objects.create(
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
        fields = (
            "reference_code",
            "student_id",
            "provider_id",
            "service_id",
            "status",
            "starts_at",
            "ends_at",
        )
        original = Appointment.objects.filter(pk=item.pk).values(*fields).get()
        counts = (User.objects.count(), Service.objects.count(), Appointment.objects.count())
        MigrationExecutor(connection).migrate(full)
        CurrentAppointment = apps.get_model("appointments", "Appointment")
        assert CurrentAppointment.objects.filter(pk=item.pk).values(*fields).get() == original
        assert (
            apps.get_model("accounts", "User").objects.count(),
            apps.get_model("service_catalog", "Service").objects.count(),
            CurrentAppointment.objects.count(),
        ) == counts
        if hasattr(CurrentAppointment, "reminder_revision"):
            assert CurrentAppointment.objects.get(pk=item.pk).reminder_revision == 1
        # SVC-1, when present in a candidate, intentionally adds flexible pathways for existing
        # bookable Services; it must not mutate the canonical Service or Appointment rows.
        if apps.is_installed("compass.service_catalog"):
            try:
                Pathway = apps.get_model("service_catalog", "ServiceBookingPathway")
            except LookupError:
                pass
            else:
                assert (
                    Pathway.objects.filter(
                        service_id=service.pk, code="FLEXIBLE_APPOINTMENT"
                    ).count()
                    == 1
                )
        assert pre_canonical_history(connection) == []
        MigrationExecutor(connection).migrate(baseline)
        assert Appointment.objects.filter(pk=item.pk).values(*fields).get() == original
        assert User.objects.count() == counts[0]
        MigrationExecutor(connection).migrate(full)
        assert CurrentAppointment.objects.filter(pk=item.pk).values(*fields).get() == original
    finally:
        MigrationExecutor(connection).migrate(full)
