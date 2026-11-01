"""Synthetic FAC-D5/D6/D7 evidence, isolated from the unavailable live providers."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.sessions import create_auth_session
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.referrals import administration
from compass.referrals import administrative_policy as policy
from tests.faculty_referral_helpers import make_world as intake_world
from tests.faculty_referral_helpers import person


def seal_admin(world, kind, **changes):
    faculty = kind.startswith("FACULTY_")
    now = timezone.now()
    values = dict(
        version="synthetic-fac4-v1",
        evidence_reference="SYNTHETIC-NOT-INSTITUTIONAL",
        contract_evidence_reference="SYNTHETIC-CRITERIA",
        kind=kind,
        contract=policy.CONTRACTS[kind],
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        activation_event_id=uuid4(),
        actor_ids=frozenset(
            {world.faculty.pk, world.other_faculty.pk}
            if faculty
            else {world.counselor.pk, world.staff.pk, world.other_counselor.pk}
        ),
        roles=frozenset({"FACULTY"} if faculty else {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}),
        student_college_ids=frozenset({world.ccms.pk}),
    )
    values.update(changes)
    approved = policy.ApprovedAdministrativePolicy(**values)
    event = record_event(
        context=AuditContext.system(),
        action=policy.POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "APPROVED",
            "policy_kind": kind,
            "policy_digest": approved.digest,
            "policy_version": approved.version,
            "evidence_reference": approved.evidence_reference,
        },
    )
    return replace(approved, activation_event_id=event.pk)


def make_world(monkeypatch):
    world = intake_world(monkeypatch)
    world.counselor = person("ccms-counselor", "COUNSELOR")
    world.other_counselor = person("cas-counselor", "COUNSELOR")
    world.staff = person("gss", "GUIDANCE_SERVICES_STAFF")
    CounselorResponsibility.objects.create(college=world.ccms, counselor=world.counselor)
    CounselorResponsibility.objects.create(college=world.cas, counselor=world.other_counselor)
    StaffSupervision.objects.create(staff=world.staff, supervisor=world.counselor)
    for name in ("counselor", "other_counselor", "staff"):
        setattr(
            world,
            name + "_issued",
            create_auth_session(getattr(world, name), mfa_verified_at=timezone.now()),
        )
    world.ack_policy = seal_admin(world, "ACKNOWLEDGMENT")
    world.close_policy = seal_admin(world, "CLOSURE")
    world.tracking_policy = seal_admin(world, "FACULTY_TRACKING")
    monkeypatch.setattr(policy, "get_approved_acknowledgment_policy", lambda: world.ack_policy)
    monkeypatch.setattr(policy, "get_approved_closure_policy", lambda: world.close_policy)
    monkeypatch.setattr(
        policy, "get_approved_tracking_disclosure_policy", lambda: world.tracking_policy
    )
    return world


def transition(world, referral_id, *, close=False, **changes):
    args = dict(
        actor=world.counselor,
        actor_session=world.counselor_issued.session,
        referral_id=referral_id,
        expected_version=2 if close else 1,
        kind="CLOSURE" if close else "ACKNOWLEDGMENT",
        obligations_reviewed=close,
        context=AuditContext.user(world.counselor),
    )
    args.update(changes)
    return administration.transition(**args)
