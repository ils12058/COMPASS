"""Production providers and canonical capabilities, without policy or authority injection."""

from uuid import uuid4

import pytest
from django.utils import timezone

from compass.accounts.models import Designation, UserCapabilityOverride, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling import continuity_policy, coverage_selection, handoff_services
from compass.counseling.case_communication import authorize_case_coordination
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.provisional_continuity import EVENT_IDS, communication_policy
from compass.guidance_messages import services as messages
from compass.guidance_messages.errors import CaseCoordinationEnded, ThreadNotFound
from compass.organization.models import College, CounselorResponsibility, StaffSupervision
from tests.test_continuity import case, decide, request  # noqa: F401
from tests.test_continuity_access import (  # noqa: F401
    SENTINEL,
    metadata_case,  # noqa: F401
    read,
    selected_case,
)

# Imported fixtures are passed into tests below.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db(transaction=True)


def test_real_head_receiver_outsider_and_expiry(selected_case, monkeypatch):
    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    assert c.head.has_capability("counseling.continuity.approve")
    assert c.receiver.has_capability("counseling.continuity.read_selected")
    g = decide(c, request(c, communication_purpose="CASE_COORDINATION"))
    assert g["effective_status"] == "ACTIVE"
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    d = handoff_services.operate(
        actor=c.author,
        grant_id=g["id"],
        operation="save",
        expected_grant_version=g["version"],
        expected_version=0,
        body="Synthetic handoff",
    )
    handoff_services.operate(
        actor=c.author,
        grant_id=g["id"],
        operation="submit",
        expected_grant_version=g["version"],
        expected_version=d["version"],
    )
    assert (
        handoff_services.operate(
            actor=c.receiver,
            grant_id=g["id"],
            operation="receive",
            expected_grant_version=g["version"],
        )["content"]
        == "Synthetic handoff"
    )
    thread, _ = messages.open_case_coordination_thread(
        actor=c.author, grant_id=g["id"], client_message_id=uuid4(), body="Synthetic coordination"
    )
    assert messages.list_messages(actor=c.receiver, thread_id=thread.pk)[0]
    with pytest.raises(ContinuityError):
        read(c, g, actor=c.outsider)
    with pytest.raises(ThreadNotFound):
        messages.get_thread(actor=c.outsider, thread_id=thread.pk)
    moment = g["expires_at"]
    monkeypatch.setattr(timezone, "now", lambda: moment)
    for actor in (c.author, c.receiver):
        with pytest.raises(CaseCoordinationEnded):
            messages.list_messages(actor=actor, thread_id=thread.pk)
        with pytest.raises(ContinuityError):
            handoff_services.operate(
                actor=actor,
                grant_id=g["id"],
                operation="receive",
                expected_grant_version=g["version"],
            )
    with pytest.raises(ContinuityError):
        read(c, g)


def test_live_membership_and_completed_approval_survive_turnover(selected_case):
    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    g = decide(c, request(c, communication_purpose="CASE_COORDINATION"))
    before = continuity_policy.get_approved_policy()
    evidence_count = AuditEvent.objects.filter(pk__in=EVENT_IDS.values()).count()
    new_head = c.user("new-head")
    assistant = c.user("new-assistant", "GUIDANCE_OFFICE_ASSISTANT")
    UserCapabilityOverride.objects.all().delete()
    UserDesignation.objects.filter(user=c.head).delete()
    c.head.is_active = False
    c.head.save(update_fields=["is_active"])
    UserDesignation.objects.create(
        user=new_head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    added = College.objects.create(campus=c.campus, code="NEW", name="New College")
    current = continuity_policy.get_approved_policy()
    assert current.digest == before.digest
    assert new_head.pk in current.approver_ids and c.head.pk not in current.approver_ids
    assert assistant.pk in current.office_requester_ids and added.pk in current.college_ids
    assert read(c, g)["evaluation"]["recommendations"] == SENTINEL
    authorize_case_coordination(actor=c.receiver, grant_id=g["id"])
    assert AuditEvent.objects.filter(pk__in=EVENT_IDS.values()).count() == evidence_count


def test_assistant_request_uses_live_responsibility_and_independent_head(selected_case):
    c = selected_case
    assistant = c.user("office-assistant", "GUIDANCE_OFFICE_ASSISTANT")
    UserCapabilityOverride.objects.all().delete()
    StaffSupervision.objects.create(staff=assistant, supervisor=c.author)
    CounselorResponsibility.objects.create(college=c.college, counselor=c.author)
    config = coverage_selection.configuration(actor=assistant)
    assert config["can_request"] and not config["can_approve"]
    assert {x["student_id"] for x in config["office_cases"]} == {c.student.pk}
    assert (
        len(
            coverage_selection.select(
                actor=assistant, student_id=c.student.pk, original_counselor_id=c.author.pk
            )["items"]
        )
        == 2
    )
    g = request(c, actor=assistant, coverage_kind="TEMPORARY_COVERAGE")
    with pytest.raises(ContinuityError):
        decide(c, g, actor=assistant)
    assert decide(c, g)["effective_status"] == "ACTIVE"
    CounselorResponsibility.objects.filter(college=c.college).delete()
    assert coverage_selection.configuration(actor=assistant)["office_cases"] == []
    with pytest.raises(ContinuityError):
        coverage_selection.select(
            actor=assistant, student_id=c.student.pk, original_counselor_id=c.author.pk
        )


def test_fixed_events_are_provisional_and_idempotent(case):
    continuity_policy.get_approved_policy().validate(timezone.now())
    communication_policy().validate(timezone.now())
    events = list(AuditEvent.objects.filter(pk__in=EVENT_IDS.values()))
    assert len(events) == 4
    assert all(e.metadata["decision"] == "PROVISIONAL" for e in events)
    assert all(
        e.metadata["evidence_reference"] == "CODE_OWNED_PROVISIONAL_NOT_INSTITUTIONAL"
        for e in events
    )
    continuity_policy.get_approved_policy()
    communication_policy()
    assert AuditEvent.objects.filter(pk__in=EVENT_IDS.values()).count() == 4


def test_demo_coverage_uses_real_services_and_does_not_extend_expiry(selected_case):
    from types import SimpleNamespace

    from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
    from compass.staging_seed.scenarios.continuity import DEMO_REQUEST_ID, seed_demo_coverage
    from compass.staging_seed.staff import COUNSELOR_A, COUNSELOR_B, HEAD_GUIDANCE
    from compass.staging_seed.students import FOURTH_YEAR

    c = selected_case
    UserCapabilityOverride.objects.all().delete()
    users = {
        COUNSELOR_A.key: c.author,
        COUNSELOR_B.key: c.receiver,
        HEAD_GUIDANCE.key: c.head,
        FOURTH_YEAR.key: c.student,
    }
    records = []
    session = SimpleNamespace(user=users.__getitem__, record=lambda name, **kw: records.append(kw))
    seed_demo_coverage(session)
    grant = Grant.objects.get(request_id=DEMO_REQUEST_ID)
    expiry = grant.expires_at
    assert grant.decision == "APPROVED" and grant.communication_purpose == "CASE_COORDINATION"
    assert (
        read(c, {"id": grant.pk, "version": grant.version})["evaluation"]["recommendations"]
        == SENTINEL
    )
    seed_demo_coverage(session)
    grant.refresh_from_db()
    assert grant.expires_at == expiry and records == [{"created": True}, {"created": False}]


@pytest.mark.parametrize("kind", ["CONTINUITY", "DISCLOSURE", "COVERAGE", "COMMUNICATION"])
def test_fixed_audit_evidence_cannot_be_replaced_with_institutional_approval(kind):
    from compass.audit.actions import CONTINUITY_POLICY_RECORDED
    from compass.audit.models import AuditActorType, AuditOutcome
    from compass.counseling import provisional_continuity as policies

    event = AuditEvent.objects.create(
        pk=EVENT_IDS[kind],
        occurred_at=timezone.now(),
        actor_type=AuditActorType.SYSTEM,
        action=CONTINUITY_POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={"decision": "APPROVED"},
    )
    provider = {
        "CONTINUITY": policies.continuity_policy,
        "DISCLOSURE": policies.disclosure_policy,
        "COVERAGE": policies.workflow_policy,
        "COMMUNICATION": policies.communication_policy,
    }[kind]
    with pytest.raises(ContinuityError, match="policy_unconfirmed"):
        provider().validate(timezone.now())
    event.refresh_from_db()
    assert event.metadata == {"decision": "APPROVED"}
