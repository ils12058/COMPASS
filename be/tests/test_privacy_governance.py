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


def make_privacy_admin(email: str = "privacy-admin@example.edu", *, active: bool = True) -> User:
    return make_user(email, role="IT_ADMIN", active=active)


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
def test_privacy_defaults_are_independent_and_head_authority_is_designation_derived():
    sync_policy()
    admin = make_privacy_admin()
    head = make_head()
    notices = {"privacy_governance.notices.view", "privacy_governance.notices.manage"}
    activity = {"privacy_governance.activity.view", "privacy_governance.activity.export"}
    assert notices | activity <= effective_capabilities(admin)
    assert "privacy_governance.activity.view" in effective_capabilities(head)
    assert (notices | {"privacy_governance.activity.export"}).isdisjoint(
        effective_capabilities(head)
    )
    assert set(
        DesignationCapability.objects.filter(
            designation__code="HEAD_GUIDANCE_COUNSELOR",
            capability__code__startswith="privacy_governance.",
        ).values_list("capability__code", flat=True)
    ) == {"privacy_governance.activity.view"}
    for role in (
        "INSTITUTIONAL_OFFICER",
        "COUNSELOR",
        "GUIDANCE_OFFICE_ASSISTANT",
        "STUDENT",
        "FACULTY",
    ):
        actor = make_user(f"privacy-{role}@example.edu", role=role)
        assert (notices | activity).isdisjoint(effective_capabilities(actor))
    assert effective_capabilities(make_user("empty-officer@example.edu")) == frozenset()


@pytest.mark.django_db
def test_inactive_admin_and_removed_head_designation_have_no_privacy_authority():
    sync_policy()
    admin = make_privacy_admin(active=False)
    assert effective_capabilities(admin) == frozenset()
    head = make_head()
    UserDesignation.objects.filter(user=head).delete()
    assert "privacy_governance.activity.view" not in effective_capabilities(head)


@pytest.mark.django_db
def test_privacy_admin_reads_and_drafts_without_step_up_but_publication_requires_it():
    sync_policy()
    privacy_admin = make_privacy_admin("mfa-privacy_admin@example.edu")
    client = auth_client(privacy_admin, recent_mfa=False)

    assert client.get("/api/v1/privacy/notices").status_code == 200
    assert client.get("/api/v1/privacy/activity").status_code == 200

    from tests.test_privacy_governance_expansion import notice_payload

    created = post_json(client, "/api/v1/privacy/notices", notice_payload())
    assert created.status_code == 201
    revision_id = created.json()["draft_revision"]["id"]

    denied = post_json(client, f"/api/v1/privacy/notice-revisions/{revision_id}/publish", {})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "mfa_setup_required"

    recent = auth_client(privacy_admin, recent_mfa=True)
    published = post_json(recent, f"/api/v1/privacy/notice-revisions/{revision_id}/publish", {})
    assert published.status_code == 200


@pytest.mark.django_db
def test_direct_api_defaults_separate_notice_administration_activity_and_export():
    sync_policy()
    admin = auth_client(make_privacy_admin())
    head = auth_client(make_head())
    assert admin.get("/api/v1/privacy/notices").status_code == 200
    assert admin.get("/api/v1/privacy/activity").status_code == 200
    assert admin.get("/api/v1/privacy/activity/export").status_code == 200
    assert head.get("/api/v1/privacy/activity").status_code == 200
    assert head.get("/api/v1/privacy/activity/export").status_code == 403
    from tests.test_privacy_governance_expansion import notice_payload

    notice = post_json(admin, "/api/v1/privacy/notices", notice_payload())
    assert notice.status_code == 201
    notice_id = notice.json()["id"]
    revision_id = notice.json()["draft_revision"]["id"]
    for path in (
        "/api/v1/privacy/notices",
        f"/api/v1/privacy/notices/{notice_id}",
        f"/api/v1/privacy/notices/{notice_id}/revisions",
        f"/api/v1/privacy/notice-revisions/{revision_id}",
    ):
        assert head.get(path).status_code == 403
    assert post_json(head, "/api/v1/privacy/notices", notice_payload()).status_code == 403
    for role in (
        "INSTITUTIONAL_OFFICER",
        "COUNSELOR",
        "GUIDANCE_OFFICE_ASSISTANT",
        "STUDENT",
        "FACULTY",
    ):
        c = auth_client(make_user(f"denied-{role}@example.edu", role=role))
        for path in (
            "/api/v1/privacy/notices",
            "/api/v1/privacy/activity",
            "/api/v1/privacy/activity/export",
        ):
            assert c.get(path).status_code == 403


@pytest.mark.django_db
def test_removed_privacy_workflow_routes_are_not_addressable():
    sync_policy()
    client = auth_client(make_privacy_admin("removed-routes@example.edu"), recent_mfa=True)

    for path in (
        "/api/v1/privacy/processing-activities",
        "/api/v1/privacy/reviews",
        "/api/v1/privacy/incidents",
        "/api/v1/privacy/retention-policies",
        "/api/v1/privacy/retention/policies",
    ):
        assert client.get(path).status_code == 404
        assert post_json(client, path, {}).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "grants,notice_status,activity_status,export_status",
    [
        ({"privacy_governance.notices.view"}, 200, 403, 403),
        ({"privacy_governance.notices.manage"}, 403, 403, 403),
        ({"privacy_governance.activity.view"}, 403, 200, 403),
        ({"privacy_governance.activity.export"}, 403, 403, 403),
        ({"privacy_governance.notices.view", "privacy_governance.notices.manage"}, 200, 403, 403),
        ({"privacy_governance.activity.view", "privacy_governance.activity.export"}, 403, 200, 200),
    ],
)
def test_independent_privacy_grants_and_dependencies(
    grants, notice_status, activity_status, export_status
):
    from compass.accounts.models import Capability, UserCapabilityOverride
    from tests.test_privacy_governance_expansion import notice_payload

    sync_policy()
    actor = make_user("explicit-privacy@example.edu")
    for code in grants:
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic independent authorization test",
        )
    client = auth_client(actor)
    assert client.get("/api/v1/privacy/notices").status_code == notice_status
    assert client.get("/api/v1/privacy/activity").status_code == activity_status
    assert client.get("/api/v1/privacy/activity/export").status_code == export_status
    can_manage = {"privacy_governance.notices.view", "privacy_governance.notices.manage"} <= grants
    assert post_json(client, "/api/v1/privacy/notices", notice_payload()).status_code == (
        201 if can_manage else 403
    )
    assert client.get("/api/v1/privacy/my-notices").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    [
        "IT_ADMIN",
        "COUNSELOR",
        "INSTITUTIONAL_OFFICER",
        "GUIDANCE_OFFICE_ASSISTANT",
        "STUDENT",
        "FACULTY",
    ],
)
def test_all_roles_keep_published_readership_and_own_exact_revision_acknowledgment(role):
    from tests.test_privacy_governance_expansion import notice_payload

    sync_policy()
    admin = auth_client(make_privacy_admin(), recent_mfa=True)
    notice = post_json(admin, "/api/v1/privacy/notices", notice_payload())
    revision = notice.json()["draft_revision"]["id"]
    assert (
        post_json(admin, f"/api/v1/privacy/notice-revisions/{revision}/publish", {}).status_code
        == 200
    )
    reader = auth_client(make_user(f"reader-{role}@example.edu", role=role))
    published = reader.get("/api/v1/privacy/my-notices")
    assert published.status_code == 200
    assert published.json()["items"][0]["revision_id"] == revision
    assert (
        post_json(reader, f"/api/v1/privacy/my-notices/{revision}/acknowledge", {}).status_code
        == 200
    )
