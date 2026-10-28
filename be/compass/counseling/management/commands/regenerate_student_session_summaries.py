"""Regenerate only explicitly approved, known synthetic summary fixtures after cutover."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.audit.context import AuditContext
from compass.counseling.models import CounselingEncounter, StudentSessionSummary
from compass.counseling.student_session_summaries import publish_assigned_student_session_summary
from compass.counseling.student_session_summary_content import (
    read_student_session_summary_content,
    write_student_session_summary_content,
)
from compass.staging_seed.content import narratives
from compass.staging_seed.guard import ensure_seeding_allowed_by_settings
from compass.staging_seed.manifest import ACCOUNTS
from compass.staging_seed.seed import exclusive_dataset_operation
from compass.staging_seed.staff import COUNSELOR_A, COUNSELOR_B
from compass.staging_seed.students import FOURTH_YEAR, REFERRED, SECOND_YEAR
from compass.staging_seed.support import align_timestamps, settle_notifications


class Command(BaseCommand):
    help = "Regenerate approved synthetic summary scope only; never restore retained content."

    def add_arguments(self, parser):
        parser.add_argument("--plan-file", type=Path, required=True)
        parser.add_argument("--approval-file", type=Path, required=True)

    def handle(self, *args, **options):
        ensure_seeding_allowed_by_settings()
        try:
            plan = json.loads(options["plan_file"].read_text())
            approval = json.loads(options["approval_file"].read_text())
            digest = plan.pop("scope_digest")
            actual = hashlib.sha256(
                json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            database = {
                name.lower(): str(connection.settings_dict[name])
                for name in ("NAME", "HOST", "PORT")
            }
            permitted = (
                digest == actual == approval["scope_digest"]
                and approval["disposable_synthetic"] is True
                and approval["consumers_stopped"] is True
                and approval["regenerate_known_fixtures"] is True
                and bool(approval["approved_by"].strip())
                and plan["database"] == database
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise CommandError(
                "Reviewed synthetic regeneration scope/approval is invalid."
            ) from None
        if not permitted:
            raise CommandError(
                "Exact database, scope and explicit synthetic regeneration approval required."
            )
        action = next(account for account in ACCOUNTS if account.key == "ar_15")
        recipes = {
            (
                SECOND_YEAR.institutional_id,
                COUNSELOR_A.institutional_id,
                "APPOINTMENT",
            ): narratives.ADJUSTMENT_STUDENT_SESSION_SUMMARY,
            (
                REFERRED.institutional_id,
                COUNSELOR_B.institutional_id,
                "APPOINTMENT",
            ): narratives.REFERRED_FOLLOW_UP_SUMMARY,
            (
                FOURTH_YEAR.institutional_id,
                COUNSELOR_A.institutional_id,
                "WALK_IN",
            ): narratives.WALK_IN_SUMMARY_DRAFT,
            (
                action.institutional_id,
                COUNSELOR_B.institutional_id,
                "APPOINTMENT",
            ): narratives.ADJUSTMENT_STUDENT_SESSION_SUMMARY,
        }
        created = 0
        with exclusive_dataset_operation(), transaction.atomic():
            prepared = []
            for record in plan["summary_records"]:
                encounter = (
                    CounselingEncounter.objects.select_for_update()
                    .select_related("student", "counselor")
                    .get(pk=record["encounter_id"])
                )
                body = recipes.get(
                    (
                        encounter.student.institutional_id,
                        encounter.counselor.institutional_id,
                        encounter.entry_mode,
                    )
                )
                if body is None:
                    raise CommandError(
                        "Unknown synthetic fixture; retained content cannot be regenerated."
                    )
                prepared.append((record, encounter, body))
            for record, encounter, body in prepared:
                existing = StudentSessionSummary.objects.filter(encounter=encounter).first()
                if existing is not None:
                    if (
                        str(existing.pk) != record["id"]
                        or read_student_session_summary_content(existing) != body
                        or bool(existing.published_at) != bool(record["published_at"])
                    ):
                        raise CommandError(
                            "Existing summary differs; regeneration never overwrites it."
                        )
                    continue
                # Narrow seed-only reconstruction: preserve reviewed UUID/Encounter/timestamps,
                # but generate new canonical ciphertext from the approved synthetic recipe.
                item = StudentSessionSummary(id=UUID(record["id"]), encounter=encounter)
                write_student_session_summary_content(item, body)
                item.save(force_insert=True)
                if record["published_at"]:
                    publish_assigned_student_session_summary(
                        encounter_id=encounter.pk,
                        counselor=encounter.counselor,
                        context=AuditContext.user(encounter.counselor),
                    )
                    settle_notifications(
                        source_id=item.pk,
                        occurred_at=datetime.fromisoformat(record["published_at"]),
                        event_code="counseling.student_session_summary.published",
                    )
                align_timestamps(
                    item,
                    **{
                        name: datetime.fromisoformat(record[name])
                        for name in ("created_at", "updated_at", "published_at")
                        if record[name]
                    },
                )
                created += 1
        self.stdout.write(
            f"Synthetic Student Session Summaries created: {created}; scope verified."
        )
