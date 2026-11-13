"""Scoped reads and explicitly attributed, append-only scheduling verification."""

from datetime import timedelta

from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import REFERRAL_TIMING_RECORDED, REFERRAL_TIMING_VERIFIED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.organization.integrity import catalog_gate

from .errors import ReferralError
from .models import Referral
from .services import (
    ReferralNotFound,
    ReferralNotPermitted,
    _student_in_scope,
    _validate_operational_actor,
    get_referral,
)
from .timing_content import read_timing_content, write_timing_content
from .timing_models import (
    ReferralSchedulingStatement,
    ReferralSchedulingVerification,
    ReferralTimingSource,
)
from .timing_rules import InvalidReferralTiming, project_window, validate_timing_content


class ReferralTimingChanged(ReferralError):
    pass


class ReferralTimingSessionUnavailable(ReferralError):
    pass


def _session(actor, actor_session, now):
    if (
        not isinstance(actor_session, AuthSession)
        or not AuthSession.objects.select_for_update(of=("self",))
        .filter(
            pk=actor_session.pk,
            user_id=actor.pk,
            token_digest=actor_session.token_digest,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .exists()
    ):
        raise ReferralTimingSessionUnavailable(
            "Your session is no longer available. Sign in again."
        )


def timing_status(referral):
    statement = getattr(referral, "scheduling_statement", None)
    return statement.answer_kind if statement is not None else "NOT_PROVIDED"


def create_statement(*, referral, actor, statement, context, now):
    """Caller holds the Referral's creation transaction. Absent is never Unknown."""
    if statement is None:
        return
    payload = validate_timing_content(
        answer_kind=statement["answer_kind"],
        windows=statement.get("windows", []),
        note=statement.get("note", ""),
        now=now,
    )
    row = ReferralSchedulingStatement(
        referral=referral,
        answer_kind=statement["answer_kind"],
        window_count=len(payload["windows"]),
        submission_channel=referral.submission_channel,
        author=actor,
        author_name_snapshot=actor.get_full_name(),
        created_at=now,
    )
    write_timing_content(row, payload)
    row.save(force_insert=True)
    record_event(
        context=context,
        action=REFERRAL_TIMING_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        target_type="referrals.scheduling_statement",
        target_id=row.pk,
        metadata={
            "referral_id": str(referral.pk),
            "answer_kind": row.answer_kind,
            "submission_channel": row.submission_channel,
        },
    )


def _content_projection(row, *, now):
    content = read_timing_content(row)
    return {
        "id": row.pk,
        "answer_kind": row.answer_kind,
        "windows": [project_window(window, now=now) for window in content["windows"]],
        "note": content["note"],
        "author_id": row.author_id,
        "author_name": row.author_name_snapshot,
        "created_at": row.created_at,
    }


def reported_statement(referral, *, now=None):
    row = getattr(referral, "scheduling_statement", None)
    if row is None:
        return None
    return {
        **_content_projection(row, now=now or timezone.now()),
        "submission_channel": row.submission_channel,
    }


def _projection(referral, *, actor, now=None):
    current = now or timezone.now()
    rows = list(referral.scheduling_verifications.all())
    return {
        "referral_id": referral.pk,
        "timing_status": timing_status(referral),
        "reported": reported_statement(referral, now=current),
        "verifications": [
            {
                **_content_projection(row, now=current),
                "confirmation_source": row.confirmation_source,
            }
            for row in rows
        ],
        "latest_verification_id": rows[0].pk if rows else None,
        # Ninja's datetime JSON encoder rounds to milliseconds. Keep the full database
        # precision in this concurrency token so a read can be submitted unchanged.
        "referral_updated_at": referral.updated_at.isoformat(),
        "referral_closed": referral.administratively_closed_at is not None,
        "can_verify": referral.voided_at is None and actor.has_capability("referrals.manage"),
    }


def _current_actor(actor, capability):
    current = User.objects.select_related("role").filter(pk=actor.pk).first()
    if current is None:
        raise ReferralNotPermitted("You don't have permission to view Referral timing.")
    _validate_operational_actor(current)
    if not current.has_capability(capability):
        raise ReferralNotPermitted("You don't have permission to access Referral timing.")
    return current


def get_timing(*, actor, referral_id):
    current = _current_actor(actor, "referrals.view")
    return _projection(get_referral(actor=current, referral_id=referral_id), actor=current)


def record_verification(
    *,
    actor,
    actor_session,
    referral_id,
    expected_latest_verification_id,
    expected_referral_updated_at,
    answer_kind,
    confirmation_source,
    windows,
    note,
    context,
):
    _current_actor(actor, "referrals.manage")
    # Responsibility, supervision and Head-fallback writers take the shared gate.
    # Match Referral administration: fence them before taking account/resource locks,
    # then recheck authority. A row lock on the outgoing Counselor is insufficient.
    with catalog_gate(exclusive=True):
        return _record_verification_locked(
            actor=actor,
            actor_session=actor_session,
            referral_id=referral_id,
            expected_latest_verification_id=expected_latest_verification_id,
            expected_referral_updated_at=expected_referral_updated_at,
            answer_kind=answer_kind,
            confirmation_source=confirmation_source,
            windows=windows,
            note=note,
            context=context,
        )


def _record_verification_locked(
    *,
    actor,
    actor_session,
    referral_id,
    expected_latest_verification_id,
    expected_referral_updated_at,
    answer_kind,
    confirmation_source,
    windows,
    note,
    context,
):
    candidate = Referral.objects.filter(pk=referral_id).values_list("student_id", flat=True).first()
    if candidate is None:
        raise ReferralNotFound("The requested Referral was not found.")
    users = {
        user.pk: user
        for user in User.objects.select_related("role")
        .select_for_update(no_key=True, of=("self",))
        .filter(pk__in={actor.pk, candidate})
        .order_by("id")
    }
    current = users.get(actor.pk)
    if current is None:
        raise ReferralNotPermitted("You don't have permission to verify Referral timing.")
    _validate_operational_actor(current)
    if not current.has_capability("referrals.manage"):
        raise ReferralNotPermitted("You don't have permission to verify Referral timing.")
    now = timezone.now()
    _session(current, actor_session, now)
    referral = (
        Referral.objects.select_for_update(of=("self",))
        .filter(pk=referral_id, student_id=candidate)
        .first()
    )
    if referral is None or not _student_in_scope(current, referral.student_id):
        raise ReferralNotFound("The requested Referral was not found.")
    latest = referral.scheduling_verifications.first()
    if referral.voided_at is not None:
        raise ReferralTimingChanged("This Referral is voided. Verification cannot be added.")
    if expected_referral_updated_at != referral.updated_at or expected_latest_verification_id != (
        latest.pk if latest else None
    ):
        raise ReferralTimingChanged(
            "The Referral or verified availability changed. "
            "Review the latest information before adding a verification."
        )
    if confirmation_source not in ReferralTimingSource.values:
        raise InvalidReferralTiming(["confirmation_source"], "Choose how the time was confirmed.")
    now = timezone.now()
    _session(current, actor_session, now)
    payload = validate_timing_content(
        answer_kind=answer_kind, windows=windows, note=note, verification=True, now=now
    )
    # Preserve insertion order even if a clock has sub-microsecond precision or moves backwards.
    at = max(now, latest.created_at + timedelta(microseconds=1)) if latest else now
    row = ReferralSchedulingVerification(
        referral=referral,
        answer_kind=answer_kind,
        confirmation_source=confirmation_source,
        window_count=len(payload["windows"]),
        author=current,
        author_name_snapshot=current.get_full_name(),
        created_at=at,
    )
    write_timing_content(row, payload)
    row.save(force_insert=True)
    record_event(
        context=context,
        action=REFERRAL_TIMING_VERIFIED,
        outcome=AuditOutcome.SUCCESS,
        target_type="referrals.scheduling_verification",
        target_id=row.pk,
        metadata={
            "referral_id": str(referral.pk),
            "answer_kind": row.answer_kind,
            "confirmation_source": row.confirmation_source,
        },
    )
    return _projection(referral, actor=current, now=now)
