"""Isolated synthetic approvals; no institution policy or external provider is activated."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import User
from compass.audit.actions import REFERRAL_FACULTY_POLICY_RECORDED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.sessions import create_auth_session
from compass.common.rate_limit import RateLimitResult
from compass.organization.models import Campus, College, FacultyAffiliation, StudentAffiliation
from compass.referrals import faculty_policy, faculty_services


def person(label, role):
    return User.objects.create_user(
        email=label + "@synthetic.invalid",
        institutional_id="FAC2-" + label,
        role=role,
        first_name="Synthetic",
        last_name=label,
    )


def seal(policy, kind):
    event = record_event(
        context=AuditContext.system(),
        action=REFERRAL_FACULTY_POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "APPROVED",
            "policy_kind": kind,
            "policy_digest": policy.digest,
            "policy_version": policy.version,
            "evidence_reference": policy.evidence_reference,
        },
    )
    return replace(policy, activation_event_id=event.pk)


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
    StudentAffiliation.objects.create(student=student, college=ccms)
    issued = create_auth_session(faculty, mfa_verified_at=timezone.now())
    other_issued = create_auth_session(other_faculty, mfa_verified_at=timezone.now())
    now = timezone.now()
    shared = dict(
        version="synthetic-fac2-v1",
        evidence_reference="SYNTHETIC-NOT-INSTITUTIONAL",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        faculty_ids=frozenset({faculty.pk, other_faculty.pk}),
        student_college_ids=frozenset({ccms.pk}),
        activation_event_id=uuid4(),
    )
    lookup = seal(
        faculty_policy.ApprovedFacultyStudentLookupPolicy(
            **shared,
            maximum_confirmation_age_seconds=300,
            actor_attempt_limit=100,
            ip_attempt_limit=200,
            attempt_window_seconds=60,
        ),
        "STUDENT_CONFIRMATION",
    )
    submission = seal(
        faculty_policy.ApprovedFacultySubmissionPolicy(
            **shared,
            lookup_policy_digest=lookup.digest,
            eligibility_evidence_reference="SYNTHETIC-ELIGIBILITY",
            own_projection_evidence_reference="SYNTHETIC-OWN-PROJECTION",
        ),
        "DIGITAL_SUBMISSION",
    )
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
        lookup=lookup,
        submission=submission,
        limiter=limiter,
    )
    monkeypatch.setattr(faculty_policy, "get_approved_lookup_policy", lambda: world.lookup)
    monkeypatch.setattr(faculty_policy, "get_approved_submission_policy", lambda: world.submission)
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
