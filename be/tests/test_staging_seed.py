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
import uuid
from contextlib import ExitStack
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
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
from compass.feedback.models import CustomerFeedbackResponse, FeedbackOpportunity
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import create_my_current_student, create_my_graduate
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
    ACCOUNTS_BY_KEY,
    SCENARIOS,
    UAT_40_ALLOCATION,
    UAT_40_STAKEHOLDER_COUNTS,
    UAT_40_STUDENT_COLLEGES,
    UAT_40_STUDENT_QUOTA,
    Readiness,
    scenarios_for,
    validate_manifest,
)
from compass.staging_seed.reports import (
    ACCOUNTS_CSV,
    ASSIGNMENT,
    CATALOG,
    CSV_COLUMNS,
    GUIDE,
    SUMMARY,
    UAT_40_ASSIGNMENTS,
    UAT_40_COLUMNS,
    ReportError,
    _scan,
    render_reports,
    write_reports,
)
from compass.staging_seed.seed import SEED_RUN_ADVISORY_LOCK_KEY, seed_staging_dataset
from compass.staging_seed.students import (
    POPULATION_STUDENTS,
    PROMOTED_BACKGROUND,
    STUDENTS,
    STUDENTS_BY_KEY,
)
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
# The College-balanced allocation promotes seven background Students and adds their scenarios.
PROMOTED_KEYS = set(PROMOTED_BACKGROUND)
COLLEGE_SCENARIOS = {
    "STU-APT-07",
    "STU-GM-08",
    "STU-MSG-03",
    "STU-FB-02",
    "STU-APT-08",
    "STU-GM-09",
    "STU-APT-09",
    "STU-APT-10",
}
# Catalog text and assignment suitability; seeding never reads them.
CATALOG_ONLY_FIELDS = {"label", "summary", "limitations", "suitability"}
UAT_40_KEYS = [key for keys in UAT_40_ALLOCATION.values() for key in keys]
REPORTS = {
    CATALOG,
    ACCOUNTS_CSV,
    GUIDE,
    "UAT-SCENARIO-MATRIX.md",
    ASSIGNMENT,
    UAT_40_ASSIGNMENTS,
    SUMMARY,
}


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def pre_cont1b_catalog_snapshot(value):
    """Compare frozen historical catalog hashes with only the approved terminology reversed.

    Identity/structure/counts remain byte-sensitive; no hash is replaced to hide a change.
    """
    if isinstance(value, dict):
        return {key: pre_cont1b_catalog_snapshot(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [pre_cont1b_catalog_snapshot(item) for item in value]
    if isinstance(value, str):
        return (
            value.replace("Student Session Summaries", "Shared Summaries")
            .replace("Student Session Summary", "Shared Summary")
            .replace("student session summaries", "shared summaries")
            .replace("student session summary", "shared summary")
        )
    return value


def pre_acad_account_snapshot(account):
    """Keep the staged identity snapshot while allowing the approved year-level correction."""
    values = asdict(account)
    if account.key == "graduating":
        years = list(values["year_levels"])
        current_year, current_level = years[-1]
        assert current_level == 4
        years[-1] = (current_year, 5)
        values["year_levels"] = tuple(years)
    return pre_cont1b_catalog_snapshot(values)


def dataset_now() -> datetime:
    """The dataset's own clock: noon on the preparation date in Asia/Manila."""

    from compass.common.institutional_time import institution_zone

    return datetime.combine(ANCHOR, time(12), tzinfo=institution_zone())


def forbidden(*_args, **_kwargs):
    raise AssertionError("Seeding reached an external boundary.")


def seed_once():
    from compass.organization.bootstrap import initialize_organization_catalog

    initialize_organization_catalog(action="seed")
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


def identity(account) -> dict:
    return {
        k: v for k, v in pre_acad_account_snapshot(account).items() if k not in CATALOG_ONLY_FIELDS
    }


def test_expansions_preserve_every_seeded_identity_and_scenario_definition():
    # Frozen from staging 8684ea10 (113 accounts, 91 scenarios) and b917e0c8 (116 accounts,
    # 94 scenarios). The College promotion changes only catalog text and suitability. The
    # graduating Student's one unsupported fifth-year value is normalized back to the frozen
    # snapshot here; the dedicated seed regression below verifies the corrected fourth year.
    original_accounts = [a for a in ACCOUNTS if a.key not in EXPANSION_KEYS]
    original_scenarios = [
        pre_cont1b_catalog_snapshot(asdict(s))
        for s in SCENARIOS
        if s.id not in EXPANSION_SCENARIOS | COLLEGE_SCENARIOS
    ]
    assert len(original_accounts) == 113
    assert len(original_scenarios) == 91
    assert fingerprint([identity(a) for a in ACCOUNTS]) == (
        "56c9cd98a74255cc05d353346ba5939e40e11faafe8260fa356e99fb0fbbf9d6"
    )
    assert (
        fingerprint(
            [pre_acad_account_snapshot(a) for a in original_accounts if a.key not in PROMOTED_KEYS]
        )
        == "6ddaa162ce458270f175d8cb0c8fd3aa257f08ee3c1bfec7fa0f2d7bcf4a8ae7"
    )
    assert fingerprint(original_scenarios) == (
        "1b63b4f8283d740993af7eccdafdc034565e15a5de26263b83b4af6775ddffa8"
    )
    assert fingerprint(
        [pre_cont1b_catalog_snapshot(asdict(s)) for s in SCENARIOS if s.id not in COLLEGE_SCENARIOS]
    ) == ("604231c50af3d63ec0f4462ea1939756b48b4d35acf18ce78f4d88ae74412b04")
    assert len(ACCOUNTS) == 116 and len(SCENARIOS) == 102
    for key in PROMOTED_KEYS:
        student = STUDENTS_BY_KEY[key]
        assert student.group == StudentGroup.BACKGROUND
        assert student.suitability == Suitability.PARTICIPANT
        assert {s.id for s in scenarios_for(key)} <= COLLEGE_SCENARIOS
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
        "ITSO Personnel": 3,
        "Data Protection Officer": 1,
    }
    assert UAT_40_STAKEHOLDER_COUNTS == {k: len(v) for k, v in UAT_40_ALLOCATION.items()}
    assert len(UAT_40_KEYS) == len(set(UAT_40_KEYS)) == 40
    for key in UAT_40_KEYS:
        account = ACCOUNTS_BY_KEY[key]
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
    alumni = [STUDENTS_BY_KEY[key] for key in UAT_40_ALLOCATION["Alumni"]]
    assert len({a.institutional_id for a in alumni}) == 5
    assert all(not a.affiliated and a.auth == AuthPlan.CREDENTIAL for a in alumni)


def test_25_current_students_follow_the_finalized_college_distribution():
    assert UAT_40_STUDENT_QUOTA == {
        "CCMS": 3,
        "CAS": 3,
        "CBPA": 3,
        "COENG": 3,
        "COED": 3,
        "CFAST": 3,
        "CANR": 3,
        "COTT": 2,
        "ENTIENZA": 2,
    }
    current = UAT_40_ALLOCATION["Current Student"]
    assert list(current) == [key for keys in UAT_40_STUDENT_COLLEGES.values() for key in keys]
    distribution = {}
    for key in current:
        student = STUDENTS_BY_KEY[key]
        assert student.lifecycle == Lifecycle.CURRENT and student.affiliated
        assert student.auth == AuthPlan.CREDENTIAL
        assert student.suitability == Suitability.PARTICIPANT
        distribution[student.college_code] = distribution.get(student.college_code, 0) + 1
    assert distribution == UAT_40_STUDENT_QUOTA
    assert sum(distribution.values()) == 25
    for college, keys in UAT_40_STUDENT_COLLEGES.items():
        assert {STUDENTS_BY_KEY[key].college_code for key in keys} == {college}
    # Every promoted background Student is allocated, so none is an unused participant.
    assert PROMOTED_KEYS <= set(current)
    assert PROMOTED_KEYS == {"bg_47", "bg_54", "bg_55", "bg_56", "bg_58", "bg_59", "bg_60"}


def test_40_person_staff_roles_designations_and_scenario_ownership():
    expected_staff = {
        "Head Guidance Counselor": ("COUNSELOR", {"HEAD_GUIDANCE_COUNSELOR"}),
        "Guidance Counselor": ("COUNSELOR", set()),
        "Guidance Services Staff": ("GUIDANCE_SERVICES_STAFF", set()),
        "ITSO Personnel": ("IT_ADMIN", set()),
        "Data Protection Officer": ("INSTITUTIONAL_OFFICER", {"DPO"}),
    }
    for category, (role, designations) in expected_staff.items():
        for key in UAT_40_ALLOCATION[category]:
            account = ACCOUNTS_BY_KEY[key]
            assert (account.role, set(account.designations)) == (role, designations), key
    for category in ("Current Student", "Alumni"):
        assert all(ACCOUNTS_BY_KEY[key].role == "STUDENT" for key in UAT_40_ALLOCATION[category])
    # Every allocated participant owns its scenarios; no scenario has two allocated actors.
    owners = {}
    for scenario in SCENARIOS:
        if scenario.account in UAT_40_KEYS and scenario.readiness == Readiness.EXECUTABLE:
            owners.setdefault(scenario.id, set()).add(scenario.account)
    assert all(len(accounts) == 1 for accounts in owners.values())
    assert {next(iter(a)) for a in owners.values()} == set(UAT_40_KEYS)
    # A promoted Student's starting state is consumed by at most one mutating scenario.
    for key in PROMOTED_KEYS:
        consumers = {}
        for scenario in SCENARIOS:
            for subject, predicate in scenario.checks:
                if subject == key and scenario.mutating:
                    consumers.setdefault(predicate, []).append(scenario.id)
        assert all(len(ids) == 1 for ids in consumers.values()), (key, consumers)


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

    def test_graduating_bachelors_seed_uses_supported_year_levels(self):
        persona = STUDENTS_BY_KEY["graduating"]
        assert persona.program_code == "BSBA"
        assert [level for _year, level in persona.year_levels] == [3, 4, 4]

        current = StudentInventory.objects.get(
            student=dataset_user("graduating"), academic_year__is_current=True
        )
        assert current.program.code == persona.program_code
        assert current.year_level == 4

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
            now=dataset_now(),
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

    def test_cont1b_scoped_summary_regeneration_is_repeatable_and_preserves_dataset(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        from compass.counseling.models import CounselingEncounter, StudentSessionSummary

        records = list(
            StudentSessionSummary.objects.order_by("pk").values(
                "id", "encounter_id", "published_at", "created_at", "updated_at"
            )
        )
        assert len(records) == 4
        encounter_rows = list(CounselingEncounter.objects.order_by("pk").values())
        credentials = list(User.objects.order_by("pk").values("pk", "password"))
        audit_ids = set(AuditEvent.objects.values_list("pk", flat=True))
        config = connection.settings_dict
        plan = json.loads(
            json.dumps(
                {
                    "format": "cont-1b-disposable-scope-v1",
                    "database": {
                        name.lower(): str(config[name]) for name in ("NAME", "HOST", "PORT")
                    },
                    "summary_ids": [str(record["id"]) for record in records],
                    "summary_records": records,
                },
                default=str,
            )
        )
        plan["scope_digest"] = hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # Explicitly disposable local synthetic fixture scope, not a deployed-data operation.
        Notification.objects.filter(
            source_type="student_session_summary", source_id__in=plan["summary_ids"]
        ).delete()
        StudentSessionSummary.objects.filter(pk__in=plan["summary_ids"]).delete()
        with tempfile.TemporaryDirectory(prefix="cont1b-regeneration-") as folder:
            scope, approval = Path(folder) / "scope.json", Path(folder) / "approval.json"
            scope.write_text(json.dumps(plan))
            approval.write_text(
                json.dumps(
                    {
                        "scope_digest": plan["scope_digest"],
                        "disposable_synthetic": True,
                        "consumers_stopped": True,
                        "regenerate_known_fixtures": True,
                        "approved_by": "isolated-dataset-test",
                    }
                )
            )
            for expected in (4, 0):
                out = StringIO()
                with override_settings(STAGING_SEED_ENABLED=True):
                    call_command(
                        "regenerate_student_session_summaries",
                        plan_file=scope,
                        approval_file=approval,
                        stdout=out,
                    )
                assert f"created: {expected};" in out.getvalue()
        assert list(CounselingEncounter.objects.order_by("pk").values()) == encounter_rows
        assert list(User.objects.order_by("pk").values("pk", "password")) == credentials
        assert audit_ids <= set(AuditEvent.objects.values_list("pk", flat=True))
        publication = Notification.objects.filter(
            event_code="counseling.student_session_summary.published"
        )
        assert publication.count() == 3
        assert not EmailDelivery.objects.filter(notification__in=publication).exists()
        assert not PushDelivery.objects.filter(notification__in=publication).exists()
        assert self.verify().passed
        assert sum(seed_once().created.values()) == 0

    def test_reports_are_complete_consistent_and_secret_free(self):
        result = self.verify()
        documents = render_reports(result)
        assert set(documents) == REPORTS
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
        uat_40 = list(csv.DictReader(StringIO(documents[UAT_40_ASSIGNMENTS])))
        assert tuple(uat_40[0]) == UAT_40_COLUMNS
        assert [row["account_key"] for row in uat_40] == UAT_40_KEYS
        assert [row["participant_reference"] for row in uat_40] == [
            f"UAT40-{n:02d}" for n in range(1, 41)
        ]
        for row in uat_40:
            account = ACCOUNTS_BY_KEY[row["account_key"]]
            assert row["institutional_id"] == account.institutional_id
            assert row["login_email"] == dataset_user(account.key).email
            assert row["canonical_role"] == account.role
            assert row["assigned_scenario_ids"]
            assert all(not row[column] for column in UAT_40_COLUMNS[8:])
        current = [row for row in uat_40 if row["stakeholder_category"] == "Current Student"]
        assert {
            unit: sum(row["college_academic_unit"] == unit for row in current)
            for unit in {row["college_academic_unit"] for row in current}
        } == {"Entienza" if c == "ENTIENZA" else c: n for c, n in UAT_40_STUDENT_QUOTA.items()}
        for key in PROMOTED_KEYS:
            assert f"| {key} |" in documents[CATALOG]
        assert "promoted to UAT-ready" in documents[CATALOG]
        assert "| COTT | College of Trades and Technology | 2 |" in documents[GUIDE]
        assert documents[GUIDE].count("  --account ") == 40
        assert "COTT 2, Entienza 2" in documents[SUMMARY]
        with tempfile.TemporaryDirectory() as directory:
            assert len(write_reports(result, Path(directory))) == 7

    def test_promoted_students_can_complete_their_own_scenarios(self):
        from compass.appointments.services import (
            list_bookable_slots,
            reschedule_appointment,
        )
        from compass.feedback.services import create_customer_feedback
        from compass.good_moral.models import CANONICAL_YEAR_LEVELS
        from compass.guidance_messages.services import open_office_thread
        from compass.staging_seed.content import narratives
        from compass.staging_seed.timeline import academic_semester
        from compass.staging_seed.workflows import counseling_service

        now = dataset_now()
        service = counseling_service()
        counselors = {"bg_47": "counselor_a", "bg_56": "counselor_c", "bg_60": "counselor_c"}
        for key, counselor in counselors.items():
            student = dataset_user(key)
            slots = [
                slot
                for offset in range(1, 15)
                for slot in list_bookable_slots(
                    student=student,
                    service_id=service.pk,
                    provider_id=dataset_user(counselor).pk,
                    delivery_mode="IN_PERSON",
                    target_date=ANCHOR + timedelta(days=offset),
                    now=now,
                ).items
            ]
            assert slots, key

        bg_59 = dataset_user("bg_59")
        upcoming = Appointment.objects.get(student=bg_59, status="SCHEDULED")
        assert upcoming.provider_id == dataset_user("counselor_c").pk
        later = [
            slot
            for offset in range(1, 21)
            for slot in list_bookable_slots(
                student=bg_59,
                service_id=service.pk,
                provider_id=upcoming.provider_id,
                delivery_mode="IN_PERSON",
                target_date=ANCHOR + timedelta(days=offset),
                now=now,
            ).items
            if slot.starts_at != upcoming.starts_at
        ]
        moved = reschedule_appointment(
            appointment_id=upcoming.pk,
            actor=bg_59,
            starts_at=later[0].starts_at,
            reason="UAT reschedule",
            administrative=False,
            context=AuditContext.user(bg_59),
            now=now,
        )
        assert moved.starts_at == later[0].starts_at and moved.status == "SCHEDULED"

        bg_55 = dataset_user("bg_55")
        opportunity = FeedbackOpportunity.objects.get(
            student=bg_55, customer_feedback_submitted_at__isnull=True
        )
        values = dict(next(iter(narratives.CUSTOMER_FEEDBACK.values())))
        responses = CustomerFeedbackResponse.objects.count()
        create_customer_feedback(
            student=bg_55,
            opportunity_id=opportunity.pk,
            values=values,
            context=AuditContext.user(bg_55),
        )
        opportunity.refresh_from_db()
        assert opportunity.customer_feedback_submitted_at is not None
        assert CustomerFeedbackResponse.objects.count() == responses + 1

        bg_58 = dataset_user("bg_58")
        request = create_my_current_student(
            student=bg_58,
            year_level=CANONICAL_YEAR_LEVELS[STUDENTS_BY_KEY["bg_58"].current_year_level - 1],
            semester=academic_semester(ANCHOR),
            idempotency_key="uat-college-good-moral",
            request_fingerprint=hashlib.sha256(b"uat-college-good-moral").hexdigest(),
            context=AuditContext.user(bg_58),
        )
        assert request.status == "REQUESTED"

        bg_54 = dataset_user("bg_54")
        thread, _message = open_office_thread(
            actor=bg_54,
            client_message_id=uuid.uuid4(),
            body="UAT: a question for the Guidance Office.",
            context=AuditContext.user(bg_54),
        )
        assert thread.kind == "OFFICE" and thread.student_id == bg_54.pk
        assert thread.assigned_to_id == dataset_user("counselor_c").pk

        assert not self.verify().passed
        changed = self.verify(allow_uat_changes=True)
        assert changed.passed
        # A rescheduled Appointment is still upcoming, so STU-APT-09 stays READY like STU-APT-03.
        assert changed.scenario_status["STU-APT-09"] == "READY"
        for scenario in ("STU-FB-02", "STU-GM-09", "STU-MSG-03"):
            assert any(scenario in w for s in changed.sections for w in s.warnings), scenario

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

    def test_the_40_person_selection_issues_exactly_40_independent_credentials(self):
        with tempfile.TemporaryDirectory(prefix="stg-uat-40-") as directory:
            target = Path(directory) / "uat-40.csv"
            outcome = issue_credentials(output=target, account_keys=tuple(UAT_40_KEYS))
            assert (outcome.issued, outcome.skipped) == (40, 0)
            assert stat.S_IMODE(target.stat().st_mode) == 0o600
            rows = list(csv.DictReader(target.open()))
            assert [row["account_key"] for row in rows] == UAT_40_KEYS
            passwords = [row["temporary_password"] for row in rows]
            assert len(set(passwords)) == 40
            for row in rows:
                user = dataset_user(row["account_key"])
                assert user.check_password(row["temporary_password"])
                assert row["email"] == user.email
            allocated = set(UAT_40_KEYS)
            assert all(
                not dataset_user(a.key).has_usable_password()
                for a in ACCOUNTS
                if a.key not in allocated
            )
            again = issue_credentials(
                output=Path(directory) / "again.csv", account_keys=tuple(UAT_40_KEYS)
            )
            assert (again.issued, again.skipped) == (0, 40)

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
                assert set(os.listdir(directory)) == REPORTS


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
            now=dataset_now(),
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
            "student_session_summaries",
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
            assert len(write_reports(result, Path(directory))) == 7
        again = seed_once()
        assert sum(again.created.values()) == 0


@pytest.mark.django_db
def test_full_seeder_repeat_refuses_retired_fixture_without_repairing_catalog():
    from compass.organization.models import Program

    seed_once()
    Program.objects.filter(code="BSIS", college__code="CCMS").update(
        name="Approved rename and retirement",
        is_active=False,
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 3, 5],
    )
    before = list(Program.objects.order_by("pk").values())
    with pytest.raises(Exception, match="synchronized active catalog"):
        seed_once()
    assert list(Program.objects.order_by("pk").values()) == before
