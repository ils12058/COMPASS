"""Verify record-bound Follow-Up envelopes before resumable wrapping-key rotation."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compass.confidential_data.crypto import encrypted_with_primary_key
from compass.guidance_followups.content import _keyring, decrypt_text, rotate_text
from compass.guidance_followups.errors import FollowUpContentUnavailable
from compass.guidance_followups.models import GuidanceFollowUp, GuidanceFollowUpEvent


class Command(BaseCommand):
    help = "Verify and rotate Follow-Up ciphertext only; never changes lifecycle or provenance."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, dry_run, batch_size, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        try:
            keyring = _keyring()
        except FollowUpContentUnavailable:
            raise CommandError(
                "GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS is unavailable or invalid."
            ) from None
        verified = rotated = failed = 0
        for model, fields in [
            (
                GuidanceFollowUp,
                [("description_ciphertext", "description"), ("outcome_ciphertext", "outcome")],
            ),
            (GuidanceFollowUpEvent, [("remarks_ciphertext", "remarks")]),
        ]:
            last_pk = None
            while True:
                with transaction.atomic():
                    rows = model.objects.order_by("pk")
                    if not dry_run:
                        rows = rows.select_for_update(of=("self",))
                    if last_pk is not None:
                        rows = rows.filter(pk__gt=last_pk)
                    batch = list(rows[:batch_size])
                    for row in batch:
                        binding_id = row.pk if model is GuidanceFollowUp else row.followup_id
                        event_id = row.pk if model is GuidanceFollowUpEvent else None
                        changes = {}
                        for field, section in fields:
                            token = getattr(row, field)
                            if token is None:
                                continue
                            try:
                                decrypt_text(binding_id, section, token, event_id=event_id)
                                verified += 1
                                if not encrypted_with_primary_key(token, keyring=keyring):
                                    changes[field] = rotate_text(
                                        binding_id, section, token, event_id=event_id
                                    )
                                    rotated += 1
                            except FollowUpContentUnavailable:
                                failed += 1
                        if changes and not dry_run:
                            model.objects.filter(pk=row.pk).update(**changes)
                if not batch:
                    break
                last_pk = batch[-1].pk
        self.stdout.write(
            f"Verified: {verified}; {'would rotate' if dry_run else 'rotated'}: {rotated}; "
            f"unreadable: {failed}."
        )
        if failed:
            raise CommandError(
                "Some Follow-Up envelopes failed verification and were left unchanged. "
                "Retain all old keys."
            )
