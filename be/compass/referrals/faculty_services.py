"""Faculty-only intake and own projections; GCO authorization stays in services.py."""

import json
from datetime import timedelta
from uuid import UUID

from django.core import signing
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.actions import REFERRAL_FACULTY_SUBMITTED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.common.idempotency import request_fingerprint
from compass.common.institutional_time import institution_today
from compass.common.rate_limit import RateLimitPolicy, RateLimitUnavailable, RedisRateLimiter
from compass.institutional_forms.models import FormRevision
from compass.organization.integrity import catalog_dependent_write
from compass.referrals import faculty_rules as rules
from compass.referrals.administrative_state import administrative_state
from compass.referrals.faculty_placement import resolve_student_placement
from compass.referrals.faculty_rules import (
    FacultyReferralError,
)
from compass.referrals.faculty_rules import (
    require_faculty as _current_actor,
)
from compass.referrals.faculty_rules import (
    require_faculty_home as _home,
)
from compass.referrals.models import Referral, ReferralSubmissionChannel
from compass.referrals.services import (
    MAX_REASON_LENGTH,
    ReferralConfigurationConflict,
    ReferralCreationConflict,
    ReferralNotFound,
    _active_referral_revision,
    _allocate_reference,
    _clean_required,
    _creation_digest,
    _pagination,
    _validate_idempotency_key,
    persist_referral,
)
from compass.referrals.tracking_disclosure import (
    require_tracking_for_item,
    require_tracking_for_queryset,
)

SUBMIT_ROUTE = "/api/v1/faculty/referrals"
CONFIRMATION_SALT = "compass.faculty-referral.student-confirmation.v1"
MAX_CONFIRMATION_LENGTH = 4096


def _lock_users(*ids):
    return {
        user.pk: user
        for user in User.objects.select_related("role")
        .select_for_update(of=("self",))
        .filter(pk__in=set(ids))
        .order_by("id")
    }


def _session(actor, actor_session, now):
    if not isinstance(actor_session, AuthSession):
        raise FacultyReferralError("session_unavailable", 401)
    current = (
        AuthSession.objects.select_for_update()
        .filter(
            pk=actor_session.pk,
            user_id=actor.pk,
            token_digest=actor_session.token_digest,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .first()
    )
    if current is None:
        raise FacultyReferralError("session_unavailable", 401)
    return current


@catalog_dependent_write
def referral_availability(*, actor, actor_session):
    """Advisory current availability only; never a grant or Student disclosure."""
    users = _lock_users(actor.pk)
    actor = _current_actor(users.get(actor.pk))
    now = timezone.now()
    session = _session(actor, actor_session, now)
    result = {
        "can_confirm_student": False,
        "can_submit_referral": False,
        "can_view_submissions": False,
        "valid_until": None,
    }
    try:
        _home(actor)
    except FacultyReferralError:
        return result
    if not rules.active_colleges().exists():
        return result
    result["can_confirm_student"] = actor.has_capability("referrals.submit_self")
    result["can_view_submissions"] = actor.has_capability("referrals.view_submitted_self")
    if result["can_confirm_student"]:
        try:
            revision = _active_referral_revision()
            result["can_submit_referral"] = (
                revision.official_code,
                revision.official_revision,
                revision.internal_schema_version,
            ) == rules.DIGITAL_FORM
        except ReferralConfigurationConflict:
            pass
    if result["can_view_submissions"]:
        require_tracking_for_queryset(actor, _own_queryset(actor), now)
    if any(
        result[key]
        for key in ("can_confirm_student", "can_submit_referral", "can_view_submissions")
    ):
        result["valid_until"] = session.expires_at
    return result


def _rate_limit(actor, ip_address):
    limiter = RedisRateLimiter.from_settings()
    for name, subject, limit in (
        ("actor", str(actor.pk), rules.LOOKUP_ACTOR_LIMIT),
        ("ip", ip_address, rules.LOOKUP_IP_LIMIT),
    ):
        try:
            # Privacy-sensitive confirmation is always fail-closed, even if the generic
            # limiter is configured fail-open for a different service.
            result = limiter.consume(
                RateLimitPolicy(f"faculty-student-confirmation-{name}", limit, rules.LOOKUP_WINDOW),
                subject,
            )
        except RateLimitUnavailable:
            raise FacultyReferralError("confirmation_unavailable", 503) from None
        if not result.allowed:
            error = FacultyReferralError("rate_limited", 429)
            error.retry_after_seconds = result.retry_after_seconds
            raise error


def _ticket(actor, home, student, placement, now):
    return signing.Signer(salt=CONFIRMATION_SALT).sign_object(
        {
            "v": 1,
            "faculty_id": str(actor.pk),
            "student_id": str(student.pk),
            "home_version": home.resource_version,
            "student_revision": student.updated_at.isoformat(),
            "placement_revision": placement.revision,
            "issued_at": now.timestamp(),
        }
    )


def _decode_confirmation(value):
    if not isinstance(value, str) or not value or len(value) > MAX_CONFIRMATION_LENGTH:
        raise FacultyReferralError("student_unavailable", 409)
    try:
        payload = signing.Signer(salt=CONFIRMATION_SALT).unsign_object(value)
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError
        payload["student_id"] = UUID(payload["student_id"])
        return payload
    except (signing.BadSignature, ValueError, KeyError, TypeError, UnicodeError):
        raise FacultyReferralError("student_unavailable", 409) from None


@catalog_dependent_write
def confirm_student(*, actor, actor_session, institutional_id, ip_address):
    actor = _current_actor(actor, "referrals.submit_self")
    _rate_limit(actor, ip_address)
    try:
        identifier = User.objects.normalize_institutional_id(institutional_id)
    except ValueError:
        identifier = None
    # An exact, bounded normalized identifier only. No substring, name or directory path.
    candidate_id = (
        User.objects.filter(
            institutional_id=identifier,
            is_active=True,
            role__code="STUDENT",
        )
        .values_list("pk", flat=True)
        .first()
        if identifier
        else None
    )
    users = _lock_users(actor.pk, *([candidate_id] if candidate_id else []))
    actor = _current_actor(users.get(actor.pk), "referrals.submit_self")
    now = timezone.now()
    _session(actor, actor_session, now)
    home = _home(actor)
    student = users.get(candidate_id)
    placement = (
        resolve_student_placement(student)
        if student and student.institutional_id == identifier
        else None
    )
    if placement is None or not rules.active_colleges().filter(pk=placement.college_id).exists():
        return {"confirmed": False, "student": None, "confirmation": None, "expires_at": None}
    return {
        "confirmed": True,
        "student": {"display_name": student.get_full_name()},
        "confirmation": _ticket(actor, home, student, placement, now),
        "expires_at": now + timedelta(seconds=rules.CONFIRMATION_MAX_AGE),
    }


def _validate_confirmation(payload, *, actor, home, student, placement, now):
    issued_at = payload.get("issued_at")
    if (
        type(issued_at) not in (int, float)
        or not now.timestamp() - rules.CONFIRMATION_MAX_AGE <= issued_at <= now.timestamp()
        or payload.get("faculty_id") != str(actor.pk)
        or payload.get("home_version") != home.resource_version
        or placement is None
        or not rules.active_colleges().filter(pk=placement.college_id).exists()
        or student.updated_at.isoformat() != payload.get("student_revision")
        or placement.revision != payload.get("placement_revision")
    ):
        raise FacultyReferralError("student_unavailable", 409)


def _projection(item):
    # Never read/decrypt confidential content or serialize a GCO detail DTO here.
    return {
        "id": item.pk,
        "reference_code": item.reference_code,
        "submitted_at": item.submitted_at,
        "state": administrative_state(item),
        "student": {"display_name": item.student_name_snapshot},
        "received_at": item.received_at,
        "closed_at": item.administratively_closed_at,
    }


def _own_queryset(actor):
    return Referral.objects.filter(
        submission_channel=ReferralSubmissionChannel.FACULTY_PORTAL,
        submitted_by_id=actor.pk,
        student_college_at_submission_id__in=rules.active_colleges().values("pk"),
        voided_at__isnull=True,
    )


@catalog_dependent_write
def submit_referral(
    *, actor, actor_session, confirmation, course_year_block, reason, idempotency_key, context
):
    actor = _current_actor(actor, "referrals.submit_self")
    key = _validate_idempotency_key(idempotency_key)
    course = _clean_required(course_year_block, "course_year_block", 255)
    cleaned_reason = _clean_required(reason, "reason", MAX_REASON_LENGTH)
    payload = _decode_confirmation(confirmation)
    fingerprint = request_fingerprint(
        method="POST",
        route=SUBMIT_ROUTE,
        query_string="",
        body=json.dumps(
            {
                "confirmation": confirmation,
                "course_year_block": course_year_block,
                "reason": reason,
            },
            sort_keys=True,
        ).encode(),
    )
    # Namespace one canonical idempotency field; old GCO digests remain byte-for-byte.
    digest = _creation_digest(actor_id=actor.pk, key=key, namespace="FACULTY_PORTAL")
    users = _lock_users(actor.pk, payload["student_id"])
    actor = _current_actor(users.get(actor.pk), "referrals.submit_self")
    now = timezone.now()
    _session(actor, actor_session, now)
    home = _home(actor)
    existing = Referral.objects.select_for_update().filter(creation_key_digest=digest).first()
    if existing is not None:
        if existing.creation_request_fingerprint != fingerprint:
            raise ReferralCreationConflict(
                "The Idempotency-Key was already used for a different Referral request."
            )
        if not _own_queryset(actor).filter(pk=existing.pk).exists():
            raise ReferralNotFound("The submitted Referral was not found.")
        # Replays do not resubmit, allocate a reference, require an unexpired ticket,
        # rewrite provenance, or announce a new receipt.
        require_tracking_for_item(actor, existing, now)
        return _projection(existing), False
    student = users.get(payload["student_id"])
    placement = resolve_student_placement(student) if student else None
    _validate_confirmation(
        payload,
        actor=actor,
        home=home,
        student=student,
        placement=placement,
        now=now,
    )
    revision = _active_referral_revision()
    # Synchronization updates this same row. Revalidate after any lock wait.
    locked_revision_id = revision.pk
    FormRevision.objects.select_for_update(no_key=True, of=("self",)).get(pk=revision.pk)
    revision = _active_referral_revision()
    if revision.pk != locked_revision_id:
        raise FacultyReferralError("form_unavailable", 409)
    if (
        revision.official_code,
        revision.official_revision,
        revision.internal_schema_version,
    ) != rules.DIGITAL_FORM:
        raise FacultyReferralError("form_unavailable", 409)
    reference = _allocate_reference(at=now)
    # Counter contention must not extend an expired confirmation or session.
    latest = timezone.now()
    _session(actor, actor_session, latest)
    _validate_confirmation(
        payload,
        actor=actor,
        home=home,
        student=student,
        placement=placement,
        now=latest,
    )
    item = persist_referral(
        actor=actor,
        student=student,
        course_snapshot=course,
        reason=cleaned_reason,
        referrer_name=_clean_required(actor.get_full_name(), "referrer_name", 255),
        referred_on=institution_today(now),
        received_at=None,
        revision=revision,
        reference_code=reference,
        digest=digest,
        fingerprint=fingerprint,
        context=context,
        channel=ReferralSubmissionChannel.FACULTY_PORTAL,
        faculty_origin={
            "submitted_by": actor,
            "submitted_at": now,
            "faculty_home_college_id": home.college_id,
            "student_college_at_submission_id": placement.college_id,
        },
    )
    record_event(
        context=context,
        action=REFERRAL_FACULTY_SUBMITTED,
        outcome=AuditOutcome.SUCCESS,
        target_type="referrals.referral",
        target_id=item.pk,
        metadata={},
    )
    return _projection(item), True


@catalog_dependent_write
def list_own_submissions(*, actor, actor_session, page=1, page_size=20):
    page, page_size = _pagination(page=page, page_size=page_size)
    users = _lock_users(actor.pk)
    actor = _current_actor(users.get(actor.pk), "referrals.view_submitted_self")
    now = timezone.now()
    _session(actor, actor_session, now)
    _home(actor)
    queryset = _own_queryset(actor)
    require_tracking_for_queryset(actor, queryset, now)
    offset = (page - 1) * page_size
    items = list(queryset.order_by("-submitted_at", "-id")[offset : offset + page_size + 1])
    return {
        "items": [_projection(item) for item in items[:page_size]],
        "page": page,
        "page_size": page_size,
        "has_next": len(items) > page_size,
    }


@catalog_dependent_write
def get_own_submission(*, actor, actor_session, referral_id):
    users = _lock_users(actor.pk)
    actor = _current_actor(users.get(actor.pk), "referrals.view_submitted_self")
    now = timezone.now()
    _session(actor, actor_session, now)
    _home(actor)
    item = _own_queryset(actor).filter(pk=referral_id).first()
    if item is None:
        raise ReferralNotFound("The submitted Referral was not found.")
    require_tracking_for_item(actor, item, now)
    return _projection(item)
