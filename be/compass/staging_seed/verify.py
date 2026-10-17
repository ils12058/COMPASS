"""Read-only verification of COMPASS Staging Dataset v1 against its manifest.

``verify_dataset`` runs inside a ``READ ONLY`` PostgreSQL transaction when it is the outermost
transaction, so verification and report generation cannot change the database. It checks:

* schema: migrations applied, no model drift, no pre-canonical history, no retired ledger/tasks;
* configuration: canonical roles, capabilities, organization catalog, forms and service;
* accounts: identity, role, designations, lifecycle, affiliation, auth state, collisions;
* organization: Counselor responsibilities and staff supervision exactly as declared;
* scenarios: every executable scenario's documented initial state, via named predicates;
* workflow integrity: ownership, Counselor assignment, notifications, Work Queue projections;
* privacy and security: ciphertext-only storage, role scopes, DPO scope, disabled accounts;
* side effects: no outbound email/push intents and no E-Counseling rooms created by seeding.

During active UAT, ``allow_uat_changes`` reports evaluator-changed scenario states (and the email
they legitimately cause) as warnings; structural failures always fail.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import ProjectState
from django.utils import timezone

from compass.accounts.bootstrap import RETIRED_CAPABILITY_CODES
from compass.accounts.models import (
    Capability,
    DesignationCapability,
    RoleCapability,
    User,
)
from compass.accounts.policy import (
    CAPABILITY_CODES,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
)
from compass.accounts.services import effective_capabilities
from compass.announcements.models import Announcement
from compass.appointments.models import Appointment
from compass.audit.models import AuditEvent
from compass.authentication.models import AuthSession
from compass.availability.models import ProviderAvailabilityWindow
from compass.call_slips.models import CallSlip
from compass.common.canonical_baseline import pre_canonical_history
from compass.counseling.models import CounselingSharedSummary
from compass.ecounseling.models import ECounselingRoom
from compass.exit_interviews.models import ExitInterview, ExitInterviewOpportunity
from compass.feedback.models import (
    ClientSatisfactionResponse,
    CustomerFeedbackResponse,
    FeedbackOpportunity,
)
from compass.good_moral.models import GoodMoralRequest
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.guidance_messages.models import GuidanceThread, GuidanceThreadReadState
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    require_active_supported_form_revision,
)
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, Notification, PushDelivery
from compass.organization.academic_years import get_current_academic_year
from compass.organization.canonical import CANONICAL_CAMPUSES
from compass.organization.models import (
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
    StudentAffiliation,
)
from compass.privacy_governance.models import PrivacyNoticeRevision
from compass.referrals.models import Referral, ReferralAction
from compass.resources.models import Resource
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.bootstrap import canonical_counseling_readiness

from . import DATASET_NAME, DATASET_VERSION
from .config import load_config
from .guard import ensure_seeding_allowed_by_settings
from .identities import AccountSpec, AuthPlan, Lifecycle, StudentGroup, StudentSpec, Suitability
from .manifest import (
    ACCOUNTS,
    ACCOUNTS_BY_KEY,
    SCENARIOS,
    Readiness,
    email_for,
    stakeholder,
    validate_manifest,
)
from .seed import REQUIRED_FORM_FAMILIES, RETIRED_DEMO_IDENTIFIER_PREFIX
from .staff import COUNSELOR_RESPONSIBILITIES, STAFF_SUPERVISION
from .students import CURRENT_YEAR, STUDENTS

RETIRED_TABLES = (
    "privacy_governance_operationalretentionrule",
    "privacy_governance_dispositioncase",
    "privacy_governance_dispositionhold",
)
RETIRED_TASK_PREFIX = "compass.privacy_governance."
# Counseling-content authority: only Counselors (and the Head designation) hold these.
COUNSELING_CONTENT = frozenset(
    {
        "counseling.view_assigned",
        "counseling.manage_assigned",
        "shared_summaries.view_assigned",
        "shared_summaries.manage_assigned",
        "routine_interviews.view_assigned",
        "routine_interviews.manage_assigned",
        "inventory.view",
        "inventory.reopen",
        "student_support.view",
        "ecounseling.access_media_assigned",
        "ecounseling.manage_media_assigned",
        "exit_interviews.view",
        "exit_interviews.reopen",
        "graduate_tracer.view",
        "assessment_records.view",
        "assessment_records.manage",
    }
)
# Any guidance-record authority; IT Administrators and Institutional Officers hold none.
GUIDANCE_RECORD_PREFIXES = (
    "appointments.manage",
    "call_slips.",
    "counseling.",
    "ecounseling.",
    "exit_interviews.",
    "good_moral.",
    "graduate_tracer.",
    "guidance_messages.",
    "inventory.",
    "referrals.",
    "routine_interviews.",
    "shared_summaries.",
    "student_support.",
)


def _counseling_content(codes) -> bool:
    return any(code in COUNSELING_CONTENT for code in codes)


FERNET_TOKEN = re.compile(r"^gAAAAA[A-Za-z0-9_\-]+=*$")


@dataclass
class Section:
    name: str
    passed_count: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def check(self, condition: bool, message: str, *, changeable: bool = False, allow=False):
        if condition:
            self.passed_count += 1
        elif changeable and allow:
            self.warnings.append(f"{message} (changed since seeding)")
        else:
            self.failures.append(message)
        return condition


@dataclass
class AccountFacts:
    key: str
    email: str
    exists: bool
    active: bool
    auth_state: str
    lifecycle: str
    role: str
    designations: tuple[str, ...]
    campus: str = ""
    college: str = ""
    program: str = ""
    year_level: str = ""
    preloaded: tuple[str, ...] = ()


@dataclass
class VerificationResult:
    dataset_name: str
    dataset_version: int
    app_env: str
    generated_at: str
    preparation_dates: tuple[str, ...]
    sections: list[Section]
    accounts: dict[str, AccountFacts]
    scenario_status: dict[str, str]
    counts: dict[str, object]

    @property
    def passed(self) -> bool:
        return all(not section.failures for section in self.sections)


# --- Database lookups -----------------------------------------------------------------------


class Lookup:
    def __init__(self, now=None):
        self.users = {
            user.institutional_id: user
            for user in User.objects.select_related("role")
            .prefetch_related("designations")
            .filter(institutional_id__in=[a.institutional_id for a in ACCOUNTS])
        }
        self.current_year = get_current_academic_year()
        self.now = now or timezone.now()

    def user(self, key: str) -> User | None:
        return self.users.get(ACCOUNTS_BY_KEY[key].institutional_id)


def _current_inventory(lookup: Lookup, user):
    return StudentInventory.objects.filter(student=user, academic_year=lookup.current_year).first()


def _upcoming(lookup: Lookup, user, mode: str | None = None):
    rows = Appointment.objects.filter(student=user, status="SCHEDULED", starts_at__gt=lookup.now)
    return rows.filter(delivery_mode=mode) if mode else rows


def _predicate(lookup: Lookup, key: str, name: str) -> bool:
    user = lookup.user(key)
    if user is None:
        return False
    kind, _, arg = name.partition(":")
    if kind == "lifecycle":
        return user.student_lifecycle_status == arg
    if kind == "role":
        return user.role.code == arg
    if kind == "designation":
        return arg == "HEAD" and user.designations.filter(code="HEAD_GUIDANCE_COUNSELOR").exists()
    if kind == "inventory":
        item = _current_inventory(lookup, user)
        return {
            "missing": item is None,
            "draft": item is not None and item.submitted_at is None,
            "submitted": item is not None and item.submitted_at is not None,
        }[arg]
    if kind == "appointment":
        if arg == "none":
            return not Appointment.objects.filter(student=user).exists()
        if arg == "past_scheduled":
            return Appointment.objects.filter(
                student=user, status="SCHEDULED", starts_at__lt=lookup.now
            ).exists()
        mode = arg.split(":")[1]
        return _upcoming(lookup, user, None if mode == "ANY" else mode).exists()
    if kind == "routine":
        rows = RoutineInterview.objects.filter(student=user)
        if arg == "intake_draft":
            return rows.filter(intake_submitted_at__isnull=True).exists()
        return rows.filter(
            intake_submitted_at__isnull=False, evaluation_finalized_at__isnull=True
        ).exists()
    if kind == "ecounseling" and arg == "no_room":
        return not ECounselingRoom.objects.filter(appointment__student=user).exists()
    if kind == "exit":
        if arg == "historical_submitted":
            return (
                ExitInterview.objects.filter(student=user, status="SUBMITTED")
                .exclude(academic_year=lookup.current_year)
                .exists()
            )
        rows = ExitInterview.objects.filter(student=user, academic_year=lookup.current_year)
        opportunity = ExitInterviewOpportunity.objects.filter(
            student=user, academic_year=lookup.current_year
        )
        return {
            "opportunity_open": opportunity.filter(status="OPEN").exists() and not rows.exists(),
            "draft": rows.filter(status="DRAFT").exists(),
            "submitted": rows.filter(status="SUBMITTED").exists(),
            "none": not rows.exists() and not opportunity.exists(),
        }[arg]
    if kind == "good_moral":
        rows = GoodMoralRequest.objects.filter(student=user)
        if arg == "none":
            return not rows.exclude(status="CANCELLED").exists()
        return rows.filter(status=arg).exists()
    if kind == "tracer":
        rows = GraduateTracerResponse.objects.filter(student=user)
        return {
            "none": not rows.exists(),
            "draft": rows.filter(status="DRAFT").exists(),
            "submitted": rows.filter(status="SUBMITTED").exists(),
        }[arg]
    if kind == "messages":
        threads = GuidanceThread.objects.filter(student=user)
        if arg == "no_office_thread":
            return not threads.filter(kind="OFFICE").exists()
        for thread in threads.filter(last_sequence__gt=0):
            state = GuidanceThreadReadState.objects.filter(thread=thread, user=user).first()
            if state is None or state.last_read_sequence < thread.last_sequence:
                return True
        return False
    if kind == "summary":
        rows = CounselingSharedSummary.objects.filter(encounter__student=user)
        if arg == "draft":
            return rows.filter(published_at__isnull=True).exists()
        return rows.filter(published_at__isnull=False).exists()
    if kind == "call_slip":
        rows = CallSlip.objects.filter(student=user, voided_at__isnull=True)
        if arg == "completed":
            return rows.filter(interview_ended_at__isnull=False).exists()
        return rows.filter(issuance_mode="LIVE").exists()
    if kind == "referral":
        return Referral.objects.filter(
            student=user, voided_at__isnull=True, actions__isnull=True
        ).exists()
    if kind == "notifications":
        return Notification.objects.filter(recipient=user, read_at__isnull=True).exists()
    if kind == "publications":
        return (
            Announcement.objects.filter(status="PUBLISHED", audience="STUDENTS").exists()
            and Resource.objects.filter(status="PUBLISHED", audience="STUDENTS").exists()
        )
    if kind == "account":
        if arg == "disabled":
            return not user.is_active
        return user.is_active and user.email_verified_at is None and not user.has_usable_password()
    if kind == "provider":
        return Appointment.objects.filter(
            provider=user, status="SCHEDULED", starts_at__gt=lookup.now
        ).exists()
    if kind == "work_queue":
        from compass.work_queue.services import list_work

        return bool(list_work(actor=user).items)
    if kind == "activity":
        return AuditEvent.objects.filter(actor_user=user).exists()
    if kind == "reports":
        if arg == "tracer_data":
            return GraduateTracerResponse.objects.filter(status="SUBMITTED").exists()
        return StudentInventory.objects.filter(
            academic_year=lookup.current_year, submitted_at__isnull=False
        ).exists()
    if kind == "availability":
        return ProviderAvailabilityWindow.objects.filter(provider=user).exists()
    if kind == "feedback":
        if arg == "invitation_pending":
            return FeedbackOpportunity.objects.filter(
                student=user, customer_feedback_submitted_at__isnull=True
            ).exists()
        return (
            CustomerFeedbackResponse.objects.exists()
            and ClientSatisfactionResponse.objects.exists()
        )
    if kind == "academic_year":
        return lookup.current_year is not None and lookup.current_year.label == CURRENT_YEAR
    if kind == "responsibility":
        return CounselorResponsibility.objects.filter(counselor=user).count() == int(arg)
    capabilities = effective_capabilities(user)
    if kind == "capabilities":
        if arg == "none":
            return not capabilities
        return not _counseling_content(capabilities)
    if kind == "capability":
        return {
            "retention_view": "privacy_governance.retention.view" in capabilities,
            "activity_export": "privacy_governance.activity.export" in capabilities,
            "no_retention_manage": capabilities.isdisjoint(RETIRED_CAPABILITY_CODES),
        }[arg]
    if kind == "privacy":
        return PrivacyNoticeRevision.objects.filter(status="DRAFT").exists()
    raise KeyError(f"Unknown verification predicate {name}")


# --- Sections -------------------------------------------------------------------------------


def _schema(section: Section) -> None:
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    section.check(not plan, f"{len(plan)} migration(s) are not applied.")
    changes = MigrationAutodetector(
        executor.loader.project_state(), ProjectState.from_apps(apps)
    ).changes(graph=executor.loader.graph)
    section.check(not changes, f"Model drift: {sorted(changes)} need migrations.")
    unknown = pre_canonical_history(connection)
    section.check(not unknown, f"Pre-canonical migration history recorded: {unknown[:3]}.")
    tables = set(connection.introspection.table_names())
    section.check(tables.isdisjoint(RETIRED_TABLES), "A retired disposition ledger table exists.")
    from config.celery import app

    app.autodiscover_tasks(force=True)
    retired = [name for name in app.tasks if name.startswith(RETIRED_TASK_PREFIX)]
    section.check(not retired, f"Retired disposition tasks are registered: {retired}.")


def _configuration(section: Section) -> None:
    capabilities = set(Capability.objects.values_list("code", flat=True))
    section.check(set(CAPABILITY_CODES) <= capabilities, "Canonical capabilities are missing.")
    section.check(
        capabilities.isdisjoint(RETIRED_CAPABILITY_CODES), "A retired capability still exists."
    )
    for role, grants in ROLE_CAPABILITY_GRANTS.items():
        stored = set(
            RoleCapability.objects.filter(role__code=role).values_list(
                "capability__code", flat=True
            )
        )
        section.check(set(grants) <= stored, f"Role {role} lacks its canonical capability grants.")
    for designation, grants in DESIGNATION_CAPABILITY_GRANTS.items():
        stored = set(
            DesignationCapability.objects.filter(designation__code=designation).values_list(
                "capability__code", flat=True
            )
        )
        section.check(set(grants) <= stored, f"Designation {designation} lacks canonical grants.")
    for campus in CANONICAL_CAMPUSES:
        for college in campus.colleges:
            for program in college.programs:
                section.check(
                    Program.objects.filter(
                        college__campus__code=campus.code,
                        college__code=college.code,
                        code=program.code,
                        is_active=True,
                    ).exists(),
                    f"Catalog program {campus.code}/{college.code}/{program.code} is missing.",
                )
    for family in REQUIRED_FORM_FAMILIES:
        try:
            require_active_supported_form_revision(family)
            section.check(True, "")
        except InstitutionalFormConflict:
            section.check(False, f"Institutional form {family} has no active supported revision.")
    ready, reason = canonical_counseling_readiness()
    section.check(ready, f"The canonical Counseling Service is not ready ({reason}).")
    current = get_current_academic_year()
    section.check(
        current is not None and current.label == CURRENT_YEAR,
        f"The current Academic Year is not {CURRENT_YEAR}.",
    )


def _auth_state(user: User) -> str:
    if not user.is_active:
        return "Disabled"
    if user.has_usable_password():
        return "Credential issued"
    if user.email_verified_at is None:
        return "Onboarding (never signed in)"
    return "Awaiting credential issuance"


def _accounts(section: Section, lookup: Lookup, domain, onboarding, allow) -> dict:
    facts: dict[str, AccountFacts] = {}
    for account in ACCOUNTS:
        user = lookup.user(account.key)
        email = email_for(account, domain=domain, onboarding_email=onboarding)
        if not section.check(user is not None, f"{account.key}: account is not seeded."):
            facts[account.key] = AccountFacts(
                account.key, email, False, False, "Missing", "", account.role, ()
            )
            continue
        designations = tuple(sorted(item.code for item in user.designations.all()))
        section.check(user.email == email, f"{account.key}: email differs from the manifest.")
        section.check(user.role.code == account.role, f"{account.key}: role is {user.role.code}.")
        section.check(
            designations == tuple(sorted(account.designations)),
            f"{account.key}: designations {designations} differ from the manifest.",
        )
        section.check(
            (user.first_name, user.middle_name, user.last_name)
            == (account.first_name, account.middle_name, account.last_name),
            f"{account.key}: name differs from the manifest.",
        )
        section.check(
            user.is_active == account.active,
            f"{account.key}: active={user.is_active}, expected {account.active}.",
            changeable=account.active,
            allow=allow,
        )
        if account.auth == AuthPlan.ONBOARDING:
            section.check(
                user.email_verified_at is None and not user.has_usable_password(),
                f"{account.key}: onboarding is already completed.",
                changeable=True,
                allow=allow,
            )
        elif account.active:
            section.check(
                user.email_verified_at is not None, f"{account.key}: email is not verified."
            )
        lifecycle = user.student_lifecycle_status or ""
        fact = AccountFacts(
            key=account.key,
            email=user.email,
            exists=True,
            active=user.is_active,
            auth_state=_auth_state(user),
            lifecycle=lifecycle,
            role=user.role.code,
            designations=designations,
        )
        if isinstance(account, StudentSpec):
            section.check(
                lifecycle == account.lifecycle,
                f"{account.key}: lifecycle is {lifecycle}, expected {account.lifecycle}.",
            )
            affiliation = (
                StudentAffiliation.objects.select_related("college__campus")
                .filter(student=user)
                .first()
            )
            if account.affiliated:
                section.check(
                    affiliation is not None
                    and (affiliation.college.campus.code, affiliation.college.code)
                    == (account.campus_code, account.college_code),
                    f"{account.key}: College affiliation differs from the manifest.",
                )
            else:
                section.check(
                    affiliation is None, f"{account.key}: a non-current Student has a College."
                )
            inventory = (
                StudentInventory.objects.select_related("program")
                .filter(student=user)
                .order_by("-academic_year__label")
                .first()
            )
            if inventory is not None:
                section.check(
                    inventory.program.code == account.program_code,
                    f"{account.key}: Inventory Program {inventory.program.code} differs.",
                )
            year = account.enrolled_year_level or (
                account.year_levels[-1][1] if account.year_levels else None
            )
            fact.campus = account.campus_code
            fact.college = account.college_code
            fact.program = account.program_code
            fact.year_level = str(year or "")
        facts[account.key] = fact
    known = {account.institutional_id for account in ACCOUNTS}
    strays = User.objects.filter(institutional_id__startswith="STG-").exclude(
        institutional_id__in=known
    )
    section.check(not strays.exists(), f"{strays.count()} STG- account(s) are not in the manifest.")
    section.check(
        not User.objects.filter(
            institutional_id__startswith=RETIRED_DEMO_IDENTIFIER_PREFIX
        ).exists(),
        "Retired Demo Dataset accounts are present.",
    )
    emails = [fact.email for fact in facts.values() if fact.exists]
    section.check(len(emails) == len(set(emails)), "Two dataset accounts share an email.")
    return facts


def _organization(section: Section, lookup: Lookup) -> None:
    for counselor_key, campus, college in COUNSELOR_RESPONSIBILITIES:
        row = CounselorResponsibility.objects.filter(
            college__campus__code=campus, college__code=college
        ).first()
        user = lookup.user(counselor_key)
        section.check(
            row is not None and user is not None and row.counselor_id == user.pk,
            f"{campus}/{college} is not routed to {counselor_key}.",
        )
    for staff_key, supervisor_key in STAFF_SUPERVISION:
        staff, supervisor = lookup.user(staff_key), lookup.user(supervisor_key)
        row = StaffSupervision.objects.filter(staff=staff).first() if staff else None
        if staff is not None and not staff.is_active:
            section.check(row is None, f"Disabled {staff_key} still has a supervisor.")
        else:
            section.check(
                row is not None and supervisor is not None and row.supervisor_id == supervisor.pk,
                f"{staff_key} is not supervised by {supervisor_key}.",
            )


def _mutable_accounts() -> frozenset[str]:
    """Accounts whose state some mutating scenario legitimately changes during UAT."""

    return frozenset(
        key
        for scenario in SCENARIOS
        if scenario.mutating
        for key in (scenario.account, *scenario.related, *(check[0] for check in scenario.checks))
    )


def _scenarios(section: Section, lookup: Lookup, allow) -> dict[str, str]:
    status: dict[str, str] = {}
    mutable = _mutable_accounts()
    for scenario in SCENARIOS:
        if scenario.readiness != Readiness.EXECUTABLE:
            status[scenario.id] = Readiness.PENDING_IMPLEMENTATION
            continue
        ok = True
        for key, predicate in scenario.checks:
            held = _predicate(lookup, key, predicate)
            ok = ok and held
            section.check(
                held,
                f"{scenario.id}: {key} is not '{predicate}'.",
                changeable=scenario.mutating or key in mutable,
                allow=allow,
            )
        status[scenario.id] = "READY" if ok else "CHANGED"
    return status


def _workflow(section: Section, lookup: Lookup, allow) -> None:
    students = [lookup.user(s.key) for s in STUDENTS]
    ids = [user.pk for user in students if user is not None]
    responsibility = dict(CounselorResponsibility.objects.values_list("college_id", "counselor_id"))
    head = lookup.user("head_guidance")
    for appointment in Appointment.objects.filter(student_id__in=ids).select_related("student"):
        affiliation = StudentAffiliation.objects.filter(student=appointment.student).first()
        expected = responsibility.get(affiliation.college_id) if affiliation else None
        section.check(
            appointment.provider_id in {expected, head.pk if head else None},
            f"Appointment {appointment.reference_code} is with neither the Counselor nor Head.",
            changeable=True,
            allow=allow,
        )
    duplicates = (
        StudentInventory.objects.filter(student_id__in=ids)
        .values_list("student_id", "academic_year_id")
        .order_by()
    )
    section.check(
        len(duplicates) == len(set(duplicates)), "A Student has two Inventories in one year."
    )
    for summary in CounselingSharedSummary.objects.filter(
        encounter__student_id__in=ids, published_at__isnull=False
    ).select_related("encounter"):
        section.check(
            Notification.objects.filter(
                recipient_id=summary.encounter.student_id, source_id=summary.pk
            ).exists(),
            "A published Shared Summary has no Student notification.",
        )
    for slip in CallSlip.objects.filter(student_id__in=ids, issuance_mode="LIVE"):
        section.check(
            Notification.objects.filter(recipient_id=slip.student_id, source_id=slip.pk).exists(),
            "A LIVE Call Slip has no Student notification.",
        )
    for request in GoodMoralRequest.objects.filter(student_id__in=ids, status="ISSUED"):
        section.check(
            Notification.objects.filter(
                recipient_id=request.student_id, source_id=request.pk
            ).exists(),
            "An issued Good Moral request has no Student notification.",
        )
    from compass.work_queue.services import list_work

    for key in ("counselor_a", "counselor_b", "counselor_c", "gss_a", "gss_b", "head_guidance"):
        user = lookup.user(key)
        section.check(
            user is not None and bool(list_work(actor=user).items),
            f"The Work Queue for {key} is empty.",
            changeable=True,
            allow=allow,
        )
    unassigned = lookup.user("unassigned_counselor")
    # Good Moral preparation and issuance are office-wide by design (good_moral.work); every
    # caseload-scoped item must be absent for a Counselor without College responsibility.
    office_wide = {"GOOD_MORAL_PREPARATION", "GOOD_MORAL_ISSUANCE"}
    section.check(
        unassigned is not None
        and {item.kind.value for item in list_work(actor=unassigned).items} <= office_wide,
        "The unassigned Counselor's Work Queue shows caseload-scoped items.",
    )


def _ciphertext_columns():
    for model in apps.get_models():
        if not model.__module__.startswith("compass."):
            continue
        for field_ in model._meta.concrete_fields:
            if field_.name.endswith("_ciphertext"):
                yield model, field_.column


def _privacy(section: Section, lookup: Lookup) -> None:
    checked = 0
    with connection.cursor() as cursor:
        for model, column in _ciphertext_columns():
            table = connection.ops.quote_name(model._meta.db_table)
            cursor.execute(
                f"SELECT {connection.ops.quote_name(column)} FROM {table} "  # noqa: S608
                f"WHERE {connection.ops.quote_name(column)} IS NOT NULL"
            )
            for (value,) in cursor.fetchall():
                checked += 1
                if not FERNET_TOKEN.match(value or ""):
                    section.check(False, f"{model.__name__}.{column} holds a non-ciphertext value.")
                    break
            else:
                section.check(True, "")
        cursor.execute(
            "SELECT count(*) FROM inventory_studentinventory WHERE "
            "full_name_snapshot IS NOT NULL AND confidential_content_ciphertext LIKE %s",
            ["%Synthetic household%"],
        )
        section.check(cursor.fetchone()[0] == 0, "An Inventory stores readable confidential text.")
    section.check(checked > 0, "No encrypted dataset content was found to verify.")
    for account in ACCOUNTS:
        user = lookup.user(account.key)
        if user is None:
            continue
        capabilities = effective_capabilities(user)
        if account.role == "STUDENT":
            section.check(
                all(
                    code.endswith(("_self", ".submit_csm", ".submit_customer_feedback"))
                    or code in {"accounts.view", "availability.view", "organization.structure.view"}
                    or code == "services.catalog.view"
                    for code in capabilities
                ),
                f"{account.key}: a Student holds a non-self capability.",
            )
        elif account.role == "GUIDANCE_SERVICES_STAFF":
            section.check(
                not _counseling_content(capabilities),
                f"{account.key}: staff hold counseling-content capabilities.",
            )
        elif account.role != "COUNSELOR":
            section.check(
                not any(code.startswith(GUIDANCE_RECORD_PREFIXES) for code in capabilities),
                f"{account.key}: holds guidance-record capabilities.",
            )
        if "DPO" in account.designations:
            section.check(
                capabilities == frozenset(DESIGNATION_CAPABILITY_GRANTS["DPO"]),
                f"{account.key}: DPO scope differs from the DPO designation.",
            )
        if not account.active:
            section.check(not user.is_active, f"{account.key}: a disabled account is active.")
            section.check(
                not AuthSession.objects.filter(user=user, revoked_at__isnull=True).exists(),
                f"{account.key}: a disabled account has a live session.",
            )


def _side_effects(section: Section, lookup: Lookup, allow) -> None:
    ids = [user.pk for user in lookup.users.values()]
    emails = EmailDelivery.objects.filter(notification__recipient_id__in=ids)
    section.check(
        not emails.exists(),
        f"{emails.count()} email delivery intent(s) exist for dataset accounts.",
        changeable=True,
        allow=allow,
    )
    section.check(
        not PushDelivery.objects.filter(notification__recipient_id__in=ids).exists(),
        "Push delivery intents exist for dataset accounts.",
        changeable=True,
        allow=allow,
    )
    rooms = ECounselingRoom.objects.filter(appointment__student_id__in=ids)
    section.check(
        not rooms.filter(daily_room_id__isnull=False).exists(),
        "A provider-provisioned Daily room exists for a dataset Appointment.",
        changeable=True,
        allow=allow,
    )
    section.check(
        not rooms.exists(),
        f"{rooms.count()} local E-Counseling room binding(s) exist.",
        changeable=True,
        allow=allow,
    )
    section.check(not settings.DEBUG or settings.APP_ENV == "local-staging", "DEBUG is enabled.")


# --- Counts and preloaded state ---------------------------------------------------------------


def _preloaded(lookup: Lookup, account: AccountSpec) -> tuple[str, ...]:
    user = lookup.user(account.key)
    if user is None or not account.is_student:
        return ()
    items = []
    inventory = _current_inventory(lookup, user)
    if account.lifecycle == Lifecycle.CURRENT:
        items.append(
            "Inventory 2026-2027: "
            + (
                "missing"
                if inventory is None
                else "draft"
                if not inventory.submitted_at
                else "submitted"
            )
        )
    history = StudentInventory.objects.filter(student=user).exclude(
        academic_year=lookup.current_year
    )
    if history.exists():
        items.append(f"{history.count()} historical Inventory record(s)")
    statuses = Counter(
        "upcoming"
        if row.status == "SCHEDULED" and row.starts_at > lookup.now
        else "past, awaiting outcome"
        if row.status == "SCHEDULED"
        else row.status.lower()
        for row in Appointment.objects.filter(student=user)
    )
    if statuses:
        items.append("Appointments: " + ", ".join(f"{n} {s}" for s, n in sorted(statuses.items())))
    for model, label in (
        (RoutineInterview, "Routine Interview"),
        (Referral, "Referral"),
        (CallSlip, "Call Slip"),
    ):
        count = model.objects.filter(student=user).count()
        if count:
            items.append(f"{count} {label}{'s' if count > 1 else ''}")
    for request in GoodMoralRequest.objects.filter(student=user):
        items.append(f"Good Moral {request.variant.lower().replace('_', '-')}: {request.status}")
    for interview in ExitInterview.objects.filter(student=user).select_related("academic_year"):
        items.append(f"Exit Interview {interview.academic_year.label}: {interview.status}")
    opportunity = ExitInterviewOpportunity.objects.filter(
        student=user, academic_year=lookup.current_year, status="OPEN"
    )
    if (
        opportunity.exists()
        and not ExitInterview.objects.filter(
            student=user, academic_year=lookup.current_year
        ).exists()
    ):
        items.append("Exit Interview opportunity open (not started)")
    for response in GraduateTracerResponse.objects.filter(student=user):
        items.append(f"Graduate Tracer: {response.status}")
    if _predicate(lookup, account.key, "messages:unread"):
        items.append("Unread Guidance Message")
    summaries = CounselingSharedSummary.objects.filter(encounter__student=user)
    if summaries.exists():
        published = summaries.filter(published_at__isnull=False).count()
        items.append(
            f"Shared Summaries: {published} published, {summaries.count() - published} draft"
        )
    unread = Notification.objects.filter(recipient=user, read_at__isnull=True).count()
    if unread:
        items.append(f"{unread} unread notification(s)")
    return tuple(items)


def _slip_state(slip: CallSlip) -> str:
    if slip.voided_at:
        return "voided"
    return "completed" if slip.interview_ended_at else "open"


def _breakdown(values) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _counts(lookup: Lookup, facts: dict[str, AccountFacts]) -> dict[str, object]:
    students = [s for s in STUDENTS if facts[s.key].exists]
    ids = [lookup.user(s.key).pk for s in students]
    staff = [a for a in ACCOUNTS if not a.is_student and facts[a.key].exists]
    appointments = Appointment.objects.filter(student_id__in=ids)
    return {
        "students": len(students),
        "staff": len(staff),
        "accounts": len(students) + len(staff),
        "by_group": _breakdown(s.group.value for s in students),
        "by_suitability": _breakdown(a.suitability.value for a in ACCOUNTS if facts[a.key].exists),
        "participants_by_role": _breakdown(
            stakeholder(a)
            for a in ACCOUNTS
            if a.suitability == Suitability.PARTICIPANT and facts[a.key].exists
        ),
        "by_lifecycle": _breakdown(facts[s.key].lifecycle for s in students),
        "by_campus": _breakdown(s.campus_code for s in students),
        "by_college": _breakdown(f"{s.campus_code}/{s.college_code}" for s in students),
        "by_program": _breakdown(f"{s.college_code}/{s.program_code}" for s in students),
        "by_year_level": _breakdown(
            facts[s.key].year_level or "n/a" for s in students if s.lifecycle == Lifecycle.CURRENT
        ),
        "by_auth_state": _breakdown(facts[a.key].auth_state for a in ACCOUNTS),
        "current_inventory": _breakdown(
            (
                "missing"
                if (item := _current_inventory(lookup, lookup.user(s.key))) is None
                else "draft"
                if item.submitted_at is None
                else "submitted"
            )
            for s in students
            if s.lifecycle == Lifecycle.CURRENT
        ),
        "inventories_total": StudentInventory.objects.filter(student_id__in=ids).count(),
        "appointments": _breakdown(
            "SCHEDULED (upcoming)"
            if a.status == "SCHEDULED" and a.starts_at > lookup.now
            else "SCHEDULED (past, awaiting outcome)"
            if a.status == "SCHEDULED"
            else a.status
            for a in appointments
        ),
        "appointment_modes": _breakdown(appointments.values_list("delivery_mode", flat=True)),
        "encounters": apps.get_model("counseling", "CounselingEncounter")
        .objects.filter(student_id__in=ids)
        .count(),
        "shared_summaries": _breakdown(
            "published" if s.published_at else "draft"
            for s in CounselingSharedSummary.objects.filter(encounter__student_id__in=ids)
        ),
        "routine_interviews": _breakdown(
            "intake draft"
            if r.intake_submitted_at is None
            else "evaluation finalized"
            if r.evaluation_finalized_at
            else "evaluation pending"
            for r in RoutineInterview.objects.filter(student_id__in=ids)
        ),
        "referrals": _breakdown(
            "voided" if r.voided_at else "with action" if r.actions.exists() else "no action yet"
            for r in Referral.objects.filter(student_id__in=ids)
        ),
        "call_slips": _breakdown(
            f"{c.issuance_mode} {_slip_state(c)}"
            for c in CallSlip.objects.filter(student_id__in=ids)
        ),
        "good_moral": _breakdown(
            GoodMoralRequest.objects.filter(student_id__in=ids).values_list("status", flat=True)
        ),
        "exit_interviews": _breakdown(
            f"{e.academic_year.label} {e.status}"
            for e in ExitInterview.objects.filter(student_id__in=ids).select_related(
                "academic_year"
            )
        ),
        "exit_opportunities_open": ExitInterviewOpportunity.objects.filter(
            student_id__in=ids, status="OPEN"
        ).count(),
        "graduate_tracer": _breakdown(
            GraduateTracerResponse.objects.filter(student_id__in=ids).values_list(
                "status", flat=True
            )
        ),
        "guidance_threads": GuidanceThread.objects.filter(student_id__in=ids).count(),
        "notifications": _breakdown(
            "unread" if n.read_at is None else "read"
            for n in Notification.objects.filter(recipient_id__in=[*ids])
        ),
        "customer_feedback": CustomerFeedbackResponse.objects.count(),
        "csm_responses": ClientSatisfactionResponse.objects.count(),
        "announcements": _breakdown(Announcement.objects.values_list("status", flat=True)),
        "resources": _breakdown(Resource.objects.values_list("status", flat=True)),
        "referral_actions": ReferralAction.objects.filter(referral__student_id__in=ids).count(),
        "colleges_covered": CounselorResponsibility.objects.count(),
        "colleges_total": College.objects.filter(is_active=True).count(),
        "scenarios_executable": sum(s.readiness == Readiness.EXECUTABLE for s in SCENARIOS),
        "scenarios_pending": sum(s.readiness != Readiness.EXECUTABLE for s in SCENARIOS),
        "students_by_group_campus": _breakdown(
            f"{s.group.value}:{s.campus_code}" for s in students if s.group != StudentGroup.RICH
        ),
    }


def _preparation_dates() -> tuple[str, ...]:
    """Distinct institutional dates of seed runs, from their own audit events."""

    from compass.common.institutional_time import institution_date

    users = User.objects.filter(institutional_id__startswith="STG-")
    events = AuditEvent.objects.filter(
        action="account.created", actor_type="SYSTEM", target_id__in=[str(u.pk) for u in users]
    ).values_list("occurred_at", flat=True)
    return tuple(sorted({institution_date(value).isoformat() for value in events}))


def _verify(allow_uat_changes: bool, now) -> VerificationResult:
    app_env = ensure_seeding_allowed_by_settings()
    config = load_config(app_env=app_env)
    validate_manifest()
    lookup = Lookup(now)
    sections = [
        Section(name)
        for name in (
            "Schema readiness",
            "Canonical configuration",
            "Account readiness",
            "Organization routing",
            "Scenario initial states",
            "Workflow integrity",
            "Privacy and security",
            "External side effects",
        )
    ]
    schema, configuration, accounts, organization, scenarios, workflow, privacy, effects = sections
    _schema(schema)
    _configuration(configuration)
    facts = _accounts(
        accounts, lookup, config.email_domain, config.onboarding_email, allow_uat_changes
    )
    _organization(organization, lookup)
    status = _scenarios(scenarios, lookup, allow_uat_changes)
    _workflow(workflow, lookup, allow_uat_changes)
    _privacy(privacy, lookup)
    _side_effects(effects, lookup, allow_uat_changes)
    for account in ACCOUNTS:
        if facts[account.key].exists:
            facts[account.key].preloaded = _preloaded(lookup, account)
    return VerificationResult(
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        app_env=app_env,
        generated_at=timezone.localtime(lookup.now).isoformat(timespec="seconds"),
        preparation_dates=_preparation_dates(),
        sections=sections,
        accounts=facts,
        scenario_status=status,
        counts=_counts(lookup, facts),
    )


def verify_dataset(*, allow_uat_changes: bool = False, now=None) -> VerificationResult:
    """Verify the dataset without changing the database.

    ``now`` defaults to the current time; tests pass the dataset's own clock.
    """

    outermost = not connection.in_atomic_block
    with transaction.atomic():
        if outermost:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
        result = _verify(allow_uat_changes, now)
        # Nothing to keep: verification never writes, and the read-only transaction ends here.
        transaction.set_rollback(True)
    return result


__all__ = ["AccountFacts", "Section", "VerificationResult", "verify_dataset"]
