from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.platform_ops.models import MaintenanceConfiguration
from compass.platform_ops.services import (
    InvalidMaintenanceWindow,
    MaintenanceAlreadyEnabled,
    MaintenanceScheduleConflict,
    MaintenanceState,
    cancel_maintenance_schedule,
    derive_maintenance_snapshot,
    disable_manual_maintenance,
    enable_manual_maintenance,
    get_maintenance_configuration,
    get_maintenance_snapshot,
    schedule_maintenance,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str = "IT_ADMIN") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Runtime",
        last_name="Operator",
    )


def auth_client(user: User, *, recent_mfa: bool) -> Client:
    issued = create_auth_session(
        user,
        mfa_verified_at=timezone.now() if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def post_json(client: Client, path: str, payload: dict[str, object]):
    return client.post(
        path,
        data=json.dumps(payload, default=str),
        content_type="application/json",
        **csrf(client),
    )


def put_json(client: Client, path: str, payload: dict[str, object]):
    return client.put(
        path,
        data=json.dumps(payload, default=str),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_singleton_configuration_lazily_initializes_once():
    assert MaintenanceConfiguration.objects.count() == 0

    first = get_maintenance_configuration()
    second = get_maintenance_configuration()

    assert first.pk == second.pk == 1
    assert MaintenanceConfiguration.objects.count() == 1
    assert first.manual_enabled is False
    assert first.scheduled_start_at is None
    assert first.scheduled_end_at is None


@pytest.mark.django_db
def test_maintenance_read_and_mutations_use_view_manage_and_recent_mfa():
    sync_policy()
    admin = make_user("runtime-admin@example.edu")
    counselor = make_user("runtime-counselor@example.edu", "COUNSELOR")
    student = make_user("runtime-student@example.edu", "STUDENT")

    assert auth_client(student, recent_mfa=True).get("/api/v1/platform/maintenance").status_code == 403

    no_mfa = auth_client(admin, recent_mfa=False)
    denied = post_json(
        no_mfa,
        "/api/v1/platform/maintenance/enable",
        {"message": "Planned database maintenance"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    counselor_client = auth_client(counselor, recent_mfa=True)
    denied_role = post_json(
        counselor_client,
        "/api/v1/platform/maintenance/enable",
        {"message": "Not authorized"},
    )
    assert denied_role.status_code == 403
    assert denied_role.json()["error"]["code"] == "permission_denied"

    admin_client = auth_client(admin, recent_mfa=True)
    enabled = post_json(
        admin_client,
        "/api/v1/platform/maintenance/enable",
        {"message": "Planned database maintenance"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["state"] == "MAINTENANCE"
    assert enabled.json()["source"] == "MANUAL"

    viewed = admin_client.get("/api/v1/platform/maintenance")
    assert viewed.status_code == 200


@pytest.mark.django_db
def test_non_it_baselines_and_institutional_designations_do_not_gain_manage():
    sync_policy()
    counselor = make_user("baseline-counselor@example.edu", "COUNSELOR")
    staff = make_user("baseline-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("baseline-student@example.edu", "STUDENT")
    officer = make_user("baseline-officer@example.edu", "INSTITUTIONAL_OFFICER")
    dpo = make_user("baseline-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    head = make_user("baseline-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    for user in (counselor, staff, student, officer, dpo, head):
        assert not user.has_capability("platform_operations.manage")


@pytest.mark.django_db
def test_manual_expected_end_is_informational_and_never_auto_disables():
    now = timezone.now()
    snapshot = enable_manual_maintenance(
        message="Manual maintenance",
        expected_end_at=now + timedelta(minutes=10),
        context=AuditContext.system(),
        now=now,
    )
    assert snapshot.state == MaintenanceState.MAINTENANCE

    later = get_maintenance_snapshot(now=now + timedelta(hours=3))
    assert later.state == MaintenanceState.MAINTENANCE
    assert later.manual_expected_end_at == now + timedelta(minutes=10)

    disabled = disable_manual_maintenance(
        context=AuditContext.system(),
        now=now + timedelta(hours=3),
    )
    assert disabled.state == MaintenanceState.NORMAL


@pytest.mark.django_db
def test_manual_enable_requires_nonblank_bounded_message():
    sync_policy()
    admin = make_user("message-admin@example.edu")
    client = auth_client(admin, recent_mfa=True)

    blank = post_json(
        client,
        "/api/v1/platform/maintenance/enable",
        {"message": "   "},
    )
    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "invalid_maintenance_window"

    too_long = post_json(
        client,
        "/api/v1/platform/maintenance/enable",
        {"message": "x" * 501},
    )
    assert too_long.status_code == 422


@pytest.mark.django_db
def test_manual_enable_and_audit_are_atomic_and_audit_failure_rolls_back():
    now = timezone.now()
    snapshot = enable_manual_maintenance(
        message="Audited maintenance",
        expected_end_at=None,
        context=AuditContext.system(),
        now=now,
    )
    assert snapshot.state == MaintenanceState.MAINTENANCE
    assert AuditEvent.objects.filter(action="platform.maintenance.enabled").count() == 1

    disable_manual_maintenance(context=AuditContext.system(), now=now)
    with patch(
        "compass.platform_ops.services.record_event",
        side_effect=RuntimeError("synthetic audit failure"),
    ):
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            enable_manual_maintenance(
                message="Must roll back",
                expected_end_at=None,
                context=AuditContext.system(),
                now=now,
            )

    item = MaintenanceConfiguration.objects.get(pk=1)
    assert item.manual_enabled is False
    assert item.manual_message == ""


@pytest.mark.django_db
def test_schedule_validation_and_effective_timestamp_rules_need_no_celery():
    now = timezone.now()
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)

    with pytest.raises(InvalidMaintenanceWindow, match="scheduled end must be after"):
        schedule_maintenance(
            message="Bad order",
            starts_at=end,
            ends_at=start,
            context=AuditContext.system(),
            now=now,
        )
    with pytest.raises(InvalidMaintenanceWindow, match="scheduled start must be in the future"):
        schedule_maintenance(
            message="Past start",
            starts_at=now - timedelta(seconds=1),
            ends_at=end,
            context=AuditContext.system(),
            now=now,
        )

    scheduled = schedule_maintenance(
        message="Scheduled maintenance",
        starts_at=start,
        ends_at=end,
        context=AuditContext.system(),
        now=now,
    )
    assert scheduled.state == MaintenanceState.SCHEDULED
    assert derive_maintenance_snapshot(
        MaintenanceConfiguration.objects.get(pk=1),
        now=start,
    ).state == MaintenanceState.MAINTENANCE
    assert derive_maintenance_snapshot(
        MaintenanceConfiguration.objects.get(pk=1),
        now=end,
    ).state == MaintenanceState.NORMAL

    from config.celery import app

    assert "compass.platform_ops" not in " ".join(app.tasks.keys())


@pytest.mark.django_db
def test_manual_and_schedule_states_cannot_overlap_and_expired_schedule_can_be_replaced():
    now = timezone.now()
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    schedule_maintenance(
        message="Future schedule",
        starts_at=start,
        ends_at=end,
        context=AuditContext.system(),
        now=now,
    )

    with pytest.raises(MaintenanceScheduleConflict):
        enable_manual_maintenance(
            message="Conflicting manual",
            expected_end_at=None,
            context=AuditContext.system(),
            now=now,
        )

    cancel_maintenance_schedule(context=AuditContext.system(), now=now)
    enable_manual_maintenance(
        message="Manual",
        expected_end_at=None,
        context=AuditContext.system(),
        now=now,
    )
    with pytest.raises(MaintenanceScheduleConflict):
        schedule_maintenance(
            message="Conflicting schedule",
            starts_at=start,
            ends_at=end,
            context=AuditContext.system(),
            now=now,
        )
    disable_manual_maintenance(context=AuditContext.system(), now=now)

    item = MaintenanceConfiguration.objects.get(pk=1)
    item.scheduled_start_at = now - timedelta(hours=2)
    item.scheduled_end_at = now - timedelta(hours=1)
    item.scheduled_message = "Expired"
    item.save(
        update_fields=[
            "scheduled_start_at",
            "scheduled_end_at",
            "scheduled_message",
            "updated_at",
        ]
    )
    replacement = schedule_maintenance(
        message="Replacement",
        starts_at=now + timedelta(hours=3),
        ends_at=now + timedelta(hours=4),
        context=AuditContext.system(),
        now=now,
    )
    assert replacement.state == MaintenanceState.SCHEDULED
    assert replacement.message == "Replacement"


@pytest.mark.django_db
def test_schedule_cancellation_restores_normal_immediately_and_reads_do_not_clean_expired_rows():
    now = timezone.now()
    item = get_maintenance_configuration()
    item.scheduled_start_at = now - timedelta(minutes=10)
    item.scheduled_end_at = now + timedelta(minutes=20)
    item.scheduled_message = "Active schedule"
    item.save(
        update_fields=[
            "scheduled_start_at",
            "scheduled_end_at",
            "scheduled_message",
            "updated_at",
        ]
    )
    assert get_maintenance_snapshot(now=now).state == MaintenanceState.MAINTENANCE
    cancelled = cancel_maintenance_schedule(context=AuditContext.system(), now=now)
    assert cancelled.state == MaintenanceState.NORMAL

    item.refresh_from_db()
    item.scheduled_start_at = now - timedelta(hours=2)
    item.scheduled_end_at = now - timedelta(hours=1)
    item.scheduled_message = "Expired remains persisted"
    item.save(
        update_fields=[
            "scheduled_start_at",
            "scheduled_end_at",
            "scheduled_message",
            "updated_at",
        ]
    )
    before = (
        item.scheduled_start_at,
        item.scheduled_end_at,
        item.scheduled_message,
        item.updated_at,
    )
    assert get_maintenance_snapshot(now=now).state == MaintenanceState.NORMAL
    item.refresh_from_db()
    after = (
        item.scheduled_start_at,
        item.scheduled_end_at,
        item.scheduled_message,
        item.updated_at,
    )
    assert after == before


@pytest.mark.django_db(transaction=True)
def test_concurrent_manual_enable_mutations_serialize():
    get_maintenance_configuration()
    barrier = threading.Barrier(2)

    def worker(index: int):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                enable_manual_maintenance(
                    message=f"Concurrent {index}",
                    expected_end_at=None,
                    context=AuditContext.system(),
                )
                return "enabled"
            except MaintenanceAlreadyEnabled:
                return "conflict"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (1, 2)))

    assert sorted(results) == ["conflict", "enabled"]
    assert AuditEvent.objects.filter(action="platform.maintenance.enabled").count() == 1


@pytest.mark.django_db
def test_health_auth_platform_and_daily_webhook_bypass_before_maintenance_lookup(client):
    with patch(
        "compass.platform_ops.middleware.get_maintenance_snapshot",
        side_effect=AssertionError("maintenance DB lookup must be bypassed"),
    ) as lookup:
        live = client.get("/api/v1/health/live")
        ready = client.get("/api/v1/health/ready")
        auth = client.get("/api/v1/auth/csrf")
        platform = client.get("/api/v1/platform/maintenance")
        webhook = client.post(
            "/api/v1/integrations/daily/webhook",
            data=b"{}",
            content_type="application/json",
        )

    assert live.status_code == 200
    assert ready.status_code == 200
    assert auth.status_code == 200
    assert platform.status_code == 401
    assert webhook.status_code != 503
    lookup.assert_not_called()


@pytest.mark.django_db
def test_active_manual_maintenance_blocks_ordinary_api_with_standard_envelope_and_request_id():
    item = get_maintenance_configuration()
    item.manual_enabled = True
    item.manual_message = "<b>Plain maintenance text</b>"
    item.manual_expected_end_at = timezone.now() + timedelta(minutes=30)
    item.save(
        update_fields=[
            "manual_enabled",
            "manual_message",
            "manual_expected_end_at",
            "updated_at",
        ]
    )

    response = Client().get("/api/v1/me/activity")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "maintenance_mode"
    assert body["error"]["message"] == "<b>Plain maintenance text</b>"
    assert body["error"]["details"]["source"] == "MANUAL"
    assert body["error"]["request_id"] == response["X-Request-ID"]
    assert "Retry-After" not in response


@pytest.mark.django_db
def test_scheduled_middleware_blocks_only_during_window_and_sets_retry_after():
    now = timezone.now()
    item = get_maintenance_configuration()
    item.scheduled_start_at = now + timedelta(minutes=30)
    item.scheduled_end_at = now + timedelta(hours=1)
    item.scheduled_message = "Scheduled maintenance"
    item.save(
        update_fields=[
            "scheduled_start_at",
            "scheduled_end_at",
            "scheduled_message",
            "updated_at",
        ]
    )

    with patch("compass.platform_ops.middleware.timezone.now", return_value=now):
        future = Client().get("/api/v1/me/activity")
    assert future.status_code == 401

    active_now = now + timedelta(minutes=45)
    with patch("compass.platform_ops.middleware.timezone.now", return_value=active_now):
        active = Client().get("/api/v1/me/activity")
    assert active.status_code == 503
    assert active.json()["error"]["details"]["source"] == "SCHEDULED"
    assert int(active["Retry-After"]) == 15 * 60

    expired_now = now + timedelta(hours=2)
    with patch("compass.platform_ops.middleware.timezone.now", return_value=expired_now):
        expired = Client().get("/api/v1/me/activity")
    assert expired.status_code == 401


@pytest.mark.django_db
def test_platform_recovery_routes_remain_capability_authorized_during_active_maintenance():
    sync_policy()
    admin = make_user("recovery-admin@example.edu")
    item = get_maintenance_configuration()
    item.manual_enabled = True
    item.manual_message = "Recovery test"
    item.save(update_fields=["manual_enabled", "manual_message", "updated_at"])

    anonymous = Client().get("/api/v1/platform/maintenance")
    assert anonymous.status_code == 401

    admin_client = auth_client(admin, recent_mfa=True)
    status = admin_client.get("/api/v1/platform/maintenance")
    assert status.status_code == 200
    disabled = admin_client.post(
        "/api/v1/platform/maintenance/disable",
        **csrf(admin_client),
    )
    assert disabled.status_code == 200
    assert disabled.json()["state"] == "NORMAL"
