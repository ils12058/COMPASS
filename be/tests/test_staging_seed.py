"""COMPASS Staging Dataset v1 (``seed_staging_dataset``): safety, population, UAT readiness.

Everything is synthetic. The shared seed runs once per class (``setUpTestData``) with every
external boundary (Daily, object storage, outbound HTTP, Celery dispatch of email/push) forbidden,
so a test failure proves the seeder never needed one.
"""

import csv
import json
import os
import stat
import tempfile
from datetime import date, datetime, time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from cryptography.fernet import Fernet
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import Role, User
from compass.appointments.models import Appointment
from compass.appointments.services import cancel_appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.actions import AUTH_PASSWORD_INITIAL_SET, AUTH_PASSWORD_RESET
from compass.authentication.models import AuthSession
from compass.ecounseling.models import ECounselingRoom
from compass.good_moral.models import GoodMoralRequest
from compass.guidance_messages.models import GuidanceThread
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, Notification, PushDelivery
from compass.staging_seed import DATASET_NAME, DATASET_VERSION
from compass.staging_seed.config import StagingSeedConfigurationError, load_config
from compass.staging_seed.credentials import (
    HANDOFF_COLUMNS,
    CredentialIssuanceError,
    issue_credentials,
)
from compass.staging_seed.guard import StagingSeedingRefused, ensure_seeding_allowed
from compass.staging_seed.identities import AuthPlan, StudentGroup, Suitability
from compass.staging_seed.manifest import (
    ACCOUNTS,
    SCENARIOS,
    Readiness,
    scenarios_for,
    validate_manifest,
)
from compass.staging_seed.reports import (
    ACCOUNTS_CSV,
    ASSIGNMENT,
    CATALOG,
    CSV_COLUMNS,
    SUMMARY,
    ReportError,
    _scan,
    render_reports,
    write_reports,
)
from compass.staging_seed.seed import SEED_RUN_ADVISORY_LOCK_KEY, seed_staging_dataset
from compass.staging_seed.students import STUDENTS
from compass.staging_seed.timeline import StagingTimelineError, resolve_timeline
from compass.staging_seed.verify import verify_dataset
from tests.test_authentication import AllowLimiter, login

ANCHOR = date(2026, 10, 15)
COMMAND = "seed_staging_dataset"
SEED_ENV = ("STAGING_SEED_EMAIL_DOMAIN", "STAGING_SEED_ONBOARDING_EMAIL")
PARTICIPANT_CREDENTIAL_KEYS = [
    a.key
    for a in ACCOUNTS
    if a.suitability == Suitability.PARTICIPANT and a.auth == AuthPlan.CREDENTIAL
]


def dataset_now() -> datetime:
    """The dataset's own clock: noon on the preparation date in Asia/Manila."""

    from compass.common.institutional_time import institution_zone

    return datetime.combine(ANCHOR, time(12), tzinfo=institution_zone())


def forbidden(*_args, **_kwargs):
    raise AssertionError("Seeding reached an external boundary.")


def seed_once():
    environment = {name: value for name, value in os.environ.items() if name not in SEED_ENV}
    with (
        patch.dict(os.environ, environment, clear=True),
        patch("compass.staging_seed.timeline.institution_today", lambda: ANCHOR),
        patch("compass.integrations.daily.DailyClient.from_settings", forbidden),
        patch("compass.integrations.daily.urlopen", forbidden),
        patch("compass.integrations.storage.ObjectStorage.__init__", forbidden),
    ):
        sent_before = len(getattr(mail, "outbox", []))
        report = seed_staging_dataset()
        assert len(getattr(mail, "outbox", [])) == sent_before, "Seeding sent email."
        return report


def dataset_user(key: str) -> User:
    account = next(a for a in ACCOUNTS if a.key == key)
    return User.objects.select_related("role").get(institutional_id=account.institutional_id)


def scratch_dir() -> Path:
    # Handoff files must live outside the repository; the system temp directory always is.
    path = Path(tempfile.mkdtemp(prefix="stg-handoff-"))
    path.chmod(0o700)
    return path


# --- Guard, configuration, timeline and manifest (no database) ---------------------------------


@pytest.mark.parametrize("app_env", ["local-staging", "live-staging"])
def test_guard_allows_only_the_explicit_staging_modes_with_opt_in(app_env):
    assert ensure_seeding_allowed(app_env=app_env, seeding_enabled=True) == app_env


@pytest.mark.parametrize(
    ("app_env", "enabled"),
    [
        ("live-staging", False),
        ("local-staging", False),
        ("live-staging", "true"),
        ("production", True),
        ("staging", True),
        ("future-mode", True),
        ("", True),
        (None, True),
    ],
)
def test_guard_fails_closed_and_the_opt_in_never_widens_the_allowlist(app_env, enabled):
    with pytest.raises(StagingSeedingRefused):
        ensure_seeding_allowed(app_env=app_env, seeding_enabled=enabled)


def test_configuration_uses_only_staging_seed_variables(monkeypatch):
    for name in SEED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert load_config(app_env="local-staging").email_domain == "compass-staging.test"
    with pytest.raises(StagingSeedConfigurationError, match="required in live-staging"):
        load_config(app_env="live-staging")
    monkeypatch.setenv("STAGING_SEED_EMAIL_DOMAIN", "UAT.Example.ORG")
    assert load_config(app_env="live-staging").email_domain == "uat.example.org"
    monkeypatch.setenv("STAGING_SEED_EMAIL_DOMAIN", "someone@example.org")
    with pytest.raises(StagingSeedConfigurationError, match="bare domain"):
        load_config(app_env="live-staging")


def test_timeline_accepts_only_a_current_preparation_date(monkeypatch):
    monkeypatch.setattr("compass.staging_seed.timeline.institution_today", lambda: ANCHOR)
    assert resolve_timeline().anchor == ANCHOR
    assert str(resolve_timeline().zone) == "Asia/Manila"
    assert resolve_timeline(anchor=date(2026, 10, 14)).anchor == date(2026, 10, 14)
    for refused in (date(2026, 10, 16), date(2026, 10, 1), date(2026, 9, 1)):
        with pytest.raises(StagingTimelineError):
            resolve_timeline(anchor=refused)


def test_manifest_population_and_uat_rules():
    validate_manifest()
    students = [a for a in ACCOUNTS if a.is_student]
    staff = [a for a in ACCOUNTS if not a.is_student]
    groups = {group: sum(s.group == group for s in students) for group in StudentGroup}
    assert (len(students), len(staff)) == (100, 13)
    assert groups == {
        StudentGroup.RICH: 11,
        StudentGroup.ACTION_READY: 24,
        StudentGroup.BACKGROUND: 65,
    }
    assert {a.role for a in staff} == {
        "IT_ADMIN",
        "COUNSELOR",
        "GUIDANCE_SERVICES_STAFF",
        "INSTITUTIONAL_OFFICER",
    }
    for account in ACCOUNTS:
        assert account.institutional_id.startswith(("STG-S-", "STG-E-"))
        if account.suitability == Suitability.PARTICIPANT:
            assert scenarios_for(account.key), account.key
        if account.auth == AuthPlan.DISABLED:
            assert account.suitability == Suitability.RESTRICTED
    pending = [s for s in SCENARIOS if s.readiness == Readiness.PENDING_IMPLEMENTATION]
    assert {s.domain for s in pending} == {
        "Appointment Reminders",
        "Service Catalog Expansion",
        "Shared Guidance Follow-Up",
    }
    assert all(not s.checks for s in pending)


def test_documentation_scan_rejects_credential_material():
    for leaked in (
        "gAAAAABlongfernettokenvalue1234567890",
        "pbkdf2_sha256$1500000$salt$hash",
        "account_key,temporary_password",
    ):
        with pytest.raises(ReportError):
            _scan("example.md", leaked)


# --- Command refusal before any work ----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["seed", "verify", "issue-credentials"])
@pytest.mark.parametrize(
    ("app_env", "enabled", "message"),
    [
        ("live-staging", False, "disabled for live-staging"),
        ("production", True, "refused for APP_ENV='production'"),
        ("future-mode", True, "refused for APP_ENV='future-mode'"),
    ],
)
def test_every_mode_refuses_before_touching_the_database(app_env, enabled, message, mode):
    arguments = (
        [mode, "--output", "/nonexistent/handoff.csv"] if mode == "issue-credentials" else [mode]
    )
    with CaptureQueriesContext(connection) as queries:
        with override_settings(APP_ENV=app_env, STAGING_SEED_ENABLED=enabled):
            with pytest.raises(CommandError, match=message):
                call_command(COMMAND, *arguments, stdout=StringIO())
    assert len(queries) == 0


@pytest.mark.django_db
def test_retired_demo_lineage_is_never_upgraded():
    sync_identity_policy()
    User.objects.create_user(
        email="old@compass-demo.test",
        password=None,
        role=Role.objects.get(code="STUDENT"),
        first_name="Old",
        last_name="Persona",
        institutional_id="DEMO-2026-0101",
    )
    with pytest.raises(Exception, match="retired Demo Dataset"):
        seed_once()
    assert not User.objects.filter(institutional_id__startswith="STG-").exists()


@pytest.mark.django_db
def test_an_identity_conflict_stops_before_business_records():
    sync_identity_policy()
    User.objects.create_user(
        email="stg-ar-01@compass-staging.test",
        password=None,
        role=Role.objects.get(code="STUDENT"),
        first_name="Real",
        last_name="Person",
        institutional_id="REAL-0001",
    )
    with pytest.raises(Exception, match="conflicts with an existing account"):
        seed_once()
    assert not User.objects.filter(institutional_id__startswith="STG-").exists()
    assert not StudentInventory.objects.exists()


# --- Read-only verification and concurrency ----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_verification_runs_in_a_read_only_transaction():
    with CaptureQueriesContext(connection) as queries:
        result = verify_dataset(now=dataset_now())
    statements = [q["sql"].strip().upper() for q in queries if q["sql"].strip()]
    statements = [sql for sql in statements if sql != "BEGIN"]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    assert not result.passed  # nothing is seeded


@pytest.mark.django_db(transaction=True)
def test_a_concurrent_seed_run_is_refused():
    params = settings.DATABASES["default"]
    other = psycopg.connect(
        dbname=connection.settings_dict["NAME"],
        user=params["USER"],
        password=params["PASSWORD"],
        host=params["HOST"],
        port=params["PORT"],
        autocommit=True,
    )
    try:
        other.execute("SELECT pg_advisory_lock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])
        with pytest.raises(Exception, match="in progress"):
            seed_once()
        assert not User.objects.filter(institutional_id__startswith="STG-").exists()
    finally:
        other.execute("SELECT pg_advisory_unlock_all()")
        other.close()


# --- The seeded dataset ---------------------------------------------------------------------


@override_settings(AUTH_TOTP_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SeededDatasetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.report = seed_once()

    def verify(self, **kwargs):
        return verify_dataset(now=dataset_now(), **kwargs)

    def test_seed_report_names_the_new_lineage(self):
        assert self.report.dataset_name == DATASET_NAME == "COMPASS Staging Dataset v1"
        assert self.report.dataset_version == DATASET_VERSION == 1
        assert self.report.anchor == ANCHOR
        assert (self.report.account_count, self.report.student_count) == (113, 100)

    def test_population_accounts_and_authentication_state(self):
        seeded = User.objects.filter(institutional_id__startswith="STG-")
        assert seeded.count() == 113
        assert not any(user.has_usable_password() for user in seeded)
        assert dataset_user("onboarding").email_verified_at is None
        assert not dataset_user("former_staff").is_active
        assert not dataset_user("bg_65").is_active
        assert all(
            dataset_user(a.key).email_verified_at is not None
            for a in ACCOUNTS
            if a.auth == AuthPlan.CREDENTIAL
        )
        lifecycles = {s.key: dataset_user(s.key).student_lifecycle_status for s in STUDENTS}
        assert sum(value == "CURRENT" for value in lifecycles.values()) == 86
        assert lifecycles["ar_13"] == "GRADUATED" and lifecycles["former"] == "FORMER"

    def test_strict_verification_passes_every_section(self):
        result = self.verify()
        failures = [f for section in result.sections for f in section.failures]
        assert failures == []
        assert result.passed
        assert set(result.scenario_status.values()) == {"READY", Readiness.PENDING_IMPLEMENTATION}

    def test_seeding_has_no_external_side_effects(self):
        ids = list(
            User.objects.filter(institutional_id__startswith="STG-").values_list("pk", flat=True)
        )
        assert not EmailDelivery.objects.filter(notification__recipient_id__in=ids).exists()
        assert not PushDelivery.objects.exists()
        assert not ECounselingRoom.objects.exists()
        # In-app notifications are kept for UAT visibility.
        assert Notification.objects.filter(recipient_id__in=ids).exists()

    def test_action_ready_states_through_domain_services(self):
        assert Appointment.objects.filter(
            student=dataset_user("ar_05"), delivery_mode="ONLINE"
        ).exists()
        assert (
            GoodMoralRequest.objects.get(student=dataset_user("ar_18")).status
            == "READY_FOR_ISSUANCE"
        )
        thread = GuidanceThread.objects.get(student=dataset_user("ar_14"))
        assert thread.kind == "COUNSELING" and thread.counselor_id == dataset_user("counselor_a").pk
        assert not StudentInventory.objects.filter(student=dataset_user("ar_08")).exists()

    def test_rerun_creates_nothing_and_preserves_evaluator_changes(self):
        student, other = dataset_user("ar_03"), dataset_user("ar_02")
        appointment = Appointment.objects.get(student=student)
        cancel_appointment(
            appointment_id=appointment.pk,
            actor=student,
            administrative=False,
            context=AuditContext.user(student),
        )
        other.set_password("an evaluator chose this passphrase")
        other.save(update_fields=["password"])
        password_hash = User.objects.get(pk=other.pk).password
        second = seed_once()
        assert sum(second.created.values()) == 0
        assert list(
            Appointment.objects.filter(student=student).values_list("status", flat=True)
        ) == ["CANCELLED"]
        assert User.objects.get(pk=other.pk).password == password_hash
        strict = self.verify()
        assert not strict.passed
        active = self.verify(allow_uat_changes=True)
        assert active.passed
        assert any("STU-APT-03" in w for s in active.sections for w in s.warnings)

    def test_reports_are_complete_consistent_and_secret_free(self):
        result = self.verify()
        documents = render_reports(result)
        assert set(documents) == {
            CATALOG,
            ACCOUNTS_CSV,
            "UAT-ACCOUNT-SELECTION-GUIDE.md",
            "UAT-SCENARIO-MATRIX.md",
            ASSIGNMENT,
            SUMMARY,
        }
        rows = list(csv.DictReader(StringIO(documents[ACCOUNTS_CSV])))
        assert tuple(rows[0]) == CSV_COLUMNS
        assert [row["account_key"] for row in rows] == [a.key for a in ACCOUNTS]
        assert sum(row["role"] == "STUDENT" for row in rows) == 100
        for account in ACCOUNTS:
            assert f"| {account.key} |" in documents[CATALOG]
        assert "**113** (100 Students, 13 staff)" in documents[SUMMARY]
        executable = sum(s.readiness == Readiness.EXECUTABLE for s in SCENARIOS)
        assert f"Executable UAT scenarios: **{executable}**" in documents[SUMMARY]
        template = list(csv.DictReader(StringIO(documents[ASSIGNMENT])))
        assert all(row["uat_participant_reference"] == "" for row in template)
        assert {row["selected_account_key"] for row in template} == {
            a.key for a in ACCOUNTS if a.suitability == Suitability.PARTICIPANT
        }
        with tempfile.TemporaryDirectory() as directory:
            assert len(write_reports(result, Path(directory))) == 6

    def test_report_refuses_to_write_after_failed_verification(self):
        dataset_user("head_guidance").designations.clear()
        result = self.verify()
        assert not result.passed
        with tempfile.TemporaryDirectory() as directory:
            with pytest.raises(ReportError):
                write_reports(result, Path(directory))
            assert os.listdir(directory) == []

    def test_credentials_are_distinct_hashed_protected_and_sign_in(self):
        directory = scratch_dir()
        target = directory / "handoff.csv"
        outcome = issue_credentials(output=target)
        assert (outcome.issued, outcome.skipped) == (len(PARTICIPANT_CREDENTIAL_KEYS), 0)
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        rows = list(csv.DictReader(target.open()))
        assert tuple(rows[0]) == HANDOFF_COLUMNS
        assert [row["account_key"] for row in rows] == PARTICIPANT_CREDENTIAL_KEYS
        passwords = [row["temporary_password"] for row in rows]
        assert len(set(passwords)) == len(passwords) and all(len(p) >= 15 for p in passwords)
        for row in rows[:3]:
            user = dataset_user(row["account_key"])
            assert (
                user.password.startswith("pbkdf2_")
                and row["temporary_password"] not in user.password
            )
            assert user.check_password(row["temporary_password"])
        events = AuditEvent.objects.filter(action=AUTH_PASSWORD_INITIAL_SET)
        assert events.count() == len(rows)
        assert not any(
            row["temporary_password"] in json.dumps(e.metadata) for e in events for row in rows
        )
        student = next(row for row in rows if row["account_key"] == "ar_01")
        with patch(
            "compass.authentication.abuse.RedisRateLimiter.from_settings", lambda: AllowLimiter()
        ):
            response = login(
                Client(), email=student["email"], password=student["temporary_password"]
            )
        assert response.status_code == 200
        assert AuthSession.objects.filter(
            user=dataset_user("ar_01"), revoked_at__isnull=True
        ).exists()

        again = issue_credentials(output=directory / "second.csv")
        assert again.issued == 0 and not (directory / "second.csv").exists()
        with pytest.raises(CredentialIssuanceError, match="already exists"):
            issue_credentials(output=target)
        with pytest.raises(CredentialIssuanceError, match="source tree"):
            issue_credentials(output=Path(settings.BASE_DIR) / "handoff.csv")
        with pytest.raises(CredentialIssuanceError, match="confirm-reissue"):
            issue_credentials(output=directory / "x.csv", account_keys=("ar_01",), reissue=True)
        for key in ("onboarding", "former_staff", "bg_65"):
            with pytest.raises(CredentialIssuanceError):
                issue_credentials(output=directory / "x.csv", account_keys=(key,))

        reissued = issue_credentials(
            output=directory / "reissue.csv",
            account_keys=("ar_01",),
            reissue=True,
            confirm_reissue=True,
        )
        assert reissued.issued == 1
        new = next(csv.DictReader((directory / "reissue.csv").open()))["temporary_password"]
        user = dataset_user("ar_01")
        assert user.check_password(new) and not user.check_password(student["temporary_password"])
        assert not AuthSession.objects.filter(user=user, revoked_at__isnull=True).exists()
        assert AuditEvent.objects.filter(
            action=AUTH_PASSWORD_RESET, target_id=str(user.pk)
        ).exists()

    def test_restricted_accounts_need_explicit_issuance(self):
        directory = scratch_dir()
        outcome = issue_credentials(
            output=directory / "negative.csv", account_keys=("officer_no_designation",)
        )
        assert outcome.issued == 1
        assert not dataset_user("unassigned_counselor").has_usable_password()

    def test_command_verify_and_report_modes(self):
        out = StringIO()
        with patch("compass.staging_seed.verify.timezone.now", dataset_now):
            call_command(COMMAND, "verify", stdout=out)
            assert "Verification PASSED." in out.getvalue()
            with tempfile.TemporaryDirectory() as directory:
                call_command(COMMAND, "report", "--output-dir", directory, stdout=StringIO())
                assert sorted(os.listdir(directory)) == sorted(
                    [
                        CATALOG,
                        ACCOUNTS_CSV,
                        "UAT-ACCOUNT-SELECTION-GUIDE.md",
                        "UAT-SCENARIO-MATRIX.md",
                        ASSIGNMENT,
                        SUMMARY,
                    ]
                )
