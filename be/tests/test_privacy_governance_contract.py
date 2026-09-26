"""Consumer-facing Privacy Governance contract: stable conflicts, projections, and discovery."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from compass.privacy_governance.models import PrivacyIncident, PrivacyIncidentStatus
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_user,
    patch_json,
    post_json,
    processing_payload,
    sync_policy,
)
from tests.test_privacy_governance_expansion import notice_payload, retention_payload

ROOT = "/api/v1/privacy"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def revision_values(**overrides):
    values = {key: value for key, value in notice_payload().items() if key not in {"code", "name"}}
    return values | overrides


@pytest.mark.django_db
def test_privacy_conflicts_use_stable_codes_for_distinct_recoveries():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    student = auth_client(make_user("conflict-student@example.edu", role="STUDENT"))

    policy = post_json(dpo, f"{ROOT}/retention-policies", retention_payload())
    assert policy.status_code == 201
    policy_id = policy.json()["id"]
    duplicate_policy = post_json(dpo, f"{ROOT}/retention-policies", retention_payload())
    assert duplicate_policy.status_code == 409
    assert error_code(duplicate_policy) == "privacy_code_in_use"

    activity = post_json(
        dpo,
        f"{ROOT}/processing-activities",
        processing_payload() | {"retention_policy_id": policy_id},
    )
    assert activity.status_code == 201
    duplicate_activity = post_json(dpo, f"{ROOT}/processing-activities", processing_payload())
    assert error_code(duplicate_activity) == "privacy_code_in_use"

    in_use = post_json(dpo, f"{ROOT}/retention-policies/{policy_id}/retire", {})
    assert in_use.status_code == 409
    assert error_code(in_use) == "privacy_retention_policy_in_use"

    patch_json(
        dpo, f"{ROOT}/processing-activities/{activity.json()['id']}", {"retention_policy_id": None}
    )
    assert post_json(dpo, f"{ROOT}/retention-policies/{policy_id}/retire", {}).status_code == 200
    retired_assignment = post_json(
        dpo,
        f"{ROOT}/processing-activities",
        processing_payload("SECOND") | {"retention_policy_id": policy_id},
    )
    assert error_code(retired_assignment) == "privacy_retention_policy_retired"
    retired_edit = patch_json(dpo, f"{ROOT}/retention-policies/{policy_id}", {"name": "Renamed"})
    assert error_code(retired_edit) == "privacy_retention_policy_retired"

    future = notice_payload("FUTURE", effective_on=timezone.localdate() + timedelta(days=3))
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
        dpo, f"{ROOT}/notice-revisions/{draft_id}", {"effective_on": str(timezone.localdate())}
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
def test_resolved_records_and_invalid_incident_moves_have_stable_codes():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    activity = post_json(dpo, f"{ROOT}/processing-activities", processing_payload())
    review = post_json(
        dpo,
        f"{ROOT}/processing-activities/{activity.json()['id']}/reviews",
        {"review_type": "PIA", "scope_summary": "Initial scope"},
    )
    review_id = review.json()["id"]
    assert (
        post_json(
            dpo, f"{ROOT}/reviews/{review_id}/resolve", {"resolution_summary": "Closed"}
        ).status_code
        == 200
    )
    again = post_json(dpo, f"{ROOT}/reviews/{review_id}/resolve", {"resolution_summary": "Again"})
    assert error_code(again) == "privacy_record_resolved"
    edit = patch_json(dpo, f"{ROOT}/reviews/{review_id}", {"findings_summary": "Late"})
    assert error_code(edit) == "privacy_record_resolved"

    incident = post_json(
        dpo,
        f"{ROOT}/incidents",
        {
            "title": "Misdirected email",
            "summary": "Summary",
            "affected_area": "Email",
            "personal_data_categories": ["Contact data"],
            "discovered_at": timezone.now().isoformat(),
        },
    )
    incident_id = incident.json()["id"]
    assert (
        patch_json(dpo, f"{ROOT}/incidents/{incident_id}", {"status": "CONTAINED"}).status_code
        == 200
    )
    backward = patch_json(dpo, f"{ROOT}/incidents/{incident_id}", {"status": "OPEN"})
    assert error_code(backward) == "privacy_incident_status_invalid"
    via_update = patch_json(dpo, f"{ROOT}/incidents/{incident_id}", {"status": "RESOLVED"})
    assert error_code(via_update) == "privacy_incident_status_invalid"
    assert post_json(dpo, f"{ROOT}/incidents/{incident_id}/resolve", {}).status_code == 200
    resolved_again = post_json(dpo, f"{ROOT}/incidents/{incident_id}/resolve", {})
    assert error_code(resolved_again) == "privacy_record_resolved"


@pytest.mark.django_db
def test_review_projection_includes_processing_activity_summary_everywhere():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    activity = post_json(dpo, f"{ROOT}/processing-activities", processing_payload())
    activity_id = activity.json()["id"]
    created = post_json(
        dpo,
        f"{ROOT}/processing-activities/{activity_id}/reviews",
        {"review_type": "PRIVACY_REVIEW", "scope_summary": "Scope"},
    )
    expected = {"id": activity_id, "code": "COUNSELING-OPS", "name": "Counseling operations"}
    assert created.json()["processing_activity"] == expected
    review_id = created.json()["id"]

    detail = dpo.get(f"{ROOT}/reviews/{review_id}")
    assert detail.status_code == 200
    assert detail.json()["processing_activity"] == expected
    assert detail.json()["processing_activity_id"] == activity_id
    assert set(detail.json()["processing_activity"]) == {"id", "code", "name"}

    nested = dpo.get(f"{ROOT}/processing-activities/{activity_id}/reviews").json()["items"][0]
    global_item = dpo.get(f"{ROOT}/reviews").json()["items"][0]
    assert nested == global_item == detail.json()
    updated = patch_json(dpo, f"{ROOT}/reviews/{review_id}", {"findings_summary": "Found"})
    assert updated.json()["processing_activity"] == expected


@pytest.mark.django_db
def test_notice_family_projects_current_and_draft_revisions_without_n_plus_one(
    django_assert_max_num_queries,
):
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
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
    dpo = auth_client(make_dpo(), recent_mfa=True)
    future = timezone.localdate() + timedelta(days=2)
    created = post_json(dpo, f"{ROOT}/notices", notice_payload("READY", effective_on=future))
    notice_id = created.json()["id"]
    revision_id = created.json()["draft_revision"]["id"]

    def readiness():
        return dpo.get(f"{ROOT}/notice-revisions/{revision_id}").json()["publish_readiness"]

    assert readiness() == {"ready": False, "blocker": "EFFECTIVE_DATE_IN_FUTURE"}
    patch_json(dpo, f"{ROOT}/notice-revisions/{revision_id}", {"effective_on": None})
    assert readiness() == {"ready": False, "blocker": "EFFECTIVE_DATE_MISSING"}
    patch_json(
        dpo, f"{ROOT}/notice-revisions/{revision_id}", {"effective_on": str(timezone.localdate())}
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


@pytest.mark.django_db
def test_retention_policy_search_is_bounded_trimmed_and_composes_with_active_filter():
    sync_policy()
    dpo = auth_client(make_dpo(), recent_mfa=True)
    for code, name in (
        ("COUNSELING-RECORDS", "Counseling records"),
        ("ADMISSION-TESTS", "Admission testing results"),
        ("GENERAL-RECORDS", "General office correspondence"),
    ):
        created = post_json(
            dpo, f"{ROOT}/retention-policies", retention_payload() | {"code": code, "name": name}
        )
        assert created.status_code == 201
    retired = dpo.get(f"{ROOT}/retention-policies?search=general").json()["items"][0]
    post_json(dpo, f"{ROOT}/retention-policies/{retired['id']}/retire", {})

    by_name = dpo.get(f"{ROOT}/retention-policies?search=%20%20counseling%20").json()["items"]
    assert [item["code"] for item in by_name] == ["COUNSELING-RECORDS"]
    by_code = dpo.get(f"{ROOT}/retention-policies?search=admission-t").json()["items"]
    assert [item["code"] for item in by_code] == ["ADMISSION-TESTS"]
    records = dpo.get(f"{ROOT}/retention-policies?search=records").json()["items"]
    assert [item["code"] for item in records] == ["COUNSELING-RECORDS", "GENERAL-RECORDS"]
    active_records = dpo.get(f"{ROOT}/retention-policies?search=records&is_active=true").json()
    assert [item["code"] for item in active_records["items"]] == ["COUNSELING-RECORDS"]
    paged = dpo.get(f"{ROOT}/retention-policies?search=records&page_size=1").json()
    assert paged["has_next"] is True
    blank = dpo.get(f"{ROOT}/retention-policies?search=%20%20").json()["items"]
    assert len(blank) == 3

    too_long = dpo.get(f"{ROOT}/retention-policies?search={'x' * 161}")
    assert too_long.status_code == 422
    assert error_code(too_long) == "invalid_privacy_governance_input"


@pytest.mark.django_db
def test_incident_list_discovers_the_active_overview_population():
    sync_policy()
    dpo_user = make_dpo()
    dpo = auth_client(dpo_user, recent_mfa=True)
    for status in (
        PrivacyIncidentStatus.OPEN,
        PrivacyIncidentStatus.ASSESSING,
        PrivacyIncidentStatus.CONTAINED,
        PrivacyIncidentStatus.RESOLVED,
    ):
        incident = post_json(
            dpo,
            f"{ROOT}/incidents",
            {
                "title": f"Incident {status}",
                "summary": "Summary",
                "affected_area": "Area",
                "personal_data_categories": ["Contact data"],
                "discovered_at": timezone.now().isoformat(),
            },
        )
        PrivacyIncident.objects.filter(pk=incident.json()["id"]).update(status=status)

    active = dpo.get(f"{ROOT}/incidents?active=true&page_size=50").json()["items"]
    assert sorted(item["status"] for item in active) == ["ASSESSING", "CONTAINED", "OPEN"]
    inactive = dpo.get(f"{ROOT}/incidents?active=false").json()["items"]
    assert [item["status"] for item in inactive] == ["RESOLVED"]
    narrowed = dpo.get(f"{ROOT}/incidents?active=true&status=OPEN").json()["items"]
    assert [item["status"] for item in narrowed] == ["OPEN"]

    overview = dpo.get("/api/v1/overview").json()["privacy"]
    assert overview["active_incident_count"] == len(active)
