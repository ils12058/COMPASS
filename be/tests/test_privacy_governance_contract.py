"""Consumer-facing contract for retained Privacy Governance workflows."""

from __future__ import annotations

from datetime import timedelta

import pytest

from compass.common.institutional_time import institution_today
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


def error_code(response) -> str:
    return response.json()["error"]["code"]


def revision_values(**overrides):
    values = {key: value for key, value in notice_payload().items() if key not in {"code", "name"}}
    return values | overrides


@pytest.mark.django_db
def test_retained_privacy_conflicts_use_stable_codes_for_distinct_recoveries():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    student = auth_client(make_user("conflict-student@example.edu", role="STUDENT"))

    future = notice_payload("FUTURE", effective_on=institution_today() + timedelta(days=3))
    notice = post_json(dpo, f"{ROOT}/notices", future)
    notice_id = notice.json()["id"]
    draft_id = notice.json()["draft_revision"]["id"]
    duplicate_notice = post_json(dpo, f"{ROOT}/notices", future)
    assert error_code(duplicate_notice) == "privacy_code_in_use"

    draft_exists = post_json(dpo, f"{ROOT}/notices/{notice_id}/revisions", revision_values())
    assert error_code(draft_exists) == "privacy_notice_draft_exists"

    not_effective = post_json(dpo, f"{ROOT}/notice-revisions/{draft_id}/publish", {})
    assert error_code(not_effective) == "privacy_notice_not_yet_effective"
    patch_json(dpo, f"{ROOT}/notice-revisions/{draft_id}", {"effective_on": None})
    missing_date = post_json(dpo, f"{ROOT}/notice-revisions/{draft_id}/publish", {})
    assert error_code(missing_date) == "privacy_notice_not_yet_effective"
    patch_json(
        dpo, f"{ROOT}/notice-revisions/{draft_id}", {"effective_on": str(institution_today())}
    )
    assert post_json(dpo, f"{ROOT}/notice-revisions/{draft_id}/publish", {}).status_code == 200

    immutable_edit = patch_json(dpo, f"{ROOT}/notice-revisions/{draft_id}", {"body": "Changed"})
    assert error_code(immutable_edit) == "privacy_notice_revision_immutable"
    immutable_publish = post_json(dpo, f"{ROOT}/notice-revisions/{draft_id}/publish", {})
    assert error_code(immutable_publish) == "privacy_notice_revision_immutable"

    second = post_json(dpo, f"{ROOT}/notices/{notice_id}/revisions", revision_values())
    second_id = second.json()["id"]
    assert post_json(dpo, f"{ROOT}/notice-revisions/{second_id}/publish", {}).status_code == 200
    stale = post_json(student, f"{ROOT}/my-notices/{draft_id}/acknowledge", {})
    assert stale.status_code == 409
    assert error_code(stale) == "privacy_notice_revision_not_current"

    staff_only = post_json(dpo, f"{ROOT}/notices", notice_payload("STAFF-ONLY", ["STAFF"]))
    staff_revision = staff_only.json()["draft_revision"]["id"]
    post_json(dpo, f"{ROOT}/notice-revisions/{staff_revision}/publish", {})
    not_applicable = post_json(student, f"{ROOT}/my-notices/{staff_revision}/acknowledge", {})
    assert error_code(not_applicable) == "privacy_notice_acknowledgment_not_applicable"

    assert post_json(dpo, f"{ROOT}/notices/{notice_id}/retire", {}).status_code == 200
    retired_rename = patch_json(dpo, f"{ROOT}/notices/{notice_id}", {"name": "Renamed"})
    assert error_code(retired_rename) == "privacy_notice_retired"
    retired_revision = post_json(dpo, f"{ROOT}/notices/{notice_id}/revisions", revision_values())
    assert error_code(retired_revision) == "privacy_notice_retired"


@pytest.mark.django_db
def test_notice_family_projects_current_and_draft_revisions_without_n_plus_one(
    django_assert_max_num_queries,
):
    sync_policy()
    dpo = auth_client(make_dpo("projection-dpo@example.edu"), recent_mfa=True)
    created = post_json(dpo, f"{ROOT}/notices", notice_payload("FIRST"))
    body = created.json()
    assert body["current_revision"] is None
    assert body["draft_revision"]["revision_number"] == 1
    assert body["draft_revision"]["published_at"] is None
    first_id = body["draft_revision"]["id"]
    assert post_json(dpo, f"{ROOT}/notice-revisions/{first_id}/publish", {}).status_code == 200

    family = dpo.get(f"{ROOT}/notices/{body['id']}").json()
    assert family["current_revision"]["id"] == first_id
    assert family["current_revision"]["published_at"] is not None
    assert family["draft_revision"] is None

    second = post_json(dpo, f"{ROOT}/notices/{body['id']}/revisions", revision_values())
    family = dpo.get(f"{ROOT}/notices/{body['id']}").json()
    assert family["current_revision"]["id"] == first_id
    assert family["draft_revision"]["id"] == second.json()["id"]
    assert set(family["draft_revision"]) == {
        "id",
        "revision_number",
        "effective_on",
        "published_at",
    }

    for index in range(8):
        post_json(dpo, f"{ROOT}/notices", notice_payload(f"EXTRA-{index}"))
    dpo.get(f"{ROOT}/notices?page_size=50")
    with django_assert_max_num_queries(7):
        listed = dpo.get(f"{ROOT}/notices?page_size=50")
    assert listed.status_code == 200
    rows = {item["code"]: item for item in listed.json()["items"]}
    assert rows["FIRST"]["draft_revision"]["revision_number"] == 2
    assert rows["EXTRA-0"]["current_revision"] is None


@pytest.mark.django_db
def test_revision_publish_readiness_follows_server_date_and_state():
    sync_policy()
    dpo = auth_client(make_dpo("readiness-dpo@example.edu"), recent_mfa=True)
    future = institution_today() + timedelta(days=2)
    created = post_json(dpo, f"{ROOT}/notices", notice_payload("READY", effective_on=future))
    notice_id = created.json()["id"]
    revision_id = created.json()["draft_revision"]["id"]

    def readiness():
        return dpo.get(f"{ROOT}/notice-revisions/{revision_id}").json()["publish_readiness"]

    assert readiness() == {"ready": False, "blocker": "EFFECTIVE_DATE_IN_FUTURE"}
    patch_json(dpo, f"{ROOT}/notice-revisions/{revision_id}", {"effective_on": None})
    assert readiness() == {"ready": False, "blocker": "EFFECTIVE_DATE_MISSING"}
    patch_json(
        dpo, f"{ROOT}/notice-revisions/{revision_id}", {"effective_on": str(institution_today())}
    )
    assert readiness() == {"ready": True, "blocker": None}
    listed = dpo.get(f"{ROOT}/notices/{notice_id}/revisions").json()["items"][0]
    assert listed["publish_readiness"] == {"ready": True, "blocker": None}

    published = post_json(dpo, f"{ROOT}/notice-revisions/{revision_id}/publish", {})
    assert published.json()["publish_readiness"] == {
        "ready": False,
        "blocker": "REVISION_NOT_DRAFT",
    }

    other = post_json(dpo, f"{ROOT}/notices", notice_payload("RETIRING"))
    other_revision = other.json()["draft_revision"]["id"]
    post_json(dpo, f"{ROOT}/notices/{other.json()['id']}/retire", {})
    retired = dpo.get(f"{ROOT}/notice-revisions/{other_revision}").json()
    assert retired["publish_readiness"] == {"ready": False, "blocker": "NOTICE_RETIRED"}
