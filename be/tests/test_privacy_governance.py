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
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.privacy_governance.models import (
    PrivacyIncident,
    PrivacyIncidentStatus,
    PrivacyNotificationAssessment,
    PrivacyReview,
    ProcessingActivity,
)
from compass.privacy_governance.services import (
    create_privacy_incident,
    create_privacy_review,
    create_processing_activity,
)


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


def processing_payload(code: str = "COUNSELING-OPS") -> dict[str, object]:
    return {
        "code": code,
        "name": "Counseling operations",
        "purpose": "Institution-entered purpose statement",
        "data_subject_categories": ["Students"],
        "personal_data_categories": ["Identity data", "Counseling administration metadata"],
        "authorized_access_summary": "Authorized institutional roles only",
        "safeguards_summary": "Institution-entered safeguards summary",
        "retention_policy_reference": "Institutional policy reference",
        "policy_basis_reference": "Institutional policy basis reference",
    }


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
    assert "privacy_governance.view" not in effective_capabilities(plain_officer)
    assert "privacy_governance.manage" not in effective_capabilities(plain_officer)
    assert "privacy_governance.view" not in effective_capabilities(admin)
    assert "privacy_governance.manage" not in effective_capabilities(admin)
    assert "privacy_governance.view" not in effective_capabilities(counselor)
    assert "privacy_governance.manage" not in effective_capabilities(counselor)
    assert "privacy_governance.view" not in effective_capabilities(head)
    assert "privacy_governance.manage" not in effective_capabilities(head)

    forbidden_dpo_capabilities = {
        "accounts.view",
        "accounts.manage",
        "platform_operations.view",
        "platform_operations.manage",
        "organization.view",
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
def test_dpo_reads_without_step_up_but_mutations_require_recent_mfa():
    sync_policy()
    dpo = make_dpo("mfa-dpo@example.edu")
    client = auth_client(dpo, recent_mfa=False)

    listing = client.get("/api/v1/privacy/processing-activities")
    assert listing.status_code == 200

    denied = post_json(
        client,
        "/api/v1/privacy/processing-activities",
        processing_payload(),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    recent = auth_client(dpo, recent_mfa=True)
    created = post_json(
        recent,
        "/api/v1/privacy/processing-activities",
        processing_payload(),
    )
    assert created.status_code == 201


@pytest.mark.django_db
def test_non_dpo_baselines_are_denied_privacy_routes_and_dpo_is_denied_operational_routes():
    sync_policy()
    admin = make_user("privacy-admin@example.edu", role="IT_ADMIN")
    counselor = make_user("privacy-counselor@example.edu", role="COUNSELOR")
    dpo = make_dpo("boundary-dpo@example.edu")

    assert auth_client(admin).get("/api/v1/privacy/processing-activities").status_code == 403
    assert auth_client(counselor).get("/api/v1/privacy/processing-activities").status_code == 403

    dpo_client = auth_client(dpo)
    assert dpo_client.get("/api/v1/accounts").status_code == 403
    assert dpo_client.get("/api/v1/platform/health").status_code == 403
    assert dpo_client.get("/api/v1/reports/student-profile").status_code == 403


@pytest.mark.django_db
def test_processing_register_crud_retire_bounds_and_no_hard_delete():
    sync_policy()
    dpo = make_dpo("processing-dpo@example.edu")
    client = auth_client(dpo, recent_mfa=True)

    created = post_json(
        client,
        "/api/v1/privacy/processing-activities",
        processing_payload(),
    )
    assert created.status_code == 201
    body = created.json()
    processing_id = body["id"]
    assert body["code"] == "COUNSELING-OPS"
    assert body["is_active"] is True

    duplicate = post_json(
        client,
        "/api/v1/privacy/processing-activities",
        processing_payload(),
    )
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/privacy/processing-activities?is_active=true")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [processing_id]

    detail = client.get(f"/api/v1/privacy/processing-activities/{processing_id}")
    assert detail.status_code == 200

    updated = patch_json(
        client,
        f"/api/v1/privacy/processing-activities/{processing_id}",
        {
            "purpose": "Updated institution-entered purpose",
            "personal_data_categories": ["Identity data", "Contact data"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["purpose"] == "Updated institution-entered purpose"

    retired = post_json(
        client,
        f"/api/v1/privacy/processing-activities/{processing_id}/retire",
        {},
    )
    assert retired.status_code == 200
    assert retired.json()["is_active"] is False
    assert client.get(f"/api/v1/privacy/processing-activities/{processing_id}").status_code == 200

    too_many = processing_payload("TOO-MANY")
    too_many["personal_data_categories"] = [f"Category {index}" for index in range(33)]
    assert post_json(client, "/api/v1/privacy/processing-activities", too_many).status_code == 422

    nested = processing_payload("NESTED")
    nested["personal_data_categories"] = [{"name": "not allowed"}]
    assert post_json(client, "/api/v1/privacy/processing-activities", nested).status_code == 422

    unexpected = processing_payload("EXTRA")
    unexpected["sample_student_record"] = {"name": "must not be accepted"}
    assert post_json(client, "/api/v1/privacy/processing-activities", unexpected).status_code == 422

    deleted = client.delete(
        f"/api/v1/privacy/processing-activities/{processing_id}",
        **csrf(client),
    )
    assert deleted.status_code in {404, 405}


@pytest.mark.django_db
def test_processing_audit_is_transactional_and_failure_rolls_back(monkeypatch):
    sync_policy()
    dpo = make_dpo("processing-rollback@example.edu")

    monkeypatch.setattr(
        "compass.privacy_governance.services.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic audit failure")),
    )
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        create_processing_activity(
            actor=dpo,
            context=AuditContext.user(dpo),
            **processing_payload("ROLLBACK"),
        )

    assert not ProcessingActivity.objects.filter(code="ROLLBACK").exists()


@pytest.mark.django_db
def test_privacy_review_lifecycle_actor_audit_and_no_delete():
    sync_policy()
    dpo = make_dpo("review-dpo@example.edu")
    client = auth_client(dpo, recent_mfa=True)
    processing = post_json(
        client,
        "/api/v1/privacy/processing-activities",
        processing_payload("REVIEWED"),
    ).json()

    created = post_json(
        client,
        f"/api/v1/privacy/processing-activities/{processing['id']}/reviews",
        {
            "review_type": "PIA",
            "scope_summary": "Institution-entered review scope",
            "findings_summary": "Initial findings",
            "recommendations_summary": "Initial recommendations",
        },
    )
    assert created.status_code == 201
    review_id = created.json()["id"]
    assert created.json()["status"] == "OPEN"
    assert created.json()["reviewed_by"]["id"] == str(dpo.pk)

    listing = client.get(f"/api/v1/privacy/processing-activities/{processing['id']}/reviews")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == review_id
    assert client.get(f"/api/v1/privacy/reviews/{review_id}").status_code == 200

    updated = patch_json(
        client,
        f"/api/v1/privacy/reviews/{review_id}",
        {"findings_summary": "Updated findings"},
    )
    assert updated.status_code == 200

    resolved = post_json(
        client,
        f"/api/v1/privacy/reviews/{review_id}/resolve",
        {"resolution_summary": "Human-entered resolution"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolved_at"] is not None

    rejected = patch_json(
        client,
        f"/api/v1/privacy/reviews/{review_id}",
        {"findings_summary": "Rewrite after resolution"},
    )
    assert rejected.status_code == 409

    deleted = client.delete(f"/api/v1/privacy/reviews/{review_id}", **csrf(client))
    assert deleted.status_code in {404, 405}

    assert set(
        AuditEvent.objects.filter(
            target_type="privacy.review",
            target_id=review_id,
        ).values_list("action", flat=True)
    ) == {
        "privacy.review.created",
        "privacy.review.updated",
        "privacy.review.resolved",
    }


@pytest.mark.django_db
def test_review_audit_failure_rolls_back_creation(monkeypatch):
    sync_policy()
    dpo = make_dpo("review-rollback@example.edu")
    processing = create_processing_activity(
        actor=dpo,
        context=AuditContext.user(dpo),
        **processing_payload("REVIEW-ROLLBACK"),
    )

    monkeypatch.setattr(
        "compass.privacy_governance.services.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("review audit failed")),
    )
    with pytest.raises(RuntimeError, match="review audit failed"):
        create_privacy_review(
            actor=dpo,
            context=AuditContext.user(dpo),
            processing_id=processing.pk,
            review_type="PRIVACY_REVIEW",
            scope_summary="Synthetic scope",
        )
    assert PrivacyReview.objects.count() == 0


@pytest.mark.django_db
def test_incident_lifecycle_reference_human_notification_assessment_and_no_attachment():
    sync_policy()
    dpo = make_dpo("incident-dpo@example.edu")
    client = auth_client(dpo, recent_mfa=True)

    created = post_json(
        client,
        "/api/v1/privacy/incidents",
        {
            "title": "Suspected privacy incident",
            "summary": "Governance summary only; no leaked dataset is stored here.",
            "affected_area": "Account security",
            "personal_data_categories": ["Account identity"],
            "discovered_at": timezone.now(),
            "estimated_affected_subjects": 3,
            "notification_assessment": "REQUIRED",
            "notification_reference": "Human-entered institutional reference",
        },
    )
    assert created.status_code == 201
    body = created.json()
    incident_id = body["id"]
    assert body["reference_code"].startswith("PRI-")
    assert body["status"] == "OPEN"
    assert body["notification_assessment"] == "REQUIRED"

    listing = client.get("/api/v1/privacy/incidents?status=OPEN")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == incident_id
    assert client.get(f"/api/v1/privacy/incidents/{incident_id}").status_code == 200

    assessing = patch_json(
        client,
        f"/api/v1/privacy/incidents/{incident_id}",
        {
            "status": "ASSESSING",
            "assessment_summary": "Human assessment in progress",
        },
    )
    assert assessing.status_code == 200

    contained = patch_json(
        client,
        f"/api/v1/privacy/incidents/{incident_id}",
        {
            "status": "CONTAINED",
            "containment_summary": "Human-entered containment summary",
        },
    )
    assert contained.status_code == 200

    backward = patch_json(
        client,
        f"/api/v1/privacy/incidents/{incident_id}",
        {"status": "OPEN"},
    )
    assert backward.status_code == 409

    resolved = post_json(
        client,
        f"/api/v1/privacy/incidents/{incident_id}/resolve",
        {},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolved_at"] is not None

    rewrite = patch_json(
        client,
        f"/api/v1/privacy/incidents/{incident_id}",
        {"summary": "Must not rewrite resolved history"},
    )
    assert rewrite.status_code == 409

    negative = post_json(
        client,
        "/api/v1/privacy/incidents",
        {
            "title": "Invalid estimate",
            "summary": "Synthetic",
            "affected_area": "Synthetic",
            "personal_data_categories": [],
            "discovered_at": timezone.now(),
            "estimated_affected_subjects": -1,
        },
    )
    assert negative.status_code == 422

    attachment = post_json(
        client,
        "/api/v1/privacy/incidents",
        {
            "title": "No attachments",
            "summary": "Synthetic",
            "affected_area": "Synthetic",
            "personal_data_categories": [],
            "discovered_at": timezone.now(),
            "attachment": "data:application/pdf;base64,forbidden",
        },
    )
    assert attachment.status_code == 422

    deleted = client.delete(f"/api/v1/privacy/incidents/{incident_id}", **csrf(client))
    assert deleted.status_code in {404, 405}

    assert not {
        "attachment",
        "file",
        "upload",
        "dataset",
    } & {field.name for field in PrivacyIncident._meta.get_fields()}


@pytest.mark.django_db
def test_incident_audit_failure_rolls_back_creation(monkeypatch):
    sync_policy()
    dpo = make_dpo("incident-rollback@example.edu")

    monkeypatch.setattr(
        "compass.privacy_governance.services.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("incident audit failed")),
    )
    with pytest.raises(RuntimeError, match="incident audit failed"):
        create_privacy_incident(
            context=AuditContext.user(dpo),
            title="Rollback incident",
            summary="Synthetic summary",
            affected_area="Synthetic area",
            personal_data_categories=["Identity"],
            discovered_at=timezone.now(),
        )

    assert PrivacyIncident.objects.count() == 0


@pytest.mark.django_db
def test_privacy_mutation_audit_metadata_never_copies_governance_narratives():
    sync_policy()
    dpo = make_dpo("metadata-dpo@example.edu")
    sentinel = "SENTINEL CONFIDENTIAL GOVERNANCE NARRATIVE"
    item = create_privacy_incident(
        context=AuditContext.user(dpo),
        title="Metadata safety",
        summary=sentinel,
        affected_area="Synthetic",
        personal_data_categories=["Identity"],
        discovered_at=timezone.now(),
        assessment_summary=sentinel,
        notification_assessment=PrivacyNotificationAssessment.NOT_ASSESSED,
    )

    event = AuditEvent.objects.get(
        action="privacy.incident.created",
        target_id=str(item.pk),
    )
    serialized = json.dumps(event.metadata)
    assert sentinel not in serialized
    assert event.metadata == {
        "reference_code": item.reference_code,
        "status": PrivacyIncidentStatus.OPEN,
    }
