"""Atomic metadata lifecycle. This module never authorizes professional reads."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User, UserDesignation
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    CONTINUITY_APPROVED,
    CONTINUITY_CANCELLED,
    CONTINUITY_DECLINED,
    CONTINUITY_REQUESTED,
    CONTINUITY_REVOKED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling.continuity_models import (
    ContinuityDecision,
    ContinuityReason,
    ContinuityRevocationReason,
    CoverageKind,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityGrant as Grant,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityScope as Scope,
)
from compass.counseling.continuity_policy import ContinuityError, require_policy
from compass.counseling.continuity_sources import resolve_source, validate_selection
from compass.organization.models import StudentAffiliation


# Identity rows (sorted UUID) -> Grant -> Scope -> exact source rows (sorted kind/UUID).
# No source mutation services are called while these locks are held.
def _users(*ids):
    return {
        u.pk: u
        for u in User.objects.select_for_update(of=("self",))
        .select_related("role")
        .only("id", "role", "role__code", "is_active", "student_lifecycle_status")
        .filter(pk__in=set(ids) - {None})
        .order_by("id")
    }


def _actor(user, action, now):
    if user is None or not user.is_active or user.role.code != "COUNSELOR":
        raise ContinuityError("invalid_role")
    if not user.has_capability("counseling.continuity." + action, at=now):
        raise ContinuityError("missing_capability")
    return user


def _head(actor, policy, now):
    _actor(actor, "approve", now)
    if (
        actor.pk not in policy.approver_ids
        or not UserDesignation.objects.filter(
            user_id=actor.pk, designation__code="HEAD_GUIDANCE_COUNSELOR"
        ).exists()
    ):
        # No Acting route: an override/supervision cannot establish formal delegation.
        raise ContinuityError("approval_authority_missing")


def _student(student, policy):
    if student is None or not is_current_student(student):
        raise ContinuityError("ineligible_student", 422)
    affiliation = (
        StudentAffiliation.objects.filter(student_id=student.pk)
        .values("college_id", "updated_at", "college__is_active", "college__campus__is_active")
        .first()
    )
    if (
        not affiliation
        or affiliation["college_id"] not in policy.college_ids
        or not affiliation["college__is_active"]
        or not affiliation["college__campus__is_active"]
    ):
        raise ContinuityError("ineligible_student", 422)
    return str(affiliation["college_id"]) + ":" + affiliation["updated_at"].isoformat()


def _receiver(receiver, now):
    if receiver is None or not receiver.is_active or receiver.role.code != "COUNSELOR":
        raise ContinuityError("ineligible_receiver", 422)
    if not receiver.has_capability("counseling.continuity.read_selected", at=now):
        raise ContinuityError("ineligible_receiver", 422)


def _interval(starts_at, expires_at, policy, now):
    if (
        not isinstance(starts_at, datetime)
        or not isinstance(expires_at, datetime)
        or timezone.is_naive(starts_at)
        or timezone.is_naive(expires_at)
        or starts_at >= expires_at
        or expires_at <= now
        or expires_at > policy.valid_until
        or starts_at < policy.valid_from
        or expires_at - starts_at > policy.maximum_duration
        or starts_at - now > policy.maximum_advance
    ):
        raise ContinuityError("invalid_interval", 422)


def _digest(grant, scopes):
    fields = (
        "student_id",
        "original_counselor_id",
        "receiving_counselor_id",
        "coverage_kind",
        "reason_category",
        "requested_by_id",
        "starts_at",
        "expires_at",
        "policy_version",
        "policy_evidence",
        "policy_digest",
        "student_affiliation_marker",
    )
    data = {}
    for field in fields:
        value = getattr(grant, field)
        data[field] = (
            value.astimezone(UTC).isoformat() if isinstance(value, datetime) else str(value)
        )
    data["scopes"] = sorted(
        (s.resource_kind, str(s.source_id), s.projection, s.source_revision) for s in scopes
    )
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _scopes(grant):
    return list(
        Scope.objects.select_for_update()
        .filter(grant=grant)
        .order_by("resource_kind", "source_id", "projection")
    )


def _snapshot(grant, scopes, policy):
    if (
        grant.policy_digest != policy.digest
        or grant.policy_version != policy.version
        or grant.policy_evidence != policy.evidence_reference
    ):
        raise ContinuityError("policy_unconfirmed")
    validate_selection(scopes)
    if grant.snapshot_digest != _digest(grant, scopes):
        raise ContinuityError("scope_changed", 409)


def _sources(grant, scopes, users, policy):
    for scope in scopes:
        revision = resolve_source(
            selection=scope,
            student_id=grant.student_id,
            requester=users[grant.requested_by_id],
            policy=policy,
            original_counselor_id=grant.original_counselor_id,
        )
        if revision != scope.source_revision:
            raise ContinuityError("source_changed", 409)


def _overlap(grant, policy):
    # Student identity lock serializes empty-set races too, across distinct receivers.
    qs = Grant.objects.filter(
        student_id=grant.student_id,
        decision__in=["REQUESTED", "APPROVED"],
        starts_at__lt=grant.expires_at,
        expires_at__gt=grant.starts_at,
    ).exclude(pk=grant.pk)
    if policy.overlap_rule == "ALLOW_DIFFERENT_RECEIVERS":
        qs = qs.filter(
            receiving_counselor_id=grant.receiving_counselor_id, coverage_kind=grant.coverage_kind
        )
    if qs.exists():
        raise ContinuityError("overlap", 409)


def _audit(grant, actor, verb, context):
    # Do not allow a caller-supplied context to attribute another person's decision.
    if context is None:
        context = AuditContext.user(actor)
    if context.actor_type != "USER" or context.actor.pk != actor.pk:
        raise ValueError("continuity audit context must match the acting user")
    record_event(
        context=context,
        action={
            "requested": CONTINUITY_REQUESTED,
            "approved": CONTINUITY_APPROVED,
            "declined": CONTINUITY_DECLINED,
            "cancelled": CONTINUITY_CANCELLED,
            "revoked": CONTINUITY_REVOKED,
        }[verb],
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.counselorcasecontinuitygrant",
        target_id=grant.pk,
        metadata={
            "student_id": str(grant.student_id),
            "receiving_counselor_id": str(grant.receiving_counselor_id),
            "coverage_kind": grant.coverage_kind,
            "reason_code": grant.revocation_reason or grant.reason_category,
            "version": grant.version,
            "starts_at": grant.starts_at.isoformat(),
            "expires_at": grant.expires_at.isoformat(),
            "policy_version": grant.policy_version,
            "policy_evidence": grant.policy_evidence,
            "scope_snapshot_digest": grant.snapshot_digest,
        },
    )


def _effective(grant, scopes, users, policy, now):
    if grant.decision != ContinuityDecision.APPROVED:
        return {
            "REQUESTED": "PENDING",
            "DECLINED": "DECLINED",
            "CANCELLED": "CANCELLED",
            "REVOKED": "REVOKED",
        }[grant.decision]
    try:
        _snapshot(grant, scopes, policy)
        _receiver(users.get(grant.receiving_counselor_id), now)
        if _student(users.get(grant.student_id), policy) != grant.student_affiliation_marker:
            return "UNAVAILABLE"
        _head(users.get(grant.decision_by_id), policy, now)
        if not grant.starts_at <= now < grant.expires_at:
            return "SCHEDULED" if now < grant.starts_at else "EXPIRED"
    except ContinuityError:
        return "UNAVAILABLE"
    return "ACTIVE"


def _metadata(grant, scopes, users, policy, now):
    _snapshot(grant, scopes, policy)
    return {
        "id": grant.pk,
        "student_id": grant.student_id,
        "original_counselor_id": grant.original_counselor_id,
        "receiving_counselor_id": grant.receiving_counselor_id,
        "coverage_kind": grant.coverage_kind,
        "reason_category": grant.reason_category,
        "requested_by_id": grant.requested_by_id,
        "requested_at": grant.requested_at,
        "starts_at": grant.starts_at,
        "expires_at": grant.expires_at,
        "decision": grant.decision,
        "effective_status": _effective(grant, scopes, users, policy, now),
        "decision_by_id": grant.decision_by_id,
        "decided_at": grant.decided_at,
        "revoked_by_id": grant.revoked_by_id,
        "revoked_at": grant.revoked_at,
        "revocation_reason": grant.revocation_reason or None,
        "version": grant.version,
        "policy_version": grant.policy_version,
        "policy_evidence": grant.policy_evidence,
        "scopes": [
            {
                "id": s.pk,
                "resource_kind": s.resource_kind,
                "source_id": s.source_id,
                "projection": s.projection,
                "source_revision": s.source_revision,
            }
            for s in scopes
        ],
    }


def _ids(grant, actor_id):
    return [
        actor_id,
        grant.student_id,
        grant.original_counselor_id,
        grant.receiving_counselor_id,
        grant.requested_by_id,
        grant.decision_by_id,
        grant.revoked_by_id,
    ]


def _visible(grant, actor, policy, now):
    if actor.pk in {grant.requested_by_id, grant.receiving_counselor_id}:
        return
    # Original-author metadata participation is new only for a sealed workflow policy.
    if policy.workflow_policy_digest and actor.pk == grant.original_counselor_id:
        from compass.counseling.coverage_policy import require_workflow_policy

        workflow = require_workflow_policy(policy, now)
        if (
            grant.policy_digest == policy.digest
            and actor.has_capability("counseling.handoff.manage_own", at=now)
            and StudentAffiliation.objects.filter(
                student_id=grant.student_id,
                college_id__in=workflow.college_ids.intersection(policy.college_ids),
            ).exists()
        ):
            return
    # Head status alone gives no office-wide enumeration; exact policy office scope applies.
    try:
        _head(actor, policy, now)
        if StudentAffiliation.objects.filter(
            student_id=grant.student_id, college_id__in=policy.college_ids
        ).exists():
            return
    except ContinuityError:
        pass
    raise ContinuityError("not_found", 404)


@transaction.atomic
def request_coverage(
    *,
    actor,
    student_id,
    receiving_counselor_id,
    original_counselor_id,
    coverage_kind,
    reason_category,
    starts_at,
    expires_at,
    scopes,
    request_id,
    expected_version,
    context=None,
):
    if expected_version != 0:
        raise ContinuityError("stale_version", 409)
    validate_selection(scopes)
    replay_hint = Grant.objects.filter(requested_by_id=actor.pk, request_id=request_id).first()
    replay_ids = _ids(replay_hint, actor.pk) if replay_hint else []
    users = _users(actor.pk, student_id, receiving_counselor_id, original_counselor_id, *replay_ids)
    now = timezone.now()
    actor = _actor(users.get(actor.pk), "request", now)
    policy = require_policy(now)
    affiliation = _student(users.get(student_id), policy)
    _receiver(users.get(receiving_counselor_id), now)
    _interval(starts_at, expires_at, policy, now)
    if (
        coverage_kind not in CoverageKind.values
        or reason_category not in ContinuityReason.values
        or reason_category not in policy.reason_categories
    ):
        raise ContinuityError("invalid_purpose", 422)
    if original_counselor_id is not None:
        original = users.get(original_counselor_id)
        if original is None or original.role.code != "COUNSELOR":
            raise ContinuityError("invalid_original_counselor", 422)
    if not isinstance(request_id, UUID):
        raise ContinuityError("invalid_request_id", 422)
    grant = Grant(
        student_id=student_id,
        receiving_counselor_id=receiving_counselor_id,
        original_counselor_id=original_counselor_id,
        coverage_kind=coverage_kind,
        reason_category=reason_category,
        requested_by=actor,
        requested_at=now,
        starts_at=starts_at,
        expires_at=expires_at,
        policy_version=policy.version,
        policy_evidence=policy.evidence_reference,
        policy_digest=policy.digest,
        student_affiliation_marker=affiliation,
        request_id=request_id,
    )
    selected = []
    for selection in sorted(scopes, key=lambda s: (s.resource_kind, s.source_id, s.projection)):
        revision = resolve_source(
            selection=selection,
            student_id=student_id,
            requester=actor,
            policy=policy,
            original_counselor_id=original_counselor_id,
        )
        selected.append(
            Scope(
                grant=grant,
                resource_kind=selection.resource_kind,
                source_id=selection.source_id,
                projection=selection.projection,
                source_revision=revision,
            )
        )
    grant.snapshot_digest = _digest(grant, selected)
    existing = (
        Grant.objects.select_for_update().filter(requested_by=actor, request_id=request_id).first()
    )
    if existing:
        if existing.snapshot_digest != grant.snapshot_digest:
            raise ContinuityError("request_conflict", 409)
        existing_scopes = _scopes(existing)
        _snapshot(existing, existing_scopes, policy)
        # Replay creates no second event or transition, irrespective of current decision/version.
        return _metadata(existing, existing_scopes, users, policy, timezone.now())
    _overlap(grant, policy)
    grant.save(force_insert=True)
    Scope.objects.bulk_create(selected)
    _audit(grant, actor, "requested", context)
    return _metadata(grant, selected, users, policy, now)


@transaction.atomic
def decide_coverage(
    *, actor, grant_id, decision, expected_version, revocation_reason="", context=None
):
    hint = Grant.objects.filter(pk=grant_id).first()
    # Role/capability errors are independent of whether the UUID exists.
    action = {
        "APPROVED": "approve",
        "DECLINED": "approve",
        "CANCELLED": "request",
        "REVOKED": "revoke",
    }.get(decision)
    if action is None:
        raise ContinuityError("invalid_transition", 409)
    users = _users(*(_ids(hint, actor.pk) if hint else [actor.pk]))
    now = timezone.now()
    actor = _actor(users.get(actor.pk), action, now)
    policy = require_policy(now)
    if hint is None:
        raise ContinuityError("not_found", 404)
    grant = Grant.objects.select_for_update().get(pk=grant_id)
    if decision != "CANCELLED":
        _head(actor, policy, now)
    _visible(grant, actor, policy, now)
    if decision == "CANCELLED":
        if actor.pk != grant.requested_by_id:
            raise ContinuityError("not_found", 404)
    else:
        _head(actor, policy, now)
        if actor.pk in {grant.requested_by_id, grant.receiving_counselor_id}:
            raise ContinuityError("self_approval")
    selected = _scopes(grant)
    # Reducing transitions remain possible when source revision/receiver eligibility changes.
    if decision == "APPROVED":
        _snapshot(grant, selected, policy)
    if expected_version != grant.version:
        raise ContinuityError("stale_version", 409)
    if grant.decision == decision and (
        (
            decision == "REVOKED"
            and grant.revoked_by_id == actor.pk
            and grant.revocation_reason == revocation_reason
        )
        or (decision != "REVOKED" and grant.decision_by_id == actor.pk)
    ):
        return _metadata(grant, selected, users, policy, now)
    required = "APPROVED" if decision == "REVOKED" else "REQUESTED"
    if grant.decision != required:
        raise ContinuityError("invalid_transition", 409)
    now = timezone.now()  # Recheck after all lock waits.
    policy.validate(now)
    if decision == "APPROVED":
        _receiver(users.get(grant.receiving_counselor_id), now)
        if _student(users.get(grant.student_id), policy) != grant.student_affiliation_marker:
            raise ContinuityError("student_changed", 409)
        _interval(grant.starts_at, grant.expires_at, policy, now)
        _sources(grant, selected, users, policy)
        # NOWAIT source locks avoid reversed-order waits; recheck expiring authority
        # immediately before persistence, after every source validation.
        now = timezone.now()
        policy.validate(now)
        _head(actor, policy, now)
        _receiver(users.get(grant.receiving_counselor_id), now)
        _interval(grant.starts_at, grant.expires_at, policy, now)
        _overlap(grant, policy)
    if decision == "REVOKED":
        if revocation_reason not in ContinuityRevocationReason.values:
            raise ContinuityError("invalid_revocation_reason", 422)
        grant.revoked_by = actor
        grant.revoked_at = now
        grant.revocation_reason = revocation_reason
    else:
        grant.decision_by = actor
        grant.decided_at = now
    grant.decision = decision
    grant.version += 1
    grant.save(
        update_fields=[
            "decision",
            "decision_by",
            "decided_at",
            "revoked_by",
            "revoked_at",
            "revocation_reason",
            "version",
            "updated_at",
        ]
    )
    _audit(
        grant,
        actor,
        {
            "APPROVED": "approved",
            "DECLINED": "declined",
            "CANCELLED": "cancelled",
            "REVOKED": "revoked",
        }[decision],
        context,
    )
    return _metadata(grant, selected, users, policy, now)


@transaction.atomic
def get_grant_metadata(*, actor, grant_id):
    hint = Grant.objects.filter(pk=grant_id).first()
    users = _users(*(_ids(hint, actor.pk) if hint else [actor.pk]))
    now = timezone.now()
    actor = _actor(users.get(actor.pk), "view", now)
    policy = require_policy(now)
    if hint is None:
        raise ContinuityError("not_found", 404)
    grant = Grant.objects.select_for_update().get(pk=grant_id)
    _visible(grant, actor, policy, now)
    selected = _scopes(grant)
    # Identity references are immutable through the service; defend against privileged drift.
    if any(i is not None and i not in users for i in _ids(grant, actor.pk)):
        raise ContinuityError("not_found", 404)
    return _metadata(grant, selected, users, policy, timezone.now())


@transaction.atomic
def list_grant_metadata(*, actor, page=1, page_size=20):
    users = _users(actor.pk)
    now = timezone.now()
    actor = _actor(users.get(actor.pk), "view", now)
    policy = require_policy(now)
    if not 1 <= page or not 1 <= page_size <= 50:
        raise ContinuityError("invalid_pagination", 422)
    scope = Q(requested_by=actor) | Q(receiving_counselor=actor)
    if policy.workflow_policy_digest and actor.has_capability(
        "counseling.handoff.manage_own", at=now
    ):
        from compass.counseling.coverage_policy import require_workflow_policy

        workflow = require_workflow_policy(policy, now)
        scope |= Q(
            original_counselor=actor,
            policy_digest=policy.digest,
            student__organization_student_affiliation__college_id__in=workflow.college_ids.intersection(
                policy.college_ids
            ),
        )
    try:
        _head(actor, policy, now)
        scope |= Q(student__organization_student_affiliation__college_id__in=policy.college_ids)
    except ContinuityError:
        pass
    # Filter before slicing; no all-Student search parameters.
    ids = list(
        Grant.objects.filter(scope).values_list("id", flat=True)[
            (page - 1) * page_size : page * page_size + 1
        ]
    )
    # Only select IDs under this actor lock; its transaction ends before per-item locks.
    return ids, page, page_size


def list_metadata_page(*, actor, page=1, page_size=20):
    ids, page, page_size = list_grant_metadata(actor=actor, page=page, page_size=page_size)
    items = []
    for grant_id in ids[:page_size]:
        try:
            items.append(get_grant_metadata(actor=actor, grant_id=grant_id))
        except ContinuityError as exc:
            if exc.status != 404:
                raise
    return {"items": items, "page": page, "page_size": page_size, "has_next": len(ids) > page_size}
