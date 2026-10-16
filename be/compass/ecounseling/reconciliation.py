"""Bounded, durable, metadata-only recovery. Never a provider command executor."""

import math
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from compass.integrations.daily import DailyClient, DailyError, safe_daily_failure_code

from .artifacts import ensure_pending_artifact
from .diagnostics import CaptureStage, log_capture_reconciliation
from .media import (
    _TERMINAL_CAPTURE_STATES,
    _capture_status_for_event,
    _has_stop_intent,
    effective_consent,
    media_scope,
)
from .models import (
    CaptureEvidence as Evidence,
)
from .models import (
    CaptureReconciliationOutcome as Outcome,
)
from .models import (
    CaptureReconciliationState as State,
)
from .models import (
    ConsentScope,
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingRoom,
)
from .models import (
    ECounselingCaptureReconciliation as Recovery,
)
from .models import (
    ECounselingMediaCapture as Capture,
)
from .provider_identity import ProviderIdentity, identity_conflict
from .webhook_events import MAX_DURATION_SECONDS, InvalidEvent, finite_number

_UNRESOLVED = ("START_REQUESTED", "STOP_REQUESTED", "ERROR")
_INITIAL_GRACE_SECONDS = 60


@dataclass(frozen=True, repr=False)
class Claim:
    capture_id: uuid.UUID
    token: uuid.UUID
    kind: str
    artifact_id: str | None
    identity: tuple


@dataclass(frozen=True)
class Observation:
    outcome: str = Outcome.UNKNOWN
    evidence: str = Evidence.UNKNOWN
    failure_code: str | None = None
    started_at: datetime | None = None
    duration: float | None = None


def _policy(name):
    return getattr(settings, f"ECOUNSELING_CAPTURE_RECONCILIATION_{name}")


def _eligible_captures():
    return (
        Capture.objects.filter(
            status__in=_UNRESOLVED,
            artifact_disposed_at__isnull=True,
            provider_binding_quarantined_at__isnull=True,
        )
        .filter(
            Q(media_authorized_at__isnull=False)
            | Q(provider_instance_id__isnull=False)
            | Q(stop_requested_at__isnull=False)
        )
        .exclude(artifact__status__in=("STORED", "DISPOSED"))
        .filter(artifact__disposed_at__isnull=True, artifact__provider_deleted_at__isnull=True)
    )


def _origin(capture):
    return (
        capture.stop_requested_at
        or (capture.failed_at if capture.status == "ERROR" else None)
        or capture.media_authorized_at
        or capture.created_at
    )


def discover_captures(*, limit):
    """A unique insert is the outbox; no capture history or authorization is rewritten."""
    captures = list(
        _eligible_captures()
        .filter(reconciliation__isnull=True)
        .order_by("created_at", "id")[:limit]
    )
    rows = [
        Recovery(
            capture=capture,
            uncertainty_since=_origin(capture),
            next_attempt_at=_origin(capture) + timedelta(seconds=_INITIAL_GRACE_SECONDS),
        )
        for capture in captures
    ]
    with transaction.atomic(durable=True):
        Recovery.objects.bulk_create(rows, ignore_conflicts=True)
    # This is a bounded discovery candidate count; concurrent unique inserts may win first.
    return len(rows)


@contextmanager
def _locked_rows(capture_id):
    room_id = Capture.objects.values_list("room_id", flat=True).get(pk=capture_id)
    with transaction.atomic(durable=True):
        room = ECounselingRoom.objects.select_for_update().get(pk=room_id)
        consents = list(
            ECounselingConsent.objects.select_for_update().filter(room=room).order_by("scope")
        )
        capture = Capture.objects.select_for_update().get(pk=capture_id)
        if capture.room_id != room.pk:
            raise RuntimeError("Reconciliation ownership changed.")
        capture.room = room
        artifact = (
            ECounselingMediaArtifact.objects.select_for_update().filter(capture=capture).first()
        )
        recovery = Recovery.objects.select_for_update().get(capture=capture)
        yield capture, artifact, recovery, consents


def _protected(capture, artifact):
    return bool(
        capture.status in _TERMINAL_CAPTURE_STATES
        or capture.provider_binding_quarantined_at
        or capture.artifact_disposed_at
        or (
            artifact
            and (
                artifact.status in ("STORED", "DISPOSED")
                or artifact.disposed_at
                or artifact.provider_deleted_at
            )
        )
    )


def _identity(capture):
    return (
        capture.room_id,
        capture.room.daily_room_name,
        capture.room.daily_room_id,
        capture.kind,
        capture.provider_instance_id,
        capture.provider_artifact_id,
        capture.provider_session_id,
        capture.media_authorized_at,
        capture.transcript_storage_authorized,
        capture.provider_binding_verified_at,
    )


def _clear_claim(recovery):
    recovery.claim_token = None
    recovery.claim_expires_at = None


def _escalate(recovery, code, now):
    recovery.state = State.ESCALATED
    recovery.escalation_code = code
    recovery.escalated_at = recovery.escalated_at or now
    recovery.next_attempt_at = None
    _clear_claim(recovery)


def _exhausted(recovery, now):
    return recovery.attempts >= _policy(
        "MAX_ATTEMPTS"
    ) or now >= recovery.uncertainty_since + timedelta(seconds=_policy("MAX_AGE_SECONDS"))


def _retry(recovery, now):
    _clear_claim(recovery)
    if _exhausted(recovery, now):
        _escalate(recovery, Outcome.EXHAUSTED, now)
    else:
        delay = min(
            900, _policy("RETRY_BASE_SECONDS") * 2 ** max(0, min(10, recovery.attempts - 1))
        )
        deadline = recovery.uncertainty_since + timedelta(seconds=_policy("MAX_AGE_SECONDS"))
        recovery.state = State.PENDING
        recovery.next_attempt_at = min(now + timedelta(seconds=delay), deadline)


def _supersede(recovery):
    recovery.state = State.SUPERSEDED
    recovery.outcome_code = Outcome.SUPERSEDED
    recovery.next_attempt_at = None
    _clear_claim(recovery)


def claim_capture(capture_id):
    with _locked_rows(capture_id) as (capture, artifact, recovery, _):
        now = timezone.now()
        if recovery.state == State.ESCALATED:
            return None
        if recovery.state == State.CLAIMED and recovery.claim_expires_at > now:
            return None
        if _protected(capture, artifact) or capture.status not in _UNRESOLVED:
            _supersede(recovery)
            recovery.save()
            return None
        if recovery.state not in (State.PENDING, State.CLAIMED, State.RESOLVED):
            return None
        if recovery.state == State.RESOLVED or _origin(capture) != recovery.uncertainty_since:
            # A later explicit Stop/error can reopen active-confirmed work, never its budget.
            recovery.uncertainty_since = _origin(capture)
            recovery.next_attempt_at = max(
                recovery.next_attempt_at or now,
                _origin(capture) + timedelta(seconds=_INITIAL_GRACE_SECONDS),
            )
        if recovery.next_attempt_at and recovery.next_attempt_at > now:
            recovery.state = State.PENDING
            _clear_claim(recovery)
            recovery.save()
            return None
        if _exhausted(recovery, now):
            _escalate(recovery, Outcome.EXHAUSTED, now)
            recovery.save()
            return None
        if recovery.state == State.CLAIMED:
            recovery.outcome_code = Outcome.UNKNOWN
        recovery.attempts += 1  # Charged before any HTTP; even a crash consumes this opportunity.
        recovery.state = State.CLAIMED
        recovery.claim_token = uuid.uuid4()
        recovery.claim_expires_at = now + timedelta(seconds=_policy("CLAIM_TTL_SECONDS"))
        recovery.next_attempt_at = recovery.claim_expires_at
        recovery.save()
        return Claim(
            capture.pk,
            recovery.claim_token,
            capture.kind,
            capture.provider_artifact_id,
            _identity(capture),
        )


def _metadata_time(value, *, recording):
    try:
        if recording:
            if type(value) not in (int, float) or not math.isfinite(value):
                return None
            return datetime.fromtimestamp(value, UTC)
        if not isinstance(value, str) or len(value) > 64:
            return None
        result = parse_datetime(value)
        return result if result and timezone.is_aware(result) else None
    except (ValueError, OverflowError, OSError):
        return None


def observe_metadata(claim, item):
    """Reduce an untrusted response to closed evidence; persist no response/body/location."""
    if not isinstance(item, dict):
        return Observation(Outcome.IDENTITY)
    _, room_name, room_id, kind, instance, artifact_id, session, _, _, verified_at = claim.identity
    recording = kind == "RECORDING"
    if not instance or not claim.identity[7] or not verified_at:
        return Observation(Outcome.IDENTITY)
    # No guaranteed instance field exists in these GET contracts. A conflicting supplied value
    # cannot override the existing binding, even when it appears as an undocumented extra.
    info = item.get("info")
    instances = [item[k] for k in ("instanceId", "instance_id") if k in item]
    if isinstance(info, dict) and "instanceId" in info:
        instances.append(info["instanceId"])
    if (
        ("info" in item and not isinstance(info, dict))
        or any(not isinstance(value, str) or not 1 <= len(value) <= 160 for value in instances)
        or (instances and any(value != instances[0] for value in instances))
    ):
        return Observation(Outcome.IDENTITY)
    if any(
        key in item and (not isinstance(item[key], str) or not 1 <= len(item[key]) <= maximum)
        for key, maximum in (("room_name", 128), ("roomId", 128), ("mtgSessionId", 160))
    ):
        return Observation(Outcome.IDENTITY)
    identity = ProviderIdentity(
        item.get("kind", kind),
        item.get("id" if recording else "transcriptId"),
        instances[0] if instances else None,
        item.get("room_name"),
        item.get("roomId"),
        item.get("mtgSessionId"),
    )
    if identity_conflict(
        identity,
        kind=kind,
        room_name=room_name,
        room_id=room_id,
        instance_id=instance,
        artifact_id=artifact_id,
        session_id=session,
        require_artifact=True,
        require_room_name=recording,
        require_room_id=not recording,
        require_known_session=True,
    ):
        return Observation(Outcome.IDENTITY)
    status = item.get("status")
    active, complete = ("in-progress", "finished") if recording else ("t_in_progress", "t_finished")
    if status not in (active, complete):
        return Observation(Outcome.UNKNOWN)
    duration = item.get("duration")
    try:
        duration = finite_number(duration, maximum=MAX_DURATION_SECONDS)
    except InvalidEvent:
        duration = None
    return Observation(
        Outcome.ACTIVE if status == active else Outcome.COMPLETED,
        Evidence.ACTIVE if status == active else Evidence.COMPLETED,
        started_at=_metadata_time(
            item.get("start_ts" if recording else "created_at"), recording=recording
        ),
        duration=duration,
    )


def _consent_checks(capture, consents):
    by_scope = {consent.scope: consent for consent in consents}
    media_ok = effective_consent(by_scope.get(media_scope(capture.room, capture.kind)))
    storage_ok = effective_consent(by_scope.get(ConsentScope.TRANSCRIPT_STORAGE))
    applicable_ok = (
        media_ok
        and capture.media_authorized_at is not None
        and (
            capture.kind != "TRANSCRIPTION"
            or not (capture.transcript_storage_enabled or capture.transcript_storage_authorized)
            or storage_ok
        )
    )
    return media_ok, storage_ok, applicable_ok


def apply_observation(claim, observation):
    with _locked_rows(claim.capture_id) as (capture, artifact, recovery, consents):
        previous_status = capture.status
        pending_created = False
        now = timezone.now()
        if recovery.state != State.CLAIMED or recovery.claim_token != claim.token:
            return  # A newer owner/evidence wins; do not rewrite even scheduling metadata.
        if _protected(capture, artifact) or capture.status not in _UNRESOLVED:
            _supersede(recovery)
        elif recovery.claim_expires_at <= now or _identity(capture) != claim.identity:
            recovery.outcome_code = Outcome.SUPERSEDED
            _retry(recovery, now)
        else:
            # A Stop/withdrawal committed during this GET establishes a new uncertainty phase;
            # only its age anchor changes. The charged lifetime budget is never reset.
            recovery.uncertainty_since = _origin(capture)
            recovery.last_checked_at = now
            recovery.outcome_code = observation.outcome
            recovery.provider_evidence = observation.evidence
            recovery.provider_failure_code = observation.failure_code
            _, _, applicable_ok = _consent_checks(capture, consents)
            if observation.evidence == Evidence.COMPLETED:
                capture.status = _capture_status_for_event(capture, "ready")
                if (
                    not capture.started_at
                    and observation.started_at
                    and observation.started_at <= now
                ):
                    capture.started_at = observation.started_at
                if capture.duration_seconds is None:
                    capture.duration_seconds = observation.duration
                # Neither the polling time nor generic updated_at is a physical end/ready time.
                capture.save(
                    update_fields=["status", "started_at", "duration_seconds", "updated_at"]
                )
                recovery.state = State.RESOLVED
                recovery.completion_confirmed_at = recovery.completion_confirmed_at or now
                recovery.next_attempt_at = None
                _clear_claim(recovery)
                # Preserve the existing custody policy for historically authorized media.
                # This eligibility path restores neither consent nor the provider storage switch.
                pending = ensure_pending_artifact(capture, publish_hint=False)
                pending_created = artifact is None and pending is not None
            elif observation.evidence == Evidence.ACTIVE:
                if _has_stop_intent(capture) or applicable_ok:
                    capture.status = _capture_status_for_event(capture, "started")
                    capture.save(update_fields=["status", "updated_at"])
                if not applicable_ok:
                    _escalate(recovery, Outcome.PRIVACY, now)
                elif _has_stop_intent(capture):
                    _retry(recovery, now)
                else:
                    recovery.state = State.RESOLVED
                    recovery.next_attempt_at = None
                    _clear_claim(recovery)
            else:
                _retry(recovery, now)
        recovery.save()
        if previous_status != capture.status or pending_created:
            from .media_realtime import media_changed_on_commit

            media_changed_on_commit(capture.room.appointment_id)
    log_capture_reconciliation(
        stage=CaptureStage.APPLY,
        kind=claim.kind,
        outcome=recovery.escalation_code or recovery.outcome_code,
        attempts=recovery.attempts,
        evidence=recovery.provider_evidence,
        retry_scheduled=recovery.state == State.PENDING,
        delay_seconds=(
            max(0, int((recovery.next_attempt_at - now).total_seconds()))
            if recovery.next_attempt_at
            else None
        ),
        terminal_confirmed=recovery.completion_confirmed_at is not None,
        escalation_required=recovery.escalated_at is not None,
    )


def reconcile_captures(*, client=None):
    counts = {
        key: 0 for key in ("disabled", "discovered", "considered", "claimed", "metadata_checks")
    }
    if not _policy("ENABLED") or not settings.DAILY_ENABLED:
        counts["disabled"] = 1
        return counts
    # Production I/O must never run inside an enclosing application transaction. Django's
    # artificial TestCase wrapper is permitted; real concurrency tests use autocommit sessions.
    if connection.in_atomic_block and any(
        not getattr(block, "_from_testcase", False) for block in connection.atomic_blocks
    ):
        raise RuntimeError("Reconciliation requires autocommit.")
    batch = _policy("BATCH_SIZE")
    counts["discovered"] = discover_captures(limit=batch * 5)
    now = timezone.now()
    ids = list(
        Recovery.objects.filter(
            Q(state=State.PENDING, next_attempt_at__lte=now)
            | Q(state=State.PENDING, next_attempt_at__isnull=True)
            | Q(state=State.CLAIMED, claim_expires_at__lte=now)
            | Q(state=State.RESOLVED, capture_id__in=_eligible_captures().values("pk"))
        )
        .order_by(Coalesce("next_attempt_at", "uncertainty_since"), "capture_id")
        .values_list("capture_id", flat=True)[:batch]
    )
    counts["considered"] = len(ids)
    for capture_id in ids:
        claim = claim_capture(capture_id)
        if claim is None:
            continue
        counts["claimed"] += 1
        if not claim.artifact_id or not claim.identity[9]:
            observation = Observation(Outcome.IDENTITY)
        else:
            try:
                metadata_client = client if client is not None else DailyClient.from_settings()
                counts["metadata_checks"] += 1
                item = metadata_client.get_capture_metadata(
                    kind=claim.kind,
                    artifact_id=claim.artifact_id,
                    timeout_seconds=_policy("TIMEOUT_SECONDS"),
                )
                observation = observe_metadata(claim, item)
            except DailyError as error:
                observation = Observation(
                    Outcome.UNAVAILABLE, failure_code=safe_daily_failure_code(error).value
                )
            except Exception:
                # Adapter/transport prose never reaches persistence, logs or Celery results.
                observation = Observation(Outcome.UNAVAILABLE)
        apply_observation(claim, observation)
    return counts
