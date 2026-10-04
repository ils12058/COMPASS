"""The pending-acknowledgment view of My notices, and draft saves that build on a stale read."""

from __future__ import annotations

import pytest

from compass.privacy_governance.models import PrivacyNoticeRevision
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_user,
    patch_json,
    post_json,
    sync_policy,
)
from tests.test_privacy_governance_expansion import notice_payload

ROOT = "/api/v1/privacy"


def publish_notice(dpo, code, *, audiences=None, requires_acknowledgment=True):
    created = post_json(
        dpo,
        f"{ROOT}/notices",
        notice_payload(code, audiences) | {"requires_acknowledgment": requires_acknowledgment},
    )
    assert created.status_code == 201, created.content
    revision_id = created.json()["draft_revision"]["id"]
    published = post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {})
    assert published.status_code == 200, published.content
    return revision_id


def pending(client, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    response = client.get(f"{ROOT}/my-notices?pending_acknowledgment=true&{query}")
    assert response.status_code == 200, response.content
    return response.json()


@pytest.mark.django_db
def test_pending_view_lists_only_required_unacknowledged_notices_for_the_audience():
    sync_policy()
    dpo = auth_client(make_dpo("pending-dpo@example.edu"), recent_mfa=True)
    student = auth_client(make_user("pending-student@example.edu", role="STUDENT"))
    staff = auth_client(make_user("pending-staff@example.edu"))

    required = publish_notice(dpo, "A-REQUIRED", audiences=["STUDENT"])
    publish_notice(dpo, "B-INFORMATIONAL", audiences=["STUDENT"], requires_acknowledgment=False)
    publish_notice(dpo, "C-STAFF", audiences=["STAFF"])
    for_everyone = publish_notice(dpo, "D-PUBLIC", audiences=["PUBLIC"])

    items = pending(student)["items"]
    assert [item["revision_id"] for item in items] == [required, for_everyone]
    assert all(item["requires_acknowledgment"] and not item["acknowledged"] for item in items)
    assert [item["code"] for item in pending(staff)["items"]] == ["C-STAFF", "D-PUBLIC"]

    # Acknowledging removes a notice from the pending view; the history view keeps it.
    assert post_json(student, f"{ROOT}/my-notices/{required}/acknowledge", {}).status_code == 200
    assert [item["revision_id"] for item in pending(student)["items"]] == [for_everyone]
    history = student.get(f"{ROOT}/my-notices").json()["items"]
    assert {item["code"]: item["acknowledged"] for item in history} == {
        "A-REQUIRED": True,
        "B-INFORMATIONAL": False,
        "D-PUBLIC": False,
    }


@pytest.mark.django_db
def test_pending_notice_beyond_the_first_history_page_is_found_one_at_a_time():
    sync_policy()
    dpo = auth_client(make_dpo("paging-dpo@example.edu"), recent_mfa=True)
    student = auth_client(make_user("paging-student@example.edu", role="STUDENT"))
    for index in range(3):
        publish_notice(dpo, f"A-INFO-{index}", requires_acknowledgment=False)
    later_first = publish_notice(dpo, "Z-FIRST")
    later_second = publish_notice(dpo, "Z-SECOND")

    # The history page the Account page reads first does not reach the pending notices...
    first_history_page = student.get(f"{ROOT}/my-notices?page=1&page_size=3").json()
    assert all(not item["requires_acknowledgment"] for item in first_history_page["items"])

    # ...but the pending view returns them directly, one per request with page_size=1.
    first = pending(student, page_size=1)
    assert [item["revision_id"] for item in first["items"]] == [later_first]
    assert first["has_next"] is True
    assert post_json(student, f"{ROOT}/my-notices/{later_first}/acknowledge", {}).status_code == 200

    second = pending(student, page_size=1)
    assert [item["revision_id"] for item in second["items"]] == [later_second]
    assert second["has_next"] is False
    assert (
        post_json(student, f"{ROOT}/my-notices/{later_second}/acknowledge", {}).status_code == 200
    )

    assert pending(student, page_size=1)["items"] == []


@pytest.mark.django_db
def test_an_unacknowledged_notice_does_not_block_other_work():
    sync_policy()
    dpo = auth_client(make_dpo("nonblocking-dpo@example.edu"), recent_mfa=True)
    student = auth_client(make_user("nonblocking-student@example.edu", role="STUDENT"))
    publish_notice(dpo, "REQUIRED", audiences=["STUDENT"])

    assert pending(student)["items"]
    assert student.get("/api/v1/auth/session").status_code == 200
    assert student.get("/api/v1/appointments/me").status_code == 200


@pytest.mark.django_db
def test_draft_save_built_on_a_stale_read_is_a_conflict_and_changes_nothing():
    sync_policy()
    dpo = auth_client(make_dpo("draft-conflict-dpo@example.edu"))
    created = post_json(dpo, f"{ROOT}/notices", notice_payload("DRAFT-CONFLICT"))
    revision_id = created.json()["draft_revision"]["id"]
    read = dpo.get(f"{ROOT}/notice-revisions/{revision_id}").json()

    # Another editor saves first.
    elsewhere = patch_json(
        dpo,
        f"{ROOT}/notice-revisions/{revision_id}",
        {"title": "Saved elsewhere", "expected_updated_at": read["updated_at"]},
    )
    assert elsewhere.status_code == 200

    stale = patch_json(
        dpo,
        f"{ROOT}/notice-revisions/{revision_id}",
        {"title": "Built on the old read", "expected_updated_at": read["updated_at"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "privacy_notice_revision_changed"
    assert PrivacyNoticeRevision.objects.get(pk=revision_id).title == "Saved elsewhere"

    # Building on the latest saved version succeeds; omitting the check keeps working too.
    latest = elsewhere.json()["updated_at"]
    rebased = patch_json(
        dpo,
        f"{ROOT}/notice-revisions/{revision_id}",
        {"title": "Reviewed and saved", "expected_updated_at": latest},
    )
    assert rebased.status_code == 200
    unchecked = patch_json(dpo, f"{ROOT}/notice-revisions/{revision_id}", {"summary": "Updated"})
    assert unchecked.status_code == 200
