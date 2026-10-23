"""Verify identity binding before rewrapping; never alter business timestamps or Audit."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compass.confidential_data import crypto
from compass.counseling import handoff_content as content
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.handoff_models import CounselorHandoffSummary


class Command(BaseCommand):
    help = "Verify/rotate Counselor Handoff ciphertext; requires separately authorized key custody."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        scanned = rotated = failed = 0
        last = None
        while True:
            with transaction.atomic():
                qs = CounselorHandoffSummary.objects.order_by("pk")
                if not dry_run:
                    qs = qs.select_for_update(of=("self",))
                if last is not None:
                    qs = qs.filter(pk__gt=last)
                batch = list(qs[:batch_size])
                for item in batch:
                    scanned += 1
                    try:
                        content.read(item)
                        if not crypto.encrypted_with_primary_key(
                            item.content_ciphertext, keyring=content.keyring()
                        ):
                            replacement = content.reencrypt(item)
                            rotated += 1
                            if not dry_run:
                                CounselorHandoffSummary.objects.filter(pk=item.pk).update(
                                    content_ciphertext=replacement
                                )
                    except ContinuityError:
                        failed += 1
            if not batch:
                break
            last = batch[-1].pk
        self.stdout.write(
            f"Handoff encryption: scanned={scanned}; rewrap={rotated}; "
            f"unreadable={failed}; dry_run={dry_run}"
        )
        if failed:
            raise CommandError("Unreadable Handoff payloads left unchanged.")
