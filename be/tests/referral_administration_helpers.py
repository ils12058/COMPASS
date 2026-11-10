"""Synthetic Counselor responsibility and staff supervision for Referral tests."""

from django.utils import timezone

from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.referrals import administration
from tests.faculty_referral_helpers import make_world as intake_world
from tests.faculty_referral_helpers import person


def make_world(monkeypatch):
    world = intake_world(monkeypatch)
    world.counselor = person("ccms-counselor", "COUNSELOR")
    world.other_counselor = person("cas-counselor", "COUNSELOR")
    world.staff = person("goa", "GUIDANCE_OFFICE_ASSISTANT")
    CounselorResponsibility.objects.create(college=world.ccms, counselor=world.counselor)
    CounselorResponsibility.objects.create(college=world.cas, counselor=world.other_counselor)
    StaffSupervision.objects.create(staff=world.staff, supervisor=world.counselor)
    for name in ("counselor", "other_counselor", "staff"):
        setattr(
            world,
            name + "_issued",
            create_auth_session(getattr(world, name), mfa_verified_at=timezone.now()),
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
