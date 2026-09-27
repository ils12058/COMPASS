"""Verify Routine Interview ciphertext and re-encrypt it under the primary key (ADR-066)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.routine_interviews.content import (
    CIPHERTEXT_COLUMNS,
    EVALUATION_FIELDS,
    INTAKE_FIELDS,
    read_section,
)
from compass.routine_interviews.crypto import (
    RoutineContentSection,
    encrypted_with_primary_key,
    reencrypt_with_primary_key,
)
from compass.routine_interviews.errors import RoutineContentUnavailable
from compass.routine_interviews.models import RoutineInterview

# Before ADR-066 every content field was a plaintext column of the same name.
LEGACY_PLAINTEXT_COLUMNS = frozenset((*INTAKE_FIELDS, *EVALUATION_FIELDS))
MAX_LISTED_FAILURES = 20
SECTION_LABELS = {
    RoutineContentSection.STUDENT_INTAKE: "Student Intake",
    RoutineContentSection.COUNSELOR_EVALUATION: "Counselor Evaluation",
}


def _legacy_plaintext_columns() -> list[str]:
    with connection.cursor() as cursor:
        described = connection.introspection.get_table_description(
            cursor, RoutineInterview._meta.db_table
        )
    return sorted({column.name for column in described} & LEGACY_PLAINTEXT_COLUMNS)


class Command(BaseCommand):
    help = (
        "Verify every Routine Interview content token against the configured keyring and "
        "re-encrypt tokens that are not yet under its primary key. Safe to interrupt and repeat."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Routine Interviews per transaction, between 1 and 1000.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only verify and count; write nothing.",
        )

    def handle(self, *args, batch_size: int, dry_run: bool, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        legacy = _legacy_plaintext_columns()
        if legacy:
            raise CommandError(
                f"{len(legacy)} legacy plaintext Routine Interview column(s) remain; apply the "
                "routine_interviews migrations first."
            )

        records = already_current = 0
        verified = dict.fromkeys(RoutineContentSection, 0)
        reencrypted = dict.fromkeys(RoutineContentSection, 0)
        failures: list[tuple[str, str, str]] = []
        last_pk = None
        while True:
            with transaction.atomic():
                rows = RoutineInterview.objects.order_by("pk").only(
                    "pk", *CIPHERTEXT_COLUMNS.values()
                )
                if not dry_run:
                    # A concurrent Intake or Evaluation save waits for this batch instead of being
                    # overwritten by a re-encryption of the token it replaced.
                    rows = rows.select_for_update(of=("self",))
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                batch = list(rows[:batch_size])
                for item in batch:
                    updates = {}
                    for section, column in CIPHERTEXT_COLUMNS.items():
                        try:
                            read_section(item, section)
                        except RoutineContentUnavailable as exc:
                            # Unreadable content is reported and left exactly as it is.
                            failures.append((str(item.pk), section.value, exc.reason))
                            continue
                        verified[section] += 1
                        token = getattr(item, column)
                        if encrypted_with_primary_key(token):
                            already_current += 1
                            continue
                        reencrypted[section] += 1
                        if not dry_run:
                            updates[column] = reencrypt_with_primary_key(token)
                    if updates:
                        # QuerySet.update() rewrites only ciphertext: updated_at and the workflow
                        # timestamps are unchanged, and no domain audit event is recorded.
                        RoutineInterview.objects.filter(pk=item.pk).update(**updates)
            if not batch:
                break
            records += len(batch)
            last_pk = batch[-1].pk

        action = "to re-encrypt" if dry_run else "re-encrypted"
        heading = " (dry run; nothing was written)" if dry_run else ""
        self.stdout.write(f"Routine Interview content encryption{heading}.")
        self.stdout.write(f"Records scanned: {records}")
        for section, label in SECTION_LABELS.items():
            self.stdout.write(
                f"{label} payloads verified: {verified[section]}; {action}: {reencrypted[section]}"
            )
        self.stdout.write(f"Payloads already under the primary key: {already_current}")
        self.stdout.write(f"Unreadable payloads: {len(failures)}")
        self.stdout.write("Legacy plaintext columns: none")
        for routine_interview_id, section, reason in failures[:MAX_LISTED_FAILURES]:
            self.stderr.write(
                f"Unreadable: Routine Interview {routine_interview_id} {section} ({reason})"
            )
        if len(failures) > MAX_LISTED_FAILURES:
            self.stderr.write(f"... and {len(failures) - MAX_LISTED_FAILURES} more")
        if failures:
            raise CommandError(
                f"{len(failures)} Routine Interview payload(s) could not be verified with the "
                "configured keyring and were left unchanged."
            )
