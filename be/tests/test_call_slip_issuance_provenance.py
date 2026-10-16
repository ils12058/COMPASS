"""Call Slip issuance provenance persists original live/historical intent across its lifecycle."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from compass.call_slips.models import CallSlip, CallSlipIssuanceMode
from compass.call_slips.services import (
    list_call_slips,
    list_my_call_slips,
    record_interview_ended,
    void_call_slip,
)
from compass.counseling.context_services import list_context_history
from compass.notifications.models import Notification
from compass.referrals.services import record_action
from tests.test_call_slips import (
    audit_context,
    auth_client,
    create_for,
    create_from_referral_for,
    create_referral_for,
    csrf,
    make_head,
    setup_scope,
    sync_policy,
)


def voided_notice_exists(call_slip: CallSlip) -> bool:
    return Notification.objects.filter(
        event_code="call_slip.voided",
        source_type="call_slip",
        source_id=call_slip.pk,
    ).exists()


@pytest.mark.django_db
def test_live_and_historical_direct_issuance_persist_provenance_and_govern_void_notification():
    sync_policy()
    counselor, _other, _gss, student, _student_b = setup_scope()
    live = create_for(counselor, student, key="live", fingerprint="1" * 64, notify_student=True)
    quiet = create_for(counselor, student, key="quiet", fingerprint="2" * 64)

    assert live.issuance_mode == CallSlipIssuanceMode.LIVE
    assert quiet.issuance_mode == CallSlipIssuanceMode.HISTORICAL

    retried = create_for(counselor, student, key="quiet", fingerprint="2" * 64)
    assert retried.pk == quiet.pk
    assert retried.issuance_mode == CallSlipIssuanceMode.HISTORICAL

    void_call_slip(
        actor=counselor,
        call_slip_id=quiet.pk,
        reason="Back-entry recorded in error",
        context=audit_context(counselor),
    )
    void_call_slip(
        actor=counselor,
        call_slip_id=live.pk,
        reason="Issued in error",
        context=audit_context(counselor),
    )

    assert not voided_notice_exists(quiet)
    assert not Notification.objects.filter(source_id=quiet.pk).exists()
    assert voided_notice_exists(live)


@pytest.mark.django_db
def test_referral_driven_issuance_persists_provenance():
    sync_policy()
    head = make_head()
    _counselor, _other, _gss, student, _student_b = setup_scope()
    live_referral = create_referral_for(head, student, key="ref-live", fingerprint="3" * 64)
    quiet_referral = create_referral_for(head, student, key="ref-quiet", fingerprint="4" * 64)

    live = create_from_referral_for(
        head,
        live_referral,
        key="from-ref-live",
        fingerprint="5" * 64,
        notify_student=True,
        action_occurred_at=timezone.now() - timedelta(minutes=5),
    )
    record_action(
        actor=head,
        referral_id=quiet_referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now() - timedelta(minutes=5),
        remarks="Paper permit already handed over",
        context=audit_context(head),
    )
    quiet = create_from_referral_for(
        head, quiet_referral, key="from-ref-quiet", fingerprint="6" * 64
    )

    assert live.issuance_mode == CallSlipIssuanceMode.LIVE
    assert quiet.issuance_mode == CallSlipIssuanceMode.HISTORICAL
    void_call_slip(
        actor=head, call_slip_id=quiet.pk, reason="Correction", context=audit_context(head)
    )
    assert not voided_notice_exists(quiet)


@pytest.mark.django_db
def test_operational_api_projects_provenance_and_void_consequence_only_to_guidance():
    sync_policy()
    counselor, _other, _gss, student, _student_b = setup_scope()
    live = create_for(counselor, student, key="api-live", fingerprint="7" * 64, notify_student=True)
    quiet = create_for(counselor, student, key="api-quiet", fingerprint="8" * 64)
    legacy = create_for(counselor, student, key="api-legacy", fingerprint="9" * 64)
    CallSlip.objects.filter(pk=legacy.pk).update(issuance_mode=CallSlipIssuanceMode.LEGACY_UNKNOWN)

    operational = auth_client(counselor)
    rows = {
        item["id"]: item
        for item in operational.get("/api/v1/call-slips?page_size=50").json()["items"]
    }
    assert rows[str(live.pk)]["issuance_mode"] == "LIVE"
    assert rows[str(live.pk)]["void_notifies_student"] is True
    assert rows[str(quiet.pk)]["issuance_mode"] == "HISTORICAL"
    assert rows[str(quiet.pk)]["void_notifies_student"] is False
    assert rows[str(legacy.pk)]["issuance_mode"] == "LEGACY_UNKNOWN"
    assert rows[str(legacy.pk)]["void_notifies_student"] is True

    self_view = auth_client(student).get("/api/v1/call-slips/me").json()["items"]
    assert all("issuance_mode" not in item for item in self_view)
    assert all("void_notifies_student" not in item for item in self_view)

    voided = operational.post(
        f"/api/v1/call-slips/{legacy.pk}/void",
        data={"reason": "Legacy correction"},
        content_type="application/json",
        **csrf(operational),
    )
    assert voided.status_code == 200
    # Legacy rows keep the pre-provenance withdrawal notification behavior.
    assert voided_notice_exists(legacy)


@pytest.mark.django_db
def test_lifecycle_state_filters_discover_active_completed_and_voided_call_slips():
    sync_policy()
    counselor, _other, _gss, student, _student_b = setup_scope()
    active = create_for(counselor, student, key="state-active", fingerprint="c" * 64)
    completed = create_for(counselor, student, key="state-completed", fingerprint="d" * 64)
    voided = create_for(counselor, student, key="state-voided", fingerprint="e" * 64)
    record_interview_ended(
        actor=counselor,
        call_slip_id=completed.pk,
        interview_ended_at=timezone.now(),
        context=audit_context(counselor),
    )
    void_call_slip(
        actor=counselor, call_slip_id=voided.pk, reason="Error", context=audit_context(counselor)
    )

    def ids(page):
        return {item.pk for item in page.items}

    assert ids(list_call_slips(actor=counselor, state="ACTIVE")) == {active.pk}
    assert ids(list_call_slips(actor=counselor, state="COMPLETED")) == {completed.pk}
    assert ids(list_call_slips(actor=counselor, state="VOIDED")) == {voided.pk}
    assert ids(list_call_slips(actor=counselor)) == {active.pk, completed.pk}
    assert ids(list_my_call_slips(actor=student, state="ACTIVE")) == {active.pk}
    assert ids(list_my_call_slips(actor=student)) == {active.pk, completed.pk, voided.pk}

    api = auth_client(counselor).get("/api/v1/call-slips?state=ACTIVE").json()["items"]
    assert [item["id"] for item in api] == [str(active.pk)]
    mine = auth_client(student).get("/api/v1/call-slips/me?state=VOIDED").json()["items"]
    assert [item["id"] for item in mine] == [str(voided.pk)]
    assert auth_client(student).get("/api/v1/call-slips/me?state=OPEN").status_code == 422

    student_overview = auth_client(student).get("/api/v1/overview").json()["student"]
    assert student_overview["active_call_slip_count"] == 1
    guidance_overview = auth_client(counselor).get("/api/v1/overview").json()["guidance"]
    assert guidance_overview["active_call_slip_count"] == 1


@pytest.mark.django_db
def test_counseling_context_history_marks_voided_call_slips_and_referrals():
    sync_policy()
    head = make_head()
    _counselor, _other, _gss, student, _student_b = setup_scope()
    referral = create_referral_for(head, student, key="history-ref", fingerprint="f" * 64)
    slip = create_for(head, student, key="history-slip", fingerprint="0" * 64)
    void_call_slip(actor=head, call_slip_id=slip.pk, reason="Error", context=audit_context(head))
    from compass.referrals.services import void_referral

    void_referral(
        actor=head, referral_id=referral.pk, reason="Wrong record", context=audit_context(head)
    )

    class Access:
        student_id = student.pk

    rows = {item.kind: item for item in list_context_history(Access())}
    assert rows["CALL_SLIP"].status == "VOIDED"
    assert rows["REFERRAL"].status == "VOIDED"


@pytest.mark.django_db
def test_referral_void_conflict_explains_completed_linked_call_slip():
    from compass.referrals.services import ReferralVoidConflict, void_referral

    sync_policy()
    head = make_head()
    _counselor, _other, _gss, student, _student_b = setup_scope()
    referral = create_referral_for(head, student, key="void-completed", fingerprint="1" * 64)
    slip = create_from_referral_for(
        head,
        referral,
        key="void-completed-slip",
        fingerprint="2" * 64,
        action_occurred_at=timezone.now() - timedelta(minutes=5),
    )
    record_interview_ended(
        actor=head,
        call_slip_id=slip.pk,
        interview_ended_at=timezone.now(),
        context=audit_context(head),
    )

    with pytest.raises(ReferralVoidConflict, match="completed linked Call Slip"):
        void_referral(
            actor=head, referral_id=referral.pk, reason="Wrong", context=audit_context(head)
        )
