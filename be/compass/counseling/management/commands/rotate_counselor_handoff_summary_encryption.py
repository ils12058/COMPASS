"""Verify identity binding before rewrapping; never alter business timestamps or Audit."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compass.confidential_data import crypto
from compass.counseling import case_closure_content, case_handoff_content
from compass.counseling import handoff_content as content
from compass.counseling.case_closure_content import ClosureContentUnavailable
from compass.counseling.case_closure_models import CounselingCaseClosure
from compass.counseling.case_continuity_rules import CaseContinuityError
from compass.counseling.case_handoff_models import (
    CounselingCaseHandoff,
    CounselingCaseHandoffAddendum,
)
from compass.counseling.continuity_rules import ContinuityError
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
        # The established command also owns case Handoff custody. Verify each envelope's
        # distinct binding before rewrapping, using update() only for ciphertext so submitted
        # immutability, timestamps, receipt and business/audit history stay intact.
        for model, reader, _binder, label in (
            (
                CounselingCaseClosure,
                case_closure_content.read,
                case_closure_content.binding,
                "Case closure note",
            ),
            (
                CounselingCaseHandoff,
                case_handoff_content.read,
                case_handoff_content.binding,
                "Case handoff",
            ),
            (
                CounselingCaseHandoffAddendum,
                case_handoff_content.read_addendum,
                case_handoff_content.addendum_binding,
                "Case handoff addendum",
            ),
        ):
            seen = changed = unreadable = 0
            last = None
            while True:
                with transaction.atomic():
                    qs = model.objects.order_by("pk")
                    if model is CounselingCaseClosure:
                        qs = qs.filter(content_ciphertext__isnull=False)
                    if not dry_run:
                        qs = qs.select_for_update(of=("self",))
                    if last is not None:
                        qs = qs.filter(pk__gt=last)
                    batch = list(qs[:batch_size])
                    for item in batch:
                        seen += 1
                        try:
                            reader(item)
                            if not crypto.encrypted_with_primary_key(
                                item.content_ciphertext, keyring=content.keyring()
                            ):
                                replacement = crypto.reencrypt_with_primary_key(
                                    item.content_ciphertext,
                                    keyring=content.keyring(),
                                )
                                changed += 1
                                if not dry_run:
                                    model.objects.filter(pk=item.pk).update(
                                        content_ciphertext=replacement
                                    )
                        except (CaseContinuityError, ClosureContentUnavailable):
                            unreadable += 1
                if not batch:
                    break
                last = batch[-1].pk
            failed += unreadable
            self.stdout.write(
                f"{label} encryption: scanned={seen}; rewrap={changed}; "
                f"unreadable={unreadable}; dry_run={dry_run}"
            )
        if failed:
            raise CommandError("Unreadable Handoff payloads left unchanged.")
