"""Verify and rewrap both Referral envelopes; preserve source/business metadata (ADR-081)."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from compass.referrals.confidential_content import (
    ReferralConfidentialContentUnavailable,
    encrypted_with_primary_key,
    read_referral_action_remarks,
    read_referral_confidential_content,
    reencrypt_referral_action_remarks,
    reencrypt_referral_content,
)
from compass.referrals.models import Referral, ReferralAction

MAX_LISTED_FAILURES = 20


def _legacy_plaintext_exists():
    with connection.cursor() as cursor:
        for model, legacy in (
            (Referral, {"reason", "referrer_name", "status_note", "void_reason"}),
            (ReferralAction, {"remarks"}),
        ):
            columns = connection.introspection.get_table_description(cursor, model._meta.db_table)
            if legacy.intersection(column.name for column in columns):
                return True
    return False


class Command(BaseCommand):
    help = "Verify Referral content and action remarks; rewrap previous-key tokens. Resumable."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Between 1 and 1000.")
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        if _legacy_plaintext_exists():
            raise CommandError("Legacy plaintext Referral columns remain; apply migrations first.")
        failures, failed_total = [], 0
        for model, label, column, read, rewrap in (
            (
                Referral,
                "Referrals",
                "confidential_content_ciphertext",
                read_referral_confidential_content,
                reencrypt_referral_content,
            ),
            (
                ReferralAction,
                "Actions",
                "remarks_ciphertext",
                read_referral_action_remarks,
                reencrypt_referral_action_remarks,
            ),
        ):
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
                            read(item)
                        except ReferralConfidentialContentUnavailable as exc:
                            failed += 1
                            if len(failures) < MAX_LISTED_FAILURES:
                                failures.append(exc)
                            continue
                        if encrypted_with_primary_key(getattr(item, column)):
                            current += 1
                            continue
                        needing_rotation += 1
                        if not dry_run:
                            model.objects.filter(pk=item.pk).update(**{column: rewrap(item)})
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
            action = (
                f" Action {exc.referral_action_id} {exc.action_type}"
                if exc.referral_action_id
                else ""
            )
            self.stderr.write(f"Unreadable: Referral {exc.referral_id}{action} ({exc.reason})")
        if failed_total > len(failures):
            self.stderr.write(f"... and {failed_total - len(failures)} more")
        if failed_total:
            raise CommandError(
                f"{failed_total} Referral payload(s) could not be verified; left unchanged."
            )
