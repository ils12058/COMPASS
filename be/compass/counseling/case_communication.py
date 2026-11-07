"""One live predicate for authorized Counselor case coordination.

`authorize_case_coordination` is the only place that answers "may this Counselor coordinate about
this Student now?". It enforces the exact pair, the recorded communication purpose, the grant
decision and window, both approved policies, the persisted scope snapshot and the current effective
grant status. Messaging must not repeat those conditionals.

Lock contract: callers that write Messages pass `lock=True` and acquire the grant **before** the
thread, so revocation serializes against a send. Read, list and contextual paths pass `lock=False`.
"""

from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.counseling import continuity_services
from compass.counseling.case_communication_policy import require_case_communication_policy
from compass.counseling.continuity_models import (
    ContinuityCommunicationPurpose,
    ContinuityDecision,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityGrant as Grant,
)
from compass.counseling.continuity_models import (
    CounselorCaseContinuityScope as Scope,
)
from compass.counseling.continuity_policy import ContinuityError, require_policy


def _scopes(grant):
    return list(
        Scope.objects.filter(grant=grant).order_by("resource_kind", "source_id", "projection")
    )


def _users(grant):
    ids = {
        grant.receiving_counselor_id,
        grant.student_id,
        grant.decision_by_id,
    } - {None}
    return {
        user.pk: user
        for user in User.objects.select_related("role").filter(pk__in=ids).order_by("id")
    }


def _evaluate(grant, actor_id, now):
    if (
        grant.original_counselor_id is None
        or grant.original_counselor_id == grant.receiving_counselor_id
        or actor_id not in (grant.original_counselor_id, grant.receiving_counselor_id)
    ):
        # Never disclose that a grant exists to anyone outside the exact pair.
        raise ContinuityError("not_found", 404)
    if (
        grant.communication_purpose != ContinuityCommunicationPurpose.CASE_COORDINATION
        or not grant.communication_policy_digest
    ):
        raise ContinuityError("not_found", 404)
    if grant.revoked_at is not None or grant.decision == ContinuityDecision.REVOKED:
        raise ContinuityError("case_access_ended")
    if grant.decision != ContinuityDecision.APPROVED:
        raise ContinuityError("not_found", 404)
    if now < grant.starts_at:
        raise ContinuityError("not_found", 404)
    if now >= grant.expires_at:
        raise ContinuityError("case_access_ended")
    policy = require_policy(now)
    communication_policy = require_case_communication_policy(now)
    if (
        grant.policy_digest != policy.digest
        or grant.policy_version != policy.version
        or grant.policy_evidence != policy.evidence_reference
    ):
        raise ContinuityError("policy_unconfirmed")
    if grant.communication_policy_digest != communication_policy.digest:
        # The reviewed communication policy changed after this grant was recorded.
        raise ContinuityError("communication_policy_unconfirmed")
    scopes = _scopes(grant)
    try:
        continuity_services._snapshot(grant, scopes, policy)
    except ContinuityError as exc:
        if exc.code.endswith("policy_unconfirmed"):
            raise
        # A changed persisted snapshot or source revision ends coordination, never widens it.
        raise ContinuityError("case_access_ended") from None
    if continuity_services._effective(grant, scopes, _users(grant), policy, now) != "ACTIVE":
        raise ContinuityError("case_access_ended")
    return grant


def authorize_case_coordination(*, actor, grant_id, now=None, lock=False) -> Grant:
    if actor is None or not actor.is_active or actor.role.code != "COUNSELOR":
        raise ContinuityError("not_found", 404)
    now = now or timezone.now()
    query = Grant.objects.all()
    if lock:
        query = query.select_for_update(of=("self",))
    grant = query.filter(pk=grant_id).first()
    if grant is None:
        raise ContinuityError("not_found", 404)
    return _evaluate(grant, actor.pk, now)


def visible_case_coordination_grant_ids(*, actor, now=None) -> list[UUID]:
    if actor is None or not actor.is_active or actor.role.code != "COUNSELOR":
        return []
    now = now or timezone.now()
    candidates = (
        Grant.objects.filter(
            Q(original_counselor_id=actor.pk) | Q(receiving_counselor_id=actor.pk),
            communication_purpose=ContinuityCommunicationPurpose.CASE_COORDINATION,
        )
        .order_by("pk")
        .iterator()
    )
    visible = []
    for grant in candidates:
        try:
            _evaluate(grant, actor.pk, now)
        except ContinuityError:
            continue
        visible.append(grant.pk)
    return visible
