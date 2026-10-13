"""Read-only operator evidence; protected by existing backend command execution authority."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Case, Count, When

from compass.ecounseling.models import (
    CaptureReconciliationOutcome as Outcome,
)
from compass.ecounseling.models import (
    ECounselingCaptureReconciliation as Recovery,
)
from compass.ecounseling.models import (
    ECounselingMediaCapture,
    MediaCaptureKind,
    MediaCaptureStatus,
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
            result = {
                "counts_by_state": totals,
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
