"""Version-two disposition verifies both live copies; V1 provider-only treatment is unchanged."""

from django.db import transaction
from django.utils import timezone

from compass.audit import actions
from compass.audit.context import AuditContext
from compass.ecounseling.artifacts import artifact_guard, delete_v2_provider
from compass.ecounseling.models import ECounselingMediaArtifact, ECounselingMediaCapture
from compass.integrations.daily import DailyClient
from compass.integrations.storage import ObjectStorage

from .retention import audit, get_case, get_rule
from .retention_models import DispositionBlocker
from .tasks import _failure


def execute_media_disposition(case_id, token, *, source_version, provider_id):
    initial = get_case(case_id)
    artifact = ECounselingMediaArtifact.objects.filter(capture_id=initial.source_id).first()
    if artifact is None:
        _failure(case_id, token, DispositionBlocker.LOCAL_ARTIFACT_MISSING)
        return
    with artifact_guard(artifact.pk) as acquired:
        if not acquired:
            _failure(case_id, token, DispositionBlocker.PROVIDER_CLEANUP_UNVERIFIED)
            return
        with transaction.atomic():
            get_rule(initial.rule_id, lock=True)
            case = get_case(case_id, lock=True)
            source = ECounselingMediaCapture.objects.select_for_update().get(pk=case.source_id)
            artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact.pk)
            if (
                case.state != "PROCESSING"
                or case.claim_token != token
                or source.updated_at != source_version
                or artifact.status != "STORED"
                or artifact.claim_token
            ):
                _failure(case_id, token, DispositionBlocker.SOURCE_CHANGED)
                return
            artifact_version, key = artifact.updated_at, artifact.object_key
            if not provider_id and artifact.provider_deleted_at is None:
                _failure(case_id, token, DispositionBlocker.PROVIDER_CLEANUP_UNVERIFIED)
                return
        # All network work is outside PostgreSQL transactions. PROCESSING blocks holds/retirement,
        # and the session advisory lock prevents ingestion/cleanup from touching this artifact.
        try:
            storage = ObjectStorage(alias="ecounseling_media")
            storage.validate_sensitive_policy()
            if artifact.storage_binding != storage.binding_identity():
                raise ValueError()
            if not key or not artifact.stored_at or not artifact.sha256:
                raise ValueError()
            if storage.exists(key):
                storage.delete(key)
            if storage.exists(key):
                raise ValueError()
        except Exception:
            _failure(case_id, token, DispositionBlocker.OBJECT_STORAGE_UNVERIFIED)
            return
        if provider_id:
            try:
                delete_v2_provider(source, DailyClient.from_settings())
            except Exception:
                _failure(case_id, token, DispositionBlocker.PROVIDER_CLEANUP_UNVERIFIED)
                return
        with transaction.atomic():
            get_rule(initial.rule_id, lock=True)
            case = get_case(case_id, lock=True)
            source = ECounselingMediaCapture.objects.select_for_update().get(pk=case.source_id)
            artifact = ECounselingMediaArtifact.objects.select_for_update().get(pk=artifact.pk)
            if (
                case.state != "PROCESSING"
                or case.claim_token != token
                or source.updated_at != source_version
                or source.provider_artifact_id != provider_id
                or artifact.updated_at != artifact_version
            ):
                _failure(case_id, token, DispositionBlocker.SOURCE_CHANGED)
                return
            now = timezone.now()
            artifact.status, artifact.disposed_at = "DISPOSED", now
            artifact.object_key, artifact.sha256 = None, None
            artifact.storage_binding = None
            artifact.content_type, artifact.size = None, None
            artifact.claim_token, artifact.claimed_at = None, None
            artifact.next_attempt_at, artifact.error_code = None, None
            if provider_id:
                artifact.provider_deleted_at = now
            artifact.save()
            source.provider_artifact_id, source.artifact_disposed_at = None, now
            source.save(
                update_fields=["provider_artifact_id", "artifact_disposed_at", "updated_at"]
            )
            case.state, case.completed_at, case.claim_token = "COMPLETED", now, None
            case.next_attempt_at, case.blocker = None, None
            case.revision += 1
            case.save()
            audit(AuditContext.system(), actions.DISPOSITION_COMPLETED, case)
