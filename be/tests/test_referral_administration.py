"""FAC-4 canonical transitions, live authorization, privacy and Faculty notices."""

import json
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Capability, Role, UserCapabilityOverride
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.models import StaffSupervision
from compass.referrals import administration, faculty_services, services
from compass.referrals import faculty_rules as rules
from compass.referrals.faculty_rules import FacultyReferralError
from compass.referrals.models import Referral
from compass.referrals.notification_contract import prepare_candidate_intent
from compass.referrals.services import ReferralNotFound
from tests.faculty_referral_helpers import confirm, submit
from tests.referral_administration_helpers import make_world, transition

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch):
    return make_world(monkeypatch)


def own(world, pk):
    return faculty_services.get_own_submission(
        actor=world.faculty, actor_session=world.issued.session, referral_id=pk
    )


def test_real_commit_three_states_preserve_source_and_minimal_own_projection(world):
    ticket = confirm(world)["confirmation"]
    value, _ = submit(world, ticket)
    row = Referral.objects.get(pk=value["id"])
    original = (
        row.confidential_content_ciphertext,
        row.submitted_by_id,
        row.submitted_at,
        row.recorded_by_id,
    )
    assert value["state"] == "SUBMITTED" and value["received_at"] is None
    received = transition(world, row.pk)
    row.refresh_from_db()
    assert received["state"] == "RECEIVED_BY_GCO" and received["version"] == 2
    assert row.acknowledged_by_id == world.counselor.pk
    assert row.received_at >= row.submitted_at
    assert own(world, row.pk)["received_at"] == row.received_at
    closed = transition(world, row.pk, close=True)
    row.refresh_from_db()
    assert closed["state"] == "ADMINISTRATIVELY_CLOSED" and closed["version"] == 3
    assert row.administratively_closed_by_id == world.counselor.pk
    assert row.administratively_closed_at >= row.received_at
    assert original == (
        row.confidential_content_ciphertext,
        row.submitted_by_id,
        row.submitted_at,
        row.recorded_by_id,
    )
    projection = own(world, row.pk)
    assert set(projection) == {
        "id",
        "reference_code",
        "submitted_at",
        "student",
        "state",
        "received_at",
        "closed_at",
    }
    assert set(projection["student"]) == {"display_name"}
    assert projection["closed_at"] == row.administratively_closed_at
    assert (
        AuditEvent.objects.filter(
            action="referral.acknowledged", actor_user_id=world.counselor.pk, target_id=str(row.pk)
        ).count()
        == 1
    )
    assert (
        AuditEvent.objects.filter(
            action="referral.administratively_closed",
            actor_user_id=world.counselor.pk,
            target_id=str(row.pk),
        ).count()
        == 1
    )
    # Retry retains identity while disclosing current persisted state.
    replay, created = submit(world, ticket)
    assert not created and replay == projection


@pytest.mark.parametrize("role", ["faculty", "student", "admin"])
def test_no_administrative_capability_for_other_roles(world, role):
    pk = submit(world)[0]["id"]
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk, actor=getattr(world, role))


@pytest.mark.parametrize("close", [False, True])
@pytest.mark.parametrize(
    "mutation",
    [
        "capability",
        "role",
        "inactive",
        "session",
        "session_expired",
        "unsupervised",
        "scope",
        "supervision",
    ],
)
def test_current_authority_and_scope_revalidated(world, mutation, close):
    pk = submit(world)[0]["id"]
    if close:
        transition(world, pk)
    args = {}
    if mutation == "capability":
        UserCapabilityOverride.objects.create(
            user=world.counselor,
            capability=Capability.objects.get(code="referrals.manage"),
            effect="REVOKE",
            reason="Synthetic",
        )
    elif mutation == "role":
        world.counselor.role = Role.objects.get(code="FACULTY")
        world.counselor.save(update_fields=["role"])
    elif mutation == "inactive":
        world.counselor.is_active = False
        world.counselor.save(update_fields=["is_active"])
    elif mutation == "session":
        world.counselor_issued.session.revoked_at = timezone.now()
        world.counselor_issued.session.save(update_fields=["revoked_at"])
    elif mutation == "session_expired":
        expired = create_auth_session(world.counselor, now=timezone.now() - timedelta(days=365))
        args = dict(actor_session=expired.session)
    elif mutation == "unsupervised":
        StaffSupervision.objects.filter(staff=world.staff).delete()
        args = dict(actor=world.staff, actor_session=world.staff_issued.session)
    elif mutation == "scope":
        args = dict(actor=world.other_counselor, actor_session=world.other_counselor_issued.session)
    elif mutation == "supervision":
        StaffSupervision.objects.filter(staff=world.staff).update(supervisor=world.other_counselor)
        args = dict(actor=world.staff, actor_session=world.staff_issued.session)
    with pytest.raises((rules.AdministrativeReferralError, ReferralNotFound)):
        transition(world, pk, close=close, **args)
    row = Referral.objects.get(pk=pk)
    assert row.administrative_version == (2 if close else 1)
    assert row.administratively_closed_at is None
    assert (row.received_at is not None) == close


def test_goa_actual_supervised_ccms_scope_not_faculty_home_college(world):
    pk = submit(world)[0]["id"]
    result = transition(world, pk, actor=world.staff, actor_session=world.staff_issued.session)
    assert result["acknowledged_by"]["id"] == world.staff.pk
    assert result["faculty_home_college"] == world.cas.name
    closed = transition(
        world, pk, close=True, actor=world.staff, actor_session=world.staff_issued.session
    )
    assert closed["closed_by"]["id"] == world.staff.pk


def test_defined_conflicts_prior_receipt_and_explicit_review(world):
    pk = submit(world)[0]["id"]
    with pytest.raises(rules.AdministrativeReferralError) as exc:
        transition(world, pk, close=True, expected_version=1)
    assert exc.value.status == 409
    transition(world, pk)
    for version in (1, 2):
        with pytest.raises(rules.AdministrativeReferralError) as exc:
            transition(world, pk, expected_version=version)
        assert exc.value.status == 409
    for reviewed in (False, 1, "true"):
        with pytest.raises(rules.AdministrativeReferralError) as exc:
            transition(world, pk, close=True, obligations_reviewed=reviewed)
        assert exc.value.status == 422
    transition(world, pk, close=True)
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk, close=True, expected_version=3)


def test_audit_failure_rolls_back_ack_and_closure(world, monkeypatch):
    pk = submit(world)[0]["id"]
    original = administration.record_event

    def fail(**kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(administration, "record_event", fail)
    with pytest.raises(RuntimeError):
        transition(world, pk)
    assert Referral.objects.get(pk=pk).received_at is None
    monkeypatch.setattr(administration, "record_event", original)
    transition(world, pk)
    monkeypatch.setattr(administration, "record_event", fail)
    with pytest.raises(RuntimeError):
        transition(world, pk, close=True)
    assert Referral.objects.get(pk=pk).administratively_closed_at is None


def test_void_preserves_history_and_omits_faculty_read(world):
    pk = submit(world)[0]["id"]
    transition(world, pk)
    transition(world, pk, close=True)
    before = Referral.objects.get(pk=pk)
    services.void_referral(
        actor=world.counselor,
        referral_id=pk,
        reason="Synthetic confidential void",
        context=AuditContext.user(world.counselor),
    )
    after = Referral.objects.get(pk=pk)
    assert (
        after.received_at == before.received_at
        and after.administratively_closed_at == before.administratively_closed_at
    )
    with pytest.raises(ReferralNotFound):
        own(world, pk)
    with pytest.raises(rules.AdministrativeReferralError):
        transition(world, pk, expected_version=3)


def test_database_fences_unacknowledged_start_and_immutable_history(world):
    pk = submit(world)[0]["id"]
    with pytest.raises(IntegrityError), transaction.atomic():
        Referral.objects.filter(pk=pk).update(received_at=timezone.now())
    transition(world, pk)
    with pytest.raises(IntegrityError), transaction.atomic():
        Referral.objects.filter(pk=pk).update(received_at=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        Referral.objects.filter(pk=pk).update(
            acknowledged_by=None,
            received_at=None,
            administrative_version=1,
        )


def test_notice_intent_current_recipient_and_stale_events(world, monkeypatch):
    from compass.notifications.models import Notification

    pk = submit(world)[0]["id"]
    start = Notification.objects.count()
    transition(world, pk)
    assert Notification.objects.count() == start + 1
    assert prepare_candidate_intent(referral_id=pk, event="RECEIVED_BY_GCO") is not None
    a = prepare_candidate_intent(referral_id=pk, event="RECEIVED_BY_GCO")
    assert a.recipient_id == world.faculty.pk and a.recipient_id != world.student.pk
    assert a.route == f"/portal/faculty/referrals/{pk}"
    assert a == prepare_candidate_intent(referral_id=pk, event="RECEIVED_BY_GCO")
    assert "reason" not in repr(a) and "confirmation" not in repr(a)
    transition(world, pk, close=True)
    assert prepare_candidate_intent(referral_id=pk, event="RECEIVED_BY_GCO") is None
    assert (
        prepare_candidate_intent(referral_id=pk, event="ADMINISTRATIVELY_CLOSED").event_at
        is not None
    )
    world.faculty.is_active = False
    world.faculty.save(update_fields=["is_active"])
    assert prepare_candidate_intent(referral_id=pk, event="ADMINISTRATIVELY_CLOSED") is None
    assert Notification.objects.count() == start + 2


def test_api_uses_actual_session_strict_payload_and_role_guards(world):
    pk = submit(world)[0]["id"]
    path = f"/api/v1/referrals/{pk}/acknowledgment"
    client = Client()
    assert (
        client.post(
            path, data=json.dumps({"expected_version": 1}), content_type="application/json"
        ).status_code
        == 401
    )
    client.cookies["compass_session"] = world.issued.token
    assert (
        client.post(
            path, data=json.dumps({"expected_version": 1}), content_type="application/json"
        ).status_code
        == 403
    )
    client.cookies["compass_session"] = world.counselor_issued.token
    for payload in (
        {"expected_version": 1, "actor_id": str(world.faculty.pk)},
        {"expected_version": True},
    ):
        assert (
            client.post(path, data=json.dumps(payload), content_type="application/json").status_code
            == 422
        )
    response = client.post(
        path, data=json.dumps({"expected_version": 1}), content_type="application/json"
    )
    assert response.status_code == 200 and response.json()["state"] == "RECEIVED_BY_GCO"
    close_path = f"/api/v1/referrals/{pk}/administrative-closure"
    for reviewed in (False, 1, "true"):
        assert (
            client.post(
                close_path,
                data=json.dumps({"expected_version": 2, "obligations_reviewed": reviewed}),
                content_type="application/json",
            ).status_code
            == 422
        )
    assert (
        client.post(
            close_path,
            data=json.dumps({"expected_version": 2, "obligations_reviewed": True}),
            content_type="application/json",
        ).status_code
        == 200
    )


def test_reads_pdf_actions_and_linked_tasks_never_ack_or_close_and_closure_retains_links(world):
    from compass.call_slips.services import create_call_slip
    from compass.guidance_followups.models import GuidanceFollowUp
    from compass.referrals.services import build_referral_render_context, get_referral

    pk = submit(world)[0]["id"]
    row = get_referral(actor=world.counselor, referral_id=pk)
    build_referral_render_context(row)
    administration.get_administration(
        actor=world.counselor, actor_session=world.counselor_issued.session, referral_id=pk
    )
    assert Referral.objects.get(pk=pk).received_at is None
    services.record_action(
        actor=world.counselor,
        referral_id=pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="Synthetic action",
        context=AuditContext.user(world.counselor),
    )
    assert Referral.objects.get(pk=pk).received_at is None
    slip = create_call_slip(
        actor=world.counselor,
        student_id=world.student.pk,
        course_year="Synthetic",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(days=1),
        referral_id=pk,
        notify_student=False,
        idempotency_key="fac4-linked-slip",
        request_fingerprint="a" * 64,
        context=AuditContext.user(world.counselor),
    )
    followup = GuidanceFollowUp.objects.create(
        student=world.student,
        source_kind="REFERRAL",
        source_id=pk,
        visibility="COUNSELOR_CONFIDENTIAL",
        category="COUNSELING",
        assigned_to=world.counselor,
        due_at=timezone.now() + timedelta(days=2),
        created_by=world.counselor,
        description_ciphertext="Synthetic retained opaque fixture",
        creation_key_digest="f" * 64,
        creation_request_fingerprint="e" * 64,
    )
    assert Referral.objects.get(pk=pk).received_at is None
    before_slip = list(type(slip).objects.filter(pk=slip.pk).values())
    before_followup = list(GuidanceFollowUp.objects.filter(pk=followup.pk).values())
    transition(world, pk)
    transition(world, pk, close=True)
    assert list(type(slip).objects.filter(pk=slip.pk).values()) == before_slip
    assert list(GuidanceFollowUp.objects.filter(pk=followup.pk).values()) == before_followup
    assert slip.lifecycle_state == "ACTIVE" and followup.status == "PENDING"
    # The existing active Call Slip void restriction still applies after administrative closure.
    with pytest.raises(services.ReferralVoidConflict):
        services.void_referral(
            actor=world.counselor,
            referral_id=pk,
            reason="Synthetic",
            context=AuditContext.user(world.counselor),
        )
    rendered = build_referral_render_context(get_referral(actor=world.counselor, referral_id=pk))
    assert "Synthetic confidential reason" in str(rendered)
    assert own(world, pk)["state"] == "ADMINISTRATIVELY_CLOSED"


def test_origin_filter_paginates_authoritative_rows_and_rejects_invalid_source(world):
    pk = submit(world)[0]["id"]
    result = services.list_referrals(
        actor=world.counselor, submission_channel="FACULTY_PORTAL", page_size=1
    )
    assert [item.pk for item in result.items] == [pk] and not result.has_next
    assert not services.list_referrals(
        actor=world.counselor, submission_channel="GCO_RECORDED"
    ).items
    with pytest.raises(services.InvalidReferralInput):
        services.list_referrals(actor=world.counselor, submission_channel="INVENTED")


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize("changed", ["inactive", "role", "capability", "home", "college", "campus"])
def test_own_tracking_rechecks_live_faculty_authority(world, closed, changed):
    pk = submit(world)[0]["id"]
    transition(world, pk)
    if closed:
        transition(world, pk, close=True)
    assert own(world, pk)["state"] == ("ADMINISTRATIVELY_CLOSED" if closed else "RECEIVED_BY_GCO")
    if changed == "inactive":
        world.faculty.is_active = False
        world.faculty.save(update_fields=["is_active"])
    elif changed == "role":
        world.faculty.role = Role.objects.get(code="IT_ADMIN")
        world.faculty.save(update_fields=["role"])
    elif changed == "capability":
        UserCapabilityOverride.objects.create(
            user=world.faculty,
            capability=Capability.objects.get(code="referrals.view_submitted_self"),
            effect="REVOKE",
            reason="Synthetic",
        )
    elif changed == "home":
        from compass.organization.models import FacultyAffiliation

        FacultyAffiliation.objects.filter(faculty=world.faculty).delete()
    elif changed == "college":
        world.ccms.is_active = False
        world.ccms.save(update_fields=["is_active"])
    else:
        world.campus.is_active = False
        world.campus.save(update_fields=["is_active"])
    with pytest.raises((FacultyReferralError, ReferralNotFound)):
        own(world, pk)
    if changed == "college":
        assert (
            faculty_services.list_own_submissions(
                actor=world.faculty, actor_session=world.issued.session
            )["items"]
            == []
        )
    else:
        with pytest.raises(FacultyReferralError):
            faculty_services.list_own_submissions(
                actor=world.faculty, actor_session=world.issued.session
            )


@pytest.mark.parametrize("stage", ["submitted", "acknowledged", "closed"])
def test_database_preserves_all_remaining_submission_and_administrative_history(world, stage):
    pk = submit(world)[0]["id"]
    if stage != "submitted":
        transition(world, pk)
    if stage == "closed":
        transition(world, pk, close=True)
    row = Referral.objects.get(pk=pk)
    changes = [
        {"submitted_by": world.other_faculty},
        {"submitted_at": row.submitted_at + timedelta(seconds=1)},
        {"faculty_home_college": world.ccms},
        {"student_college_at_submission": world.cas},
        {"student_name_snapshot": "Changed"},
        {"course_year_block_snapshot": "Changed"},
        {"form_revision_id": None},
        {"referred_on": row.referred_on + timedelta(days=1)},
        {"creation_key_digest": "b" * 64},
        {"creation_request_fingerprint": "c" * 64},
    ]
    if stage != "submitted":
        changes += [{"acknowledged_by": world.staff}, {"received_at": timezone.now()}]
    if stage == "closed":
        changes += [
            {"administratively_closed_by": world.staff},
            {"administratively_closed_at": timezone.now()},
            {
                "administratively_closed_by": None,
                "administratively_closed_at": None,
                "administrative_version": 2,
            },
        ]
    for change in changes:
        with pytest.raises(IntegrityError), transaction.atomic():
            Referral.objects.filter(pk=pk).update(**change)
    if stage != "submitted":
        with pytest.raises(IntegrityError), transaction.atomic():
            Referral.objects.filter(pk=pk).delete()
    assert Referral.objects.get(pk=pk).administrative_version == row.administrative_version
