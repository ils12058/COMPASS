from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
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
from compass.organization.models import Campus, College, CounselorResponsibility
from compass.service_catalog.models import (
    Service,
    ServiceCounselorProvider,
    ServiceDeliveryMode,
    ServiceProviderRole,
)
from compass.service_catalog.services import (
    InvalidServiceCatalogInput,
    ServiceCatalogConflict,
    activation_blockers,
    create_service,
    service_counselor_eligible,
    service_eligible_counselors,
    service_supports_delivery_mode,
    set_service_active,
    update_service,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Test",
        last_name=email.split("@")[0].title(),
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User, *, recent_mfa: bool = True) -> Client:
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


def configured_service(actor: User, *, active: bool = False, **overrides):
    values = {
        "code": "SYNTHETIC_SERVICE",
        "name": "Synthetic Service",
        "description": "Synthetic test configuration.",
        "appointment_booking_enabled": True,
        "default_appointment_duration_minutes": 60,
        "delivery_modes": ["IN_PERSON", "ONLINE"],
    }
    values.update(overrides)
    service = create_service(**values, context=context(actor))
    if active:
        service = set_service_active(service_id=service.pk, is_active=True, context=context(actor))
    return service


@pytest.mark.django_db
def test_policy_grants_service_catalog_capabilities_and_preserves_overrides():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    staff = make_user("staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    head = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    dpo = Designation.objects.get(code="DPO")
    UserDesignation.objects.create(user=counselor, designation=head)
    UserDesignation.objects.create(user=student, designation=dpo)

    assert admin.has_capability("services.catalog.view")
    assert admin.has_capability("services.manage")
    assert counselor.has_capability("services.catalog.view")
    assert counselor.has_capability("services.manage")
    assert staff.has_capability("services.catalog.view")
    assert not staff.has_capability("services.manage")
    assert student.has_capability("services.catalog.view")
    assert not student.has_capability("services.manage")

    manage = Capability.objects.get(code="services.manage")
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=manage,
        effect="REVOKE",
        reason="separation",
    )
    assert not counselor.has_capability("services.manage")

    UserCapabilityOverride.objects.create(
        user=staff,
        capability=manage,
        effect="GRANT",
        reason="approved catalog duty",
    )
    assert staff.has_capability("services.manage")


@pytest.mark.django_db
def test_create_normalizes_code_uses_uuid_and_starts_inactive_with_all_counselors():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = create_service(
        code="  synthetic_service  ",
        name=" Synthetic Service ",
        context=context(actor),
    )

    assert isinstance(service.pk, uuid.UUID)
    assert service.code == "SYNTHETIC_SERVICE"
    assert service.name == "Synthetic Service"
    assert not service.is_active
    assert service.appointment_booking_enabled is False
    assert service.default_appointment_duration_minutes is None
    assert service.cancellation_cutoff_minutes is None
    assert service.provider_coverage == "ALL_COUNSELORS"
    assert list(service.delivery_mode_assignments.all()) == []
    assert not ServiceProviderRole.objects.filter(service=service).exists()
    assert activation_blockers(service) == ("DELIVERY_MODE_MISSING",)


@pytest.mark.django_db
def test_duplicate_code_is_a_conflict_and_code_is_not_updateable():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = create_service(code="SYNTHETIC", name="Synthetic", context=context(actor))
    with pytest.raises(ServiceCatalogConflict, match="already exists"):
        create_service(code=" synthetic ", name="Other", context=context(actor))
    with pytest.raises(InvalidServiceCatalogInput, match="unsupported fields"):
        update_service(
            service_id=service.pk,
            changes={"code": "RENAMED"},
            context=context(actor),
        )


@pytest.mark.django_db
def test_booking_settings_are_appointment_only_and_bounded():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    for duration in (0, -1, 481):
        with pytest.raises(InvalidServiceCatalogInput, match="between 1 and 480"):
            create_service(
                code=f"BAD_DURATION_{abs(duration)}",
                name="Bad duration",
                appointment_booking_enabled=True,
                default_appointment_duration_minutes=duration,
                context=context(actor),
            )
    with pytest.raises(InvalidServiceCatalogInput, match="non-negative"):
        configured_service(actor, code="NEGATIVE_CUTOFF", cancellation_cutoff_minutes=-1)

    # Booking-off Services cannot carry Appointment-only settings.
    for setting, value in (
        ("default_appointment_duration_minutes", 60),
        ("cancellation_cutoff_minutes", 30),
        ("requires_current_inventory", True),
    ):
        with pytest.raises(ServiceCatalogConflict, match="Appointment booking"):
            create_service(
                code=f"NO_BOOKING_{setting.upper()}",
                name="No booking",
                appointment_booking_enabled=False,
                context=context(actor),
                **{setting: value},
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Service.objects.create(
                code="RAW_NO_BOOKING",
                name="Raw",
                appointment_booking_enabled=False,
                default_appointment_duration_minutes=60,
            )


@pytest.mark.django_db
def test_turning_booking_off_clears_appointment_settings_atomically():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = configured_service(
        actor,
        active=True,
        cancellation_cutoff_minutes=30,
        requires_current_inventory=True,
    )
    with pytest.raises(ServiceCatalogConflict, match="duration"):
        update_service(
            service_id=service.pk,
            changes={"default_appointment_duration_minutes": None},
            context=context(actor),
        )
    with pytest.raises(ServiceCatalogConflict, match="Appointment booking"):
        update_service(
            service_id=service.pk,
            changes={"appointment_booking_enabled": False, "cancellation_cutoff_minutes": 15},
            context=context(actor),
        )

    changed = update_service(
        service_id=service.pk,
        changes={"appointment_booking_enabled": False},
        context=context(actor),
    )
    assert changed.is_active
    assert changed.appointment_booking_enabled is False
    assert changed.default_appointment_duration_minutes is None
    assert changed.cancellation_cutoff_minutes is None
    assert changed.requires_current_inventory is False
    event = AuditEvent.objects.filter(action="service.updated").latest("occurred_at")
    assert set(event.metadata["changed_fields"]) == {
        "appointment_booking_enabled",
        "booking_pathways",
        "default_appointment_duration_minutes",
        "cancellation_cutoff_minutes",
        "requires_current_inventory",
    }


@pytest.mark.django_db
def test_delivery_modes_and_selected_counselors_are_closed_and_validated():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    staff = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    inactive = make_user("inactive@example.edu", "COUNSELOR", active=False)
    with pytest.raises(InvalidServiceCatalogInput, match="delivery_modes"):
        create_service(
            code="BAD_MODE", name="Bad mode", delivery_modes=["PHONE"], context=context(actor)
        )
    with pytest.raises(InvalidServiceCatalogInput, match="duplicates"):
        create_service(
            code="DUP_MODE",
            name="Duplicate mode",
            delivery_modes=["ONLINE", "ONLINE"],
            context=context(actor),
        )
    with pytest.raises(InvalidServiceCatalogInput, match="provider_coverage"):
        create_service(
            code="BAD_COVERAGE", name="Bad", provider_coverage="SOME", context=context(actor)
        )
    selected = {"provider_coverage": "SELECTED_COUNSELORS"}
    with pytest.raises(ServiceCatalogConflict, match="Only Counselors"):
        create_service(
            code="GSS_PROVIDER",
            name="GSS provider",
            selected_counselor_ids=[staff.pk],
            context=context(actor),
            **selected,
        )
    with pytest.raises(ServiceCatalogConflict, match="inactive"):
        create_service(
            code="INACTIVE_PROVIDER",
            name="Inactive provider",
            selected_counselor_ids=[inactive.pk],
            context=context(actor),
            **selected,
        )
    with pytest.raises(InvalidServiceCatalogInput, match="not found"):
        create_service(
            code="UNKNOWN_PROVIDER",
            name="Unknown provider",
            selected_counselor_ids=[uuid.uuid4()],
            context=context(actor),
            **selected,
        )
    with pytest.raises(InvalidServiceCatalogInput, match="duplicates"):
        create_service(
            code="DUP_PROVIDER",
            name="Duplicate provider",
            selected_counselor_ids=[counselor.pk, counselor.pk],
            context=context(actor),
            **selected,
        )
    with pytest.raises(ServiceCatalogConflict, match="SELECTED_COUNSELORS"):
        create_service(
            code="ALL_WITH_SELECTION",
            name="All with selection",
            selected_counselor_ids=[counselor.pk],
            context=context(actor),
        )


@pytest.mark.django_db
def test_database_prevents_duplicate_mode_and_selected_counselor_rows():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    service = configured_service(
        actor, provider_coverage="SELECTED_COUNSELORS", selected_counselor_ids=[counselor.pk]
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServiceDeliveryMode.objects.create(service=service, mode="IN_PERSON")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServiceCounselorProvider.objects.create(service=service, counselor=counselor)


@pytest.mark.django_db
def test_activation_requires_modes_duration_when_booking_and_selected_counselors():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    incomplete = create_service(code="INCOMPLETE", name="Incomplete", context=context(actor))
    with pytest.raises(ServiceCatalogConflict, match="delivery mode"):
        set_service_active(service_id=incomplete.pk, is_active=True, context=context(actor))

    no_duration = create_service(
        code="BOOKING_NO_DURATION",
        name="Booking no duration",
        appointment_booking_enabled=True,
        delivery_modes=["IN_PERSON"],
        context=context(actor),
    )
    assert activation_blockers(no_duration) == ("APPOINTMENT_DURATION_MISSING",)
    with pytest.raises(ServiceCatalogConflict, match="duration"):
        set_service_active(service_id=no_duration.pk, is_active=True, context=context(actor))

    no_counselors = create_service(
        code="SELECTED_EMPTY",
        name="Selected empty",
        delivery_modes=["IN_PERSON"],
        provider_coverage="SELECTED_COUNSELORS",
        context=context(actor),
    )
    assert activation_blockers(no_counselors) == ("SELECTED_COUNSELORS_MISSING",)
    with pytest.raises(ServiceCatalogConflict, match="selected Counselor"):
        set_service_active(service_id=no_counselors.pk, is_active=True, context=context(actor))
    update_service(
        service_id=no_counselors.pk,
        changes={"selected_counselor_ids": [counselor.pk]},
        context=context(actor),
    )
    assert set_service_active(
        service_id=no_counselors.pk, is_active=True, context=context(actor)
    ).is_active

    # ALL_COUNSELORS needs no rows, and a booking-off Service needs no duration.
    walk_in_only = create_service(
        code="NO_BOOKING",
        name="No booking",
        delivery_modes=["IN_PERSON"],
        context=context(actor),
    )
    assert set_service_active(
        service_id=walk_in_only.pk, is_active=True, context=context(actor)
    ).is_active

    with pytest.raises(ServiceCatalogConflict, match="selected Counselor"):
        update_service(
            service_id=no_counselors.pk,
            changes={"selected_counselor_ids": []},
            context=context(actor),
        )


@pytest.mark.django_db
def test_enable_disable_and_equivalent_updates_are_idempotent_without_fake_audit():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = configured_service(actor)
    service = set_service_active(service_id=service.pk, is_active=True, context=context(actor))
    enabled_count = AuditEvent.objects.filter(action="service.enabled").count()
    set_service_active(service_id=service.pk, is_active=True, context=context(actor))
    assert AuditEvent.objects.filter(action="service.enabled").count() == enabled_count

    updated_count = AuditEvent.objects.filter(action="service.updated").count()
    update_service(
        service_id=service.pk,
        changes={
            "delivery_modes": ["ONLINE", "IN_PERSON"],
            "provider_coverage": "ALL_COUNSELORS",
            "selected_counselor_ids": [],
        },
        context=context(actor),
    )
    assert AuditEvent.objects.filter(action="service.updated").count() == updated_count

    set_service_active(service_id=service.pk, is_active=False, context=context(actor))
    disabled_count = AuditEvent.objects.filter(action="service.disabled").count()
    set_service_active(service_id=service.pk, is_active=False, context=context(actor))
    assert AuditEvent.objects.filter(action="service.disabled").count() == disabled_count


@pytest.mark.django_db
def test_counselor_qualification_follows_coverage_not_college_or_legacy_roles():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    selected = make_user("selected@example.edu", "COUNSELOR")
    unselected = make_user("unselected@example.edu", "COUNSELOR")
    staff = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("student@example.edu", "STUDENT")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    campus = Campus.objects.create(code="QUAL", name="Qualification Campus")
    college = College.objects.create(campus=campus, code="QUAL-COL", name="Qualification College")
    CounselorResponsibility.objects.create(college=college, counselor=unselected)

    everyone = configured_service(actor, code="EVERYONE", active=True)
    # Historical GSS provider rows survive but never grant eligibility.
    ServiceProviderRole.objects.create(
        service=everyone, role=Role.objects.get(code="GUIDANCE_SERVICES_STAFF")
    )
    assert service_counselor_eligible(everyone, selected)
    assert service_counselor_eligible(everyone, unselected)
    assert service_counselor_eligible(everyone, head)
    assert not service_counselor_eligible(everyone, staff)
    assert not service_counselor_eligible(everyone, student)
    assert service_supports_delivery_mode(everyone, "ONLINE")
    assert not service_supports_delivery_mode(everyone, "FAX")

    testing = configured_service(
        actor,
        code="TESTING",
        active=True,
        provider_coverage="SELECTED_COUNSELORS",
        selected_counselor_ids=[selected.pk, head.pk],
    )
    assert service_counselor_eligible(testing, selected)
    assert service_counselor_eligible(testing, head)
    # College responsibility neither grants nor restricts qualification.
    assert not service_counselor_eligible(testing, unselected)
    assert set(service_eligible_counselors(testing)) == {selected, head}

    # A selected Counselor who becomes inactive stays selected but is no longer eligible, and
    # coverage is never widened automatically.
    selected.is_active = False
    selected.save(update_fields=["is_active", "updated_at"])
    assert not service_counselor_eligible(testing, selected)
    assert set(service_eligible_counselors(testing)) == {head}
    assert ServiceCounselorProvider.objects.filter(service=testing, counselor=selected).exists()
    testing.refresh_from_db()
    assert testing.provider_coverage == "SELECTED_COUNSELORS"

    # Keeping an already-selected inactive Counselor is allowed; adding one is not.
    renamed = update_service(
        service_id=testing.pk,
        changes={"name": "Psychological Testing", "selected_counselor_ids": [selected.pk, head.pk]},
        context=context(actor),
    )
    assert renamed.name == "Psychological Testing"


@pytest.mark.django_db
def test_provider_management_reads_are_manager_only_and_narrow():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    alpha = make_user("alpha@example.edu", "COUNSELOR")
    make_user("beta@example.edu", "COUNSELOR")
    make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    make_user("inactive@example.edu", "COUNSELOR", active=False)
    student = make_user("student@example.edu", "STUDENT")
    service = configured_service(
        admin, provider_coverage="SELECTED_COUNSELORS", selected_counselor_ids=[alpha.pk]
    )

    client = auth_client(admin)
    candidates = client.get("/api/v1/services/provider-candidates")
    assert candidates.status_code == 200
    names = [row["display_name"] for row in candidates.json()["items"]]
    assert names == ["Test Alpha", "Test Beta"]
    assert set(candidates.json()["items"][0]) == {"id", "display_name"}
    assert [
        row["display_name"]
        for row in client.get("/api/v1/services/provider-candidates", {"search": "bet"}).json()[
            "items"
        ]
    ] == ["Test Beta"]

    providers = client.get(f"/api/v1/services/{service.pk}/providers")
    assert providers.status_code == 200
    assert providers.json() == {
        "provider_coverage": "SELECTED_COUNSELORS",
        "counselors": [{"id": str(alpha.pk), "display_name": "Test Alpha", "is_active": True}],
    }

    student_client = auth_client(student)
    assert student_client.get("/api/v1/services/provider-candidates").status_code == 403
    assert student_client.get(f"/api/v1/services/{service.pk}/providers").status_code == 403


@pytest.mark.django_db
def test_student_can_read_only_active_catalog_and_cannot_manage():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    active_service = configured_service(actor, active=True)
    inactive_service = create_service(
        code="DRAFT_SERVICE", name="Draft Service", context=context(actor)
    )
    student = make_user("student@example.edu", "STUDENT")
    client = auth_client(student)

    listed = client.get("/api/v1/services")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [str(active_service.pk)]
    row = listed.json()["items"][0]
    assert row["appointment_booking_enabled"] is True
    assert row["provider_coverage"] == "ALL_COUNSELORS"
    assert "selected_counselor_ids" not in row
    assert client.get(f"/api/v1/services/{active_service.pk}").status_code == 200
    assert client.get(f"/api/v1/services/{inactive_service.pk}").status_code == 404
    assert client.get("/api/v1/services?include_inactive=true").status_code == 403
    denied = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "NOPE", "name": "Nope"}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 403
    for method, suffix, payload in (
        (client.patch, str(active_service.pk), {"name": "Denied"}),
        (client.post, f"{inactive_service.pk}/enable", {}),
        (client.post, f"{active_service.pk}/disable", {}),
    ):
        assert (
            method(
                f"/api/v1/services/{suffix}",
                data=json.dumps(payload),
                content_type="application/json",
                **csrf(client),
            ).status_code
            == 403
        )


@pytest.mark.django_db
def test_booking_filter_replaces_policy_filter():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    configured_service(admin, code="BOOKABLE", active=True)
    walk_in = create_service(
        code="WALK_IN_ONLY",
        name="Walk-in only",
        delivery_modes=["IN_PERSON"],
        context=context(admin),
    )
    set_service_active(service_id=walk_in.pk, is_active=True, context=context(admin))
    client = auth_client(admin)

    def codes(**params):
        return [row["code"] for row in client.get("/api/v1/services", params).json()["items"]]

    assert codes() == ["BOOKABLE", "WALK_IN_ONLY"]
    assert codes(appointment_booking_enabled="true") == ["BOOKABLE"]
    assert codes(appointment_booking_enabled="false") == ["WALK_IN_ONLY"]


@pytest.mark.django_db
def test_admin_and_head_can_manage_with_recent_mfa_but_revoke_and_stale_mfa_win():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    head = make_user("head@example.edu", "COUNSELOR")
    selected = make_user("selected@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    stale = auth_client(admin, recent_mfa=False)
    stale_response = stale.post(
        "/api/v1/services",
        data=json.dumps({"code": "STALE", "name": "Stale"}),
        content_type="application/json",
        **csrf(stale),
    )
    assert stale_response.status_code == 403
    assert stale_response.json()["error"]["code"] == "mfa_setup_required"

    admin_client = auth_client(admin)
    created = admin_client.post(
        "/api/v1/services",
        data=json.dumps(
            {
                "code": " ADMIN_SERVICE ",
                "name": "Admin Service",
                "delivery_modes": ["IN_PERSON"],
                "provider_coverage": "SELECTED_COUNSELORS",
                "selected_counselor_ids": [str(selected.pk)],
            }
        ),
        content_type="application/json",
        **csrf(admin_client),
    )
    assert created.status_code == 201
    assert created.json()["code"] == "ADMIN_SERVICE"
    assert not created.json()["is_active"]
    assert created.json()["activation_blockers"] == []
    assert created.json()["provider_coverage"] == "SELECTED_COUNSELORS"

    head_client = auth_client(head)
    assert head_client.get("/api/v1/services?include_inactive=true").status_code == 200

    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="services.manage"),
        effect="REVOKE",
        reason="separation",
    )
    denied = head_client.patch(
        f"/api/v1/services/{created.json()['id']}",
        data=json.dumps({"name": "Renamed"}),
        content_type="application/json",
        **csrf(head_client),
    )
    assert denied.status_code == 403
    assert head_client.get(f"/api/v1/services/{created.json()['id']}/providers").status_code == 403


@pytest.mark.django_db
def test_strict_api_rejects_retired_and_activation_fields_and_has_no_delete_endpoint():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    client = auth_client(admin)
    headers = csrf(client)

    for retired in (
        {"is_active": True},
        {"appointment_policy": "REQUIRED"},
        {"provider_roles": ["COUNSELOR"]},
        {"default_duration_minutes": 60},
    ):
        bad_create = client.post(
            "/api/v1/services",
            data=json.dumps({"code": "STRICT", "name": "Strict", **retired}),
            content_type="application/json",
            **headers,
        )
        assert bad_create.status_code == 422

    created = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "STRICT", "name": "Strict"}),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["activation_blockers"] == ["DELIVERY_MODE_MISSING"]

    bad_patch = client.patch(
        f"/api/v1/services/{created.json()['id']}",
        data=json.dumps({"code": "RENAMED"}),
        content_type="application/json",
        **headers,
    )
    assert bad_patch.status_code == 422

    deleted = client.delete(
        f"/api/v1/services/{created.json()['id']}",
        **headers,
    )
    assert deleted.status_code == 405


# COMPASS-SVC-1: independent booking configuration, legacy API and scheduling guards.
@pytest.mark.django_db
def test_booking_pathways_backwards_compatible_create_and_partial_updates():
    from compass.service_catalog.models import ServiceBookingPathway
    from compass.service_catalog.services import service_booking_pathways

    sync_policy()
    admin = make_user("pathway-admin@example.edu", "IT_ADMIN")
    flexible = configured_service(admin, active=True)
    assert service_booking_pathways(flexible) == ("FLEXIBLE_APPOINTMENT",)
    assert list(
        ServiceBookingPathway.objects.filter(service=flexible).values_list("code", flat=True)
    ) == ["FLEXIBLE_APPOINTMENT"]

    updated = update_service(
        service_id=flexible.pk,
        changes={"booking_pathways": ["FLEXIBLE_APPOINTMENT", "FIXED_DATE_SLOT", "GROUP_SESSION"]},
        context=context(admin),
    )
    assert updated.appointment_booking_enabled is True
    assert set(service_booking_pathways(updated)) == {
        "FLEXIBLE_APPOINTMENT",
        "FIXED_DATE_SLOT",
        "GROUP_SESSION",
    }

    # Legacy callers may update flexible booking without resetting other pathways.
    updated = update_service(
        service_id=flexible.pk,
        changes={"description": "New description"},
        context=context(admin),
    )
    assert len(service_booking_pathways(updated)) == 3
    updated = update_service(
        service_id=flexible.pk,
        changes={"appointment_booking_enabled": False},
        context=context(admin),
    )
    assert not updated.appointment_booking_enabled
    assert set(service_booking_pathways(updated)) == {"FIXED_DATE_SLOT", "GROUP_SESSION"}
    assert updated.default_appointment_duration_minutes is None
    assert updated.cancellation_cutoff_minutes is None
    assert ServiceBookingPathway.objects.filter(service=flexible).count() == 2


@pytest.mark.django_db
def test_independent_booking_pathway_validation_and_no_duplicate_rows():
    from compass.service_catalog.models import ServiceBookingPathway
    from compass.service_catalog.services import (
        InvalidServiceCatalogInput,
        service_booking_pathways,
    )
    from django.db import IntegrityError, transaction

    sync_policy()
    admin = make_user("pathway-validator@example.edu", "IT_ADMIN")
    service = create_service(
        code="GROUP_FUTURE",
        name="Group future",
        delivery_modes=["IN_PERSON"],
        booking_pathways=["GROUP_SESSION", "FIXED_DATE_SLOT"],
        context=context(admin),
    )
    assert service_booking_pathways(service) == ("FIXED_DATE_SLOT", "GROUP_SESSION")
    assert not service.appointment_booking_enabled
    assert service.default_appointment_duration_minutes is None
    assert set_service_active(
        service_id=service.pk, is_active=True, context=context(admin)
    ).is_active

    for invalid in (["GROUP_SESSION", "GROUP_SESSION"], ["BAD_PATHWAY"], "GROUP_SESSION"):
        with pytest.raises(InvalidServiceCatalogInput):
            update_service(
                service_id=service.pk,
                changes={"booking_pathways": invalid},
                context=context(admin),
            )
    with pytest.raises(InvalidServiceCatalogInput):
        update_service(
            service_id=service.pk,
            changes={
                "appointment_booking_enabled": False,
                "booking_pathways": ["FLEXIBLE_APPOINTMENT"],
            },
            context=context(admin),
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        ServiceBookingPathway.objects.create(service=service, code="GROUP_SESSION")


@pytest.mark.django_db
def test_pathway_api_permissions_mfa_and_student_active_only_visibility():
    sync_policy()
    admin = make_user("pathway-api-admin@example.edu", "IT_ADMIN")
    student = make_user("pathway-api-student@example.edu", "STUDENT")
    cold = auth_client(admin, recent_mfa=False)
    client = auth_client(admin)
    payload = {
        "code": "PATHWAY_API",
        "name": "Pathway API",
        "delivery_modes": ["IN_PERSON"],
        "booking_pathways": ["FIXED_DATE_SLOT", "GROUP_SESSION"],
    }
    rejected = cold.post(
        "/api/v1/services",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(cold),
    )
    assert rejected.status_code == 403
    created = client.post(
        "/api/v1/services",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert created.status_code == 201
    item = created.json()
    assert item["appointment_booking_enabled"] is False
    assert item["booking_pathways"] == ["FIXED_DATE_SLOT", "GROUP_SESSION"]
    assert item["activation_blockers"] == []
    student_client = auth_client(student)
    assert student_client.get(f"/api/v1/services/{item['id']}").status_code == 404
    assert (
        student_client.patch(
            f"/api/v1/services/{item['id']}",
            data=json.dumps({"booking_pathways": ["GROUP_SESSION"]}),
            content_type="application/json",
            **csrf(student_client),
        ).status_code
        == 403
    )
    enabled = client.post(
        f"/api/v1/services/{item['id']}/enable",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert enabled.status_code == 200
    visible = student_client.get(f"/api/v1/services/{item['id']}")
    assert visible.status_code == 200
    assert visible.json()["booking_pathways"] == ["FIXED_DATE_SLOT", "GROUP_SESSION"]

    # Contradictory old+new fields and duplicate pathways fail closed.
    conflict = client.patch(
        f"/api/v1/services/{item['id']}",
        data=json.dumps(
            {"appointment_booking_enabled": True, "booking_pathways": ["GROUP_SESSION"]}
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert conflict.status_code == 422
    duplicate = client.patch(
        f"/api/v1/services/{item['id']}",
        data=json.dumps({"booking_pathways": ["GROUP_SESSION", "GROUP_SESSION"]}),
        content_type="application/json",
        **csrf(client),
    )
    assert duplicate.status_code == 422


@pytest.mark.django_db
def test_pathway_only_change_is_audited_once_with_noop_idempotence():
    from compass.service_catalog.services import service_booking_pathways

    sync_policy()
    admin = make_user("pathway-audit@example.edu", "IT_ADMIN")
    service = configured_service(admin, active=True)
    previous = AuditEvent.objects.filter(action="service.updated").count()
    altered = update_service(
        service_id=service.pk,
        changes={"booking_pathways": ["FLEXIBLE_APPOINTMENT", "GROUP_SESSION"]},
        context=context(admin),
    )
    assert service_booking_pathways(altered) == ("FLEXIBLE_APPOINTMENT", "GROUP_SESSION")
    assert AuditEvent.objects.filter(action="service.updated").count() == previous + 1
    assert (
        "booking_pathways"
        in AuditEvent.objects.filter(action="service.updated")
        .latest("occurred_at")
        .metadata["changed_fields"]
    )
    update_service(
        service_id=service.pk,
        changes={"booking_pathways": ["FLEXIBLE_APPOINTMENT", "GROUP_SESSION"]},
        context=context(admin),
    )
    assert AuditEvent.objects.filter(action="service.updated").count() == previous + 1


@pytest.mark.django_db
def test_disabling_flexible_pathway_preserves_scheduled_appointment_after_review():
    from compass.appointments.models import Appointment, AppointmentStatus
    from compass.service_catalog.services import (
        ServiceSchedulingConsequenceReviewRequired,
        service_booking_pathways,
    )

    sync_policy()
    admin = make_user("pathways-review@example.edu", "IT_ADMIN")
    student = make_user("pathways-reservation-student@example.edu", "STUDENT")
    counselor = make_user("pathways-reservation-counselor@example.edu", "COUNSELOR")
    service = configured_service(admin, active=True)
    starts = timezone.now() + timedelta(days=3)
    appointment = Appointment.objects.create(
        reference_code="APT-2026-888801",
        student=student,
        provider=counselor,
        service=service,
        service_name_snapshot=service.name,
        delivery_mode="IN_PERSON",
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=AppointmentStatus.SCHEDULED,
    )

    with pytest.raises(ServiceSchedulingConsequenceReviewRequired) as caught:
        update_service(
            service_id=service.pk,
            changes={"booking_pathways": ["FIXED_DATE_SLOT", "GROUP_SESSION"]},
            context=context(admin),
        )
    assert caught.value.existing_appointment_dependency_detected
    assert service_booking_pathways(service) == ("FLEXIBLE_APPOINTMENT",)

    altered = update_service(
        service_id=service.pk,
        changes={"booking_pathways": ["FIXED_DATE_SLOT", "GROUP_SESSION"]},
        context=context(admin),
        acknowledge_scheduling_consequences=True,
    )
    appointment.refresh_from_db()
    assert appointment.starts_at == starts
    assert appointment.status == AppointmentStatus.SCHEDULED
    assert appointment.service_id == altered.pk
    assert not altered.appointment_booking_enabled
    assert set(service_booking_pathways(altered)) == {"FIXED_DATE_SLOT", "GROUP_SESSION"}


@pytest.mark.django_db
def test_pathway_backfill_is_idempotent_and_preserves_legacy_rows():
    import importlib
    from django.apps import apps
    from django.db import connection
    from compass.service_catalog.models import ServiceBookingPathway

    legacy = Service.objects.create(
        code="BACKFILL_LEGACY",
        name="Previously bookable",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=30,
    )
    no_booking = Service.objects.create(code="BACKFILL_UNAVAILABLE", name="Not bookable")
    assert not ServiceBookingPathway.objects.filter(service=legacy).exists()
    operation = importlib.import_module("compass.service_catalog.migrations.0002_booking_pathways")
    # Reuse the active test database's schema through a minimal migration editor proxy.
    editor = type("Editor", (), {"connection": connection})()
    operation.backfill_flexible_bookings(apps, editor)
    operation.backfill_flexible_bookings(apps, editor)
    assert (
        ServiceBookingPathway.objects.filter(service=legacy, code="FLEXIBLE_APPOINTMENT").count()
        == 1
    )
    assert not ServiceBookingPathway.objects.filter(service=no_booking).exists()
    legacy.refresh_from_db()
    assert legacy.appointment_booking_enabled
    assert legacy.default_appointment_duration_minutes == 30
