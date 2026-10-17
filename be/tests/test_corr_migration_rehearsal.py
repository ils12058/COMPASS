"""Real PostgreSQL rehearsal of the reviewed CORR-1A/1B migrations over pre-existing rows.

Live staging is at group_sessions 0001 and service_catalog 0003. This migrates pytest's disposable
database back to that state, adds representative Group Session, facilitator, registration and
Fixed Slot rows through historical models, then applies the exact reviewed forward plan.
"""

from datetime import timedelta

import pytest
from django.apps import apps
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from compass.accounts.confidential_profile import (
    AccountProfileConfidentialContent,
    write_account_profile_confidential_content,
)

REVIEWED = [
    ("group_sessions", "0002_alter_groupsessionfacilitator_group_session"),
    ("group_sessions", "0003_group_session_scheduling_and_external_facilitators"),
    ("service_catalog", "0004_serviceappointmentslot_withdrawn_at_and_more"),
]
LIVE_STATE = {"group_sessions": "0001_initial", "service_catalog": "0003_fixed_date_slots"}


def targets():
    full = MigrationExecutor(connection).loader.graph.leaf_nodes()
    return full, [(label, LIVE_STATE.get(label, name)) for label, name in full]


def applied(label):
    executor = MigrationExecutor(connection)
    return {name for app, name in executor.loader.applied_migrations if app == label}


def columns(table):
    with connection.cursor() as cursor:
        return {c.name for c in connection.introspection.get_table_description(cursor, table)}


def live_state_rows(historical, *, second_lead=False):
    """Rows the deployed live code can create before the reviewed migrations run."""
    Role = historical.get_model("accounts", "Role")
    User = historical.get_model("accounts", "User")
    Service = historical.get_model("service_catalog", "Service")
    Appointment = historical.get_model("appointments", "Appointment")
    GroupSession = historical.get_model("group_sessions", "GroupSession")
    Facilitator = historical.get_model("group_sessions", "GroupSessionFacilitator")
    Registration = historical.get_model("group_sessions", "GroupSessionRegistration")
    Slot = historical.get_model("service_catalog", "ServiceAppointmentSlot")

    student_role, _ = Role.objects.get_or_create(code="STUDENT", defaults={"name": "Student"})
    counselor_role, _ = Role.objects.get_or_create(code="COUNSELOR", defaults={"name": "Counselor"})
    users = {}
    for key, role, first, last in [
        ("student", student_role, "Synthetic", "Student"),
        ("lead", counselor_role, "Lead", "Counselor"),
        ("co", counselor_role, "Co", "Facilitator"),
    ]:
        user = User(
            email=f"rehearsal-{key}@example.test",
            password="!",
            role_id=role.pk,
            first_name=first,
            last_name=last,
            is_active=True,
        )
        write_account_profile_confidential_content(user, AccountProfileConfidentialContent())
        user.save()
        users[key] = user
    service = Service.objects.create(
        code="REHEARSAL_FIXTURE",
        name="Synthetic rehearsal service",
        is_active=True,
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
    )
    starts = timezone.now() + timedelta(days=3)
    appointment = Appointment.objects.create(
        reference_code="REHEARSAL-FIXTURE",
        student_id=users["student"].pk,
        provider_id=users["lead"].pk,
        service_id=service.pk,
        service_name_snapshot=service.name,
        delivery_mode="IN_PERSON",
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status="SCHEDULED",
        created_by_id=users["student"].pk,
    )
    sessions = []
    for title, status, facilitators in [
        ("Published with two facilitators", "PUBLISHED", [("lead", True), ("co", second_lead)]),
        ("Draft with one facilitator", "DRAFT", [("lead", True)]),
    ]:
        session = GroupSession.objects.create(
            title=title,
            service_id=service.pk,
            organizer_id=users["lead"].pk,
            starts_at=starts + timedelta(days=1),
            ends_at=starts + timedelta(days=1, hours=2),
            capacity=10,
            status=status,
        )
        for key, is_lead in facilitators:
            Facilitator.objects.create(
                group_session_id=session.pk, counselor_id=users[key].pk, is_lead=is_lead
            )
        sessions.append(session)
    Registration.objects.create(group_session_id=sessions[0].pk, student_id=users["student"].pk)
    booked = Slot.objects.create(
        service_id=service.pk,
        provider_id=users["lead"].pk,
        delivery_mode="IN_PERSON",
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        current_appointment_id=appointment.pk,
    )
    open_slot = Slot.objects.create(
        service_id=service.pk,
        provider_id=users["co"].pk,
        delivery_mode="ONLINE",
        starts_at=starts + timedelta(hours=2),
        ends_at=starts + timedelta(hours=3),
    )
    return users, appointment, sessions, booked, open_slot


@pytest.mark.django_db(transaction=True)
def test_reviewed_plan_preserves_live_state_rows_and_installs_lifecycle_protection():
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["NAME"].startswith("test_")
    full, live = targets()
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(live)
        executor.loader.build_graph()
        plan = executor.migration_plan(full)
        assert not any(backwards for _, backwards in plan)
        assert sorted((m.app_label, m.name) for m, _ in plan) == sorted(REVIEWED)
        historical = executor.loader.project_state(live).apps
        users, appointment, sessions, booked, open_slot = live_state_rows(historical)

        MigrationExecutor(connection).migrate(full)

        GroupSession = apps.get_model("group_sessions", "GroupSession")
        Facilitator = apps.get_model("group_sessions", "GroupSessionFacilitator")
        Registration = apps.get_model("group_sessions", "GroupSessionRegistration")
        Slot = apps.get_model("service_catalog", "ServiceAppointmentSlot")
        Booking = apps.get_model("service_catalog", "ServiceAppointmentSlotBooking")
        assert {
            (s.pk, s.title, s.status, s.version, s.schedule_revision)
            for s in GroupSession.objects.all()
        } == {(s.pk, s.title, s.status, s.version, 1) for s in sessions}
        rows = {(f.group_session_id, f.internal_user_id): f for f in Facilitator.objects.all()}
        assert set(rows) == {
            (sessions[0].pk, users["lead"].pk),
            (sessions[0].pk, users["co"].pk),
            (sessions[1].pk, users["lead"].pk),
        }
        for (_, user_id), row in rows.items():
            user = next(u for u in users.values() if u.pk == user_id)
            assert row.kind == "INTERNAL" and row.external_display_name == ""
            assert row.removed_at is None
            assert row.display_name_snapshot == f"{user.first_name} {user.last_name}"
            assert row.is_lead is (user_id == users["lead"].pk)
        assert Registration.objects.filter(group_session_id=sessions[0].pk).count() == 1
        assert Slot.objects.filter(withdrawn_at__isnull=True).count() == 2
        assert list(Booking.objects.values_list("slot_id", "appointment_id")) == [
            (booked.pk, appointment.pk)
        ]

        # Lifecycle protection installed by the reviewed RunPython operations.
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM group_sessions_groupsession WHERE id = %s", [sessions[1].pk]
            )
        co = rows[(sessions[0].pk, users["co"].pk)]
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM group_sessions_groupsessionfacilitator WHERE id = %s", [co.pk]
            )
        co.refresh_from_db()
        assert co.removed_at is not None, "Facilitator deletion is preserved as removal"
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM service_catalog_serviceappointmentslot WHERE id = %s", [open_slot.pk]
            )
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM service_catalog_serviceappointmentslotbooking")
        Slot.objects.filter(pk=open_slot.pk).update(current_appointment_id=appointment.pk)
        assert Booking.objects.filter(slot_id=open_slot.pk, appointment_id=appointment.pk).exists()
        # The new active-lead constraint now holds for every session.
        with pytest.raises(IntegrityError), transaction.atomic():
            Facilitator.objects.filter(pk=co.pk).update(is_lead=True, removed_at=None)
    finally:
        MigrationExecutor(connection).migrate(full)


@pytest.mark.django_db(transaction=True)
def test_more_than_one_lead_stops_0003_atomically_and_recovers_forward_after_data_review():
    full, live = targets()
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(live)
        executor.loader.build_graph()
        historical = executor.loader.project_state(live).apps
        users, _, sessions, _, _ = live_state_rows(historical, second_lead=True)
        co_facilitator = users["co"]

        with pytest.raises(IntegrityError):
            MigrationExecutor(connection).migrate(full)
        # 0002 committed on its own; 0003 rolled back entirely, including its new columns.
        assert applied("group_sessions") == {
            "0001_initial",
            "0002_alter_groupsessionfacilitator_group_session",
        }
        assert "kind" not in columns("group_sessions_groupsessionfacilitator")
        assert "schedule_revision" not in columns("group_sessions_groupsession")

        # Forward recovery only: review the data, keep one lead, then continue the plan.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE group_sessions_groupsessionfacilitator SET is_lead = false "
                "WHERE group_session_id = %s AND counselor_id = %s",
                [sessions[0].pk, co_facilitator.pk],
            )
        MigrationExecutor(connection).migrate(full)
        assert applied("group_sessions") >= {
            name for app, name in REVIEWED if app == "group_sessions"
        }
        Facilitator = apps.get_model("group_sessions", "GroupSessionFacilitator")
        assert (
            Facilitator.objects.filter(group_session_id=sessions[0].pk, is_lead=True).count() == 1
        )
    finally:
        MigrationExecutor(connection).migrate(full)
