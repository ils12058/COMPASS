"""Live authority shared by case transfer and case coverage; no legacy grant bypass."""

from datetime import timedelta

from django.db import OperationalError, transaction
from django.utils import timezone

from compass.accounts.models import User, UserDesignation
from compass.counseling.continuity_locks import lock_authority_relations
from compass.counseling.continuity_rules import (
    ContinuityError,
    is_head,
    is_office_requester,
    office_can_select,
)

from .case_models import CounselingCase
from .case_transfer_models import CaseAuthorizationRoute, CaseTransferPurpose

REVIEW_WINDOW = timedelta(days=7)


class CaseContinuityError(Exception):
    def __init__(self, code, message, status=409):
        self.code = "case_continuity_" + code
        self.message = message
        self.status = status
        super().__init__(message)


def fail(code, message, status=409):
    raise CaseContinuityError(code, message, status)


def current_actor(actor, capability="view", *, now=None):
    actor = (
        User.objects.select_related("role")
        .filter(pk=getattr(actor, "pk", None), is_active=True)
        .first()
    )
    if (
        actor is None
        or actor.role.code not in {"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"}
        or not actor.has_capability("counseling.continuity." + capability, at=now or timezone.now())
    ):
        fail("access_denied", "Case continuity is unavailable to this account.", 403)
    return actor


def receiver_eligible(receiver, now):
    return bool(
        receiver
        and receiver.is_active
        and receiver.role.code == "COUNSELOR"
        and receiver.has_capability("counseling.manage_assigned", at=now)
    )


def eligible_authorizers(*, requester_id, receiver_id, now):
    # Evaluate the roster, not the number or identity of Heads. An additional eligible Head
    # automatically selects ordinary independent authorization (owner decision, 13 November 2026).
    heads = UserDesignation.objects.filter(designation__code="HEAD_GUIDANCE_COUNSELOR").values(
        "user_id"
    )
    candidates = (
        User.objects.select_related("role")
        .filter(is_active=True, role__code="COUNSELOR", pk__in=heads)
        .exclude(pk__in=[requester_id, receiver_id])
        .distinct()
    )
    return tuple(
        person
        for person in candidates
        if person.has_capability("counseling.continuity.approve", at=now)
    )


def authorization_route(*, requester, receiver, case, now):
    if receiver.pk == requester.pk or receiver.pk == case.primary_counselor_id:
        fail("receiver_ineligible", "Choose another active Counselor to receive this case.", 422)
    if requester.pk == case.primary_counselor_id and is_head(requester):
        return CaseAuthorizationRoute.DIRECT_OUTGOING_HEAD
    if eligible_authorizers(requester_id=requester.pk, receiver_id=receiver.pk, now=now):
        return CaseAuthorizationRoute.INDEPENDENT_HEAD
    if requester.pk == case.primary_counselor_id and is_head(receiver):
        return CaseAuthorizationRoute.OWNER_TO_HEAD
    fail("no_independent_approver", "No independent approver is available.")


def may_prepare(actor, case, purpose=None):
    if purpose == CaseTransferPurpose.REOPEN:
        return (
            actor.pk != case.primary_counselor_id
            and is_office_requester(actor)
            and (is_head(actor) or office_can_select(actor, case.student_id))
        )
    if actor.pk == case.primary_counselor_id:
        return actor.role.code == "COUNSELOR" and actor.has_capability("counseling.manage_assigned")
    return is_office_requester(actor) and (
        is_head(actor) or office_can_select(actor, case.student_id)
    )


def require_preparer(actor, case, office_reason, purpose=None):
    if not may_prepare(actor, case, purpose):
        fail("case_not_found", "The case is not available for this arrangement.", 404)
    if purpose == CaseTransferPurpose.REOPEN and office_reason != "OWNER_UNAVAILABLE":
        fail(
            "office_reason_required",
            "Reopening transfer requires office preparation because the owner is unavailable.",
            422,
        )
    if actor.pk != case.primary_counselor_id and office_reason not in {
        "OWNER_UNAVAILABLE",
        "IMPARTIALITY_CONCERN",
    }:
        fail("office_reason_required", "Record why the office is preparing this arrangement.", 422)


def transfer_case_is_current(case, outgoing_id, purpose=None):
    status = "CLOSED" if purpose == CaseTransferPurpose.REOPEN else "ACTIVE"
    return case.primary_counselor_id == outgoing_id and case.status == status


def require_case_current(case, outgoing_id, purpose=None):
    if case.primary_counselor_id != outgoing_id:
        fail("owner_changed", "The primary Counselor changed. Prepare another arrangement.")
    if purpose == CaseTransferPurpose.REOPEN:
        if case.status != "CLOSED":
            fail("case_not_closed", "Only a Closed case can use a reopening transfer.")
    elif case.status != "ACTIVE":
        fail("case_not_active", "This case is no longer Active.")


def lock_case(case_id):
    case = CounselingCase.objects.select_for_update(of=("self",)).filter(pk=case_id).first()
    if case is None:
        fail("case_not_found", "The case was not found.", 404)
    return case


def lock_people(ids):
    head_ids = set(
        UserDesignation.objects.filter(designation__code="HEAD_GUIDANCE_COUNSELOR").values_list(
            "user_id", flat=True
        )
    )
    rows = tuple(
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk__in=(set(ids) | head_ids) - {None})
        .order_by("pk")
    )
    try:
        lock_authority_relations()
    except ContinuityError as exc:
        fail(
            "authority_busy",
            "Account authority is being updated. Review the arrangement again.",
            exc.status,
        )
    if not set(
        UserDesignation.objects.filter(designation__code="HEAD_GUIDANCE_COUNSELOR").values_list(
            "user_id", flat=True
        )
    ).issubset({person.pk for person in rows}):
        fail("authority_busy", "The Head roster changed. Review the arrangement again.")
    # Reload after the authority fence: definitions may have changed while a User lock waited.
    return {person.pk: User.objects.select_related("role").get(pk=person.pk) for person in rows}


def locked_rows(queryset):
    # Existing task/Appointment writers have other lock orders. Refuse a busy review instead of
    # waiting in an inverted order, and roll back the entire arrangement.
    try:
        with transaction.atomic():
            return tuple(queryset.select_for_update(of=("self",), nowait=True).order_by("pk"))
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) == "55P03":
            fail("work_busy", "The case's work is being changed. Review it again.")
        raise


def state_at(item, now=None):
    if (
        item.state == "AUTHORIZED"
        and item.review_expires_at is not None
        and item.review_expires_at <= (now or timezone.now())
    ):
        return "EXPIRED"
    return item.state


def require_version(item, expected_version):
    if type(expected_version) is not int or expected_version != item.version:
        fail("changed", "This arrangement changed. Review the latest details before acting.")


def require_review(item, now):
    if state_at(item, now) == "EXPIRED":
        fail(
            "review_expired",
            "The review window ended. The primary Counselor must arrange another review.",
        )
    if item.state != "AUTHORIZED" or item.authorized_version != item.version:
        fail("review_required", "This arrangement needs fresh authorization before acceptance.")
