"""Rule governance, deterministic discovery and frozen single-record authorization."""

from datetime import UTC, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.audit import actions
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.errors import APIError
from compass.ecounseling.models import (
    ECounselingMediaArtifact,
    ECounselingMediaCapture,
    MediaCaptureKind,
    MediaCaptureStatus,
)
from compass.graduate_tracer.models import (
    GTS_SCHEMA_VERSION,
    GraduateTracerResponse,
    GraduateTracerStatus,
)

from .retention_models import (
    DispositionAction,
    DispositionBlocker,
    DispositionCase,
    DispositionHold,
    DispositionState,
    OperationalRetentionRule,
    RetentionCategory,
    RetentionRuleStatus,
    RetentionTrigger,
)

SUPPORTED = {
    RetentionCategory.GRADUATE_TRACER: (RetentionTrigger.SUBMITTED_AT, DispositionAction.ANONYMIZE),
    RetentionCategory.ECOUNSELING_RECORDING: (
        RetentionTrigger.MEDIA_READY_AT,
        DispositionAction.DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE,
    ),
    RetentionCategory.ECOUNSELING_TRANSCRIPT: (
        RetentionTrigger.MEDIA_READY_AT,
        DispositionAction.DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE,
    ),
}
SUPPORTED_CONTRACTS = {(category, 1): treatment for category, treatment in SUPPORTED.items()}
SUPPORTED_CONTRACTS.update(
    {
        (category, 2): (
            RetentionTrigger.MEDIA_READY_AT,
            DispositionAction.DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE,
        )
        for category in (
            RetentionCategory.ECOUNSELING_RECORDING,
            RetentionCategory.ECOUNSELING_TRANSCRIPT,
        )
    }
)
REVIEW_STATES = {
    DispositionState.READY,
    DispositionState.BLOCKED,
    DispositionState.NO_LONGER_ELIGIBLE,
    DispositionState.ON_HOLD,
}


def require(actor, capability):
    if not actor.is_active or not actor.has_capability(capability):
        raise APIError(403, "permission_denied", "Retention authority is required.")


def conflict(message="This record changed. Review its current state before submitting again."):
    raise APIError(409, "retention_state_changed", message)


def audit(context, action, item, *, blocker=None):
    rule = item if isinstance(item, OperationalRetentionRule) else item.rule
    metadata = {
        "category": rule.category,
        "contract_version": rule.contract_version,
        "disposition_action": rule.action,
        "rule_id": str(rule.pk),
        "rule_revision": rule.revision,
    }
    if isinstance(item, DispositionCase):
        metadata.update({"affected_count": 1, "state": item.state})
    if blocker:
        metadata["blocker"] = blocker
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.FAILED
        if action == actions.DISPOSITION_FAILED
        else AuditOutcome.SUCCESS,
        target_type="privacy.retention.rule"
        if isinstance(item, OperationalRetentionRule)
        else "privacy.disposition.case",
        target_id=item.pk,
        metadata=metadata,
    )


def _validate_rule(values):
    values.setdefault("contract_version", 1)
    if type(values["contract_version"]) is not int or SUPPORTED_CONTRACTS.get(
        (values["category"], values["contract_version"])
    ) != (values["trigger"], values["action"]):
        raise APIError(
            422, "invalid_retention_rule", "Unsupported category, trigger, or disposition."
        )
    if type(values["duration_days"]) is not int or not 1 <= values["duration_days"] <= 365000:
        raise APIError(
            422, "invalid_retention_rule", "Duration must be 1 to 365000 whole elapsed days."
        )
    for field, maximum in (("code", 64), ("label", 160), ("policy_reference", 500)):
        value = values[field]
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise APIError(
                422,
                "invalid_retention_rule",
                f"{field} must be nonblank and at most {maximum} characters.",
            )
        values[field] = value.strip()
    return values


def get_rule(rule_id, *, lock=False):
    qs = OperationalRetentionRule.objects
    if lock:
        qs = qs.select_for_update()
    item = qs.filter(pk=rule_id).first()
    if item is None:
        raise APIError(404, "retention_rule_not_found", "Retention rule not found.")
    return item


def get_case(case_id, *, lock=False):
    qs = DispositionCase.objects
    if lock:
        qs = qs.select_for_update()
    item = qs.filter(pk=case_id).first()
    if item is None:
        raise APIError(404, "disposition_case_not_found", "Disposition case not found.")
    return item


def _expected(item, expected_revision):
    if item.revision != expected_revision:
        conflict()


@transaction.atomic
def create_rule(*, actor, values, context):
    require(actor, "privacy_governance.retention.manage")
    values = _validate_rule(dict(values))
    try:
        with transaction.atomic():
            item = OperationalRetentionRule.objects.create(
                **values, created_by=actor, updated_by=actor
            )
    except IntegrityError as exc:
        raise APIError(409, "retention_state_changed", "The rule code is already in use.") from exc
    audit(context, actions.RETENTION_RULE_CREATED, item)
    return item


@transaction.atomic
def update_rule(*, actor, rule_id, expected_revision, values, context):
    require(actor, "privacy_governance.retention.manage")
    item = get_rule(rule_id, lock=True)
    _expected(item, expected_revision)
    if item.status != RetentionRuleStatus.DRAFT:
        conflict("Activated and retired rules are immutable. Create a new draft rule.")
    values = _validate_rule(dict(values) | {"code": item.code})
    for field, value in values.items():
        setattr(item, field, value)
    item.revision += 1
    item.updated_by = actor
    item.save()
    audit(context, actions.RETENTION_RULE_UPDATED, item)
    return item


@transaction.atomic
def transition_rule(*, actor, rule_id, expected_revision, activate, context):
    require(actor, "privacy_governance.retention.manage")
    item = get_rule(rule_id, lock=True)
    _expected(item, expected_revision)
    expected = RetentionRuleStatus.DRAFT if activate else RetentionRuleStatus.ACTIVE
    if item.status != expected:
        conflict()
    if not activate and item.cases.filter(state=DispositionState.PROCESSING).exists():
        conflict(
            "A disposition is already processing. Review its outcome before retiring the rule."
        )
    now = timezone.now()
    item.status = RetentionRuleStatus.ACTIVE if activate else RetentionRuleStatus.RETIRED
    item.updated_by = actor
    if activate:
        item.activated_by, item.activated_at = actor, now
    else:
        item.retired_by, item.retired_at = actor, now
    item.revision += 1
    try:
        with transaction.atomic():
            item.save()
    except IntegrityError as exc:
        raise APIError(
            409,
            "retention_state_changed",
            "Retire the active rule for this category and contract version first.",
        ) from exc
    audit(
        context,
        actions.RETENTION_RULE_ACTIVATED if activate else actions.RETENTION_RULE_RETIRED,
        item,
    )
    if not activate:
        for case in item.cases.select_for_update().exclude(state__in=("COMPLETED", "PROCESSING")):
            case.blocker = DispositionBlocker.RULE_INACTIVE
            case.state = (
                "ON_HOLD" if case.holds.filter(released_at__isnull=True).exists() else "BLOCKED"
            )
            case.approved_at, case.approved_by = None, None
            case.next_attempt_at = None
            case.revision += 1
            case.save()
    return item


def active(rule, now):
    return rule.status == RetentionRuleStatus.ACTIVE and rule.effective_on <= timezone.localdate(
        now
    )


def source_queryset(category, contract_version=1):
    if category == RetentionCategory.GRADUATE_TRACER:
        return GraduateTracerResponse.objects.filter(
            status=GraduateTracerStatus.SUBMITTED,
            instrument_schema_version=GTS_SCHEMA_VERSION,
            anonymized_at__isnull=True,
            student__isnull=False,
        )
    kind = (
        MediaCaptureKind.RECORDING
        if category == RetentionCategory.ECOUNSELING_RECORDING
        else MediaCaptureKind.TRANSCRIPTION
    )
    return ECounselingMediaCapture.objects.filter(
        kind=kind,
        ready_at__isnull=False,
        artifact_disposed_at__isnull=True,
        room__media_policy_version=contract_version,
    )


def source_eligibility(rule, source, now):
    if not active(rule, now):
        return None, DispositionBlocker.RULE_INACTIVE
    anchor = (
        source.submitted_at
        if rule.category == RetentionCategory.GRADUATE_TRACER
        else source.ready_at
    )
    if anchor is None:
        return None, DispositionBlocker.SOURCE_CHANGED
    eligible_at = anchor.astimezone(UTC) + timedelta(days=rule.duration_days)
    if eligible_at > now:
        return eligible_at, DispositionBlocker.SOURCE_CHANGED
    if rule.category != RetentionCategory.GRADUATE_TRACER:
        if (
            source.status != MediaCaptureStatus.READY
            or source.room.room_expires_at is None
            or source.room.room_expires_at > now
        ):
            return eligible_at, DispositionBlocker.MEDIA_NOT_TERMINAL
        if source.room.media_policy_version != rule.contract_version:
            return eligible_at, DispositionBlocker.SOURCE_CHANGED
        if rule.contract_version == 2:
            artifact = ECounselingMediaArtifact.objects.filter(capture=source).first()
            if artifact is None:
                return eligible_at, DispositionBlocker.LOCAL_ARTIFACT_MISSING
            if artifact.status != "STORED":
                return eligible_at, DispositionBlocker.INGESTION_INCOMPLETE
            if artifact.claim_token:
                return eligible_at, DispositionBlocker.PROVIDER_CLEANUP_UNVERIFIED
        elif not source.provider_artifact_id:
            return eligible_at, DispositionBlocker.ARTIFACT_ID_MISSING
    return eligible_at, None


def revalidate(case, rule, *, now, lock_source=True):
    if case.rule_id != rule.pk or case.contract_version != rule.contract_version:
        return None, DispositionBlocker.SOURCE_CHANGED
    qs = source_queryset(case.category, case.contract_version)
    if lock_source:
        if case.category == RetentionCategory.GRADUATE_TRACER:
            from compass.accounts.models import User

            student_id = qs.filter(pk=case.source_id).values_list("student_id", flat=True).first()
            if student_id:
                User.objects.select_for_update().get(pk=student_id)
        qs = qs.select_for_update()
    source = qs.filter(pk=case.source_id).first()
    if source is None:
        return None, DispositionBlocker.SOURCE_UNAVAILABLE
    eligible_at, blocker = source_eligibility(rule, source, now)
    if blocker:
        return source, blocker
    if (
        case.rule_revision != rule.revision
        or case.source_updated_at != source.updated_at
        or case.eligible_at != eligible_at
    ):
        return source, DispositionBlocker.SOURCE_CHANGED
    return source, None


def discover_eligibility(*, limit=200):
    """Bounded periodic discovery. Never creates approval or queues unapproved work."""
    now = timezone.now()
    changed = 0
    for rule_id in OperationalRetentionRule.objects.filter(
        status="ACTIVE", effective_on__lte=timezone.localdate(now)
    ).values_list("id", flat=True):
        with transaction.atomic():
            rule = get_rule(rule_id, lock=True)
            if not active(rule, now):
                continue
            anchor = (
                "submitted_at" if rule.category == RetentionCategory.GRADUATE_TRACER else "ready_at"
            )
            sources = source_queryset(rule.category, rule.contract_version).filter(
                **{anchor + "__lte": now - timedelta(days=rule.duration_days)}
            )
            # Discover new records in bounded pages; refresh existing cases separately.
            known = DispositionCase.objects.filter(
                category=rule.category, contract_version=rule.contract_version
            ).values("source_id")
            for source in sources.exclude(pk__in=known).order_by(anchor, "id")[:limit]:
                eligible_at, blocker = source_eligibility(rule, source, now)
                DispositionCase.objects.get_or_create(
                    category=rule.category,
                    source_id=source.pk,
                    defaults={
                        "rule": rule,
                        "contract_version": rule.contract_version,
                        "rule_revision": rule.revision,
                        "source_updated_at": source.updated_at,
                        "eligible_at": eligible_at,
                        "state": "BLOCKED" if blocker else "READY",
                        "blocker": blocker,
                    },
                )
                changed += 1
            for case in (
                DispositionCase.objects.select_for_update()
                .filter(
                    category=rule.category,
                    contract_version=rule.contract_version,
                    state__in=REVIEW_STATES,
                )
                .order_by("updated_at", "id")[:limit]
            ):
                source = (
                    source_queryset(rule.category, rule.contract_version)
                    .filter(pk=case.source_id)
                    .first()
                )
                eligible_at, blocker = (
                    source_eligibility(rule, source, now)
                    if source
                    else (None, DispositionBlocker.SOURCE_UNAVAILABLE)
                )
                state = (
                    "ON_HOLD"
                    if case.holds.filter(released_at__isnull=True).exists()
                    else "BLOCKED"
                    if blocker
                    else "READY"
                )
                if (
                    case.rule_id,
                    case.rule_revision,
                    case.state,
                    case.blocker,
                    case.source_updated_at,
                ) != (
                    rule.pk,
                    rule.revision,
                    state,
                    blocker,
                    source.updated_at if source else case.source_updated_at,
                ):
                    case.rule, case.rule_revision = rule, rule.revision
                    case.state, case.blocker = state, blocker
                    case.source_updated_at = source.updated_at if source else case.source_updated_at
                    case.eligible_at = eligible_at or case.eligible_at
                    case.revision += 1
                case.save()  # Touch refresh order so bounded refresh cannot starve later cases.
    return changed


@transaction.atomic
def change_hold(*, actor, case_id, expected_revision, reason, release, context):
    require(actor, "privacy_governance.retention.manage")
    # Every governance/worker path locks rule then case, to avoid retirement/claim races.
    initial = get_case(case_id)
    rule = get_rule(initial.rule_id, lock=True)
    case = get_case(case_id, lock=True)
    _expected(case, expected_revision)
    if case.state in {DispositionState.PROCESSING, DispositionState.COMPLETED}:
        conflict("Processing has already started or completed; a hold can no longer prevent it.")
    hold = case.holds.filter(released_at__isnull=True).first()
    if release:
        if hold is None:
            conflict()
        hold.released_by, hold.released_at = actor, timezone.now()
        hold.save()
        _, blocker = revalidate(case, rule, now=timezone.now())
        case.state = "BLOCKED" if blocker else "READY"
        case.blocker = blocker
    else:
        if hold is not None:
            conflict()
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
            raise APIError(
                422,
                "invalid_disposition_hold",
                "Use a safe nonblank administrative reason of at most 240 characters.",
            )
        DispositionHold.objects.create(case=case, reason=reason.strip(), placed_by=actor)
        case.state = "ON_HOLD"
    # Revokes a queued authorization; releasing a hold is never implicit reapproval.
    case.approved_by, case.approved_at = None, None
    case.claim_token, case.next_attempt_at = None, None
    case.revision += 1
    case.save()
    audit(
        context, actions.RETENTION_HOLD_RELEASED if release else actions.RETENTION_HOLD_PLACED, case
    )
    return case


def enqueue(case_id):
    from .tasks import execute_disposition

    try:
        execute_disposition.delay(str(case_id))
    except Exception:
        # Durable QUEUED state is the outbox. Beat recovers dispatch without changing approval.
        pass


@transaction.atomic
def approve_case(*, actor, case_id, expected_revision, context, retry=False):
    require(actor, "privacy_governance.retention.approve")
    initial = get_case(case_id)
    rule = get_rule(initial.rule_id, lock=True)
    case = get_case(case_id, lock=True)
    _expected(case, expected_revision)
    permitted = (
        {DispositionState.FAILED, DispositionState.RECONCILIATION_REQUIRED}
        if retry
        else {DispositionState.READY}
    )
    if case.state not in permitted or case.holds.filter(released_at__isnull=True).exists():
        conflict("This case is held or no longer ready. Review its current state.")
    _, blocker = revalidate(case, rule, now=timezone.now())
    if blocker:
        conflict("Eligibility or rule state changed. Refresh discovery and review again.")
    if retry:
        if case.manual_retries >= 3 or case.blocker == DispositionBlocker.EXTERNAL_STORAGE:
            conflict(
                "Deployment-owned reconciliation is required; automatic retries are unavailable."
            )
        case.manual_retries += 1
    case.approved_by, case.approved_at = actor, timezone.now()
    case.state = "APPROVED"
    case.attempts, case.blocker = 0, None
    case.revision += 1
    case.save()
    audit(
        context,
        actions.DISPOSITION_RETRY_AUTHORIZED if retry else actions.DISPOSITION_APPROVED,
        case,
    )
    case.state = "QUEUED"
    case.next_attempt_at = timezone.now()
    case.save(update_fields=["state", "next_attempt_at", "updated_at"])
    transaction.on_commit(lambda: enqueue(case.pk))
    return case
