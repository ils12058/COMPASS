"""Real independent PostgreSQL connections and observed lock waits, no sequential race mocks."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from compass.account_management.services import OrganizationRelationshipConflict, set_account_active
from compass.accounts.services import set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.models import AuthSession
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import create_my_current_student, update_request
from compass.inventory.services import (
    InvalidInventoryInput,
    InventoryConflict,
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization import catalog_services as cs
from compass.organization.integrity import catalog_gate
from compass.organization.models import (
    College,
    Program,
    StudentAffiliation,
)
from compass.organization.services import (
    set_counselor_responsibility,
    set_student_affiliation,
)
from tests.catalog_test_helpers import authority, hierarchy, manager, run_serialized_race, student
from tests.inventory_test_helpers import minimum_normalized_inventory_values
from tests.test_inventory import configure_year

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def setup():
    u, s = manager()
    return authority(u, s), hierarchy(), s


def inventory_fixture(auth, p, *, submit=False):
    s = student()
    configure_year(auth["actor"])
    StudentAffiliation.objects.create(student=s, college=p.college)
    context = AuditContext.user(s)
    ensure_current_inventory(student=s, context=context)
    replace_current_inventory(
        student=s, values=minimum_normalized_inventory_values(program_id=p.pk, year_level=1)
    )
    if submit:
        return s, submit_current_inventory(student=s, context=context)
    return s, None


def policy(auth, p, classification="BACHELORS", levels=None):
    return cs.update_program_policy(
        **auth,
        target_id=p.pk,
        expected_resource_version=1,
        academic_classification=classification,
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=levels or [2, 3, 4],
    )


def f4(s, key="race-f4"):
    return create_my_current_student(
        student=s,
        semester="First Semester",
        idempotency_key=key,
        request_fingerprint="f" * 64,
        context=AuditContext.user(s),
    )


@pytest.mark.parametrize("kind", ["campus", "college", "program", "normalized_campus"])
def test_duplicate_creates_have_one_identity_and_one_audit(setup, kind):
    auth, (c, k, p), _ = setup
    fn = {
        "campus": cs.create_campus,
        "normalized_campus": cs.create_campus,
        "college": cs.create_college,
        "program": cs.create_program,
    }[kind]
    args = dict(name="Race", is_active=True)
    if kind == "college":
        args["campus_id"] = c.pk
    if kind == "program":
        args.update(
            college_id=k.pk,
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 2, 3, 4],
        )
    a, b = run_serialized_race(
        lambda: fn(**auth, code="DUP", **args),
        lambda: fn(**auth, code=" dup " if kind == "normalized_campus" else "DUP", **args),
    )
    assert isinstance(b, cs.CatalogError) and b.code == "catalog_duplicate_code"
    assert type(a).objects.filter(code="DUP").count() == 1
    assert AuditEvent.objects.filter(target_id=str(a.pk), action__endswith=".created").count() == 1


@pytest.mark.parametrize("second_status", [False, True])
def test_two_renames_or_rename_versus_deactivation_reject_stale_writer(setup, second_status):
    auth, (_, _, p), _ = setup
    second = (
        (
            lambda: cs.set_program_active(
                **auth, target_id=p.pk, expected_resource_version=1, is_active=False
            )
        )
        if second_status
        else (
            lambda: cs.rename_program(
                **auth, target_id=p.pk, expected_resource_version=1, name="Loser"
            )
        )
    )
    _, error = run_serialized_race(
        lambda: cs.rename_program(
            **auth, target_id=p.pk, expected_resource_version=1, name="Winner"
        ),
        second,
    )
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_stale_version"
    p.refresh_from_db()
    assert p.name == "Winner" and p.is_active and p.resource_version == 2


@pytest.mark.parametrize(
    "kind", ["college_create", "program_create", "college_activate", "program_activate"]
)
def test_child_create_or_activation_commits_before_parent_retirement_blocker_recheck(setup, kind):
    auth, (c, k, p), _ = setup
    if kind.startswith("college"):
        Program.objects.filter(pk=p.pk).update(is_active=False)
        College.objects.filter(pk=k.pk).update(is_active=False)
        first = (
            (
                lambda: cs.create_college(
                    **auth, campus_id=c.pk, code="CHILD", name="Child", is_active=True
                )
            )
            if kind.endswith("create")
            else (
                lambda: cs.set_college_active(
                    **auth, target_id=k.pk, expected_resource_version=1, is_active=True
                )
            )
        )

        def second():
            return cs.set_campus_active(
                **auth, target_id=c.pk, expected_resource_version=1, is_active=False
            )
    else:
        Program.objects.filter(pk=p.pk).update(is_active=False)
        first = (
            (
                lambda: cs.create_program(
                    **auth,
                    college_id=k.pk,
                    code="CHILD",
                    name="Child",
                    is_active=True,
                    academic_classification="BACHELORS",
                    year_level_policy_status="CONFIGURED",
                    applicable_year_levels=[1],
                )
            )
            if kind.endswith("create")
            else (
                lambda: cs.set_program_active(
                    **auth, target_id=p.pk, expected_resource_version=1, is_active=True
                )
            )
        )

        def second():
            return cs.set_college_active(
                **auth, target_id=k.pk, expected_resource_version=1, is_active=False
            )

    _, error = run_serialized_race(first, second)
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_deactivation_blocked"
    c.refresh_from_db()
    k.refresh_from_db()
    assert c.is_active and (k.is_active if not kind.startswith("college") else True)


@pytest.mark.parametrize("relationship", ["student", "counselor"])
def test_relationship_assignment_vs_college_retirement(setup, relationship):
    auth, (_, k, p), _ = setup
    Program.objects.filter(pk=p.pk).update(is_active=False)
    target = student() if relationship == "student" else manager("COUNSELOR", grant=False)[0]
    first = (
        (
            lambda: set_student_affiliation(
                student_id=target.pk, college_id=k.pk, context=auth["context"]
            )
        )
        if relationship == "student"
        else (
            lambda: set_counselor_responsibility(
                counselor_id=target.pk, college_id=k.pk, context=auth["context"]
            )
        )
    )
    preview = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert preview.can_deactivate
    _, error = run_serialized_race(
        first,
        lambda: cs.set_college_active(
            **auth,
            target_id=k.pk,
            expected_resource_version=preview.resource_version,
            is_active=False,
        ),
    )
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_deactivation_blocked"


def test_account_reactivation_vs_college_retirement(setup):
    auth, (_, k, p), issued = setup
    Program.objects.filter(pk=p.pk).update(is_active=False)
    s = student()
    type(s).objects.filter(pk=s.pk).update(is_active=False)
    StudentAffiliation.objects.create(student=s, college=k)
    _, error = run_serialized_race(
        lambda: cs.set_college_active(
            **auth, target_id=k.pk, expected_resource_version=1, is_active=False
        ),
        lambda: set_account_active(
            actor=auth["actor"],
            actor_session=issued.session,
            target_id=s.pk,
            context=auth["context"],
            is_active=True,
        ),
    )
    assert isinstance(error, OrganizationRelationshipConflict)
    s.refresh_from_db()
    assert not s.is_active


def test_policy_change_vs_inventory_submission_revalidates_membership(setup):
    auth, (_, _, p), _ = setup
    s, _ = inventory_fixture(auth, p)
    _, error = run_serialized_race(
        lambda: policy(auth, p),
        lambda: submit_current_inventory(student=s, context=AuditContext.user(s)),
    )
    assert isinstance(error, (InventoryConflict, InvalidInventoryInput))
    from compass.inventory.models import StudentInventory

    assert StudentInventory.objects.get(student=s).submitted_at is None


def test_policy_change_vs_f4_creation_revalidates_classification(setup):
    auth, (_, _, p), _ = setup
    s, inv = inventory_fixture(auth, p, submit=True)
    _, error = run_serialized_race(lambda: policy(auth, p, "MASTERS", [1]), lambda: f4(s))
    from compass.good_moral.services import GoodMoralError

    assert isinstance(error, GoodMoralError)
    assert not GoodMoralRequest.objects.filter(student=s).exists()
    inv.refresh_from_db()
    assert inv.year_level == 1 and inv.course_currently_enrolled == "Program"


def test_f4_creation_first_blocks_later_policy_mutation(setup):
    auth, (_, _, p), _ = setup
    s, _ = inventory_fixture(auth, p, submit=True)
    _, error = run_serialized_race(lambda: f4(s), lambda: policy(auth, p, "MASTERS", [1]))
    assert (
        isinstance(error, cs.CatalogError)
        and error.code == "catalog_pending_f4_policy_decision_required"
    )
    p.refresh_from_db()
    assert p.academic_classification == "BACHELORS" and p.resource_version == 1


def test_program_retirement_vs_inventory_selection(setup):
    auth, (_, _, p), _ = setup
    s = student()
    configure_year(auth["actor"])
    ensure_current_inventory(student=s, context=AuditContext.user(s))
    _, error = run_serialized_race(
        lambda: cs.set_program_active(
            **auth, target_id=p.pk, expected_resource_version=1, is_active=False
        ),
        lambda: replace_current_inventory(student=s, values={"program_id": p.pk, "year_level": 1}),
    )
    assert isinstance(error, InventoryConflict)


def test_pending_f4_correction_vs_policy_update(setup):
    auth, (_, _, p), _ = setup
    s, _ = inventory_fixture(auth, p, submit=True)
    item = f4(s)
    GoodMoralRequest.objects.filter(pk=item.pk).update(year_level_snapshot="2nd Year")
    counselor = manager("COUNSELOR", grant=False)[0]
    _, error = run_serialized_race(
        lambda: update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"year_level_snapshot": "1st Year"},
            context=AuditContext.user(counselor),
        ),
        lambda: policy(auth, p),
    )
    assert (
        isinstance(error, cs.CatalogError)
        and error.code == "catalog_pending_f4_policy_decision_required"
    )
    item.refresh_from_db()
    assert item.year_level_snapshot == "1st Year"


def test_revoked_authority_during_wait_is_reloaded(setup):
    auth, (c, _, _), _ = setup
    _, error = run_serialized_race(
        lambda: set_user_capability_override(
            user=auth["actor"],
            capability="organization.catalog.manage",
            effect="REVOKE",
            reason="Synthetic revocation",
        ),
        lambda: cs.rename_campus(
            **auth, target_id=c.pk, expected_resource_version=1, name="Denied"
        ),
    )
    assert isinstance(error, cs.CatalogError) and error.status == 403
    c.refresh_from_db()
    assert c.resource_version == 1


def test_mfa_expired_while_mutation_waited(setup):
    auth, (c, _, _), issued = setup

    def expire():
        with catalog_gate():
            return AuthSession.objects.filter(pk=issued.session.pk).update(
                mfa_verified_at=timezone.now() - timedelta(days=1)
            )

    _, error = run_serialized_race(
        expire,
        lambda: cs.rename_campus(
            **auth, target_id=c.pk, expected_resource_version=1, name="Denied"
        ),
    )
    from compass.authentication.sessions import RecentMFARequired

    assert isinstance(error, RecentMFARequired)


@pytest.mark.parametrize("fault", ["audit", "after_version_increment"])
def test_failed_transaction_rolls_back_before_waiting_writer_commits(setup, monkeypatch, fault):
    auth, (_, _, p), _ = setup

    def first():
        with catalog_gate(exclusive=True):
            try:
                with transaction.atomic():
                    if fault == "audit":
                        with monkeypatch.context() as patch:

                            def fail(**kwargs):
                                raise RuntimeError("Synthetic Audit failure")

                            patch.setattr(cs, "record_event", fail)
                            cs.rename_program(
                                **auth,
                                target_id=p.pk,
                                expected_resource_version=1,
                                name="Rolled back",
                            )
                    else:
                        cs.rename_program(
                            **auth, target_id=p.pk, expected_resource_version=1, name="Rolled back"
                        )
                        raise RuntimeError("Synthetic rollback after version increment")
            except RuntimeError:
                pass

    _, updated = run_serialized_race(
        first,
        lambda: cs.rename_program(
            **auth, target_id=p.pk, expected_resource_version=1, name="Committed"
        ),
    )
    assert isinstance(updated, Program) and updated.resource_version == 2
    assert AuditEvent.objects.filter(target_id=str(p.pk), metadata__catalog_change=1).count() == 1


def test_lock_timeout_returns_typed_safe_catalog_conflict(setup):
    auth, (_, _, p), _ = setup

    def contender():
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout='200ms'")
            return cs.rename_program(
                **auth, target_id=p.pk, expected_resource_version=1, name="Timed out"
            )

    # Hold a real exclusive lock in another connection until the contender timeout, not a mock.
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    def run():
        close_old_connections()
        try:
            try:
                return contender()
            except cs.CatalogError as exc:
                return exc
        finally:
            connection.close()

    with catalog_gate(exclusive=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            error = pool.submit(run).result(timeout=10)
    assert error.code == "catalog_busy"
    p.refresh_from_db()
    assert p.resource_version == 1 and p.name == "Program"


@pytest.mark.parametrize("entity", ["college", "program"])
def test_parent_retirement_first_prevents_concurrent_active_child_creation(setup, entity):
    auth, (c, k, p), _ = setup
    Program.objects.filter(pk=p.pk).update(is_active=False)
    if entity == "college":
        College.objects.filter(pk=k.pk).update(is_active=False)

        def first():
            return cs.set_campus_active(
                **auth, target_id=c.pk, expected_resource_version=1, is_active=False
            )

        def second():
            return cs.create_college(**auth, campus_id=c.pk, code="NEW", name="New", is_active=True)
    else:

        def first():
            return cs.set_college_active(
                **auth, target_id=k.pk, expected_resource_version=1, is_active=False
            )

        def second():
            return cs.create_program(
                **auth,
                college_id=k.pk,
                code="NEW",
                name="New",
                is_active=True,
                academic_classification="BACHELORS",
                year_level_policy_status="CONFIGURED",
                applicable_year_levels=[1],
            )

    _, error = run_serialized_race(first, second)
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_inactive_parent"


def test_actual_postgresql_deadlock_is_translated_and_audit_rolls_back(setup, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from django.db import OperationalError, close_old_connections

    from compass.organization.integrity import CATALOG_INTEGRITY_LOCK

    auth, (_, _, p), _ = setup
    reached = Event()
    external_lock = 477580715099
    original = cs.record_event

    def stalled_audit(**kwargs):
        reached.set()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [external_lock])
        return original(**kwargs)

    monkeypatch.setattr(cs, "record_event", stalled_audit)

    def catalog_writer():
        close_old_connections()
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL deadlock_timeout='100ms'")
                try:
                    return cs.rename_program(
                        **auth, target_id=p.pk, expected_resource_version=1, name="Deadlock victim"
                    )
                except cs.CatalogError as exc:
                    return exc
        finally:
            connection.close()

    # Deliberate TEST-ONLY inversion injects a PostgreSQL failure. Production writers never
    # acquire this external key. Catalog detects first (100 ms versus external 5 s).
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL deadlock_timeout='5s'")
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [external_lock])
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(catalog_writer)
            assert reached.wait(10)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CATALOG_INTEGRITY_LOCK])
            except OperationalError:
                pytest.fail("Test external process unexpectedly selected as victim")
            error = result.result(timeout=10)
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_busy"
    p.refresh_from_db()
    assert p.resource_version == 1 and p.name == "Program"
    assert not AuditEvent.objects.filter(target_id=str(p.pk), metadata__catalog_change=1).exists()
