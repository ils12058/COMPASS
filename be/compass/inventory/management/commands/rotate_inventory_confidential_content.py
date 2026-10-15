"""Verify and rewrap all eight Inventory envelopes; preserve business metadata (ADR-083)."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.inventory.confidential_content import (
    FAMILIES,
    FIELDS,
    TARGETS_COLUMN,
    TARGETS_FAMILY,
    InventoryConfidentialContentUnavailable,
    encrypted_with_primary_key,
    read_confidential_content,
    read_reopen_targets,
    reencrypt_confidential_content,
    reencrypt_reopen_targets,
)

MAX_LISTED_FAILURES = 20


def _legacy_plaintext_exists():
    with connection.cursor() as cursor:
        for name, _column, _relation in FAMILIES:
            model = apps.get_model("inventory", name)
            legacy = set(FIELDS[name])
            columns = connection.introspection.get_table_description(cursor, model._meta.db_table)
            if legacy.intersection(column.name for column in columns):
                return True
    return False


class Command(BaseCommand):
    help = "Verify all Inventory envelopes and rewrap previous-key tokens. Resumable."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Between 1 and 1000.")
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        if _legacy_plaintext_exists():
            raise CommandError("Legacy plaintext Inventory columns remain; apply migrations first.")
        failures, failed_total = [], 0
        envelopes = [
            (
                apps.get_model("inventory", name),
                name,
                column,
                read_confidential_content,
                reencrypt_confidential_content,
            )
            for name, column, _relation in FAMILIES
        ]
        # Correction targets share the reopen-event row but are a separate, optional envelope.
        envelopes.append(
            (
                apps.get_model("inventory", "InventoryReopenEvent"),
                TARGETS_FAMILY,
                TARGETS_COLUMN,
                read_reopen_targets,
                reencrypt_reopen_targets,
            )
        )
        for model, label, column, read, reencrypt in envelopes:
            scanned = empty = current = needing_rotation = failed = 0
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
                        if column == TARGETS_COLUMN and not getattr(item, column):
                            empty += 1
                            continue
                        try:
                            read(item)
                        except InventoryConfidentialContentUnavailable as exc:
                            failed += 1
                            if len(failures) < MAX_LISTED_FAILURES:
                                failures.append(exc)
                            continue
                        if encrypted_with_primary_key(getattr(item, column)):
                            current += 1
                            continue
                        needing_rotation += 1
                        if not dry_run:
                            model.objects.filter(pk=item.pk).update(**{column: reencrypt(item)})
                if not batch:
                    break
                scanned += len(batch)
                last_pk = batch[-1].pk
            failed_total += failed
            action = "needing rotation" if dry_run else "rotated"
            empty_note = f"empty {empty}; " if column == TARGETS_COLUMN else ""
            self.stdout.write(
                f"{label}: scanned {scanned}; {empty_note}current {current}; "
                f"{action} {needing_rotation}; failures {failed}"
            )
        for exc in failures:
            self.stderr.write(
                f"Unreadable: Inventory {exc.inventory_id}; "
                f"{exc.family} {exc.object_id} ({exc.reason})"
            )
        if failed_total > len(failures):
            self.stderr.write(f"... and {failed_total - len(failures)} more")
        if failed_total:
            raise CommandError(
                f"{failed_total} Inventory payload(s) could not be verified; left unchanged."
            )
