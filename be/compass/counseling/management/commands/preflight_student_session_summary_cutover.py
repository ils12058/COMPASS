"""Offline, content-free preflight and explicitly approved disposable-resource cleanup.

This command intentionally uses the historical migration state, never the new content adapter.
No retained-data conversion is provided. Stop all old consumers before approved execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.models import Q

from compass.common.canonical_baseline import pre_canonical_history

BASELINE = "0001_canonical_baseline"
CUTOVER = "0002_student_session_summary_contract"


def historical_models():
    if pre_canonical_history(connection):
        raise CommandError("Pre-canonical database refused.")
    loader = MigrationLoader(connection)
    if ("counseling", BASELINE) not in loader.applied_migrations:
        raise CommandError("Canonical Counseling baseline must already be applied.")
    if ("counseling", CUTOVER) in loader.applied_migrations:
        raise CommandError("Cutover already applied; legacy cleanup is unavailable.")
    state = loader.project_state([("counseling", BASELINE), ("notifications", BASELINE)])
    return tuple(
        state.apps.get_model(app, name)
        for app, name in (
            ("counseling", "CounselingSharedSummary"),
            ("notifications", "Notification"),
            ("notifications", "EmailDelivery"),
            ("notifications", "PushDelivery"),
        )
    )


def collect_plan(models):
    Summary, Notification, EmailDelivery, PushDelivery = models
    summaries = Summary.objects.all()
    notifications = Notification.objects.filter(
        Q(event_code="counseling.shared_summary.published")
        | Q(source_type="counseling_shared_summary")
        | Q(target_type="COUNSELING_SHARED_SUMMARY")
    )
    emails = EmailDelivery.objects.filter(notification_id__in=notifications.values("pk"))
    pushes = PushDelivery.objects.filter(notification_id__in=notifications.values("pk"))
    config = connection.settings_dict
    plan = {
        "format": "cont-1b-disposable-scope-v1",
        "database": {name.lower(): str(config[name]) for name in ("NAME", "HOST", "PORT")},
        "summary_ids": sorted(str(pk) for pk in summaries.values_list("pk", flat=True)),
        "summary_records": list(
            summaries.order_by("pk").values(
                "id", "encounter_id", "published_at", "created_at", "updated_at"
            )
        ),
        "notification_ids": sorted(str(pk) for pk in notifications.values_list("pk", flat=True)),
        "email_delivery_ids": sorted(str(pk) for pk in emails.values_list("pk", flat=True)),
        "push_delivery_ids": sorted(str(pk) for pk in pushes.values_list("pk", flat=True)),
        "email_states": sorted(
            list(emails.values_list("id", "status", "claim_expires_at")),
            key=lambda row: str(row[0]),
        ),
        "push_states": sorted(
            list(pushes.values_list("id", "status", "claim_expires_at")),
            key=lambda row: str(row[0]),
        ),
    }
    # Stable serializable metadata only. No ciphertext, body, recipient address or key access.
    plan = json.loads(json.dumps(plan, default=str))
    plan["scope_digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan, notifications, emails, pushes


class Command(BaseCommand):
    help = (
        "Preflight legacy summary scope; execution requires matching explicit synthetic approval."
    )

    def add_arguments(self, parser):
        parser.add_argument("--plan-file", type=Path, required=True)
        parser.add_argument("--approval-file", type=Path)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        models = historical_models()
        if not options["execute"]:
            plan, *_ = collect_plan(models)
            # Never overwrite an operator's reviewed plan.
            with options["plan_file"].open("x") as output:
                json.dump(plan, output, indent=2)
                output.write("\n")
            self.stdout.write(f"Preflight complete; scope digest: {plan['scope_digest']}")
            return
        if options["approval_file"] is None:
            raise CommandError(
                "Execution requires a reviewed plan and explicit synthetic approval."
            )
        try:
            reviewed = json.loads(options["plan_file"].read_text())
            approval = json.loads(options["approval_file"].read_text())
        except (OSError, ValueError):
            raise CommandError("Plan or approval file is unavailable or invalid.") from None
        if not isinstance(reviewed, dict) or not isinstance(approval, dict):
            raise CommandError("Plan and approval must be JSON objects.")
        if (
            approval.get("disposable_synthetic") is not True
            or approval.get("consumers_stopped") is not True
            or not isinstance(approval.get("approved_by"), str)
            or not approval["approved_by"].strip()
            or approval.get("scope_digest") != reviewed.get("scope_digest")
        ):
            raise CommandError(
                "Verified disposability, stopped consumers and exact scope approval required."
            )
        if connection.vendor != "postgresql":
            raise CommandError("Scoped cleanup requires PostgreSQL transaction fencing.")
        with transaction.atomic():
            with connection.cursor() as cursor:
                for model in models:
                    cursor.execute(
                        f"LOCK TABLE {connection.ops.quote_name(model._meta.db_table)} "
                        "IN SHARE ROW EXCLUSIVE MODE"
                    )
            current, notifications, emails, pushes = collect_plan(models)
            if current != reviewed:
                raise CommandError("Scope changed since preflight; create and approve a new plan.")
            if (
                emails.filter(status="PROCESSING").exists()
                or pushes.filter(status="PROCESSING").exists()
            ):
                raise CommandError("Claimed delivery work remains; drain it before scoped cleanup.")
            # Only explicitly reviewed legacy resource rows; cascades remove dependent deliveries.
            # AuditEvent, Encounters, accounts and unrelated notifications are never selected.
            notifications.delete()
            models[0].objects.all().delete()
        self.stdout.write(
            "Approved legacy synthetic scope removed atomically; run additive migrations next."
        )
