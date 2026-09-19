from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.actions import (
    ACCOUNT_CAPABILITY_OVERRIDE_SET,
    ACCOUNT_DESIGNATION_ASSIGNED,
    ACCOUNT_ROLE_CHANGED,
    APPOINTMENT_CREATED,
    COUNSELING_ENCOUNTER_UPDATED,
    DOCUMENT_DOWNLOAD_RELEASED,
    PRIVACY_INCIDENT_CREATED,
    REPORT_EXPORT_RELEASED,
)
from compass.audit.context import AuditContext
from compass.audit.services import record_event
from compass.authentication.actions import (
    AUTH_LOGIN_FAILED,
    AUTH_MFA_TOTP_FAILED,
    AUTH_PASSWORD_RESET,
)
from compass.authentication.sessions import create_auth_session


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(email: str, role: str = "INSTITUTIONAL_OFFICER") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-that-is-long",
        role=Role.objects.get(code=role),
        first_name="Privacy",
        last_name="Observer",
    )


def make_dpo(email: str = "activity-dpo@example.edu") -> User:
    user = make_user(email)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="DPO"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def audited_context(actor: User) -> AuditContext:
    return AuditContext.user(
        actor,
        ip_address="203.0.113.7",
        user_agent_summary="SENTINEL-PRIVATE-USER-AGENT",
    )


@pytest.mark.django_db
def test_privacy_activity_requires_dpo_view_capability():
    sync_policy()
    dpo = make_dpo()
    admin = make_user("activity-admin@example.edu", "IT_ADMIN")

    assert Client().get("/api/v1/privacy/activity").status_code == 401
    assert auth_client(admin).get("/api/v1/privacy/activity").status_code == 403
    assert auth_client(dpo).get("/api/v1/privacy/activity").status_code == 200


@pytest.mark.django_db
def test_privacy_activity_data_release_presenters_are_content_free():
    sync_policy()
    dpo = make_dpo("release-activity-dpo@example.edu")
    actor = make_user("release-actor@example.edu", "COUNSELOR")
    academic_year_id = uuid4()
    good_moral_id = uuid4()
    now = timezone.now()

    report_event = record_event(
        context=audited_context(actor),
        action=REPORT_EXPORT_RELEASED,
        outcome="SUCCESS",
        target_type="report.student_profiling",
        target_id=academic_year_id,
        occurred_at=now,
        metadata={
            "report_type": "student_profiling",
            "format": "XLSX",
            "academic_year_id": str(academic_year_id),
            "academic_year_label": "2026-2027",
            "campus_id": str(uuid4()),
            "campus_code": "MAIN",
            "college_id": str(uuid4()),
            "college_code": "CCMS",
            "program_id": str(uuid4()),
            "program_code": "BSIS",
            "year_level": 4,
            "SENTINEL_AGGREGATE_CONTENT": "must never be projected",
        },
    )
    document_event = record_event(
        context=audited_context(actor),
        action=DOCUMENT_DOWNLOAD_RELEASED,
        outcome="SUCCESS",
        target_type="goodmoral.request",
        target_id=good_moral_id,
        occurred_at=now - timedelta(seconds=1),
        metadata={
            "document_type": "good_moral_certificate",
            "variant": "GRADUATE",
            "access_mode": "GCO",
            "SENTINEL_APPLICANT_NAME": "must never be projected",
        },
    )

    response = auth_client(dpo).get("/api/v1/privacy/activity?category=DATA_RELEASE")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [
        str(report_event.pk),
        str(document_event.pk),
    ]
    assert items[0]["title"] == "Student Profiling XLSX released"
    assert items[0]["artifact_type"] == "student_profiling"
    assert items[0]["artifact_format"] == "XLSX"
    assert "Academic Year 2026-2027" in items[0]["scope"]
    assert "CCMS" in items[0]["scope"]
    assert "BSIS" in items[0]["scope"]
    assert items[1]["title"] == "Good Moral certificate released"
    assert items[1]["resource_reference"] == str(good_moral_id)

    serialized = response.content.decode()
    for forbidden in (
        "SENTINEL_AGGREGATE_CONTENT",
        "SENTINEL_APPLICANT_NAME",
        "SENTINEL-PRIVATE-USER-AGENT",
        "203.0.113.7",
        '"metadata"',
    ):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_access_control_projection_allowlists_only_safe_authority_facts():
    sync_policy()
    dpo = make_dpo("access-activity-dpo@example.edu")
    operator = make_user("account-admin-operator@example.edu", "IT_ADMIN")
    target_id = uuid4()
    now = timezone.now()

    role_event = record_event(
        context=audited_context(operator),
        action=ACCOUNT_ROLE_CHANGED,
        outcome="SUCCESS",
        target_type="accounts.user",
        target_id=target_id,
        occurred_at=now,
        metadata={
            "from_role": "COUNSELOR",
            "to_role": "INSTITUTIONAL_OFFICER",
            "SENTINEL_PRIVATE_EMAIL": "student@example.edu",
        },
    )
    designation_event = record_event(
        context=audited_context(operator),
        action=ACCOUNT_DESIGNATION_ASSIGNED,
        outcome="SUCCESS",
        target_type="accounts.user",
        target_id=target_id,
        occurred_at=now - timedelta(seconds=1),
        metadata={"designation": "DPO"},
    )
    override_event = record_event(
        context=audited_context(operator),
        action=ACCOUNT_CAPABILITY_OVERRIDE_SET,
        outcome="SUCCESS",
        target_type="accounts.user",
        target_id=target_id,
        occurred_at=now - timedelta(seconds=2),
        metadata={
            "capability": "privacy_governance.view",
            "effect": "GRANT",
            "has_expiry": False,
        },
    )

    response = auth_client(dpo).get("/api/v1/privacy/activity?category=ACCESS_CONTROL")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [
        str(role_event.pk),
        str(designation_event.pk),
        str(override_event.pk),
    ]
    assert items[0]["actor_display_name"] == "Privacy Observer"
    assert "COUNSELOR" in items[0]["description"]
    assert "INSTITUTIONAL_OFFICER" in items[0]["description"]
    assert "DPO" in items[1]["description"]
    assert "privacy_governance.view" in items[2]["description"]
    assert "SENTINEL_PRIVATE_EMAIL" not in response.content.decode()


@pytest.mark.django_db
def test_account_security_projection_does_not_misattribute_failed_login_or_mfa():
    sync_policy()
    dpo = make_dpo("security-activity-dpo@example.edu")
    target = make_user("known-target@example.edu", "STUDENT")
    now = timezone.now()

    login_failed = record_event(
        context=audited_context(target),
        action=AUTH_LOGIN_FAILED,
        outcome="DENIED",
        target_type="accounts.user",
        target_id=target.pk,
        occurred_at=now,
        metadata={"method": "password", "submitted_email": "must-not-project"},
    )
    mfa_failed = record_event(
        context=audited_context(target),
        action=AUTH_MFA_TOTP_FAILED,
        outcome="DENIED",
        target_type="auth.totpfactor",
        target_id=uuid4(),
        occurred_at=now - timedelta(seconds=1),
        metadata={"stage": "login"},
    )
    password_reset = record_event(
        context=audited_context(target),
        action=AUTH_PASSWORD_RESET,
        outcome="SUCCESS",
        target_type="accounts.user",
        target_id=target.pk,
        occurred_at=now - timedelta(seconds=2),
        metadata={"method": "email_otp"},
    )

    response = auth_client(dpo).get("/api/v1/privacy/activity?category=ACCOUNT_SECURITY")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [
        str(login_failed.pk),
        str(mfa_failed.pk),
        str(password_reset.pk),
    ]
    assert items[0]["title"] == "Failed login attempt"
    assert items[0]["description"] == "Failed login attempt for an account."
    assert items[0]["actor_display_name"] is None
    assert items[1]["actor_display_name"] is None
    assert items[2]["actor_display_name"] == "Privacy Observer"

    serialized = response.content.decode()
    assert target.email not in serialized
    assert "submitted_email" not in serialized
    assert "email_otp" not in serialized
    assert "SENTINEL-PRIVATE-USER-AGENT" not in serialized
    assert "203.0.113.7" not in serialized


@pytest.mark.django_db
def test_privacy_governance_projection_never_copies_incident_narrative():
    sync_policy()
    dpo = make_dpo("governance-activity-dpo@example.edu")
    incident_id = uuid4()
    event = record_event(
        context=audited_context(dpo),
        action=PRIVACY_INCIDENT_CREATED,
        outcome="SUCCESS",
        target_type="privacy.incident",
        target_id=incident_id,
        metadata={
            "reference_code": "PRI-ABCDEF123456",
            "status": "OPEN",
            "summary": "SENTINEL INCIDENT NARRATIVE",
        },
    )

    response = auth_client(dpo).get(
        "/api/v1/privacy/activity?category=PRIVACY_GOVERNANCE"
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(event.pk)
    assert item["title"] == "Privacy incident recorded"
    assert item["resource_reference"] == str(incident_id)
    assert "SENTINEL INCIDENT NARRATIVE" not in response.content.decode()


@pytest.mark.django_db
def test_privacy_activity_excludes_unrelated_domains_unknown_actions_and_malformed_rows():
    sync_policy()
    dpo = make_dpo("closed-activity-dpo@example.edu")
    actor = make_user("ordinary-actor@example.edu", "COUNSELOR")
    now = timezone.now()

    record_event(
        context=AuditContext.user(actor),
        action=APPOINTMENT_CREATED,
        outcome="SUCCESS",
        target_type="appointment",
        target_id=uuid4(),
        occurred_at=now,
        metadata={},
    )
    record_event(
        context=AuditContext.user(actor),
        action=COUNSELING_ENCOUNTER_UPDATED,
        outcome="SUCCESS",
        target_type="counseling.encounter",
        target_id=uuid4(),
        occurred_at=now - timedelta(seconds=1),
        metadata={"SENTINEL_COUNSELING_CONTENT": "must not appear"},
    )
    record_event(
        context=AuditContext.user(actor),
        action=REPORT_EXPORT_RELEASED,
        outcome="SUCCESS",
        target_type="report.student_profiling",
        target_id="not-a-uuid",
        occurred_at=now - timedelta(seconds=2),
        metadata={
            "report_type": "student_profiling",
            "format": "PDF",
            "academic_year_label": "2026-2027",
        },
    )

    response = auth_client(dpo).get("/api/v1/privacy/activity")

    assert response.status_code == 200
    assert response.json()["items"] == []
    serialized = response.content.decode()
    assert "appointment.created" not in serialized
    assert "counseling" not in serialized.lower()
    assert "SENTINEL_COUNSELING_CONTENT" not in serialized


@pytest.mark.django_db
def test_privacy_activity_pagination_and_category_filter_are_bounded_and_deterministic():
    sync_policy()
    dpo = make_dpo("pagination-privacy-dpo@example.edu")
    actor = make_user("pagination-actor@example.edu", "IT_ADMIN")
    now = timezone.now()

    events = [
        record_event(
            context=AuditContext.user(actor),
            action=ACCOUNT_ROLE_CHANGED,
            outcome="SUCCESS",
            target_type="accounts.user",
            target_id=uuid4(),
            occurred_at=now - timedelta(minutes=index),
            metadata={"from_role": "COUNSELOR", "to_role": "INSTITUTIONAL_OFFICER"},
        )
        for index in range(4)
    ]
    client = auth_client(dpo)

    first = client.get(
        "/api/v1/privacy/activity?category=ACCESS_CONTROL&page=1&page_size=2"
    )
    second = client.get(
        "/api/v1/privacy/activity?category=ACCESS_CONTROL&page=2&page_size=2"
    )
    invalid = client.get("/api/v1/privacy/activity?page_size=51")

    assert first.status_code == second.status_code == 200
    assert [item["id"] for item in first.json()["items"]] == [
        str(events[0].pk),
        str(events[1].pk),
    ]
    assert [item["id"] for item in second.json()["items"]] == [
        str(events[2].pk),
        str(events[3].pk),
    ]
    assert invalid.status_code == 422


@pytest.mark.django_db
def test_privacy_activity_has_no_arbitrary_action_filter_or_global_audit_route():
    sync_policy()
    dpo = make_dpo("no-global-audit-dpo@example.edu")
    client = auth_client(dpo)

    arbitrary = client.get("/api/v1/privacy/activity?action=counseling.encounter.updated")
    assert arbitrary.status_code == 422
    assert client.get("/api/v1/privacy/audit-events").status_code == 404
