"""COMPASS Staging Dataset v1 (``seed_staging_dataset``): safety, population, UAT readiness.

Everything is synthetic. The shared seed runs once per class (``setUpTestData``) with every
external boundary (Daily, object storage, outbound HTTP, Celery dispatch of email/push) forbidden,
so a test failure proves the seeder never needed one.
"""

import csv
import hashlib
import json
import os
import stat
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, replace
from datetime import date, datetime, time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from cryptography.fernet import Fernet
from django.apps import apps
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
from compass.exit_interviews.models import ExitInterview
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import create_my_graduate
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.services import replace_my_draft, submit_my_response
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
from compass.staging_seed.identities import AuthPlan, Lifecycle, StudentGroup, Suitability
from compass.staging_seed.manifest import (
    ACCOUNTS,
    SCENARIOS,
    UAT_40_ALLOCATION,
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
from compass.staging_seed.students import POPULATION_STUDENTS, STUDENTS, STUDENTS_BY_KEY
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
EXPANSION_KEYS = {"it_admin_3", "ar_25", "ar_26"}
EXPANSION_SCENARIOS = {"ITA-PLT-02", "STU-GT-03", "STU-GM-07"}


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


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
    assert (len(students), len(staff)) == (102, 14)
    assert groups == {
        StudentGroup.RICH: 11,
        StudentGroup.ACTION_READY: 26,
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


def test_expansion_preserves_all_original_identity_and_scenario_definitions():
    # Frozen from staging 8684ea10, excluding only the three additive participants/scenarios.
    original_accounts = [asdict(a) for a in ACCOUNTS if a.key not in EXPANSION_KEYS]
    original_scenarios = [asdict(s) for s in SCENARIOS if s.id not in EXPANSION_SCENARIOS]
    assert len(original_accounts) == 113
    assert len(original_scenarios) == 91
    assert fingerprint(original_accounts) == (
        "520a0b48acaae6b51dd7265bae2c77ed80fdb08005bd8b5bbf5d515e73d24477"
    )
    assert fingerprint(original_scenarios) == (
        "1b63b4f8283d740993af7eccdafdc034565e15a5de26263b83b4af6775ddffa8"
    )
    assert len(ACCOUNTS) == 116 and len(SCENARIOS) == 94
    names = [account.full_name for account in ACCOUNTS]
    for account in ACCOUNTS:
        if account.key in EXPANSION_KEYS:
            assert names.count(account.full_name) == 1


def test_40_person_allocation_has_independent_eligible_account_owners():
    assert {category: len(keys) for category, keys in UAT_40_ALLOCATION.items()} == {
        "Head Guidance Counselor": 1,
        "Guidance Counselor": 3,
        "Guidance Services Staff": 2,
        "Current Student": 25,
        "Alumni": 5,
        "ITSO personnel": 3,
        "Data Protection Officer": 1,
    }
    keys = [key for group in UAT_40_ALLOCATION.values() for key in group]
    assert len(keys) == len(set(keys)) == 40
    for key in keys:
        account = next(a for a in ACCOUNTS if a.key == key)
        assert account.suitability == Suitability.PARTICIPANT
        assert account.auth == AuthPlan.CREDENTIAL
        assert any(s.readiness == Readiness.EXECUTABLE for s in scenarios_for(key))
    for category, lifecycle in (
        ("Current Student", Lifecycle.CURRENT),
        ("Alumni", Lifecycle.GRADUATED),
    ):
        assert all(
            STUDENTS_BY_KEY[key].lifecycle == lifecycle for key in UAT_40_ALLOCATION[category]
        )


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
        assert (self.report.account_count, self.report.student_count) == (116, 102)

    def test_population_accounts_and_authentication_state(self):
        seeded = User.objects.filter(institutional_id__startswith="STG-")
        assert seeded.count() == 116
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
        assert sum(row["role"] == "STUDENT" for row in rows) == 102
        for account in ACCOUNTS:
            assert f"| {account.key} |" in documents[CATALOG]
        assert "**116** (102 Students, 14 staff)" in documents[SUMMARY]
        assert "40 independent participants" in documents[SUMMARY]
        executable = sum(s.readiness == Readiness.EXECUTABLE for s in SCENARIOS)
        assert f"Executable UAT scenarios: **{executable}**" in documents[SUMMARY]
        template = list(csv.DictReader(StringIO(documents[ASSIGNMENT])))
        assert all(row["uat_participant_reference"] == "" for row in template)
        assert {row["selected_account_key"] for row in template} == {
            a.key for a in ACCOUNTS if a.suitability == Suitability.PARTICIPANT
        }
        with tempfile.TemporaryDirectory() as directory:
            assert len(write_reports(result, Path(directory))) == 6

    def test_new_alumni_can_complete_their_existing_domain_workflows(self):
        from compass.staging_seed.content.forms import tracer_answers
        from compass.staging_seed.organization import program_for
        from compass.staging_seed.scenarios.rich import tracer_values

        for key in ("ar_25", "ar_26"):
            student = dataset_user(key)
            assert student.role.code == "STUDENT"
            assert student.student_lifecycle_status == Lifecycle.GRADUATED
            assert ExitInterview.objects.filter(student=student, status="SUBMITTED").exists()
            assert not StudentInventory.objects.filter(
                student=student, academic_year__label="2026-2027"
            ).exists()
        student = dataset_user("ar_25")
        response = GraduateTracerResponse.objects.get(student=student)
        assert response.status == "DRAFT"
        persona = replace(STUDENTS_BY_KEY["ar_25"], tracer="related")
        replace_my_draft(
            student=student,
            values=tracer_values(
                response,
                persona,
                tracer_answers(persona, program_for(persona)),
                graduation_year=2026,
            ),
        )
        submit_my_response(student=student, context=AuditContext.user(student), now=dataset_now())
        student = dataset_user("ar_26")
        request = create_my_graduate(
            student=student,
            degree="Bachelor of Science in Accountancy",
            major="",
            graduation_date=date(2026, 6, 15),
            idempotency_key="uat-expansion-graduate-request",
            request_fingerprint=hashlib.sha256(b"uat-expansion-graduate-request").hexdigest(),
            context=AuditContext.user(student),
        )
        assert request.status == "REQUESTED" and request.student_id == student.pk
        response.refresh_from_db()
        assert response.status == "SUBMITTED"
        seed_once()
        assert GoodMoralRequest.objects.filter(pk=request.pk, status="REQUESTED").exists()
        assert not self.verify().passed
        assert self.verify(allow_uat_changes=True).passed

    def test_new_participants_support_only_selected_credential_issuance(self):
        with tempfile.TemporaryDirectory(prefix="stg-expansion-") as directory:
            target = Path(directory) / "selected.csv"
            outcome = issue_credentials(output=target, account_keys=tuple(sorted(EXPANSION_KEYS)))
            assert outcome.issued == 3 and outcome.skipped == 0
            assert stat.S_IMODE(target.stat().st_mode) == 0o600
            rows = list(csv.DictReader(target.open()))
            assert {r["account_key"] for r in rows} == EXPANSION_KEYS
            for row in rows:
                assert dataset_user(row["account_key"]).check_password(row["temporary_password"])
            assert all(
                not dataset_user(a.key).has_usable_password()
                for a in ACCOUNTS
                if a.key not in EXPANSION_KEYS
            )
            admin = dataset_user("it_admin_3")
            assert admin.role.code == "IT_ADMIN" and not admin.designations.exists()
            assert not admin.capability_overrides.exists()

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


class IncrementalParticipantExpansionTests(TestCase):
    def test_existing_113_account_dataset_expands_without_rewriting_uat(self):
        # Run the original population through the same unchanged units, then upgrade it.
        legacy_accounts = tuple(a for a in ACCOUNTS if a.key not in EXPANSION_KEYS)
        legacy_students = tuple(s for s in STUDENTS if s.key not in EXPANSION_KEYS)
        legacy_population = tuple(s for s in POPULATION_STUDENTS if s.key not in EXPANSION_KEYS)
        with ExitStack() as stack:
            for module, name, value in (
                ("seed", "ACCOUNTS", legacy_accounts),
                ("accounts", "ACCOUNTS", legacy_accounts),
                ("seed", "STUDENTS", legacy_students),
                ("history", "STUDENTS", legacy_students),
                ("organization", "STUDENTS", legacy_students),
                ("scenarios.background", "POPULATION_STUDENTS", legacy_population),
            ):
                stack.enter_context(patch(f"compass.staging_seed.{module}.{name}", value))
            original = seed_once()
        assert original.account_count == User.objects.count() == 113
        assert User.objects.filter(role__code="STUDENT").count() == 100

        student = dataset_user("ar_03")
        appointment = Appointment.objects.get(student=student)
        cancel_appointment(
            appointment_id=appointment.pk,
            actor=student,
            administrative=False,
            context=AuditContext.user(student),
        )
        other = dataset_user("ar_02")
        other.set_password("an evaluator retained this passphrase")
        other.save(update_fields=["password"])
        with patch(
            "compass.authentication.abuse.RedisRateLimiter.from_settings", lambda: AllowLimiter()
        ):
            response = login(
                Client(), email=other.email, password="an evaluator retained this passphrase"
            )
        assert response.status_code == 200
        assert AuthSession.objects.filter(user=other, revoked_at__isnull=True).exists()

        # Fingerprint every existing account/auth/domain row, including encrypted history and
        # routing. New audit events and transient Academic Year selection are allowed.
        labels = {
            "accounts",
            "authentication",
            "organization",
            "inventory",
            "appointments",
            "exit_interviews",
            "graduate_tracer",
            "good_moral",
            "counseling",
            "routine_interviews",
            "shared_summaries",
            "referrals",
            "call_slips",
            "guidance_messages",
            "feedback",
        }
        snapshots = []
        for model in apps.get_models():
            if (
                model._meta.app_label not in labels
                or model._meta.label == "organization.AcademicYear"
            ):
                continue
            rows = model.objects.order_by("pk")
            snapshots.append(
                (model, list(rows.values_list("pk", flat=True)), fingerprint(list(rows.values())))
            )

        expanded = seed_once()
        assert expanded.created["Accounts"] == 3
        assert (expanded.account_count, expanded.student_count) == (116, 102)
        assert User.objects.count() == 116
        for model, ids, before in snapshots:
            assert (
                fingerprint(list(model.objects.filter(pk__in=ids).order_by("pk").values()))
                == before
            ), model._meta.label
        for key in EXPANSION_KEYS:
            assert not dataset_user(key).has_usable_password()
        appointment.refresh_from_db()
        assert appointment.status == "CANCELLED"
        other.refresh_from_db()
        assert other.check_password("an evaluator retained this passphrase")
        result = verify_dataset(now=dataset_now(), allow_uat_changes=True)
        assert result.passed
        assert all(result.scenario_status[key] == "READY" for key in EXPANSION_SCENARIOS)
        with tempfile.TemporaryDirectory() as directory:
            assert len(write_reports(result, Path(directory))) == 6
        again = seed_once()
        assert sum(again.created.values()) == 0
