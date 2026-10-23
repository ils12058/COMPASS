"""Real PostgreSQL row/table/advisory locks; no mocked locking proof."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, current_thread

import pytest
from django.db import OperationalError, close_old_connections, connection, connections, transaction
from django.utils import timezone

from compass.account_management.services import (
    change_role,
    remove_designation,
    set_account_active,
    set_capability_override,
    set_student_lifecycle,
)
from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.counseling import continuity_access as access
from compass.counseling.continuity_locks import AUTHORITY_TABLES, continuity_policy_change
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.models import CounselingEncounter
from compass.organization.models import Campus, College, StudentAffiliation
from compass.organization.services import set_student_affiliation
from compass.routine_interviews import content
from compass.routine_interviews.models import RoutineInterview
from tests import test_continuity_access as selected_tests
from tests.test_continuity import decide
from tests.test_continuity_access import SENTINEL, approved, read, reads

metadata_case = selected_tests.metadata_case
selected_case = selected_tests.selected_case

pytestmark = pytest.mark.django_db(transaction=True)


def run(op, application_name=None):
    close_old_connections()
    try:
        assert connection.vendor == "postgresql"
        if application_name:
            with connection.cursor() as cursor:
                cursor.execute("SET application_name=%s", [application_name])
        return ("ok", op())
    except ContinuityError as exc:
        return ("denied", exc.status, exc.code)
    except RuntimeError as exc:
        return ("failure", str(exc))
    finally:
        connections.close_all()


def gated_decryption(monkeypatch):
    entered, release = Event(), Event()
    original = content.read_evaluation

    def decrypt(item):
        result = original(item)
        entered.set()
        assert release.wait(timeout=5)
        return result

    monkeypatch.setattr(content, "read_evaluation", decrypt)
    return entered, release


def wait_for_pg_lock(application_name):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute(
                "SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",
                [application_name],
            )
            rows = cursor.fetchall()
        if any(row[0] == "Lock" for row in rows):
            return
        time.sleep(0.01)
    pytest.fail("Expected an actual PostgreSQL lock wait")


@pytest.mark.parametrize(
    "mutation",
    [
        "grant_revoke",
        "capability_revoke",
        "deactivate",
        "role",
        "student_lifecycle",
        "affiliation",
        "head_designation",
        "source_revision",
    ],
)
def test_read_linearizes_before_real_supported_mutation(selected_case, monkeypatch, mutation):
    c = selected_case
    g = approved(c)
    manager = c.user("manager", "IT_ADMIN")
    # Existing governance capability needed for formal Head assignment/removal.
    from compass.accounts.services import set_user_capability_override

    set_user_capability_override(
        user=manager,
        capability="institutional_designations.manage",
        effect="GRANT",
        reason="Synthetic institutional manager",
    )
    now = timezone.now()
    session = create_auth_session(manager, now=now, mfa_verified_at=now).session
    context = AuditContext.user(manager)
    entered, release = gated_decryption(monkeypatch)

    def mutate():
        options = dict(actor=manager, actor_session=session, context=context)
        if mutation == "grant_revoke":
            return decide(c, g, "REVOKED", revocation_reason="COVERAGE_ENDED")
        if mutation == "capability_revoke":
            return set_capability_override(
                **options,
                target_id=c.receiver.pk,
                capability="counseling.continuity.read_selected",
                effect="REVOKE",
                reason="Synthetic revoke",
            )
        if mutation == "deactivate":
            return set_account_active(**options, target_id=c.receiver.pk, is_active=False)
        if mutation == "role":
            return change_role(**options, target_id=c.receiver.pk, role="GUIDANCE_SERVICES_STAFF")
        if mutation == "student_lifecycle":
            return set_student_lifecycle(**options, target_id=c.student.pk, status="FORMER")
        if mutation == "affiliation":
            return set_student_affiliation(
                student_id=c.student.pk, college_id=c.college_b.pk, context=context
            )
        if mutation == "head_designation":
            return remove_designation(
                **options, target_id=c.head.pk, designation="HEAD_GUIDANCE_COUNSELOR"
            )
        with transaction.atomic():
            item = RoutineInterview.objects.select_for_update().get(pk=c.routine.pk)
            item.updated_at = timezone.now()
            item.save(update_fields=["updated_at"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(run, lambda: read(c, g))
        assert entered.wait(timeout=5)
        writer = pool.submit(run, mutate, "cont2b_supported_writer")
        try:
            wait_for_pg_lock("cont2b_supported_writer")
            assert not writer.done()
        finally:
            release.set()
        result = reader.result(timeout=10)
        change = writer.result(timeout=10)
    assert result[0] == "ok" and result[1]["evaluation"]["recommendations"] == SENTINEL
    assert change[0] == "ok", change
    assert reads().count() == 1
    with pytest.raises(ContinuityError):
        read(c, g)
    assert reads().count() == 1


def authority_mutation(c, table):
    if table == "accounts_role":
        return lambda: Role.objects.filter(pk=c.receiver.role_id).update(name="SYNTHETIC CHANGED")
    if table == "accounts_capability":
        return lambda: Capability.objects.filter(code="counseling.continuity.read_selected").update(
            name="SYNTHETIC CHANGED"
        )
    if table == "accounts_designation":
        return lambda: Designation.objects.filter(code="HEAD_GUIDANCE_COUNSELOR").update(
            name="SYNTHETIC CHANGED"
        )
    if table == "accounts_rolecapability":
        return lambda: RoleCapability.objects.filter(
            role=c.receiver.role, capability__code="routine_interviews.view_assigned"
        ).delete()
    if table == "accounts_designationcapability":
        return lambda: DesignationCapability.objects.filter(
            designation__code="HEAD_GUIDANCE_COUNSELOR"
        ).delete()
    if table == "accounts_userdesignation":
        return lambda: UserDesignation.objects.filter(user=c.head).delete()
    if table == "accounts_usercapabilityoverride":
        return lambda: UserCapabilityOverride.objects.filter(
            user=c.receiver, capability__code="counseling.continuity.read_selected"
        ).update(effect="REVOKE")
    if table == "organization_studentaffiliation":
        return lambda: StudentAffiliation.objects.filter(student=c.student).update(
            college=c.college_b, updated_at=timezone.now()
        )
    if table == "organization_college":
        return lambda: College.objects.filter(pk=c.college.pk).update(is_active=False)
    if table == "organization_campus":
        return lambda: Campus.objects.filter(pk=c.campus.pk).update(is_active=False)
    raise AssertionError(table)


@pytest.mark.parametrize("table", AUTHORITY_TABLES)
def test_every_authority_relation_is_fenced_against_ordinary_dml(selected_case, monkeypatch, table):
    c = selected_case
    g = approved(c)
    entered, release = gated_decryption(monkeypatch)
    mutate = authority_mutation(c, table)
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(run, lambda: read(c, g))
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(OperationalError) as exc, transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout='100ms'")
                mutate()
            assert getattr(exc.value.__cause__, "sqlstate", None) == "55P03"
        finally:
            release.set()
        assert reader.result(timeout=10)[0] == "ok"
    mutate()  # The same DML is possible after read commit; this is synchronization, not ownership.
    assert reads().count() == 1


@pytest.mark.parametrize(
    "table",
    [
        "accounts_usercapabilityoverride",
        "accounts_userdesignation",
        "organization_college",
        "organization_campus",
    ],
)
def test_authority_writer_first_denies_before_decryption(selected_case, monkeypatch, table):
    c = selected_case
    g = approved(c)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    mutate = authority_mutation(c, table)
    with transaction.atomic():
        mutate()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(run, lambda: read(c, g)).result(timeout=5)
        assert result == ("denied", 409, "continuity_authority_busy")
    assert reads().count() == 0
    with pytest.raises(ContinuityError):
        read(c, g)


@pytest.mark.parametrize("policy_kind", ["operational", "disclosure"])
def test_policy_invalidation_is_coordinated_by_postgresql_fence(
    selected_case, monkeypatch, policy_kind
):
    c = selected_case
    g = approved(c)
    entered, release = gated_decryption(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(run, lambda: read(c, g))
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(ContinuityError, match="policy_busy"), continuity_policy_change():
                setattr(c.control, policy_kind, None)
        finally:
            release.set()
        assert reader.result(timeout=10)[0] == "ok"
    assert getattr(c.control, policy_kind) is not None
    with continuity_policy_change():
        setattr(c.control, policy_kind, None)
    with pytest.raises(ContinuityError, match="policy_unconfirmed"):
        read(c, g)
    assert reads().count() == 1


def test_policy_invalidation_first_prevents_read(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with continuity_policy_change():
        c.control.disclosure = None
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(run, lambda: read(c, g)).result(timeout=5)
        assert result == ("denied", 409, "continuity_policy_busy")
    with pytest.raises(ContinuityError, match="disclosure_policy_unconfirmed"):
        read(c, g)
    assert reads().count() == 0


def test_read_waiting_on_user_rechecks_exact_expiry(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    clock = SimpleClock(timezone.now())
    monkeypatch.setattr(access.timezone, "now", lambda: clock.now)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update().get(pk=c.receiver.pk)
            future = pool.submit(run, lambda: read(c, g), "cont2b_expiry_reader")
            wait_for_pg_lock("cont2b_expiry_reader")
            clock.now = g["expires_at"]
        assert future.result(timeout=5) == ("denied", 404, "continuity_not_found")
    assert reads().count() == 0


class SimpleClock:
    def __init__(self, now):
        self.now = now


@pytest.mark.parametrize("source_kind", ["ROUTINE", "ENCOUNTER"])
def test_nowait_source_conflict_prevents_reversed_lock_deadlock(
    selected_case, monkeypatch, source_kind
):
    c = selected_case
    g = approved(c)
    source_locked, users_locked, attempted_user = Event(), Event(), Event()
    model, pk = (
        (RoutineInterview, c.routine.pk)
        if source_kind == "ROUTINE"
        else (CounselingEncounter, c.encounter.pk)
    )
    original = access.grants._users

    def users(*ids):
        result = original(*ids)
        users_locked.set()
        assert attempted_user.wait(timeout=5)
        return result

    monkeypatch.setattr(access.grants, "_users", users)

    def source_writer():
        with transaction.atomic():
            model.objects.select_for_update().get(pk=pk)
            source_locked.set()
            assert users_locked.wait(timeout=5)
            attempted_user.set()
            User.objects.select_for_update().get(pk=c.receiver.pk)
            model.objects.filter(pk=pk).update(updated_at=timezone.now())

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(run, source_writer)
        assert source_locked.wait(timeout=5)
        reader = pool.submit(run, lambda: read(c, g))
        assert reader.result(timeout=5) == ("denied", 409, "continuity_source_busy")
        assert writer.result(timeout=5)[0] == "ok"
    assert reads().count() == 0


def test_concurrent_selected_reads_each_audit_once(selected_case):
    c = selected_case
    g = approved(c)
    barrier = Barrier(2)

    def operation():
        barrier.wait(timeout=5)
        return read(c, g)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, operation) for _ in range(2)]
        results = [f.result(timeout=10) for f in futures]
    assert all(r[0] == "ok" for r in results), results
    assert reads().count() == 2


def test_concurrent_audit_failure_cannot_release_first_body(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    barrier = Barrier(2)
    original = access.record_event

    def audit(**kwargs):
        if current_thread().name.startswith("cont2b-fail"):
            raise RuntimeError("Synthetic audit failure")
        return original(**kwargs)

    monkeypatch.setattr(access, "record_event", audit)

    def operation():
        barrier.wait(timeout=5)
        return read(c, g)

    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="cont2b-fail") as failing,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="cont2b-ok") as good,
    ):
        futures = [failing.submit(run, operation), good.submit(run, operation)]
        results = [f.result(timeout=10) for f in futures]
    assert results[0] == ("failure", "Synthetic audit failure")
    assert results[1][0] == "ok"
    assert reads().count() == 1


def test_missing_override_row_is_protected_against_revoke_phantom(selected_case, monkeypatch):
    c = selected_case
    g = approved(c)
    capability = Capability.objects.get(code="routine_interviews.view_assigned")
    assert not UserCapabilityOverride.objects.filter(
        user=c.receiver, capability=capability
    ).exists()
    entered, release = gated_decryption(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run, lambda: read(c, g))
        assert entered.wait(timeout=5)
        try:
            with pytest.raises(OperationalError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout='100ms'")
                UserCapabilityOverride.objects.create(
                    user=c.receiver,
                    capability=capability,
                    effect="REVOKE",
                    reason="Synthetic phantom revoke",
                )
        finally:
            release.set()
        assert future.result(timeout=10)[0] == "ok"
    UserCapabilityOverride.objects.create(
        user=c.receiver, capability=capability, effect="REVOKE", reason="Synthetic phantom revoke"
    )
    with pytest.raises(ContinuityError, match="missing_capability"):
        read(c, g)
    assert reads().count() == 1


def test_unrelated_guessed_grant_does_not_leak_row_contention(selected_case, monkeypatch):
    from uuid import uuid4

    from compass.counseling.continuity_models import CounselorCaseContinuityGrant

    c = selected_case
    g = approved(c)
    monkeypatch.setattr(content, "read_evaluation", lambda *a, **k: pytest.fail("decrypt"))
    with transaction.atomic():
        CounselorCaseContinuityGrant.objects.select_for_update().get(pk=g["id"])
        with ThreadPoolExecutor(max_workers=1) as pool:
            for grant_id in [g["id"], uuid4()]:
                result = pool.submit(
                    run, lambda value=grant_id: read(c, g, actor=c.outsider, grant_id=value)
                ).result(timeout=5)
                assert result == ("denied", 404, "continuity_not_found")
    assert reads().count() == 0
