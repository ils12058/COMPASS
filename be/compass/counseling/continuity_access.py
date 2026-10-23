"""Per-call selected reads with live policy, source-owned adapters and atomic release audit.

No decision/token is returned. The only result is a fixed approved projection after
transaction commit. Neither ordinary getters nor mutation services consume this path.
"""

from django.db import OperationalError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import CONTINUITY_SOURCE_READ
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.counseling import continuity_services as grants
from compass.counseling.continuity_disclosure import require_disclosure_policy
from compass.counseling.continuity_encounters import (
    _encounter_projection,
    _lock_encounter,
    encounter_revision,
)
from compass.counseling.continuity_locks import (
    lock_authority_relations,
    lock_policy_for_selected_read,
)
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_policy import ContinuityError, require_policy
from compass.counseling.continuity_read_schemas import (
    ContinuitySelectedEncounterResponse,
    ContinuitySelectedEvaluationResponse,
)
from compass.organization.models import StudentAffiliation
from compass.routine_interviews.continuity import (
    _evaluation_projection,
    _lock_evaluation,
    evaluation_revision,
)

SOURCE_CAPABILITIES = {
    ("ENCOUNTER", "ENCOUNTER_METADATA_V1"): "counseling.view_assigned",
    ("ROUTINE_EVALUATION", "FINALIZED_EVALUATION_V1"): "routine_interviews.view_assigned",
}


def _read_authority(*, actor, grant, scopes, users, resource_kind, projection, now, session):
    grants._actor(actor, "read_selected", now)
    source_capability = SOURCE_CAPABILITIES.get((resource_kind, projection))
    if source_capability is None:
        raise ContinuityError("source_not_found", 404)
    if not actor.has_capability(source_capability, at=now):
        raise ContinuityError("missing_capability")
    policy = require_policy(now)
    disclosure = require_disclosure_policy(now)
    if not policy.disclosure_policy_digest or policy.disclosure_policy_digest != disclosure.digest:
        raise ContinuityError("disclosure_policy_unconfirmed")
    selected = disclosure.selected_projection(resource_kind, projection)
    if grant is None or grant.receiving_counselor_id != actor.pk or grant.decision != "APPROVED":
        raise ContinuityError("not_found", 404)
    if not grant.starts_at <= now < grant.expires_at:
        raise ContinuityError("not_found", 404)
    grants._snapshot(grant, scopes, policy)
    if grants._effective(grant, scopes, users, policy, now) != "ACTIVE":
        raise ContinuityError("not_found", 404)
    if not StudentAffiliation.objects.filter(
        student_id=grant.student_id, college_id__in=disclosure.college_ids
    ).exists():
        raise ContinuityError("not_found", 404)
    if session is not None and (
        session.user_id != actor.pk
        or session.revoked_at is not None
        or not now < session.expires_at
    ):
        raise ContinuityError("session_unavailable", 401)
    return policy, disclosure, selected


def _prepared_read(
    *,
    actor,
    grant_id,
    resource_kind,
    source_id,
    projection,
    expected_version,
    context,
    actor_session_id,
    actor_session_digest,
):
    lock_policy_for_selected_read()
    # Never lock another receiver's Grant: contention must not become an existence oracle.
    hint = Grant.objects.filter(pk=grant_id, receiving_counselor_id=actor.pk).first()
    ids = (
        [actor.pk, hint.student_id, hint.receiving_counselor_id, hint.decision_by_id]
        if hint
        else [actor.pk]
    )
    users = grants._users(*ids)
    # These are the only intentionally waiting row locks. Recompute time after every wait.
    now = timezone.now()
    current_actor = grants._actor(users.get(actor.pk), "read_selected", now)
    grant = (
        (
            Grant.objects.select_for_update(nowait=True)
            .filter(pk=grant_id, receiving_counselor_id=actor.pk)
            .first()
        )
        if hint
        else None
    )
    scopes = (
        list(
            Scope.objects.select_for_update(nowait=True)
            .filter(grant_id=grant.pk)
            .order_by("resource_kind", "source_id", "projection")
        )
        if grant
        else []
    )
    if (
        grant is not None
        and grant.decision == "APPROVED"
        and any(
            i is not None and i not in users
            for i in [grant.student_id, grant.receiving_counselor_id, grant.decision_by_id]
        )
    ):
        raise ContinuityError("authority_changed", 409)
    lock_authority_relations()
    # Role definitions might have committed while User locks were being acquired.
    users = {
        u.pk: u
        for u in User.objects.select_related("role")
        .only("id", "role", "role__code", "is_active", "student_lifecycle_status")
        .filter(pk__in=users)
    }
    current_actor = users[actor.pk]
    session = None
    if actor_session_id is not None:
        session = (
            AuthSession.objects.select_for_update(nowait=True)
            .only("id", "user_id", "revoked_at", "expires_at")
            .filter(pk=actor_session_id, token_digest=actor_session_digest)
            .first()
        )
        if session is None or not actor_session_digest:
            raise ContinuityError("session_unavailable", 401)
    policy, disclosure, selected = _read_authority(
        actor=current_actor,
        grant=grant,
        scopes=scopes,
        users=users,
        resource_kind=resource_kind,
        projection=projection,
        now=timezone.now(),
        session=session,
    )
    scope = next(
        (
            s
            for s in scopes
            if (s.resource_kind, s.source_id, s.projection)
            == (resource_kind, source_id, projection)
        ),
        None,
    )
    if scope is None:
        raise ContinuityError("source_not_found", 404)
    if type(expected_version) is not int or expected_version != grant.version:
        raise ContinuityError("stale_version", 409)
    if resource_kind == "ENCOUNTER":
        source, _service = _lock_encounter(
            encounter_id=source_id,
            student_id=grant.student_id,
            original_counselor_id=grant.original_counselor_id,
            now=timezone.now(),
        )
        revision = encounter_revision(source)
    else:
        source, encounter = _lock_evaluation(
            routine_interview_id=source_id,
            student_id=grant.student_id,
            original_counselor_id=grant.original_counselor_id,
            now=timezone.now(),
        )
        revision = evaluation_revision(source, encounter)
    if revision != scope.source_revision:
        raise ContinuityError("source_changed", 409)
    # Final pre-decryption authorization: no source body is loaded before this point.
    policy, disclosure, selected = _read_authority(
        actor=current_actor,
        grant=grant,
        scopes=scopes,
        users=users,
        resource_kind=resource_kind,
        projection=projection,
        now=timezone.now(),
        session=session,
    )
    result = dict(
        grant_id=grant.pk,
        grant_version=grant.version,
        policy_version=policy.version,
        disclosure_policy_version=disclosure.version,
        projection=projection,
    )
    if resource_kind == "ENCOUNTER":
        result["encounter"] = _encounter_projection(source)
        schema = ContinuitySelectedEncounterResponse
    else:
        result.update(
            routine_interview_id=source.pk,
            evaluation=_evaluation_projection(source, selected.fields),
        )
        schema = ContinuitySelectedEvaluationResponse
    result = schema.model_validate(result).model_dump(exclude_unset=True)
    # Re-evaluate live clocks and provider snapshots after decryption/serialization.
    policy, disclosure, _ = _read_authority(
        actor=current_actor,
        grant=grant,
        scopes=scopes,
        users=users,
        resource_kind=resource_kind,
        projection=projection,
        now=timezone.now(),
        session=session,
    )
    if context is None:
        context = AuditContext.user(current_actor)
    if context.actor_type != "USER" or context.actor.pk != current_actor.pk:
        raise ValueError("continuity audit context must match the acting user")
    record_event(
        context=context,
        action=CONTINUITY_SOURCE_READ,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.counselorcasecontinuitygrant",
        target_id=grant.pk,
        metadata={
            "grant_id": str(grant.pk),
            "receiving_counselor_id": str(current_actor.pk),
            "student_id": str(grant.student_id),
            "resource_kind": resource_kind,
            "source_id": str(source_id),
            "projection": projection,
            "grant_version": grant.version,
            "policy_version": policy.version,
            "policy_evidence": policy.evidence_reference,
            "disclosure_policy_version": disclosure.version,
            "disclosure_policy_evidence": disclosure.evidence_reference,
            "disclosure_policy_digest": disclosure.digest,
        },
    )
    # An audit insert may itself wait. Expiry then rolls back the event and returns no body.
    _read_authority(
        actor=current_actor,
        grant=grant,
        scopes=scopes,
        users=users,
        resource_kind=resource_kind,
        projection=projection,
        now=timezone.now(),
        session=session,
    )
    return result


def read_selected_continuity_record(
    *,
    actor,
    grant_id,
    resource_kind,
    source_id,
    projection,
    expected_version,
    context=None,
    actor_session_id=None,
    actor_session_digest=None,
):
    try:
        with transaction.atomic(durable=True):
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            return _prepared_read(
                actor=actor,
                grant_id=grant_id,
                resource_kind=resource_kind,
                source_id=source_id,
                projection=projection,
                expected_version=expected_version,
                context=context,
                actor_session_id=actor_session_id,
                actor_session_digest=actor_session_digest,
            )
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            raise ContinuityError("source_busy", 409) from None
        raise
