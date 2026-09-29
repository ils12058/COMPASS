from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    DesignationCapability,
    Role,
    User,
    UserDesignation,
)
from compass.accounts.services import effective_capabilities
from compass.authentication.sessions import create_auth_session


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(
    email: str,
    *,
    role: str = "INSTITUTIONAL_OFFICER",
    active: bool = True,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name="Privacy",
        last_name="Operator",
        is_active=active,
    )


def make_dpo(email: str = "dpo@example.edu", *, active: bool = True) -> User:
    user = make_user(email, active=active)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="DPO"),
    )
    return user


def make_head(email: str = "head@example.edu") -> User:
    user = make_user(email, role="COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


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


def post_json(client: Client, path: str, payload: dict[str, object]):
    return client.post(
        path,
        data=json.dumps(payload, default=str),
        content_type="application/json",
        **csrf(client),
    )


def patch_json(client: Client, path: str, payload: dict[str, object]):
    return client.patch(
        path,
        data=json.dumps(payload, default=str),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_dpo_privacy_authority_is_designation_derived_and_separate_from_roles():
    sync_policy()

    dpo = make_dpo()
    plain_officer = make_user("plain-officer@example.edu")
    admin = make_user("admin@example.edu", role="IT_ADMIN")
    counselor = make_user("counselor@example.edu", role="COUNSELOR")
    head = make_head()

    assert set(
        DesignationCapability.objects.filter(designation__code="DPO").values_list(
            "capability__code", flat=True
        )
    ) == {"privacy_governance.view", "privacy_governance.manage"}

    assert effective_capabilities(dpo) == frozenset(
        {"privacy_governance.view", "privacy_governance.manage"}
    )
    for actor in (plain_officer, admin, counselor, head):
        assert "privacy_governance.view" not in effective_capabilities(actor)
        assert "privacy_governance.manage" not in effective_capabilities(actor)

    forbidden_dpo_capabilities = {
        "accounts.view",
        "accounts.manage",
        "platform_operations.view",
        "platform_operations.manage",
        "organization.structure.view",
        "organization.manage",
        "reports.view",
        "counseling.view_assigned",
        "counseling.manage_assigned",
        "inventory.view_self",
        "referrals.view",
        "referrals.manage",
        "exit_interviews.view",
        "graduate_tracer.view",
    }
    assert forbidden_dpo_capabilities.isdisjoint(effective_capabilities(dpo))


@pytest.mark.django_db
def test_inactive_or_removed_dpo_has_no_privacy_authority():
    sync_policy()
    dpo = make_dpo("removed-dpo@example.edu")
    assignment = UserDesignation.objects.get(user=dpo, designation__code="DPO")

    assignment.delete()
    assert "privacy_governance.view" not in effective_capabilities(dpo)
    assert "privacy_governance.manage" not in effective_capabilities(dpo)

    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    dpo.is_active = False
    dpo.save(update_fields=["is_active", "updated_at"])
    assert effective_capabilities(dpo) == frozenset()


@pytest.mark.django_db
def test_dpo_reads_without_step_up_but_retained_mutations_require_recent_mfa():
    sync_policy()
    dpo = make_dpo("mfa-dpo@example.edu")
    client = auth_client(dpo, recent_mfa=False)

    assert client.get("/api/v1/privacy/notices").status_code == 200
    assert client.get("/api/v1/privacy/activity").status_code == 200

    from tests.test_privacy_governance_expansion import notice_payload

    denied = post_json(client, "/api/v1/privacy/notices", notice_payload())
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    recent = auth_client(dpo, recent_mfa=True)
    assert post_json(recent, "/api/v1/privacy/notices", notice_payload()).status_code == 201


@pytest.mark.django_db
def test_non_dpo_baselines_are_denied_retained_routes_and_dpo_is_denied_operational_routes():
    sync_policy()
    admin = make_user("privacy-admin@example.edu", role="IT_ADMIN")
    counselor = make_user("privacy-counselor@example.edu", role="COUNSELOR")
    dpo = make_dpo("boundary-dpo@example.edu")

    for actor in (admin, counselor):
        client = auth_client(actor)
        assert client.get("/api/v1/privacy/notices").status_code == 403
        assert client.get("/api/v1/privacy/activity").status_code == 403

    dpo_client = auth_client(dpo)
    assert dpo_client.get("/api/v1/accounts").status_code == 403
    assert dpo_client.get("/api/v1/platform/health").status_code == 403
    assert dpo_client.get("/api/v1/reports/student-profile").status_code == 403


@pytest.mark.django_db
def test_removed_privacy_workflow_routes_are_not_addressable():
    sync_policy()
    client = auth_client(make_dpo("removed-routes@example.edu"), recent_mfa=True)

    for path in (
        "/api/v1/privacy/processing-activities",
        "/api/v1/privacy/reviews",
        "/api/v1/privacy/incidents",
        "/api/v1/privacy/retention-policies",
    ):
        assert client.get(path).status_code == 404
        assert post_json(client, path, {}).status_code == 404
