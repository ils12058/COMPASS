"""Synthetic domain activity: typed ownership, current authority and negative disclosure cases."""

from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.activity.domains import DOMAIN_ACTIVITY_POLICIES
from compass.activity.presenters import MY_ACTIVITY_PRESENTERS, SECURITY_ACTIVITY_PRESENTERS
from compass.activity.projections import get_my_activity, get_security_activity
from compass.appointments.models import Appointment
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent, AuditEventAppendOnlyError
from compass.audit.services import record_event
from compass.authentication.actions import AUTH_LOGIN_SUCCESS, AUTH_SESSION_CREATED
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip
from compass.exit_interviews.confidential_content import (
    ExitInterviewConfidentialContent,
    write_exit_interview_confidential_content,
)
from compass.exit_interviews.models import ExitInterview
from compass.good_moral.models import GoodMoralRequest
from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.referrals.confidential_content import (
    ReferralConfidentialContent,
    write_referral_confidential_content,
)
from compass.referrals.models import Referral, ReferralAction
from compass.routine_interviews.content import initial_content
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service
from tests.inventory_encryption_helpers import create_inventory_row

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    call_command("sync_identity_policy", stdout=StringIO())
    roles = {
        "student": "STUDENT",
        "other": "STUDENT",
        "counselor": "COUNSELOR",
        "unrelated": "COUNSELOR",
        "head": "COUNSELOR",
        "gss": "GUIDANCE_SERVICES_STAFF",
        "it": "IT_ADMIN",
        "dpo": "INSTITUTIONAL_OFFICER",
    }
    people = {
        name: User.objects.create_user(
            email=f"act2-{name}@example.edu",
            password=None,
            role=Role.objects.get(code=role),
            first_name=name,
            last_name="Synthetic",
        )
        for name, role in roles.items()
    }
    for name, designation in (("head", "HEAD_GUIDANCE_COUNSELOR"), ("dpo", "DPO")):
        UserDesignation.objects.create(
            user=people[name], designation=Designation.objects.get(code=designation)
        )
    campus = Campus.objects.create(code="ACT2", name="Synthetic Campus")
    college = College.objects.create(campus=campus, code="ACT2A", name="Synthetic College")
    outside = College.objects.create(campus=campus, code="ACT2B", name="Other College")
    CounselorResponsibility.objects.create(college=college, counselor=people["counselor"])
    CounselorResponsibility.objects.create(college=outside, counselor=people["unrelated"])
    StaffSupervision.objects.create(staff=people["gss"], supervisor=people["counselor"])
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    service = Service.objects.create(code="ACT2", name="Synthetic service")
    counseling = Service.objects.create(code="COUNSELING", name="Counseling")
    rows = {}
    for name, owner_college in (("student", college), ("other", outside)):
        student = people[name]
        StudentAffiliation.objects.create(student=student, college=owner_college)
        inventory = create_inventory_row(
            StudentInventory,
            student=student,
            academic_year=year,
            form_revision=FormRevision.objects.get(
                family__key="individual_inventory", status="ACTIVE"
            ),
        )
        exit_interview = ExitInterview(student=student, academic_year=year, inventory=inventory)
        write_exit_interview_confidential_content(
            exit_interview, ExitInterviewConfidentialContent(dean_comments="SECRET ANSWERS")
        )
        exit_interview.save(force_insert=True)
        request = GoodMoralRequest.objects.create(student=student, variant="GRADUATE")
        routine_id = uuid4()
        routine = RoutineInterview.objects.create(
            id=routine_id,
            student=student,
            counselor=people["counselor"],
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            **initial_content(routine_id),
        )
        referral = Referral(
            student=student,
            reference_code=f"ACT2-{name}",
            referred_on=timezone.localdate(),
            form_revision=FormRevision.objects.get(family__key="referral_slip", status="ACTIVE"),
        )
        write_referral_confidential_content(
            referral,
            ReferralConfidentialContent(
                reason="SECRET REFERRAL", referrer_name="SECRET THIRD PARTY"
            ),
        )
        referral.save(force_insert=True)
        child = ReferralAction.objects.create(
            referral=referral,
            action_type="CALL_PARENT_GUARDIAN",
            occurred_at=timezone.now(),
            remarks_ciphertext="synthetic-unread-ciphertext",
        )
        slip = CallSlip.objects.create(
            student=student,
            destination_type="GUIDANCE_OFFICE",
            report_at=timezone.now(),
            issuance_mode="HISTORICAL",
            issued_by=people["head"],
            form_revision=FormRevision.objects.get(family__key="call_slip", status="ACTIVE"),
        )
        appointment = Appointment.objects.create(
            student=student,
            provider=people["counselor"],
            service=service,
            reference_code=f"ACT2-{name}",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
            delivery_mode="IN_PERSON",
        )
        rows[name] = {
            "appointments.appointment": appointment,
            "inventory.studentinventory": inventory,
            "goodmoral.request": request,
            "exitinterviews.exitinterview": exit_interview,
            "routine.interview": routine,
            "referrals.referral": referral,
            "referrals.referralaction": child,
            "callslips.callslip": slip,
        }
    return {
        **people,
        "rows": rows,
        "college": college,
        "outside": outside,
        "counseling": counseling,
    }


def emit(
    actor, action, source=None, *, target_type=None, target_id=None, outcome="SUCCESS", at=None
):
    return record_event(
        context=AuditContext.user(actor, request_id=uuid4()),
        action=action,
        outcome=outcome,
        target_type=target_type or DOMAIN_ACTIVITY_POLICIES[action].target_type,
        target_id=target_id if target_id is not None else source.pk,
        occurred_at=at or timezone.now(),
        metadata={"internal_note": "SECRET AUDIT METADATA"},
    )


def ids(user, **kwargs):
    return [item.id for item in get_my_activity(user, **kwargs).items]


@pytest.mark.parametrize("action", list(DOMAIN_ACTIVITY_POLICIES))
def test_allowlisted_actions_have_exact_viewer_relationships(world, action):
    policy = DOMAIN_ACTIVITY_POLICIES[action]
    source = world["rows"]["student"][policy.target_type]
    actor = (
        world["student"]
        if policy.student_self
        else world["head"]
        if action == actions.EXIT_INTERVIEW_REOPENED
        else world["counselor"]
    )
    event = emit(actor, action, source)
    student_items = get_my_activity(world["student"]).items
    if policy.student_self or policy.student_affected:
        assert [item.id for item in student_items] == [event.id]
        assert student_items[0].description == (policy.student_self or policy.student_affected)
    else:
        assert student_items == ()
    assert ids(world["other"]) == []
    if policy.staff_self:
        if policy.student_self:
            actor = world["counselor"]
            if action == actions.GOOD_MORAL_REQUEST_CREATED:
                source = GoodMoralRequest.objects.create(
                    student=world["student"],
                    variant="GRADUATE",
                    initiation_origin="GCO_ASSISTED",
                    initiated_by=actor,
                )
            event = emit(actor, action, source)
        assert ids(actor) == [event.id]
        assert get_my_activity(actor).items[0].description == policy.staff_self
    else:
        assert ids(world["head"]) == []
    assert ids(world["unrelated"]) == []
    assert ids(world["gss"]) == []
    assert ids(world["dpo"]) == []
    assert ids(world["it"]) == []
    assert get_security_activity(actor).items == ()


@pytest.mark.parametrize(
    "bad_id", ["not-a-uuid", "42", "", str(uuid4()), "00000000-0000-0000-0000-000000000000"]
)
def test_malformed_and_orphaned_targets_fail_closed(world, bad_id):
    # Empty strings normalize to no target, so use a valid target ID for that wrong-type case.
    emit(
        world["student"],
        actions.INVENTORY_SUBMITTED,
        target_type="inventory.other" if not bad_id else "inventory.studentinventory",
        target_id=bad_id or world["student"].pk,
    )
    assert ids(world["student"]) == []


@pytest.mark.parametrize("outcome", ["DENIED", "FAILED"])
def test_ineligible_outcomes_never_imply_success(world, outcome):
    for action, policy in DOMAIN_ACTIVITY_POLICIES.items():
        emit(world["head"], action, world["rows"]["student"][policy.target_type], outcome=outcome)
    assert ids(world["head"]) == []
    assert ids(world["student"]) == []


def test_cross_domain_and_child_substitution_cannot_establish_ownership(world):
    student, counselor = world["student"], world["counselor"]
    own = world["rows"]["student"]
    other = world["rows"]["other"]
    emit(student, actions.INVENTORY_SUBMITTED, own["goodmoral.request"])
    emit(student, actions.INVENTORY_SUBMITTED, other["inventory.studentinventory"])
    emit(
        student,
        actions.INVENTORY_SUBMITTED,
        own["inventory.studentinventory"],
        target_type="goodmoral.request",
    )
    emit(counselor, actions.REFERRAL_ACTION_RECORDED, own["referrals.referral"])
    emit(counselor, actions.REFERRAL_ACTION_RECORDED, other["referrals.referralaction"])
    good = emit(counselor, actions.REFERRAL_ACTION_RECORDED, own["referrals.referralaction"])
    assert ids(student) == []
    assert ids(counselor) == [good.id]
    # Reassigning the canonical parent owner removes current scope immediately.
    Referral.objects.filter(pk=own["referrals.referral"].pk).update(student=world["other"])
    assert ids(counselor) == []


def test_real_inventory_correction_sequence_and_unrelated_issuance(world):
    from compass.inventory.services import reopen_inventory_for_correction

    student, counselor = world["student"], world["counselor"]
    inventory = world["rows"]["student"]["inventory.studentinventory"]
    submitted = timezone.now()
    StudentInventory.objects.filter(pk=inventory.pk).update(
        submitted_at=submitted,
        first_submitted_at=submitted,
        last_submitted_at=submitted,
    )
    created = emit(
        student, actions.INVENTORY_CREATED, inventory, at=submitted - timedelta(minutes=2)
    )
    initial = emit(
        student, actions.INVENTORY_SUBMITTED, inventory, at=submitted - timedelta(minutes=1)
    )
    reopened = reopen_inventory_for_correction(
        actor=counselor,
        inventory_id=inventory.pk,
        reason="SECRET CORRECTION REASON",
        context=AuditContext.user(counselor),
        targets=["personal.full_name"],
    )
    reopen_event = AuditEvent.objects.get(
        action=actions.INVENTORY_REOPENED, target_id=str(reopened.pk)
    )
    resubmitted = emit(student, actions.INVENTORY_RESUBMITTED, inventory)
    issued = emit(counselor, actions.GOOD_MORAL_ISSUED, world["rows"]["other"]["goodmoral.request"])
    assert ids(student) == [resubmitted.id, reopen_event.id, initial.id, created.id]
    assert ids(counselor) == [issued.id, reopen_event.id]
    descriptions = [item.description for item in get_my_activity(student).items]
    assert descriptions[1] == "Your Individual Inventory was returned for correction."
    reopen_event.refresh_from_db()
    assert reopen_event.actor_user_id == counselor.pk
    # The unrelated applicant sees its issuance effect only, never the first Student's Inventory.
    assert ids(world["other"]) == [issued.id]


def test_gss_has_own_operational_activity_without_professional_or_supervision_fallback(world):
    gss = world["gss"]
    own = world["rows"]["student"]
    expected = []
    for action in (
        actions.GOOD_MORAL_PREPARED,
        actions.CALL_SLIP_CREATED,
        actions.REFERRAL_CREATED,
    ):
        expected.append(emit(gss, action, own[DOMAIN_ACTIVITY_POLICIES[action].target_type]).id)
    emit(gss, actions.INVENTORY_REOPENED, own["inventory.studentinventory"])
    emit(gss, actions.GOOD_MORAL_ISSUED, own["goodmoral.request"])
    emit(world["counselor"], actions.GOOD_MORAL_PREPARED, own["goodmoral.request"])
    assert ids(gss) == list(reversed(expected))
    StaffSupervision.objects.filter(staff=gss).delete()
    assert ids(gss) == [expected[0]]  # Good Moral staff reads have no delegated college scope.


def test_appointment_relationship_scope_and_head_are_not_global(world):
    source = world["rows"]["student"]["appointments.appointment"]
    source.service = world["counseling"]
    source.save(update_fields=["service"])
    own = emit(world["counselor"], actions.APPOINTMENT_RESCHEDULED, source)
    emit(world["head"], actions.APPOINTMENT_RESCHEDULED, source)
    emit(world["gss"], actions.APPOINTMENT_RESCHEDULED, source)
    assert ids(world["counselor"]) == [own.id]
    assert ids(world["head"]) == []
    assert ids(world["gss"]) == []
    source.provider = world["unrelated"]
    source.save(update_fields=["provider"])
    assert ids(world["counselor"]) == []


@pytest.mark.parametrize(
    "viewer, capability",
    [
        ("student", "inventory.view_self"),
        ("counselor", "inventory.view"),
        ("gss", "good_moral.view"),
        ("head", "exit_interviews.view"),
    ],
)
def test_revoked_read_capabilities_hide_previously_eligible_events(world, viewer, capability):
    action = {
        "student": actions.INVENTORY_SUBMITTED,
        "counselor": actions.INVENTORY_REOPENED,
        "gss": actions.GOOD_MORAL_PREPARED,
        "head": actions.EXIT_INTERVIEW_REOPENED,
    }[viewer]
    actor = world[viewer]
    emit(actor, action, world["rows"]["student"][DOMAIN_ACTIVITY_POLICIES[action].target_type])
    assert len(ids(actor)) == 1
    UserCapabilityOverride.objects.create(
        user=actor,
        capability=Capability.objects.get(code=capability),
        effect="REVOKE",
    )
    assert ids(actor) == []


@pytest.mark.parametrize("viewer", ["dpo", "it"])
def test_administrative_roles_cannot_gain_domain_feed_through_capability_override(world, viewer):
    actor = world[viewer]
    for code in (
        "inventory.view",
        "exit_interviews.view",
        "good_moral.view",
        "referrals.view",
        "call_slips.view",
        "appointments.manage",
    ):
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
        )
    for action, policy in DOMAIN_ACTIVITY_POLICIES.items():
        emit(actor, action, world["rows"]["student"][policy.target_type])
    assert ids(actor) == []
    account = emit(actor, AUTH_LOGIN_SUCCESS, target_type="accounts.user", target_id=actor.pk)
    assert ids(actor) == [account.id]


def test_professional_exclusions_even_for_owner_actor_and_assigned_counselor(world):
    for actor in (world["student"], world["counselor"]):
        for action, target in (
            (actions.ROUTINE_INTERVIEW_ENCOUNTER_LINKED, "routine.interview"),
            (actions.ROUTINE_INTERVIEW_EVALUATION_FINALIZED, "routine.interview"),
            (actions.CALL_SLIP_INTERVIEW_ENDED, "callslips.callslip"),
            (actions.COUNSELING_ENCOUNTER_CREATED, "counseling.encounter"),
        ):
            source = world["rows"]["student"].get(target)
            emit(actor, action, target_type=target, target_id=source.pk if source else uuid4())
    assert ids(world["student"]) == []
    assert ids(world["counselor"]) == []
    # Staff creation is not intake submission and is not disclosed to the affected Student.
    emit(
        world["counselor"],
        actions.ROUTINE_INTERVIEW_CREATED,
        world["rows"]["student"]["routine.interview"],
    )
    assert ids(world["student"]) == []


def test_mixed_long_history_filters_before_pagination_and_never_duplicates(world):
    user = world["student"]
    now = timezone.now()
    expected = []
    for _index in range(63):
        source = world["rows"]["student"]["inventory.studentinventory"]
        expected.append(emit(user, actions.INVENTORY_SUBMITTED, source, at=now).id)
        emit(
            user,
            actions.INVENTORY_SUBMITTED,
            world["rows"]["other"]["inventory.studentinventory"],
            at=now,
        )
    expected.append(
        emit(user, AUTH_LOGIN_SUCCESS, target_type="accounts.user", target_id=user.pk, at=now).id
    )
    expected.sort(reverse=True)
    actual = []
    counts = []
    for page in range(1, 5):
        with CaptureQueriesContext(connection) as queries:
            result = get_my_activity(user, page=page)
        counts.append(len(queries))
        actual.extend(item.id for item in result.items)
        assert result.has_next == (page < 4)
        assert len(result.items) == (20 if page < 4 else 4)
    assert actual == expected
    assert len(set(actual)) == 64
    assert len(set(counts)) == 1
    assert counts[0] <= 5  # Three capability reads, one source SELECT, no per-event queries.
    assert all("metadata" not in q["sql"] for q in queries)
    overlap = emit(
        user, actions.APPOINTMENT_CANCELLED, world["rows"]["student"]["appointments.appointment"]
    )
    assert ids(user).count(overlap.id) == 1
    assert len(get_my_activity(user, page_size=50).items) == 50


def test_api_minimization_no_actor_impersonation_or_evidence_mutation(world, client):
    user = world["student"]
    event = emit(
        world["head"],
        actions.INVENTORY_REOPENED,
        world["rows"]["student"]["inventory.studentinventory"],
    )
    original = AuditEvent.objects.values().get(pk=event.pk)
    session = create_auth_session(user)
    client.cookies["compass_session"] = session.token
    response = client.get(
        f"/api/v1/me/activity?user_id={world['other'].pk}&actor_id={world['head'].pk}"
    )
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [str(event.pk)]
    assert set(response.json()["items"][0]) == {"id", "type", "title", "description", "occurred_at"}
    for secret in (
        "SECRET",
        str(event.target_id),
        str(event.request_id),
        str(world["head"].pk),
        "metadata",
        "actor_user_id",
        "target_id",
    ):
        assert secret not in response.content.decode()
    assert AuditEvent.objects.values().get(pk=event.pk) == original
    with pytest.raises(AuditEventAppendOnlyError):
        event.save()


def test_security_registry_is_explicit_and_independent(world, monkeypatch):
    assert AUTH_SESSION_CREATED not in SECURITY_ACTIVITY_PRESENTERS
    assert not set(DOMAIN_ACTIVITY_POLICIES).intersection(SECURITY_ACTIVITY_PRESENTERS)
    monkeypatch.setitem(
        MY_ACTIVITY_PRESENTERS, "future.domain.action", next(iter(MY_ACTIVITY_PRESENTERS.values()))
    )
    assert "future.domain.action" not in SECURITY_ACTIVITY_PRESENTERS


def test_deleted_source_and_spoofed_metadata_cannot_preserve_owner_access(world):
    request = world["rows"]["student"]["goodmoral.request"]
    event = emit(world["head"], actions.GOOD_MORAL_ISSUED, request)
    assert ids(world["student"]) == [event.pk]
    request.delete()
    assert ids(world["student"]) == []
    assert ids(world["head"]) == []
    assert AuditEvent.objects.filter(pk=event.pk).exists()
    record_event(
        context=AuditContext.user(world["head"]),
        action=actions.GOOD_MORAL_ISSUED,
        outcome="SUCCESS",
        target_type="goodmoral.request",
        target_id=uuid4(),
        metadata={"student_id": str(world["student"].pk)},
    )
    assert ids(world["student"]) == []


def test_system_and_anonymous_domain_events_are_not_invented_user_actions(world):
    request = world["rows"]["student"]["goodmoral.request"]
    for context in (AuditContext.system(), AuditContext.anonymous()):
        record_event(
            context=context,
            action=actions.GOOD_MORAL_ISSUED,
            outcome="SUCCESS",
            target_type="goodmoral.request",
            target_id=request.pk,
        )
    assert ids(world["student"]) == []


def test_staff_scope_loss_and_inactive_sources_follow_existing_read_rules(world):
    user = world["counselor"]
    source = world["rows"]["student"]["inventory.studentinventory"]
    event = emit(user, actions.INVENTORY_REOPENED, source)
    assert ids(user) == [event.pk]
    # Scoped Inventory history requires an active Student in an active college/campus.
    College.objects.filter(pk=world["college"].pk).update(is_active=False)
    assert ids(user) == []
    College.objects.filter(pk=world["college"].pk).update(is_active=True)
    assert ids(user) == [event.pk]
    CounselorResponsibility.objects.filter(counselor=user).delete()
    assert ids(user) == []


def test_inactive_viewer_has_no_domain_projection(world):
    user = world["student"]
    emit(user, actions.INVENTORY_SUBMITTED, world["rows"]["student"]["inventory.studentinventory"])
    user.is_active = False
    assert ids(user) == []


def test_domain_copy_is_bounded_and_all_source_reads_avoid_content(world):
    for policy in DOMAIN_ACTIVITY_POLICIES.values():
        assert len(policy.title) <= 100
        for description in (policy.student_self, policy.student_affected, policy.staff_self):
            assert description is None or len(description) <= 160
    user = world["head"]
    for action, policy in DOMAIN_ACTIVITY_POLICIES.items():
        emit(user, action, world["rows"]["student"][policy.target_type])
    with CaptureQueriesContext(connection) as queries:
        get_my_activity(user, page_size=1)
    first_count = len(queries)
    with CaptureQueriesContext(connection) as queries:
        get_my_activity(user, page_size=50)
    assert len(queries) == first_count
    for query in queries:
        assert "ciphertext" not in query["sql"]
        assert "metadata" not in query["sql"]


def test_assisted_creation_requires_persisted_initiator_and_origin(world):
    request = world["rows"]["student"]["goodmoral.request"]
    forged = emit(world["counselor"], actions.GOOD_MORAL_REQUEST_CREATED, request)
    assert forged.pk not in ids(world["student"])
    assert forged.pk not in ids(world["counselor"])
    request.initiation_origin = "GCO_ASSISTED"
    request.initiated_by = world["gss"]
    request.save(update_fields=["initiation_origin", "initiated_by"])
    assert forged.pk not in ids(world["student"])
    verified = emit(world["gss"], actions.GOOD_MORAL_REQUEST_CREATED, request)
    assert ids(world["student"]) == [verified.pk]
    assert ids(world["gss"]) == [verified.pk]
