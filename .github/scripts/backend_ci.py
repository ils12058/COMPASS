#!/usr/bin/env python3
"""COMPASS backend CI: dependency-aware test selection and runtime-balanced sharding.

Pull requests run a *targeted* selection: the always-run safety bundle plus the bundles mapped
from the backend areas a change touches. Shared infrastructure, settings, migrations, dependency
changes, and any path this file does not recognize select the complete suite instead. Targeted
never means a test is skipped for good: every staging revision runs the complete suite (see
``backend-full.yml``), and deployment requires that exact revision to have passed it.

Subcommands (run from anywhere; selection and planning need only the standard library):

  select      Map changed paths (``--base``/``--head`` git SHAs) to test files and print why.
  plan        Show how selected or all test files are balanced across shards.
  run-shard   Run one shard's tests with pytest (run inside the backend virtualenv).
  verify      Check that every test file is in a bundle and in exactly one full-regression shard.
  durations   Rebuild the per-file duration table from pytest JUnit XML reports.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "be"
TESTS = BACKEND / "tests"
DURATIONS_FILE = Path(__file__).with_name("backend_test_durations.json")

FULL_SHARDS = 6
TARGETED_MAX_SHARDS = 6
# Aim for shards of about seven minutes of pytest time in targeted runs.
TARGETED_SHARD_SECONDS = 420
DEFAULT_TEST_SECONDS = 30.0

# Files too slow to run as one unit. Their tests are distributed round-robin by node id, which is
# safe because their fixtures are function-scoped (no class- or module-level setup is repeated).
SPLIT_FILES = {
    "test_inventory_confidential_content_encryption.py": 4,
    "test_graduate_tracer_confidential_content_encryption.py": 2,
}

# --------------------------------------------------------------------------------------------
# Test bundles. Every backend test file belongs to at least one bundle (``verify`` enforces it).
# --------------------------------------------------------------------------------------------

BUNDLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "safety": (
        "Always run: cheap system-wide invariants that any backend change can break.",
        (
            # Settings, institutional time, and startup readiness.
            "test_common_config.py",
            "test_institutional_time.py",
            "test_health.py",
            "test_build_metadata.py",
            "test_request_context.py",
            # Every locking query is scoped to its own rows; database errors map safely.
            "test_lock_scope.py",
            "test_database_error_mapping.py",
            # The audit trail and identity/access policy (capabilities, step-up) are global.
            "test_audit.py",
            "test_capability_dependencies.py",
            "test_step_up_policy.py",
            # The API surface: meta endpoint and the typed OpenAPI contract.
            "test_metadata.py",
            "test_openapi_contract.py",
        ),
    ),
    "identity-access": (
        "Accounts, authentication, passwords, profiles, and institutional identity.",
        (
            "test_accounts.py",
            "test_authentication.py",
            "test_password_access.py",
            "test_password_change.py",
            "test_email_change.py",
            "test_account_management.py",
            "test_account_csv_import.py",
            "test_account_profile_confidential_content_encryption.py",
            "test_capability_rename_migration.py",
            "test_profiles.py",
            "test_profile_photos.py",
            "test_institutional_identity.py",
            "test_rate_limit.py",
            "test_turnstile.py",
            "test_idempotency.py",
        ),
    ),
    "activity-audit": (
        "Activity history, retrieval, and platform/privacy activity views.",
        (
            "test_activity.py",
            "test_activity_retrieval.py",
            "test_platform_activity.py",
            "test_privacy_activity.py",
        ),
    ),
    "organization": (
        "Campus/College/Program structure, catalogs, and operational student lookups.",
        (
            "test_organization.py",
            "test_organization_catalog.py",
            "test_program_inventory_academic_context.py",
            "test_operational_students.py",
        ),
    ),
    "service-catalog": (
        "Services, canonical Counseling, provider qualification, scheduling consequences.",
        (
            "test_service_catalog.py",
            "test_canonical_services.py",
            "test_service_provider_qualification.py",
            "test_service_scheduling_consequences.py",
        ),
    ),
    "scheduling": (
        "Appointments and Availability, including reservations and lifecycle reconciliation.",
        (
            "test_appointments.py",
            "test_appointment_action_projection.py",
            "test_appointment_management_scope.py",
            "test_appointment_slot_reservations.py",
            "test_availability.py",
            "test_availability_reservation_neutrality.py",
            "test_cross_domain_lifecycle_reconciliation.py",
        ),
    ),
    "guidance-messages": (
        "Guidance Messages encryption, workload/relationship authorization and commit hints.",
        (
            "test_guidance_messages.py",
            "test_guidance_messages_concurrency.py",
            "test_guidance_messages_context.py",
            "test_guidance_messages_realtime.py",
        ),
    ),
    "counseling": (
        "Counseling encounters, context, shared summaries, and downstream lifecycle.",
        (
            "test_counseling.py",
            "test_counseling_context.py",
            "test_counseling_downstream_lifecycle.py",
            "test_counseling_frontend_readiness.py",
            "test_counseling_shared_summary_encryption.py",
            "test_shared_summaries.py",
            "test_inventory_counseling_regression.py",
        ),
    ),
    "routine-interviews": (
        "Routine Interviews, their encryption, and Encounter/Inventory linking.",
        (
            "test_routine_interviews.py",
            "test_routine_interview_encryption.py",
            "test_routine_crypto_compatibility.py",
            "test_routine_encounter_linking.py",
            "test_routine_inventory_decoupling.py",
        ),
    ),
    "ecounseling": (
        "E-Counseling rooms, the Daily integration seam, and media governance.",
        (
            "test_ecounseling.py",
            "test_ecounseling_media.py",
            "test_ecounseling_media_v2.py",
            "test_ecounseling_media_v2_migration.py",
            "test_daily_integration.py",
            "test_sensitive_media_storage.py",
        ),
    ),
    "referrals-call-slips": (
        "Referrals and Call Slips, which create and void each other.",
        (
            "test_referrals.py",
            "test_referral_confidential_content_encryption.py",
            "test_referral_call_slip_lifecycle.py",
            "test_call_slips.py",
            "test_call_slip_issuance_provenance.py",
            "test_operational_students.py",
        ),
    ),
    "inventory": (
        "Individual Inventory workflow, review, documents, and profiling normalization.",
        (
            "test_inventory.py",
            "test_inventory_counselor_review.py",
            "test_inventory_documents.py",
            "test_inventory_frontend_readiness.py",
            "test_inventory_profiling_normalization.py",
            "test_program_inventory_academic_context.py",
            "test_institutional_identity.py",
        ),
    ),
    "inventory-encryption": (
        "Inventory confidential-content encryption and its migrations (slow; split by node id).",
        ("test_inventory_confidential_content_encryption.py",),
    ),
    "student-support": (
        "Student Support profiles derived from the Inventory.",
        ("test_student_support.py", "test_student_support_migrations.py"),
    ),
    "exit-interviews": (
        "Exit Interviews, opportunities, documents, and encryption.",
        (
            "test_exit_interviews.py",
            "test_exit_interview_documents.py",
            "test_exit_interview_opportunities.py",
            "test_exit_interview_confidential_content_encryption.py",
        ),
    ),
    "good-moral": (
        "Good Moral requests, preparation, issuance, and release audit.",
        ("test_good_moral.py", "test_good_moral_preparation.py", "test_privacy_release_audit.py"),
    ),
    "feedback": (
        "Customer feedback and CSM responses, including encryption.",
        ("test_feedback.py", "test_feedback_confidential_content_encryption.py"),
    ),
    "graduate-tracer": (
        "Graduate Tracer responses, encryption, reports, and exports.",
        (
            "test_graduate_tracer.py",
            "test_graduate_tracer_confidential_content_encryption.py",
            "test_graduate_tracer_reports.py",
            "test_graduate_tracer_xlsx.py",
        ),
    ),
    "reports": (
        "Student profiling and Graduate Tracer reports in every output format.",
        (
            "test_student_profiling_reports.py",
            "test_student_profiling_report_aggregates.py",
            "test_student_profiling_report_coverage.py",
            "test_student_profiling_pdf.py",
            "test_student_profiling_xlsx.py",
            "test_graduate_tracer_reports.py",
            "test_graduate_tracer_xlsx.py",
        ),
    ),
    "privacy-governance": (
        "Privacy notices, acknowledgments, release audit, and operational retention.",
        (
            "test_privacy_governance.py",
            "test_privacy_governance_contract.py",
            "test_privacy_governance_expansion.py",
            "test_privacy_governance_migrations.py",
            "test_privacy_pending_acknowledgment.py",
            "test_privacy_release_audit.py",
            "test_privacy_activity.py",
            "test_operational_retention.py",
        ),
    ),
    "documents": (
        "Document rendering and every controlled-form PDF that uses it.",
        (
            "test_documents.py",
            "test_documents_migrations.py",
            "test_inventory_documents.py",
            "test_exit_interview_documents.py",
            "test_student_profiling_pdf.py",
            "test_call_slips.py",
            "test_referrals.py",
            "test_good_moral.py",
            "test_final_api_ergonomics.py",
        ),
    ),
    "institutional-forms": (
        "Institutional Form Families/Revisions and the catalogs that bootstrap them.",
        ("test_institutional_forms.py", "test_organization_catalog.py"),
    ),
    "notifications": (
        "In-app, email, and push notifications and their delivery workers.",
        (
            "test_notifications.py",
            "test_notification_realtime.py",
            "test_notification_delivery.py",
            "test_notification_push.py",
            "test_transactional_email.py",
            "test_mail.py",
            "test_celery.py",
        ),
    ),
    "platform-ops": (
        "Platform operations, maintenance, email operations, and diagnostics.",
        (
            "test_platform_operations.py",
            "test_platform_email_operations.py",
            "test_platform_activity.py",
            "test_runtime_maintenance.py",
            "test_runtime_operations_audit.py",
            "test_compass_doctor.py",
            "test_transactional_email.py",
        ),
    ),
    "content": (
        "Announcements, Resources, publication audiences, and object storage.",
        ("test_announcements.py", "test_resources.py", "test_storage.py"),
    ),
    "reference-data": (
        "PSGC reference data and its integration client.",
        ("test_psgc_integration.py", "test_psgc_reference_api.py"),
    ),
    "cross-domain-lists": (
        "Collection ordering, record retrieval, and the Overview, which read many domains.",
        ("test_collection_ordering.py", "test_record_retrieval.py", "test_overview.py"),
    ),
    "cross-domain-api": (
        "End-to-end API ergonomics and lifecycle completion across scheduling and cases.",
        (
            "test_final_api_ergonomics.py",
            "test_final_api_lifecycle_completion.py",
            "test_cross_domain_lifecycle_reconciliation.py",
        ),
    ),
    "crypto": (
        "The shared confidential-data primitive and Routine Interview crypto compatibility.",
        ("test_confidential_data_crypto.py", "test_routine_crypto_compatibility.py"),
    ),
    "demo-seed": (
        "The staging demo dataset seeders, which drive nearly every domain service.",
        ("test_demo_seed.py", "test_demo_seed_v2.py"),
    ),
    "deployment-runtime": (
        "Runtime secrets, compose files, Redis/Celery configuration, and build metadata.",
        (
            "test_runtime_secrets.py",
            "test_runtime_secrets_compose.py",
            "test_redis_config.py",
            "test_celery.py",
            "test_build_metadata.py",
            "test_health.py",
            "test_common_config.py",
            "test_realtime_isolation.py",
        ),
    ),
    "realtime": (
        "Realtime tickets, session-revocation hooks, and the standalone WebSocket service.",
        (
            "test_realtime_tickets.py",
            "test_notification_realtime.py",
            "test_realtime_service.py",
            "test_realtime_isolation.py",
            "test_redis_config.py",
        ),
    ),
}


@dataclass(frozen=True)
class Area:
    """What a changed path means for testing."""

    name: str
    reason: str
    bundles: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    full: bool = False


def domain(name: str, reason: str, bundles: tuple[str, ...], tests: tuple[str, ...] = ()) -> Area:
    return Area(name=name, reason=reason, bundles=bundles, tests=tests)


# Shared infrastructure: imported by most domains, so a change selects the complete suite.
INFRASTRUCTURE = {
    "accounts": "User, roles, capabilities, and policy are used by every domain.",
    "authentication": "Session authentication and step-up guard every API.",
    "audit": "The audit trail is written by nearly every service.",
    "common": "Shared helpers (institutional time, ordering, errors, idempotency).",
    "api": "The API router aggregates every domain.",
    "confidential_data": "The encryption primitive behind every encrypted domain.",
    "notifications": "Notification intents are created by most workflows.",
    "organization": "Organization scope decides access in every operational domain.",
}

# Domain apps. Bundles come from the domain's own tests plus the domains that import it
# (``compass.<app>`` reverse imports) and the cross-domain test files that exercise it.
DOMAINS: dict[str, Area] = {
    "account_management": domain(
        "account_management",
        "Account administration also blocks role changes on scheduled work.",
        ("identity-access", "organization"),
        ("test_appointments.py",),
    ),
    "activity": domain(
        "activity",
        "Activity history is read by privacy governance, platform ops, and profiles.",
        ("activity-audit", "privacy-governance", "platform-ops"),
        ("test_password_access.py", "test_profiles.py"),
    ),
    "announcements": domain(
        "announcements",
        "Announcements are publications listed with the other content collections.",
        ("content", "cross-domain-lists"),
    ),
    "appointments": domain(
        "appointments",
        "Counseling, Routine Interviews, E-Counseling, Messages, services and accounts build on "
        "bookings.",
        (
            "scheduling",
            "service-catalog",
            "counseling",
            "routine-interviews",
            "ecounseling",
            "guidance-messages",
            "cross-domain-api",
            "cross-domain-lists",
        ),
        ("test_account_management.py", "test_inventory.py", "test_call_slips.py"),
    ),
    "availability": domain(
        "availability",
        "Availability decides bookable slots for appointments and qualified providers.",
        ("scheduling", "service-catalog", "cross-domain-api"),
        ("test_account_management.py", "test_inventory.py", "test_record_retrieval.py"),
    ),
    "call_slips": domain(
        "call_slips",
        "Call Slips are issued from Referrals and read by Counseling context and lists.",
        ("referrals-call-slips", "counseling", "documents", "cross-domain-api", "cross-domain-lists"),
        ("test_exit_interviews.py", "test_institutional_forms.py", "test_profiles.py"),
    ),
    "counseling": domain(
        "counseling",
        "Encounters link Appointments, Routine Interviews, feedback, and Referral context.",
        (
            "counseling",
            "routine-interviews",
            "scheduling",
            "ecounseling",
            "feedback",
            "referrals-call-slips",
            "service-catalog",
            "cross-domain-api",
            "cross-domain-lists",
        ),
        ("test_exit_interviews.py",),
    ),
    "demo_seed": domain(
        "demo_seed",
        "The demo seeders and the tests that reuse their dataset.",
        ("demo-seed",),
        (
            "test_exit_interview_opportunities.py",
            "test_feedback_confidential_content_encryption.py",
            "test_graduate_tracer_confidential_content_encryption.py",
        ),
    ),
    "documents": domain(
        "documents",
        "Rendering is shared by every controlled-form PDF.",
        ("documents", "reports"),
    ),
    "ecounseling": domain(
        "ecounseling",
        "Rooms ride on Appointments; media governance feeds retention and disposition.",
        ("ecounseling", "scheduling", "privacy-governance", "service-catalog", "cross-domain-api"),
        ("test_call_slips.py",),
    ),
    "exit_interviews": domain(
        "exit_interviews",
        "Exit Interviews gate graduation Good Moral and shape the session payload.",
        ("exit-interviews", "good-moral", "cross-domain-lists"),
        ("test_authentication.py",),
    ),
    "feedback": domain(
        "feedback",
        "Counseling and Good Moral open feedback opportunities.",
        ("feedback", "counseling", "good-moral", "cross-domain-lists"),
    ),
    "guidance_messages": domain(
        "guidance_messages",
        "Messages depends on workload, Counseling Appointment anchors, encryption and realtime.",
        (
            "guidance-messages",
            "organization",
            "counseling",
            "scheduling",
            "realtime",
            "deployment-runtime",
        ),
    ),
    "good_moral": domain(
        "good_moral",
        "Good Moral depends on Inventory and Exit Interviews and feeds the Overview.",
        ("good-moral", "exit-interviews", "feedback", "documents", "cross-domain-lists"),
        ("test_final_api_lifecycle_completion.py",),
    ),
    "graduate_tracer": domain(
        "graduate_tracer",
        "Tracer responses feed reports, exports, and retention disposition.",
        ("graduate-tracer", "reports", "privacy-governance"),
    ),
    "institutional_forms": domain(
        "institutional_forms",
        "Form Revisions are snapshotted by Inventory, Referrals, Call Slips, Feedback, Good Moral.",
        (
            "institutional-forms",
            "inventory",
            "referrals-call-slips",
            "feedback",
            "good-moral",
            "routine-interviews",
            "exit-interviews",
            "student-support",
            "cross-domain-lists",
        ),
        ("test_profiles.py", "test_student_profiling_reports.py"),
    ),
    "inventory": domain(
        "inventory",
        "The Inventory is a prerequisite or source for Appointments, Counseling, Routine "
        "Interviews, Exit Interviews, Good Moral, Student Support, and reports.",
        (
            "inventory",
            "inventory-encryption",
            "student-support",
            "reports",
            "routine-interviews",
            "counseling",
            "exit-interviews",
            "good-moral",
            "institutional-forms",
            "cross-domain-lists",
        ),
        ("test_appointments.py", "test_profiles.py"),
    ),
    "overview": domain(
        "overview",
        "The Overview reads appointments, cases, Good Moral, and platform state.",
        ("cross-domain-lists",),
        ("test_platform_operations.py",),
    ),
    "platform_ops": domain(
        "platform_ops",
        "Platform operations, maintenance, and email operations.",
        ("platform-ops", "notifications", "cross-domain-lists"),
    ),
    "privacy_governance": domain(
        "privacy_governance",
        "Release audit guards every PDF; retention disposes Tracer and E-Counseling media.",
        (
            "privacy-governance",
            "activity-audit",
            "ecounseling",
            "graduate-tracer",
            "documents",
            "exit-interviews",
        ),
        ("test_step_up_policy.py",),
    ),
    "realtime": domain(
        "realtime",
        "Ticket issuance and the revocation hook every AuthSession revocation calls.",
        ("realtime", "identity-access"),
    ),
    "reference_data": domain(
        "reference_data",
        "PSGC reference data used by Inventory locations.",
        ("reference-data",),
        ("test_inventory_frontend_readiness.py",),
    ),
    "referrals": domain(
        "referrals",
        "Referrals create Call Slips and appear in Counseling context.",
        ("referrals-call-slips", "counseling", "documents", "cross-domain-api", "cross-domain-lists"),
        ("test_exit_interviews.py", "test_institutional_forms.py", "test_profiles.py"),
    ),
    "reports": domain(
        "reports",
        "Reports read Inventory, Student Support, and Graduate Tracer data.",
        ("reports", "graduate-tracer", "inventory-encryption", "privacy-governance"),
        ("test_inventory_counselor_review.py",),
    ),
    "resources": domain(
        "resources",
        "Resources are publications listed with the other content collections.",
        ("content", "cross-domain-lists"),
        ("test_final_api_ergonomics.py",),
    ),
    "routine_interviews": domain(
        "routine_interviews",
        "Routine Interviews link Appointments, Encounters, and the Inventory.",
        (
            "routine-interviews",
            "counseling",
            "scheduling",
            "ecounseling",
            "inventory-encryption",
            "cross-domain-api",
            "cross-domain-lists",
        ),
        ("test_exit_interviews.py", "test_institutional_forms.py", "test_service_provider_qualification.py"),
    ),
    "service_catalog": domain(
        "service_catalog",
        "Services gate booking, Counseling, Routine Interviews, E-Counseling, and Messages.",
        (
            "service-catalog",
            "scheduling",
            "counseling",
            "routine-interviews",
            "ecounseling",
            "guidance-messages",
            "inventory",
        ),
        ("test_account_management.py", "test_exit_interviews.py", "test_overview.py"),
    ),
    "student_support": domain(
        "student_support",
        "Student Support is derived from the Inventory and read by reports and Counseling.",
        ("student-support", "inventory", "inventory-encryption", "reports"),
        ("test_counseling_context.py",),
    ),
}

# compass/integrations is split by client: each client is used by different domains.
INTEGRATIONS: dict[str, Area] = {
    "daily.py": domain("integrations:daily", "Daily.co client for E-Counseling.", ("ecounseling",)),
    "mail.py": domain("integrations:mail", "Outbound email transport.", ("notifications", "platform-ops")),
    "media_download.py": domain(
        "integrations:media_download", "E-Counseling media download.", ("ecounseling", "privacy-governance")
    ),
    "psgc.py": domain(
        "integrations:psgc", "PSGC client for Inventory locations.", ("reference-data", "inventory")
    ),
    "sensitive_storage.py": domain(
        "integrations:sensitive_storage", "Private media storage.", ("ecounseling", "privacy-governance")
    ),
    "storage.py": domain(
        "integrations:storage",
        "Object storage for Resources, profile photos, and media.",
        ("content", "ecounseling"),
        ("test_profile_photos.py", "test_sensitive_media_storage.py"),
    ),
    "turnstile.py": domain("integrations:turnstile", "Turnstile bot challenge.", ("identity-access",)),
}

# The standalone realtime service shares only its wire protocol with Django (ADR-100).
REALTIME_SERVICE = domain(
    "realtime_service",
    "The Django-free realtime WebSocket service and its shared wire protocol.",
    ("realtime", "deployment-runtime"),
)

TOP_LEVEL_MODULES: dict[str, Area] = {
    "be/compass/publications.py": domain(
        "publications", "Publication audiences for Announcements and Resources.", ("content",)
    ),
    "be/compass/operational_students.py": domain(
        "operational_students",
        "Student pickers used by Referrals, Call Slips, and Exit Interview opportunities.",
        ("referrals-call-slips", "exit-interviews", "organization"),
    ),
}

FULL_PATHS = {
    "be/pyproject.toml": "Dependency or tool configuration changed.",
    "be/uv.lock": "Locked dependencies changed.",
    "be/.python-version": "The Python version changed.",
    "be/manage.py": "The Django entry point changed.",
    "be/compass/__init__.py": "The application package changed.",
    "be/compass/tasks.py": "The Celery task registry imports every domain.",
    "be/tests/conftest.py": "Test configuration applies to every test.",
    "be/tests/settings.py": "Test settings apply to every test.",
    "be/tests/__init__.py": "The test package changed.",
}

DEPLOYMENT_PREFIXES = (
    "be/deploy/",
    "be/compose.yaml",
    "be/compose.staging.yaml",
    "be/Caddyfile",
    "be/Containerfile",
    "be/.dockerignore",
    "be/.env.example",
)
DOC_PREFIXES = ("be/docs/", "be/README.md")
CI_PATHS = (
    ".github/scripts/",
    ".github/workflows/backend-targeted.yml",
    ".github/workflows/backend-full.yml",
    ".github/workflows/deploy-staging.yml",
)


def full(name: str, reason: str) -> Area:
    return Area(name=name, reason=reason, full=True)


def classify(path: str) -> Area | None:
    """Map one changed repository path to an area; ``None`` means it does not affect backend CI."""

    if path.startswith(CI_PATHS):
        return domain("ci", "CI selection and sharding code; its self-tests run in prepare.", ())
    if path.startswith("contracts/"):
        return domain("contract", "The committed API contract; checked against the generator.", ())
    if not path.startswith("be/"):
        return None
    if "/migrations/" in path:
        return full("migrations", "Migrations change the schema every test builds.")
    if path in FULL_PATHS:
        return full(path, FULL_PATHS[path])
    if path.startswith("be/config/"):
        return full("settings", "Django settings, URLs, ASGI/WSGI, or Celery configuration.")
    if path.startswith(DEPLOYMENT_PREFIXES):
        return domain("deployment", "Deployment and runtime configuration.", ("deployment-runtime",))
    if path.startswith(DOC_PREFIXES) or (path.startswith("be/") and path.endswith(".md")):
        return domain("docs", "Documentation only.", ())
    if path in TOP_LEVEL_MODULES:
        return TOP_LEVEL_MODULES[path]
    if path.startswith("be/realtime_service/"):
        return REALTIME_SERVICE
    if path.startswith("be/tests/"):
        return classify_test_path(path)
    parts = path.split("/")
    if len(parts) >= 4 and parts[1] == "compass":
        app = parts[2]
        if app in INFRASTRUCTURE:
            return full(f"infrastructure:{app}", INFRASTRUCTURE[app])
        if app == "integrations":
            return INTEGRATIONS.get(parts[3]) or full(
                f"integrations:{parts[3]}", "An unrecognized integration client changed."
            )
        if app in DOMAINS:
            return DOMAINS[app]
    return full(path, "This backend path is not mapped, so the complete suite runs.")


def classify_test_path(path: str) -> Area:
    name = path.removeprefix("be/tests/")
    if "/" in name or not name.endswith(".py"):
        return full(path, "Test data or packages outside the mapped test modules changed.")
    module = name.removesuffix(".py")
    importers = tuple(sorted(test_importers(module)))
    if name.startswith("test_"):
        return domain(f"tests:{module}", "A test module changed; it and its importers run.", (), (name, *importers))
    if not importers:
        return full(path, "A test helper with no importing test module changed.")
    return domain(f"tests:{module}", "A test helper changed; the test modules importing it run.", (), importers)


def _imported_test_modules(file: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            if node.module == "tests":
                names.extend(f"tests.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        modules.update(name.split(".")[1] for name in names if name.startswith("tests."))
    return modules


def test_importers(module: str) -> set[str]:
    """Test files that import ``tests.<module>``, directly or through other test modules."""

    imports = {file.stem: _imported_test_modules(file) for file in TESTS.glob("*.py")}
    found: set[str] = set()
    pending = [module]
    while pending:
        current = pending.pop()
        for importer, modules in imports.items():
            if current in modules and importer not in found and importer != module:
                found.add(importer)
                pending.append(importer)
    return {f"{name}.py" for name in found if name.startswith("test_")}


def all_test_files() -> list[str]:
    return sorted(path.name for path in TESTS.glob("test_*.py"))


# --------------------------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------------------------


@dataclass
class Selection:
    full: bool
    files: list[str]
    areas: dict[str, list[str]] = field(default_factory=dict)
    bundles: list[str] = field(default_factory=list)
    full_reasons: list[str] = field(default_factory=list)
    area_tests: dict[str, list[str]] = field(default_factory=dict)


def changed_paths(base: str, head: str) -> list[str]:
    merge_base = subprocess.run(
        ["git", "merge-base", base, head], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    output = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{merge_base}..{head}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted({line.strip() for line in output.splitlines() if line.strip()})


def select(paths: list[str]) -> Selection:
    existing = set(all_test_files())
    areas: dict[str, list[str]] = defaultdict(list)
    area_tests: dict[str, list[str]] = {}
    bundles = {"safety"}
    files: set[str] = set(BUNDLES["safety"][1])
    full_reasons: list[str] = []
    for path in paths:
        area = classify(path)
        if area is None:
            continue
        areas[area.name].append(path)
        if area.full:
            full_reasons.append(f"{path}: {area.reason}")
            continue
        bundles.update(area.bundles)
        for bundle in area.bundles:
            files.update(BUNDLES[bundle][1])
        files.update(area.tests)
        if area.tests:
            area_tests[area.name] = sorted(area.tests)
    if full_reasons:
        return Selection(True, sorted(existing), dict(areas), ["complete-suite"], full_reasons)
    # Deleted test files cannot run; everything selected must exist at the head revision.
    return Selection(False, sorted(files & existing), dict(areas), sorted(bundles), [], area_tests)


def describe(selection: Selection, weights: dict[str, float]) -> str:
    lines = ["Changed backend areas:"]
    for name, paths in sorted(selection.areas.items()):
        lines.append(f"  {name}")
        lines.extend(f"    - {path}" for path in paths)
    if not selection.areas:
        lines.append("  (none: only the always-run safety bundle applies)")
    if selection.full:
        lines.append("")
        lines.append("Complete backend suite selected because:")
        lines.extend(f"  - {reason}" for reason in selection.full_reasons)
    else:
        lines.append("")
        lines.append("Selected test bundles:")
        for name in selection.bundles:
            lines.append(f"  {name}: {BUNDLES[name][0]}")
        for name, tests in sorted(selection.area_tests.items()):
            lines.append(f"  {name} also selects: {', '.join(tests)}")
    total = sum(weights.get(name, DEFAULT_TEST_SECONDS) for name in selection.files)
    lines.append("")
    lines.append(f"Pytest files selected ({len(selection.files)}, about {total / 60:.0f} min serial):")
    lines.extend(f"  tests/{name}" for name in selection.files)
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------
# Sharding
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Item:
    """One schedulable unit: a whole test file, or one round-robin part of a split file."""

    file: str
    part: int = 0
    parts: int = 1

    @property
    def label(self) -> str:
        return self.file if self.parts == 1 else f"{self.file} (part {self.part + 1}/{self.parts})"


def load_weights() -> dict[str, float]:
    if not DURATIONS_FILE.exists():
        return {}
    return {name: float(seconds) for name, seconds in json.loads(DURATIONS_FILE.read_text()).items()}


def items_for(files: list[str]) -> list[Item]:
    items: list[Item] = []
    for name in files:
        parts = SPLIT_FILES.get(name, 1)
        items.extend(Item(name, part, parts) for part in range(parts))
    return items


def plan(files: list[str], shards: int, weights: dict[str, float]) -> list[list[Item]]:
    """Longest-processing-time-first assignment; deterministic for identical inputs."""

    def weight(item: Item) -> float:
        return max(weights.get(item.file, DEFAULT_TEST_SECONDS), 1.0) / item.parts

    buckets: list[list[Item]] = [[] for _ in range(shards)]
    loads = [0.0] * shards
    for item in sorted(items_for(files), key=lambda item: (-weight(item), item)):
        index = min(range(shards), key=lambda i: (loads[i], i))
        buckets[index].append(item)
        loads[index] += weight(item)
    return buckets


def shard_count_for(files: list[str], weights: dict[str, float]) -> int:
    total = sum(max(weights.get(name, DEFAULT_TEST_SECONDS), 1.0) for name in files)
    return max(1, min(TARGETED_MAX_SHARDS, math.ceil(total / TARGETED_SHARD_SECONDS)))


def describe_plan(buckets: list[list[Item]], weights: dict[str, float]) -> str:
    lines = []
    for index, bucket in enumerate(buckets):
        load = sum(max(weights.get(i.file, DEFAULT_TEST_SECONDS), 1.0) / i.parts for i in bucket)
        lines.append(f"Shard {index + 1}/{len(buckets)}: {len(bucket)} items, about {load / 60:.1f} min")
        lines.extend(f"  {item.label}" for item in sorted(bucket))
    return "\n".join(lines)


def shard_matrix(shards: int) -> dict[str, list[dict[str, object]]]:
    """A GitHub Actions matrix with zero-based indexes and human labels such as "2/6"."""

    return {"include": [{"index": i, "label": f"{i + 1}/{shards}"} for i in range(shards)]}


def collect_node_ids(file: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", f"tests/{file}"],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )
    node_ids = [line.strip() for line in result.stdout.splitlines() if "::" in line]
    if not node_ids:
        raise SystemExit(f"No tests collected from tests/{file}; refusing to run an empty part.")
    return node_ids


def pytest_targets(bucket: list[Item]) -> list[str]:
    targets: list[str] = []
    split: dict[str, set[int]] = defaultdict(set)
    for item in sorted(bucket):
        if item.parts == 1:
            targets.append(f"tests/{item.file}")
        else:
            split[item.file].add(item.part)
    for file, parts in sorted(split.items()):
        count = SPLIT_FILES[file]
        node_ids = collect_node_ids(file)
        selected = [node for index, node in enumerate(node_ids) if index % count in parts]
        print(f"tests/{file}: running parts {sorted(p + 1 for p in parts)}/{count} "
              f"({len(selected)} of {len(node_ids)} tests)")
        targets.extend(selected)
    return targets


# --------------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------------


def verify() -> list[str]:
    problems: list[str] = []
    tests = set(all_test_files())
    bundled = {name for _, files in BUNDLES.values() for name in files}
    for name in sorted(tests - bundled):
        problems.append(f"tests/{name} is in no CI bundle; add it to BUNDLES in {Path(__file__).name}.")
    for bundle, (_, files) in sorted(BUNDLES.items()):
        for name in files:
            if name not in tests:
                problems.append(f"Bundle {bundle!r} names missing test file tests/{name}.")
    for area in [*DOMAINS.values(), *INTEGRATIONS.values(), *TOP_LEVEL_MODULES.values()]:
        for bundle in area.bundles:
            if bundle not in BUNDLES:
                problems.append(f"Area {area.name!r} names unknown bundle {bundle!r}.")
        for name in area.tests:
            if name not in tests:
                problems.append(f"Area {area.name!r} names missing test file tests/{name}.")
    apps = {path.name for path in (BACKEND / "compass").iterdir() if path.is_dir() and not path.name.startswith("__")}
    for app in sorted(apps - set(DOMAINS) - set(INFRASTRUCTURE) - {"integrations"}):
        problems.append(f"compass/{app} has no CI mapping; it would always select the complete suite.")
    for name in SPLIT_FILES:
        if name not in tests:
            problems.append(f"SPLIT_FILES names missing test file tests/{name}.")
    # The full regression must run every test file, every part exactly once.
    seen: dict[str, list[int]] = defaultdict(list)
    for bucket in plan(sorted(tests), FULL_SHARDS, load_weights()):
        for item in bucket:
            seen[item.file].append(item.part)
    for name in sorted(tests):
        expected = list(range(SPLIT_FILES.get(name, 1)))
        if sorted(seen.get(name, [])) != expected:
            problems.append(f"tests/{name} is not covered exactly once by the full-regression shards.")
    return problems


# --------------------------------------------------------------------------------------------
# Durations
# --------------------------------------------------------------------------------------------


def durations_from_junit(paths: list[Path]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            classname = case.get("classname", "")
            pieces = classname.split(".")
            if len(pieces) >= 2 and pieces[0] == "tests":
                totals[f"{pieces[1]}.py"] += float(case.get("time") or 0)
    return {name: round(seconds, 1) for name, seconds in sorted(totals.items())}


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def write_output(name: str, value: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_select = sub.add_parser("select", help="Select tests for the changes between two revisions.")
    p_select.add_argument("--base", required=True, help="Base revision; the merge base with --head is used.")
    p_select.add_argument("--head", required=True, help="Head revision being validated.")
    p_select.add_argument("--paths", nargs="*", help="Use these changed paths instead of git (for testing).")

    p_plan = sub.add_parser("plan", help="Show the shard plan for the full suite or given files.")
    p_plan.add_argument("--shards", type=int, default=FULL_SHARDS)
    p_plan.add_argument("--files-json", help="JSON list of test file names; default: every test file.")

    p_run = sub.add_parser("run-shard", help="Run one shard with pytest (inside the backend virtualenv).")
    p_run.add_argument("--index", type=int, required=True, help="Zero-based shard index.")
    p_run.add_argument("--total", type=int, required=True)
    p_run.add_argument("--files-json", help="JSON list of test file names; default: every test file.")
    p_run.add_argument("--junitxml", help="Write a JUnit XML report here.")

    sub.add_parser("verify", help="Check bundle and full-regression shard coverage.")

    p_durations = sub.add_parser("durations", help="Rebuild durations from JUnit XML reports.")
    p_durations.add_argument("reports", nargs="+", type=Path)
    p_durations.add_argument("--write", action="store_true", help=f"Update {DURATIONS_FILE.name}.")

    args = parser.parse_args(argv)
    weights = load_weights()

    if args.command == "select":
        paths = args.paths if args.paths is not None else changed_paths(args.base, args.head)
        selection = select(paths)
        print(describe(selection, weights))
        shards = FULL_SHARDS if selection.full else shard_count_for(selection.files, weights)
        write_output("full", "true" if selection.full else "false")
        write_output("files", json.dumps(selection.files, separators=(",", ":")))
        write_output("shard_count", str(shards))
        write_output("matrix", json.dumps(shard_matrix(shards), separators=(",", ":")))
        print()
        print(describe_plan(plan(selection.files, shards, weights), weights))
        return 0

    if args.command == "plan":
        files = json.loads(args.files_json) if args.files_json else all_test_files()
        print(describe_plan(plan(files, args.shards, weights), weights))
        write_output("shard_count", str(args.shards))
        write_output("matrix", json.dumps(shard_matrix(args.shards), separators=(",", ":")))
        return 0

    if args.command == "run-shard":
        files = json.loads(args.files_json) if args.files_json else all_test_files()
        if not 0 <= args.index < args.total:
            raise SystemExit("--index must be within --total")
        bucket = plan(files, args.total, weights)[args.index]
        print(describe_plan([bucket], weights).replace("Shard 1/1", f"Shard {args.index + 1}/{args.total}"))
        if not bucket:
            print("This shard has no tests assigned.")
            return 0
        command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"]
        if args.junitxml:
            command.append(f"--junitxml={args.junitxml}")
        command.extend(pytest_targets(bucket))
        sys.stdout.flush()
        return subprocess.run(command, cwd=BACKEND).returncode

    if args.command == "verify":
        problems = verify()
        for problem in problems:
            print(f"error: {problem}")
        if not problems:
            tests = all_test_files()
            print(f"OK: {len(tests)} test files are bundled and each runs exactly once across "
                  f"{FULL_SHARDS} full-regression shards.")
        return 1 if problems else 0

    if args.command == "durations":
        measured = durations_from_junit(args.reports)
        print(json.dumps(measured, indent=1))
        if args.write:
            DURATIONS_FILE.write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
