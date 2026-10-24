"""Explicit physical inspection, exact-revision gates, and bounded operational state."""

import hashlib
import json
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import (
    GOOD_MORAL_RECEIPT_VERIFICATION_INVALIDATED,
    GOOD_MORAL_RECEIPT_VERIFIED,
    GOOD_MORAL_RETURNED_TO_PREPARATION,
)
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_today

from . import receipt_fee_policy as fees
from . import receipt_identity as receipts
from .models import GoodMoralReceiptAssignment as Assignment
from .models import GoodMoralReceiptIdentity as Identity
from .models import GoodMoralReceiptVerification as Verification
from .models import GoodMoralRequest, GoodMoralStatus
from .services import (
    GoodMoralConflict,
    GoodMoralNotFound,
    GoodMoralNotPermitted,
    InvalidGoodMoralInput,
    _queryset,
    _validate_counselor,
    _validate_operational,
)

METHOD = "PHYSICAL_OR_INSPECTION"
PENDING = {GoodMoralStatus.REQUESTED, GoodMoralStatus.READY_FOR_ISSUANCE}


class ReceiptBlocked(GoodMoralConflict):
    def __init__(self, code, message):
        self.code = f"good_moral_receipt_{code}"
        super().__init__(message)


def authority(actor, capability, context=None, *, lock=False, student_id=None):
    rows = User.objects.select_related("role")
    if lock:
        # Account management locks actor/target in UUID order. F4 issuance must
        # acquire its Counselor and Student together in that same order.
        identities = {actor.pk}
        if student_id is not None:
            identities.add(student_id)
        locked = {
            user.pk: user
            for user in rows.select_for_update(of=("self",))
            .filter(pk__in=identities)
            .order_by("id")
        }
        fresh = locked.get(actor.pk)
    else:
        fresh = rows.filter(pk=actor.pk).first()
    if fresh is None:
        raise GoodMoralNotPermitted("Authorized Guidance receipt access is required.")
    validate = _validate_counselor if capability == "good_moral.issue" else _validate_operational
    validate(fresh, capability)
    if context is not None and getattr(context.actor, "pk", None) != fresh.pk:
        raise GoodMoralNotPermitted("The audit actor must be the acting operator.")
    return fresh


def active_mode(*, verifying=False, lock=False):
    mode = receipts.ledger_mode(lock=lock)
    if mode == "FENCED" or (verifying and mode != "ACTIVE"):
        raise receipts.ReceiptCutoverRequired(
            "Receipt inspection is unavailable during this ledger state."
        )
    return mode == "ACTIVE"


def eligible(item, *, lock=False):
    # Match GM-OR-1: request fence, identity, assignment. No Student lock here.
    latest = receipts.latest_revision(item)
    if not latest or not latest.display_number.strip():
        raise ReceiptBlocked("missing", "Record the presented Official Receipt before inspection.")
    if latest.identity_id:
        identities = Identity.objects.select_for_update() if lock else Identity.objects
        identity = identities.get(pk=latest.identity_id)
    else:
        identity = None
    if lock:
        latest = Assignment.objects.select_for_update().get(pk=latest.pk)
    if (
        identity is None
        or identity.state != "BOUND"
        or identity.bound_request_id != item.pk
        or latest.request_id != item.pk
    ):
        raise ReceiptBlocked("conflict", "This receipt requires authorized GCO review.")
    if not latest.receipt_date or latest.amount is None:
        raise ReceiptBlocked("incomplete", "Complete the receipt date and actual printed amount.")
    if latest.receipt_date > institution_today():
        raise ReceiptBlocked("incomplete", "Official Receipt date cannot be in the future.")
    if not latest.is_current:
        raise ReceiptBlocked("conflict", "This receipt requires authorized GCO review.")
    if not latest.amount.is_finite() or latest.amount < 0 or latest.amount.as_tuple().exponent < -2:
        raise ReceiptBlocked("incomplete", "The recorded receipt amount is invalid.")
    return latest


def approved_decision(item, assignment):
    decision = fees.resolve_approved_fee(item=item, assignment=assignment)
    if not isinstance(decision, fees.FeeDecision) or not decision.applies(item, assignment):
        raise ReceiptBlocked(
            "policy_unresolved", "No approved fee decision applies to this receipt."
        )
    return decision


def decision_for(item, assignment):
    decision = approved_decision(item, assignment)
    if assignment.amount != decision.expected_amount:
        raise ReceiptBlocked(
            "fee_mismatch", "The actual receipt amount does not match the approved expected fee."
        )
    return decision


def current_verification(assignment, *, lock=False):
    rows = Verification.objects.select_for_update() if lock else Verification.objects
    return rows.filter(assignment=assignment, invalidated_at__isnull=True).first()


def gate(
    item,
    *,
    expected_resource_version=None,
    expected_receipt_revision=None,
    expected_verification=None,
    issuing=False,
    lock=False,
):
    if not active_mode(lock=lock):
        return None
    assignment = eligible(item, lock=lock)
    decision = decision_for(item, assignment)
    if lock and (
        not expected_resource_version or item.updated_at.isoformat() != expected_resource_version
    ):
        raise receipts.ReceiptChanged(
            "This request changed. Review the current details before continuing."
        )
    verification = current_verification(assignment, lock=lock)
    if verification is None:
        raise ReceiptBlocked(
            "unverified", "An authorized employee must inspect this physical receipt first."
        )
    if verification.fee_decision != decision.snapshot():
        raise ReceiptBlocked(
            "policy_unresolved", "The approved fee decision changed. Inspect and prepare again."
        )
    if issuing and (
        expected_receipt_revision != assignment.pk
        or expected_verification != verification.pk
        or item.prepared_receipt_verification_id != verification.pk
    ):
        raise receipts.ReceiptChanged(
            "Receipt inspection or preparation changed. Review and prepare again."
        )
    return assignment, verification, decision


def invalidate(*, item, actor, context, reason):
    for verification in Verification.objects.select_for_update().filter(
        assignment__request_id=item.pk, invalidated_at__isnull=True
    ):
        verification.invalidated_at = timezone.now()
        verification.invalidated_by = actor
        verification.invalidation_reason = reason
        verification.save(update_fields=["invalidated_at", "invalidated_by", "invalidation_reason"])
        record_event(
            context=context,
            action=GOOD_MORAL_RECEIPT_VERIFICATION_INVALIDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "revision_id": str(verification.assignment_id),
                "verification_id": str(verification.pk),
                "policy_id": verification.policy_id,
                "policy_version": verification.policy_version,
                "reason": reason,
            },
        )


def verify_receipt(
    *, actor, request_id, expected_resource_version, assignment_id, operation_id, method, context
):
    authority(actor, "good_moral.verify_receipt", context)
    if (
        method != METHOD
        or not all(isinstance(x, UUID) for x in (assignment_id, operation_id))
        or not expected_resource_version
    ):
        raise InvalidGoodMoralInput(
            "Inspection requires the reviewed request, exact revision, method and operation UUID."
        )
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "actor": str(actor.pk),
                "request": str(request_id),
                "version": expected_resource_version,
                "assignment": str(assignment_id),
                "method": method,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with transaction.atomic():
        item = GoodMoralRequest.objects.select_for_update().filter(pk=request_id).first()
        if item is None:
            raise GoodMoralNotFound("The requested Good Moral record was not found.")
        active_mode(verifying=True, lock=True)
        authority(actor, "good_moral.verify_receipt", context, lock=True)
        existing = Verification.objects.filter(operation_id=operation_id).first()
        if existing:
            if (
                existing.fingerprint != fingerprint
                or existing.verified_by_id != actor.pk
                or existing.assignment.request_id != item.pk
            ):
                raise receipts.ReceiptOperationConflict(
                    "The inspection operation was already used for different intent."
                )
            result = _queryset().get(pk=item.pk)
            result.receipt_verification_result = existing
            return result
        if item.status not in PENDING:
            raise GoodMoralConflict(
                "Only pending requests can have their physical receipt inspected."
            )
        if item.updated_at.isoformat() != expected_resource_version:
            raise receipts.ReceiptChanged(
                "This request changed. Review its latest details before inspecting."
            )
        assignment = eligible(item, lock=True)
        if assignment.pk != assignment_id:
            raise receipts.ReceiptChanged(
                "This receipt revision changed. Review its latest details before inspecting."
            )
        decision = decision_for(item, assignment)
        existing = current_verification(assignment, lock=True)
        if existing:
            if existing.fee_decision == decision.snapshot():
                raise ReceiptBlocked(
                    "already_verified",
                    "This exact receipt already has an attributable physical inspection.",
                )
            invalidate(item=item, actor=actor, context=context, reason="POLICY_CHANGED")
        try:
            with transaction.atomic():
                verification = Verification.objects.create(
                    assignment=assignment,
                    verified_by=actor,
                    method=METHOD,
                    policy_id=decision.policy_id,
                    policy_version=decision.version,
                    expected_amount=decision.expected_amount,
                    currency=decision.currency,
                    fee_decision=decision.snapshot(),
                    operation_id=operation_id,
                    fingerprint=fingerprint,
                )
        except IntegrityError as exc:
            if (
                receipts._constraint(exc)
                != "good_moral_goodmoralreceiptverification_operation_id_key"
            ):
                raise
            raise receipts.ReceiptOperationConflict(
                "The inspection operation was already used for different intent."
            ) from exc
        if item.status == GoodMoralStatus.READY_FOR_ISSUANCE:
            item.status = GoodMoralStatus.REQUESTED
            item.prepared_at = None
            item.prepared_by = None
            item.prepared_receipt_verification = None
            record_event(
                context=context,
                action=GOOD_MORAL_RETURNED_TO_PREPARATION,
                outcome=AuditOutcome.SUCCESS,
                target_type="goodmoral.request",
                target_id=item.pk,
                metadata={
                    "transition": "READY_FOR_ISSUANCE -> REQUESTED",
                    "reason": "RECEIPT_INSPECTED",
                },
            )
        item.save(
            update_fields=[
                "status",
                "prepared_at",
                "prepared_by",
                "prepared_receipt_verification",
                "updated_at",
            ]
        )
        record_event(
            context=context,
            action=GOOD_MORAL_RECEIPT_VERIFIED,
            outcome=AuditOutcome.SUCCESS,
            target_type="goodmoral.request",
            target_id=item.pk,
            metadata={
                "revision_id": str(assignment.pk),
                "verification_id": str(verification.pk),
                "policy_id": decision.policy_id,
                "policy_version": decision.version,
                "method": METHOD,
            },
        )
        authority(actor, "good_moral.verify_receipt", context)
        if decision_for(item, assignment).snapshot() != decision.snapshot():
            raise ReceiptBlocked(
                "policy_unresolved", "The approved fee decision changed during inspection."
            )
        result = _queryset().get(pk=item.pk)
        result.receipt_verification_result = verification
        return result


def operational_status(item, actor):
    mode = receipts.ledger_mode()
    revision = receipts.latest_revision(item)
    verification = current_verification(revision) if revision else None
    blocker = None
    decision = None
    state = "LEGACY_UNKNOWN"
    historical = item.status == GoodMoralStatus.ISSUED and item.issued_receipt_verification_id
    if historical:
        verification = Verification.objects.get(pk=item.issued_receipt_verification_id)
        state = "VERIFIED"
    elif mode == "ACTIVE":
        try:
            assignment = eligible(item)
            decision = approved_decision(item, assignment)
            if assignment.amount != decision.expected_amount:
                raise ReceiptBlocked(
                    "fee_mismatch", "The actual amount does not match the approved expected fee."
                )
            state = "NEEDS_VERIFICATION"
            if verification and verification.fee_decision == decision.snapshot():
                state = "VERIFIED"
            else:
                raise ReceiptBlocked("unverified", "Physical receipt inspection is required.")
        except ReceiptBlocked as exc:
            blocker = exc.code
            state = {
                "missing": "MISSING",
                "incomplete": "INCOMPLETE",
                "conflict": "LEGACY_CONFLICT",
                "policy_unresolved": "POLICY_UNAVAILABLE",
                "fee_mismatch": "INCOMPLETE",
            }.get(exc.code.removeprefix("good_moral_receipt_"), state)
            if revision and revision.identity_id and revision.identity.state == "DISPUTED":
                state = "DISPUTED"
    elif mode == "FENCED":
        blocker = "good_moral_receipt_cutover_required"
    can_verify = False
    if mode == "ACTIVE" and item.status in PENDING and decision and state == "NEEDS_VERIFICATION":
        try:
            authority(actor, "good_moral.verify_receipt")
            can_verify = True
        except GoodMoralNotPermitted:
            pass
    return {
        "status": state,
        "blocker": blocker,
        "can_verify": can_verify,
        "verification_id": verification.pk if verification else None,
        "verified_by_id": verification.verified_by_id if verification else None,
        "verified_at": verification.verified_at if verification else None,
        "method": verification.method if verification else None,
        "expected_amount": decision.expected_amount
        if decision
        else verification.expected_amount
        if historical
        else None,
        "currency": decision.currency
        if decision
        else verification.currency
        if historical
        else None,
    }
