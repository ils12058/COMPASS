"""Explicit bounded resumable rotation; only envelope columns change."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.feedback.confidential_content import (
    FeedbackConfidentialContentUnavailable,
    encrypted_with_primary_key,
    read_feedback_confidential_content,
    reencrypt_feedback_confidential_content,
)

FAMILIES = ("CustomerFeedbackResponse", "ClientSatisfactionResponse")
COLUMN = "confidential_content_ciphertext"
FIELDS = {
    "CustomerFeedbackResponse": {
        "other_service": 255,
        "additional_feedback": 4000,
        "future_service_improvement": 4000,
        "address_snapshot": 2000,
        "mobile_number_snapshot": 64,
    },
    "ClientSatisfactionResponse": {"suggestions": 4000, "email": 320},
}
MAX_LISTED_FAILURES = 20


def _legacy_plaintext_exists():
    with connection.cursor() as cursor:
        for family in FAMILIES:
            model = apps.get_model("feedback", family)
            columns = connection.introspection.get_table_description(cursor, model._meta.db_table)
            if set(FIELDS[family]).intersection(column.name for column in columns):
                return True
    return False


class Command(BaseCommand):
    help = "Verify and rotate feedback envelopes. Resumable; metadata is preserved."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        if _legacy_plaintext_exists():
            raise CommandError("Legacy plaintext columns remain; apply migrations first.")
        failures, failed_total = [], 0
        for family in FAMILIES:
            model = apps.get_model("feedback", family)
            scanned = current = needing_rotation = failed = 0
            last_pk = None
            while True:
                with transaction.atomic():
                    rows = model.objects.order_by("pk")
                    if not dry_run:
                        rows = rows.select_for_update(of=("self",))
                    if last_pk is not None:
                        rows = rows.filter(pk__gt=last_pk)
                    batch = list(rows[:batch_size])
                    for item in batch:
                        try:
                            read_feedback_confidential_content(item)
                        except FeedbackConfidentialContentUnavailable as exc:
                            failed += 1
                            if len(failures) < MAX_LISTED_FAILURES:
                                failures.append(exc)
                            continue
                        if encrypted_with_primary_key(getattr(item, COLUMN)):
                            current += 1
                            continue
                        needing_rotation += 1
                        if not dry_run:
                            model.objects.filter(pk=item.pk).update(
                                **{COLUMN: reencrypt_feedback_confidential_content(item)}
                            )
                if not batch:
                    break
                scanned += len(batch)
                last_pk = batch[-1].pk
            failed_total += failed
            action = "needing rotation" if dry_run else "rotated"
            self.stdout.write(
                f"{family}: scanned {scanned}; current {current}; "
                f"{action} {needing_rotation}; failures {failed}"
            )
        for exc in failures:
            self.stderr.write(f"{exc.family} {exc.object_id} ({exc.reason})")
        if failed_total > len(failures):
            self.stderr.write(f"... and {failed_total - len(failures)} more")
        if failed_total:
            raise CommandError(f"{failed_total} payload(s) could not be verified; left unchanged.")
