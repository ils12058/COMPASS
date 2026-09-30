from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.account_management.services import inspect_account_access
from compass.accounts import policy as capability_policy
from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.policy import (
    CAPABILITY_DEPENDENCIES,
    DESIGNATION_CAPABILITY_GRANTS,
    DESIGNATION_ROLE_COMPATIBILITY,
    ROLE_CAPABILITY_GRANTS,
    missing_required_capabilities,
    resolve_capability_dependencies,
)
from compass.accounts.services import (
    effective_capabilities,
    projected_capabilities,
    set_user_capability_override,
    user_has_capability,
)
from compass.authentication.sessions import create_auth_session


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    role: str,
    *,
    active: bool = True,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Capability",
        last_name="Test",
        is_active=active,
    )


def auth_client(user: User, *, recent_mfa: bool = True) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        mfa_verified_at=now if recent_mfa else None,
        now=now,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def put_json(client: Client, path: str, payload: dict[str, object]):
    return client.put(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_normal_role_and_designation_baselines_remain_dependency_coherent():
    sync_policy()

    for role_code, grants in ROLE_CAPABILITY_GRANTS.items():
        assert resolve_capability_dependencies(grants) == grants
        user = make_user(
            f"baseline-{role_code.lower()}@example.edu",
            role_code,
        )
        assert effective_capabilities(user) == grants

    head = make_user("baseline-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    expected_head = (
        ROLE_CAPABILITY_GRANTS["COUNSELOR"]
        | DESIGNATION_CAPABILITY_GRANTS["HEAD_GUIDANCE_COUNSELOR"]
    )
    assert effective_capabilities(head) == expected_head

    dpo = make_user("baseline-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    expected_dpo = (
        ROLE_CAPABILITY_GRANTS["INSTITUTIONAL_OFFICER"] | DESIGNATION_CAPABILITY_GRANTS["DPO"]
    )
    assert effective_capabilities(dpo) == expected_dpo

    for designation_code, compatible_roles in DESIGNATION_ROLE_COMPATIBILITY.items():
        for role_code in compatible_roles:
            combined = (
                ROLE_CAPABILITY_GRANTS[role_code] | DESIGNATION_CAPABILITY_GRANTS[designation_code]
            )
            assert resolve_capability_dependencies(combined) == combined


def test_dependency_resolver_runs_until_fixed_point(monkeypatch):
    monkeypatch.setitem(
        CAPABILITY_DEPENDENCIES,
        "referrals.view",
        frozenset({"accounts.view"}),
    )
    assert resolve_capability_dependencies({"referrals.manage", "referrals.view"}) == frozenset()


def test_dependency_policy_validation_rejects_cycles(monkeypatch):
    monkeypatch.setitem(
        CAPABILITY_DEPENDENCIES,
        "referrals.view",
        frozenset({"referrals.manage"}),
    )
    with pytest.raises(RuntimeError, match="cycle"):
        capability_policy._validate_dependency_graph()


@pytest.mark.django_db
def test_prerequisite_revoke_suppresses_dependents_without_rewriting_baseline():
    sync_policy()
    counselor = make_user("revoke-counselor@example.edu", "COUNSELOR")
    role = counselor.role
    view = Capability.objects.get(code="routine_interviews.view_assigned")
    manage = Capability.objects.get(code="routine_interviews.manage_assigned")

    assert RoleCapability.objects.filter(role=role, capability=view).exists()
    assert RoleCapability.objects.filter(role=role, capability=manage).exists()

    set_user_capability_override(
        user=counselor,
        capability=view,
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary review-only separation",
    )

    effective = effective_capabilities(counselor)
    assert "routine_interviews.view_assigned" not in effective
    assert "routine_interviews.manage_assigned" not in effective
    assert not user_has_capability(counselor, "routine_interviews.manage_assigned")
    assert RoleCapability.objects.filter(role=role, capability=manage).exists()
    assert UserCapabilityOverride.objects.filter(user=counselor).count() == 1
    assert not UserCapabilityOverride.objects.filter(
        user=counselor,
        capability=manage,
    ).exists()


@pytest.mark.django_db
def test_incompatible_historical_grant_remains_recorded_but_ineffective_and_explained():
    sync_policy()
    user = make_user("historical-grant@example.edu", "INSTITUTIONAL_OFFICER")
    override = set_user_capability_override(
        user=user,
        capability="call_slips.manage",
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Historical pre-dependency grant",
    )

    assert override.pk is not None
    assert "call_slips.manage" not in effective_capabilities(user)

    access = inspect_account_access(user_id=user.pk)
    row = next(item for item in access["capabilities"] if item["code"] == "call_slips.manage")
    assert row["effective"] is False
    assert row["required_capabilities"] == ["call_slips.view"]
    assert row["missing_required_capabilities"] == ["call_slips.view"]
    assert row["baseline_sources"] == []
    assert row["override"]["effect"] == "GRANT"
    assert row["override"]["reason"] == "Historical pre-dependency grant"


@pytest.mark.django_db
def test_grant_override_rejects_missing_prerequisite_then_accepts_explicit_sequence():
    sync_policy()
    admin = make_user("grant-admin@example.edu", "IT_ADMIN")
    target = make_user("grant-target@example.edu", "INSTITUTIONAL_OFFICER")
    client = auth_client(admin)

    blocked = put_json(
        client,
        f"/api/v1/accounts/{target.pk}/capability-overrides/call_slips.manage",
        {
            "effect": "GRANT",
            "reason": "Needs scoped Call Slip management",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "capability_dependency_conflict"
    assert "View scoped Call Slips" in blocked.json()["error"]["message"]
    assert not UserCapabilityOverride.objects.filter(user=target).exists()

    granted_view = put_json(
        client,
        f"/api/v1/accounts/{target.pk}/capability-overrides/call_slips.view",
        {
            "effect": "GRANT",
            "reason": "Approved scoped Call Slip visibility",
        },
    )
    assert granted_view.status_code == 200

    granted_manage = put_json(
        client,
        f"/api/v1/accounts/{target.pk}/capability-overrides/call_slips.manage",
        {
            "effect": "GRANT",
            "reason": "Approved scoped Call Slip management",
        },
    )
    assert granted_manage.status_code == 200
    assert {
        "call_slips.view",
        "call_slips.manage",
    } <= effective_capabilities(target)
    assert UserCapabilityOverride.objects.filter(user=target).count() == 2


@pytest.mark.django_db
def test_prerequisite_revoke_is_allowed_and_removal_restores_baseline_dependents():
    sync_policy()
    admin = make_user("restore-admin@example.edu", "IT_ADMIN")
    counselor = make_user("restore-counselor@example.edu", "COUNSELOR")
    client = auth_client(admin)

    revoke = put_json(
        client,
        f"/api/v1/accounts/{counselor.pk}/capability-overrides/good_moral.view",
        {
            "effect": "REVOKE",
            "reason": "Temporary least-privilege restriction",
        },
    )
    assert revoke.status_code == 200
    effective = effective_capabilities(counselor)
    assert {
        "good_moral.view",
        "good_moral.manage",
        "good_moral.issue",
    }.isdisjoint(effective)
    assert UserCapabilityOverride.objects.filter(user=counselor).count() == 1

    removed = client.delete(
        f"/api/v1/accounts/{counselor.pk}/capability-overrides/good_moral.view",
        **csrf(client),
    )
    assert removed.status_code == 200
    assert removed.json() == {"removed": True}
    assert {
        "good_moral.view",
        "good_moral.manage",
        "good_moral.issue",
    } <= effective_capabilities(counselor)
    assert not UserCapabilityOverride.objects.filter(user=counselor).exists()


@pytest.mark.django_db
def test_dependency_resolution_tracks_override_expiry_without_background_jobs():
    sync_policy()
    base = timezone.now()

    delegated = make_user("expiry-grant@example.edu", "INSTITUTIONAL_OFFICER")
    set_user_capability_override(
        user=delegated,
        capability="call_slips.view",
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Temporary view",
        expires_at=base + timedelta(hours=1),
    )
    set_user_capability_override(
        user=delegated,
        capability="call_slips.manage",
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Longer management delegation",
        expires_at=base + timedelta(hours=2),
    )

    before_expiry = effective_capabilities(delegated, at=base + timedelta(minutes=30))
    assert {"call_slips.view", "call_slips.manage"} <= before_expiry

    after_view_expiry = effective_capabilities(delegated, at=base + timedelta(minutes=90))
    assert "call_slips.view" not in after_view_expiry
    assert "call_slips.manage" not in after_view_expiry

    counselor = make_user("expiry-revoke@example.edu", "COUNSELOR")
    set_user_capability_override(
        user=counselor,
        capability="good_moral.view",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary review separation",
        expires_at=base + timedelta(hours=1),
    )

    during_revoke = effective_capabilities(counselor, at=base + timedelta(minutes=30))
    assert {
        "good_moral.view",
        "good_moral.manage",
        "good_moral.issue",
    }.isdisjoint(during_revoke)

    after_revoke = effective_capabilities(counselor, at=base + timedelta(minutes=90))
    assert {
        "good_moral.view",
        "good_moral.manage",
        "good_moral.issue",
    } <= after_revoke


@pytest.mark.django_db
def test_access_inspector_explains_dependency_suppression_without_corrupting_provenance():
    sync_policy()
    counselor = make_user("inspector-counselor@example.edu", "COUNSELOR")
    set_user_capability_override(
        user=counselor,
        capability="referrals.view",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary intake separation",
    )

    access = inspect_account_access(user_id=counselor.pk)
    manage = next(item for item in access["capabilities"] if item["code"] == "referrals.manage")
    view = next(item for item in access["capabilities"] if item["code"] == "referrals.view")

    assert manage["effective"] is False
    assert manage["required_capabilities"] == ["referrals.view"]
    assert manage["missing_required_capabilities"] == ["referrals.view"]
    assert manage["baseline_sources"] == [{"type": "ROLE", "code": "COUNSELOR"}]
    assert manage["override"] is None

    assert view["effective"] is False
    assert view["required_capabilities"] == []
    assert view["missing_required_capabilities"] == []
    assert view["baseline_sources"] == [{"type": "ROLE", "code": "COUNSELOR"}]
    assert view["override"]["effect"] == "REVOKE"


@pytest.mark.django_db
def test_inactive_account_override_validation_uses_projected_policy_composition():
    sync_policy()
    admin = make_user("inactive-admin@example.edu", "IT_ADMIN")
    target = make_user(
        "inactive-target@example.edu",
        "INSTITUTIONAL_OFFICER",
        active=False,
    )
    blocked_target = make_user(
        "inactive-blocked@example.edu",
        "INSTITUTIONAL_OFFICER",
        active=False,
    )
    client = auth_client(admin)

    blocked = put_json(
        client,
        f"/api/v1/accounts/{blocked_target.pk}/capability-overrides/call_slips.manage",
        {
            "effect": "GRANT",
            "reason": "Missing prerequisite",
        },
    )
    assert blocked.status_code == 409

    assert (
        put_json(
            client,
            f"/api/v1/accounts/{target.pk}/capability-overrides/call_slips.view",
            {
                "effect": "GRANT",
                "reason": "Future scoped visibility",
            },
        ).status_code
        == 200
    )
    assert (
        put_json(
            client,
            f"/api/v1/accounts/{target.pk}/capability-overrides/call_slips.manage",
            {
                "effect": "GRANT",
                "reason": "Future scoped management",
            },
        ).status_code
        == 200
    )

    assert effective_capabilities(target) == frozenset()
    assert {
        "call_slips.view",
        "call_slips.manage",
    } <= projected_capabilities(target)


@pytest.mark.django_db
def test_session_and_domain_guard_consume_dependency_resolved_authority():
    sync_policy()
    admin = make_user("dependency-session-admin@example.edu", "IT_ADMIN")
    set_user_capability_override(
        user=admin,
        capability="platform_operations.view",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary runtime visibility restriction",
    )

    assert "platform_operations.view" not in effective_capabilities(admin)
    assert "platform_operations.manage" not in effective_capabilities(admin)
    assert not user_has_capability(admin, "platform_operations.manage")

    client = auth_client(admin)
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    capabilities = set(session.json()["user"]["capabilities"])
    assert "platform_operations.view" not in capabilities
    assert "platform_operations.manage" not in capabilities

    denied = client.post(
        "/api/v1/platform/maintenance/enable",
        data=json.dumps({"message": "Must be denied by central capability resolution"}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"


def test_required_capability_helper_is_policy_owned_and_specific():
    assert missing_required_capabilities(
        "good_moral.issue",
        {"good_moral.issue"},
    ) == {"good_moral.view"}
    assert capability_policy.required_capabilities("availability.manage") == frozenset()
