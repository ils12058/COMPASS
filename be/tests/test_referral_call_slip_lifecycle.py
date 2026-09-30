from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from compass.call_slips.lifecycle import (
    ReferralCallSlipDependency,
    referral_call_slip_dependency,
)
from compass.call_slips.models import CallSlip
from compass.call_slips.services import (
    CallSlipVoidConflict,
    create_call_slip_from_referral,
    record_interview_ended,
    void_call_slip,
)
from compass.referrals.models import ReferralAction, ReferralActionType
from compass.referrals.services import (
    ReferralActiveCallSlipConflict,
    ReferralCompletedCallSlipConflict,
    record_action,
    void_referral,
)
from tests.test_call_slips import (
    audit_context,
    auth_client,
    create_for,
    create_referral_for,
    csrf,
    make_head,
    make_user,
    sync_policy,
)


def _linked_call_slip(*, actor, student, referral, key: str, fingerprint: str):
    if not ReferralAction.objects.filter(
        referral=referral,
        action_type=ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT,
    ).exists():
        record_action(
            actor=actor,
            referral_id=referral.pk,
            action_type=ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT,
            occurred_at=timezone.now() - timedelta(minutes=5),
            remarks="Call Slip source action",
            context=audit_context(actor),
        )
    return create_for(
        actor,
        student,
        key=key,
        fingerprint=fingerprint,
        referral_id=referral.pk,
        notify_student=False,
    )


@pytest.mark.django_db
def test_call_slip_owned_referral_dependency_covers_current_and_historical_states():
    sync_policy()
    head = make_head("dependency-head@example.edu")
    student = make_user("dependency-student@example.edu", "STUDENT")

    none_referral = create_referral_for(
        head,
        student,
        key="dependency-none-ref",
        fingerprint="a" * 64,
    )
    assert (
        referral_call_slip_dependency(referral_id=none_referral.pk)
        == ReferralCallSlipDependency.NONE
    )

    active_referral = create_referral_for(
        head,
        student,
        key="dependency-active-ref",
        fingerprint="b" * 64,
    )
    _linked_call_slip(
        actor=head,
        student=student,
        referral=active_referral,
        key="dependency-active-call",
        fingerprint="c" * 64,
    )
    assert (
        referral_call_slip_dependency(referral_id=active_referral.pk)
        == ReferralCallSlipDependency.ACTIVE
    )

    completed_referral = create_referral_for(
        head,
        student,
        key="dependency-completed-ref",
        fingerprint="d" * 64,
    )
    completed = _linked_call_slip(
        actor=head,
        student=student,
        referral=completed_referral,
        key="dependency-completed-call",
        fingerprint="e" * 64,
    )
    record_interview_ended(
        actor=head,
        call_slip_id=completed.pk,
        interview_ended_at=timezone.now() - timedelta(minutes=1),
        context=audit_context(head),
    )
    assert (
        referral_call_slip_dependency(referral_id=completed_referral.pk)
        == ReferralCallSlipDependency.COMPLETED
    )

    voided_referral = create_referral_for(
        head,
        student,
        key="dependency-voided-ref",
        fingerprint="f" * 64,
    )
    voided = _linked_call_slip(
        actor=head,
        student=student,
        referral=voided_referral,
        key="dependency-voided-call",
        fingerprint="1" * 64,
    )
    void_call_slip(
        actor=head,
        call_slip_id=voided.pk,
        reason="Superseded permit",
        context=audit_context(head),
    )
    assert (
        referral_call_slip_dependency(referral_id=voided_referral.pk)
        == ReferralCallSlipDependency.NONE
    )

    replacement = create_call_slip_from_referral(
        actor=head,
        referral_id=voided_referral.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(hours=2),
        notify_student=False,
        action_occurred_at=None,
        action_remarks=None,
        idempotency_key="dependency-replacement-call",
        request_fingerprint="2" * 64,
        context=audit_context(head),
    )
    assert (
        referral_call_slip_dependency(referral_id=voided_referral.pk)
        == ReferralCallSlipDependency.ACTIVE
    )
    record_interview_ended(
        actor=head,
        call_slip_id=replacement.pk,
        interview_ended_at=timezone.now() - timedelta(seconds=1),
        context=audit_context(head),
    )
    assert (
        referral_call_slip_dependency(referral_id=voided_referral.pk)
        == ReferralCallSlipDependency.COMPLETED
    )


@pytest.mark.django_db
def test_referral_void_allows_none_or_only_voided_history_and_preserves_provenance():
    sync_policy()
    head = make_head("void-clear-head@example.edu")
    student = make_user("void-clear-student@example.edu", "STUDENT")

    no_call = create_referral_for(
        head,
        student,
        key="void-no-call-ref",
        fingerprint="3" * 64,
    )
    voided_no_call = void_referral(
        actor=head,
        referral_id=no_call.pk,
        reason="Source Referral entered in error",
        context=audit_context(head),
    )
    assert voided_no_call.voided_at is not None

    with_history = create_referral_for(
        head,
        student,
        key="void-history-ref",
        fingerprint="4" * 64,
    )
    old = _linked_call_slip(
        actor=head,
        student=student,
        referral=with_history,
        key="void-history-call",
        fingerprint="5" * 64,
    )
    void_call_slip(
        actor=head,
        call_slip_id=old.pk,
        reason="Incorrect Call Slip",
        context=audit_context(head),
    )
    action_ids = set(
        ReferralAction.objects.filter(referral=with_history).values_list("id", flat=True)
    )

    voided_with_history = void_referral(
        actor=head,
        referral_id=with_history.pk,
        reason="Referral no longer valid",
        context=audit_context(head),
    )

    assert voided_with_history.voided_at is not None
    old.refresh_from_db()
    assert old.voided_at is not None
    assert old.void_reason == "Incorrect Call Slip"
    assert set(
        ReferralAction.objects.filter(referral=with_history).values_list("id", flat=True)
    ) == action_ids
    assert CallSlip.objects.filter(referral=with_history).count() == 1


@pytest.mark.django_db
def test_referral_void_blocks_active_and_completed_dependencies_without_partial_mutation():
    sync_policy()
    head = make_head("void-block-head@example.edu")
    student = make_user("void-block-student@example.edu", "STUDENT")

    active_referral = create_referral_for(
        head,
        student,
        key="void-active-ref",
        fingerprint="6" * 64,
    )
    active = _linked_call_slip(
        actor=head,
        student=student,
        referral=active_referral,
        key="void-active-call",
        fingerprint="7" * 64,
    )
    with pytest.raises(ReferralActiveCallSlipConflict, match="Void the active linked Call Slip"):
        void_referral(
            actor=head,
            referral_id=active_referral.pk,
            reason="Should not persist",
            context=audit_context(head),
        )
    active_referral.refresh_from_db()
    active.refresh_from_db()
    assert active_referral.voided_at is None
    assert active_referral.voided_by_id is None
    assert active_referral.void_reason == ""
    assert active.lifecycle_state == "ACTIVE"

    completed_referral = create_referral_for(
        head,
        student,
        key="void-completed-ref",
        fingerprint="8" * 64,
    )
    completed = _linked_call_slip(
        actor=head,
        student=student,
        referral=completed_referral,
        key="void-completed-call",
        fingerprint="9" * 64,
    )
    completed_at = timezone.now() - timedelta(minutes=1)
    record_interview_ended(
        actor=head,
        call_slip_id=completed.pk,
        interview_ended_at=completed_at,
        context=audit_context(head),
    )
    with pytest.raises(ReferralCompletedCallSlipConflict, match="historical"):
        void_referral(
            actor=head,
            referral_id=completed_referral.pk,
            reason="Should not persist",
            context=audit_context(head),
        )
    completed_referral.refresh_from_db()
    completed.refresh_from_db()
    assert completed_referral.voided_at is None
    assert completed_referral.voided_by_id is None
    assert completed_referral.void_reason == ""
    assert completed.lifecycle_state == "COMPLETED"
    assert completed.interview_ended_at == completed_at


@pytest.mark.django_db
def test_referral_void_api_uses_stable_call_slip_lifecycle_conflict_codes():
    sync_policy()
    head = make_head("void-api-head@example.edu")
    student = make_user("void-api-student@example.edu", "STUDENT")
    client = auth_client(head)
    headers = csrf(client)

    active_referral = create_referral_for(
        head,
        student,
        key="void-api-active-ref",
        fingerprint="a1" * 32,
    )
    _linked_call_slip(
        actor=head,
        student=student,
        referral=active_referral,
        key="void-api-active-call",
        fingerprint="b1" * 32,
    )
    active_response = client.post(
        f"/api/v1/referrals/{active_referral.pk}/void",
        data=json.dumps({"reason": "Should be blocked"}),
        content_type="application/json",
        **headers,
    )
    assert active_response.status_code == 409
    assert active_response.json()["error"]["code"] == "referral_active_call_slip_conflict"

    completed_referral = create_referral_for(
        head,
        student,
        key="void-api-completed-ref",
        fingerprint="c1" * 32,
    )
    completed = _linked_call_slip(
        actor=head,
        student=student,
        referral=completed_referral,
        key="void-api-completed-call",
        fingerprint="d1" * 32,
    )
    record_interview_ended(
        actor=head,
        call_slip_id=completed.pk,
        interview_ended_at=timezone.now() - timedelta(minutes=1),
        context=audit_context(head),
    )
    completed_response = client.post(
        f"/api/v1/referrals/{completed_referral.pk}/void",
        data=json.dumps({"reason": "Should be blocked"}),
        content_type="application/json",
        **headers,
    )
    assert completed_response.status_code == 409
    assert (
        completed_response.json()["error"]["code"]
        == "referral_completed_call_slip_conflict"
    )


@pytest.mark.django_db
def test_void_reissue_reconciliation_uses_replacement_as_authoritative_dependency():
    sync_policy()
    head = make_head("reissue-head@example.edu")
    student = make_user("reissue-student@example.edu", "STUDENT")
    referral = create_referral_for(
        head,
        student,
        key="reissue-ref",
        fingerprint="e1" * 32,
    )
    first = _linked_call_slip(
        actor=head,
        student=student,
        referral=referral,
        key="reissue-first",
        fingerprint="f1" * 32,
    )
    void_call_slip(
        actor=head,
        call_slip_id=first.pk,
        reason="Superseded",
        context=audit_context(head),
    )

    second = create_call_slip_from_referral(
        actor=head,
        referral_id=referral.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(hours=2),
        notify_student=False,
        action_occurred_at=None,
        action_remarks=None,
        idempotency_key="reissue-second",
        request_fingerprint="a2" * 32,
        context=audit_context(head),
    )
    assert referral_call_slip_dependency(referral_id=referral.pk) == ReferralCallSlipDependency.ACTIVE
    with pytest.raises(ReferralActiveCallSlipConflict):
        void_referral(
            actor=head,
            referral_id=referral.pk,
            reason="Blocked by replacement",
            context=audit_context(head),
        )

    void_call_slip(
        actor=head,
        call_slip_id=second.pk,
        reason="Replacement also withdrawn",
        context=audit_context(head),
    )
    assert referral_call_slip_dependency(referral_id=referral.pk) == ReferralCallSlipDependency.NONE
    voided = void_referral(
        actor=head,
        referral_id=referral.pk,
        reason="All Call Slips resolved",
        context=audit_context(head),
    )
    assert voided.voided_at is not None
    assert ReferralAction.objects.filter(referral=referral).count() == 1
    assert CallSlip.objects.filter(referral=referral).count() == 2


@pytest.mark.django_db
def test_completed_replacement_permanently_blocks_referral_void_and_stays_immutable():
    sync_policy()
    head = make_head("completed-reissue-head@example.edu")
    student = make_user("completed-reissue-student@example.edu", "STUDENT")
    referral = create_referral_for(
        head,
        student,
        key="completed-reissue-ref",
        fingerprint="b2" * 32,
    )
    first = _linked_call_slip(
        actor=head,
        student=student,
        referral=referral,
        key="completed-reissue-first",
        fingerprint="c2" * 32,
    )
    void_call_slip(
        actor=head,
        call_slip_id=first.pk,
        reason="Superseded",
        context=audit_context(head),
    )
    second = create_call_slip_from_referral(
        actor=head,
        referral_id=referral.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(hours=2),
        notify_student=False,
        action_occurred_at=None,
        action_remarks=None,
        idempotency_key="completed-reissue-second",
        request_fingerprint="d2" * 32,
        context=audit_context(head),
    )
    completed_at = timezone.now() - timedelta(seconds=1)
    record_interview_ended(
        actor=head,
        call_slip_id=second.pk,
        interview_ended_at=completed_at,
        context=audit_context(head),
    )

    assert (
        referral_call_slip_dependency(referral_id=referral.pk)
        == ReferralCallSlipDependency.COMPLETED
    )
    with pytest.raises(ReferralCompletedCallSlipConflict):
        void_referral(
            actor=head,
            referral_id=referral.pk,
            reason="Must stay historical",
            context=audit_context(head),
        )
    with pytest.raises(CallSlipVoidConflict, match="completed Call Slip"):
        void_call_slip(
            actor=head,
            call_slip_id=second.pk,
            reason="Must not be allowed",
            context=audit_context(head),
        )

    referral.refresh_from_db()
    second.refresh_from_db()
    assert referral.voided_at is None
    assert second.interview_ended_at == completed_at
    assert second.voided_at is None
