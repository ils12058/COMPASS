"""Read-only, minimized database preflight for the in-app disposition decommission (ADR-114).

Prints aggregate counts only: no Student identity, record content, source, case, rule or
provider identifier, and no recording information. The command never writes. It evaluates the
database-inspectable release gates; broker, worker, provider-cleanup health and deployed-build
checks need the separate operator commands documented in the decommission runbook. A passing
result is necessary but not sufficient for a deployment decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone

from compass.accounts.models import DesignationCapability, RoleCapability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.ecounseling.models import (
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    ECounselingRoom,
)
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.privacy_governance.retention_models import (
    DispositionCase,
    DispositionHold,
    OperationalRetentionRule,
)

BLOCKED_EXIT_CODE = 3
MEDIA_CATEGORIES = ("ECOUNSELING_RECORDING", "ECOUNSELING_TRANSCRIPT")
RETENTION_CAPABILITY_PREFIX = "privacy_governance.retention."
STALE_PROCESSING = timedelta(minutes=15)

NOT_VERIFIED = (
    (
        "G6",
        "Broker-resident compass.privacy_governance.* messages (Redis queue and unacked set).",
    ),
    ("G7", "Running execute_disposition work on any worker (celery inspect active)."),
    ("G8", "E-Counseling custody-transfer cleanup health (worker diagnostics); counts only here."),
    ("G9", "Operator records the printed retention grant/override counts for PR 2 rollback."),
    ("G10", "Deployed backend build identity equals the preflighted SHA (/api/v1/meta)."),
)


@dataclass
class Report:
    rows: list[tuple[str, str, int]] = field(default_factory=list)
    gates: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, item, bucket, count):
        self.rows.append((item, str(bucket), int(count)))

    def grouped(self, item, queryset, *fields):
        for row in queryset.values(*fields).annotate(n=Count("pk")).order_by(*fields):
            self.add(item, ":".join(str(row[name]) for name in fields), row["n"])

    def gate(self, code, passed, description):
        self.gates.append((code, passed, description))

    @property
    def blocked(self):
        return any(not passed for _, passed, _ in self.gates)


def collect(now=None) -> Report:
    now = now or timezone.now()
    report = Report()
    cases = DispositionCase.objects.all()

    report.grouped("rule_status", OperationalRetentionRule.objects.all(), "status")
    active_effective = OperationalRetentionRule.objects.filter(
        status="ACTIVE", effective_on__lte=institution_today(now)
    ).count()
    active = OperationalRetentionRule.objects.filter(status="ACTIVE").count()
    report.add("rule_active", "-", active)
    report.add("rule_active_effective", "-", active_effective)

    report.grouped("case_state", cases, "state")
    report.grouped("case_category_contract", cases, "category", "contract_version")
    report.grouped(
        "case_unresolved_blocker",
        cases.filter(state__in=("FAILED", "RECONCILIATION_REQUIRED")),
        "state",
        "blocker",
    )
    processing = cases.filter(state="PROCESSING").count()
    stale = cases.filter(state="PROCESSING", started_at__lt=now - STALE_PROCESSING).count()
    pending = cases.filter(state__in=("APPROVED", "QUEUED")).count()
    unresolved = cases.filter(state__in=("FAILED", "RECONCILIATION_REQUIRED")).count()
    report.add("case_processing", "-", processing)
    report.add("case_stale_processing_gt_15m", "-", stale)
    report.add("case_approved_or_queued", "-", pending)
    report.add("case_unresolved", "-", unresolved)

    report.add("hold_active", "-", DispositionHold.objects.filter(released_at__isnull=True).count())
    report.add("hold_total", "-", DispositionHold.objects.count())

    completed_media = cases.filter(state="COMPLETED", category__in=MEDIA_CATEGORIES)
    media_mismatch = completed_media.filter(
        source_id__in=ECounselingMediaCapture.objects.filter(
            artifact_disposed_at__isnull=True
        ).values("pk")
    ).count()
    tracer_mismatch = cases.filter(
        state="COMPLETED",
        category="GRADUATE_TRACER",
        source_id__in=GraduateTracerResponse.objects.values("pk"),
    ).count()
    report.add("completed_media_without_disposed_marker", "-", media_mismatch)
    report.add("completed_tracer_source_still_present", "-", tracer_mismatch)

    report.add(
        "gt_anonymized_rows",
        "-",
        GraduateTracerResponse.objects.filter(anonymized_at__isnull=False).count(),
    )
    report.add("gt_disposed_markers", "-", GraduateTracerDisposedParticipation.objects.count())
    report.add(
        "ec_capture_artifact_disposed",
        "-",
        ECounselingMediaCapture.objects.filter(artifact_disposed_at__isnull=False).count(),
    )
    report.grouped(
        "ec_capture_ready_with_provider_ref",
        ECounselingMediaCapture.objects.filter(status="READY", provider_artifact_id__isnull=False),
        "kind",
    )
    report.grouped("ec_artifact_status", ECounselingMediaArtifact.objects.all(), "status")
    report.add(
        "ec_artifact_provider_cleanup_pending",
        "-",
        ECounselingMediaArtifact.objects.filter(
            status="STORED", provider_deleted_at__isnull=True
        ).count(),
    )
    report.grouped("ec_room_media_policy", ECounselingRoom.objects.all(), "media_policy_version")

    report.grouped(
        "retention_capability_override",
        UserCapabilityOverride.objects.filter(
            capability__code__startswith=RETENTION_CAPABILITY_PREFIX
        ),
        "capability__code",
        "effect",
    )
    report.grouped(
        "retention_designation_grant",
        DesignationCapability.objects.filter(
            capability__code__startswith=RETENTION_CAPABILITY_PREFIX
        ),
        "designation__code",
        "capability__code",
    )
    report.grouped(
        "retention_role_grant",
        RoleCapability.objects.filter(capability__code__startswith=RETENTION_CAPABILITY_PREFIX),
        "role__code",
        "capability__code",
    )
    report.grouped(
        "retention_audit_action",
        AuditEvent.objects.filter(
            Q(action__startswith="privacy.retention.")
            | Q(action__startswith="privacy.disposition.")
        ),
        "action",
    )

    report.gate("G1", processing == 0, "No disposition is PROCESSING (in-flight, irreversible).")
    report.gate(
        "G2",
        pending == 0,
        "No APPROVED or QUEUED disposition. A prior DPO approval in COMPASS is not institutional "
        "or National Archives disposal authority; pending cases need review by authorized "
        "institutional personnel before any destructive processing.",
    )
    report.gate(
        "G3",
        unresolved == 0,
        "No FAILED or RECONCILIATION_REQUIRED case, unless each is carried under a recorded "
        "owner decision outside this command.",
    )
    report.gate("G4", active == 0, "No ACTIVE retention rule.")
    report.gate(
        "G5",
        media_mismatch == 0 and tracer_mismatch == 0,
        "Completed cases agree with source state (disposed media marked; tracer source absent).",
    )
    return report


class Command(BaseCommand):
    help = (
        "Read-only aggregate status of the retired in-app disposition ledger and its "
        f"database release gates. Exits {BLOCKED_EXIT_CODE} when a gate is blocked."
    )

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        # As the outermost transaction, PostgreSQL itself refuses any write. Inside a caller's
        # transaction (tests), the command still issues only SELECT statements.
        outermost = not connection.in_atomic_block
        with transaction.atomic():
            if outermost and connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
            report = collect()
        if options["format"] == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "scope": "database",
                        "counts": [
                            {"item": item, "bucket": bucket, "count": count}
                            for item, bucket, count in report.rows
                        ],
                        "gates": [
                            {"gate": code, "passed": passed, "description": description}
                            for code, passed, description in report.gates
                        ],
                        "not_verified": [
                            {"gate": code, "description": description}
                            for code, description in NOT_VERIFIED
                        ],
                        "blocked": report.blocked,
                        "certifies_deployment": False,
                    },
                    sort_keys=True,
                )
            )
        else:
            self._text(report)
        if report.blocked:
            raise CommandError(
                "A database release gate is blocked. Do not deploy the disposition decommission "
                "until the blocked gates are resolved by authorized personnel.",
                returncode=BLOCKED_EXIT_CODE,
            )

    def _text(self, report):
        write = self.stdout.write
        write("Retention decommission status (database checks only; read-only, counts only)")
        write("item | bucket | count")
        for item, bucket, count in report.rows:
            write(f"{item} | {bucket} | {count}")
        write("")
        write("Database release gates:")
        for code, passed, description in report.gates:
            write(f"{code} {'PASS' if passed else 'BLOCKED'}: {description}")
        write("")
        write("Not verified by this command (use the runbook's operator commands):")
        for code, description in NOT_VERIFIED:
            write(f"{code}: {description}")
        write("")
        write("A passing result does not by itself certify that deployment is safe.")
