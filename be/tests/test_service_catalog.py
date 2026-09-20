from __future__ import annotations

import json
import uuid

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
from compass.service_catalog.models import ServiceDeliveryMode, ServiceProviderRole
from compass.service_catalog.services import (
    InvalidServiceCatalogInput,
    ServiceCatalogConflict,
    create_service,
    provider_role_eligible,
    service_allows_provider_role,
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
        last_name="User",
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


def configured_service(actor: User, *, active: bool = False, provider_roles=None):
    service = create_service(
        code="SYNTHETIC_SERVICE",
        name="Synthetic Service",
        description="Synthetic test configuration.",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_roles=provider_roles or ["COUNSELOR"],
        context=context(actor),
    )
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

    assert admin.has_capability("services.view")
    assert admin.has_capability("services.manage")
    assert counselor.has_capability("services.view")
    assert counselor.has_capability("services.manage")
    assert staff.has_capability("services.view")
    assert not staff.has_capability("services.manage")
    assert student.has_capability("services.view")
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
def test_create_normalizes_code_uses_uuid_and_starts_inactive():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = create_service(
        code="  synthetic_service  ",
        name=" Synthetic Service ",
        appointment_policy="NONE",
        context=context(actor),
    )

    assert isinstance(service.pk, uuid.UUID)
    assert service.code == "SYNTHETIC_SERVICE"
    assert service.name == "Synthetic Service"
    assert not service.is_active
    assert service.default_duration_minutes is None
    assert service.cancellation_cutoff_minutes is None
    assert list(service.delivery_mode_assignments.all()) == []
    assert list(service.provider_role_assignments.all()) == []


@pytest.mark.django_db
def test_duplicate_code_is_a_conflict_and_code_is_not_updateable():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = create_service(
        code="SYNTHETIC",
        name="Synthetic",
        appointment_policy="NONE",
        context=context(actor),
    )
    with pytest.raises(ServiceCatalogConflict, match="already exists"):
        create_service(
            code=" synthetic ",
            name="Other",
            appointment_policy="NONE",
            context=context(actor),
        )
    with pytest.raises(InvalidServiceCatalogInput, match="unsupported fields"):
        update_service(
            service_id=service.pk,
            changes={"code": "RENAMED"},
            context=context(actor),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("policy", ["NONE", "OPTIONAL", "REQUIRED"])
def test_all_appointment_policies_are_accepted_while_inactive(policy):
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = create_service(
        code=f"SERVICE_{policy}",
        name=f"Service {policy}",
        appointment_policy=policy,
        context=context(actor),
    )
    assert service.appointment_policy == policy


@pytest.mark.django_db
def test_invalid_appointment_policy_and_duration_bounds_are_rejected():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    with pytest.raises(InvalidServiceCatalogInput, match="appointment_policy"):
        create_service(
            code="BAD_POLICY",
            name="Bad",
            appointment_policy="SOMETIMES",
            context=context(actor),
        )
    for duration in (0, -1, 481):
        with pytest.raises(InvalidServiceCatalogInput, match="between 1 and 480"):
            create_service(
                code=f"BAD_DURATION_{abs(duration)}",
                name="Bad duration",
                appointment_policy="NONE",
                default_duration_minutes=duration,
                context=context(actor),
            )


@pytest.mark.django_db
def test_delivery_modes_and_provider_roles_are_closed_and_duplicates_are_rejected():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    with pytest.raises(InvalidServiceCatalogInput, match="delivery_modes"):
        create_service(
            code="BAD_MODE",
            name="Bad mode",
            appointment_policy="NONE",
            delivery_modes=["PHONE"],
            context=context(actor),
        )
    with pytest.raises(InvalidServiceCatalogInput, match="duplicates"):
        create_service(
            code="DUP_MODE",
            name="Duplicate mode",
            appointment_policy="NONE",
            delivery_modes=["ONLINE", "ONLINE"],
            context=context(actor),
        )
    for role_code in ("STUDENT", "IT_ADMIN"):
        with pytest.raises(InvalidServiceCatalogInput, match="provider_roles"):
            create_service(
                code=f"BAD_ROLE_{role_code}",
                name="Bad role",
                appointment_policy="NONE",
                provider_roles=[role_code],
                context=context(actor),
            )
    with pytest.raises(InvalidServiceCatalogInput, match="duplicates"):
        create_service(
            code="DUP_ROLE",
            name="Duplicate role",
            appointment_policy="NONE",
            provider_roles=["COUNSELOR", "COUNSELOR"],
            context=context(actor),
        )


@pytest.mark.django_db
def test_database_prevents_duplicate_mode_and_provider_role_rows():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = configured_service(actor)
    counselor_role = Role.objects.get(code="COUNSELOR")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServiceDeliveryMode.objects.create(service=service, mode="IN_PERSON")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServiceProviderRole.objects.create(service=service, role=counselor_role)


@pytest.mark.django_db
def test_activation_requires_complete_configuration_and_schedulable_duration():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    incomplete = create_service(
        code="INCOMPLETE",
        name="Incomplete",
        appointment_policy="NONE",
        context=context(actor),
    )
    with pytest.raises(ServiceCatalogConflict, match="delivery mode"):
        set_service_active(service_id=incomplete.pk, is_active=True, context=context(actor))

    optional = create_service(
        code="OPTIONAL_NO_DURATION",
        name="Optional no duration",
        appointment_policy="OPTIONAL",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    with pytest.raises(ServiceCatalogConflict, match="duration"):
        set_service_active(service_id=optional.pk, is_active=True, context=context(actor))

    none_policy = create_service(
        code="NONE_NO_DURATION",
        name="None no duration",
        appointment_policy="NONE",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    enabled = set_service_active(
        service_id=none_policy.pk,
        is_active=True,
        context=context(actor),
    )
    assert enabled.is_active

    with pytest.raises(InvalidServiceCatalogInput, match="COUNSELOR"):
        create_service(
            code="GSS_PROVIDER",
            name="GSS provider",
            appointment_policy="NONE",
            delivery_modes=["IN_PERSON"],
            provider_roles=["GUIDANCE_SERVICES_STAFF"],
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
            "provider_roles": ["COUNSELOR"],
        },
        context=context(actor),
    )
    assert AuditEvent.objects.filter(action="service.updated").count() == updated_count

    set_service_active(service_id=service.pk, is_active=False, context=context(actor))
    disabled_count = AuditEvent.objects.filter(action="service.disabled").count()
    set_service_active(service_id=service.pk, is_active=False, context=context(actor))
    assert AuditEvent.objects.filter(action="service.disabled").count() == disabled_count


@pytest.mark.django_db
def test_active_service_cannot_be_mutated_into_invalid_configuration():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = configured_service(actor, active=True)

    with pytest.raises(ServiceCatalogConflict, match="delivery mode"):
        update_service(
            service_id=service.pk,
            changes={"delivery_modes": []},
            context=context(actor),
        )
    with pytest.raises(ServiceCatalogConflict, match="provider role"):
        update_service(
            service_id=service.pk,
            changes={"provider_roles": []},
            context=context(actor),
        )
    with pytest.raises(ServiceCatalogConflict, match="duration"):
        update_service(
            service_id=service.pk,
            changes={"default_duration_minutes": None},
            context=context(actor),
        )

    changed = update_service(
        service_id=service.pk,
        changes={"appointment_policy": "NONE", "default_duration_minutes": None},
        context=context(actor),
    )
    assert changed.is_active
    assert changed.appointment_policy == "NONE"
    assert changed.default_duration_minutes is None


@pytest.mark.django_db
def test_provider_role_eligibility_keeps_legacy_gss_assignment_readable_but_non_operational():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    service = configured_service(actor, provider_roles=["COUNSELOR"])
    counselor = make_user("c@example.edu", "COUNSELOR")
    staff = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("s@example.edu", "STUDENT")
    other_admin = make_user("other-admin@example.edu", "IT_ADMIN")
    inactive_counselor = make_user("inactive@example.edu", "COUNSELOR", active=False)
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    # Preserve historical rows created under ADR-018, while ADR-050 prevents GSS from acting as a
    # live provider.
    ServiceProviderRole.objects.create(
        service=service,
        role=Role.objects.get(code="GUIDANCE_SERVICES_STAFF"),
    )

    assert service_allows_provider_role(service, "COUNSELOR")
    assert service_allows_provider_role(service, "GUIDANCE_SERVICES_STAFF")
    assert service_supports_delivery_mode(service, "ONLINE")
    assert not service_supports_delivery_mode(service, "FAX")
    assert provider_role_eligible(service, counselor)
    assert not provider_role_eligible(service, staff)
    assert provider_role_eligible(service, head)
    assert not provider_role_eligible(service, student)
    assert not provider_role_eligible(service, other_admin)
    assert not provider_role_eligible(service, inactive_counselor)


@pytest.mark.django_db
def test_student_can_read_only_active_catalog_and_cannot_manage():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    active_service = configured_service(actor, active=True)
    inactive_service = create_service(
        code="DRAFT_SERVICE",
        name="Draft Service",
        appointment_policy="NONE",
        context=context(actor),
    )
    student = make_user("student@example.edu", "STUDENT")
    client = auth_client(student)

    listed = client.get("/api/v1/services")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [str(active_service.pk)]
    assert client.get(f"/api/v1/services/{inactive_service.pk}").status_code == 404
    assert client.get("/api/v1/services?include_inactive=true").status_code == 403
    denied = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "NOPE", "name": "Nope", "appointment_policy": "NONE"}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_admin_and_head_can_manage_with_recent_mfa_but_revoke_and_stale_mfa_win():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    stale = auth_client(admin, recent_mfa=False)
    stale_response = stale.post(
        "/api/v1/services",
        data=json.dumps({"code": "STALE", "name": "Stale", "appointment_policy": "NONE"}),
        content_type="application/json",
        **csrf(stale),
    )
    assert stale_response.status_code == 403
    assert stale_response.json()["error"]["code"] == "recent_mfa_required"

    admin_client = auth_client(admin)
    created = admin_client.post(
        "/api/v1/services",
        data=json.dumps(
            {
                "code": " ADMIN_SERVICE ",
                "name": "Admin Service",
                "appointment_policy": "NONE",
                "delivery_modes": ["IN_PERSON"],
                "provider_roles": ["COUNSELOR"],
            }
        ),
        content_type="application/json",
        **csrf(admin_client),
    )
    assert created.status_code == 201
    assert created.json()["code"] == "ADMIN_SERVICE"
    assert not created.json()["is_active"]

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


@pytest.mark.django_db
def test_strict_api_rejects_activation_and_code_fields_and_has_no_delete_endpoint():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    client = auth_client(admin)
    headers = csrf(client)

    bad_create = client.post(
        "/api/v1/services",
        data=json.dumps(
            {
                "code": "STRICT",
                "name": "Strict",
                "appointment_policy": "NONE",
                "is_active": True,
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert bad_create.status_code == 422

    created = client.post(
        "/api/v1/services",
        data=json.dumps({"code": "STRICT", "name": "Strict", "appointment_policy": "NONE"}),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201

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


@pytest.mark.django_db
def test_cancellation_cutoff_is_nonnegative_and_validated_with_active_appointment_policy():
    sync_policy()
    actor = make_user("cutoff-admin@example.edu", "IT_ADMIN")

    with pytest.raises(InvalidServiceCatalogInput, match="non-negative"):
        create_service(
            code="NEGATIVE_CUTOFF",
            name="Negative cutoff",
            appointment_policy="OPTIONAL",
            default_duration_minutes=60,
            cancellation_cutoff_minutes=-1,
            delivery_modes=["IN_PERSON"],
            provider_roles=["COUNSELOR"],
            context=context(actor),
        )

    draft_none = create_service(
        code="DRAFT_NONE_CUTOFF",
        name="Draft none cutoff",
        appointment_policy="NONE",
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    with pytest.raises(ServiceCatalogConflict, match="cannot configure"):
        set_service_active(service_id=draft_none.pk, is_active=True, context=context(actor))

    service = create_service(
        code="CUT_OFF_SERVICE",
        name="Cutoff Service",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    service = set_service_active(service_id=service.pk, is_active=True, context=context(actor))
    assert service.cancellation_cutoff_minutes == 30

    with pytest.raises(ServiceCatalogConflict, match="cannot configure"):
        update_service(
            service_id=service.pk,
            changes={"appointment_policy": "NONE", "default_duration_minutes": None},
            context=context(actor),
        )

    changed = update_service(
        service_id=service.pk,
        changes={
            "appointment_policy": "NONE",
            "default_duration_minutes": None,
            "cancellation_cutoff_minutes": None,
        },
        context=context(actor),
    )
    assert changed.appointment_policy == "NONE"
    assert changed.cancellation_cutoff_minutes is None
