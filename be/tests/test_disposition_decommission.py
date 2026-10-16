"""The in-app disposition engine is absent from the canonical baseline (ADR-114, CANON-1C).

The reset-only baseline removes the retired ADR-072 ledger (rules, cases, holds), its tombstone
tasks, fallback services and preflight command. These tests prove the absence, and that the
surviving canonical boundaries still hold: code-owned oversight for the DPO, historical audit
vocabulary, Graduate Tracer anonymous-contribution invariants and the E-Counseling disposal and
unknown-room fences. All data is synthetic; nothing exercises a destructive path.
"""

import ast
import importlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import get_commands
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from compass.accounts.services import effective_capabilities
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.ecounseling.media import process_media_webhook_event
from compass.ecounseling.models import DailyWebhookReceipt as Receipt
from compass.ecounseling.models import (
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
)
from compass.graduate_tracer.disposition import ANALYTICAL_FIELDS, verify_anonymized
from compass.graduate_tracer.models import (
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerTraining,
)
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.integrations.daily import DailyClient
from compass.reports.graduate_tracer import build_graduate_tracer_report
from config.celery import app
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.historical_outcome_fixtures import (
    historical_anonymized_contribution,
    historically_disposed_media,
    legacy_media_source,
)
from tests.test_ecounseling_webhook_security import body_for, reservation, signed
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_head,
    make_user,
    post_json,
    sync_policy,
)

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/privacy/retention"
CAPS = {"privacy_governance.retention.view"}
RETIRED_CAPS = {"privacy_governance.retention.manage", "privacy_governance.retention.approve"}
RETIRED_TASK_NAMES = (
    "compass.privacy_governance.discover_retention",
    "compass.privacy_governance.execute_disposition",
    "compass.privacy_governance.recover_disposition",
)
RETIRED_MODULES = (
    "compass.privacy_governance.retention",
    "compass.privacy_governance.retention_models",
    "compass.privacy_governance.tasks",
)
RETIRED_TABLES = (
    "privacy_governance_operationalretentionrule",
    "privacy_governance_dispositioncase",
    "privacy_governance_dispositionhold",
)
RETIRED_MODELS = ("OperationalRetentionRule", "DispositionCase", "DispositionHold")
COMPASS = Path(__file__).resolve().parents[1] / "compass"


@pytest.fixture
def dpo():
    sync_policy()
    return make_dpo()


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


# --- Absence of the retired engine --------------------------------------------------------------


def test_beat_schedule_has_no_retention_entries_and_keeps_unrelated_schedules():
    schedule = settings.CELERY_BEAT_SCHEDULE
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


def test_retired_disposition_task_names_are_not_registered():
    app.autodiscover_tasks(force=True)
    registered = set(app.tasks)
    assert registered.isdisjoint(RETIRED_TASK_NAMES)
    assert not any(name.startswith("compass.privacy_governance.") for name in registered)
    # Custody transfer and recovery are canonical E-Counseling work, not disposition.
    assert {
        "compass.ecounseling.ingest_media_artifact",
        "compass.ecounseling.recover_media_artifacts",
        "compass.notifications.email.dispatch_due",
    } <= registered


@pytest.mark.parametrize("module", RETIRED_MODULES)
def test_retired_engine_modules_are_not_importable(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_ledger_models_tables_and_preflight_command_are_absent():
    names = {model.__name__ for model in apps.get_app_config("privacy_governance").get_models()}
    assert names.isdisjoint(RETIRED_MODELS)
    tables = set(connection.introspection.table_names())
    assert tables.isdisjoint(RETIRED_TABLES)
    # The canonical privacy tables remain.
    assert {
        "privacy_governance_privacynotice",
        "privacy_governance_privacynoticerevision",
    } <= tables
    assert "retention_decommission_status" not in get_commands()


def test_no_production_module_references_the_retired_engine():
    """No import, task name, model name or retired error code survives outside migrations."""

    retired_symbols = {
        *RETIRED_MODELS,
        "discover_retention",
        "execute_disposition",
        "recover_disposition",
        "SUPPORTED_CONTRACTS",
    }
    offenders = []
    for path in COMPASS.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        rel = path.relative_to(COMPASS.parent).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                relative_retired = (
                    node.level
                    and rel.startswith("compass/privacy_governance/")
                    and node.module in {"retention", "retention_models", "tasks"}
                )
                if node.module in RETIRED_MODULES or relative_retired:
                    offenders.append((rel, node.module))
                if {alias.name for alias in node.names} & retired_symbols:
                    offenders.append((rel, "import"))
            elif isinstance(node, ast.Name | ast.Attribute):
                name = node.id if isinstance(node, ast.Name) else node.attr
                if name in retired_symbols:
                    offenders.append((rel, name))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in RETIRED_TASK_NAMES or node.value == "retention_decommissioned":
                    offenders.append((rel, node.value))
    assert offenders == []


# --- Canonical oversight boundary ---------------------------------------------------------------


def test_dpo_keeps_only_retention_view_and_no_confidential_content(dpo):
    assert CAPS <= effective_capabilities(dpo)
    assert RETIRED_CAPS.isdisjoint(effective_capabilities(dpo))
    assert (CAPS | RETIRED_CAPS).isdisjoint(effective_capabilities(make_head()))
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


def test_retired_ledger_routes_are_unreachable_and_the_register_is_served(dpo):
    client = auth_client(dpo, recent_mfa=True)
    for path in (
        f"{ROOT}/summary",
        f"{ROOT}/rules",
        f"{ROOT}/cases",
        f"{ROOT}/cases/00000000-0000-4000-8000-000000000001",
    ):
        assert client.get(path).status_code == 404
    for path in (
        f"{ROOT}/rules/00000000-0000-4000-8000-000000000001/activate",
        f"{ROOT}/cases/00000000-0000-4000-8000-000000000001/approve",
    ):
        assert post_json(client, path, {"expected_revision": 1}).status_code == 404
    response = client.get(f"{ROOT}/policies")
    assert response.status_code == 200
    assert {item["adoption_status"] for item in response.json()["items"]} == {"NOT_ADOPTED"}


def test_historical_audit_vocabulary_is_still_presented(dpo):
    """Append-only history from earlier environments keeps its presenters (ADR-114)."""

    for action in (
        actions.RETENTION_RULE_ACTIVATED,
        actions.DISPOSITION_APPROVED,
        actions.DISPOSITION_COMPLETED,
    ):
        record_event(
            context=AuditContext.system(),
            action=action,
            outcome="SUCCESS",
            target_type=(
                "privacy.retention.rule"
                if action == actions.RETENTION_RULE_ACTIVATED
                else "privacy.disposition.case"
            ),
            target_id="00000000-0000-4000-8000-000000000002",
            metadata={"category": "GRADUATE_TRACER", "rule_revision": 1},
        )
    titles = {
        item["title"]
        for item in auth_client(dpo)
        .get("/api/v1/privacy/activity?category=PRIVACY_GOVERNANCE&page_size=50")
        .json()["items"]
    }
    assert {"Retention rule activated", "Disposition approved", "Disposition completed"} <= titles
    assert AuditEvent.objects.filter(action=actions.DISPOSITION_COMPLETED).count() == 1


# --- Surviving historical-outcome readers -------------------------------------------------------


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
    source_id = source.pk
    anonymous = historical_anonymized_contribution(source)

    assert verify_anonymized(anonymous) and anonymous.pk != source_id
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
    served = json.dumps(auth_client(dpo).get(f"{ROOT}/policies").json())
    assert str(anonymous.pk) not in served and str(source_id) not in served
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
def test_disposal_markers_fence_late_provider_callbacks_without_a_ledger(kind):
    source, consent = legacy_media_source(kind)
    historically_disposed_media(source)
    with patch("celery.app.task.Task.apply_async") as dispatch:
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
    assert not ECounselingMediaArtifact.objects.filter(capture=source).exists()
    dispatch.assert_not_called()
    consent.refresh_from_db()
    assert consent.decision == "APPROVED" and consent.withdrawn_at


@override_settings(DAILY_ENABLED=True)
@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_callback_for_a_room_absent_from_the_new_database_creates_nothing(kind):
    """A late callback from a pre-reset room cannot recreate a room, capture or artifact."""

    _, capture = reservation(kind)
    rooms = ECounselingRoom.objects.count()
    captures = ECounselingMediaCapture.objects.count()
    event = body_for(capture)
    event["payload"]["room_name"] = "ec-" + "0" * 32
    if kind == "RECORDING":
        event["payload"]["instance_id"] = "pre-reset-instance"
    else:
        event["payload"]["info"]["instanceId"] = "pre-reset-instance"
    with patch("celery.app.task.Task.apply_async") as dispatch:
        signed(event)
    receipt = Receipt.objects.get(provider_event_id=event["id"])
    assert receipt.anomaly_code == "UNKNOWN_ROOM" and receipt.capture_id is None
    assert receipt.mitigation_attempted_at is None
    assert ECounselingRoom.objects.count() == rooms
    assert ECounselingMediaCapture.objects.count() == captures
    assert not ECounselingMediaArtifact.objects.exists()
    dispatch.assert_not_called()


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
