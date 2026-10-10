"""Bounded, resumable rotation without changing provenance or emitting content."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compass.assessment_records.confidential_content import (
    AssessmentRecordConfidentialContentUnavailable,
    encrypted_with_primary_key,
    read_confidential_content,
    reencrypt_confidential_content,
)
from compass.assessment_records.models import StudentAssessmentRecord


class Command(BaseCommand):
    help = "Verify Assessment Record envelopes and rewrap previous-key tokens. Resumable."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        scanned = current = rotated = failed = 0
        failures = []
        last_pk = None
        while True:
            with transaction.atomic():
                rows = StudentAssessmentRecord.objects.order_by("pk")
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                if not dry_run:
                    rows = rows.select_for_update(of=("self",))
                batch = list(rows[:batch_size])
                for item in batch:
                    try:
                        read_confidential_content(item)
                        if encrypted_with_primary_key(item.confidential_content_ciphertext):
                            current += 1
                            continue
                        if not dry_run:
                            StudentAssessmentRecord.objects.filter(pk=item.pk).update(
                                confidential_content_ciphertext=reencrypt_confidential_content(item)
                            )
                        rotated += 1
                    except AssessmentRecordConfidentialContentUnavailable as exc:
                        failed += 1
                        if len(failures) < 20:
                            failures.append((item.pk, exc.reason))
            if not batch:
                break
            scanned += len(batch)
            last_pk = batch[-1].pk
        action = "needing rotation" if dry_run else "rotated"
        self.stdout.write(
            f"Assessment Records: scanned {scanned}; current {current}; "
            f"{action} {rotated}; failures {failed}"
        )
        for pk, reason in failures:
            self.stderr.write(f"Unreadable: Assessment Record {pk} ({reason})")
        if failed > len(failures):
            self.stderr.write(f"... and {failed - len(failures)} more")
        if failed:
            raise CommandError(
                f"{failed} Assessment Record payload(s) could not be verified; left unchanged."
            )
