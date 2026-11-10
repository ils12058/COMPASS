"""Synthetic Faculty accounts, placements and isolated confirmation limiter."""

from types import SimpleNamespace

from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.common.rate_limit import RateLimitResult
from compass.organization.models import Campus, College, FacultyAffiliation
from compass.referrals import faculty_services
from compass.student_academics.models import StudentAcademicProfile


def person(label, role):
    return User.objects.create_user(
        email=label + "@synthetic.invalid",
        institutional_id="FAC2-" + label,
        role=role,
        first_name="Synthetic",
        last_name=label,
    )


class SyntheticLimiter:
    def __init__(self):
        self.counts = {}

    def consume(self, policy, subject):
        key = policy.name, subject
        count = self.counts[key] = self.counts.get(key, 0) + 1
        return RateLimitResult(
            count <= policy.limit, count, policy.limit, max(0, policy.limit - count), 60
        )


def make_world(monkeypatch):
    sync_identity_policy()
    admin = person("admin", "IT_ADMIN")
    faculty = person("faculty", "FACULTY")
    other_faculty = person("other-faculty", "FACULTY")
    student = person("student", "STUDENT")
    campus = Campus.objects.create(code="FAC2", name="Synthetic Campus")
    cas = College.objects.create(campus=campus, code="CAS", name="Synthetic CAS")
    ccms = College.objects.create(campus=campus, code="CCMS", name="Synthetic CCMS")
    for member in (faculty, other_faculty):
        FacultyAffiliation.objects.create(
            faculty=member, college=cas, assigned_by=admin, basis="Synthetic"
        )
    StudentAcademicProfile.objects.create(student=student, current_college=ccms)
    issued = create_auth_session(faculty, mfa_verified_at=timezone.now())
    other_issued = create_auth_session(other_faculty, mfa_verified_at=timezone.now())
    limiter = SyntheticLimiter()
    monkeypatch.setattr(faculty_services.RedisRateLimiter, "from_settings", lambda: limiter)
    world = SimpleNamespace(
        admin=admin,
        faculty=faculty,
        other_faculty=other_faculty,
        student=student,
        cas=cas,
        ccms=ccms,
        campus=campus,
        issued=issued,
        other_issued=other_issued,
        limiter=limiter,
    )
    return world


def confirm(world, *, actor=None, issued=None):
    return faculty_services.confirm_student(
        actor=actor or world.faculty,
        actor_session=(issued or world.issued).session,
        institutional_id=world.student.institutional_id,
        ip_address="127.0.0.1",
    )


def submit(world, confirmation=None, **changes):
    args = dict(
        actor=world.faculty,
        actor_session=world.issued.session,
        confirmation=confirmation or confirm(world)["confirmation"],
        course_year_block="Faculty supplied course/year/block",
        reason="Synthetic confidential reason",
        idempotency_key="synthetic-faculty-referral",
        context=AuditContext.user(world.faculty),
    )
    args.update(changes)
    return faculty_services.submit_referral(**args)
