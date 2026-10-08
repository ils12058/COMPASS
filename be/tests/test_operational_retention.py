"""Governance boundaries, real anonymization and fake-only provider disposition."""

import json
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.accounts.services import effective_capabilities
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.models import TOTPFactor
from compass.common.errors import APIError
from compass.common.institutional_time import institution_today
from compass.ecounseling.media import process_media_webhook_event
from compass.ecounseling.models import ECounselingConsent, ECounselingMediaCapture, ECounselingRoom
from compass.graduate_tracer.disposition import (
    ANALYTICAL_FIELDS,
    anonymize_response,
    verify_anonymized,
)
from compass.graduate_tracer.models import (
    GraduateTracerEducation,
    GraduateTracerProfessionalExam,
    GraduateTracerResponse,
    GraduateTracerTraining,
)
from compass.graduate_tracer.participation import GraduateTracerDisposedParticipation
from compass.integrations.daily import DailyClient, DailyHTTPError, DailyUnavailable
from compass.privacy_governance import retention
from compass.privacy_governance.retention_models import DispositionCase, OperationalRetentionRule
from compass.privacy_governance.tasks import execute_disposition, recover_disposition
from compass.reports.graduate_tracer import build_graduate_tracer_report
from tests.graduate_tracer_test_helpers import encrypted_row
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_head,
    make_user,
    patch_json,
    post_json,
    sync_policy,
)

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/privacy/retention"
CAPS = {f"privacy_governance.retention.{suffix}" for suffix in ("view", "manage", "approve")}


@pytest.fixture
def dpo():
    sync_policy()
    return make_dpo()


def rule_values(category="GRADUATE_TRACER"):
    trigger, action = retention.SUPPORTED[category]
    return {
        "code": "SYNTHETIC-TEST",
        "label": "Synthetic test rule",
        "category": category,
        "trigger": trigger,
        "action": action,
        "duration_days": 30,
        "policy_reference": "TEST FIXTURE ONLY - not institutional policy",
        "effective_on": institution_today(),
    }


def active_rule(dpo, category="GRADUATE_TRACER"):
    item = retention.create_rule(
        actor=dpo, values=rule_values(category), context=AuditContext.user(dpo)
    )
    return retention.transition_rule(
        actor=dpo,
        rule_id=item.pk,
        expected_revision=item.revision,
        activate=True,
        context=AuditContext.user(dpo),
    )


def tracer(email="graduate@example.edu", **values):
    student = make_user(email, role="STUDENT")
    student.student_lifecycle_status = "GRADUATED"
    student.save()
    return encrypted_row(
        GraduateTracerResponse,
        student=student,
        status="SUBMITTED",
        submitted_at=timezone.now() - timedelta(days=31),
        name_snapshot="Confidential Name",
        email_snapshot="private@example.edu",
        permanent_address_snapshot="Private address",
        telephone_contact_numbers_snapshot="secret-phone",
        mobile_number_snapshot="secret-mobile",
        province="specific-location",
        curriculum_improvement_suggestions="Confidential curriculum narrative",
        present_occupation="Specific named employer",
        sex="FEMALE",
        current_employment_state="EMPLOYED",
        employer_business_line="EDUCATION",
        **values,
    )


def discovered_case(source):
    retention.discover_eligibility()
    return DispositionCase.objects.get(source_id=source.pk)


def approve(dpo, case):
    return retention.approve_case(
        actor=dpo, case_id=case.pk, expected_revision=case.revision, context=AuditContext.user(dpo)
    )


@pytest.mark.parametrize(
    "role", ["INSTITUTIONAL_OFFICER", "IT_ADMIN", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT"]
)
def test_only_dpo_baseline_and_backend_denies_other_roles(dpo, role):
    assert CAPS <= effective_capabilities(dpo)
    other = make_user("other@example.edu", role=role)
    assert CAPS.isdisjoint(effective_capabilities(other))
    client = auth_client(other, recent_mfa=True)
    assert client.get(f"{ROOT}/summary").status_code == 403
    assert post_json(client, f"{ROOT}/rules", rule_values()).status_code == 403


def test_dependencies_overrides_and_confidential_content_boundary(dpo):
    assert CAPS.isdisjoint(effective_capabilities(make_head()))
    assert not any(
        code.startswith(
            (
                "counseling.",
                "inventory.",
                "graduate_tracer.",
                "ecounseling.",
                "exit_interviews.",
                "referrals.",
                "routine_interviews.",
            )
        )
        for code in effective_capabilities(dpo)
    )
    client = auth_client(dpo)
    assert client.get("/api/v1/graduate-tracer/responses").status_code == 403
    for suffix in ("view", "manage", "approve"):
        code = f"privacy_governance.retention.{suffix}"
        UserCapabilityOverride.objects.create(
            user=dpo,
            capability=Capability.objects.get(code=code),
            effect="REVOKE" if suffix == "view" else "GRANT",
            reason="Test authority",
        )
    assert CAPS.isdisjoint(effective_capabilities(dpo))
    UserCapabilityOverride.objects.filter(
        user=dpo, capability__code="privacy_governance.retention.view"
    ).delete()
    assert CAPS <= effective_capabilities(dpo)
    officer = make_user("override@example.edu")
    for code in CAPS:
        UserCapabilityOverride.objects.create(
            user=officer,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Test exception",
        )
    assert CAPS <= effective_capabilities(officer)


def test_drafting_no_mfa_activation_approval_and_retirement_step_up(dpo):
    client = auth_client(dpo)
    result = post_json(client, f"{ROOT}/rules", rule_values())
    assert result.status_code == 201, result.content
    item = result.json()
    result = patch_json(
        client,
        f"{ROOT}/rules/{item['id']}",
        {key: value for key, value in rule_values().items() if key != "code"}
        | {"expected_revision": item["revision"]},
    )
    assert result.status_code == 200
    item = result.json()
    url = f"{ROOT}/rules/{item['id']}/activate"
    result = post_json(client, url, {"expected_revision": item["revision"]})
    assert result.status_code == 403 and result.json()["error"]["code"] == "mfa_setup_required"
    TOTPFactor.objects.create(user=dpo, encrypted_secret="test-only", confirmed_at=timezone.now())
    result = post_json(client, url, {"expected_revision": item["revision"]})
    assert result.status_code == 403 and result.json()["error"]["code"] == "recent_mfa_required"
    recent = auth_client(dpo, recent_mfa=True)
    result = post_json(recent, url, {"expected_revision": item["revision"]})
    assert result.status_code == 200
    item = result.json()
    source = tracer()
    case = discovered_case(source)
    result = post_json(
        client, f"{ROOT}/cases/{case.pk}/approve", {"expected_revision": case.revision}
    )
    assert result.status_code == 403 and result.json()["error"]["code"] == "recent_mfa_required"
    assert (
        post_json(
            client, f"{ROOT}/rules/{item['id']}/retire", {"expected_revision": item["revision"]}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "update",
    [
        {"duration_days": 0},
        {"duration_days": -1},
        {"duration_days": 1.5},
        {"category": "INVENTORY"},
        {"action": "DELETE"},
        {"trigger": "MEDIA_READY_AT"},
        {"policy_reference": " "},
    ],
)
def test_api_rejects_invalid_or_unsupported_rules(dpo, update):
    assert post_json(auth_client(dpo), f"{ROOT}/rules", rule_values() | update).status_code == 422


def test_historical_effective_date_is_policy_metadata_and_activation_time_stays_real(dpo):
    source = tracer()
    effective_on = institution_today() - timedelta(days=730)
    item = retention.create_rule(
        actor=dpo,
        values={**rule_values(), "effective_on": effective_on},
        context=AuditContext.user(dpo),
    )
    assert item.effective_on == effective_on
    before = timezone.now()
    item = retention.transition_rule(
        actor=dpo,
        rule_id=item.pk,
        expected_revision=item.revision,
        activate=True,
        context=AuditContext.user(dpo),
    )
    assert item.effective_on == effective_on
    # The policy may predate COMPASS; the activation is still recorded when it happened.
    assert before <= item.activated_at <= timezone.now()
    # Records whose period already elapsed become eligible at once, still awaiting approval.
    case = discovered_case(source)
    assert case.state == "READY" and case.approved_at is None

    drafted = post_json(
        auth_client(dpo),
        f"{ROOT}/rules",
        {**rule_values(), "code": "SYNTHETIC-HISTORICAL", "effective_on": effective_on},
    )
    assert drafted.status_code == 201, drafted.content
    assert drafted.json()["effective_on"] == effective_on.isoformat()


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_effective_on_starts_on_the_manila_day_under_a_utc_runtime(dpo):
    source = tracer()
    item = retention.create_rule(
        actor=dpo,
        values={**rule_values(), "effective_on": date(2026, 10, 9)},
        context=AuditContext.user(dpo),
    )
    item = retention.transition_rule(
        actor=dpo,
        rule_id=item.pk,
        expected_revision=item.revision,
        activate=True,
        context=AuditContext.user(dpo),
    )
    # 15:30 UTC is still 8 October in Manila; 16:30 UTC is already 9 October.
    before_midnight = datetime(2026, 10, 8, 15, 30, tzinfo=UTC)
    after_midnight = datetime(2026, 10, 8, 16, 30, tzinfo=UTC)
    assert not retention.active(item, before_midnight)
    assert retention.active(item, after_midnight)

    with patch("django.utils.timezone.now", return_value=before_midnight):
        assert retention.discover_eligibility() == 0
    GraduateTracerResponse.objects.filter(pk=source.pk).update(
        submitted_at=after_midnight - timedelta(days=31)
    )
    with patch("django.utils.timezone.now", return_value=after_midnight):
        assert retention.discover_eligibility() == 1
    # The retention period itself stays exact instant arithmetic.
    case = DispositionCase.objects.get(source_id=source.pk)
    assert case.eligible_at == after_midnight - timedelta(days=1)


@override_settings(TIME_ZONE="UTC", INSTITUTION_TIME_ZONE="Asia/Manila")
def test_anonymized_submission_keeps_its_manila_day_for_report_filters(dpo):
    source = tracer()
    # 00:30 on 9 October in Manila is still 8 October in UTC.
    GraduateTracerResponse.objects.filter(pk=source.pk).update(
        submitted_at=datetime(2026, 10, 8, 16, 30, tzinfo=UTC)
    )
    anonymize_response(source.pk)

    anonymous = GraduateTracerResponse.objects.get(anonymized_at__isnull=False)
    assert anonymous.submitted_at == datetime(2026, 10, 8, 16, 0, tzinfo=UTC)
    on_the_day = build_graduate_tracer_report(
        submitted_from=date(2026, 10, 9), submitted_to=date(2026, 10, 9)
    )
    day_before = build_graduate_tracer_report(
        submitted_from=date(2026, 10, 8), submitted_to=date(2026, 10, 8)
    )
    assert on_the_day["report_context"]["submitted_response_count"] == 1
    assert day_before["report_context"]["submitted_response_count"] == 0


def test_no_rule_draft_future_retired_and_exact_elapsed_day_boundary(dpo):
    source = tracer()
    assert retention.discover_eligibility() == 0
    item = retention.create_rule(actor=dpo, values=rule_values(), context=AuditContext.user(dpo))
    assert retention.discover_eligibility() == 0
    item = retention.transition_rule(
        actor=dpo,
        rule_id=item.pk,
        expected_revision=item.revision,
        activate=True,
        context=AuditContext.user(dpo),
    )
    OperationalRetentionRule.objects.filter(pk=item.pk).update(
        effective_on=institution_today() + timedelta(days=1)
    )
    assert retention.discover_eligibility() == 0
    OperationalRetentionRule.objects.filter(pk=item.pk).update(effective_on=institution_today())
    case = discovered_case(source)
    assert case.eligible_at == source.submitted_at + timedelta(days=30)
    assert case.state == "READY" and case.approved_at is None
    item.refresh_from_db()
    retention.transition_rule(
        actor=dpo,
        rule_id=item.pk,
        expected_revision=item.revision,
        activate=False,
        context=AuditContext.user(dpo),
    )
    case.refresh_from_db()
    assert case.state == "BLOCKED"
    execute_disposition(str(case.pk))
    assert GraduateTracerResponse.objects.filter(pk=source.pk).exists()


def test_hold_stale_approval_release_and_queued_hold_never_auto_approve(dpo):
    active_rule(dpo)
    case = discovered_case(tracer())
    original_revision = case.revision
    case = retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason="Approved administrative review",
        release=False,
        context=AuditContext.user(dpo),
    )
    with pytest.raises(APIError):
        retention.approve_case(
            actor=dpo,
            case_id=case.pk,
            expected_revision=original_revision,
            context=AuditContext.user(dpo),
        )
    execute_disposition(str(case.pk))
    case = retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason=None,
        release=True,
        context=AuditContext.user(dpo),
    )
    assert case.state == "READY" and case.approved_at is None
    case = approve(dpo, case)
    case = retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason="Hold queued case",
        release=False,
        context=AuditContext.user(dpo),
    )
    execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "ON_HOLD" and case.approved_at is None
    assert AuditEvent.objects.filter(action="privacy.retention.hold.placed").count() == 2
    assert AuditEvent.objects.filter(action="privacy.retention.hold.released").count() == 1


def test_frozen_single_case_new_source_not_approved_and_dispatch_after_commit(
    dpo, django_capture_on_commit_callbacks
):
    active_rule(dpo)
    first = tracer()
    case = discovered_case(first)
    with patch("compass.privacy_governance.tasks.execute_disposition.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            approved = approve(dpo, case)
            assert not delay.called
        delay.assert_called_once_with(str(case.pk))
    second = tracer("second@example.edu")
    new = discovered_case(second)
    execute_disposition(str(approved.pk))
    assert new.state == "READY" and new.approved_at is None
    assert GraduateTracerResponse.objects.filter(pk=second.pk).exists()


def test_anonymization_map_children_aggregate_identity_and_personal_api(dpo):
    active_rule(dpo)
    source = tracer(
        birth_date=institution_today(),
        undergraduate_degree_reasons=["PEER_INFLUENCE"],
        advanced_study_reasons=["OTHER"],
        reasons_for_accepting_first_job=["OTHER"],
        degree_other_reason="Confidential detail",
        self_employed_college_skills="Identifying skill",
    )
    student = source.student
    for model, values in (
        (
            GraduateTracerEducation,
            {
                "degree_and_specialization": "Identifying degree",
                "college_or_university": "Named school",
                "year_graduated": 2020,
            },
        ),
        (GraduateTracerProfessionalExam, {"examination_name": "Named exam"}),
        (GraduateTracerTraining, {"title": "Specific training"}),
    ):
        encrypted_row(model, response=source, position=1, **values)
    before = build_graduate_tracer_report()
    case = approve(dpo, discovered_case(source))
    execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "COMPLETED"
    assert not GraduateTracerResponse.objects.filter(pk=source.pk).exists()
    anonymous = GraduateTracerResponse.objects.get(anonymized_at__isnull=False)
    assert verify_anonymized(anonymous) and anonymous.pk != source.pk
    assert all(getattr(source, field) == getattr(anonymous, field) for field in ANALYTICAL_FIELDS)
    assert anonymous.confidential_content_ciphertext is None
    assert not hasattr(anonymous, "birth_date")
    assert not hasattr(anonymous, "province")
    assert not hasattr(anonymous, "undergraduate_degree_reasons")
    assert not hasattr(anonymous, "advanced_study_reasons")
    assert not hasattr(anonymous, "curriculum_improvement_suggestions")
    assert all(
        model.objects.count() == 0
        for model in (
            GraduateTracerEducation,
            GraduateTracerProfessionalExam,
            GraduateTracerTraining,
        )
    )
    after = build_graduate_tracer_report()
    assert before["sections"] == after["sections"]
    assert after["report_context"]["submitted_response_count"] == 1
    anonymize_response(anonymous.pk)
    execute_disposition(str(case.pk))
    assert GraduateTracerResponse.objects.count() == 1
    assert GraduateTracerDisposedParticipation.objects.filter(student=student).exists()
    client = auth_client(student)
    assert (
        client.get("/api/v1/graduate-tracer/me").json()["error"]["code"]
        == "graduate_tracer_disposed"
    )
    assert (
        post_json(client, "/api/v1/graduate-tracer/me", {}).json()["error"]["code"]
        == "graduate_tracer_disposed"
    )
    safe = auth_client(dpo).get(f"{ROOT}/cases/{case.pk}").json()
    assert safe["affected_count"] == 1
    assert not {"source_id", "student_id", "name_snapshot", "email_snapshot"} & safe.keys()
    assert str(anonymous.pk) not in json.dumps(safe)
    head = auth_client(make_head())
    assert head.get(f"/api/v1/graduate-tracer/responses/{source.pk}").status_code == 404
    assert head.get(f"/api/v1/graduate-tracer/responses/{anonymous.pk}").status_code == 404
    assert head.get("/api/v1/graduate-tracer/responses").json()["items"] == []


class CapturingDispositionDaily:
    def __init__(self, outcome="success", transcript=False):
        self.outcome, self.calls, self.transcript = outcome, [], transcript

    def get_recording(self, *, artifact_id):
        self.calls.append(("GET_RECORDING", artifact_id))
        return {
            "id": artifact_id,
            "status": "finished",
            **({"storage_provider": "aws"} if self.outcome == "external" else {}),
        }

    def get_transcript(self, *, artifact_id):
        self.calls.append(("GET_TRANSCRIPT", artifact_id))
        return {
            "transcriptId": artifact_id,
            "status": "t_deleted" if self.outcome == "already_deleted" else "t_finished",
            **({"outParams": {"bucket": "external"}} if self.outcome == "external" else {}),
        }

    def _delete(self, artifact_id):
        self.calls.append(("DELETE", artifact_id))
        if self.outcome == "transient":
            raise DailyUnavailable("Sanitized provider failure")
        if self.outcome == "permanent":
            raise DailyHTTPError(403)
        return (
            {}
            if self.outcome == "unverified"
            else {
                "deleted": True,
                "id": artifact_id,
                "transcriptId": artifact_id,
                "status": "t_deleted",
                "temporary_url": "never-store",
                "token": "never-audit",
            }
        )

    def delete_recording(self, *, artifact_id):
        return self._delete(artifact_id)

    def delete_transcript(self, *, artifact_id):
        return self._delete(artifact_id)


def media_source(kind):
    from tests.test_ecounseling_media import setup_session

    _, student, counselor, appointment = setup_session(media_policy_version=2)
    room = ECounselingRoom.objects.create(
        appointment=appointment,
        daily_room_name="safe-opaque-room",
        media_policy_version=1,
        room_expires_at=timezone.now() - timedelta(days=31),
    )
    consent = ECounselingConsent.objects.create(
        room=room,
        scope="AUDIO_VIDEO_RECORDING" if kind == "RECORDING" else "TRANSCRIPT_STORAGE",
        requested_by=counselor,
        decision="APPROVED",
        decided_at=timezone.now() - timedelta(days=32),
        withdrawn_at=timezone.now() - timedelta(days=31),
    )
    source = ECounselingMediaCapture.objects.create(
        room=room,
        kind=kind,
        status="READY",
        provider_artifact_id="artifact-opaque",
        provider_instance_id="instance-opaque",
        ready_at=timezone.now() - timedelta(days=31),
    )
    return source, consent


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("success", "COMPLETED"),
        ("transient", "QUEUED"),
        ("permanent", "FAILED"),
        ("unverified", "RECONCILIATION_REQUIRED"),
        ("external", "RECONCILIATION_REQUIRED"),
    ],
)
def test_provider_disposition_truth_verification_consent_and_idempotency(
    dpo, kind, outcome, expected
):
    source, consent = media_source(kind)
    category = "ECOUNSELING_RECORDING" if kind == "RECORDING" else "ECOUNSELING_TRANSCRIPT"
    active_rule(dpo, category)
    case = discovered_case(source)
    fake = CapturingDispositionDaily(outcome, transcript=kind == "TRANSCRIPTION")
    with patch.object(DailyClient, "from_settings", return_value=fake):
        execute_disposition(str(case.pk))
        assert fake.calls == []
        case = approve(dpo, case)
        execute_disposition(str(case.pk))
        case.refresh_from_db()
        assert case.state == expected
        count = len(fake.calls)
        execute_disposition(str(case.pk))
        assert len(fake.calls) == count
    source.refresh_from_db()
    assert (source.provider_artifact_id is None) == (expected == "COMPLETED")
    assert (source.artifact_disposed_at is not None) == (expected == "COMPLETED")
    consent.refresh_from_db()
    assert consent.decision == "APPROVED" and consent.withdrawn_at
    metadata = json.dumps(
        list(
            AuditEvent.objects.filter(action__startswith="privacy.").values_list(
                "metadata", flat=True
            )
        )
    )
    for forbidden in (
        "never-store",
        "never-audit",
        "artifact-opaque",
        "instance-opaque",
        "temporary_url",
        "Confidential",
    ):
        assert forbidden not in metadata
    if expected == "COMPLETED":
        process_media_webhook_event(
            event_type="recording.ready-to-download"
            if kind == "RECORDING"
            else "transcript.ready-to-download",
            event_id="late-ready",
            event_ts=timezone.now().timestamp(),
            payload={
                "room_name": source.room.daily_room_name,
                "recording_id": "artifact-opaque",
                "transcript_id": "artifact-opaque",
            },
        )
        source.refresh_from_db()
        assert source.provider_artifact_id is None and source.artifact_disposed_at


def test_provider_retries_bounded_and_stale_claim_needs_reconciliation(dpo):
    source, _ = media_source("RECORDING")
    active_rule(dpo, "ECOUNSELING_RECORDING")
    case = approve(dpo, discovered_case(source))
    fake = CapturingDispositionDaily("transient")
    with patch.object(DailyClient, "from_settings", return_value=fake):
        for _ in range(3):
            DispositionCase.objects.filter(pk=case.pk).update(next_attempt_at=timezone.now())
            execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "FAILED" and case.attempts == 3
    case = retention.approve_case(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        context=AuditContext.user(dpo),
        retry=True,
    )
    DispositionCase.objects.filter(pk=case.pk).update(
        state="PROCESSING", started_at=timezone.now() - timedelta(minutes=16)
    )
    with patch("compass.privacy_governance.tasks.enqueue"):
        recover_disposition()
    case.refresh_from_db()
    assert case.state == "RECONCILIATION_REQUIRED" and case.blocker == "WORKER_INTERRUPTED"


def test_changed_source_rejected_before_approval_and_execution(dpo):
    active_rule(dpo)
    source = tracer()
    case = discovered_case(source)
    GraduateTracerResponse.objects.filter(pk=source.pk).update(updated_at=timezone.now())
    with pytest.raises(APIError):
        approve(dpo, case)
    retention.discover_eligibility()
    case.refresh_from_db()
    case = approve(dpo, case)
    GraduateTracerResponse.objects.filter(pk=source.pk).update(updated_at=timezone.now())
    execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert (
        case.state == "NO_LONGER_ELIGIBLE"
        and GraduateTracerResponse.objects.filter(pk=source.pk).exists()
    )


def test_required_audit_failure_rolls_back_anonymization(dpo):
    active_rule(dpo)
    source = tracer()
    case = approve(dpo, discovered_case(source))
    original_audit = retention.audit

    def fail_completion(context, action, item, **kwargs):
        if action == actions.DISPOSITION_COMPLETED:
            raise RuntimeError("audit unavailable")
        return original_audit(context, action, item, **kwargs)

    with patch("compass.privacy_governance.tasks.audit", side_effect=fail_completion):
        with pytest.raises(RuntimeError):
            execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "QUEUED" and GraduateTracerResponse.objects.filter(pk=source.pk).exists()
    assert not GraduateTracerResponse.objects.filter(anonymized_at__isnull=False).exists()
    assert not GraduateTracerDisposedParticipation.objects.exists()
    assert not AuditEvent.objects.filter(action=actions.DISPOSITION_STARTED).exists()


def test_anonymization_verification_failure_preserves_source_and_records_failure(dpo):
    active_rule(dpo)
    source = tracer()
    case = approve(dpo, discovered_case(source))
    with patch("compass.graduate_tracer.disposition.verify_anonymized", return_value=False):
        execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "FAILED" and case.blocker == "VERIFICATION_FAILED"
    assert AuditEvent.objects.filter(
        action="privacy.disposition.failed", target_id=case.pk
    ).exists()
    assert GraduateTracerResponse.objects.filter(pk=source.pk, student=source.student).exists()
    assert not GraduateTracerResponse.objects.filter(anonymized_at__isnull=False).exists()
    assert not GraduateTracerDisposedParticipation.objects.exists()


@pytest.mark.parametrize("kind", ["RECORDING", "TRANSCRIPTION"])
def test_held_provider_case_does_not_call_daily(dpo, kind):
    source, _ = media_source(kind)
    category = "ECOUNSELING_RECORDING" if kind == "RECORDING" else "ECOUNSELING_TRANSCRIPT"
    active_rule(dpo, category)
    case = approve(dpo, discovered_case(source))
    retention.change_hold(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        reason="Administrative hold",
        release=False,
        context=AuditContext.user(dpo),
    )
    with patch.object(DailyClient, "from_settings") as provider:
        execute_disposition(str(case.pk))
        provider.assert_not_called()
    source.refresh_from_db()
    assert source.provider_artifact_id and source.artifact_disposed_at is None


def test_documented_deleted_transcript_reconciles_without_second_delete(dpo):
    source, _ = media_source("TRANSCRIPTION")
    active_rule(dpo, "ECOUNSELING_TRANSCRIPT")
    case = approve(dpo, discovered_case(source))
    fake = CapturingDispositionDaily("already_deleted", transcript=True)
    with patch.object(DailyClient, "from_settings", return_value=fake):
        execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "COMPLETED"
    assert fake.calls == [("GET_TRANSCRIPT", "artifact-opaque")]


def test_approval_setup_step_up_and_exact_lifecycle_audits(dpo):
    rule = active_rule(dpo)
    source = tracer()
    case = discovered_case(source)
    response = post_json(
        auth_client(dpo), f"{ROOT}/cases/{case.pk}/approve", {"expected_revision": case.revision}
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "mfa_setup_required"
    case = approve(dpo, case)
    execute_disposition(str(case.pk))
    retention.transition_rule(
        actor=dpo,
        rule_id=rule.pk,
        expected_revision=rule.revision,
        activate=False,
        context=AuditContext.user(dpo),
    )
    assert list(
        AuditEvent.objects.filter(action__startswith="privacy.")
        .order_by("occurred_at", "id")
        .values_list("action", flat=True)
    ) == [
        "privacy.retention.rule.created",
        "privacy.retention.rule.activated",
        "privacy.disposition.approved",
        "privacy.disposition.started",
        "privacy.disposition.completed",
        "privacy.retention.rule.retired",
    ]


@pytest.mark.parametrize(
    "method,path",
    [
        ("get_recording", "/recordings/opaque%2Fid"),
        ("delete_recording", "/recordings/opaque%2Fid"),
        ("get_transcript", "/transcript/opaque%2Fid"),
        ("delete_transcript", "/transcript/opaque%2Fid"),
    ],
)
def test_daily_disposition_uses_documented_quoted_resource_paths(method, path):
    client = DailyClient("test-key", base_url="https://api.daily.test/v1", timeout_seconds=1)
    with patch.object(client, "_request", return_value={}) as request:
        getattr(client, method)(artifact_id="opaque/id")
    request.assert_called_once_with("DELETE" if method.startswith("delete") else "GET", path)


def test_unknown_tracer_instrument_version_is_never_executable(dpo):
    active_rule(dpo)
    with pytest.raises(IntegrityError), transaction.atomic():
        tracer(instrument_schema_version=2)
    assert retention.discover_eligibility() == 0
    assert not DispositionCase.objects.exists()


def test_provider_completion_audit_failure_preserves_evidence_and_reconciles(dpo):
    source, _ = media_source("TRANSCRIPTION")
    active_rule(dpo, "ECOUNSELING_TRANSCRIPT")
    case = approve(dpo, discovered_case(source))
    fake = CapturingDispositionDaily()
    original_audit = retention.audit

    def fail_completion(context, action, item, **kwargs):
        if action == actions.DISPOSITION_COMPLETED:
            raise RuntimeError("audit unavailable")
        return original_audit(context, action, item, **kwargs)

    with patch.object(DailyClient, "from_settings", return_value=fake):
        with patch("compass.privacy_governance.tasks.audit", side_effect=fail_completion):
            with pytest.raises(RuntimeError):
                execute_disposition(str(case.pk))
    case.refresh_from_db()
    source.refresh_from_db()
    assert case.state == "PROCESSING"
    assert source.provider_artifact_id == "artifact-opaque" and source.artifact_disposed_at is None
    assert not AuditEvent.objects.filter(action=actions.DISPOSITION_COMPLETED).exists()
    DispositionCase.objects.filter(pk=case.pk).update(
        started_at=timezone.now() - timedelta(minutes=16)
    )
    with patch("compass.privacy_governance.tasks.enqueue"):
        recover_disposition()
    case.refresh_from_db()
    assert case.state == "RECONCILIATION_REQUIRED"
    case = retention.approve_case(
        actor=dpo,
        case_id=case.pk,
        expected_revision=case.revision,
        context=AuditContext.user(dpo),
        retry=True,
    )
    fake = CapturingDispositionDaily("already_deleted", transcript=True)
    with patch.object(DailyClient, "from_settings", return_value=fake):
        execute_disposition(str(case.pk))
    case.refresh_from_db()
    assert case.state == "COMPLETED" and fake.calls == [("GET_TRANSCRIPT", "artifact-opaque")]
