"""In-app disposition is retired (ADR-114): refusal, tombstones, preflight and preserved history.

All data is synthetic. No test exercises a destructive path: the legacy ledger and historical
outcomes are written directly by ``tests.legacy_disposition_fixtures``.
"""

import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.accounts.services import effective_capabilities
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.authentication.models import TOTPFactor
from compass.common.errors import APIError
from compass.common.institutional_time import institution_today
from compass.common.json_logging import JsonFormatter
from compass.ecounseling.media import process_media_webhook_event
from compass.graduate_tracer.disposition import ANALYTICAL_FIELDS, verify_anonymized
from compass.graduate_tracer.models import (
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerTraining,
)
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.integrations.daily import DailyClient
from compass.privacy_governance import retention
from compass.privacy_governance.retention_models import (
    DispositionCase,
    DispositionHold,
    OperationalRetentionRule,
)
from compass.privacy_governance.tasks import (
    TOMBSTONE_TASK_NAMES,
    discover_retention,
    execute_disposition,
    recover_disposition,
)
from compass.reports.graduate_tracer import build_graduate_tracer_report
from config.celery import app
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.legacy_disposition_fixtures import (
    historical_anonymized_contribution,
    historically_disposed_media,
    legacy_case,
    legacy_media_source,
    legacy_rule,
)
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_head,
    make_user,
    patch_json,
    post_json,
    sync_policy,
)

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/privacy/retention"
CAPS = {f"privacy_governance.retention.{suffix}" for suffix in ("view", "manage", "approve")}
TOMBSTONES = (discover_retention, execute_disposition, recover_disposition)


@pytest.fixture
def dpo():
    sync_policy()
    return make_dpo()


def rule_values(category="GRADUATE_TRACER"):
    trigger, action = retention.SUPPORTED[category]
    return {
        "code": "SYNTHETIC-TEST",
        "label": "Synthetic test rule",
        "category": category,
        "trigger": trigger,
        "action": action,
        "duration_days": 30,
        "policy_reference": "TEST FIXTURE ONLY - not institutional policy",
        "effective_on": institution_today(),
    }


def tracer(email="graduate@example.edu", **values):
    student = make_user(email, role="STUDENT")
    student.student_lifecycle_status = "GRADUATED"
    student.save()
    return encrypted_row(
        GraduateTracerResponse,
        student=student,
        status="SUBMITTED",
        submitted_at=timezone.now() - timedelta(days=31),
        name_snapshot="Confidential Name",
        email_snapshot="private@example.edu",
        permanent_address_snapshot="Private address",
        telephone_contact_numbers_snapshot="secret-phone",
        mobile_number_snapshot="secret-mobile",
        province="specific-location",
        curriculum_improvement_suggestions="Confidential curriculum narrative",
        present_occupation="Specific named employer",
        sex="FEMALE",
        current_employment_state="EMPLOYED",
        employer_business_line="EDUCATION",
        **values,
    )


def stepped_up(user):
    TOTPFactor.objects.get_or_create(
        user=user, defaults={"encrypted_secret": "test-only", "confirmed_at": timezone.now()}
    )
    return auth_client(user, recent_mfa=True)


def grant_overrides(user, effect="GRANT"):
    for code in CAPS:
        UserCapabilityOverride.objects.update_or_create(
            user=user,
            capability=Capability.objects.get(code=code),
            defaults={"effect": effect, "reason": "Synthetic exceptional authority"},
        )


def ledger_snapshot():
    """Every legacy ledger value plus the audit trail, for exact before/after comparison."""
    return (
        list(OperationalRetentionRule.objects.order_by("pk").values()),
        list(DispositionCase.objects.order_by("pk").values()),
        list(DispositionHold.objects.order_by("pk").values()),
        list(AuditEvent.objects.order_by("occurred_at", "pk").values("pk", "action", "metadata")),
    )


def legacy_world(dpo):
    """A historical ledger with one case in every engine state and an active hold."""
    rule = legacy_rule(actor=dpo, status="ACTIVE")
    retired = legacy_rule(actor=dpo, category="ECOUNSELING_RECORDING")
    cases = {}
    for index, state in enumerate(
        (
            "READY",
            "ON_HOLD",
            "BLOCKED",
            "NO_LONGER_ELIGIBLE",
            "APPROVED",
            "QUEUED",
            "PROCESSING",
            "FAILED",
            "RECONCILIATION_REQUIRED",
        )
    ):
        source = tracer(f"legacy-{index}@example.edu")
        cases[state] = legacy_case(
            rule=rule,
            source=source,
            state=state,
            blocker="PROVIDER_UNVERIFIED" if state == "RECONCILIATION_REQUIRED" else None,
            hold_reason="Synthetic administrative hold" if state == "ON_HOLD" else None,
        )
    capture, _ = legacy_media_source("RECORDING")
    historically_disposed_media(capture)
    cases["COMPLETED"] = legacy_case(rule=retired, source=capture, state="COMPLETED")
    return rule, cases


# --- Celery decommission ------------------------------------------------------------------------


def test_beat_schedule_has_no_retention_entries_and_keeps_unrelated_schedules():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "retention-eligibility-discovery" not in schedule
    assert "retention-approved-dispatch-recovery" not in schedule
    assert not any(
        entry["task"].startswith("compass.privacy_governance.") for entry in schedule.values()
    )
    assert {
        "ecounseling-artifact-recovery": "compass.ecounseling.recover_media_artifacts",
        "notification-push-recovery": "compass.notifications.push.dispatch_due",
        "notification-email-recovery": "compass.notifications.email.dispatch_due",
        "email-change-security-alert-recovery": (
            "compass.authentication.email_change.recover_unsent_alerts"
        ),
    }.items() <= {name: entry["task"] for name, entry in schedule.items()}.items()


def test_tombstone_names_stay_registered_beside_unrelated_tasks():
    app.autodiscover_tasks(force=True)
    registered = set(app.tasks)
    assert set(TOMBSTONE_TASK_NAMES) <= registered
    assert {
        "compass.ecounseling.ingest_media_artifact",
        "compass.ecounseling.recover_media_artifacts",
        "compass.notifications.email.dispatch_due",
        "compass.infrastructure.noop",
    } <= registered
    assert {task.name for task in TOMBSTONES} == set(TOMBSTONE_TASK_NAMES)


def test_tombstones_never_touch_the_database_providers_storage_or_the_broker(dpo):
    rule, cases = legacy_world(dpo)
    queued = cases["QUEUED"]
    before = ledger_snapshot()
    sources = list(GraduateTracerResponse.objects.order_by("pk").values())

    def forbidden(*args, **kwargs):
        raise AssertionError("A retired disposition task reached an external boundary.")

    with (
        patch.object(DailyClient, "from_settings", side_effect=forbidden),
        patch("compass.integrations.storage.ObjectStorage.__init__", side_effect=forbidden),
        patch("celery.app.task.Task.apply_async", side_effect=forbidden),
        CaptureQueriesContext(connection) as queries,
    ):
        for _ in range(2):  # repeated delivery
            execute_disposition(str(queued.pk))
            execute_disposition(str(cases["PROCESSING"].pk))
            discover_retention()
            recover_disposition()
    assert len(queries) == 0
    assert ledger_snapshot() == before
    assert list(GraduateTracerResponse.objects.order_by("pk").values()) == sources
    queued.refresh_from_db()
    assert queued.state == "QUEUED" and queued.completed_at is None
    assert not GraduateTracerResponse.objects.filter(anonymized_at__isnull=False).exists()
    assert not GraduateTracerDisposedParticipation.objects.exists()


def test_redelivered_broker_messages_are_acknowledged_without_effect(dpo):
    _, cases = legacy_world(dpo)
    before = ledger_snapshot()
    for task, args in (
        (execute_disposition, [str(cases["QUEUED"].pk)]),
        (execute_disposition, [str(cases["APPROVED"].pk)]),
        (discover_retention, []),
        (recover_disposition, []),
    ):
        for redelivered in (False, True, True):
            result = task.apply(
                args=args, task_id=str(uuid.uuid4()), headers={"redelivered": redelivered}
            )
            assert result.successful() and result.result is None
    assert ledger_snapshot() == before
    assert DispositionCase.objects.get(pk=cases["QUEUED"].pk).state == "QUEUED"


class CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_tombstone_diagnostic_is_minimized():
    case_id = str(uuid.uuid4())
    logger = logging.getLogger("compass.privacy_governance")
    handler = CapturingHandler()
    logger.addHandler(handler)
    try:
        execute_disposition(case_id)
        execute_disposition(case_id=case_id)
    finally:
        logger.removeHandler(handler)
    assert len(handler.records) == 2
    for record in handler.records:
        payload = json.loads(JsonFormatter().format(record))
        assert payload["event"] == "retention_task_decommissioned"
        assert payload["task_name"] == "compass.privacy_governance.execute_disposition"
        assert payload["outcome_code"] == "DECOMMISSIONED"
        assert case_id not in json.dumps(payload) and case_id not in record.getMessage()


# --- Mutation refusal ---------------------------------------------------------------------------


def mutation_requests(rule, case):
    update = {k: v for k, v in rule_values().items() if k != "code"}
    revision = {"expected_revision": 1}
    return [
        ("POST", f"{ROOT}/rules", rule_values()),
        ("PATCH", f"{ROOT}/rules/{rule.pk}", update | revision),
        ("POST", f"{ROOT}/rules/{rule.pk}/activate", revision),
        ("POST", f"{ROOT}/rules/{rule.pk}/retire", revision),
        ("POST", f"{ROOT}/cases/{case.pk}/hold", revision | {"reason": "Synthetic hold"}),
        ("POST", f"{ROOT}/cases/{case.pk}/release-hold", revision),
        ("POST", f"{ROOT}/cases/{case.pk}/approve", revision),
        ("POST", f"{ROOT}/cases/{case.pk}/retry", revision),
    ]


def send(client, method, path, payload):
    return (post_json if method == "POST" else patch_json)(client, path, payload)


@pytest.mark.parametrize("holder", ["dpo", "override"])
def test_every_retention_mutation_route_is_refused_for_any_authority(
    dpo, holder, django_capture_on_commit_callbacks
):
    rule, cases = legacy_world(dpo)
    actor = dpo
    if holder == "override":
        actor = make_user("exceptional-authority@example.edu")
        grant_overrides(actor)
        assert CAPS <= effective_capabilities(actor)
    client = stepped_up(actor)
    before = ledger_snapshot()
    targets = [cases["READY"], cases["ON_HOLD"], cases["FAILED"], cases["QUEUED"]]
    with (
        patch("celery.app.task.Task.apply_async") as dispatch,
        django_capture_on_commit_callbacks(execute=True) as callbacks,
    ):
        for case in targets:
            for method, path, payload in mutation_requests(rule, case):
                response = send(client, method, path, payload)
                assert response.status_code == 409, (path, response.content)
                error = response.json()["error"]
                assert error["code"] == "retention_decommissioned"
                assert error["message"] == retention.DECOMMISSIONED_MESSAGE
    dispatch.assert_not_called()
    assert callbacks == []
    assert ledger_snapshot() == before


def test_service_refusal_precedes_every_query_lock_and_write():
    calls = [
        lambda: retention.create_rule(actor=None, values={}, context=None),
        lambda: retention.update_rule(
            actor=None, rule_id=uuid.uuid4(), expected_revision=1, values={}, context=None
        ),
        lambda: retention.transition_rule(
            actor=None, rule_id=uuid.uuid4(), expected_revision=1, activate=True, context=None
        ),
        lambda: retention.transition_rule(
            actor=None, rule_id=uuid.uuid4(), expected_revision=1, activate=False, context=None
        ),
        lambda: retention.change_hold(
            actor=None,
            case_id=uuid.uuid4(),
            expected_revision=1,
            reason="x",
            release=False,
            context=None,
        ),
        lambda: retention.change_hold(
            actor=None,
            case_id=uuid.uuid4(),
            expected_revision=1,
            reason=None,
            release=True,
            context=None,
        ),
        lambda: retention.approve_case(
            actor=None, case_id=uuid.uuid4(), expected_revision=1, context=None
        ),
        lambda: retention.approve_case(
            actor=None, case_id=uuid.uuid4(), expected_revision=1, context=None, retry=True
        ),
    ]
    with CaptureQueriesContext(connection) as queries:
        for call in calls:
            with pytest.raises(APIError) as refused:
                call()
            assert refused.value.status_code == 409
            assert refused.value.code == "retention_decommissioned"
    assert len(queries) == 0


@pytest.mark.parametrize(
    "role", ["INSTITUTIONAL_OFFICER", "IT_ADMIN", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT"]
)
def test_existing_authorization_boundary_still_applies_first(dpo, role):
    other = make_user("other@example.edu", role=role)
    assert CAPS.isdisjoint(effective_capabilities(other))
    client = stepped_up(other)
    assert client.get(f"{ROOT}/summary").status_code == 403
    assert post_json(client, f"{ROOT}/rules", rule_values()).status_code == 403


def test_step_up_boundary_is_unchanged_before_refusal(dpo):
    rule, cases = legacy_world(dpo)
    client = auth_client(dpo)
    for path in (f"{ROOT}/rules/{rule.pk}/activate", f"{ROOT}/cases/{cases['READY'].pk}/approve"):
        response = post_json(client, path, {"expected_revision": 1})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "mfa_setup_required"
    # Drafting routes never required step-up; they now refuse instead of creating a draft.
    response = post_json(client, f"{ROOT}/rules", rule_values())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "retention_decommissioned"
    assert not OperationalRetentionRule.objects.filter(code="SYNTHETIC-TEST").exists()


def test_dpo_capabilities_unchanged_and_without_confidential_content(dpo):
    assert CAPS <= effective_capabilities(dpo)
    assert CAPS.isdisjoint(effective_capabilities(make_head()))
    assert not any(
        code.startswith(
            (
                "counseling.",
                "inventory.",
                "graduate_tracer.",
                "ecounseling.",
                "exit_interviews.",
                "referrals.",
                "routine_interviews.",
            )
        )
        for code in effective_capabilities(dpo)
    )
    assert auth_client(dpo).get("/api/v1/graduate-tracer/responses").status_code == 403


# --- Historical preservation --------------------------------------------------------------------


def test_read_endpoints_serve_the_historical_ledger_without_source_identifiers(dpo):
    rule, cases = legacy_world(dpo)
    before = ledger_snapshot()
    client = auth_client(dpo)
    summary = client.get(f"{ROOT}/summary").json()
    assert summary["needs_review"] == 1 and summary["on_hold"] == 1
    assert summary["processing"] == 3 and summary["recently_completed"] == 1
    assert client.get(f"{ROOT}/categories").status_code == 200
    rules = client.get(f"{ROOT}/rules").json()["items"]
    assert {item["status"] for item in rules} == {"ACTIVE", "RETIRED"}
    assert client.get(f"{ROOT}/rules/{rule.pk}").json()["duration_days"] == 30
    listed = client.get(f"{ROOT}/cases?page_size=50").json()["items"]
    assert len(listed) == len(cases)
    held = client.get(f"{ROOT}/cases/{cases['ON_HOLD'].pk}").json()
    assert held["holds"][0]["reason"] == "Synthetic administrative hold"
    detail = client.get(f"{ROOT}/cases/{cases['RECONCILIATION_REQUIRED'].pk}").json()
    assert detail["state"] == "RECONCILIATION_REQUIRED"
    assert detail["blocker"] == "PROVIDER_UNVERIFIED"
    serialized = json.dumps(listed)
    for case in cases.values():
        assert str(case.source_id) not in serialized
    assert "source_id" not in detail
    assert ledger_snapshot() == before


def test_historical_anonymized_contribution_keeps_its_integrity_and_exclusions(dpo):
    source = tracer(
        undergraduate_degree_reasons=["PEER_INFLUENCE"],
        degree_other_reason="Confidential detail",
    )
    student = source.student
    for model, values in (
        (
            GraduateTracerEducation,
            {
                "degree_and_specialization": "Identifying degree",
                "college_or_university": "Named school",
                "year_graduated": 2020,
            },
        ),
        (GraduateTracerProfessionalExam, {"examination_name": "Named exam"}),
        (GraduateTracerTraining, {"title": "Specific training"}),
    ):
        encrypted_row(model, response=source, position=1, **values)
    before = build_graduate_tracer_report()
    analytical = {field: getattr(source, field) for field in ANALYTICAL_FIELDS}
    rule = legacy_rule(actor=dpo)
    case = legacy_case(rule=rule, source=source, state="COMPLETED")
    anonymous = historical_anonymized_contribution(source)

    for task in TOMBSTONES:
        task(str(case.pk))
    assert verify_anonymized(anonymous) and anonymous.pk != source.pk
    assert {field: getattr(anonymous, field) for field in ANALYTICAL_FIELDS} == analytical
    assert anonymous.confidential_content_ciphertext is None
    assert all(
        not model.objects.exists()
        for model in (
            GraduateTracerEducation,
            GraduateTracerProfessionalExam,
            GraduateTracerTraining,
        )
    )
    after = build_graduate_tracer_report()
    assert after["sections"] == before["sections"]
    assert after["report_context"]["submitted_response_count"] == 1
    assert GraduateTracerDisposedParticipation.objects.filter(student=student).exists()
    client = auth_client(student)
    for response in (
        client.get("/api/v1/graduate-tracer/me"),
        post_json(client, "/api/v1/graduate-tracer/me", {}),
    ):
        assert response.json()["error"]["code"] == "graduate_tracer_disposed"
    safe = auth_client(dpo).get(f"{ROOT}/cases/{case.pk}").json()
    assert safe["state"] == "COMPLETED" and safe["affected_count"] == 1
    assert str(anonymous.pk) not in json.dumps(safe)
    assert str(source.pk) not in json.dumps(safe)
    head = auth_client(make_head())
    assert head.get(f"/api/v1/graduate-tracer/responses/{anonymous.pk}").status_code == 404
    assert head.get("/api/v1/graduate-tracer/responses").json()["items"] == []
    # The integrity rule still rejects a contribution that carries a quasi-identifier.
    GraduateTracerResponse.objects.filter(pk=anonymous.pk).update(graduation_year=2024)
    assert not verify_anonymized(anonymous)


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_historical_anonymized_submission_keeps_its_manila_report_day():
    # 00:00 on 9 October in Manila is still 8 October in UTC.
    GraduateTracerResponse.objects.create(
        student=None,
        confidential_content_ciphertext=None,
        status="SUBMITTED",
        submitted_at=datetime(2026, 10, 8, 16, 0, tzinfo=UTC),
        anonymized_at=datetime(2026, 10, 9, 16, 0, tzinfo=UTC),
        sex="FEMALE",
        current_employment_state="EMPLOYED",
    )
    on_the_day = build_graduate_tracer_report(
        submitted_from=date(2026, 10, 9), submitted_to=date(2026, 10, 9)
    )
    day_before = build_graduate_tracer_report(
        submitted_from=date(2026, 10, 8), submitted_to=date(2026, 10, 8)
    )
    assert on_the_day["report_context"]["submitted_response_count"] == 1
    assert day_before["report_context"]["submitted_response_count"] == 0


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_historically_disposed_provider_media_cannot_be_resurrected(dpo, kind):
    source, consent = legacy_media_source(kind)
    rule = legacy_rule(
        actor=dpo,
        category="ECOUNSELING_RECORDING" if kind == "RECORDING" else "ECOUNSELING_TRANSCRIPT",
    )
    case = legacy_case(rule=rule, source=source, state="COMPLETED")
    historically_disposed_media(source)
    for task in TOMBSTONES:
        task(str(case.pk))
    process_media_webhook_event(
        event_type="recording.ready-to-download"
        if kind == "RECORDING"
        else "transcript.ready-to-download",
        event_id="late-ready",
        event_ts=timezone.now().timestamp(),
        payload={
            "room_name": source.room.daily_room_name,
            "recording_id": "artifact-opaque",
            "transcript_id": "artifact-opaque",
        },
    )
    source.refresh_from_db()
    assert source.provider_artifact_id is None and source.artifact_disposed_at
    consent.refresh_from_db()
    assert consent.decision == "APPROVED" and consent.withdrawn_at
    case.refresh_from_db()
    assert case.state == "COMPLETED"


def test_historical_audit_trail_is_unchanged_and_still_presented(dpo):
    rule, cases = legacy_world(dpo)
    for action, item in (
        (actions.RETENTION_RULE_ACTIVATED, rule),
        (actions.DISPOSITION_APPROVED, cases["QUEUED"]),
        (actions.DISPOSITION_COMPLETED, cases["COMPLETED"]),
        (actions.DISPOSITION_FAILED, cases["FAILED"]),
    ):
        record_event(
            context=AuditContext.system(),
            action=action,
            outcome="FAILED" if action == actions.DISPOSITION_FAILED else "SUCCESS",
            target_type="privacy.retention.rule" if item is rule else "privacy.disposition.case",
            target_id=item.pk,
            metadata={"category": rule.category, "rule_revision": rule.revision},
        )
    before = ledger_snapshot()
    client = stepped_up(dpo)
    for method, path, payload in mutation_requests(rule, cases["QUEUED"]):
        assert send(client, method, path, payload).status_code == 409
    for task in TOMBSTONES:
        task(str(cases["QUEUED"].pk))
    assert ledger_snapshot() == before
    titles = {
        item["title"]
        for item in auth_client(dpo)
        .get("/api/v1/privacy/activity?category=PRIVACY_GOVERNANCE&page_size=50")
        .json()["items"]
    }
    assert {"Retention rule activated", "Disposition approved", "Disposition completed"} <= titles
    # FAILED-outcome events were never part of the curated feed; they remain stored as evidence.
    assert AuditEvent.objects.filter(action=actions.DISPOSITION_FAILED, outcome="FAILED").exists()


@pytest.mark.parametrize(
    "method,path",
    [
        ("get_recording", "/recordings/opaque%2Fid"),
        ("delete_recording", "/recordings/opaque%2Fid"),
        ("get_transcript", "/transcript/opaque%2Fid"),
        ("delete_transcript", "/transcript/opaque%2Fid"),
    ],
)
def test_daily_artifact_resource_paths_used_by_custody_cleanup_stay_documented(method, path):
    client = DailyClient("test-key", base_url="https://api.daily.test/v1", timeout_seconds=1)
    with patch.object(client, "_request", return_value={}) as request:
        getattr(client, method)(artifact_id="opaque/id")
    request.assert_called_once_with("DELETE" if method.startswith("delete") else "GET", path)


# --- Read-only preflight command ----------------------------------------------------------------


def run_status(*args):
    out = StringIO()
    try:
        call_command("retention_decommission_status", *args, stdout=out)
    except CommandError as exc:
        return exc.returncode, out.getvalue()
    return 0, out.getvalue()


def identifiers(*rows):
    values = set()
    for row in rows:
        values.add(str(row.pk))
        for name in ("source_id", "student_id", "provider_artifact_id"):
            value = getattr(row, name, None)
            if value:
                values.add(str(value))
    return values


def test_status_passes_on_an_empty_or_terminal_ledger_and_lists_operator_checks(dpo):
    code, output = run_status()
    assert code == 0
    for gate in ("G1", "G2", "G3", "G4", "G5"):
        assert f"{gate} PASS" in output
    for gate in ("G6", "G7", "G8", "G9", "G10"):
        assert f"{gate}:" in output
    assert "does not by itself certify" in output
    rule = legacy_rule(actor=dpo, category="ECOUNSELING_RECORDING")
    capture, _ = legacy_media_source("RECORDING")
    historically_disposed_media(capture)
    case = legacy_case(rule=rule, source=capture, state="COMPLETED")
    code, output = run_status()
    assert code == 0 and "case_state | COMPLETED | 1" in output
    assert not identifiers(rule, case, capture, dpo) & set(output.split())
    assert all(value not in output for value in identifiers(rule, case, capture, dpo))


@pytest.mark.parametrize(
    "state,gate",
    [
        ("PROCESSING", "G1"),
        ("APPROVED", "G2"),
        ("QUEUED", "G2"),
        ("FAILED", "G3"),
        ("RECONCILIATION_REQUIRED", "G3"),
    ],
)
def test_status_blocks_pending_in_flight_and_unresolved_cases(dpo, state, gate):
    rule = legacy_rule(actor=dpo)
    source = tracer()
    case = legacy_case(rule=rule, source=source, state=state)
    code, output = run_status()
    assert code == 3
    assert f"{gate} BLOCKED" in output
    if gate == "G2":
        assert "not institutional or National Archives disposal authority" in output
    for value in identifiers(rule, case, source, dpo):
        assert value not in output


def test_status_blocks_active_rules_and_inconsistent_completed_evidence(dpo):
    legacy_rule(actor=dpo, status="ACTIVE")
    code, output = run_status()
    assert code == 3 and "G4 BLOCKED" in output
    OperationalRetentionRule.objects.update(status="RETIRED")
    assert run_status()[0] == 0

    media_rule = legacy_rule(actor=dpo, category="ECOUNSELING_TRANSCRIPT")
    capture, _ = legacy_media_source("TRANSCRIPTION")
    legacy_case(rule=media_rule, source=capture, state="COMPLETED")  # marker missing
    code, output = run_status()
    assert code == 3 and "G5 BLOCKED" in output
    assert "completed_media_without_disposed_marker | - | 1" in output
    historically_disposed_media(capture)
    assert run_status()[0] == 0

    tracer_rule = OperationalRetentionRule.objects.get(category="GRADUATE_TRACER")
    legacy_case(rule=tracer_rule, source=tracer(), state="COMPLETED")  # source still present
    code, output = run_status()
    assert code == 3 and "completed_tracer_source_still_present | - | 1" in output


def test_status_json_is_minimized_and_never_claims_certification(dpo):
    rule = legacy_rule(actor=dpo)
    legacy_case(rule=rule, source=tracer(), state="QUEUED")
    code, output = run_status("--format", "json")
    assert code == 3
    report = json.loads(output)
    assert report["scope"] == "database" and report["blocked"] is True
    assert report["certifies_deployment"] is False
    assert {gate["gate"] for gate in report["not_verified"]} == {"G6", "G7", "G8", "G9", "G10"}
    assert {"item", "bucket", "count"} == set(report["counts"][0])


def test_status_issues_only_reads(dpo):
    _, cases = legacy_world(dpo)
    before = ledger_snapshot()
    with CaptureQueriesContext(connection) as queries:
        run_status()
    statements = [query["sql"].lstrip().upper() for query in queries]
    assert statements and all(
        sql.startswith(("SELECT", "SAVEPOINT", "RELEASE SAVEPOINT")) for sql in statements
    )
    assert ledger_snapshot() == before


@pytest.mark.django_db(transaction=True)
def test_status_runs_as_a_database_read_only_transaction_when_outermost():
    sync_policy()
    dpo = make_dpo("outermost-dpo@example.edu")
    legacy_rule(actor=dpo)
    with CaptureQueriesContext(connection) as queries:
        code, _ = run_status()
    assert code == 0
    statements = [query["sql"].strip().upper() for query in queries]
    statements = [sql for sql in statements if sql != "BEGIN"]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert all(sql.startswith(("SELECT", "SET TRANSACTION", "COMMIT")) for sql in statements)
