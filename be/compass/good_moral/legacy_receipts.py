"""Count-only inventory and resumable observation import. No ownership reconciliation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass

from django.db import transaction

from compass.audit.actions import GOOD_MORAL_RECEIPT_LEGACY_IMPORTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_today

from .models import (
    GoodMoralReceiptAssignment as Assignment,
)
from .models import (
    GoodMoralReceiptIdentity as Identity,
)
from .models import (
    GoodMoralReceiptImportBatch as Batch,
)
from .models import (
    GoodMoralReceiptLedger as Ledger,
)
from .models import (
    GoodMoralRequest,
)
from .receipt_identity import normalize_number
from .services import InvalidGoodMoralInput


@dataclass
class ReceiptInventory:
    digest: str
    count: int
    keys: dict
    counts: dict


def inventory(*, maximum_records=100000):
    total = GoodMoralRequest.objects.count()
    if total > maximum_records:
        raise ValueError("Inventory record bound exceeded; review the authorized execution budget.")
    digest = hashlib.sha256()
    keys = {}
    counters = Counter()
    today = institution_today()
    observed_count = 0
    for row in (
        GoodMoralRequest.objects.order_by("id")
        .values(
            "id",
            "student_id",
            "variant",
            "status",
            "official_receipt_number",
            "official_receipt_date",
            "official_receipt_amount",
        )
        .iterator(chunk_size=500)
    ):
        observed_count += 1
        if observed_count > maximum_records:
            raise ValueError(
                "Inventory record bound exceeded; review the authorized execution budget."
            )
        digest.update(json.dumps(row, sort_keys=True, default=str, separators=(",", ":")).encode())
        number = row["official_receipt_number"]
        amount = row["official_receipt_amount"]
        receipt_date = row["official_receipt_date"]
        counters[f"{row['variant']}:{row['status']}"] += 1
        counters["missing_date"] += receipt_date is None
        counters["missing_amount"] += amount is None
        counters["zero_amount"] += amount is not None and amount.is_finite() and amount == 0
        counters["non_80_amount"] += amount is not None and (not amount.is_finite() or amount != 80)
        counters["future_date"] += receipt_date is not None and receipt_date > today
        if not number.strip(" "):
            counters["missing_number"] += 1
            continue
        try:
            _, key = normalize_number(number)
        except InvalidGoodMoralInput:
            counters["quarantined"] += 1
            continue
        previous = keys.get(key)
        keys[key] = (previous[0] + 1, None) if previous else (1, row["id"])
    counters["records"] = observed_count
    counters["duplicate_groups"] = sum(n > 1 for n, _ in keys.values())
    counters["duplicate_claims"] = sum(n for n, _ in keys.values() if n > 1)
    return ReceiptInventory(digest.hexdigest(), observed_count, keys, dict(counters))


def begin_import(*, batch_id, evidence_reference, maximum_records=100000):
    with transaction.atomic():
        Ledger.objects.get_or_create(pk=1)
        control = Ledger.objects.select_for_update().get(pk=1)
        observed = inventory(maximum_records=maximum_records)
        if control.mode != "DORMANT":
            if control.batch_id != batch_id:
                raise ValueError("Resume requires the original receipt import batch.")
            batch = Batch.objects.get(pk=batch_id)
            if batch.source_digest != observed.digest or batch.source_count != observed.count:
                raise ValueError("The frozen source changed; stop and investigate privately.")
            return observed
        if (
            not evidence_reference
            or len(evidence_reference) > 200
            or not evidence_reference.isprintable()
        ):
            raise ValueError("A bounded import evidence reference is required.")
        batch = Batch.objects.create(
            id=batch_id,
            source_digest=observed.digest,
            source_count=observed.count,
            evidence_reference=evidence_reference,
        )
        control.batch = batch
        control.mode = "FENCED"
        control.save(update_fields=["batch", "mode"])
        return observed


def import_chunk(*, batch_id, observed, size=100):
    with transaction.atomic():
        control = Ledger.objects.select_for_update().get(pk=1)
        if control.batch_id != batch_id or control.mode != "FENCED":
            if control.batch_id == batch_id and control.mode == "ACTIVE":
                return 0
            raise ValueError("The import batch is not the fenced receipt writer.")
        rows = list(
            GoodMoralRequest.objects.exclude(receipt_revisions__origin="LEGACY_OBSERVED").order_by(
                "id"
            )[:size]
        )
        for item in rows:
            identity = None
            try:
                _, key = normalize_number(item.official_receipt_number)
            except InvalidGoodMoralInput:
                key = None
            if key:
                count, owner = observed.keys[key]
                identity, _ = Identity.objects.get_or_create(
                    normalized_key=key,
                    defaults={
                        "state": "BOUND" if count == 1 else "LEGACY_AMBIGUOUS",
                        "bound_request_id": owner if count == 1 else None,
                        "origin": "LEGACY_OBSERVED",
                        "import_batch_id": batch_id,
                    },
                )
            amount_ok = item.official_receipt_amount is None or (
                item.official_receipt_amount.is_finite() and item.official_receipt_amount >= 0
            )
            current = (
                identity is not None
                and identity.state == "BOUND"
                and item.status in {"REQUESTED", "READY_FOR_ISSUANCE"}
                and amount_ok
                and (
                    item.official_receipt_date is None
                    or item.official_receipt_date <= institution_today()
                )
            )
            revision = Assignment.objects.create(
                identity=identity,
                request=item,
                display_number=item.official_receipt_number,
                receipt_date=item.official_receipt_date,
                amount=item.official_receipt_amount,
                origin="LEGACY_OBSERVED",
                sequence=1,
                change_kind="LEGACY",
                is_current=current,
                import_batch_id=batch_id,
            )
            record_event(
                context=AuditContext.system(),
                action=GOOD_MORAL_RECEIPT_LEGACY_IMPORTED,
                outcome=AuditOutcome.SUCCESS,
                target_type="goodmoral.request",
                target_id=item.pk,
                metadata={
                    "revision_id": str(revision.pk),
                    "batch_id": str(batch_id),
                    "origin": "LEGACY_OBSERVED",
                },
            )
        return len(rows)


def activate_synthetic_import(*, batch_id):
    """Only called by the disposable-database command/tests. Not a live cutover command."""
    with transaction.atomic():
        control = Ledger.objects.select_for_update().get(pk=1)
        if control.batch_id != batch_id:
            raise ValueError("The receipt import batch does not match.")
        if control.mode == "ACTIVE":
            return
        control.mode = "ACTIVE"
        # The database checks every source projection/import observation and unresolved format.
        control.save(update_fields=["mode"])
