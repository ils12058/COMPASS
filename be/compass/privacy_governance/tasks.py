"""Durable at-least-once dispatch, bounded claims and domain verification."""

import uuid
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from compass.audit import actions
from compass.audit.context import AuditContext
from compass.ecounseling.models import ECounselingMediaCapture
from compass.graduate_tracer.disposition import anonymize_response
from compass.integrations.daily import (
    DailyClient,
    DailyConfigurationError,
    DailyHTTPError,
    DailyInvalidResponse,
    DailyUnavailable,
)
from compass.tasks import CorrelationTask

from .retention import audit, discover_eligibility, enqueue, get_case, get_rule, revalidate
from .retention_models import (
    DispositionBlocker,
    DispositionCase,
    DispositionState,
    RetentionCategory,
)

MAX_ATTEMPTS = 3
CLAIM_TIMEOUT = timedelta(minutes=15)


class ProviderOutcomeUnverified(Exception):
    pass


class ExternalStorageRequired(Exception):
    pass


def dispose_provider_artifact(source, *, client):
    """Use documented IDs and terminal DELETE responses; discard all provider payloads."""
    artifact_id = source.provider_artifact_id
    if source.kind == "RECORDING":
        before = client.get_recording(artifact_id=artifact_id)
        if before.get("id") != artifact_id or before.get("status") != "finished":
            raise ProviderOutcomeUnverified()
        if before.get("storage_provider"):
            raise ExternalStorageRequired()
        result = client.delete_recording(artifact_id=artifact_id)
        if result.get("deleted") is not True or result.get("id") != artifact_id:
            raise ProviderOutcomeUnverified()
        if result.get("storage_provider"):
            raise ExternalStorageRequired()
    else:
        before = client.get_transcript(artifact_id=artifact_id)
        if before.get("transcriptId") != artifact_id:
            raise ProviderOutcomeUnverified()
        if before.get("outParams"):
            raise ExternalStorageRequired()
        if before.get("status") == "t_deleted":
            return  # Documented terminal reconciliation after a lost DELETE response.
        if before.get("status") != "t_finished":
            raise ProviderOutcomeUnverified()
        result = client.delete_transcript(artifact_id=artifact_id)
        if result.get("transcriptId") != artifact_id or result.get("status") != "t_deleted":
            raise ProviderOutcomeUnverified()
        if result.get("outParams"):
            raise ExternalStorageRequired()


def _failure(case_id, token, blocker, *, transient=False):
    with transaction.atomic():
        initial = get_case(case_id)
        get_rule(initial.rule_id, lock=True)
        case = get_case(case_id, lock=True)
        if case.state != DispositionState.PROCESSING or case.claim_token != token:
            return
        case.blocker = blocker
        case.claim_token = None
        if transient and case.attempts < MAX_ATTEMPTS:
            case.state = "QUEUED"
            case.next_attempt_at = timezone.now() + timedelta(seconds=60 * 2 ** (case.attempts - 1))
        else:
            case.state = (
                "RECONCILIATION_REQUIRED"
                if blocker
                in {
                    DispositionBlocker.PROVIDER_UNVERIFIED,
                    DispositionBlocker.EXTERNAL_STORAGE,
                    DispositionBlocker.WORKER_INTERRUPTED,
                }
                else "FAILED"
            )
            case.next_attempt_at = None
        case.revision += 1
        case.save()
        audit(AuditContext.system(), actions.DISPOSITION_FAILED, case, blocker=blocker)


@shared_task(
    name="compass.privacy_governance.execute_disposition",
    base=CorrelationTask,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_disposition(case_id):
    token = uuid.uuid4()
    with transaction.atomic():
        initial = get_case(case_id)
        rule = get_rule(initial.rule_id, lock=True)
        case = get_case(case_id, lock=True)
        now = timezone.now()
        if case.state != "QUEUED" or not case.approved_at or not case.approved_by_id:
            return
        if case.next_attempt_at and case.next_attempt_at > now:
            return
        if case.holds.filter(released_at__isnull=True).exists():
            case.state = "ON_HOLD"
            case.approved_at, case.approved_by = None, None
            case.revision += 1
            case.save()
            return
        source, blocker = revalidate(case, rule, now=now)
        if blocker:
            case.state, case.blocker = "NO_LONGER_ELIGIBLE", blocker
            case.approved_at, case.approved_by = None, None
            case.revision += 1
            case.save()
            audit(AuditContext.system(), actions.DISPOSITION_FAILED, case, blocker=blocker)
            return
        case.state, case.claim_token, case.started_at = "PROCESSING", token, now
        case.attempts += 1
        case.revision += 1
        case.save()
        audit(AuditContext.system(), actions.DISPOSITION_STARTED, case)
        if case.category == RetentionCategory.GRADUATE_TRACER:
            # Anonymization, verification, source removal, outcome and AuditEvent commit together.
            # A crash rolls the entire claim and treatment back, allowing safe redelivery.
            try:
                with transaction.atomic():
                    anonymize_response(source.pk)
            except ValueError:
                case.state, case.blocker, case.claim_token = (
                    "FAILED",
                    DispositionBlocker.VERIFICATION_FAILED,
                    None,
                )
                case.next_attempt_at = None
                case.revision += 1
                case.save()
                audit(AuditContext.system(), actions.DISPOSITION_FAILED, case, blocker=case.blocker)
                return
            case.state, case.completed_at, case.claim_token = "COMPLETED", now, None
            case.next_attempt_at = None
            case.revision += 1
            case.save()
            audit(AuditContext.system(), actions.DISPOSITION_COMPLETED, case)
            return
        source_version = source.updated_at
        artifact_id = source.provider_artifact_id

    # Never hold a PostgreSQL transaction across Daily HTTP. PROCESSING blocks new holds/retirement.
    try:
        dispose_provider_artifact(source, client=DailyClient.from_settings())
    except (DailyConfigurationError, DailyUnavailable):
        _failure(case_id, token, DispositionBlocker.PROVIDER_UNAVAILABLE, transient=True)
        return
    except DailyHTTPError as exc:
        transient = exc.status_code == 429 or exc.status_code >= 500
        _failure(
            case_id,
            token,
            DispositionBlocker.PROVIDER_UNAVAILABLE
            if transient
            else DispositionBlocker.PROVIDER_REJECTED,
            transient=transient,
        )
        return
    except (DailyInvalidResponse, ProviderOutcomeUnverified):
        _failure(case_id, token, DispositionBlocker.PROVIDER_UNVERIFIED)
        return
    except ExternalStorageRequired:
        _failure(case_id, token, DispositionBlocker.EXTERNAL_STORAGE)
        return

    with transaction.atomic():
        initial = get_case(case_id)
        get_rule(initial.rule_id, lock=True)
        case = get_case(case_id, lock=True)
        if case.state != "PROCESSING" or case.claim_token != token:
            return
        capture = ECounselingMediaCapture.objects.select_for_update().get(pk=case.source_id)
        if capture.updated_at != source_version or capture.provider_artifact_id != artifact_id:
            case.state, case.blocker = "RECONCILIATION_REQUIRED", DispositionBlocker.SOURCE_CHANGED
            case.claim_token, case.next_attempt_at = None, None
            case.revision += 1
            case.save()
            audit(AuditContext.system(), actions.DISPOSITION_FAILED, case, blocker=case.blocker)
            return
        capture.provider_artifact_id = None
        capture.artifact_disposed_at = timezone.now()
        capture.save(update_fields=["provider_artifact_id", "artifact_disposed_at", "updated_at"])
        capture.refresh_from_db()
        if capture.provider_artifact_id is not None or capture.artifact_disposed_at is None:
            raise ValueError("Provider disposition verification failed.")
        case.state, case.completed_at, case.claim_token = "COMPLETED", timezone.now(), None
        case.next_attempt_at, case.blocker = None, None
        case.revision += 1
        case.save()
        audit(AuditContext.system(), actions.DISPOSITION_COMPLETED, case)


@shared_task(base=CorrelationTask, name="compass.privacy_governance.discover_retention")
def discover_retention():
    return discover_eligibility()


@shared_task(base=CorrelationTask, name="compass.privacy_governance.recover_disposition")
def recover_disposition():
    now = timezone.now()
    # A stale provider claim may have reached Daily. Require deliberate reconciliation/retry.
    for case_id, token in DispositionCase.objects.filter(
        state="PROCESSING", started_at__lt=now - CLAIM_TIMEOUT
    ).values_list("id", "claim_token")[:100]:
        _failure(case_id, token, DispositionBlocker.WORKER_INTERRUPTED)
    ids = list(
        DispositionCase.objects.filter(
            state="QUEUED", next_attempt_at__lte=now, approved_at__isnull=False
        )
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:100]
    )
    for case_id in ids:
        enqueue(case_id)
    return len(ids)
