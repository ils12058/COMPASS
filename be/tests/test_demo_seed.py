"""Focused tests for the staging-only ``seed_demo_staging`` demo dataset."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import UUID

import psycopg
import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from compass.accounts.models import User
from compass.activity.projections import get_my_activity
from compass.announcements.models import Announcement
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.models import AuditEvent
from compass.authentication.models import (
    AuthSession,
    EmailChangeRequest,
    EmailOTPChallenge,
    EmailOTPPurpose,
    LoginChallenge,
    RecoveryCode,
    TOTPFactor,
    TrustedSession,
)
from compass.authentication.password_access import (
    confirm_password_access,
    request_password_access,
)
from compass.authentication.sessions import create_auth_session
from compass.availability.models import (
    OfficeAvailabilityWindow,
    OfficeUnavailability,
    ProviderAvailabilityWindow,
    ProviderUnavailability,
)
from compass.call_slips.models import CallSlip, CallSlipIssuanceMode, CallSlipLifecycleState
from compass.call_slips.services import build_call_slip_render_context
from compass.common.rate_limit import RateLimitResult
from compass.counseling.models import CounselingEncounter, CounselingSharedSummary
from compass.demo_seed import DEMO_DATASET_VERSION
from compass.demo_seed.cast import (
    ACTIVE_REFERRAL,
    ALUMNI,
    CAST,
    COUNSELOR_A,
    COUNSELOR_B,
    DPO,
    FIRST_YEAR,
    FORMER,
    FORMER_STAFF,
    FOURTH_YEAR,
    GOOD_MORAL,
    GRADUATING,
    GUIDANCE_STAFF,
    HEAD_GUIDANCE,
    IT_ADMIN,
    ONBOARDING,
    RECENT_GRADUATE,
    REFERRED,
    SECOND_YEAR,
    STAFF,
    STUDENTS,
    AuthState,
)
from compass.demo_seed.config import DemoConfigurationError, load_demo_config
from compass.demo_seed.guard import DemoSeedingRefused, ensure_demo_seeding_allowed
from compass.demo_seed.narratives import (
    ADJUSTMENT_EVALUATION,
    ADJUSTMENT_INTAKE,
    REFERRED_INTAKE,
    WALK_IN_EVALUATION,
    WALK_IN_INTAKE,
)
from compass.demo_seed.seed import SEED_RUN_ADVISORY_LOCK_KEY, seed_demo_staging
from compass.demo_seed.timeline import (
    DemoTimelineError,
    academic_semester,
    resolve_timeline,
)
from compass.documents.rendering import render_document_html
from compass.exit_interviews.models import ExitInterview, ExitInterviewStatus
from compass.feedback.models import (
    ClientSatisfactionResponse,
    CustomerFeedbackResponse,
    FeedbackOpportunity,
)
from compass.good_moral.models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from compass.good_moral.services import build_certificate_render_context
from compass.graduate_tracer.models import GraduateTracerResponse, GraduateTracerStatus
from compass.inventory.models import StudentInventory
from compass.inventory.services import list_inventory_students
from compass.notifications.models import EmailDelivery, Notification
from compass.operational_students import list_scoped_operational_students
from compass.organization.models import (
    AcademicYear,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.organization.services import set_counselor_responsibility
from compass.overview.services import build_overview_summary
from compass.privacy_governance.activity import list_privacy_activity
from compass.privacy_governance.models import (
    PrivacyNotice,
    PrivacyNoticeRevisionStatus,
    RetentionPolicy,
)
from compass.referrals.models import Referral, ReferralAction
from compass.referrals.services import build_referral_render_context
from compass.reports.graduate_tracer import build_graduate_tracer_report
from compass.reports.services import build_student_profiling_report, resolve_report_access_scope
from compass.resources.models import Resource
from compass.routine_interviews.content import (
    CIPHERTEXT_COLUMNS,
    EVALUATION_FIELDS,
    INTAKE_FIELDS,
    read_evaluation,
    read_intake,
)
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import ServiceDeliveryMode
from compass.student_support.services import get_student_support_context

DEMO_PASSWORD = "amber harbor lanterns at dusk"
ANCHOR = date(2026, 9, 28)
COMMAND = "seed_demo_staging"
DEMO_OPTIONAL_VARIABLES = (
    "DEMO_ACCOUNT_PASSWORD_FILE",
    "DEMO_EMAIL_DOMAIN",
    "DEMO_EMAIL_DOMAIN_FILE",
    "DEMO_ONBOARDING_EMAIL",
    "DEMO_ONBOARDING_EMAIL_FILE",
)


class AllowLimiter:
    def consume_with_failure_policy(self, policy, subject):
        return RateLimitResult(
            allowed=True,
            count=1,
            limit=policy.limit,
            remaining=policy.limit - 1,
            retry_after_seconds=0,
        )


@pytest.fixture
def demo_env(monkeypatch):
    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD", DEMO_PASSWORD)
    for name in DEMO_OPTIONAL_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    # A fixed past anchor keeps the demo timeline deterministic whatever day the suite runs.
    monkeypatch.setattr("compass.demo_seed.timeline.institution_today", lambda: ANCHOR)


@pytest.fixture
def seeded(db, demo_env):
    return seed_demo_staging()


def demo_user(persona) -> User:
    return User.objects.select_related("role").get(institutional_id=persona.institutional_id)


def _demo_user_ids() -> list:
    return list(
        User.objects.filter(
            institutional_id__in=[persona.institutional_id for persona in CAST]
        ).values_list("pk", flat=True)
    )


def _anchor_time(hour: int = 0) -> datetime:
    return timezone.make_aware(datetime.combine(ANCHOR, time(hour)))


def _raw_routine_row(routine_interview_id) -> dict[str, object]:
    table = RoutineInterview._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{table}" WHERE id = %s', [routine_interview_id])
        names = [column.name for column in cursor.description]
        return dict(zip(names, cursor.fetchone(), strict=True))


# --- Environment boundary --------------------------------------------------------------------


@pytest.mark.parametrize("app_env", ["local-staging", "live-staging"])
def test_guard_allows_only_the_explicit_staging_modes_with_opt_in(app_env):
    assert ensure_demo_seeding_allowed(app_env=app_env, seeding_enabled=True) == app_env


@pytest.mark.parametrize(
    ("app_env", "enabled"),
    [
        ("live-staging", False),
        ("local-staging", False),
        ("live-staging", "true"),
        ("production", True),
        ("live-production", True),
        ("staging", True),
        ("prod", True),
        ("", True),
        (None, True),
    ],
)
def test_guard_fails_closed_and_the_opt_in_never_widens_the_allowlist(app_env, enabled):
    with pytest.raises(DemoSeedingRefused):
        ensure_demo_seeding_allowed(app_env=app_env, seeding_enabled=enabled)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("app_env", "enabled", "message"),
    [
        ("live-staging", False, "disabled for live-staging"),
        ("production", True, "refused for APP_ENV='production'"),
        ("future-mode", True, "refused for APP_ENV='future-mode'"),
    ],
)
def test_command_refuses_before_reading_secrets_or_touching_the_database(
    monkeypatch, app_env, enabled, message
):
    monkeypatch.delenv("DEMO_ACCOUNT_PASSWORD", raising=False)
    with override_settings(APP_ENV=app_env, DEMO_SEEDING_ENABLED=enabled):
        with pytest.raises(CommandError, match=message):
            call_command(COMMAND, stdout=StringIO())
    assert not User.objects.exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_live_staging_with_opt_in_seeds_using_the_configured_domain(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_EMAIL_DOMAIN", "Demo.Example.ORG")
    with override_settings(APP_ENV="live-staging", DEMO_SEEDING_ENABLED=True):
        call_command(COMMAND, stdout=StringIO())
    assert demo_user(IT_ADMIN).email == "demo-admin@demo.example.org"
    assert demo_user(FIRST_YEAR).check_password(DEMO_PASSWORD)


@pytest.mark.django_db
def test_live_staging_requires_an_operator_controlled_email_domain(demo_env):
    with override_settings(APP_ENV="live-staging", DEMO_SEEDING_ENABLED=True):
        with pytest.raises(CommandError, match="DEMO_EMAIL_DOMAIN is required in live-staging"):
            call_command(COMMAND, stdout=StringIO())
    assert not User.objects.exists()


# --- Credentials and configuration -----------------------------------------------------------


@pytest.mark.django_db
def test_missing_demo_password_fails_before_any_write(demo_env, monkeypatch):
    monkeypatch.delenv("DEMO_ACCOUNT_PASSWORD")
    with pytest.raises(CommandError, match="DEMO_ACCOUNT_PASSWORD or DEMO_ACCOUNT_PASSWORD_FILE"):
        call_command(COMMAND, stdout=StringIO())
    assert not User.objects.exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "weak",
    [
        "short-secret",  # below the 15-character minimum
        "4829105736284910",  # entirely numeric
        "demo-admin@compass-demo.test",  # identical to a persona's email address
    ],
)
def test_weak_demo_password_is_rejected_by_the_normal_policy_without_echo(
    demo_env, monkeypatch, weak
):
    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD", weak)
    with pytest.raises(CommandError, match="password policy") as excinfo:
        call_command(COMMAND, stdout=StringIO())
    assert weak not in str(excinfo.value)
    assert not User.objects.exists()


def test_demo_config_reads_the_password_file_convention_and_never_reprs_it(
    demo_env, monkeypatch, tmp_path
):
    secret_file = tmp_path / "demo_password"
    secret_file.write_text(DEMO_PASSWORD + "\n", encoding="utf-8")
    monkeypatch.delenv("DEMO_ACCOUNT_PASSWORD")
    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD_FILE", str(secret_file))
    monkeypatch.setenv("DEMO_ONBOARDING_EMAIL", "Onboarding.Demo@Example.org")

    config = load_demo_config(app_env="local-staging")

    assert config.password == DEMO_PASSWORD
    assert config.email_domain == "compass-demo.test"
    assert config.onboarding_email == "onboarding.demo@example.org"
    assert DEMO_PASSWORD not in repr(config)

    monkeypatch.setenv("DEMO_ACCOUNT_PASSWORD", DEMO_PASSWORD)
    with pytest.raises(DemoConfigurationError, match="cannot both be set"):
        load_demo_config(app_env="local-staging")


@pytest.mark.parametrize("domain", ["not a domain", "user@example.org", "example"])
def test_demo_email_domain_must_be_a_bare_valid_domain(demo_env, monkeypatch, domain):
    monkeypatch.setenv("DEMO_EMAIL_DOMAIN", domain)
    with pytest.raises(DemoConfigurationError, match="DEMO_EMAIL_DOMAIN"):
        load_demo_config(app_env="live-staging")


@pytest.mark.django_db
def test_clean_seed_credentials_auth_state_and_secret_hygiene(demo_env, caplog):
    caplog.set_level(logging.DEBUG)
    stdout = StringIO()
    call_command(COMMAND, stdout=stdout)
    output = stdout.getvalue()

    assert "COMPASS staging demo dataset ready." in output
    assert f"Dataset version: {DEMO_DATASET_VERSION}" in output
    assert "Password: configured externally; not displayed." in output
    assert DEMO_PASSWORD not in output
    logged = "\n".join(json.dumps(record.__dict__, default=str) for record in caplog.records)
    assert DEMO_PASSWORD not in logged
    audit_json = json.dumps(list(AuditEvent.objects.values_list("metadata", flat=True)))
    assert DEMO_PASSWORD not in audit_json

    for persona in CAST:
        user = demo_user(persona)
        assert user.email in output
        assert user.institutional_id.startswith("DEMO-2026-")
        if persona.auth_state == AuthState.READY:
            assert user.has_usable_password()
            assert user.check_password(DEMO_PASSWORD)
            assert user.email_verified_at is not None
        else:
            assert persona is ONBOARDING
            assert user.is_active
            assert not user.has_usable_password()
            assert user.email_verified_at is None
        assert user.is_active is persona.active

    demo_ids = _demo_user_ids()
    for model in (
        AuthSession,
        TrustedSession,
        LoginChallenge,
        EmailOTPChallenge,
        TOTPFactor,
        RecoveryCode,
        EmailChangeRequest,
    ):
        assert not model.objects.filter(user_id__in=demo_ids).exists(), model.__name__

    disabled = demo_user(FORMER_STAFF)
    assert not disabled.is_active
    assert disabled.check_password(DEMO_PASSWORD)
    assert "demo-former-staff@compass-demo.test" in output


@pytest.mark.django_db
def test_onboarding_persona_resolves_to_the_real_first_password_flow(seeded, monkeypatch):
    monkeypatch.setattr(
        "compass.authentication.abuse.RedisRateLimiter.from_settings",
        lambda: AllowLimiter(),
    )
    onboarding = demo_user(ONBOARDING)
    with (
        patch("compass.authentication.email_otp._new_code", return_value="246810"),
        patch("compass.authentication.email_otp.deliver_email_otp.delay"),
    ):
        challenge = request_password_access(email=onboarding.email).challenge
    assert challenge.purpose == EmailOTPPurpose.EMAIL_VERIFICATION
    assert challenge.user_id == onboarding.pk

    confirm_password_access(
        challenge_id=challenge.pk,
        code="246810",
        new_password="my own onboarding passphrase",
    )
    onboarding.refresh_from_db()
    assert onboarding.check_password("my own onboarding passphrase")
    completed = (onboarding.password, onboarding.email_verified_at)
    assert completed[1] is not None

    report = seed_demo_staging()

    onboarding.refresh_from_db()
    assert (onboarding.password, onboarding.email_verified_at) == completed
    line = next(item for item in report.accounts if item.email == onboarding.email)
    assert line.auth == "onboarding completed"


# --- External side effects ---------------------------------------------------------------------


@pytest.mark.django_db
def test_seeding_makes_no_external_calls_and_sends_no_email(
    db, demo_env, django_capture_on_commit_callbacks
):
    def forbidden(*args, **kwargs):
        raise AssertionError("seeding must not reach an external service")

    delivered: list[str] = []

    def deliver_now(delivery_id):
        from compass.notifications.delivery import deliver_email_delivery

        delivered.append(deliver_email_delivery(UUID(delivery_id)))

    with (
        patch("compass.integrations.daily.urlopen", side_effect=forbidden),
        patch("compass.integrations.daily.DailyClient.from_settings", side_effect=forbidden),
        patch("compass.integrations.psgc.urlopen", side_effect=forbidden),
        patch("compass.integrations.psgc.PSGCClient.from_settings", side_effect=forbidden),
        patch("compass.documents.rendering.sync_playwright", side_effect=forbidden),
        patch("compass.integrations.storage.ObjectStorage.save", side_effect=forbidden),
        patch("compass.integrations.mail.Mailer.send", side_effect=forbidden) as send,
        patch(
            "compass.notifications.tasks.deliver_notification_email.delay",
            side_effect=deliver_now,
        ),
        patch("urllib.request.urlopen", side_effect=forbidden),
        django_capture_on_commit_callbacks(execute=True),
    ):
        report = seed_demo_staging()

    send.assert_not_called()
    # Services queued email kicks on commit; each finds no delivery row and does nothing.
    assert delivered and set(delivered) == {"skipped"}
    assert not EmailDelivery.objects.exists()
    assert Notification.objects.exists()
    assert dict(report.records)["Pending demo emails"] == "0"


# --- One clean seed: accounts, cohorts, domains, derived surfaces, encryption, audit ----------


class SeededDemoDatasetTests(TestCase):
    """Read-only checks share one clean seed; each test still runs in its own savepoint."""

    @classmethod
    def setUpTestData(cls):
        environment = {"DEMO_ACCOUNT_PASSWORD": DEMO_PASSWORD}
        with (
            patch.dict(os.environ, environment),
            patch("compass.demo_seed.timeline.institution_today", return_value=ANCHOR),
        ):
            for name in DEMO_OPTIONAL_VARIABLES:
                os.environ.pop(name, None)
            cls.report = seed_demo_staging()

    def test_roles_designations_lifecycle_and_account_state_are_independent(self):
        head = demo_user(HEAD_GUIDANCE)
        assert head.role.code == "COUNSELOR"
        assert list(head.designations.values_list("code", flat=True)) == ["HEAD_GUIDANCE_COUNSELOR"]
        dpo = demo_user(DPO)
        assert dpo.role.code == "INSTITUTIONAL_OFFICER"
        assert list(dpo.designations.values_list("code", flat=True)) == ["DPO"]
        assert demo_user(IT_ADMIN).role.code == "IT_ADMIN"
        assert demo_user(GUIDANCE_STAFF).role.code == "GUIDANCE_SERVICES_STAFF"

        expected = {persona.key: persona.lifecycle for persona in STUDENTS}
        for persona in STUDENTS:
            user = demo_user(persona)
            assert user.student_lifecycle_status == expected[persona.key]
            # Lifecycle never implies account state: every Student account stays active.
            assert user.is_active
        assert demo_user(RECENT_GRADUATE).has_usable_password()
        assert demo_user(FORMER).has_usable_password()
        assert StudentInventory.objects.filter(student=demo_user(FORMER)).count() == 1

        # A disabled former staff member stays referenceable from records they entered.
        former_staff = demo_user(FORMER_STAFF)
        assert not former_staff.is_active
        assert Referral.objects.filter(recorded_by=former_staff).count() == 1
        assert CallSlip.objects.filter(recorded_by=former_staff).count() == 1
        assert Announcement.objects.filter(created_by=former_staff, status="ARCHIVED").count() == 1
        assert not StaffSupervision.objects.filter(staff=former_staff).exists()

    def test_graduates_and_former_students_are_never_current_classmates(self):
        for persona in (RECENT_GRADUATE, ALUMNI, FORMER):
            assert not StudentAffiliation.objects.filter(student=demo_user(persona)).exists()
        for persona in STUDENTS:
            if persona.lifecycle == "CURRENT":
                affiliation = StudentAffiliation.objects.select_related("college").get(
                    student=demo_user(persona)
                )
                assert affiliation.college.code == persona.college_code

        # Operational pickers require CURRENT lifecycle even for the institution-wide Head.
        for actor in (HEAD_GUIDANCE, COUNSELOR_A, COUNSELOR_B, GUIDANCE_STAFF):
            visible = {
                item.id
                for item in list_scoped_operational_students(
                    actor=demo_user(actor), page_size=50
                ).items
            }
            assert visible
            for persona in (RECENT_GRADUATE, ALUMNI, FORMER):
                assert demo_user(persona).pk not in visible
        head_roster = {
            row.student.pk
            for row in list_inventory_students(actor=demo_user(HEAD_GUIDANCE), page_size=50).items
        }
        assert head_roster == {
            demo_user(persona).pk for persona in STUDENTS if persona.lifecycle == "CURRENT"
        }

        current = AcademicYear.objects.get(is_current=True)
        assert not StudentInventory.objects.filter(
            academic_year=current,
            student__in=[demo_user(p) for p in (RECENT_GRADUATE, ALUMNI, FORMER)],
        ).exists()

    def test_academic_years_and_cohort_histories_are_coherent(self):
        assert list(AcademicYear.objects.order_by("label").values_list("label", "is_current")) == [
            ("2024-2025", False),
            ("2025-2026", False),
            ("2026-2027", True),
        ]
        for persona in STUDENTS:
            rows = {
                item.academic_year.label: item
                for item in StudentInventory.objects.select_related(
                    "academic_year", "program"
                ).filter(student=demo_user(persona))
            }
            assert {label: item.year_level for label, item in rows.items()} == dict(
                persona.year_levels
            )
            for label, item in rows.items():
                assert item.program.code == persona.program_code
                start_year = int(label[:4])
                if item.submitted_at is not None:
                    submitted = timezone.localtime(item.submitted_at).date()
                    assert date(start_year, 8, 1) <= submitted <= date(start_year + 1, 5, 31)
                    assert item.created_at <= item.submitted_at
        assert set(dict(FIRST_YEAR.year_levels)) == {"2026-2027"}
        assert len(FOURTH_YEAR.year_levels) == 3
        assert StudentInventory.objects.filter(student=demo_user(ONBOARDING)).count() == 0

        draft = StudentInventory.objects.get(
            student=demo_user(ACTIVE_REFERRAL), academic_year__label="2026-2027"
        )
        assert draft.submitted_at is None

        # Graduates' last enrolled year is historical; their graduate records follow graduation.
        recent = ExitInterview.objects.get(student=demo_user(RECENT_GRADUATE))
        assert recent.academic_year.label == "2025-2026"
        assert recent.status == ExitInterviewStatus.SUBMITTED
        assert timezone.localtime(recent.first_submitted_at).date() < date(2026, 6, 26)
        alumni_tracer = GraduateTracerResponse.objects.get(student=demo_user(ALUMNI))
        assert alumni_tracer.status == GraduateTracerStatus.SUBMITTED
        assert timezone.localtime(alumni_tracer.submitted_at).date() > date(2025, 6, 27)
        for persona in STUDENTS:
            if persona.lifecycle == "CURRENT":
                assert not GraduateTracerResponse.objects.filter(
                    student=demo_user(persona)
                ).exists()
        current_exit = ExitInterview.objects.get(student=demo_user(GRADUATING))
        assert current_exit.academic_year.label == "2026-2027"
        assert current_exit.status == ExitInterviewStatus.DRAFT
        assert ExitInterview.objects.filter(student__in=_demo_user_ids()).count() == 3

    def test_configuration_relationships_and_availability(self):
        responsibilities = {
            (item.college.code, item.counselor_id)
            for item in CounselorResponsibility.objects.select_related("college")
        }
        assert responsibilities == {
            ("CCMS", demo_user(COUNSELOR_A).pk),
            ("CAS", demo_user(COUNSELOR_A).pk),
            ("CBPA", demo_user(COUNSELOR_B).pk),
            ("COED", demo_user(COUNSELOR_B).pk),
        }
        assert StaffSupervision.objects.get(
            staff=demo_user(GUIDANCE_STAFF)
        ).supervisor == demo_user(COUNSELOR_A)
        modes = set(ServiceDeliveryMode.objects.values_list("mode", flat=True))
        assert modes == {"IN_PERSON", "ONLINE"}
        assert OfficeAvailabilityWindow.objects.count() == 10
        for persona in (HEAD_GUIDANCE, COUNSELOR_A, COUNSELOR_B):
            assert ProviderAvailabilityWindow.objects.filter(provider=demo_user(persona)).exists()
        assert OfficeUnavailability.objects.count() == 1
        assert ProviderUnavailability.objects.filter(provider=demo_user(COUNSELOR_B)).count() == 1
        assert OfficeUnavailability.objects.get().starts_at > _anchor_time()

    def test_appointments_counseling_and_shared_summaries_cover_real_lifecycles(self):
        appointments = Appointment.objects.filter(student__in=_demo_user_ids())
        statuses = sorted(appointments.values_list("status", flat=True))
        assert statuses.count(AppointmentStatus.SCHEDULED) == 4
        assert statuses.count(AppointmentStatus.COMPLETED) == 2
        assert statuses.count(AppointmentStatus.CANCELLED) == 1
        assert statuses.count(AppointmentStatus.NO_SHOW) == 1
        assert appointments.filter(delivery_mode="ONLINE", status="SCHEDULED").count() == 1
        for item in appointments:
            assert item.created_at < item.starts_at
            if item.status == AppointmentStatus.SCHEDULED:
                assert item.starts_at > _anchor_time()
            else:
                assert item.starts_at < _anchor_time()
            if item.completed_at is not None:
                assert item.completed_at >= item.starts_at
            if item.no_show_at is not None:
                assert item.no_show_at >= item.ends_at
            if item.cancelled_at is not None:
                assert item.created_at <= item.cancelled_at < item.starts_at

        encounters = CounselingEncounter.objects.filter(student__in=_demo_user_ids())
        assert sorted(encounters.values_list("entry_mode", flat=True)) == [
            "APPOINTMENT",
            "APPOINTMENT",
            "REFERRED",
            "WALK_IN",
        ]
        for encounter in encounters.select_related("appointment"):
            assert encounter.ended_at <= encounter.created_at
            if encounter.appointment is not None:
                assert encounter.appointment.status == AppointmentStatus.COMPLETED
                assert encounter.appointment.provider_id == encounter.counselor_id
                assert encounter.appointment.starts_at <= encounter.started_at
                assert encounter.ended_at <= encounter.appointment.ends_at

        summaries = CounselingSharedSummary.objects.filter(encounter__in=encounters)
        assert summaries.filter(published_at__isnull=False).count() == 2
        assert summaries.filter(published_at__isnull=True).count() == 1
        for summary in summaries.filter(published_at__isnull=False).select_related("encounter"):
            assert summary.published_at > summary.encounter.ended_at

    def test_routine_interviews_cover_draft_submitted_and_finalized_states(self):
        routines = {
            item.student_id: item
            for item in RoutineInterview.objects.select_related(
                "appointment", "counseling_encounter", "inventory__academic_year"
            ).filter(student__in=_demo_user_ids())
        }
        assert len(routines) == 4
        draft = routines[demo_user(FIRST_YEAR).pk]
        assert draft.intake_submitted_at is None
        assert draft.appointment.delivery_mode == "ONLINE"
        pending = routines[demo_user(REFERRED).pk]
        assert pending.intake_submitted_at is not None
        assert pending.evaluation_finalized_at is None
        assert pending.entry_mode == "REFERRED"
        for persona in (SECOND_YEAR, FOURTH_YEAR):
            finalized = routines[demo_user(persona).pk]
            assert finalized.evaluation_finalized_at is not None
            assert finalized.counseling_encounter is not None
            assert finalized.intake_submitted_at <= finalized.evaluation_finalized_at
            assert finalized.counseling_encounter.ended_at <= finalized.evaluation_finalized_at
        appointment_backed = routines[demo_user(SECOND_YEAR).pk]
        assert appointment_backed.intake_submitted_at < appointment_backed.appointment.starts_at
        for item in routines.values():
            assert item.inventory.academic_year.label == "2026-2027"

    def test_referrals_and_call_slips_form_believable_workflows(self):
        referrals = Referral.objects.filter(student__in=_demo_user_ids()).prefetch_related(
            "actions"
        )
        assert referrals.count() == 4
        assert referrals.filter(voided_at__isnull=True).count() == 3
        voided = referrals.get(voided_at__isnull=False)
        assert "Duplicate entry" in voided.void_reason
        for referral in referrals.filter(voided_at__isnull=True):
            assert referral.received_at.date() >= referral.referred_on
            action = referral.actions.get(action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT")
            assert action.occurred_at >= referral.received_at
            slip = CallSlip.objects.get(referral=referral)
            assert slip.created_at >= action.occurred_at
            assert slip.created_at <= slip.report_at or slip.issuance_mode == "LIVE"
            if slip.interview_ended_at is not None:
                assert slip.report_at <= slip.interview_ended_at
            context = build_referral_render_context(referral)
            assert context

        slips = CallSlip.objects.filter(student__in=_demo_user_ids())
        states = sorted(item.lifecycle_state for item in slips)
        assert states == sorted(
            [
                CallSlipLifecycleState.ACTIVE,
                CallSlipLifecycleState.COMPLETED,
                CallSlipLifecycleState.COMPLETED,
                CallSlipLifecycleState.VOIDED,
            ]
        )
        active = next(
            item for item in slips if item.lifecycle_state == CallSlipLifecycleState.ACTIVE
        )
        assert active.issuance_mode == CallSlipIssuanceMode.LIVE
        assert active.report_at > _anchor_time()
        assert Notification.objects.filter(
            source_id=active.pk, event_code="call_slip.issued"
        ).exists()
        for item in slips.exclude(pk=active.pk):
            # Back-entered slips never pretend to be live issuance and never notified anyone.
            assert item.issuance_mode == CallSlipIssuanceMode.HISTORICAL
            assert not Notification.objects.filter(source_id=item.pk).exists()
            assert build_call_slip_render_context(item, access_mode="GCO")

    def test_good_moral_exit_interview_tracer_and_feedback(self):
        requests = GoodMoralRequest.objects.filter(student__in=_demo_user_ids())
        assert sorted(requests.values_list("status", flat=True)) == sorted(
            ["ISSUED", "ISSUED", "REQUESTED", "REQUESTED", "CANCELLED"]
        )
        for item in requests.filter(status=GoodMoralStatus.ISSUED):
            assert item.created_at < item.issued_at
            certificate = build_certificate_render_context(item)
            assert certificate["certificate"]["applicant_name"]
            assert certificate["controlled_form"]["official_code"]
        graduate = requests.get(variant=GoodMoralVariant.GRADUATE, status=GoodMoralStatus.ISSUED)
        assert graduate.student == demo_user(RECENT_GRADUATE)
        assert graduate.graduation_date < timezone.localtime(graduate.issued_at).date()
        current = requests.get(
            variant=GoodMoralVariant.CURRENT_STUDENT, status=GoodMoralStatus.ISSUED
        )
        assert current.academic_year.label == "2026-2027"
        assert (
            current.college_snapshot
            == StudentAffiliation.objects.get(student=current.student).college.name
        )
        assert current.college_snapshot.startswith("College of ")
        html, _ = render_document_html(
            current.document_template_key,
            current.document_template_version,
            context=build_certificate_render_context(current),
        )
        rendered_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
        assert current.college_snapshot in rendered_text
        assert "College of College of" not in rendered_text
        assert "Year year" not in rendered_text
        assert "Semester semester" not in rendered_text
        # A Student states the semester they file in; it follows each request's own date.
        for item in requests.filter(variant=GoodMoralVariant.CURRENT_STUDENT):
            filed_on = timezone.localtime(item.created_at).date()
            assert item.semester_snapshot == academic_semester(filed_on)

        exit_interview = ExitInterview.objects.get(student=demo_user(ALUMNI))
        assert exit_interview.self_assessment_ratings.count() == 15
        assert exit_interview.college_feedback_ratings.count() == 26

        assert CustomerFeedbackResponse.objects.count() == 4
        overall = sorted(
            CustomerFeedbackResponse.objects.values_list("overall_satisfaction_rating", flat=True)
        )
        assert len(set(overall)) > 1
        assert ClientSatisfactionResponse.objects.count() == 4
        reconciled = FeedbackOpportunity.objects.filter(
            customer_feedback_submitted_at__isnull=False,
            csm_submitted_at__isnull=False,
        )
        assert reconciled.count() == 4
        assert set(reconciled.values_list("student__email", flat=True)) == {
            demo_user(SECOND_YEAR).email,
            demo_user(GOOD_MORAL).email,
            demo_user(RECENT_GRADUATE).email,
            demo_user(REFERRED).email,
        }
        patterns = {
            tuple(getattr(item, f"sqd{index}") for index in range(9))
            for item in ClientSatisfactionResponse.objects.all()
        }
        assert (5,) * 9 not in patterns
        assert len(patterns) == 4

    def test_publications_and_privacy_governance(self):
        staff_ids = [demo_user(persona).pk for persona in STAFF]
        announcements = Announcement.objects.filter(created_by_id__in=staff_ids)
        assert sorted(announcements.values_list("status", flat=True)) == sorted(
            ["PUBLISHED", "PUBLISHED", "PUBLISHED", "PUBLISHED", "DRAFT", "ARCHIVED"]
        )
        assert set(announcements.values_list("audience", flat=True)) == {
            "STUDENTS",
            "ALL_AUTHENTICATED",
            "PUBLIC",
            "GCO_PERSONNEL",
        }
        for item in announcements.filter(status="PUBLISHED"):
            assert item.published_at < _anchor_time()
            assert item.expires_at is None or item.expires_at > _anchor_time()

        resources = Resource.objects.filter(created_by_id__in=staff_ids)
        assert sorted(resources.values_list("status", flat=True)) == sorted(
            ["PUBLISHED", "PUBLISHED", "PUBLISHED", "PUBLISHED", "DRAFT", "ARCHIVED"]
        )
        link = resources.get(kind="EXTERNAL_LINK")
        assert link.external_url.startswith("https://www.who.int/")
        assert not resources.exclude(storage_key="").exists()

        policies = RetentionPolicy.objects.filter(code__startswith="DEMO-RET-")
        assert policies.count() == 2
        assert all(policy.is_active for policy in policies)
        assert all("Staging demonstration" in policy.policy_reference for policy in policies)
        notice = PrivacyNotice.objects.get(code="DEMO-GCO-STUDENT-SERVICES")
        published = notice.revisions.get(status=PrivacyNoticeRevisionStatus.PUBLISHED)
        assert "staging demonstration" in published.title.lower()
        assert "not an official University privacy notice" in published.summary
        assert notice.revisions.filter(status=PrivacyNoticeRevisionStatus.DRAFT).count() == 1
        assert published.acknowledgments.filter(user=demo_user(SECOND_YEAR)).exists()

    def test_derived_projections_are_useful_without_being_seeded_directly(self):
        now = _anchor_time(6)
        first_year = build_overview_summary(demo_user(FIRST_YEAR), now=now).student
        assert first_year.upcoming_appointments_count == 1
        assert first_year.routine_intake_draft_count == 1
        assert build_overview_summary(
            demo_user(GRADUATING), now=now
        ).student.good_moral_requested_count
        assert (
            build_overview_summary(
                demo_user(ACTIVE_REFERRAL), now=now
            ).student.active_call_slip_count
            == 1
        )
        counselor_a = build_overview_summary(demo_user(COUNSELOR_A), now=now).guidance
        assert counselor_a.upcoming_self_appointments_count == 3
        counselor_b = build_overview_summary(demo_user(COUNSELOR_B), now=now).guidance
        assert counselor_b.routine_evaluation_pending_count == 1
        assert counselor_b.good_moral_requested_count == 2
        staff = build_overview_summary(demo_user(GUIDANCE_STAFF), now=now).guidance
        assert staff.active_call_slip_count == 1
        platform = build_overview_summary(demo_user(IT_ADMIN), now=now).platform
        assert platform is not None
        assert platform.email_failed_count == 0

        # Student Support is derived from each Student's submitted current Inventory.
        expectations = {
            FIRST_YEAR: (COUNSELOR_A, {"FOUR_PS_BENEFICIARY"}),
            FOURTH_YEAR: (COUNSELOR_A, {"PWD"}),
            REFERRED: (COUNSELOR_B, {"INDIGENOUS_PEOPLES_MEMBER"}),
            GOOD_MORAL: (COUNSELOR_B, {"FATHER_DECEASED"}),
            SECOND_YEAR: (COUNSELOR_A, set()),
        }
        for persona, (counselor, codes) in expectations.items():
            context = get_student_support_context(
                actor=demo_user(counselor), student_id=demo_user(persona).pk
            )
            assert context.available
            assert {indicator.code for indicator in context.indicators} == codes
        draft = get_student_support_context(
            actor=demo_user(COUNSELOR_A), student_id=demo_user(ACTIVE_REFERRAL).pk
        )
        assert draft.inventory_status == "DRAFT"

        head_scope = resolve_report_access_scope(demo_user(HEAD_GUIDANCE))
        current_report = build_student_profiling_report(access_scope=head_scope)
        assert current_report["report_context"]["submitted_inventory_count"] == 6
        coverage = current_report["inventory_coverage"]
        assert (
            coverage["submitted_count"],
            coverage["draft_count"],
            coverage["missing_count"],
        ) == (
            6,
            1,
            1,
        )
        historical = build_student_profiling_report(
            academic_year_id=AcademicYear.objects.get(label="2025-2026").pk,
            access_scope=head_scope,
        )
        assert historical["report_context"]["submitted_inventory_count"] == 8
        scoped = build_student_profiling_report(
            access_scope=resolve_report_access_scope(demo_user(COUNSELOR_A))
        )
        assert scoped["report_context"]["submitted_inventory_count"] == 3
        tracer_report = build_graduate_tracer_report(submitted_from=None, submitted_to=None)
        assert tracer_report["report_context"]["submitted_response_count"] == 1

        activity_types = {item.type for item in get_my_activity(demo_user(SECOND_YEAR)).items}
        assert {"account.created", "profile.updated"} <= activity_types
        head_activity = {item.type for item in get_my_activity(demo_user(HEAD_GUIDANCE)).items}
        assert "account.designation.assigned" in head_activity
        privacy_types = {item.type for item in list_privacy_activity(page_size=50).items}
        assert {
            "account.designation.assigned",
            "account.disabled",
            "privacy.notice.revision.published",
        } <= privacy_types

        second_year_notifications = Notification.objects.filter(recipient=demo_user(SECOND_YEAR))
        assert second_year_notifications.filter(read_at__isnull=False).count() == 2
        assert second_year_notifications.filter(read_at__isnull=True).exists()
        assert not Notification.objects.filter(event_code__startswith="security.").exists()
        for notification in Notification.objects.all():
            assert notification.created_at < timezone.now()

    def test_seeded_records_are_readable_through_the_normal_api(self):
        def client_for(persona) -> Client:
            client = Client()
            issued = create_auth_session(demo_user(persona), now=timezone.now())
            client.cookies["compass_session"] = issued.token
            return client

        adjustment = RoutineInterview.objects.get(student=demo_user(SECOND_YEAR))
        response = client_for(COUNSELOR_A).get(f"/api/v1/routine-interviews/{adjustment.pk}")
        assert response.status_code == 200
        assert response.json()["intake"] == ADJUSTMENT_INTAKE
        assert response.json()["evaluation"] == ADJUSTMENT_EVALUATION

        history = client_for(SECOND_YEAR).get("/api/v1/inventory/me/history")
        assert history.status_code == 200
        assert len(history.json()["items"]) == 2

        online = Appointment.objects.get(student=demo_user(FIRST_YEAR), delivery_mode="ONLINE")
        workspace = client_for(FIRST_YEAR).get(f"/api/v1/e-counseling/me/appointments/{online.pk}")
        assert workspace.status_code == 200
        assert workspace.json()["routine_interview"]["intake_status"] == "DRAFT"

        assert client_for(HEAD_GUIDANCE).get("/api/v1/reports/student-profile").status_code == 200
        assert client_for(HEAD_GUIDANCE).get("/api/v1/reports/graduate-tracer").status_code == 200
        assert client_for(HEAD_GUIDANCE).get("/api/v1/graduate-tracer/responses").status_code == 200
        submitted_exit = ExitInterview.objects.get(student=demo_user(RECENT_GRADUATE))
        assert (
            client_for(HEAD_GUIDANCE)
            .get(f"/api/v1/exit-interviews/{submitted_exit.pk}")
            .status_code
            == 200
        )
        active_slip = CallSlip.objects.get(student=demo_user(ACTIVE_REFERRAL))
        assert (
            client_for(GUIDANCE_STAFF).get(f"/api/v1/call-slips/{active_slip.pk}").status_code
            == 200
        )
        assert client_for(ACTIVE_REFERRAL).get("/api/v1/call-slips/me").status_code == 200
        referral = Referral.objects.get(student=demo_user(REFERRED), voided_at__isnull=True)
        assert client_for(COUNSELOR_B).get(f"/api/v1/referrals/{referral.pk}").status_code == 200
        assert client_for(GOOD_MORAL).get("/api/v1/good-moral/me").status_code == 200
        notifications = client_for(SECOND_YEAR).get("/api/v1/notifications")
        assert notifications.status_code == 200
        support = client_for(COUNSELOR_A).get(
            f"/api/v1/student-support/students/{demo_user(FIRST_YEAR).pk}/context"
        )
        assert support.status_code == 200

    def test_routine_content_is_written_through_the_encrypted_boundary(self):
        sentences = [
            ADJUSTMENT_INTAKE["concerns_explanation"],
            ADJUSTMENT_EVALUATION["recommendations"],
            WALK_IN_INTAKE["concerns_explanation"],
            WALK_IN_EVALUATION["recommendations"],
            REFERRED_INTAKE["family_description"],
        ]
        for persona, intake, evaluation in (
            (SECOND_YEAR, ADJUSTMENT_INTAKE, ADJUSTMENT_EVALUATION),
            (FOURTH_YEAR, WALK_IN_INTAKE, WALK_IN_EVALUATION),
        ):
            item = RoutineInterview.objects.get(student=demo_user(persona))
            assert read_intake(item) == intake
            assert read_evaluation(item) == evaluation

        for item in RoutineInterview.objects.filter(student__in=_demo_user_ids()):
            row = _raw_routine_row(item.pk)
            assert set(row).isdisjoint({*INTAKE_FIELDS, *EVALUATION_FIELDS})
            stored = json.dumps(row, default=str)
            for sentence in sentences:
                assert sentence not in stored
            for column in CIPHERTEXT_COLUMNS.values():
                assert row[column].startswith("gAAAAA")

    def test_audit_trail_is_legitimate_attributable_and_secret_free(self):
        events = AuditEvent.objects.all()
        run_ids = {str(value) for value in events.values_list("request_id", flat=True)}
        assert run_ids == {self.report.run_id}
        actions = set(events.values_list("action", flat=True))
        assert {
            "account.created",
            "account.designation.assigned",
            "account.student_lifecycle.changed",
            "account.disabled",
            "academic_year.created",
            "academic_year.current_changed",
            "inventory.submitted",
            "appointment.created",
            "counseling.encounter.created",
            "routine_interview.evaluation_finalized",
            "referral.created",
            "call_slip.created",
            "good_moral.issued",
            "privacy.notice.revision.published",
        } <= actions
        serialized = json.dumps(list(events.values_list("metadata", flat=True)))
        for forbidden in (
            DEMO_PASSWORD,
            ADJUSTMENT_INTAKE["concerns_explanation"],
            ADJUSTMENT_EVALUATION["recommendations"],
            "otp",
            "totp",
        ):
            assert forbidden not in serialized
        # On a clean database the Academic Year audit reads as a normal forward progression.
        changes = [
            (event.metadata["old_label"], event.metadata["new_label"])
            for event in events.filter(action="academic_year.current_changed").order_by(
                "occurred_at"
            )
        ]
        assert changes == [
            (None, "2024-2025"),
            ("2024-2025", "2025-2026"),
            ("2025-2026", "2026-2027"),
        ]


# --- Idempotency and conflicts ---------------------------------------------------------------


def _snapshot() -> dict[str, object]:
    demo_ids = _demo_user_ids()
    return {
        "users": User.objects.count(),
        "affiliations": StudentAffiliation.objects.count(),
        "responsibilities": CounselorResponsibility.objects.count(),
        "supervision": StaffSupervision.objects.count(),
        "years": AcademicYear.objects.count(),
        "inventories": StudentInventory.objects.count(),
        "appointments": Appointment.objects.count(),
        "encounters": CounselingEncounter.objects.count(),
        "summaries": CounselingSharedSummary.objects.count(),
        "routines": RoutineInterview.objects.count(),
        "referrals": Referral.objects.count(),
        "actions": ReferralAction.objects.count(),
        "call_slips": CallSlip.objects.count(),
        "good_moral": GoodMoralRequest.objects.count(),
        "exit_interviews": ExitInterview.objects.count(),
        "tracer": GraduateTracerResponse.objects.count(),
        "feedback": CustomerFeedbackResponse.objects.count(),
        "csm": ClientSatisfactionResponse.objects.count(),
        "feedback_opportunities": FeedbackOpportunity.objects.count(),
        "announcements": Announcement.objects.count(),
        "resources": Resource.objects.count(),
        "notices": PrivacyNotice.objects.count(),
        "policies": RetentionPolicy.objects.count(),
        "notifications": Notification.objects.count(),
        "office_windows": OfficeAvailabilityWindow.objects.count(),
        "provider_windows": ProviderAvailabilityWindow.objects.count(),
        "exceptions": OfficeUnavailability.objects.count() + ProviderUnavailability.objects.count(),
        "audit": AuditEvent.objects.count(),
        "passwords": dict(User.objects.filter(pk__in=demo_ids).values_list("pk", "password")),
        "states": sorted(
            User.objects.filter(pk__in=demo_ids).values_list(
                "institutional_id", "is_active", "student_lifecycle_status", "email_verified_at"
            )
        ),
    }


@pytest.mark.django_db
def test_ordinary_rerun_is_idempotent_and_preserves_established_credentials(seeded):
    changed = demo_user(SECOND_YEAR)
    changed.set_password("a password the student chose later")
    changed.save(update_fields=["password"])
    before = _snapshot()

    report = seed_demo_staging()

    assert _snapshot() == before
    assert sum(report.created.values()) == 0
    assert report.existing["Accounts"] == len(CAST)
    assert report.existing["Scenarios"] == 9
    assert demo_user(SECOND_YEAR).check_password("a password the student chose later")
    assert not demo_user(FORMER_STAFF).is_active


@pytest.mark.django_db
def test_feedback_opportunities_reconcile_known_demo_sources_without_recreating_raw_responses(
    seeded,
):
    raw_customer_ids = set(CustomerFeedbackResponse.objects.values_list("pk", flat=True))
    raw_csm_ids = set(ClientSatisfactionResponse.objects.values_list("pk", flat=True))

    FeedbackOpportunity.objects.all().delete()
    Notification.objects.filter(source_type="feedback_opportunity").delete()

    report = seed_demo_staging()

    assert set(CustomerFeedbackResponse.objects.values_list("pk", flat=True)) == raw_customer_ids
    assert set(ClientSatisfactionResponse.objects.values_list("pk", flat=True)) == raw_csm_ids
    reconciled = FeedbackOpportunity.objects.filter(
        customer_feedback_submitted_at__isnull=False,
        csm_submitted_at__isnull=False,
    )
    assert reconciled.count() == 4
    assert report.existing["Customer Feedback"] == 4
    assert report.existing["CSM responses"] == 4


@pytest.mark.django_db
def test_changing_the_demo_domain_between_runs_fails_closed(seeded, monkeypatch):
    before = _snapshot()
    monkeypatch.setenv("DEMO_EMAIL_DOMAIN", "another-demo.test")
    with pytest.raises(CommandError, match="Keep DEMO_EMAIL_DOMAIN and DEMO_ONBOARDING_EMAIL"):
        call_command(COMMAND, stdout=StringIO())
    assert _snapshot() == before


@pytest.mark.django_db
def test_a_second_concurrent_run_is_refused(demo_env):
    settings_dict = connection.settings_dict
    other = psycopg.connect(
        dbname=settings_dict["NAME"],
        user=settings_dict["USER"],
        password=settings_dict["PASSWORD"],
        host=settings_dict["HOST"],
        port=settings_dict["PORT"],
        autocommit=True,
    )
    try:
        other.execute("SELECT pg_advisory_lock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])
        with pytest.raises(CommandError, match="Another seed_demo_staging run is in progress"):
            call_command(COMMAND, stdout=StringIO())
    finally:
        other.close()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_existing_real_routing_is_never_reassigned(demo_env):
    call_command("sync_identity_policy", stdout=StringIO())
    call_command("sync_organization_catalog", stdout=StringIO())
    real_counselor = User.objects.create_user(
        email="real.counselor@example.edu",
        role="COUNSELOR",
        first_name="Real",
        last_name="Counselor",
    )
    from compass.audit.context import AuditContext
    from compass.organization.models import College

    college = College.objects.get(campus__code="MAIN", code="CCMS")
    set_counselor_responsibility(
        college_id=college.pk, counselor_id=real_counselor.pk, context=AuditContext.system()
    )

    with pytest.raises(CommandError, match="already has a different Counselor responsibility"):
        call_command(COMMAND, stdout=StringIO())
    assert not User.objects.filter(email__endswith="@compass-demo.test").exists()
    assert CounselorResponsibility.objects.get(college=college).counselor == real_counselor


@pytest.mark.django_db
def test_demo_identity_collisions_and_foreign_academic_years_fail_closed(demo_env):
    call_command("sync_identity_policy", stdout=StringIO())
    User.objects.create_user(
        email="demo-head@compass-demo.test",
        role="STUDENT",
        first_name="Someone",
        last_name="Else",
        institutional_id="DEMO-2026-0002",
    )
    with pytest.raises(CommandError, match="requires COUNSELOR"):
        call_command(COMMAND, stdout=StringIO())
    User.objects.filter(email="demo-head@compass-demo.test").delete()

    from compass.audit.context import AuditContext
    from compass.organization.academic_years import (
        create_academic_year,
        set_current_academic_year,
    )

    year = create_academic_year(label="2030-2031", context=AuditContext.system())
    set_current_academic_year(academic_year_id=year.pk, context=AuditContext.system())
    with pytest.raises(CommandError, match="current Academic Year is 2030-2031"):
        call_command(COMMAND, stdout=StringIO())
    assert not User.objects.filter(email__endswith="@compass-demo.test").exists()


def test_timeline_anchor_window_is_enforced():
    resolve_timeline(anchor=date(2026, 9, 21))
    resolve_timeline(anchor=date(2027, 4, 30))
    with pytest.raises(DemoTimelineError, match="2026-2027"):
        resolve_timeline(anchor=date(2026, 9, 1))
    with pytest.raises(DemoTimelineError, match="2026-2027"):
        resolve_timeline(anchor=date(2027, 6, 1))


def test_timeline_places_activity_on_business_days_only():
    timeline = resolve_timeline(anchor=ANCHOR)
    for offset in (*range(-20, 0), *range(1, 12)):
        day = timeline.business_day(offset)
        assert day.weekday() < 5
        assert (day < ANCHOR) is (offset < 0)
    assert timeline.business_day(-1) == ANCHOR - timedelta(days=3)


def test_semester_follows_the_dataset_academic_calendar():
    assert academic_semester(date(2026, 8, 3)) == "First"
    assert academic_semester(date(2026, 12, 18)) == "First"
    assert academic_semester(date(2027, 1, 4)) == "Second"
    assert academic_semester(date(2027, 5, 31)) == "Second"
    with pytest.raises(ValueError, match="midyear"):
        academic_semester(date(2027, 6, 15))
