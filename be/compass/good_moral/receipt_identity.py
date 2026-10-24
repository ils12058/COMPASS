"""GM_OR_V1 reservations and correction receipts; dormant until a database-fenced cutover."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    GOOD_MORAL_RECEIPT_ASSIGNED,
    GOOD_MORAL_RECEIPT_REMOVED,
    GOOD_MORAL_RECEIPT_REVISED,
)
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import (
    GoodMoralReceiptAssignment as Assignment,
)
from .models import (
    GoodMoralReceiptIdentity as Identity,
)
from .models import (
    GoodMoralReceiptLedger,
    ReceiptLedgerMode,
)
from .models import (
    GoodMoralReceiptMutation as Mutation,
)
from .services import GoodMoralConflict, GoodMoralNotPermitted, InvalidGoodMoralInput

NORMALIZATION_VERSION = "GM_OR_V1"
RECEIPT_FIELDS = frozenset(
    {"official_receipt_number", "official_receipt_date", "official_receipt_amount"}
)
UNSET = object()


class ReceiptConflict(GoodMoralConflict):
    pass


class ReceiptChanged(GoodMoralConflict):
    pass


class ReceiptOperationConflict(GoodMoralConflict):
    pass


class ReceiptCutoverRequired(GoodMoralConflict):
    pass


def normalize_number(value: object) -> tuple[str, str]:
    """Return preserved display and byte-comparable identity. Never silently repair input."""
    if not isinstance(value, str) or any(not 32 <= ord(c) <= 126 for c in value):
        raise InvalidGoodMoralInput("Official Receipt number must use printable ASCII characters.")
    display = value.strip(" ")
    if not display or len(display) > 96:
        raise InvalidGoodMoralInput("Official Receipt number must contain 1 to 96 characters.")
    return display, display.upper()


def receipt_display(value: object) -> str:
    # Null and space-only strings express deliberate absence, not a reserved identity.
    if value is None or (isinstance(value, str) and not value.strip(" ")):
        return ""
    return normalize_number(value)[0]


def ledger_mode(*, lock=False) -> str:
    if lock:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT mode FROM good_moral_goodmoralreceiptledger WHERE id=1 FOR SHARE"
            )
            row = cursor.fetchone()
        return row[0] if row else ReceiptLedgerMode.DORMANT
    return (
        GoodMoralReceiptLedger.objects.filter(pk=1).values_list("mode", flat=True).first()
        or ReceiptLedgerMode.DORMANT
    )


def latest_revision(item):
    return Assignment.objects.filter(request_id=item.pk).order_by("-sequence").first()


@dataclass
class ReceiptIntent:
    operation_id: UUID
    fingerprint: str
    previous: Assignment | None
    replay: Mutation | None = None


def begin_edit(
    *,
    item,
    actor,
    changes,
    context,
    expected_resource_version,
    expected_receipt_revision=UNSET,
    operation_id=None,
):
    mode = ledger_mode(lock=True)
    if mode == ReceiptLedgerMode.FENCED:
        raise ReceiptCutoverRequired("Good Moral changes are paused for the receipt transition.")
    if mode != ReceiptLedgerMode.ACTIVE or not RECEIPT_FIELDS.intersection(changes):
        return None
    # Refresh authority independently of the caller's cached role and require truthful attribution.
    from .services import _validate_operational

    fresh_actor = User.objects.select_related("role").get(pk=actor.pk)
    _validate_operational(fresh_actor, "good_moral.prepare")
    if getattr(context.actor, "pk", None) != actor.pk:
        raise GoodMoralNotPermitted("The audit actor must be the correcting operator.")
    if (
        not isinstance(operation_id, UUID)
        or expected_receipt_revision is UNSET
        or not expected_resource_version
    ):
        raise InvalidGoodMoralInput(
            "Receipt changes require the reviewed request version, "
            "receipt revision and operation UUID."
        )
    if expected_receipt_revision is not None and not isinstance(expected_receipt_revision, UUID):
        raise InvalidGoodMoralInput("The reviewed receipt revision must be a UUID or null.")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "actor": str(actor.pk),
                "request": str(item.pk),
                "action": "CORRECTION",
                "request_version": expected_resource_version,
                "revision": str(expected_receipt_revision) if expected_receipt_revision else None,
                "changes": changes,
            },
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    existing = Mutation.objects.filter(pk=operation_id).first()
    if existing:
        if (
            existing.actor_id != actor.pk
            or existing.request_id != item.pk
            or existing.fingerprint != fingerprint
        ):
            raise ReceiptOperationConflict(
                "The correction operation was already used for different intent."
            )
        return ReceiptIntent(operation_id, fingerprint, None, existing)
    previous = latest_revision(item)
    if (
        item.updated_at.isoformat() != expected_resource_version
        or getattr(previous, "pk", None) != expected_receipt_revision
    ):
        raise ReceiptChanged(
            "This request or receipt changed. Review the latest saved details before saving again."
        )
    return ReceiptIntent(operation_id, fingerprint, previous)


def _constraint(exc):
    return getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)


def append_revision(*, item, actor, normalized, intent, context):
    facts = {name: normalized.get(name, getattr(item, name)) for name in RECEIPT_FIELDS}
    if all(facts[name] == getattr(item, name) for name in RECEIPT_FIELDS):
        return
    from .services import _clean_amount

    _clean_amount(facts["official_receipt_amount"])
    display = facts["official_receipt_number"]
    key = normalize_number(display)[1] if display else None
    previous = intent.previous
    keys = {key} if key else set()
    if previous and previous.identity_id:
        keys.add(Identity.objects.get(pk=previous.identity_id).normalized_key)
    identities = {
        x.normalized_key: x
        for x in Identity.objects.select_for_update()
        .filter(normalized_key__in=keys)
        .order_by("normalized_key")
    }
    identity = identities.get(key)
    if identity is not None:
        same_revision_identity = previous and previous.identity_id == identity.pk
        legacy_remediation = previous and previous.origin == "LEGACY_OBSERVED"
        if (
            identity.state != "BOUND"
            or identity.bound_request_id != item.pk
            or not same_revision_identity
            or not (previous.is_current or legacy_remediation)
        ):
            raise ReceiptConflict(
                "Official Receipt number already recorded. Check the number or ask GCO for review."
            )
    elif key:
        try:
            with transaction.atomic():
                identity = Identity.objects.create(
                    normalized_key=key,
                    bound_request=item,
                    state="BOUND",
                    recorded_by=actor,
                    origin="ORDINARY",
                )
        except IntegrityError as exc:
            if _constraint(exc) != "gm_receipt_identity_key_uniq":
                raise
            raise ReceiptConflict(
                "Official Receipt number already recorded. Check the number or ask GCO for review."
            ) from exc
    if previous:
        # The request fence serializes all revision writers; identities precede revision row locks.
        previous = Assignment.objects.select_for_update().get(pk=previous.pk)
        if previous.is_current:
            previous.is_current = False
            previous.closed_at = timezone.now()
            previous.closed_by = actor
            previous.closure_reason = "REVISION"
            previous.save(update_fields=["is_current", "closed_at", "closed_by", "closure_reason"])
    kind = (
        "REMOVED"
        if identity is None
        else (
            "REVISED"
            if previous and previous.identity_id == identity.pk
            else "REPLACED"
            if previous and previous.identity_id
            else "ASSIGNED"
        )
    )
    revision = Assignment.objects.create(
        identity=identity,
        request=item,
        display_number=display,
        receipt_date=facts["official_receipt_date"],
        amount=facts["official_receipt_amount"],
        origin="ORDINARY",
        sequence=previous.sequence + 1 if previous else 1,
        previous=previous,
        recorded_by=actor,
        change_kind=kind,
        is_current=identity is not None,
    )
    action = (
        GOOD_MORAL_RECEIPT_REMOVED
        if kind == "REMOVED"
        else (GOOD_MORAL_RECEIPT_ASSIGNED if kind == "ASSIGNED" else GOOD_MORAL_RECEIPT_REVISED)
    )
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="goodmoral.request",
        target_id=item.pk,
        metadata={
            "revision_id": str(revision.pk),
            "sequence": revision.sequence,
            "change_kind": kind,
            "previous_revision_id": str(previous.pk) if previous else None,
        },
    )


def finish_edit(*, item, actor, intent):
    if intent is None:
        return None
    try:
        with transaction.atomic():
            return Mutation.objects.create(
                operation_id=intent.operation_id,
                request=item,
                actor=actor,
                fingerprint=intent.fingerprint,
                intended_revision=intent.previous,
                result_revision=latest_revision(item),
                result_request_version=item.updated_at.isoformat(),
            )
    except IntegrityError as exc:
        if _constraint(exc) != "good_moral_goodmoralreceiptmutation_pkey":
            raise
        raise ReceiptOperationConflict(
            "The correction operation was already used for different intent."
        ) from exc


def operational_receipt_state(item):
    """Restricted, bounded own-request evidence; no global identity lookup or verification claim."""
    revision = latest_revision(item)
    mode = ledger_mode()
    state = "DORMANT" if mode == ReceiptLedgerMode.DORMANT else "ABSENT"
    if revision and revision.identity_id:
        state = Identity.objects.get(pk=revision.identity_id).state
    elif revision and revision.display_number:
        state = "QUARANTINED"
    return {
        "ledger_mode": mode,
        "revision_id": revision.pk if revision else None,
        "identity_state": state,
        "history": [
            {
                "id": x.pk,
                "sequence": x.sequence,
                "change_kind": x.change_kind,
                "origin": x.origin,
                "recorded_at": x.recorded_at,
                "recorded_by_id": x.recorded_by_id,
                "is_current": x.is_current,
                "closed_at": x.closed_at,
            }
            for x in Assignment.objects.filter(request_id=item.pk).order_by("-sequence")[:20]
        ],
    }
