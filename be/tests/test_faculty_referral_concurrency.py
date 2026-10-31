"""Real independent PostgreSQL connections, observed row/advisory lock waits."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from compass.account_management.faculty import set_faculty_affiliation
from compass.account_management.services import change_role, set_account_active
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.organization.models import CounselorResponsibility, StudentAffiliation
from compass.referrals import faculty_services, services
from compass.referrals.faculty_policy import FacultyReferralError
from compass.referrals.models import Referral, ReferralReferenceCounter
from tests.faculty_referral_helpers import confirm, make_world, person, submit

pytestmark = pytest.mark.django_db(transaction=True)


def ordered_race(first, second):
    held, release, entering = Event(), Event(), Event()
    contender_pid = []

    def winner():
        close_old_connections()
        try:
            with transaction.atomic():
                result = first()
                held.set()
                assert release.wait(15)
            return result
        finally:
            connection.close()

    def contender():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                contender_pid.append(cursor.fetchone()[0])
            entering.set()
            try:
                return second()
            except Exception as error:
                return error
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(winner)
        try:
            assert held.wait(15)
            b = pool.submit(contender)
            assert entering.wait(15)
            until = monotonic() + 10
            waiting = False
            while monotonic() < until:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=%s",
                        [contender_pid[0]],
                    )
                    waiting = cursor.fetchone()[0]
                if waiting:
                    break
                if b.done():
                    raise AssertionError(f"No actual lock wait: {b.result()!r}")
                release.wait(0.01)
            assert waiting, "No real PostgreSQL lock contention observed"
        finally:
            release.set()
        return a.result(timeout=15), b.result(timeout=15)


@pytest.mark.parametrize("change_first", [False, True])
@pytest.mark.parametrize("change", ["role", "inactive", "affiliation", "student_placement"])
def test_submission_serializes_with_current_identity_and_placement(
    monkeypatch, change_first, change
):
    world = make_world(monkeypatch)
    ticket = confirm(world)["confirmation"]
    issued_admin = create_auth_session(world.admin, mfa_verified_at=timezone.now())
    args = dict(
        actor=world.admin,
        actor_session=issued_admin.session,
        context=AuditContext.user(world.admin),
    )

    def mutate():
        if change == "role":
            return change_role(**args, target_id=world.faculty.pk, role="INSTITUTIONAL_OFFICER")
        if change == "inactive":
            return set_account_active(**args, target_id=world.faculty.pk, is_active=False)
        if change == "affiliation":
            return set_faculty_affiliation(
                **args,
                target_id=world.faculty.pk,
                college_id=world.ccms.pk,
                expected_resource_version=1,
                basis="Synthetic",
            )
        from compass.organization.services import set_student_affiliation

        return set_student_affiliation(
            student_id=world.student.pk, college_id=world.cas.pk, context=args["context"]
        )

    def submit_one():
        return submit(world, ticket)

    a, b = ordered_race(
        mutate if change_first else submit_one, submit_one if change_first else mutate
    )
    if change_first:
        assert isinstance(b, FacultyReferralError)
        assert not Referral.objects.exists()
    else:
        assert not isinstance(b, Exception)
        row = Referral.objects.get()
        assert row.faculty_home_college_id == world.cas.pk
        assert row.student_college_at_submission_id == world.ccms.pk
        assert a[1] is True


def test_same_actor_key_concurrent_replay_commits_once(monkeypatch):
    world = make_world(monkeypatch)
    ticket = confirm(world)["confirmation"]
    a, b = ordered_race(lambda: submit(world, ticket), lambda: submit(world, ticket))
    assert a[0] == b[0] and a[1] is True and b[1] is False
    assert Referral.objects.count() == 1
    assert ReferralReferenceCounter.objects.get().next_value == 2


def test_gco_and_faculty_share_annual_counter_without_deadlock(monkeypatch):
    world = make_world(monkeypatch)
    ticket = confirm(world)["confirmation"]
    counselor = person("counselor", "COUNSELOR")
    other_student = person("other-student", "STUDENT")
    StudentAffiliation.objects.create(student=other_student, college=world.ccms)
    CounselorResponsibility.objects.create(counselor=counselor, college=world.ccms)
    barrier = Barrier(2)
    original = services._allocate_reference

    def allocate(*, at):
        barrier.wait(timeout=10)
        return original(at=at)

    monkeypatch.setattr(services, "_allocate_reference", allocate)
    monkeypatch.setattr(faculty_services, "_allocate_reference", allocate)

    def faculty():
        return submit(world, ticket)

    def gco():
        return services.create_referral(
            actor=counselor,
            student_id=other_student.pk,
            course_year_block="GCO course",
            reason="GCO reason",
            referrer_name="Paper referrer",
            referred_on=timezone.localdate(),
            received_at=None,
            idempotency_key="gco-parallel",
            request_fingerprint="f" * 64,
            context=AuditContext.user(counselor),
        )

    def isolated(fn):
        close_old_connections()
        try:
            return fn()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(isolated, faculty), pool.submit(isolated, gco)
        assert a.result(timeout=20)[1]
        assert b.result(timeout=20).submission_channel == "GCO_RECORDED"
    assert Referral.objects.count() == 2
    references = sorted(Referral.objects.values_list("reference_code", flat=True))
    assert references[0].endswith("000001") and references[1].endswith("000002")
    assert ReferralReferenceCounter.objects.get().next_value == 3
