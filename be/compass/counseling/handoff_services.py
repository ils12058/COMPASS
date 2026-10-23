"""Grant-bound Handoff lifecycle with durable authorization and content-free Audit."""

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.counseling import continuity_services as grants
from compass.counseling import handoff_content as content
from compass.counseling.continuity_locks import (
    lock_authority_relations,
    lock_policy_for_selected_read,
)
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_policy import ContinuityError, require_policy
from compass.counseling.coverage_policy import require_workflow_policy
from compass.counseling.handoff_models import CounselorHandoffSummary as Handoff


def _metadata(item):
    if item is None:
        return None
    return {
        k: getattr(item, k)
        for k in (
            "id",
            "grant_id",
            "student_id",
            "author_id",
            "receiving_counselor_id",
            "state",
            "submitted_at",
            "version",
            "created_at",
            "updated_at",
        )
    }


def _guard(actor, grant, scopes, users, operation, session):
    now = timezone.now()
    grants._actor(actor, "view", now)
    policy = require_policy(now)
    workflow = require_workflow_policy(policy, now)
    if session is not None and (
        session.user_id != actor.pk or session.revoked_at is not None or now >= session.expires_at
    ):
        raise ContinuityError("session_unavailable", 401)
    if grant is None:
        raise ContinuityError("not_found", 404)
    grants._snapshot(grant, scopes, policy)
    if operation == "metadata":
        grants._visible(grant, actor, policy, now)
        return workflow
    if grant.decision not in {"REQUESTED", "APPROVED"} or now >= grant.expires_at:
        raise ContinuityError("not_found", 404)
    if grants._student(users.get(grant.student_id), policy) != grant.student_affiliation_marker:
        raise ContinuityError("not_found", 404)
    grants._receiver(users.get(grant.receiving_counselor_id), now)
    if (
        not workflow.college_ids.intersection(policy.college_ids)
        or not grants.StudentAffiliation.objects.filter(
            student_id=grant.student_id, college_id__in=workflow.college_ids
        ).exists()
    ):
        raise ContinuityError("not_found", 404)
    if operation == "receive":
        grants._actor(actor, "read_selected", now)
        if not actor.has_capability("counseling.handoff.read_received", at=now):
            raise ContinuityError("missing_capability")
        if (
            actor.pk != grant.receiving_counselor_id
            or grants._effective(grant, scopes, users, policy, now) != "ACTIVE"
        ):
            raise ContinuityError("not_found", 404)
    else:
        if actor.pk != grant.original_counselor_id or actor.pk == grant.receiving_counselor_id:
            raise ContinuityError("not_found", 404)
        if not actor.has_capability(
            "counseling.handoff.manage_own", at=now
        ) or not actor.has_capability("counseling.view_assigned", at=now):
            raise ContinuityError("missing_capability")
        if grant.decision == "APPROVED" and grants._effective(
            grant, scopes, users, policy, now
        ) not in {"ACTIVE", "SCHEDULED"}:
            raise ContinuityError("not_found", 404)
    return workflow


def _audit(actor, item, verb, grant, workflow, context):
    context = context or AuditContext.user(actor)
    if context.actor_type != "USER" or context.actor.pk != actor.pk:
        raise ValueError("Handoff Audit actor must match")
    record_event(
        context=context,
        action="counseling.handoff." + verb,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.counselorhandoffsummary",
        target_id=item.pk,
        metadata={
            "grant_id": str(grant.pk),
            "student_id": str(item.student_id),
            "author_id": str(item.author_id),
            "receiving_counselor_id": str(item.receiving_counselor_id),
            "version": item.version,
            "state": item.state,
            "grant_version": grant.version,
            "policy_version": workflow.version,
            "policy_evidence": workflow.evidence_reference,
        },
    )


def operate(
    *,
    actor,
    grant_id,
    operation,
    expected_grant_version,
    expected_version=None,
    body=None,
    context=None,
    actor_session_id=None,
    actor_session_digest=None,
):
    """No reusable decision escapes. All bodies return only after the outermost commit."""
    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            lock_policy_for_selected_read()
            hint_qs = Grant.objects.filter(pk=grant_id)
            if operation != "metadata":
                hint_qs = hint_qs.filter(
                    Q(original_counselor_id=actor.pk) | Q(receiving_counselor_id=actor.pk)
                )
            hint = hint_qs.first()
            users = grants._users(*(grants._ids(hint, actor.pk) if hint else [actor.pk]))
            current_actor = grants._actor(users.get(actor.pk), "view", timezone.now())
            grant = (
                Grant.objects.select_for_update(nowait=True).filter(pk=hint.pk).first()
                if hint
                else None
            )
            scopes = (
                list(
                    Scope.objects.select_for_update(nowait=True)
                    .filter(grant=grant)
                    .order_by("resource_kind", "source_id", "projection")
                )
                if grant
                else []
            )
            if grant and any(
                i is not None and i not in users for i in grants._ids(grant, actor.pk)
            ):
                raise ContinuityError("authority_changed", 409)
            lock_authority_relations()
            users = {u.pk: u for u in User.objects.select_related("role").filter(pk__in=users)}
            current_actor = users[current_actor.pk]
            session = None
            if actor_session_id is not None:
                session = (
                    AuthSession.objects.select_for_update(nowait=True)
                    .filter(pk=actor_session_id, token_digest=actor_session_digest)
                    .first()
                )
                if session is None or not actor_session_digest:
                    raise ContinuityError("session_unavailable", 401)

            def guard():
                return _guard(current_actor, grant, scopes, users, operation, session)

            workflow = guard()
            if type(expected_grant_version) is not int or expected_grant_version != grant.version:
                raise ContinuityError("stale_version", 409)
            item = (
                Handoff.objects.select_for_update(nowait=True)
                .defer("content_ciphertext")
                .filter(grant=grant)
                .first()
            )
            if item and (
                item.student_id != grant.student_id
                or item.author_id != grant.original_counselor_id
                or item.receiving_counselor_id != grant.receiving_counselor_id
            ):
                raise ContinuityError("not_found", 404)
            if operation == "metadata":
                # Draft existence and state are author-only; approver/receiver see no draft.
                result = {
                    "handoff": _metadata(item)
                    if item and (item.state == "SUBMITTED" or current_actor.pk == item.author_id)
                    else None
                }
                guard()
                return result
            if operation == "save":
                content.validate_content(body)
                if item is None:
                    if expected_version != 0:
                        raise ContinuityError("stale_handoff_version", 409)
                    item = Handoff(
                        grant=grant,
                        student_id=grant.student_id,
                        author=current_actor,
                        receiving_counselor_id=grant.receiving_counselor_id,
                    )
                    verb = "draft_created"
                else:
                    if item.state != "DRAFT":
                        raise ContinuityError("handoff_submitted", 409)
                    if expected_version != item.version:
                        raise ContinuityError("stale_handoff_version", 409)
                    item.version += 1
                    verb = "draft_updated"
                try:
                    item.content_ciphertext = content.encrypt(item, body)
                except ImproperlyConfigured:
                    raise ContinuityError("handoff_unavailable", 503) from None
                guard()
                item.save()
                _audit(current_actor, item, verb, grant, workflow, context)
                result = _metadata(item)
            elif operation == "submit":
                if item is None:
                    raise ContinuityError("not_found", 404)
                if item.state == "SUBMITTED" and expected_version in {
                    item.version,
                    item.version - 1,
                }:
                    guard()
                    return _metadata(item)
                if expected_version != item.version:
                    raise ContinuityError("stale_handoff_version", 409)
                guard()
                if not content.read(item).strip():
                    raise ContinuityError("empty_handoff", 422)
                guard()
                item.state = "SUBMITTED"
                item.submitted_at = timezone.now()
                item.version += 1
                item.save(update_fields=["state", "submitted_at", "version", "updated_at"])
                _audit(current_actor, item, "submitted", grant, workflow, context)
                result = _metadata(item)
            elif operation in {"author_read", "receive"}:
                if item is None or (operation == "receive" and item.state != "SUBMITTED"):
                    raise ContinuityError("not_found", 404)
                guard()
                result = {**_metadata(item), "content": content.read(item)}
                guard()
                _audit(current_actor, item, "read", grant, workflow, context)
            else:
                raise ContinuityError("not_found", 404)
            guard()  # Audit insertion can wait; expiry rolls back event/body/mutation.
            return result
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            raise ContinuityError("source_busy", 409) from None
        raise
