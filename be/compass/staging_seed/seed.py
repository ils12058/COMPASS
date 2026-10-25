"""Orchestration for ``seed_staging_dataset seed``: guard, preflight, bounded units, report.

A normal run creates what is missing and reuses what exists. It never deletes, truncates or
resets data, never sets or changes a credential, and never restores a state an evaluator already
changed: every unit is skipped as a whole once its marker record exists. Conflicting identities or
routing stop the run before business records are written. A pristine dataset is a separately
authorized database rebuild, never a seeder option.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from django.db import DatabaseError, connection, transaction

from compass.accounts.bootstrap import IdentityPolicySyncError, sync_identity_policy
from compass.accounts.models import Designation, Role, User
from compass.common.correlation import reset_current_request_id, set_current_request_id
from compass.institutional_forms.bootstrap import CanonicalFormSyncError, sync_institutional_forms
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.organization.bootstrap import (
    CatalogInitializationError,
    check_organization_catalog,
)
from compass.service_catalog.bootstrap import (
    CanonicalIdentityPolicyMissing,
    canonical_counseling_readiness,
    sync_canonical_services,
)
from compass.service_catalog.services import ServiceCatalogError

from . import DATASET_NAME, DATASET_VERSION
from .accounts import disable_account, plan_accounts, provision_accounts
from .config import StagingSeedConfig, StagingSeedConfigurationError, load_config
from .content import feedback_population
from .encryption import verify_encryption_keyrings
from .guard import ensure_seeding_allowed_by_settings
from .history import check_history_preconditions, run_academic_timeline, seed_profiles
from .identities import AuthPlan
from .manifest import ACCOUNTS
from .organization import (
    check_organization_conflicts,
    college_for,
    ensure_counseling_configuration,
    ensure_organization,
    offboard_former_staff,
    program_for,
)
from .publications import seed_feedback, seed_privacy_governance, seed_publications
from .scenarios.action_ready import ACTION_UNITS, run_action_unit
from .scenarios.background import seed_population_forms, seed_secondary_stories
from .scenarios.rich import RICH_STORIES, run_story
from .staff import FORMER_STAFF
from .students import STUDENTS
from .support import SeedSession, StagingSeedConflict, StagingSeedError
from .timeline import resolve_timeline

# Session-level PostgreSQL advisory lock reserved for every Staging Dataset v1 write mode.
SEED_RUN_ADVISORY_LOCK_KEY = 2_026_101_601
# Identifiers of the retired Demo Dataset v1/v2 lineage. Dataset v1 never adopts or upgrades it.
RETIRED_DEMO_IDENTIFIER_PREFIX = "DEMO-2026-"
REQUIRED_FORM_FAMILIES = (
    "individual_inventory",
    "referral_slip",
    "call_slip",
    "good_moral_current_student",
    "good_moral_graduate",
    "customer_feedback",
    "routine_interview",
    "exit_interview",
)


@dataclass(frozen=True)
class SeedReport:
    app_env: str
    dataset_name: str
    dataset_version: int
    anchor: date
    timezone_name: str
    run_id: str
    account_count: int
    student_count: int
    created: dict[str, int]
    existing: dict[str, int]
    notes: tuple[str, ...] = field(default_factory=tuple)


def _safe_failure(unit: str, exc: Exception) -> StagingSeedError:
    """Name the failed unit without echoing database values or form content."""

    if isinstance(exc, DatabaseError):
        return StagingSeedError(f"{unit} failed: database error ({exc.__class__.__name__}).")
    return StagingSeedError(f"{unit} failed: {exc.__class__.__name__}: {exc}")


def _unit(unit: str, operation: Callable[[], object]) -> object:
    try:
        return operation()
    except StagingSeedConfigurationError:
        raise
    except StagingSeedError as exc:
        raise type(exc)(f"{unit}: {exc}") from exc
    except Exception as exc:
        raise _safe_failure(unit, exc) from exc


@contextmanager
def exclusive_dataset_operation():
    """Refuse a second concurrent write run instead of racing it on shared staging data."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])
        (acquired,) = cursor.fetchone()
    if not acquired:
        raise StagingSeedError(
            "Another seed_staging_dataset write operation is in progress; try again later."
        )
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [SEED_RUN_ADVISORY_LOCK_KEY])


def sync_prerequisites() -> None:
    """Verify adopted catalog; sync only unrelated source-owned configuration."""

    try:
        check_organization_catalog()
        sync_identity_policy()
        sync_institutional_forms()
        sync_canonical_services()
    except (
        IdentityPolicySyncError,
        CatalogInitializationError,
        CanonicalFormSyncError,
        CanonicalIdentityPolicyMissing,
        ServiceCatalogError,
    ) as exc:
        raise StagingSeedError(f"Canonical synchronization failed: {exc}") from exc


def refuse_retired_lineage() -> None:
    if User.objects.filter(institutional_id__startswith=RETIRED_DEMO_IDENTIFIER_PREFIX).exists():
        raise StagingSeedConflict(
            "This database contains retired Demo Dataset (DEMO-2026-…) accounts. Staging Dataset "
            "v1 is a new lineage for a clean canonical database and never upgrades the old one."
        )


def verify_prerequisites() -> None:
    required_roles = {account.role for account in ACCOUNTS}
    if Role.objects.filter(code__in=required_roles).count() != len(required_roles):
        raise StagingSeedError("Required canonical roles are not synchronized.")
    required_designations = {code for account in ACCOUNTS for code in account.designations}
    if Designation.objects.filter(code__in=required_designations).count() != len(
        required_designations
    ):
        raise StagingSeedError("Required canonical designations are not synchronized.")
    for student in STUDENTS:
        college_for(student.campus_code, student.college_code)
        program_for(student)
    for family_key in REQUIRED_FORM_FAMILIES:
        try:
            require_active_supported_form_revision(family_key)
        except InstitutionalFormConflict as exc:
            raise StagingSeedError(f"Institutional form {family_key} is not ready: {exc}") from exc
    ready, reason = canonical_counseling_readiness()
    if not ready:
        raise StagingSeedError(f"The canonical Counseling Service is not ready ({reason}).")


def finalize_account_state(session: SeedSession) -> None:
    """Disable the accounts the manifest declares disabled, after their history exists."""

    with transaction.atomic():
        for account in ACCOUNTS:
            if account.auth != AuthPlan.DISABLED:
                continue
            if account.key == FORMER_STAFF.key:
                offboard_former_staff(session)
            disabled = disable_account(session, account)
            session.record("Disabled accounts", created=disabled)


def _run(session: SeedSession, config: StagingSeedConfig) -> None:
    _unit("Encryption preflight", verify_encryption_keyrings)
    _unit("Retired lineage preflight", refuse_retired_lineage)
    _unit("Canonical synchronization", sync_prerequisites)
    _unit("Prerequisite verification", verify_prerequisites)

    plans = _unit("Account preflight", lambda: plan_accounts(config))
    session.users.update({plan.persona.key: plan.existing for plan in plans if plan.existing})
    _unit("Organization preflight", lambda: check_organization_conflicts(dict(session.users)))
    _unit("Academic Year preflight", lambda: check_history_preconditions(session))

    created_keys = {plan.persona.key for plan in plans if plan.existing is None}

    def accounts() -> None:
        with transaction.atomic():
            provision_accounts(session, plans)
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
    for story in RICH_STORIES:
        _unit(story.key, lambda story=story: run_story(session, story))
    _unit("Population forms and history", lambda: seed_population_forms(session))
    for unit in ACTION_UNITS:
        _unit(f"Action-ready {unit.key}", lambda unit=unit: run_action_unit(session, unit))
    _unit("Background stories", lambda: seed_secondary_stories(session))
    _unit("Announcements and Resources", lambda: seed_publications(session))
    _unit("Privacy Governance", lambda: seed_privacy_governance(session))
    _unit("Customer Feedback and CSM", lambda: seed_feedback(session))
    _unit(
        "Population Feedback and CSM",
        lambda: feedback_population.seed_population_feedback(session),
    )
    _unit("Account state", lambda: finalize_account_state(session))


def seed_staging_dataset(*, anchor: date | None = None) -> SeedReport:
    """Seed or reconcile Staging Dataset v1 and return a secret-free report."""

    app_env = ensure_seeding_allowed_by_settings()
    config = load_config(app_env=app_env)
    timeline = resolve_timeline(anchor=anchor)
    session = SeedSession(timeline=timeline, app_env=app_env)
    # One correlation ID for the whole run: every audit event the run causes carries it.
    token = set_current_request_id(session.run_id)
    try:
        with exclusive_dataset_operation():
            _run(session, config)
        return SeedReport(
            app_env=app_env,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            anchor=timeline.anchor,
            timezone_name=str(timeline.zone),
            run_id=session.run_id,
            account_count=len(ACCOUNTS),
            student_count=len(STUDENTS),
            created=dict(session.created),
            existing=dict(session.existing),
            notes=tuple(session.notes),
        )
    finally:
        reset_current_request_id(token)


__all__ = [
    "SEED_RUN_ADVISORY_LOCK_KEY",
    "SeedReport",
    "exclusive_dataset_operation",
    "seed_staging_dataset",
]
