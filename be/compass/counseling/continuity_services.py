"""Atomic metadata lifecycle. This module never authorizes professional reads."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
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
    ContinuityRevocationReason,
    CoverageKind,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityGrant as Grant,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityScope as Scope,
)
from compass.counseling.continuity_rules import (
    CASE_COORDINATION,
    REASON_CATEGORIES,
    ContinuityError,
    active_college_ids,
    overlapping_grants,
    require_unchanged_placement,
)
from compass.counseling.continuity_rules import (
    require_actor as _actor,
)
from compass.counseling.continuity_rules import (
    require_approver as _head,
)
from compass.counseling.continuity_rules import (
    require_receiver as _receiver,
)
from compass.counseling.continuity_rules import (
    student_placement_marker as _student,
)
from compass.counseling.continuity_rules import (
    validate_interval as _interval,
)
from compass.counseling.continuity_sources import resolve_source, validate_selection
from compass.student_academics.models import StudentAcademicProfile


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
        "student_placement_marker",
    )
    fields = (*fields, "communication_purpose")
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


def _snapshot(grant, scopes):
    validate_selection(scopes)
    if grant.snapshot_digest != _digest(grant, scopes):
        raise ContinuityError("scope_changed", 409)


def _sources(grant, scopes, users):
    for scope in scopes:
        revision = resolve_source(
            selection=scope,
            student_id=grant.student_id,
            requester=users[grant.requested_by_id],
            original_counselor_id=grant.original_counselor_id,
        )
        if revision != scope.source_revision:
            raise ContinuityError("source_changed", 409)


def _overlap(grant):
    # Student identity lock serializes empty-set races too, across distinct receivers.
    if overlapping_grants(grant).exists():
        raise ContinuityError("overlap", 409)


def _audit(grant, actor, verb, context):
    # Do not allow a caller-supplied context to attribute another person's decision.
    if context is None:
        context = AuditContext.user(actor)
    if context.actor_type != "USER" or context.actor.pk != actor.pk:
        raise ValueError("continuity audit context must match the acting user")
    metadata = {
        "student_id": str(grant.student_id),
        "receiving_counselor_id": str(grant.receiving_counselor_id),
        "coverage_kind": grant.coverage_kind,
        "reason_code": grant.revocation_reason or grant.reason_category,
        "version": grant.version,
        "starts_at": grant.starts_at.isoformat(),
        "expires_at": grant.expires_at.isoformat(),
        "scope_snapshot_digest": grant.snapshot_digest,
    }
    if grant.communication_purpose is not None:
        metadata["communication_purpose"] = grant.communication_purpose
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
        metadata=metadata,
    )


def _effective(grant, scopes, users, now):
    if grant.decision != ContinuityDecision.APPROVED:
        return {
            "REQUESTED": "PENDING",
            "DECLINED": "DECLINED",
            "CANCELLED": "CANCELLED",
            "REVOKED": "REVOKED",
        }[grant.decision]
    try:
        _snapshot(grant, scopes)
        _receiver(users.get(grant.receiving_counselor_id), now)
        if _student(users.get(grant.student_id)) != grant.student_placement_marker:
            return "UNAVAILABLE"
        # Completed approvals survive Head turnover; receiver rights remain live.
        if not grant.starts_at <= now < grant.expires_at:
            return "SCHEDULED" if now < grant.starts_at else "EXPIRED"
    except ContinuityError:
        return "UNAVAILABLE"
    return "ACTIVE"


def display_people(ids):
    """Names for identities a response already references; display only, never authority."""
    rows = User.objects.filter(pk__in=set(ids) - {None}).only(
        "id", "first_name", "middle_name", "last_name", "suffix", "institutional_id"
    )
    return {
        user.pk: {
            "id": user.pk,
            "name": user.get_full_name() or "Name not recorded",
            "institutional_id": user.institutional_id or None,
        }
        for user in rows
    }


def _people(grant):
    # Lets Counselors and the Head recognize a coverage without reading raw identifiers.
    people = display_people(
        [
            grant.student_id,
            grant.original_counselor_id,
            grant.receiving_counselor_id,
            grant.requested_by_id,
            grant.decision_by_id,
            grant.revoked_by_id,
        ]
    )
    return [people[key] for key in sorted(people, key=str)]


def _metadata(grant, scopes, users, now):
    _snapshot(grant, scopes)
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
        "effective_status": _effective(grant, scopes, users, now),
        "decision_by_id": grant.decision_by_id,
        "decided_at": grant.decided_at,
        "revoked_by_id": grant.revoked_by_id,
        "revoked_at": grant.revoked_at,
        "revocation_reason": grant.revocation_reason or None,
        "communication_purpose": grant.communication_purpose,
        "version": grant.version,
        "people": _people(grant),
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


def _visible(grant, actor, now):
    if actor.pk in {grant.requested_by_id, grant.receiving_counselor_id}:
        return
    # Original authors may view metadata within their live College placement.
    if actor.pk == grant.original_counselor_id:
        try:
            student = User.objects.select_related("role").filter(pk=grant.student_id).first()
            placement_matches = _student(student) == grant.student_placement_marker
        except ContinuityError:
            placement_matches = False
        if (
            placement_matches
            and actor.has_capability("counseling.handoff.manage_own", at=now)
            and StudentAcademicProfile.objects.filter(
                student_id=grant.student_id,
                current_college_id__in=active_college_ids(),
            ).exists()
        ):
            return
    # Head metadata enumeration remains limited to active Colleges.
    try:
        _head(actor, now)
        if StudentAcademicProfile.objects.filter(
            student_id=grant.student_id, current_college_id__in=active_college_ids()
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
    communication_purpose=None,
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
    placement_marker = _student(users.get(student_id))
    _receiver(users.get(receiving_counselor_id), now)
    _interval(starts_at, expires_at, now)
    if coverage_kind not in CoverageKind.values or reason_category not in REASON_CATEGORIES:
        raise ContinuityError("invalid_purpose", 422)
    if original_counselor_id is not None:
        original = users.get(original_counselor_id)
        if (
            original is None
            or original.role.code != "COUNSELOR"
            or original.pk == receiving_counselor_id
        ):
            raise ContinuityError("invalid_original_counselor", 422)
    if communication_purpose is not None:
        if communication_purpose != CASE_COORDINATION:
            raise ContinuityError("invalid_purpose", 422)
        if original_counselor_id is None or original_counselor_id == receiving_counselor_id:
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
        student_placement_marker=placement_marker,
        communication_purpose=communication_purpose,
        request_id=request_id,
    )
    selected = []
    for selection in sorted(scopes, key=lambda s: (s.resource_kind, s.source_id, s.projection)):
        revision = resolve_source(
            selection=selection,
            student_id=student_id,
            requester=actor,
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
        _snapshot(existing, existing_scopes)
        # Replay creates no second event or transition, irrespective of current decision/version.
        return _metadata(existing, existing_scopes, users, timezone.now())
    _overlap(grant)
    grant.save(force_insert=True)
    Scope.objects.bulk_create(selected)
    _audit(grant, actor, "requested", context)
    return _metadata(grant, selected, users, now)


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
    if hint is None:
        raise ContinuityError("not_found", 404)
    grant = Grant.objects.select_for_update().get(pk=grant_id)
    if decision != "CANCELLED":
        _head(actor, now)
    _visible(grant, actor, now)
    if decision == "CANCELLED":
        if actor.pk != grant.requested_by_id:
            raise ContinuityError("not_found", 404)
    else:
        _head(actor, now)
        if actor.pk in {grant.requested_by_id, grant.receiving_counselor_id}:
            raise ContinuityError("self_approval")
    selected = _scopes(grant)
    # Reducing transitions remain possible when source revision/receiver eligibility changes.
    if decision == "APPROVED":
        _snapshot(grant, selected)
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
        return _metadata(grant, selected, users, now)
    required = "APPROVED" if decision == "REVOKED" else "REQUESTED"
    if grant.decision != required:
        raise ContinuityError("invalid_transition", 409)
    now = timezone.now()  # Recheck after all lock waits.
    if decision == "APPROVED":
        _receiver(users.get(grant.receiving_counselor_id), now)
        require_unchanged_placement(
            _student(users.get(grant.student_id)), grant.student_placement_marker
        )
        _interval(grant.starts_at, grant.expires_at, now)
        _sources(grant, selected, users)
        # NOWAIT source locks avoid reversed-order waits; recheck expiring authority
        # immediately before persistence, after every source validation.
        now = timezone.now()
        _head(actor, now)
        _receiver(users.get(grant.receiving_counselor_id), now)
        _interval(grant.starts_at, grant.expires_at, now)
        _overlap(grant)
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
    return _metadata(grant, selected, users, now)


@transaction.atomic
def get_grant_metadata(*, actor, grant_id):
    hint = Grant.objects.filter(pk=grant_id).first()
    users = _users(*(_ids(hint, actor.pk) if hint else [actor.pk]))
    now = timezone.now()
    actor = _actor(users.get(actor.pk), "view", now)
    if hint is None:
        raise ContinuityError("not_found", 404)
    grant = Grant.objects.select_for_update().get(pk=grant_id)
    _visible(grant, actor, now)
    selected = _scopes(grant)
    # Identity references are immutable through the service; defend against privileged drift.
    if any(i is not None and i not in users for i in _ids(grant, actor.pk)):
        raise ContinuityError("not_found", 404)
    return _metadata(grant, selected, users, timezone.now())


@transaction.atomic
def list_grant_metadata(*, actor, page=1, page_size=20):
    users = _users(actor.pk)
    now = timezone.now()
    actor = _actor(users.get(actor.pk), "view", now)
    if not 1 <= page or not 1 <= page_size <= 50:
        raise ContinuityError("invalid_pagination", 422)
    scope = Q(requested_by=actor) | Q(receiving_counselor=actor)
    if actor.has_capability("counseling.handoff.manage_own", at=now):
        scope |= Q(
            original_counselor_id=actor.pk,
            student__student_academic_profile__current_college_id__in=active_college_ids(),
        )
    try:
        _head(actor, now)
        scope |= Q(student__student_academic_profile__current_college_id__in=active_college_ids())
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
