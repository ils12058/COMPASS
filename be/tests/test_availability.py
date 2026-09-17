from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.models import (
    OfficeAvailabilityWindow,
    OfficeUnavailability,
    ProviderAvailabilityWindow,
    ProviderUnavailability,
)
from compass.availability.services import (
    AvailabilityNotApplicable,
    InvalidAvailabilityInput,
    compute_base_availability,
    create_office_exception,
    create_provider_exception,
    normalize_weekly_windows,
    remove_provider_exception,
    replace_office_weekly,
    replace_provider_weekly,
)
from compass.service_catalog.services import create_service, set_service_active


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name="User",
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def active_service(
    actor: User,
    *,
    code: str = "SYNTHETIC_SERVICE",
    duration: int | None = 60,
    delivery_modes=None,
    provider_roles=None,
):
    service = create_service(
        code=code,
        name=code.replace("_", " ").title(),
        appointment_policy="OPTIONAL" if duration is not None else "NONE",
        default_duration_minutes=duration,
        delivery_modes=delivery_modes or ["IN_PERSON", "ONLINE"],
        provider_roles=provider_roles or ["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def weekly(
    weekday: str = "MONDAY",
    start: time = time(8),
    end: time = time(17),
    scope: str = "ALL",
) -> dict[str, object]:
    return {
        "weekday": weekday,
        "start_time": start,
        "end_time": end,
        "mode_scope": scope,
    }


@pytest.mark.django_db
def test_availability_capability_policy_matches_role_and_designation_boundaries():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert admin.has_capability("availability.view")
    assert admin.has_capability("availability.manage")
    assert not admin.has_capability("availability.manage_self")
    assert counselor.has_capability("availability.view")
    assert counselor.has_capability("availability.manage_self")
    assert not counselor.has_capability("availability.manage")
    assert gss.has_capability("availability.view")
    assert not gss.has_capability("availability.manage_self")
    assert not gss.has_capability("availability.manage")
    assert student.has_capability("availability.view")
    assert not student.has_capability("availability.manage_self")
    assert not student.has_capability("availability.manage")
    assert head.has_capability("availability.manage_self")
    assert head.has_capability("availability.manage")

    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="availability.manage"),
        effect="REVOKE",
        reason="separation",
    )
    assert not head.has_capability("availability.manage")
    assert head.has_capability("availability.manage_self")


@pytest.mark.django_db
def test_weekly_validation_rejects_invalid_duplicate_and_semantic_overlap_but_allows_adjacency():
    adjacent = normalize_weekly_windows(
        [
            weekly(start=time(8), end=time(9), scope="ALL"),
            weekly(start=time(9), end=time(10), scope="ALL"),
        ]
    )
    assert len(adjacent) == 2

    with pytest.raises(InvalidAvailabilityInput, match="earlier"):
        normalize_weekly_windows([weekly(start=time(9), end=time(9))])
    with pytest.raises(InvalidAvailabilityInput, match="earlier"):
        normalize_weekly_windows([weekly(start=time(10), end=time(9))])
    with pytest.raises(InvalidAvailabilityInput, match="exact duplicates"):
        normalize_weekly_windows([weekly(), weekly()])
    with pytest.raises(InvalidAvailabilityInput, match="overlap"):
        normalize_weekly_windows(
            [
                weekly(start=time(8), end=time(12), scope="ALL"),
                weekly(start=time(10), end=time(11), scope="ONLINE"),
            ]
        )

    independent_modes = normalize_weekly_windows(
        [
            weekly(start=time(8), end=time(12), scope="IN_PERSON"),
            weekly(start=time(8), end=time(12), scope="ONLINE"),
        ]
    )
    assert len(independent_modes) == 2


@pytest.mark.django_db
def test_database_constraints_reject_bad_or_duplicate_weekly_rows():
    sync_policy()
    provider = make_user("provider@example.edu", "COUNSELOR")
    OfficeAvailabilityWindow.objects.create(
        weekday="MONDAY", start_time=time(8), end_time=time(12), mode_scope="ALL"
    )
    ProviderAvailabilityWindow.objects.create(
        provider=provider,
        weekday="MONDAY",
        start_time=time(8),
        end_time=time(12),
        mode_scope="ALL",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OfficeAvailabilityWindow.objects.create(
                weekday="MONDAY", start_time=time(8), end_time=time(12), mode_scope="ALL"
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProviderAvailabilityWindow.objects.create(
                provider=provider,
                weekday="MONDAY",
                start_time=time(12),
                end_time=time(12),
                mode_scope="ALL",
            )


@pytest.mark.django_db
def test_provider_configuration_accepts_operational_roles_and_allows_inactive_cleanup_only():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("c@example.edu", "COUNSELOR")
    gss = make_user("g@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("s@example.edu", "STUDENT")
    other_admin = make_user("a2@example.edu", "IT_ADMIN")
    inactive = make_user("inactive@example.edu", "COUNSELOR", active=False)

    assert (
        len(
            replace_provider_weekly(
                provider_id=counselor.pk, windows=[weekly()], context=context(actor)
            )
        )
        == 1
    )
    assert (
        len(replace_provider_weekly(provider_id=gss.pk, windows=[weekly()], context=context(actor)))
        == 1
    )
    for provider in (student, other_admin, inactive):
        with pytest.raises(AvailabilityNotApplicable):
            replace_provider_weekly(
                provider_id=provider.pk, windows=[weekly()], context=context(actor)
            )

    ProviderAvailabilityWindow.objects.create(
        provider=inactive,
        weekday="MONDAY",
        start_time=time(8),
        end_time=time(12),
        mode_scope="ALL",
    )
    cleaned = replace_provider_weekly(provider_id=inactive.pk, windows=[], context=context(actor))
    assert cleaned == ()


@pytest.mark.django_db
def test_weekly_replacement_is_idempotent_and_emits_one_meaningful_audit_event():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")

    replace_office_weekly(windows=[weekly()], context=context(actor))
    replace_office_weekly(windows=[weekly()], context=context(actor))
    assert AuditEvent.objects.filter(action="availability.office_schedule.updated").count() == 1

    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    event = AuditEvent.objects.get(action="availability.provider_schedule.updated")
    assert event.target_type == "accounts.user"
    assert event.target_id == str(provider.pk)
    assert event.metadata == {"provider_id": str(provider.pk), "window_count": 1}


@pytest.mark.django_db
def test_exception_validation_requires_aware_ordered_ranges_and_bounded_reason():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    aware_start = datetime(2026, 9, 21, 8, tzinfo=ZoneInfo("Asia/Manila"))
    aware_end = datetime(2026, 9, 21, 9, tzinfo=ZoneInfo("Asia/Manila"))

    with pytest.raises(InvalidAvailabilityInput, match="timezone-aware"):
        create_office_exception(
            starts_at=datetime(2026, 9, 21, 8),
            ends_at=datetime(2026, 9, 21, 9),
            mode_scope="ALL",
            context=context(actor),
        )
    with pytest.raises(InvalidAvailabilityInput, match="earlier"):
        create_provider_exception(
            provider_id=provider.pk,
            starts_at=aware_end,
            ends_at=aware_start,
            mode_scope="ALL",
            context=context(actor),
        )
    with pytest.raises(InvalidAvailabilityInput, match="255"):
        create_office_exception(
            starts_at=aware_start,
            ends_at=aware_end,
            mode_scope="ALL",
            reason="x" * 256,
            context=context(actor),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_effective_availability_intersects_office_provider_and_subtracts_provider_exception():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    replace_office_weekly(windows=[weekly(start=time(9), end=time(17))], context=context(actor))
    create_provider_exception(
        provider_id=provider.pk,
        starts_at=datetime(2026, 9, 21, 12, tzinfo=ZoneInfo("Asia/Manila")),
        ends_at=datetime(2026, 9, 21, 13, tzinfo=ZoneInfo("Asia/Manila")),
        mode_scope="ALL",
        context=context(actor),
    )

    result = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode="IN_PERSON",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 22),
    )
    assert result.timezone_name == "Asia/Manila"
    assert [(item.starts_at.hour, item.ends_at.hour) for item in result.windows] == [
        (9, 12),
        (13, 17),
    ]
    assert all(item.starts_at.utcoffset() == timedelta(hours=8) for item in result.windows)


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_mode_specific_office_exception_only_subtracts_matching_mode():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    replace_office_weekly(windows=[weekly()], context=context(actor))
    create_office_exception(
        starts_at=datetime(2026, 9, 21, 13, tzinfo=ZoneInfo("Asia/Manila")),
        ends_at=datetime(2026, 9, 21, 17, tzinfo=ZoneInfo("Asia/Manila")),
        mode_scope="IN_PERSON",
        context=context(actor),
    )

    in_person = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode="IN_PERSON",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 22),
    )
    online = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode="ONLINE",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 22),
    )
    assert [(item.starts_at.hour, item.ends_at.hour) for item in in_person.windows] == [(8, 13)]
    assert [(item.starts_at.hour, item.ends_at.hour) for item in online.windows] == [(8, 17)]


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_service_default_duration_filters_short_windows_without_generating_slots():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, duration=60)
    short = [weekly(start=time(10), end=time(10, 30))]
    replace_provider_weekly(provider_id=provider.pk, windows=short, context=context(actor))
    replace_office_weekly(windows=short, context=context(actor))
    result = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode="IN_PERSON",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 22),
    )
    assert result.windows == ()

    long_window = [weekly(start=time(10), end=time(11, 30))]
    replace_provider_weekly(provider_id=provider.pk, windows=long_window, context=context(actor))
    replace_office_weekly(windows=long_window, context=context(actor))
    result = compute_base_availability(
        provider_id=provider.pk,
        service_id=service.pk,
        delivery_mode="IN_PERSON",
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 22),
    )
    assert len(result.windows) == 1
    assert result.windows[0].ends_at - result.windows[0].starts_at == timedelta(minutes=90)


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_effective_query_rejects_inactive_service_unsupported_mode_role_and_large_horizon():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("c@example.edu", "COUNSELOR")
    gss = make_user("g@example.edu", "GUIDANCE_SERVICES_STAFF")
    inactive_service = create_service(
        code="INACTIVE",
        name="Inactive",
        appointment_policy="NONE",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    with pytest.raises(AvailabilityNotApplicable, match="inactive"):
        compute_base_availability(
            provider_id=counselor.pk,
            service_id=inactive_service.pk,
            delivery_mode="IN_PERSON",
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
        )

    service = active_service(
        actor,
        code="IN_PERSON_ONLY",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
    )
    with pytest.raises(AvailabilityNotApplicable, match="delivery mode"):
        compute_base_availability(
            provider_id=counselor.pk,
            service_id=service.pk,
            delivery_mode="ONLINE",
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
        )
    with pytest.raises(AvailabilityNotApplicable, match="provider role"):
        compute_base_availability(
            provider_id=gss.pk,
            service_id=service.pk,
            delivery_mode="IN_PERSON",
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
        )
    with pytest.raises(InvalidAvailabilityInput, match="31"):
        compute_base_availability(
            provider_id=counselor.pk,
            service_id=service.pk,
            delivery_mode="IN_PERSON",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 10, 3),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_inactive_provider_keeps_configuration_but_has_no_effective_availability():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor)
    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    replace_office_weekly(windows=[weekly()], context=context(actor))
    provider.is_active = False
    provider.save(update_fields=["is_active", "updated_at"])

    assert ProviderAvailabilityWindow.objects.filter(provider=provider).exists()
    with pytest.raises(AvailabilityNotApplicable):
        compute_base_availability(
            provider_id=provider.pk,
            service_id=service.pk,
            delivery_mode="IN_PERSON",
            start_date=date(2026, 9, 21),
            end_date=date(2026, 9, 22),
        )


@pytest.mark.django_db
def test_provider_exception_cleanup_can_remove_inactive_provider_data():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    item = create_provider_exception(
        provider_id=provider.pk,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(hours=1),
        mode_scope="ALL",
        context=context(actor),
    )
    provider.is_active = False
    provider.save(update_fields=["is_active", "updated_at"])
    assert remove_provider_exception(
        exception_id=item.pk, provider_id=provider.pk, context=context(actor)
    )
    assert not ProviderUnavailability.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_self_service_uses_authenticated_counselor_and_does_not_require_recent_mfa():
    sync_policy()
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    client = auth_client(counselor, recent_mfa=False)
    response = client.put(
        "/api/v1/availability/me/weekly",
        data=json.dumps(
            {
                "windows": [
                    {
                        "weekday": "MONDAY",
                        "start_time": "08:00",
                        "end_time": "12:00",
                        "mode_scope": "ALL",
                    }
                ]
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 200
    assert response.json()["provider_id"] == str(counselor.pk)
    assert ProviderAvailabilityWindow.objects.filter(provider=counselor).count() == 1

    own = client.get("/api/v1/availability/me/weekly")
    assert own.status_code == 200
    assert len(own.json()["windows"]) == 1


@pytest.mark.django_db
def test_gss_and_student_cannot_use_counselor_self_mutation_and_manage_self_revoke_wins():
    sync_policy()
    for role, email in [("GUIDANCE_SERVICES_STAFF", "g@example.edu"), ("STUDENT", "s@example.edu")]:
        user = make_user(email, role)
        client = auth_client(user)
        response = client.put(
            "/api/v1/availability/me/weekly",
            data=json.dumps({"windows": []}),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 403

    counselor = make_user("c@example.edu", "COUNSELOR")
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code="availability.manage_self"),
        effect="REVOKE",
        reason="separation",
    )
    client = auth_client(counselor)
    denied = client.put(
        "/api/v1/availability/me/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_head_manage_capability_can_still_self_manage_when_manage_self_is_revoked():
    sync_policy()
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="availability.manage_self"),
        effect="REVOKE",
        reason="use administrative authority",
    )
    client = auth_client(head, recent_mfa=False)
    response = client.put(
        "/api/v1/availability/me/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_administrative_mutation_requires_manage_and_recent_mfa():
    sync_policy()
    provider = make_user("provider@example.edu", "COUNSELOR")
    counselor = make_user("ordinary@example.edu", "COUNSELOR")
    counselor_client = auth_client(counselor, recent_mfa=True)
    denied = counselor_client.put(
        f"/api/v1/availability/providers/{provider.pk}/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert denied.status_code == 403

    admin = make_user("admin@example.edu", "IT_ADMIN")
    stale = auth_client(admin, recent_mfa=False)
    stale_response = stale.put(
        "/api/v1/availability/office/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(stale),
    )
    assert stale_response.status_code == 403
    assert stale_response.json()["error"]["code"] == "recent_mfa_required"

    recent = auth_client(admin, recent_mfa=True)
    okay = recent.put(
        "/api/v1/availability/office/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(recent),
    )
    assert okay.status_code == 200


@pytest.mark.django_db
def test_self_exception_delete_cannot_target_another_provider_and_reason_is_not_audit_metadata():
    sync_policy()
    a = make_user("a@example.edu", "COUNSELOR")
    b = make_user("b@example.edu", "COUNSELOR")
    item = create_provider_exception(
        provider_id=b.pk,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(hours=1),
        mode_scope="ALL",
        reason="Internal operational note",
        context=context(b),
    )
    client = auth_client(a)
    response = client.delete(
        f"/api/v1/availability/me/exceptions/{item.pk}",
        **csrf(client),
    )
    assert response.status_code == 404
    assert ProviderUnavailability.objects.filter(pk=item.pk).exists()
    event = AuditEvent.objects.get(
        action="availability.provider_exception.created", target_id=str(item.pk)
    )
    assert "reason" not in event.metadata
    assert "Internal operational note" not in str(event.metadata)


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_student_can_read_effective_availability_but_not_raw_configuration_or_reasons():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = active_service(actor)
    replace_provider_weekly(provider_id=provider.pk, windows=[weekly()], context=context(actor))
    replace_office_weekly(windows=[weekly()], context=context(actor))
    create_provider_exception(
        provider_id=provider.pk,
        starts_at=datetime(2026, 9, 21, 12, tzinfo=ZoneInfo("Asia/Manila")),
        ends_at=datetime(2026, 9, 21, 13, tzinfo=ZoneInfo("Asia/Manila")),
        mode_scope="ALL",
        reason="Private operational note",
        context=context(actor),
    )
    client = auth_client(student)
    effective = client.get(
        f"/api/v1/availability/providers/{provider.pk}/effective",
        {
            "service_id": str(service.pk),
            "delivery_mode": "IN_PERSON",
            "start_date": "2026-09-21",
            "end_date": "2026-09-22",
        },
    )
    assert effective.status_code == 200
    body = effective.json()
    assert body["timezone"] == "Asia/Manila"
    assert "reason" not in json.dumps(body).lower()
    assert "Private operational note" not in json.dumps(body)
    assert client.get(f"/api/v1/availability/providers/{provider.pk}/weekly").status_code == 403
    assert client.get("/api/v1/availability/office/exceptions").status_code == 403


@pytest.mark.django_db
def test_head_can_manage_office_and_other_provider_with_recent_mfa():
    sync_policy()
    head = make_user("head@example.edu", "COUNSELOR")
    provider = make_user("provider@example.edu", "GUIDANCE_SERVICES_STAFF")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    client = auth_client(head, recent_mfa=True)
    office = client.put(
        "/api/v1/availability/office/weekly",
        data=json.dumps({"windows": []}),
        content_type="application/json",
        **csrf(client),
    )
    provider_response = client.put(
        f"/api/v1/availability/providers/{provider.pk}/weekly",
        data=json.dumps(
            {
                "windows": [
                    {
                        "weekday": "MONDAY",
                        "start_time": "08:00",
                        "end_time": "12:00",
                        "mode_scope": "ALL",
                    }
                ]
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert office.status_code == 200
    assert provider_response.status_code == 200
    assert ProviderAvailabilityWindow.objects.filter(provider=provider).count() == 1


@pytest.mark.django_db
def test_gss_schedule_is_independent_and_not_copied_from_counselor():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("c@example.edu", "COUNSELOR")
    gss = make_user("g@example.edu", "GUIDANCE_SERVICES_STAFF")
    replace_provider_weekly(
        provider_id=counselor.pk,
        windows=[weekly(start=time(8), end=time(17))],
        context=context(actor),
    )
    replace_provider_weekly(
        provider_id=gss.pk,
        windows=[weekly(start=time(8), end=time(12))],
        context=context(actor),
    )
    counselor_window = ProviderAvailabilityWindow.objects.get(provider=counselor)
    gss_window = ProviderAvailabilityWindow.objects.get(provider=gss)
    assert counselor_window.end_time == time(17)
    assert gss_window.end_time == time(12)


@pytest.mark.django_db
def test_exception_database_constraints_reject_nonpositive_ranges():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    provider = make_user("provider@example.edu", "COUNSELOR")
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OfficeUnavailability.objects.create(
                starts_at=now,
                ends_at=now,
                mode_scope="ALL",
                created_by=actor,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProviderUnavailability.objects.create(
                provider=provider,
                starts_at=now + timedelta(hours=1),
                ends_at=now,
                mode_scope="ALL",
                created_by=actor,
            )
