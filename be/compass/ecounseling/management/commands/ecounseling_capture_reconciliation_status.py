"""Read-only operator evidence; protected by existing backend command execution authority."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Case, Count, When

from compass.ecounseling.models import (
    CaptureReconciliationOutcome as Outcome,
)
from compass.ecounseling.models import (
    DailyWebhookReceipt,
    ECounselingMediaCapture,
    MediaCaptureKind,
    MediaCaptureStatus,
    WebhookOutcome,
)
from compass.ecounseling.models import (
    ECounselingCaptureReconciliation as Recovery,
)


class Command(BaseCommand):
    help = "Read bounded capture-reconciliation evidence without provider I/O or private media."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("limit must be between 1 and 100")
        try:
            totals = list(Recovery.objects.values("state").annotate(count=Count("capture_id")))
            escalations = list(
                Recovery.objects.filter(state="ESCALATED")
                .order_by(
                    Case(When(escalation_code=Outcome.PRIVACY, then=0), default=1),
                    "escalated_at",
                    "capture_id",
                )
                .values(
                    "capture_id",
                    "capture__kind",
                    "capture__status",
                    "attempts",
                    "outcome_code",
                    "provider_evidence",
                    "provider_failure_code",
                    "escalation_code",
                    "escalated_at",
                    "last_checked_at",
                )[:limit]
            )
            for row in escalations:
                row["capture__kind"] = (
                    row["capture__kind"]
                    if row["capture__kind"] in MediaCaptureKind.values
                    else "UNKNOWN"
                )
                row["capture__status"] = (
                    row["capture__status"]
                    if row["capture__status"] in MediaCaptureStatus.values
                    else "UNKNOWN"
                )
            anomalies = list(
                DailyWebhookReceipt.objects.filter(operator_review_required=True)
                .select_related("capture", "ecounseling_room")
                .order_by(Case(When(severity="PRIVACY", then=0), default=1), "received_at", "pk")[
                    :limit
                ]
            )
            webhook_rows = []
            for row in anomalies:
                completed = bool(
                    row.identity_verified
                    and not row.event_id_conflict
                    and row.capture_id
                    and row.capture.status == "READY"
                    and row.capture.provider_binding_verified_at is not None
                    and not row.capture.provider_binding_quarantined_at
                )
                webhook_rows.append(
                    {
                        "receipt_id": str(row.pk),
                        "capture_id": str(row.capture_id) if row.capture_id else None,
                        "outcome": row.processing_outcome,
                        "anomaly": row.anomaly_code,
                        "severity": row.severity,
                        "attempts": row.processing_attempts,
                        "duplicate_count": row.duplicate_count,
                        "identity_verified": row.identity_verified,
                        "mitigation_state": row.mitigation_state,
                        "mitigation_failure_code": row.mitigation_failure_code,
                        "terminal_evidence_confirmed": completed,
                        "physical_cutoff_verified": False,
                        "current_review_required": not completed,
                        "historical_escalation": completed,
                        "activity_evidence": (
                            "START_OBSERVED"
                            if row.event_type.endswith(".started")
                            else "COMPLETION_OBSERVED"
                            if row.event_type.endswith(".ready-to-download")
                            else "UNKNOWN"
                        ),
                        "received_at": row.received_at,
                    }
                )
            result = {
                "counts_by_state": totals,
                "historical_capture_escalations": Recovery.objects.filter(
                    escalated_at__isnull=False
                )
                .exclude(state="ESCALATED")
                .count(),
                "webhook_counts_by_outcome": list(
                    DailyWebhookReceipt.objects.values("processing_outcome").annotate(
                        count=Count("id")
                    )
                ),
                "webhook_anomalies": webhook_rows,
                "pending_webhook_replay": DailyWebhookReceipt.objects.filter(
                    processing_outcome=WebhookOutcome.UNRESOLVED, next_attempt_at__isnull=False
                ).count(),
                "unverified_capture_bindings": ECounselingMediaCapture.objects.filter(
                    provider_artifact_id__isnull=False, provider_binding_verified_at__isnull=True
                ).count(),
                "quarantined_capture_bindings": ECounselingMediaCapture.objects.filter(
                    provider_binding_quarantined_at__isnull=False
                ).count(),
                "escalations": escalations,
                "legacy_transcription_stopped_without_ready_anchor": (
                    ECounselingMediaCapture.objects.filter(
                        kind="TRANSCRIPTION", status="STOPPED", ready_at__isnull=True
                    ).count()
                ),
                "confirmed_completion_without_ready_anchor": Recovery.objects.filter(
                    completion_confirmed_at__isnull=False, capture__ready_at__isnull=True
                ).count(),
            }
        except Exception:
            raise CommandError("Capture reconciliation evidence could not be read.") from None
        self.stdout.write(json.dumps(result, default=str, sort_keys=True))
