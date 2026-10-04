"""Retained Privacy Governance: notices and acknowledgment."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.privacy_governance.models import (
    PrivacyNotice,
    PrivacyNoticeAcknowledgment,
    PrivacyNoticeRevision,
)
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_user,
    patch_json,
    post_json,
    sync_policy,
)

ROOT = "/api/v1/privacy"


def notice_payload(code="NOTICE-1", audiences=None, effective_on=None):
    return {
        "code": code,
        "name": "Student Privacy Notice",
        "title": "Information notice",
        "audiences": audiences or ["PUBLIC", "STUDENT"],
        "summary": "A short human-entered notice summary.",
        "body": "Plain text\nwith two lines.",
        "requires_acknowledgment": True,
        "effective_on": str(effective_on or timezone.localdate()),
    }


@pytest.mark.django_db
def test_notice_lifecycle_public_self_acknowledgment_and_new_revision():
    sync_policy()
    dpo = auth_client(make_dpo("notice-lifecycle@example.edu"), recent_mfa=True)
    student = auth_client(make_user("student@example.edu", role="STUDENT"))
    staff = auth_client(make_user("staff@example.edu"))
    public = Client()
    created = post_json(dpo, f"{ROOT}/notices", notice_payload())
    assert created.status_code == 201, created.content
    notice_id = created.json()["id"]
    first = dpo.get(f"{ROOT}/notices/{notice_id}/revisions").json()["items"][0]
    first_id = first["id"]
    assert first["status"] == "DRAFT" and first["revision_number"] == 1
    assert public.get(f"{ROOT}/public-notices").json()["items"] == []
    assert post_json(dpo, f"{ROOT}/notice-revisions/{first_id}/publish", {}).status_code == 200
    public_item = public.get(f"{ROOT}/public-notices").json()["items"][0]
    assert public_item["revision_id"] == first_id
    assert "created_by" not in public_item and "published_by" not in public_item
    assert student.get(f"{ROOT}/my-notices").json()["items"][0]["acknowledged"] is False
    assert staff.get(f"{ROOT}/my-notices").json()["items"][0]["acknowledged"] is False
    assert post_json(student, f"{ROOT}/my-notices/{first_id}/acknowledge", {}).status_code == 200
    assert post_json(student, f"{ROOT}/my-notices/{first_id}/acknowledge", {}).status_code == 200
    assert PrivacyNoticeAcknowledgment.objects.filter(revision_id=first_id).count() == 1
    assert (
        patch_json(dpo, f"{ROOT}/notice-revisions/{first_id}", {"body": "Changed"}).status_code
        == 409
    )
    revision_values = {
        key: value for key, value in notice_payload().items() if key not in {"code", "name"}
    }
    second = post_json(
        dpo, f"{ROOT}/notices/{notice_id}/revisions", revision_values | {"body": "Correction"}
    )
    assert second.status_code == 201, second.content
    second_id = second.json()["id"]
    assert second.json()["revision_number"] == 2
    assert (
        post_json(dpo, f"{ROOT}/notices/{notice_id}/revisions", revision_values).status_code == 409
    )
    assert post_json(dpo, f"{ROOT}/notice-revisions/{second_id}/publish", {}).status_code == 200
    assert PrivacyNoticeRevision.objects.get(pk=first_id).status == "SUPERSEDED"
    assert student.get(f"{ROOT}/my-notices").json()["items"][0]["acknowledged"] is False
    assert post_json(student, f"{ROOT}/my-notices/{first_id}/acknowledge", {}).status_code == 409
    assert post_json(student, f"{ROOT}/my-notices/{second_id}/acknowledge", {}).status_code == 200
    assert PrivacyNoticeAcknowledgment.objects.count() == 2
    assert post_json(dpo, f"{ROOT}/notices/{notice_id}/retire", {}).status_code == 200
    assert public.get(f"{ROOT}/public-notices").json()["items"] == []
    assert student.get(f"{ROOT}/my-notices").json()["items"] == []
    assert PrivacyNoticeAcknowledgment.objects.count() == 2


@pytest.mark.django_db
def test_audiences_future_effective_date_and_publication_step_up():
    sync_policy()
    dpo_user = make_dpo("notice-audience-dpo@example.edu")
    dpo = auth_client(dpo_user, recent_mfa=True)
    no_mfa = auth_client(dpo_user)
    student = auth_client(make_user("audience-student@example.edu", role="STUDENT"))
    staff = auth_client(make_user("audience-staff@example.edu"))
    payload = notice_payload("STAFF-ONLY", ["STAFF"], timezone.localdate() + timedelta(days=1))
    assert (
        post_json(dpo, f"{ROOT}/notices", payload | {"audiences": ["STAFF", "STAFF"]}).status_code
        == 422
    )
    # Draft authoring needs no step-up; publishing the draft does.
    notice = post_json(no_mfa, f"{ROOT}/notices", payload)
    assert notice.status_code == 201, notice.content
    revision_id = dpo.get(f"{ROOT}/notices/{notice.json()['id']}/revisions").json()["items"][0][
        "id"
    ]
    assert (
        post_json(no_mfa, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 403
    )
    assert post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 409
    assert (
        patch_json(
            dpo,
            f"{ROOT}/notice-revisions/{revision_id}",
            {"effective_on": str(timezone.localdate())},
        ).status_code
        == 200
    )
    assert post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 200
    assert student.get(f"{ROOT}/my-notices").json()["items"] == []
    assert staff.get(f"{ROOT}/my-notices").json()["items"][0]["revision_id"] == revision_id
    assert post_json(student, f"{ROOT}/my-notices/{revision_id}/acknowledge", {}).status_code == 409
    assert post_json(staff, f"{ROOT}/my-notices/{revision_id}/acknowledge", {}).status_code == 200


@pytest.mark.django_db
def test_management_boundary_and_self_route_rejects_impersonation():
    sync_policy()
    dpo = auth_client(make_dpo("management-dpo@example.edu"), recent_mfa=True)
    ordinary = auth_client(make_user("ordinary@example.edu"))
    student = auth_client(make_user("self-student@example.edu", role="STUDENT"))
    assert ordinary.get(f"{ROOT}/notices").status_code == 403
    assert ordinary.get(f"{ROOT}/activity").status_code == 403
    assert post_json(ordinary, f"{ROOT}/notices", notice_payload()).status_code == 403
    assert student.get(f"{ROOT}/my-notices").status_code == 200

    created = post_json(dpo, f"{ROOT}/notices", notice_payload("SELF-NOTICE"))
    revision_id = dpo.get(f"{ROOT}/notices/{created.json()['id']}/revisions").json()["items"][0][
        "id"
    ]
    assert post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 200
    assert (
        post_json(
            student, f"{ROOT}/my-notices/{revision_id}/acknowledge", {"user_id": "someone-else"}
        ).status_code
        == 422
    )
    assert PrivacyNoticeAcknowledgment.objects.count() == 0


@pytest.mark.django_db
def test_audit_rollback_minimized_metadata_and_curated_activity():
    sync_policy()
    dpo = auth_client(make_dpo("audit-dpo@example.edu"), recent_mfa=True)
    with patch(
        "compass.privacy_governance.expansion.record_event",
        side_effect=RuntimeError("audit unavailable"),
    ):
        assert post_json(dpo, f"{ROOT}/notices", notice_payload()).status_code == 500
    assert PrivacyNotice.objects.count() == 0

    notice = post_json(dpo, f"{ROOT}/notices", notice_payload())
    assert notice.status_code == 201
    revision_id = dpo.get(f"{ROOT}/notices/{notice.json()['id']}/revisions").json()["items"][0][
        "id"
    ]
    with patch(
        "compass.privacy_governance.expansion.record_event",
        side_effect=RuntimeError("audit unavailable"),
    ):
        assert (
            post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 500
        )
    assert PrivacyNoticeRevision.objects.get(pk=revision_id).status == "DRAFT"
    assert post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {}).status_code == 200
    activity_types = {
        item["type"]
        for item in dpo.get(f"{ROOT}/activity?category=PRIVACY_GOVERNANCE").json()["items"]
    }
    assert "privacy.notice.revision.published" in activity_types
    for event in AuditEvent.objects.filter(action__startswith="privacy."):
        metadata = str(event.metadata)
        for sensitive in ("Plain text", "Institution-approved", "Human-reviewed", "human-entered"):
            assert sensitive not in metadata


@pytest.mark.django_db
def test_database_rejects_second_draft_and_duplicate_acknowledgment():
    sync_policy()
    actor = make_dpo("constraint-dpo@example.edu")
    dpo = auth_client(actor, recent_mfa=True)
    student_user = make_user("constraint-student@example.edu", role="STUDENT")
    student = auth_client(student_user)
    created = post_json(dpo, f"{ROOT}/notices", notice_payload("CONSTRAINT-NOTICE"))
    first = PrivacyNoticeRevision.objects.get(notice_id=created.json()["id"])
    with pytest.raises(IntegrityError), transaction.atomic():
        PrivacyNoticeRevision.objects.create(
            notice=first.notice,
            revision_number=2,
            created_by=actor,
            title="Second draft",
            audiences=["STUDENT"],
            summary="Summary",
            body="Body",
        )
    assert post_json(dpo, f"{ROOT}/notice-revisions/{first.pk}/publish", {}).status_code == 200
    assert post_json(student, f"{ROOT}/my-notices/{first.pk}/acknowledge", {}).status_code == 200
    with pytest.raises(IntegrityError), transaction.atomic():
        PrivacyNoticeAcknowledgment.objects.create(user=student_user, revision=first)
