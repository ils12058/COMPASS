"""Orchestration for ``seed_demo_staging``: guard, preflight, bounded units, and the report."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from django.db import DatabaseError, connection, transaction

from compass.accounts.bootstrap import IdentityPolicySyncError, sync_identity_policy
from compass.accounts.models import Designation, Role, User
from compass.announcements.models import Announcement
from compass.appointments.models import Appointment
from compass.call_slips.models import CallSlip
from compass.common.correlation import reset_current_request_id, set_current_request_id
from compass.counseling.models import CounselingEncounter, CounselingSharedSummary
from compass.exit_interviews.models import ExitInterview
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.good_moral.models import GoodMoralRequest
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.institutional_forms.bootstrap import CanonicalFormSyncError, sync_institutional_forms
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.academic_years import get_current_academic_year
from compass.organization.bootstrap import (
    CanonicalOrganizationSyncError,
    sync_organization_catalog,
)
from compass.organization.models import AcademicYear
from compass.privacy_governance.models import PrivacyNotice
from compass.referrals.models import Referral
from compass.resources.models import Resource
from compass.routine_interviews.crypto import (
    RoutineContentSection,
    decrypt_section,
    encrypt_section,
)
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.bootstrap import (
    CanonicalIdentityPolicyMissing,
    canonical_counseling_readiness,
    sync_canonical_services,
)
from compass.service_catalog.services import ServiceCatalogError

from . import DEMO_DATASET_VERSION, publication_data
from .accounts import (
    disable_account,
    plan_accounts,
    provision_accounts,
    validate_demo_password,
)
from .cast import CAST, FORMER_STAFF, PERSONAS_BY_KEY, STAFF, STUDENTS, AuthState, Persona
from .config import DemoConfig, DemoConfigurationError, load_demo_config
from .configuration import (
    check_organization_conflicts,
    college_for,
    ensure_counseling_configuration,
    ensure_organization,
    offboard_former_staff,
    program_for,
)
from .guard import ensure_demo_seeding_allowed_by_settings
from .history import check_history_preconditions, run_academic_timeline, seed_profiles
from .narratives import CLIENT_SATISFACTION, CUSTOMER_FEEDBACK
from .publications import seed_feedback, seed_privacy_governance, seed_publications
from .scenarios import SCENARIOS, run_scenario
from .support import DemoSeedError, SeedSession
from .timeline import DATASET_ACADEMIC_YEARS, resolve_timeline

# Session-level PostgreSQL advisory lock key reserved for demo seeding.
SEED_RUN_ADVISORY_LOCK_KEY = 2_026_092_801
REQUIRED_FORM_FAMILIES = (
    "individual_inventory",
    "referral_slip",
    "call_slip",
    "good_moral_current_student",
    "good_moral_graduate",
    "customer_feedback",
)


@dataclass(frozen=True)
class AccountLine:
    label: str
    email: str
    role: str
    designations: tuple[str, ...]
    lifecycle: str | None
    active: bool
    auth: str


@dataclass(frozen=True)
class SeedReport:
    app_env: str
    dataset_version: int
    anchor: date
    timezone_name: str
    run_id: str
    accounts: tuple[AccountLine, ...]
    records: tuple[tuple[str, str], ...]
    created: dict[str, int]
    existing: dict[str, int]
    notes: tuple[str, ...] = field(default_factory=tuple)


def _safe_failure(unit: str, exc: Exception) -> DemoSeedError:
    """Name the failed unit without echoing database values or form content."""

    if isinstance(exc, DatabaseError):
        return DemoSeedError(f"{unit} failed: database error ({exc.__class__.__name__}).")
    return DemoSeedError(f"{unit} failed: {exc.__class__.__name__}: {exc}")


def _unit(unit: str, operation: Callable[[], object]) -> object:
    try:
        return operation()
    except DemoConfigurationError:
        raise
    except DemoSeedError as exc:
        raise type(exc)(f"{unit}: {exc}") from exc
    except Exception as exc:
        raise _safe_failure(unit, exc) from exc


@contextmanager
def _exclusive_seed_run():
    """Refuse a second concurrent seed run instead of racing it on shared staging data."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])
        (acquired,) = cursor.fetchone()
    if not acquired:
        raise DemoSeedError("Another seed_demo_staging run is in progress; try again later.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])


def sync_prerequisites() -> None:
    """Reuse the source-owned synchronizers; the seeder never restates canonical definitions."""

    try:
        sync_identity_policy()
        sync_organization_catalog()
        sync_institutional_forms()
        sync_canonical_services()
    except (
        IdentityPolicySyncError,
        CanonicalOrganizationSyncError,
        CanonicalFormSyncError,
        CanonicalIdentityPolicyMissing,
        ServiceCatalogError,
    ) as exc:
        raise DemoSeedError(f"Canonical synchronization failed: {exc}") from exc


def verify_prerequisites() -> None:
    required_roles = {persona.role for persona in CAST}
    if Role.objects.filter(code__in=required_roles).count() != len(required_roles):
        raise DemoSeedError("Required canonical roles are not synchronized.")
    required_designations = {code for persona in CAST for code in persona.designations}
    if Designation.objects.filter(code__in=required_designations).count() != len(
        required_designations
    ):
        raise DemoSeedError("Required canonical designations are not synchronized.")
    for persona in STUDENTS:
        college_for(persona.campus_code, persona.college_code)
        program_for(persona)
    for family_key in REQUIRED_FORM_FAMILIES:
        try:
            require_active_supported_form_revision(family_key)
        except InstitutionalFormConflict as exc:
            raise DemoSeedError(f"Institutional form {family_key} is not ready: {exc}") from exc
    ready, reason = canonical_counseling_readiness()
    if not ready:
        raise DemoSeedError(f"The canonical Counseling Service is not ready ({reason}).")
    # Prove the Routine Interview keyring can encrypt and decrypt before any content is written.
    probe = uuid.uuid4()
    token = encrypt_section(
        routine_interview_id=probe,
        section=RoutineContentSection.STUDENT_INTAKE,
        payload={"probe": True},
    )
    decrypt_section(token, routine_interview_id=probe, section=RoutineContentSection.STUDENT_INTAKE)


def finalize_account_state(session: SeedSession) -> None:
    """Close out the departed staff member after their historical records exist."""

    with transaction.atomic():
        if not FORMER_STAFF.active:
            offboard_former_staff(session)
            disabled = disable_account(session, FORMER_STAFF)
            session.record("Disabled accounts", created=disabled)


def _run(session: SeedSession, config: DemoConfig) -> None:
    _unit("Canonical synchronization", sync_prerequisites)
    _unit("Prerequisite verification", verify_prerequisites)

    plans = _unit("Account preflight", lambda: plan_accounts(config))
    session.users.update({plan.persona.key: plan.existing for plan in plans if plan.existing})
    _unit("Organization preflight", lambda: check_organization_conflicts(dict(session.users)))
    _unit("Academic Year preflight", lambda: check_history_preconditions(session))

    created_keys = {plan.persona.key for plan in plans if plan.existing is None}

    def accounts() -> None:
        with transaction.atomic():
            provision_accounts(session, plans, config)
            seed_profiles(session, created_keys=created_keys)

    _unit("Accounts", accounts)

    def organization() -> None:
        with transaction.atomic():
            ensure_organization(session)

    _unit("Organization relationships", organization)

    def counseling() -> None:
        with transaction.atomic():
            ensure_counseling_configuration(session)

    _unit("Counseling configuration and Availability", counseling)
    _unit("Academic timeline", lambda: run_academic_timeline(session))
    for scenario in SCENARIOS:
        _unit(scenario.key, lambda scenario=scenario: run_scenario(session, scenario))
    _unit("Announcements and Resources", lambda: seed_publications(session))
    _unit("Privacy Governance", lambda: seed_privacy_governance(session))
    _unit("Customer Feedback and CSM", lambda: seed_feedback(session))
    _unit("Account state", lambda: finalize_account_state(session))


def _auth_label(persona: Persona, user: User) -> str:
    if not user.is_active:
        return "disabled"
    if persona.auth_state == AuthState.ONBOARDING:
        if user.has_usable_password():
            return "onboarding completed"
        return "onboarding (no password yet)"
    return "ready"


def _account_lines(session: SeedSession) -> tuple[AccountLine, ...]:
    lines = []
    for persona in (*STAFF, *STUDENTS):
        user = (
            User.objects.select_related("role")
            .prefetch_related("designations")
            .get(pk=session.users[persona.key].pk)
        )
        lines.append(
            AccountLine(
                label=persona.label,
                email=user.email,
                role=user.role.code,
                designations=tuple(sorted(item.code for item in user.designations.all())),
                lifecycle=user.student_lifecycle_status,
                active=user.is_active,
                auth=_auth_label(persona, user),
            )
        )
    return tuple(lines)


def _status_breakdown(queryset, field_name: str) -> str:
    counts: dict[str, int] = {}
    for value in queryset.values_list(field_name, flat=True):
        counts[str(value)] = counts.get(str(value), 0) + 1
    return ", ".join(f"{count} {status.lower()}" for status, count in sorted(counts.items()))


def _records(session: SeedSession) -> tuple[tuple[str, str], ...]:
    students = [session.users[persona.key].pk for persona in STUDENTS]
    staff = [session.users[persona.key].pk for persona in STAFF]
    current = get_current_academic_year()
    appointments = Appointment.objects.filter(student_id__in=students)
    summaries = CounselingSharedSummary.objects.filter(encounter__student_id__in=students)
    routines = RoutineInterview.objects.filter(student_id__in=students)
    call_slips = CallSlip.objects.filter(student_id__in=students)
    notifications = Notification.objects.filter(recipient_id__in=[*students, *staff])
    return (
        (
            "Academic Years",
            f"{AcademicYear.objects.filter(label__in=DATASET_ACADEMIC_YEARS).count()} "
            f"(current {current.label if current else 'none'})",
        ),
        (
            "Inventories",
            _count_with_breakdown(
                StudentInventory.objects.filter(student_id__in=students),
                submitted="submitted_at__isnull",
            ),
        ),
        (
            "Appointments",
            f"{appointments.count()} ({_status_breakdown(appointments, 'status')})",
        ),
        (
            "Counseling Encounters",
            str(CounselingEncounter.objects.filter(student_id__in=students).count()),
        ),
        (
            "Shared Summaries",
            f"{summaries.count()} ({summaries.filter(published_at__isnull=False).count()} "
            "published)",
        ),
        (
            "Routine Interviews",
            f"{routines.count()} ({routines.filter(intake_submitted_at__isnull=True).count()} "
            f"intake draft, {routines.filter(evaluation_finalized_at__isnull=False).count()} "
            "finalized)",
        ),
        ("Referrals", str(Referral.objects.filter(student_id__in=students).count())),
        (
            "Call Slips",
            f"{call_slips.count()} ({call_slips.filter(voided_at__isnull=False).count()} voided, "
            f"{call_slips.filter(interview_ended_at__isnull=False).count()} completed)",
        ),
        (
            "Good Moral Requests",
            _status_breakdown_with_total(
                GoodMoralRequest.objects.filter(student_id__in=students), "status"
            ),
        ),
        (
            "Exit Interviews",
            _status_breakdown_with_total(
                ExitInterview.objects.filter(student_id__in=students), "status"
            ),
        ),
        (
            "Graduate Tracer",
            _status_breakdown_with_total(
                GraduateTracerResponse.objects.filter(student_id__in=students), "status"
            ),
        ),
        ("Customer Feedback", str(_seeded_customer_feedback())),
        ("CSM responses", str(_seeded_csm())),
        (
            "Announcements",
            _status_breakdown_with_total(
                Announcement.objects.filter(created_by_id__in=staff), "status"
            ),
        ),
        (
            "Resources",
            _status_breakdown_with_total(
                Resource.objects.filter(created_by_id__in=staff), "status"
            ),
        ),
        (
            "Privacy Notices",
            str(PrivacyNotice.objects.filter(code=publication_data.PRIVACY_NOTICE["code"]).count()),
        ),
        (
            "Notifications",
            f"{notifications.count()} ({notifications.filter(read_at__isnull=True).count()} "
            "unread)",
        ),
        (
            "Pending demo emails",
            str(
                EmailDelivery.objects.filter(
                    notification__recipient_id__in=[*students, *staff], status="PENDING"
                ).count()
            ),
        ),
    )


def _count_with_breakdown(queryset, *, submitted: str) -> str:
    total = queryset.count()
    drafts = queryset.filter(**{submitted: True}).count()
    return f"{total} ({total - drafts} submitted, {drafts} draft)"


def _status_breakdown_with_total(queryset, field_name: str) -> str:
    return f"{queryset.count()} ({_status_breakdown(queryset, field_name)})"


def _seeded_customer_feedback() -> int:
    return sum(
        CustomerFeedbackResponse.objects.filter(
            respondent_name_snapshot=PERSONAS_BY_KEY[key].full_name,
            additional_feedback=values["additional_feedback"],
        ).count()
        for key, values in CUSTOMER_FEEDBACK.items()
    )


def _seeded_csm() -> int:
    return sum(
        ClientSatisfactionResponse.objects.filter(
            service_availed=item["service_availed"], suggestions=item["suggestions"]
        ).count()
        for item in CLIENT_SATISFACTION
    )


def seed_demo_staging(*, anchor: date | None = None) -> SeedReport:
    """Seed or reconcile the staging demo dataset and return a secret-free report."""

    app_env = ensure_demo_seeding_allowed_by_settings()
    config = load_demo_config(app_env=app_env)
    validate_demo_password(config)
    timeline = resolve_timeline(anchor=anchor)
    session = SeedSession(timeline=timeline, app_env=app_env)
    # One correlation ID for the whole run: every audit event the run causes carries it.
    token = set_current_request_id(session.run_id)
    try:
        with _exclusive_seed_run():
            _run(session, config)
        return SeedReport(
            app_env=app_env,
            dataset_version=DEMO_DATASET_VERSION,
            anchor=timeline.anchor,
            timezone_name=str(timeline.zone),
            run_id=session.run_id,
            accounts=_account_lines(session),
            records=_records(session),
            created=dict(session.created),
            existing=dict(session.existing),
            notes=tuple(session.notes),
        )
    finally:
        reset_current_request_id(token)


__all__ = ["AccountLine", "SeedReport", "seed_demo_staging"]
