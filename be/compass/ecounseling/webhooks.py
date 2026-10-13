"""Transactional signed-event provenance, small completion replay and truthful anomalies."""

from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from compass.integrations.daily import DailyClient, DailyError, safe_daily_failure_code
from compass.privacy_governance.retention_models import DispositionCase

from .diagnostics import log_media_webhook
from .media import (
    _capture_status_for_event,
    _has_stop_intent,
    _provider_ack,
    effective_consent,
    media_scope,
)
from .models import (
    CaptureReconciliationOutcome,
    CaptureReconciliationState,
    ConsentScope,
    ECounselingCaptureReconciliation,
    ECounselingConsent,
    ECounselingMediaArtifact,
    ECounselingRoom,
)
from .models import (
    DailyWebhookReceipt as Receipt,
)
from .models import (
    ECounselingMediaCapture as Capture,
)
from .models import (
    WebhookAnomaly as Anomaly,
)
from .models import (
    WebhookMitigation as Mitigation,
)
from .models import (
    WebhookOutcome as Outcome,
)
from .models import (
    WebhookSeverity as Severity,
)
from .provider_identity import ProviderIdentity, capture_identity_conflict
from .services import (
    ECounselingInvalidWebhook,
    ECounselingProviderUnavailable,
    WebhookProcessingResult,
)
from .webhook_events import InvalidEvent, ValidatedEvent, identifier, validate_event

REPLAY_LIMIT = 20
REPLAY_ATTEMPTS = 6
REPLAY_AGE = timedelta(hours=1)
REPLAY_DELAY = timedelta(seconds=60)


def _stored_event(receipt):
    kind = (
        "MEETING"
        if receipt.event_type.startswith("meeting.")
        else "RECORDING"
        if receipt.event_type.startswith("recording.")
        else "TRANSCRIPTION"
    )
    return ValidatedEvent(
        receipt.event_type,
        receipt.provider_event_id,
        receipt.dispatch_at,
        ProviderIdentity(
            kind,
            receipt.provider_artifact_id,
            receipt.provider_instance_id,
            receipt.provider_room_name,
            receipt.provider_room_id,
            receipt.provider_session_id,
        ),
        receipt.provider_status,
        receipt.provider_started_at,
        receipt.provider_occurred_at,
        receipt.duration_seconds,
    )


def _event_defaults(event):
    identity = event.identity
    return dict(
        event_type=event.event_type,
        dispatch_at=event.dispatch_at,
        provider_occurred_at=event.occurred_at,
        provider_started_at=event.started_at,
        provider_instance_id=identity.instance_id,
        provider_artifact_id=identity.artifact_id,
        provider_room_name=identity.room_name,
        provider_room_id=identity.room_id,
        provider_session_id=identity.session_id,
        provider_status=event.status,
        duration_seconds=event.duration,
        processing_outcome=Outcome.UNRESOLVED,
        mitigation_state=Mitigation.NONE,
    )


def _contradicts(receipt, event):
    if receipt.event_type != event.event_type:
        return True
    stored = _stored_event(receipt).identity
    incoming = event.identity
    return any(
        old is not None and new is not None and old != new
        for old, new in zip(
            (
                stored.instance_id,
                stored.artifact_id,
                stored.room_name,
                stored.room_id,
                stored.session_id,
            ),
            (
                incoming.instance_id,
                incoming.artifact_id,
                incoming.room_name,
                incoming.room_id,
                incoming.session_id,
            ),
            strict=True,
        )
    )


def _outcome(receipt, outcome, code=None, *, urgent=False):
    receipt.processing_outcome = outcome
    receipt.anomaly_code = code
    receipt.severity = Severity.PRIVACY if urgent else Severity.WARNING if code else None
    receipt.operator_review_required = code is not None
    receipt.next_attempt_at = None
    if code:
        receipt.mitigation_state = Mitigation.REVIEW if urgent else Mitigation.NONE


def _supersede_reconciliation(capture):
    recovery = (
        ECounselingCaptureReconciliation.objects.select_for_update().filter(capture=capture).first()
    )
    if recovery is not None:
        recovery.state = CaptureReconciliationState.SUPERSEDED
        recovery.outcome_code = CaptureReconciliationOutcome.SUPERSEDED
        recovery.next_attempt_at = recovery.claim_token = recovery.claim_expires_at = None
        recovery.save(
            update_fields=[
                "state",
                "outcome_code",
                "next_attempt_at",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )


def _conflict(receipt):
    receipt.event_id_conflict = True
    _outcome(receipt, Outcome.CONFLICT, Anomaly.EVENT_ID, urgent=True)
    # Preserve original accepted fields. Only an applied contradictory delivery invalidates a
    # previously established binding; a foreign event alone cannot rewrite a good capture.
    if receipt.applied_at and receipt.capture_id:
        room_id = Capture.objects.values_list("room_id", flat=True).get(pk=receipt.capture_id)
        ECounselingRoom.objects.select_for_update().get(pk=room_id)
        list(
            ECounselingConsent.objects.select_for_update().filter(room_id=room_id).order_by("scope")
        )
        capture = Capture.objects.select_for_update().get(pk=receipt.capture_id)
        ECounselingMediaArtifact.objects.select_for_update().filter(capture=capture).first()
        capture.provider_binding_quarantined_at = (
            capture.provider_binding_quarantined_at or timezone.now()
        )
        capture.save(update_fields=["provider_binding_quarantined_at", "updated_at"])
        _supersede_reconciliation(capture)


def _candidate(event):
    identity = event.identity
    query = Capture.objects.select_related("room").filter(kind=identity.kind)
    matches = list(
        (
            query.filter(provider_artifact_id=identity.artifact_id)
            if event.completion
            else query.filter(provider_instance_id=identity.instance_id)
        )[:2]
    )
    if len(matches) == 1:
        return matches[0].room, matches[0], None
    if len(matches) > 1:
        return None, None, Anomaly.IDENTITY
    room = (
        ECounselingRoom.objects.filter(daily_room_name=identity.room_name).first()
        if identity.room_name
        else None
    )
    if room is None:
        return None, None, Anomaly.UNKNOWN_ROOM if identity.room_name else Anomaly.UNKNOWN_INSTANCE
    capture = query.filter(room=room).first()
    if capture is None:
        return room, None, Anomaly.RESERVATION
    return room, capture, None


def _protected(capture, artifact):
    return bool(
        capture.artifact_disposed_at
        or (
            artifact
            and (
                artifact.status in ("STORED", "DISPOSED")
                or artifact.disposed_at
                or artifact.provider_deleted_at
            )
        )
        or DispositionCase.objects.filter(
            source_id=capture.pk, state__in=("PROCESSING", "COMPLETED")
        ).exists()
    )


def _consent_ok(capture, consents):
    scopes = {row.scope: row for row in consents}
    media = scopes.get(media_scope(capture.room, capture.kind))
    storage = scopes.get(ConsentScope.TRANSCRIPT_STORAGE)
    ok = effective_consent(media) and (
        capture.kind != "TRANSCRIPTION"
        or not capture.transcript_storage_enabled
        or effective_consent(storage)
    )
    withdrawn = bool(
        (media and media.withdrawn_at)
        or (capture.transcript_storage_enabled and storage and storage.withdrawn_at)
    )
    return ok, Anomaly.WITHDRAWN if withdrawn else Anomaly.AUTHORIZATION


def _defer(receipt):
    _outcome(receipt, Outcome.UNRESOLVED, Anomaly.IDENTITY)
    if (
        receipt.processing_attempts < REPLAY_ATTEMPTS
        and timezone.now() < receipt.received_at + REPLAY_AGE
    ):
        receipt.next_attempt_at = timezone.now() + REPLAY_DELAY


def _apply(receipt, event):
    room, candidate, reason = _candidate(event)
    if room is None:
        _outcome(receipt, Outcome.ANOMALY, reason, urgent=event.started)
        return None
    room = ECounselingRoom.objects.select_for_update().get(pk=room.pk)
    consents = list(
        ECounselingConsent.objects.select_for_update().filter(room=room).order_by("scope")
    )
    capture = (
        Capture.objects.select_for_update().filter(room=room, kind=event.identity.kind).first()
    )
    receipt.ecounseling_room = room
    receipt.capture = capture
    if capture is None or candidate is None or capture.pk != candidate.pk:
        _outcome(receipt, Outcome.ANOMALY, Anomaly.RESERVATION, urgent=event.started)
        return None
    capture.room = room
    artifact = ECounselingMediaArtifact.objects.select_for_update().filter(capture=capture).first()
    if _protected(capture, artifact):
        _outcome(receipt, Outcome.PROTECTED, Anomaly.CLEANUP, urgent=event.started)
        _supersede_reconciliation(capture)
        return None
    if capture.provider_binding_quarantined_at:
        _outcome(receipt, Outcome.ANOMALY, Anomaly.QUARANTINED, urgent=True)
        return None
    reason = capture_identity_conflict(
        capture,
        event.identity,
        require_instance=not event.completion,
        require_artifact=event.completion,
        require_room_name=not (event.event_type == "recording.started"),
        require_known_session=event.completion,
    )
    if reason:
        if (
            reason == Anomaly.ARTIFACT
            and event.started
            and event.identity.instance_id == capture.provider_instance_id
        ):
            capture.provider_binding_quarantined_at = (
                capture.provider_binding_quarantined_at or timezone.now()
            )
            capture.save(update_fields=["provider_binding_quarantined_at", "updated_at"])
            _supersede_reconciliation(capture)
        if (
            reason == Anomaly.IDENTITY
            and event.completion
            and not capture.provider_artifact_id
            and capture.media_authorized_at
            and capture.provider_instance_id
        ):
            _defer(receipt)
        else:
            _outcome(
                receipt,
                Outcome.UNRESOLVED if reason == Anomaly.IDENTITY else Outcome.CONFLICT,
                reason,
                urgent=event.started,
            )
        return None
    if (
        capture.status == "NOT_STARTED"
        or not capture.provider_instance_id
        or not capture.media_authorized_at
    ):
        _outcome(receipt, Outcome.ANOMALY, Anomaly.RESERVATION, urgent=event.started)
        return None
    if event.completion and not capture.provider_binding_verified_at:
        _defer(receipt)
        return None
    receipt.identity_verified = True
    if event.started and room.room_expires_at and room.room_expires_at <= timezone.now():
        terminal = capture.status in ("READY", "STOPPED")
        _outcome(
            receipt,
            Outcome.TERMINAL if terminal else Outcome.ANOMALY,
            Anomaly.EXPIRED_ROOM,
            urgent=not terminal,
        )
        return None
    if capture.status in ("READY", "STOPPED") and not event.started and not event.completion:
        _outcome(receipt, Outcome.TERMINAL)
        return None
    ok, consent_code = _consent_ok(capture, consents)
    now = timezone.now()
    _outcome(receipt, Outcome.APPLIED)
    was_stopping = _has_stop_intent(capture)
    mitigation = None
    if event.started:
        # Only an exact authorized Start reservation establishes a new artifact/session.
        capture.provider_artifact_id = capture.provider_artifact_id or event.identity.artifact_id
        capture.provider_binding_verified_at = capture.provider_binding_verified_at or now
        capture.provider_session_id = capture.provider_session_id or event.identity.session_id
        capture.started_at = capture.started_at or event.started_at
        if capture.status not in ("READY", "STOPPED") and not ok:
            capture.status = "STOP_REQUESTED"
            capture.stop_requested_at = capture.stop_requested_at or now
            capture.error_code = capture.error_code or "CONSENT_NOT_EFFECTIVE"
            _outcome(receipt, Outcome.APPLIED, consent_code, urgent=True)
            # The recording operation is room-scoped and cannot uniquely target this instance.
            # Preserve explicit authorized withdrawal operations, but never issue this automatic
            # recording backstop from a delayed event. The existing targeted transcription path
            # remains one-shot after exact provenance and a durable attempt reservation.
            if not was_stopping and capture.kind == "TRANSCRIPTION":
                receipt.mitigation_state = Mitigation.ATTEMPTED
                receipt.mitigation_attempted_at = now
                mitigation = receipt.pk
        else:
            capture.status = _capture_status_for_event(capture, "started")
    elif event.completion:
        capture.status = _capture_status_for_event(capture, "ready")
        capture.started_at = capture.started_at or event.started_at
        if capture.duration_seconds is None:
            capture.duration_seconds = event.duration
        capture.ready_at = capture.ready_at or event.dispatch_at
        if (
            capture.kind == "RECORDING"
            and capture.ended_at is None
            and capture.started_at
            and capture.duration_seconds is not None
        ):
            if event.duration is not None:
                try:
                    capture.ended_at = capture.started_at + timedelta(seconds=event.duration)
                except OverflowError:
                    pass  # Keep an ambiguous historical time rather than inventing a cutoff.
        _supersede_reconciliation(capture)
        # Keep historical anomaly evidence, while distinguishing a proven terminal capture.
        # Other event-ID row locks are deliberately not taken under capture locks.
    else:
        capture.status = _capture_status_for_event(capture, "error")
        capture.failed_at = capture.failed_at or event.occurred_at or receipt.received_at
        capture.error_code = capture.error_code or "PROVIDER_ERROR"
    capture.save()
    receipt.applied_at = now
    if event.completion:
        from .artifacts import ensure_pending_artifact

        ensure_pending_artifact(capture)
    return mitigation


def _after_commit(callback):
    # Pytest's TestCase wrapper is artificial. Every real application transaction must commit
    # before provider I/O or cross-receipt callbacks; PostgreSQL concurrency tests prove this.
    if any(not getattr(block, "_from_testcase", False) for block in connection.atomic_blocks):
        transaction.on_commit(callback)
    else:
        callback()


def _run_policy_stop(receipt_id):
    try:
        with transaction.atomic():
            receipt = Receipt.objects.select_for_update().get(pk=receipt_id)
            if receipt.mitigation_state != Mitigation.ATTEMPTED or not receipt.capture_id:
                return
            room = ECounselingRoom.objects.select_for_update().get(pk=receipt.capture.room_id)
            consents = list(
                ECounselingConsent.objects.select_for_update().filter(room=room).order_by("scope")
            )
            capture = Capture.objects.select_for_update().get(pk=receipt.capture_id)
            capture.room = room
            artifact = (
                ECounselingMediaArtifact.objects.select_for_update().filter(capture=capture).first()
            )
            reason = capture_identity_conflict(
                capture,
                _stored_event(receipt).identity,
                require_instance=True,
                require_artifact=True,
            )
            if (
                reason
                or receipt.event_id_conflict
                or capture.provider_binding_quarantined_at
                or _protected(capture, artifact)
                or capture.status != "STOP_REQUESTED"
                or _consent_ok(capture, consents)[0]
                or not settings.DAILY_ENABLED
                or not room.provisioned_at
                or capture.kind != "TRANSCRIPTION"
            ):
                receipt.mitigation_state = Mitigation.REVIEW
                receipt.save(update_fields=["mitigation_state"])
                return
            name, instance = room.daily_room_name, capture.provider_instance_id
        # The existing verified policy Stop runs once, after its durable attempt reservation.
        failure = None
        try:
            client = DailyClient.from_settings()
            _provider_ack(client.stop_transcription(room_name=name, instance_id=instance))
        except DailyError as exc:
            failure = safe_daily_failure_code(exc)
        except Exception:
            failure = safe_daily_failure_code(Exception())
        with transaction.atomic():
            receipt = Receipt.objects.select_for_update().get(pk=receipt_id)
            receipt.mitigation_state = Mitigation.FAILED if failure else Mitigation.ACK
            receipt.mitigation_failure_code = failure
            receipt.save(update_fields=["mitigation_state", "mitigation_failure_code"])
        log_media_webhook(receipt)
    except DatabaseError:
        # The committed reservation truthfully remains outcome-unknown. No automatic Stop retry.
        return


def process_event(*, event_type, event_id, event_ts, payload):
    try:
        identifier(event_id)
    except InvalidEvent:
        raise ECounselingInvalidWebhook("Daily webhook event ID is invalid.") from None
    try:
        event = validate_event(
            event_type=event_type, event_id=event_id, event_ts=event_ts, payload=payload
        )
    except InvalidEvent:
        event = None
    mitigation = None
    replay_capture = None
    try:
        with transaction.atomic():
            receipt, created = Receipt.objects.get_or_create(
                provider_event_id=event_id,
                defaults=_event_defaults(event)
                if event
                else {"event_type": event_type, "processing_outcome": Outcome.MALFORMED},
            )
            receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
            if not created:
                receipt.duplicate_count = min(2**31 - 1, receipt.duplicate_count + 1)
            if event is None:
                if created or receipt.event_type == event_type:
                    _outcome(receipt, Outcome.MALFORMED, Anomaly.MALFORMED)
                else:
                    _conflict(receipt)
            elif not created and (
                _contradicts(receipt, event)
                or (receipt.processing_outcome == Outcome.MALFORMED and not receipt.applied_at)
            ):
                _conflict(receipt)
            elif receipt.processing_outcome == Outcome.HISTORICAL:
                pass  # Historical receipts never become retroactively verified.
            elif not created and receipt.processing_outcome not in (Outcome.UNRESOLVED,):
                # New optional contradictory evidence must not hide behind event-ID deduplication.
                if receipt.capture_id and receipt.applied_at:
                    capture = Capture.objects.select_related("room").get(pk=receipt.capture_id)
                    if capture_identity_conflict(capture, event.identity):
                        _conflict(receipt)
            elif (
                not created and receipt.next_attempt_at and receipt.next_attempt_at > timezone.now()
            ):
                pass  # Duplicate delivery cannot consume the delayed automatic retry budget.
            elif event.identity.kind == "MEETING":
                receipt.ecounseling_room = ECounselingRoom.objects.filter(
                    daily_room_name=event.identity.room_name
                ).first()
                _outcome(
                    receipt,
                    Outcome.ACCEPTED if receipt.ecounseling_room else Outcome.ANOMALY,
                    None if receipt.ecounseling_room else Anomaly.UNKNOWN_ROOM,
                )
                receipt.processing_attempts += 1
            else:
                # Redelivery reuses the original approved evidence; it cannot replace times or
                # duration by changing an otherwise identical delivery.
                event = event if created else _stored_event(receipt)
                if (
                    receipt.processing_attempts < REPLAY_ATTEMPTS
                    and timezone.now() < receipt.received_at + REPLAY_AGE
                ):
                    receipt.processing_attempts += 1
                    mitigation = _apply(receipt, event)
                    if (
                        event.started
                        and receipt.identity_verified
                        and receipt.processing_outcome == Outcome.APPLIED
                    ):
                        replay_capture = receipt.capture_id
                else:
                    receipt.next_attempt_at = None
                    receipt.operator_review_required = True
            receipt.processed_at = timezone.now()
            receipt.save()
    except DatabaseError:
        raise ECounselingProviderUnavailable(
            "Daily webhook processing is temporarily unavailable."
        ) from None
    _after_commit(lambda: log_media_webhook(receipt))
    if mitigation:
        _after_commit(lambda: _run_policy_stop(mitigation))
    if replay_capture:
        _after_commit(lambda: replay_for_capture(replay_capture))
    return WebhookProcessingResult(accepted=True, duplicate=not created, supported=True)


def replay_receipt(receipt_id, *, binding_established=False):
    try:
        with transaction.atomic():
            receipt = Receipt.objects.select_for_update().get(pk=receipt_id)
            now = timezone.now()
            if (
                receipt.processing_outcome != Outcome.UNRESOLVED
                or receipt.event_id_conflict
                or not receipt.event_type.endswith(".ready-to-download")
                or not receipt.dispatch_at
            ):
                return False
            if (
                not binding_established
                and receipt.next_attempt_at
                and receipt.next_attempt_at > now
            ):
                return False
            if (
                receipt.processing_attempts >= REPLAY_ATTEMPTS
                or now >= receipt.received_at + REPLAY_AGE
            ):
                receipt.next_attempt_at = None
                receipt.operator_review_required = True
            else:
                receipt.processing_attempts += 1
                _apply(receipt, _stored_event(receipt))
            receipt.processed_at = now
            receipt.save()
        _after_commit(lambda: log_media_webhook(receipt))
        return True
    except DatabaseError:
        raise ECounselingProviderUnavailable(
            "Daily webhook replay is temporarily unavailable."
        ) from None


def replay_for_capture(capture_id):
    capture = Capture.objects.select_related("room").get(pk=capture_id)
    ids = list(
        Receipt.objects.filter(
            processing_outcome=Outcome.UNRESOLVED,
            event_id_conflict=False,
            provider_artifact_id=capture.provider_artifact_id,
            provider_room_name=capture.room.daily_room_name,
            event_type="recording.ready-to-download"
            if capture.kind == "RECORDING"
            else "transcript.ready-to-download",
            next_attempt_at__isnull=False,
        )
        .order_by("received_at", "pk")
        .values_list("pk", flat=True)[:REPLAY_LIMIT]
    )
    for receipt_id in ids:
        replay_receipt(receipt_id, binding_established=True)


def replay_due_events():
    if not settings.ECOUNSELING_WEBHOOK_REPLAY_ENABLED:
        return 0
    ids = list(
        Receipt.objects.filter(
            processing_outcome=Outcome.UNRESOLVED,
            event_id_conflict=False,
            next_attempt_at__lte=timezone.now(),
            event_type__in=("recording.ready-to-download", "transcript.ready-to-download"),
        )
        .order_by("next_attempt_at", "received_at", "pk")
        .values_list("pk", flat=True)[:REPLAY_LIMIT]
    )
    return sum(replay_receipt(receipt_id) for receipt_id in ids)
