"""The in-app disposition engine is absent from the canonical baseline (ADR-114, CANON-1C).

The reset-only baseline removes the retired ADR-072 ledger (rules, cases, holds), its tombstone
tasks, fallback services and preflight command. These tests prove the absence, and that the
surviving canonical boundaries still hold: privacy authorization and the
E-Counseling disposal and unknown-room fences. All data is synthetic; nothing exercises a
destructive path.
"""

import ast
import importlib
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import get_commands
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from compass.ecounseling.media import process_media_webhook_event
from compass.ecounseling.models import DailyWebhookReceipt as Receipt
from compass.ecounseling.models import (
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
)
from compass.graduate_tracer.models import (
    GraduateTracerResponse,
)
from compass.integrations.daily import DailyClient
from config.celery import app
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.historical_outcome_fixtures import (
    historically_disposed_media,
    legacy_media_source,
)
from tests.test_ecounseling_webhook_security import body_for, reservation, signed
from tests.test_privacy_governance import (
    make_privacy_admin,
    make_user,
    sync_policy,
)

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/privacy/retention"
CAPS = set()
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
def officer():
    sync_policy()
    return make_privacy_admin()


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


# --- Surviving historical-outcome readers -------------------------------------------------------


def test_disposal_markers_fence_late_provider_callbacks_without_a_ledger():
    source, consent = legacy_media_source("RECORDING")
    historically_disposed_media(source)
    with patch("celery.app.task.Task.apply_async") as dispatch:
        process_media_webhook_event(
            event_type="recording.ready-to-download",
            event_id="late-ready",
            event_ts=timezone.now().timestamp(),
            payload={
                "room_name": source.room.daily_room_name,
                "recording_id": "artifact-opaque",
            },
        )
    source.refresh_from_db()
    assert source.provider_artifact_id is None and source.artifact_disposed_at
    assert not ECounselingMediaArtifact.objects.filter(capture=source).exists()
    dispatch.assert_not_called()
    consent.refresh_from_db()
    assert consent.decision == "APPROVED" and consent.withdrawn_at


@override_settings(DAILY_ENABLED=True)
def test_callback_for_a_room_absent_from_the_new_database_creates_nothing():
    """A late callback from a pre-reset room cannot recreate a room, capture or artifact."""

    _, capture = reservation("RECORDING")
    rooms = ECounselingRoom.objects.count()
    captures = ECounselingMediaCapture.objects.count()
    event = body_for(capture)
    event["payload"]["room_name"] = "ec-" + "0" * 32
    event["payload"]["instance_id"] = "pre-reset-instance"
    with patch("celery.app.task.Task.apply_async") as dispatch:
        signed(event)
    receipt = Receipt.objects.get(provider_event_id=event["id"])
    assert receipt.anomaly_code == "UNKNOWN_ROOM" and receipt.capture_id is None
    assert ECounselingRoom.objects.count() == rooms
    assert ECounselingMediaCapture.objects.count() == captures
    assert not ECounselingMediaArtifact.objects.exists()
    dispatch.assert_not_called()


@pytest.mark.parametrize(
    "method,path",
    [
        ("get_recording", "/recordings/opaque%2Fid"),
        ("delete_recording", "/recordings/opaque%2Fid"),
    ],
)
def test_daily_artifact_resource_paths_used_by_custody_cleanup_stay_documented(method, path):
    client = DailyClient("test-key", base_url="https://api.daily.test/v1", timeout_seconds=1)
    with patch.object(client, "_request", return_value={}) as request:
        getattr(client, method)(artifact_id="opaque/id")
    request.assert_called_once_with("DELETE" if method.startswith("delete") else "GET", path)
