"""Verify and rewrap Shared Summary bodies only; preserve all business metadata (ADR-080)."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.counseling.models import CounselingSharedSummary
from compass.counseling.shared_summary_content import (
    CounselingSharedSummaryContentUnavailable,
    encrypted_with_primary_key,
    read_shared_summary_content,
    reencrypt_shared_summary_content,
)

MAX_LISTED_FAILURES = 20


def _legacy_plaintext_exists() -> bool:
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(
            cursor, CounselingSharedSummary._meta.db_table
        )
    return any(column.name == "content" for column in columns)


class Command(BaseCommand):
    help = "Verify Shared Summary bodies and rewrap previous-key tokens. Safe to interrupt/resume."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Between 1 and 1000.")
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")

    def handle(self, *args, batch_size: int, dry_run: bool, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        if _legacy_plaintext_exists():
            raise CommandError(
                "Legacy plaintext Shared Summary column remains; apply migrations first."
            )

        scanned = verified = current = rotated = failed = 0
        failures = []
        last_pk = None
        while True:
            with transaction.atomic():
                rows = CounselingSharedSummary.objects.order_by("pk").only(
                    "pk", "encounter_id", "content_ciphertext"
                )
                if not dry_run:
                    rows = rows.select_for_update(of=("self",))
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                batch = list(rows[:batch_size])
                for item in batch:
                    try:
                        read_shared_summary_content(item)
                    except CounselingSharedSummaryContentUnavailable as exc:
                        failed += 1
                        if len(failures) < MAX_LISTED_FAILURES:
                            failures.append((item.pk, item.encounter_id, exc.reason))
                        continue
                    verified += 1
                    if encrypted_with_primary_key(item.content_ciphertext):
                        current += 1
                        continue
                    rotated += 1
                    if not dry_run:
                        # Never touches auto_now timestamps, publication, Audit or notifications.
                        CounselingSharedSummary.objects.filter(pk=item.pk).update(
                            content_ciphertext=reencrypt_shared_summary_content(item)
                        )
            if not batch:
                break
            scanned += len(batch)
            last_pk = batch[-1].pk

        action = "to re-encrypt" if dry_run else "re-encrypted"
        self.stdout.write(
            "Shared Summary encryption" + (" (dry run; nothing written)." if dry_run else ".")
        )
        self.stdout.write(f"Records scanned: {scanned}; payloads verified: {verified}")
        self.stdout.write(f"Payloads already under the primary key: {current}; {action}: {rotated}")
        self.stdout.write(f"Unreadable payloads: {failed}; legacy plaintext columns: none")
        for summary_id, encounter_id, reason in failures:
            self.stderr.write(
                f"Unreadable: Summary {summary_id} Encounter {encounter_id} ({reason})"
            )
        if failed > len(failures):
            self.stderr.write(f"... and {failed - len(failures)} more")
        if failed:
            raise CommandError(
                f"{failed} Shared Summary payload(s) could not be verified; left unchanged."
            )
