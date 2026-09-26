"""Required Counseling bootstrap, Catalog boundaries, and deployment readiness."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.db import close_old_connections
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.accounts.policy import CAPABILITY_CODES
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.services import create_encounter, get_counseling_service
from compass.service_catalog.bootstrap import (
    canonical_counseling_readiness,
    sync_canonical_services,
)
from compass.service_catalog.models import Service, ServiceDeliveryMode, ServiceProviderRole
from compass.service_catalog.services import (
    CanonicalServiceRequired,
    CanonicalServiceReserved,
    create_service,
    set_service_active,
    update_service,
)
from tests.canonical_service_helpers import legacy_counseling_service


def sync_policy():
    call_command("sync_identity_policy", verbosity=0)


def user(email: str, role: str):
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
    )


def auth_client(actor):
    now = timezone.now()
    issued = create_auth_session(actor, now=now, mfa_verified_at=now)
    client = Client()
    client.cookies["compass_session"] = issued.token
    csrf_response = client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200
    return client, {"HTTP_X_CSRFTOKEN": csrf_response.json()["csrf_token"]}


def service_events():
    return list(
        AuditEvent.objects.filter(action__startswith="service.")
        .order_by("occurred_at", "id")
        .values_list("action", "actor_type")
    )


@pytest.mark.django_db
def test_sync_requires_identity_policy_and_command_explains_order():
    with pytest.raises(CommandError, match="sync_identity_policy before sync_canonical_services"):
        call_command("sync_canonical_services", stdout=StringIO())
    assert not Role.objects.filter(code="COUNSELOR").exists()
    assert not Service.objects.filter(code="COUNSELING").exists()


@pytest.mark.django_db
def test_fresh_sync_is_active_bookable_idempotent_and_audited_once():
    sync_policy()
    first_output = StringIO()
    call_command("sync_canonical_services", stdout=first_output)
    service = Service.objects.get(code="COUNSELING")
    assert "created" in first_output.getvalue()
    assert service.name == "Counseling"
    assert service.is_active
    assert service.appointment_policy == "OPTIONAL"
    assert service.default_duration_minutes == 60
    assert service.cancellation_cutoff_minutes == 30
    assert not service.requires_current_inventory
    assert set(service.delivery_mode_assignments.values_list("mode", flat=True)) == {"IN_PERSON"}
    assert set(service.provider_role_assignments.values_list("role__code", flat=True)) == {
        "COUNSELOR"
    }
    assert canonical_counseling_readiness() == (True, "ok")
    assert get_counseling_service().pk == service.pk
    events = service_events()
    assert events == [("service.created", "SYSTEM")]

    second_output = StringIO()
    call_command("sync_canonical_services", stdout=second_output)
    assert "unchanged" in second_output.getvalue()
    assert Service.objects.filter(code="COUNSELING").count() == 1
    assert ServiceDeliveryMode.objects.filter(service=service).count() == 1
    assert ServiceProviderRole.objects.filter(service=service).count() == 1
    assert Service.objects.get(code="COUNSELING").pk == service.pk
    assert service_events() == events


@pytest.mark.django_db(transaction=True)
def test_concurrent_sync_creates_one_complete_canonical_service():
    sync_policy()

    def run_sync():
        close_old_connections()
        try:
            return sync_canonical_services()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_sync(), range(2)))
    assert {result.outcome for result in results} == {"created", "unchanged"}
    assert len({result.service_id for result in results}) == 1
    assert Service.objects.filter(code="COUNSELING").count() == 1
    assert ServiceDeliveryMode.objects.filter(service_id=results[0].service_id).count() == 1
    assert ServiceProviderRole.objects.filter(service_id=results[0].service_id).count() == 1


@pytest.mark.django_db
def test_existing_customization_and_references_survive_sync():
    sync_policy()
    admin = user("admin@example.edu", "IT_ADMIN")
    student = user("student@example.edu", "STUDENT")
    counselor = user("counselor@example.edu", "COUNSELOR")
    service = legacy_counseling_service(
        code="COUNSELING",
        name="Guidance Counseling",
        description="Locally configured",
        appointment_policy="REQUIRED",
        default_duration_minutes=45,
        cancellation_cutoff_minutes=60,
        requires_current_inventory=True,
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_roles=["COUNSELOR"],
        context=AuditContext.user(admin),
    )
    set_service_active(service_id=service.pk, is_active=True, context=AuditContext.user(admin))
    start = timezone.now() + timedelta(days=7)
    appointment = Appointment.objects.create(
        reference_code="APT-2026-990001",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=start,
        ends_at=start + timedelta(minutes=45),
        cancellation_cutoff_minutes=60,
        created_by=student,
    )
    before_events = service_events()

    result = sync_canonical_services()
    service.refresh_from_db()
    appointment.refresh_from_db()
    assert result.outcome == "unchanged"
    assert result.service_id == appointment.service_id == service.pk
    assert service.name == "Guidance Counseling"
    assert service.description == "Locally configured"
    assert service.appointment_policy == "REQUIRED"
    assert service.default_duration_minutes == 45
    assert service.cancellation_cutoff_minutes == 60
    assert service.requires_current_inventory
    assert set(service.delivery_mode_assignments.values_list("mode", flat=True)) == {
        "IN_PERSON",
        "ONLINE",
    }
    assert service_events() == before_events


@pytest.mark.django_db
def test_existing_required_drift_repairs_in_place_without_resetting_valid_settings():
    sync_policy()
    admin = user("admin@example.edu", "IT_ADMIN")
    service = legacy_counseling_service(
        code="COUNSELING",
        name="",
        description="Keep this description",
        appointment_policy="OPTIONAL",
        default_duration_minutes=None,
        cancellation_cutoff_minutes=45,
        requires_current_inventory=True,
        delivery_modes=[],
        provider_roles=[],
        context=AuditContext.user(admin),
    )
    result = sync_canonical_services()
    service.refresh_from_db()
    assert result.outcome == "updated"
    assert result.service_id == service.pk
    assert service.is_active
    assert service.name == "Counseling"
    assert service.description == "Keep this description"
    assert service.default_duration_minutes == 60
    assert service.cancellation_cutoff_minutes == 45
    assert service.requires_current_inventory
    assert canonical_counseling_readiness() == (True, "ok")
    assert set(service.delivery_mode_assignments.values_list("mode", flat=True)) == {"IN_PERSON"}
    assert set(service.provider_role_assignments.values_list("role__code", flat=True)) == {
        "COUNSELOR"
    }
    assert ("service.updated", "SYSTEM") in service_events()
    assert ("service.enabled", "SYSTEM") in service_events()
    before_events = service_events()
    assert sync_canonical_services().outcome == "unchanged"
    assert service_events() == before_events


@pytest.mark.django_db
def test_none_policy_cutoff_drift_is_normalized_without_reopening_booking():
    sync_policy()
    admin = user("admin@example.edu", "IT_ADMIN")
    service = legacy_counseling_service(
        code="COUNSELING",
        name="Locally named Counseling",
        appointment_policy="NONE",
        default_duration_minutes=45,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=AuditContext.user(admin),
    )
    result = sync_canonical_services()
    service.refresh_from_db()
    assert result.outcome == "updated"
    assert service.pk == result.service_id
    assert service.is_active
    assert service.name == "Locally named Counseling"
    assert service.appointment_policy == "NONE"
    assert service.default_duration_minutes == 45
    assert service.cancellation_cutoff_minutes is None
    assert canonical_counseling_readiness() == (True, "ok")


@pytest.mark.django_db
def test_fresh_bootstrap_supports_direct_counseling_and_routine_options():
    sync_policy()
    counselor = user("counselor@example.edu", "COUNSELOR")
    student = user("student@example.edu", "STUDENT")
    service = Service.objects.get(pk=sync_canonical_services().service_id)
    end = timezone.now() - timedelta(minutes=10)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=45),
        ended_at=end,
        context=AuditContext.user(counselor),
    )
    assert encounter.service_id == service.pk
    client, _ = auth_client(counselor)
    options = client.get("/api/v1/routine-interviews/direct/options")
    assert options.status_code == 200
    assert options.json()["service"]["id"] == str(service.pk)
    assert options.json()["delivery_modes"] == ["IN_PERSON"]


@pytest.mark.django_db
def test_reserved_code_disable_provider_invariant_and_generic_services():
    sync_policy()
    admin = user("admin@example.edu", "IT_ADMIN")
    context = AuditContext.user(admin)
    with pytest.raises(CanonicalServiceReserved, match="system-managed"):
        create_service(
            code=" counseling ", name="Manual", appointment_policy="NONE", context=context
        )
    assert not Service.objects.filter(code="COUNSELING").exists()

    service = Service.objects.get(pk=sync_canonical_services().service_id)
    with pytest.raises(CanonicalServiceReserved, match="system-managed"):
        create_service(
            code="COUNSELING", name="Duplicate", appointment_policy="NONE", context=context
        )
    with pytest.raises(CanonicalServiceRequired, match="cannot be disabled"):
        set_service_active(service_id=service.pk, is_active=False, context=context)
    with pytest.raises(CanonicalServiceRequired, match="COUNSELOR"):
        update_service(service_id=service.pk, changes={"provider_roles": []}, context=context)
    service.refresh_from_db()
    assert service.is_active
    assert service.provider_role_assignments.filter(role__code="COUNSELOR").exists()

    changed = update_service(
        service_id=service.pk,
        changes={"appointment_policy": "NONE", "cancellation_cutoff_minutes": None},
        context=context,
    )
    assert changed.is_active and changed.appointment_policy == "NONE"
    assert canonical_counseling_readiness() == (True, "ok")
    assert sync_canonical_services().outcome == "unchanged"
    changed = update_service(
        service_id=service.pk,
        changes={"delivery_modes": ["IN_PERSON", "ONLINE"]},
        context=context,
    )
    assert set(changed.delivery_mode_assignments.values_list("mode", flat=True)) == {
        "IN_PERSON",
        "ONLINE",
    }
    changed = update_service(
        service_id=service.pk, changes={"delivery_modes": ["IN_PERSON"]}, context=context
    )
    assert list(changed.delivery_mode_assignments.values_list("mode", flat=True)) == ["IN_PERSON"]

    ordinary = create_service(
        code="OTHER_SERVICE",
        name="Other",
        appointment_policy="NONE",
        context=context,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
    )
    assert not ordinary.is_active
    ordinary = set_service_active(service_id=ordinary.pk, is_active=True, context=context)
    assert ordinary.is_active
    ordinary = set_service_active(service_id=ordinary.pk, is_active=False, context=context)
    assert not ordinary.is_active


@pytest.mark.django_db
def test_api_rejects_reserved_create_disable_and_provider_removal():
    sync_policy()
    admin = user("admin@example.edu", "IT_ADMIN")
    client, headers = auth_client(admin)
    create_response = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "COUNSELING", "name": "Manual", "appointment_policy": "NONE"}),
        content_type="application/json",
        **headers,
    )
    assert create_response.status_code == 409
    assert create_response.json()["error"]["code"] == "canonical_service_reserved"
    service = Service.objects.get(pk=sync_canonical_services().service_id)
    disabled = client.post(f"/api/v1/services/{service.pk}/disable", **headers)
    assert disabled.status_code == 409
    assert disabled.json()["error"]["code"] == "canonical_service_required"
    removed = client.patch(
        f"/api/v1/services/{service.pk}",
        data=json.dumps({"provider_roles": []}),
        content_type="application/json",
        **headers,
    )
    assert removed.status_code == 409
    assert removed.json()["error"]["code"] == "canonical_service_required"
    service.refresh_from_db()
    assert service.is_active


@pytest.mark.django_db
def test_service_projection_marks_only_canonical_services_as_system_required():
    sync_policy()
    admin = user("system-required-admin@example.edu", "IT_ADMIN")
    client, headers = auth_client(admin)
    canonical = Service.objects.get(pk=sync_canonical_services().service_id)
    created = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "ADMISSION", "name": "Admission", "appointment_policy": "NONE"}),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["is_system_required"] is False

    detail = client.get(f"/api/v1/services/{canonical.pk}").json()
    assert detail["is_system_required"] is True
    rows = client.get("/api/v1/services?include_inactive=true").json()["items"]
    assert {row["code"]: row["is_system_required"] for row in rows} == {
        "ADMISSION": False,
        "COUNSELING": True,
    }


@pytest.mark.django_db
def test_student_booking_discovers_fresh_service_without_availability():
    sync_policy()
    student = user("student@example.edu", "STUDENT")
    service = Service.objects.get(pk=sync_canonical_services().service_id)
    client, _ = auth_client(student)
    response = client.get("/api/v1/appointments/booking/services")
    assert response.status_code == 200
    rows = response.json()["items"]
    assert len(rows) == 1
    assert rows[0]["id"] == str(service.pk)
    assert rows[0]["code"] == "COUNSELING"
    assert rows[0]["appointment_policy"] == "OPTIONAL"
    assert rows[0]["delivery_modes"] == ["IN_PERSON"]
    assert rows[0]["default_duration_minutes"] == 60
    assert not rows[0]["requires_current_inventory"]


@pytest.mark.django_db
@override_settings(DAILY_ENABLED=False)
def test_readiness_requires_canonical_configuration_but_not_daily(client):
    missing = client.get("/api/v1/health/ready")
    assert missing.status_code == 503
    assert missing.json() == {
        "status": "not_ready",
        "checks": {"application": "ok", "database": "ok", "canonical_services": "failed"},
    }
    sync_policy()
    service = Service.objects.get(pk=sync_canonical_services().service_id)
    assert client.get("/api/v1/health/ready").status_code == 200

    Service.objects.filter(pk=service.pk).update(is_active=False)
    assert client.get("/api/v1/health/ready").status_code == 503
    Service.objects.filter(pk=service.pk).update(is_active=True)
    ServiceProviderRole.objects.filter(service=service).delete()
    assert client.get("/api/v1/health/ready").status_code == 503
    ServiceProviderRole.objects.create(service=service, role=Role.objects.get(code="COUNSELOR"))
    ServiceDeliveryMode.objects.filter(service=service).delete()
    assert client.get("/api/v1/health/ready").status_code == 503
    ServiceDeliveryMode.objects.create(service=service, mode="IN_PERSON")
    Service.objects.filter(pk=service.pk).update(default_duration_minutes=None)
    assert client.get("/api/v1/health/ready").status_code == 503
    Service.objects.filter(pk=service.pk).update(default_duration_minutes=60)
    assert client.get("/api/v1/health/ready").status_code == 200
    ServiceDeliveryMode.objects.create(service=service, mode="ONLINE")
    assert client.get("/api/v1/health/ready").status_code == 200
    Service.objects.filter(pk=service.pk).update(
        appointment_policy="NONE", cancellation_cutoff_minutes=None
    )
    assert client.get("/api/v1/health/ready").status_code == 200
    assert "COUNSELING" not in json.dumps(client.get("/api/v1/health/ready").json())


def test_pr89_capability_codes_remain_canonical():
    assert {
        "services.catalog.view",
        "organization.structure.view",
        "services.manage",
        "organization.manage",
    } <= CAPABILITY_CODES
    assert "services.view" not in CAPABILITY_CODES
    assert "organization.view" not in CAPABILITY_CODES


@pytest.mark.django_db
def test_readiness_database_failure_skips_service_query(client):
    with (
        patch("compass.api.v1.health.connection.cursor", side_effect=RuntimeError("database gone")),
        patch("compass.api.v1.health.canonical_counseling_readiness") as check,
    ):
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"application": "ok", "database": "failed"}
    check.assert_not_called()
