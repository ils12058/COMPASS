"""Verify bound Message envelopes and rotate wrapping only (ADR-105)."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compass.confidential_data.crypto import encrypted_with_primary_key, reencrypt_with_primary_key
from compass.guidance_messages.content import encryption_keyring, read_body
from compass.guidance_messages.errors import GuidanceMessageContentUnavailable
from compass.guidance_messages.models import GuidanceMessage

MAX_LISTED_FAILURES = 20


class Command(BaseCommand):
    help = "Verify Guidance Message bodies and rotate old-key tokens; safe to interrupt/resume."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Between 1 and 1000.")
        parser.add_argument("--dry-run", action="store_true", help="Verify/count; write nothing.")

    def handle(self, *args, batch_size, dry_run, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        try:
            keyring = encryption_keyring()
            if not keyring:
                raise GuidanceMessageContentUnavailable()
        except GuidanceMessageContentUnavailable:
            raise CommandError(
                "GUIDANCE_MESSAGE_ENCRYPTION_KEYS is unavailable or invalid."
            ) from None

        scanned = verified = current = rotated = failed = 0
        failures = []
        last_pk = None
        while True:
            with transaction.atomic():
                rows = GuidanceMessage.objects.order_by("pk").only(
                    "pk",
                    "thread_id",
                    "sequence",
                    "sender_id",
                    "body_schema_version",
                    "body_ciphertext",
                )
                if not dry_run:
                    rows = rows.select_for_update(of=("self",))
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                batch = list(rows[:batch_size])
                for message in batch:
                    try:
                        # Validates the stored schema, all four bindings, shape and exact body.
                        read_body(message)
                    except GuidanceMessageContentUnavailable:
                        failed += 1
                        if len(failures) < MAX_LISTED_FAILURES:
                            failures.append((message.pk, message.thread_id))
                        continue
                    verified += 1
                    if encrypted_with_primary_key(message.body_ciphertext, keyring=keyring):
                        current += 1
                        continue
                    rotated += 1
                    if not dry_run:
                        # QuerySet.update leaves every business fact and timestamp alone.
                        GuidanceMessage.objects.filter(pk=message.pk).update(
                            body_ciphertext=reencrypt_with_primary_key(
                                message.body_ciphertext, keyring=keyring
                            )
                        )
            if not batch:
                break
            scanned += len(batch)
            last_pk = batch[-1].pk

        action = "to re-encrypt" if dry_run else "re-encrypted"
        self.stdout.write(
            "Guidance Message encryption" + (" (dry run; nothing written)." if dry_run else ".")
        )
        self.stdout.write(f"Records scanned: {scanned}; payloads verified: {verified}")
        self.stdout.write(
            f"Already under primary key: {current}; {action}: {rotated}; unreadable: {failed}"
        )
        for message_id, thread_id in failures:
            self.stderr.write(
                f"Unreadable: Message {message_id} Thread {thread_id} (invalid_envelope)"
            )
        if failed > len(failures):
            self.stderr.write(f"... and {failed - len(failures)} more")
        if failed:
            raise CommandError(
                f"{failed} Message payload(s) could not be verified; left unchanged."
            )
