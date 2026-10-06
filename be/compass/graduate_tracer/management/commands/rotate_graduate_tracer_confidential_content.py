"""Verify and rewrap all four Graduate Tracer envelopes; preserve business metadata (ADR-084)."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.graduate_tracer.confidential_content import (
    FAMILIES,
    FIELDS,
    GraduateTracerConfidentialContentUnavailable,
    encrypted_with_primary_key,
    read_confidential_content,
    reencrypt_confidential_content,
)

MAX_LISTED_FAILURES = 20


def _legacy_plaintext_exists():
    with connection.cursor() as cursor:
        for name, _column, _relation in FAMILIES:
            model = apps.get_model("graduate_tracer", name)
            legacy = set(FIELDS[name])
            columns = connection.introspection.get_table_description(cursor, model._meta.db_table)
            if legacy.intersection(column.name for column in columns):
                return True
    return False


class Command(BaseCommand):
    help = "Verify all Graduate Tracer envelopes and rewrap previous-key tokens. Resumable."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Between 1 and 1000.")
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        if _legacy_plaintext_exists():
            raise CommandError(
                "Legacy plaintext Graduate Tracer columns remain; apply migrations first."
            )
        from compass.graduate_tracer.models import GraduateTracerResponse

        anonymous = GraduateTracerResponse.objects.filter(
            student__isnull=True, anonymized_at__isnull=False
        )
        if anonymous.exclude(confidential_content_ciphertext__isnull=True).exists():
            raise CommandError("Anonymous Graduate Tracer ciphertext invariant failed.")
        self.stdout.write(f"Anonymous contributions skipped: {anonymous.count()}")
        failures, failed_total = [], 0
        for name, column, _relation in FAMILIES:
            model = apps.get_model("graduate_tracer", name)
            label = name
            scanned = current = needing_rotation = failed = 0
            last_pk = None
            while True:
                with transaction.atomic():
                    rows = model.objects.order_by("pk")
                    if name == "GraduateTracerResponse":
                        rows = rows.filter(student__isnull=False, anonymized_at__isnull=True)
                    elif rows.filter(response__student__isnull=True).exists():
                        raise CommandError("Anonymous Graduate Tracer child invariant failed.")
                    if not dry_run:
                        rows = rows.select_for_update(of=("self",))
                    if last_pk is not None:
                        rows = rows.filter(pk__gt=last_pk)
                    batch = list(rows[:batch_size])
                    for item in batch:
                        try:
                            read_confidential_content(item)
                        except GraduateTracerConfidentialContentUnavailable as exc:
                            failed += 1
                            if len(failures) < MAX_LISTED_FAILURES:
                                failures.append(exc)
                            continue
                        if encrypted_with_primary_key(getattr(item, column)):
                            current += 1
                            continue
                        needing_rotation += 1
                        if not dry_run:
                            model.objects.filter(pk=item.pk).update(
                                **{column: reencrypt_confidential_content(item)}
                            )
                if not batch:
                    break
                scanned += len(batch)
                last_pk = batch[-1].pk
            failed_total += failed
            action = "needing rotation" if dry_run else "rotated"
            self.stdout.write(
                f"{label}: scanned {scanned}; current {current}; "
                f"{action} {needing_rotation}; failures {failed}"
            )
        for exc in failures:
            self.stderr.write(
                f"Unreadable: Graduate Tracer {exc.response_id}; "
                f"{exc.family} {exc.object_id} ({exc.reason})"
            )
        if failed_total > len(failures):
            self.stderr.write(f"... and {failed_total - len(failures)} more")
        if failed_total:
            raise CommandError(
                f"{failed_total} Graduate Tracer payload(s) could not be verified; left unchanged."
            )
