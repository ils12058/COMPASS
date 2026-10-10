"""Scope, projection, filtering and bulk-release boundaries for curated activity."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
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
from compass.activity.supervised import CAPABILITY, SUPERVISED_PRESENTERS, SupervisedActivityType
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.authentication.actions import (
    AUTH_LOGIN_FAILED,
    AUTH_LOGIN_SUCCESS,
    AUTH_MFA_TOTP_ENROLLED,
)
from compass.authentication.sessions import create_auth_session
from compass.organization.models import StaffSupervision
from compass.organization.services import remove_staff_supervisor, set_staff_supervisor
from compass.privacy_governance.activity import PrivacyActivityType
from compass.privacy_governance.activity_export import MAX_EXPORT_ROWS

EXPORT = "privacy_governance.activity.export"
VIEW = "privacy_governance.view"
SUP_PATH = "/api/v1/me/supervised-staff-activity"
PRIV_PATH = "/api/v1/privacy/activity"
PLAT_PATH = "/api/v1/platform/activity"


@pytest.fixture
def users(db):
    call_command("sync_identity_policy", stdout=StringIO())

    def make(name, role):
        return User.objects.create_user(
            email=f"synthetic-{uuid4()}@example.edu",
            password=None,
            role=Role.objects.get(code=role),
            first_name=name,
            last_name="Operator",
        )

    result = {
        "a": make("CounselorA", "COUNSELOR"),
        "b": make("CounselorB", "COUNSELOR"),
        "staff": make("José", "GUIDANCE_SERVICES_STAFF"),
        "other": make("OtherStaff", "GUIDANCE_SERVICES_STAFF"),
        "student": make("Student", "STUDENT"),
        "it": make("IT", "IT_ADMIN"),
        "dpo": make("DPO", "INSTITUTIONAL_OFFICER"),
        "head": make("Head", "COUNSELOR"),
    }
    for key, designation in (("dpo", "DPO"), ("head", "HEAD_GUIDANCE_COUNSELOR")):
        UserDesignation.objects.create(
            user=result[key], designation=Designation.objects.get(code=designation)
        )
    set_staff_supervisor(
        staff_id=result["staff"].pk,
        supervisor_id=result["a"].pk,
        context=AuditContext.user(result["it"]),
    )
    set_staff_supervisor(
        staff_id=result["other"].pk,
        supervisor_id=result["b"].pk,
        context=AuditContext.user(result["it"]),
    )
    return result


def client(user):
    issued = create_auth_session(user)
    result = Client()
    result.cookies["compass_session"] = issued.token
    return result


def event(user, action, target=None, at=None, metadata=None, target_id=None, outcome="SUCCESS"):
    return record_event(
        context=AuditContext.user(
            user, ip_address="203.0.113.11", user_agent_summary="PRIVATE-UA", request_id=uuid4()
        ),
        action=action,
        outcome=outcome,
        target_type=target,
        target_id=target_id if target_id is not None else (uuid4() if target else None),
        occurred_at=at or timezone.now(),
        metadata=metadata or {"internal_note": "HIDDEN-CONFIDENTIAL"},
    )


def override(user, capability, effect):
    return UserCapabilityOverride.objects.update_or_create(
        user=user, capability=Capability.objects.get(code=capability), defaults={"effect": effect}
    )


def ids(response):
    assert response.status_code == 200, response.content
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize(
    "key,allowed",
    [
        ("a", True),
        ("head", True),
        ("staff", False),
        ("student", False),
        ("it", False),
        ("dpo", False),
    ],
)
def test_supervised_capability_baselines_and_routes(users, key, allowed):
    assert users[key].has_capability(CAPABILITY) is allowed
    for path in (SUP_PATH, "/api/v1/me/supervised-staff"):
        assert client(users[key]).get(path).status_code == (200 if allowed else 403)
        assert Client().get(path).status_code == 401
    if allowed and key == "head":
        assert ids(client(users[key]).get(SUP_PATH)) == []
        assert client(users[key]).get("/api/v1/me/supervised-staff").json()["items"] == []


def test_overrides_preserve_capability_and_scope_independently(users):
    override(users["a"], CAPABILITY, "REVOKE")
    assert client(users["a"]).get(SUP_PATH).status_code == 403
    override(users["it"], CAPABILITY, "GRANT")
    assert ids(client(users["it"]).get(SUP_PATH)) == []
    assert client(users["it"]).get("/api/v1/me/supervised-staff").json()["items"] == []


def test_current_direct_scope_and_picker_exclude_other_staff_and_names(users):
    mine = event(users["staff"], actions.REFERRAL_CREATED, "referrals.referral")
    event(users["other"], actions.REFERRAL_CREATED, "referrals.referral")
    c = client(users["a"])
    assert ids(c.get(SUP_PATH)) == [str(mine.pk)]
    assert (
        ids(
            c.get(
                SUP_PATH, {"staff_id": str(users["other"].pk), "supervisor_id": str(users["b"].pk)}
            )
        )
        == []
    )
    picker = c.get("/api/v1/me/supervised-staff").json()
    assert picker["items"] == [{"id": str(users["staff"].pk), "display_name": "José Operator"}]
    assert "email" not in str(picker)
    assert "OtherStaff" not in str(picker)


def test_assignment_reassignment_noop_and_removal_boundaries(users):
    a, b, staff = users["a"], users["b"], users["staff"]
    row = StaffSupervision.objects.get(staff=staff)
    event(
        staff,
        actions.REFERRAL_CREATED,
        "referrals.referral",
        at=row.updated_at - timedelta(microseconds=1),
    )
    old = event(staff, actions.REFERRAL_CREATED, "referrals.referral")
    before = row.updated_at
    set_staff_supervisor(
        staff_id=staff.pk, supervisor_id=a.pk, context=AuditContext.user(users["it"])
    )
    row.refresh_from_db()
    assert row.updated_at == before  # a no-op cannot hide existing current-assignment work
    assert ids(client(a).get(SUP_PATH)) == [str(old.pk)]
    row = set_staff_supervisor(
        staff_id=staff.pk, supervisor_id=b.pk, context=AuditContext.user(users["it"])
    )
    new = event(staff, actions.REFERRAL_CREATED, "referrals.referral", at=row.updated_at)
    assert ids(client(b).get(SUP_PATH, {"staff_id": staff.pk})) == [str(new.pk)]
    assert ids(client(a).get(SUP_PATH)) == []  # intentionally no former-membership history
    remove_staff_supervisor(staff_id=staff.pk, context=AuditContext.user(users["it"]))
    assert ids(client(b).get(SUP_PATH, {"staff_id": staff.pk})) == []


@pytest.mark.parametrize("action", list(SUPERVISED_PRESENTERS))
def test_exact_operational_allowlist_validates_targets_and_never_reads_contents(users, action):
    _, _, target = SUPERVISED_PRESENTERS[action]
    good = event(users["staff"], action, target)
    event(users["staff"], action, "accounts.user")
    event(users["staff"], action, target, target_id="not-a-uuid")
    event(users["staff"], action, target, outcome="FAILED")
    response = client(users["a"]).get(SUP_PATH, {"event_type": action})
    assert ids(response) == [str(good.pk)]
    body = response.content.decode()
    for forbidden in (
        "HIDDEN-CONFIDENTIAL",
        "PRIVATE-UA",
        "203.0.113.11",
        "metadata",
        "target_id",
        "request_id",
        str(good.target_id),
    ):
        assert forbidden not in body


@pytest.mark.parametrize(
    "action,target",
    [
        (AUTH_LOGIN_SUCCESS, "accounts.user"),
        (AUTH_MFA_TOTP_ENROLLED, "auth.totpfactor"),
        ("auth.logout", "auth.session"),
        ("auth.session.revoked", "auth.session"),
        ("profile.updated", "accounts.user"),
        ("auth.password.reset", "accounts.user"),
        (actions.APPOINTMENT_CREATED, "appointments.appointment"),
        (actions.COUNSELING_ENCOUNTER_UPDATED, "counseling.encounter"),
    ],
)
def test_personal_security_and_unapproved_work_never_enters_supervision(users, action, target):
    event(users["staff"], action, target)
    assert ids(client(users["a"]).get(SUP_PATH)) == []


def test_supervised_search_staff_dates_and_projected_pagination_compose(users):
    boundary = timezone.now()
    StaffSupervision.objects.filter(staff=users["staff"]).update(
        updated_at=boundary - timedelta(days=10)
    )
    # Oct 4 in Asia/Manila begins at Oct 3 16:00 UTC.
    start = datetime(2026, 10, 3, 16, tzinfo=UTC)
    StaffSupervision.objects.filter(staff=users["staff"]).update(
        updated_at=start - timedelta(days=10)
    )
    included = [
        event(
            users["staff"],
            actions.REFERRAL_CREATED,
            "referrals.referral",
            at=start + timedelta(hours=n),
        )
        for n in range(3)
    ]
    event(
        users["staff"],
        actions.REFERRAL_CREATED,
        "referrals.referral",
        at=start - timedelta(microseconds=1),
    )
    event(
        users["staff"], actions.REFERRAL_CREATED, "referrals.referral", at=start + timedelta(days=1)
    )
    event(
        users["staff"],
        actions.REFERRAL_CREATED,
        "referrals.referral",
        at=start + timedelta(hours=4),
        target_id="bad",
    )
    c = client(users["a"])
    criteria = {
        "search": "josé",
        "event_type": actions.REFERRAL_CREATED,
        "staff_id": users["staff"].pk,
        "date_from": "2026-10-04",
        "date_to": "2026-10-04",
        "page_size": 1,
    }
    collected = []
    for page in range(1, 4):
        response = c.get(SUP_PATH, {**criteria, "page": page})
        collected += ids(response)
        assert response.json()["has_next"] == (page < 3)
    assert collected == [str(row.pk) for row in reversed(included)]
    assert ids(c.get(SUP_PATH, {"search": "HIDDEN-CONFIDENTIAL"})) == []
    assert len(ids(c.get(SUP_PATH, {"search": "Referral recorded"}))) == 5


@pytest.mark.parametrize(
    "path,key",
    [(SUP_PATH, "a"), (PLAT_PATH, "it"), (PRIV_PATH, "dpo"), (PRIV_PATH + "/export", "dpo")],
)
@pytest.mark.parametrize(
    "criteria",
    [
        {"event_type": "counseling.encounter.updated"},
        {"date_from": "2026-10-05", "date_to": "2026-10-04"},
        {"date_from": "not-a-date"},
        {"search": "x" * 101},
        {"date_to": "9999-12-31"},
    ],
)
def test_closed_types_and_invalid_criteria_fail_typed(users, path, key, criteria):
    response = client(users[key]).get(path, criteria)
    assert response.status_code == 422
    assert "error" in response.json()


def test_platform_matches_only_safe_presentation_and_operator_before_paging(users):
    now = timezone.now()
    good = [
        event(
            users["it"],
            actions.PLATFORM_MAINTENANCE_ENABLED,
            "platform.maintenance",
            target_id="1",
            at=now,
        )
        for _ in range(3)
    ]
    event(
        users["it"],
        actions.NOTIFICATION_EMAIL_RETRY_REQUESTED,
        "notifications.emaildelivery",
        target_id="bad",
        at=now + timedelta(seconds=1),
    )
    event(users["it"], actions.RETENTION_RULE_CREATED, "privacy.retention.rule")
    c = client(users["it"])
    criteria = {
        "search": "manual",
        "operator": "IT Operator",
        "event_type": actions.PLATFORM_MAINTENANCE_ENABLED,
        "date_from": now.astimezone().date().isoformat(),
        "page_size": 1,
    }
    rows = []
    for page in range(1, 4):
        rows += ids(c.get(PLAT_PATH, {**criteria, "page": page}))
    assert rows == [str(item.pk) for item in sorted(good, key=lambda x: x.pk, reverse=True)]
    assert ids(c.get(PLAT_PATH, {"search": "HIDDEN-CONFIDENTIAL"})) == []
    assert ids(c.get(PLAT_PATH, {"operator": users["dpo"].get_full_name()})) == []
    assert c.get(PLAT_PATH + "/export").status_code == 404


def test_privacy_filtered_paging_skips_malformed_without_duplicates_and_actor_suppression(users):
    now = timezone.now()
    good = [
        event(
            users["it"],
            actions.ACCOUNT_ROLE_CHANGED,
            "accounts.user",
            at=now,
            metadata={
                "from_role": "COUNSELOR",
                "to_role": "INSTITUTIONAL_OFFICER",
                "internal_note": "HIDDEN-CONFIDENTIAL",
            },
        )
        for _ in range(3)
    ]
    for _ in range(8):
        event(
            users["it"],
            actions.ACCOUNT_ROLE_CHANGED,
            "accounts.user",
            metadata={"from_role": "INVALID", "to_role": "COUNSELOR"},
        )
    event(users["it"], AUTH_LOGIN_FAILED, "accounts.user", outcome="DENIED")
    c = client(users["dpo"])
    criteria = {
        "search": "COUNSELOR",
        "actor": "IT",
        "category": "ACCESS_CONTROL",
        "event_type": actions.ACCOUNT_ROLE_CHANGED,
        "page_size": 1,
    }
    rows = []
    for page in range(1, 4):
        response = c.get(PRIV_PATH, {**criteria, "page": page})
        rows += ids(response)
        assert response.json()["has_next"] == (page < 3)
    assert rows == [str(item.pk) for item in sorted(good, key=lambda x: x.pk, reverse=True)]
    assert ids(c.get(PRIV_PATH, {"search": "HIDDEN-CONFIDENTIAL"})) == []
    assert ids(c.get(PRIV_PATH, {"actor": "IT", "category": "ACCOUNT_SECURITY"})) == []
    assert ids(c.get(PRIV_PATH, {"search": "IT", "category": "ACCOUNT_SECURITY"})) == []


def test_privacy_search_supports_visible_scope_artifact_format_and_reference(users):
    ref = uuid4()
    event(
        users["it"],
        actions.REPORT_EXPORT_RELEASED,
        "reports.studentprofiling",
        target_id=ref,
        metadata={
            "report_type": "student_profiling",
            "format": "XLSX",
            "academic_year_label": "2026-2027",
            "college_code": "CCMS",
        },
    )
    c = client(users["dpo"])
    for search in (
        "CCMS",
        "XLSX",
        "student_profiling",
        str(ref),
        "IT Operator",
        "Student Profiling",
    ):
        assert len(ids(c.get(PRIV_PATH, {"search": search}))) == 1


def test_new_and_historical_retention_events_survive_search_filter_and_export(users):
    for action, (_, _, target) in actions.RETENTION_PRESENTATIONS.items():
        event(users["dpo"], action, target, metadata={"internal_note": "HIDDEN-CONFIDENTIAL"})
    for action in (
        actions.PRIVACY_RETENTION_CREATED,
        actions.PRIVACY_RETENTION_UPDATED,
        actions.PRIVACY_RETENTION_RETIRED,
    ):
        event(users["dpo"], action, "privacy.retention")
    c = client(users["dpo"])
    listed = c.get(PRIV_PATH, {"category": "PRIVACY_GOVERNANCE", "page_size": 50})
    assert len(ids(listed)) == 14
    for item in listed.json()["items"]:
        assert (
            len(ids(c.get(PRIV_PATH, {"event_type": item["type"], "search": item["title"]}))) == 1
        )
    exported = c.get(PRIV_PATH + "/export", {"category": "PRIVACY_GOVERNANCE"})
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8"))))
    assert {row["Event Type"] for row in rows} == {item["type"] for item in listed.json()["items"]}
    assert "HIDDEN-CONFIDENTIAL" not in exported.content.decode()


@pytest.mark.parametrize("key", ["a", "head", "student", "staff", "it"])
def test_export_default_denial(users, key):
    assert not users[key].has_capability(EXPORT)
    assert client(users[key]).get(PRIV_PATH + "/export").status_code == 403


def test_export_capability_dependency_overrides_and_browse_only(users):
    assert users["dpo"].has_capability(EXPORT)
    override(users["dpo"], EXPORT, "REVOKE")
    assert client(users["dpo"]).get(PRIV_PATH).status_code == 200
    assert client(users["dpo"]).get(PRIV_PATH + "/export").status_code == 403
    override(users["it"], VIEW, "GRANT")
    override(users["it"], EXPORT, "GRANT")
    assert client(users["it"]).get(PRIV_PATH + "/export").status_code == 200
    override(users["it"], VIEW, "REVOKE")
    assert not users["it"].has_capability(EXPORT)
    assert client(users["it"]).get(PRIV_PATH + "/export").status_code == 403


def test_export_all_matching_not_page_and_safe_minimized_audit(users):
    now = timezone.now()
    for n in range(24):
        event(
            users["it"],
            actions.RETENTION_RULE_UPDATED,
            "privacy.retention.rule",
            at=now - timedelta(seconds=n),
        )
    c = client(users["dpo"])
    criteria = {
        "category": "PRIVACY_GOVERNANCE",
        "event_type": actions.RETENTION_RULE_UPDATED,
        "actor": "IT",
        "search": "draft updated",
    }
    assert len(ids(c.get(PRIV_PATH, criteria))) == 20
    response = c.get(PRIV_PATH + "/export", criteria)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert "COMPASS-Privacy-Activity-" in response["Content-Disposition"]
    assert response["Cache-Control"] == "no-store"
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
    assert len(rows) == 24
    assert rows[0]["Occurred At"].endswith("+08:00")
    assert set(rows[0]) == {
        "Occurred At",
        "Category",
        "Event Type",
        "Title",
        "Description",
        "Actor",
        "Artifact",
        "Format",
        "Scope",
        "Reference",
    }
    export = AuditEvent.objects.get(action=actions.PRIVACY_ACTIVITY_EXPORTED)
    assert export.metadata == {
        "exported_row_count": 24,
        "category": "PRIVACY_GOVERNANCE",
        "event_type": actions.RETENTION_RULE_UPDATED,
        "date_from": None,
        "date_to": None,
        "search_applied": True,
        "actor_applied": True,
    }
    assert "draft updated" not in str(export.metadata)
    for forbidden in (
        "HIDDEN-CONFIDENTIAL",
        "PRIVATE-UA",
        "203.0.113.11",
        "request_id",
        "metadata",
        "target_id",
    ):
        assert forbidden not in response.content.decode()
    assert len(ids(c.get(PRIV_PATH, {"event_type": actions.PRIVACY_ACTIVITY_EXPORTED}))) == 1


def test_export_snapshot_excludes_own_append_and_supports_unicode_formula_safety(users):
    users["it"].first_name = '=HYPERLINK("danger")'
    users["it"].last_name = "José 李"
    users["it"].save(update_fields=["first_name", "last_name"])
    event(
        users["it"],
        actions.REPORT_EXPORT_RELEASED,
        "reports.studentprofiling",
        metadata={
            "report_type": "student_profiling",
            "format": "XLSX",
            "academic_year_label": "@INJECTION",
        },
    )
    c = client(users["dpo"])
    response = c.get(PRIV_PATH + "/export")
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
    assert len(rows) == 1
    assert rows[0]["Actor"].startswith("'=HYPERLINK")
    assert "José 李" in rows[0]["Actor"]
    assert actions.PRIVACY_ACTIVITY_EXPORTED not in response.content.decode()
    assert len(ids(c.get(PRIV_PATH, {"event_type": actions.PRIVACY_ACTIVITY_EXPORTED}))) == 1


@pytest.mark.parametrize(
    "text", ["=1+1", "+SUM(1)", "-1+1", "@formula", "  =1", "\tvalue", "\rvalue", "\nvalue"]
)
def test_csv_formula_entry_points_are_neutralized(text):
    from compass.common.csv_export import spreadsheet_safe_text

    assert spreadsheet_safe_text(text) == "'" + text
    assert spreadsheet_safe_text("José 李") == "José 李"


def test_export_real_maximum_without_silent_truncation(users):
    assert MAX_EXPORT_ROWS == 10_000
    AuditEvent.objects.bulk_create(
        [
            AuditEvent(
                actor_type="USER",
                actor_user=users["it"],
                action=actions.ACCOUNT_ENABLED,
                outcome="SUCCESS",
                target_type="accounts.user",
                target_id=str(uuid4()),
                metadata={},
            )
            for _ in range(MAX_EXPORT_ROWS + 1)
        ],
        batch_size=1000,
    )
    response = client(users["dpo"]).get(
        PRIV_PATH + "/export", {"event_type": actions.ACCOUNT_ENABLED}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "privacy_activity_export_too_large"
    assert not AuditEvent.objects.filter(action=actions.PRIVACY_ACTIVITY_EXPORTED).exists()


def test_export_audit_failure_releases_no_csv(users, monkeypatch):
    from compass.privacy_governance import releases

    event(users["it"], actions.ACCOUNT_ENABLED, "accounts.user")

    def unavailable(**kwargs):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(releases, "record_event", unavailable)
    response = client(users["dpo"]).get(PRIV_PATH + "/export")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "release_audit_unavailable"
    assert response["Content-Type"].startswith("application/json")
    assert not AuditEvent.objects.filter(action=actions.PRIVACY_ACTIVITY_EXPORTED).exists()


def test_bounded_scan_fails_clearly_for_sparse_malformed_feed(users, monkeypatch):
    from compass.activity import retrieval

    monkeypatch.setattr(retrieval, "MAX_CANDIDATES", 2)
    for _ in range(3):
        event(
            users["it"],
            actions.ACCOUNT_ROLE_CHANGED,
            "accounts.user",
            metadata={"from_role": "bad", "to_role": "bad"},
        )
    c = client(users["dpo"])
    assert c.get(PRIV_PATH).status_code == 422
    assert c.get(PRIV_PATH + "/export").status_code == 422


@pytest.mark.parametrize("key", ["student", "staff", "a", "head"])
def test_self_activity_preserves_self_scope_and_rejects_cross_user_effect(users, key):
    own = event(users[key], AUTH_LOGIN_SUCCESS, "accounts.user", target_id=users[key].pk)
    event(users["it"], AUTH_LOGIN_SUCCESS, "accounts.user", target_id=users["it"].pk)
    c = client(users[key])
    for path in ("/api/v1/me/activity", "/api/v1/me/security-activity"):
        assert ids(
            c.get(path, {"another_user_id": users["it"].pk, "staff_id": users["it"].pk})
        ) == [str(own.pk)]


def test_openapi_closed_filters_and_self_contracts():
    from compass.api.v1.router import api

    schema = api.get_openapi_schema()
    for path in ("/api/v1/me/activity", "/api/v1/me/security-activity"):
        assert {p["name"] for p in schema["paths"][path]["get"]["parameters"]} == {
            "page",
            "page_size",
        }
        assert path + "/export" not in schema["paths"]
    for path, enum in ((SUP_PATH, SupervisedActivityType), (PRIV_PATH, PrivacyActivityType)):
        parameter = next(
            p for p in schema["paths"][path]["get"]["parameters"] if p["name"] == "event_type"
        )
        ref = parameter["schema"]["anyOf"][0]["$ref"].split("/")[-1]
        assert set(schema["components"]["schemas"][ref]["enum"]) == set(enum)
    assert "/api/v1/audit-events" not in schema["paths"]


@pytest.mark.parametrize(
    "metadata",
    [
        [],
        {"from_role": [], "to_role": "COUNSELOR"},
        {"from_role": "COUNSELOR", "to_role": {"invalid": True}},
    ],
)
def test_malformed_metadata_shapes_fail_closed_for_list_and_export(users, metadata):
    AuditEvent.objects.bulk_create(
        [
            AuditEvent(
                actor_type="USER",
                actor_user=users["it"],
                action=actions.ACCOUNT_ROLE_CHANGED,
                outcome="SUCCESS",
                target_type="accounts.user",
                target_id=str(uuid4()),
                metadata=metadata,
            )
        ]
    )
    c = client(users["dpo"])
    assert ids(c.get(PRIV_PATH)) == []
    response = c.get(PRIV_PATH + "/export")
    assert response.status_code == 200
    assert len(list(csv.DictReader(StringIO(response.content.decode())))) == 0
