"""GMSG-1: the kind catalog is closed and every kind it can hold has an explicit rule."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import Q

from compass.accounts.models import Capability, Role, User, UserCapabilityOverride
from compass.guidance_messages import policy
from compass.guidance_messages.errors import MessagesPermissionDenied, ThreadNotFound
from compass.guidance_messages.models import (
    ALL_THREAD_KINDS,
    GuidanceThread,
    ThreadKind,
)
from compass.organization.access_scope import resolve_general_guidance_college_scope
from tests.test_guidance_messages import counseling, office, world  # noqa: F401

# Imported world fixture is injected by pytest.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db

NEW_COLUMNS = (
    "requester",
    "direct_first_user",
    "direct_second_user",
    "student_subject",
    "relationship_referral",
    "relationship_case_grant",
)
# The parity oracles below model only the kinds creatable before GMSG-3. Referral coordination
# staff scope is current-placement based, so it has no legacy oracle; it is tested in
# tests/test_guidance_messages_referral.py.
PRE_GMSG3_KINDS = (ThreadKind.OFFICE, ThreadKind.COUNSELING, ThreadKind.FACULTY_INQUIRY)
UNCREATABLE_CODES = ("NOT_A_KIND",)
CONSTRAINTS = (
    "gm_thread_family_shape",
    "gm_direct_pair_ordered",
    "gm_one_thread_per_referral",
    "gm_direct_pair_unique",
    "gm_case_grant_subject_unique",
)


def unknown_kind_row(world, kind):
    """An unsaved row shaped to be maximally reachable: participant and College all present.

    Never written. The College value is deliberately in scope for the world's staff so that a denial
    can only come from the kind, not from the row being out of reach anyway.
    """
    return GuidanceThread(
        kind=kind,
        student_id=world.student.pk,
        counselor_id=world.counselor.pk,
        routing_college_id=world.colleges[0].pk,
    )


def faculty_actor():
    """A synthetic Faculty account: no password, because a profile ciphertext would fail a check."""
    email = "gm-kinds-faculty@example.edu"
    return User.objects.filter(email=email).first() or User.objects.create_user(
        email=email,
        password=None,
        role=Role.objects.get(code="FACULTY"),
        first_name="Synthetic",
        last_name="Faculty",
    )


def actors(world):
    """Every role the messaging surface knows, plus the three denied at the role gate."""
    faculty = faculty_actor()
    UserCapabilityOverride.objects.get_or_create(
        user=world.admin,
        capability=Capability.objects.get(code="guidance_messages.manage"),
        defaults={"effect": "GRANT", "reason": "Synthetic probe: grants do not widen a role"},
    )
    return [
        world.student,
        world.counselor,
        world.goa,
        world.head,
        world.admin,
        world.officer,
        faculty,
    ]


def legacy_authorized_pks(actor):
    """`policy.authorized_threads` verbatim as of 5557a3f8, kept as the parity oracle."""
    policy.require_actor(actor)
    if actor.role.code == "STUDENT":
        return set(
            GuidanceThread.objects.filter(
                kind__in=PRE_GMSG3_KINDS, student_id=actor.pk
            ).values_list("pk", flat=True)
        )
    scope = resolve_general_guidance_college_scope(actor)
    allowed = Q(kind=ThreadKind.OFFICE, routing_college_id__in=scope.college_ids)
    if actor.role.code == "COUNSELOR":
        allowed |= Q(kind=ThreadKind.COUNSELING, counselor_id=actor.pk)
    return set(GuidanceThread.objects.filter(allowed).values_list("pk", flat=True))


def legacy_require_thread(actor, thread, *, manage=False, staff_only=False):
    """`policy.require_thread` verbatim as of 5557a3f8, including its Office fallthrough."""
    if thread.kind not in PRE_GMSG3_KINDS:
        raise ThreadNotFound()
    try:
        policy.require_actor(actor, manage=manage, staff_only=staff_only)
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    if actor.role.code == "STUDENT":
        allowed = thread.student_id == actor.pk
    elif thread.kind == ThreadKind.COUNSELING:
        allowed = actor.role.code == "COUNSELOR" and thread.counselor_id == actor.pk
    else:
        allowed = (
            thread.routing_college_id in resolve_general_guidance_college_scope(actor).college_ids
        )
    if not allowed:
        raise ThreadNotFound()


def legacy_recipient_ids(thread):
    """`policy.recipient_ids` candidate query and re-check verbatim as of 5557a3f8."""
    candidates = Q(pk=thread.student_id)
    if thread.kind == ThreadKind.COUNSELING:
        candidates |= Q(pk=thread.counselor_id)
    else:
        candidates |= policy.office_staff_candidates(thread)
    recipients = set()
    for user in (
        User.objects.filter(candidates, is_active=True).select_related("role").distinct().iterator()
    ):
        try:
            legacy_require_thread(user, thread)
        except ThreadNotFound:
            continue
        recipients.add(user.pk)
    return recipients


def current_authorized_pks(actor):
    policy.require_actor(actor)
    return set(policy.authorized_threads(actor).values_list("pk", flat=True))


def result(function, *args, **kwargs):
    """A comparable value that distinguishes an allow from a deny without failing the test."""
    try:
        return ("allowed", function(*args, **kwargs))
    except MessagesPermissionDenied:
        return ("denied", "capability")
    except ThreadNotFound:
        return ("denied", "thread")


def test_kind_catalog_is_explicit_and_closed():
    assert ThreadKind.choices == [
        ("OFFICE", "Guidance Office"),
        ("COUNSELING", "Counseling"),
        ("FACULTY_INQUIRY", "Faculty inquiry"),
        ("REFERRAL_COORDINATION", "Referral coordination"),
        ("COUNSELOR_DIRECT", "Counselor direct"),
        ("COUNSELOR_CASE_COORDINATION", "Counselor case coordination"),
    ]
    assert ALL_THREAD_KINDS == frozenset(ThreadKind.values)
    assert len(ALL_THREAD_KINDS) == 6
    assert set(policy._RULES) == set(ALL_THREAD_KINDS)
    assert [kind for kind, rule in policy._RULES.items() if rule is not None] == [
        ThreadKind.OFFICE,
        ThreadKind.COUNSELING,
        ThreadKind.FACULTY_INQUIRY,
        ThreadKind.REFERRAL_COORDINATION,
        ThreadKind.COUNSELOR_DIRECT,
        ThreadKind.COUNSELOR_CASE_COORDINATION,
    ]


def test_legacy_shapes_still_insert_with_all_new_columns_null(world):
    office_thread, _ = office(world)
    counseling_thread, _ = counseling(world)
    office_thread.refresh_from_db()
    counseling_thread.refresh_from_db()

    assert office_thread.kind == "OFFICE"
    assert office_thread.student_id == world.student.pk
    assert office_thread.routing_college_id == world.colleges[0].pk
    assert office_thread.counselor_id is None
    assert office_thread.relationship_appointment_id is None
    assert counseling_thread.kind == "COUNSELING"
    assert counseling_thread.student_id == world.student.pk
    assert counseling_thread.counselor_id == world.counselor.pk
    assert counseling_thread.relationship_appointment_id == world.appointment.pk
    assert counseling_thread.routing_college_id is None
    for thread in (office_thread, counseling_thread):
        for name in NEW_COLUMNS:
            assert getattr(thread, name) is None, (thread.kind, name)
    assert GuidanceThread._meta.get_field("student").null is True
    assert all(GuidanceThread._meta.get_field(name).null for name in NEW_COLUMNS)

    for actor in (world.student, world.counselor, world.goa, world.head):
        assert result(current_authorized_pks, actor) == result(legacy_authorized_pks, actor), (
            actor.role.code
        )
        assert set(policy.recipient_ids(office_thread)) == legacy_recipient_ids(office_thread)
        assert set(policy.recipient_ids(counseling_thread)) == legacy_recipient_ids(
            counseling_thread
        )
        for thread in (office_thread, counseling_thread):
            for manage in (False, True):
                assert result(policy.require_thread, actor, thread, manage=manage) == result(
                    legacy_require_thread, actor, thread, manage=manage
                ), (actor.role.code, thread.kind, manage)
                assert result(
                    policy.require_thread, actor, thread, manage=manage, staff_only=True
                ) == result(legacy_require_thread, actor, thread, manage=manage, staff_only=True), (
                    actor.role.code,
                    thread.kind,
                    manage,
                )

    for actor in (world.admin, world.officer):
        for thread in (office_thread, counseling_thread):
            # The role gate is concealed: an outside role sees the same denial as a missing thread.
            assert (
                result(policy.require_thread, actor, thread)
                == result(legacy_require_thread, actor, thread)
                == ("denied", "thread")
            )
        assert result(current_authorized_pks, actor) == ("denied", "capability")
        assert result(legacy_authorized_pks, actor) == ("denied", "capability")


def test_inquiry_shape_inserts_with_a_requester_and_no_student(world):
    """GMSG-2 W3: the FACULTY_INQUIRY branch needs a requester and forbids the Student columns."""
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind=ThreadKind.FACULTY_INQUIRY,
            requester=faculty_actor(),
            student=world.student,
            created_by=world.counselor,
        )
    thread = GuidanceThread.objects.create(
        kind=ThreadKind.FACULTY_INQUIRY, requester=faculty_actor(), created_by=world.counselor
    )
    thread.refresh_from_db()
    assert thread.requester_id == faculty_actor().pk
    for name in (*NEW_COLUMNS[1:], "routing_college", "assigned_to"):
        assert getattr(thread, name) is None, name


def test_direct_shape_is_canonical_and_pair_unique(world):
    """GMSG-4 W8: the DB CHECK and partial unique index are independent pair guards."""
    first_id, second_id = sorted((world.counselor.pk, world.other.pk))
    thread = GuidanceThread.objects.create(
        kind=ThreadKind.COUNSELOR_DIRECT,
        direct_first_user_id=first_id,
        direct_second_user_id=second_id,
        created_by=world.counselor,
    )
    thread.refresh_from_db()
    assert (thread.direct_first_user_id, thread.direct_second_user_id) == (first_id, second_id)
    for name in (
        "student",
        "counselor",
        "requester",
        "student_subject",
        "relationship_referral",
        "relationship_case_grant",
        "relationship_appointment",
        "routing_college",
        "assigned_to",
    ):
        assert getattr(thread, name) is None, name

    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind=ThreadKind.COUNSELOR_DIRECT,
            direct_first_user_id=second_id,
            direct_second_user_id=first_id,
            created_by=world.counselor,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind=ThreadKind.COUNSELOR_DIRECT,
            direct_first_user_id=first_id,
            direct_second_user_id=second_id,
            created_by=world.other,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind=ThreadKind.COUNSELOR_DIRECT,
            direct_first_user_id=first_id,
            direct_second_user_id=second_id,
            student=world.student,
            created_by=world.counselor,
        )
    assert GuidanceThread.objects.filter(kind=ThreadKind.COUNSELOR_DIRECT).count() == 1


@pytest.mark.parametrize("code", UNCREATABLE_CODES)
def test_unknown_kinds_are_denied_for_every_role(world, code):
    thread = unknown_kind_row(world, code)
    for actor in actors(world):
        for manage in (False, True):
            assert result(policy.require_thread, actor, thread, manage=manage) == (
                "denied",
                "thread",
            )
        assert result(policy.require_thread, actor, thread, staff_only=True) == (
            "denied",
            "thread",
        )


@pytest.mark.parametrize("code", UNCREATABLE_CODES)
def test_unknown_kinds_have_no_recipients(world, code):
    assert policy.recipient_ids(unknown_kind_row(world, code)) == ()


@pytest.mark.parametrize("code", UNCREATABLE_CODES)
def test_kind_gate_precedes_the_resource_checks(world, code):
    office_thread, _ = office(world)
    relabeled = GuidanceThread.objects.get(pk=office_thread.pk)
    relabeled.kind = code  # in memory only; the stored row keeps kind OFFICE
    for actor in actors(world):
        assert result(policy.require_thread, actor, relabeled) == ("denied", "thread")
    assert policy.authorized_threads(world.student).filter(kind=code).count() == 0
    assert not GuidanceThread.objects.filter(kind=code).exists()


def test_new_constraints_are_installed_in_postgresql():
    """Constraint *presence*, not behavior: pair/referral/case routing is proven in GMSG-3..5."""
    table = "guidance_messages_guidancethread"
    with connection.cursor() as cursor:
        installed = set(connection.introspection.get_constraints(cursor, table))
        # Partial uniqueness is a unique *index* in PostgreSQL, so both catalogs are read.
        cursor.execute(
            "select conname, pg_get_constraintdef(oid) from pg_constraint"
            " where conrelid = %s::regclass"
            " union all select indexname, indexdef from pg_indexes where tablename = %s",
            [table, table],
        )
        definitions = dict(cursor.fetchall())
    for name in CONSTRAINTS:
        assert name in installed, name
        assert name in definitions, name
    shape = definitions["gm_thread_family_shape"]
    for name in NEW_COLUMNS:
        assert f"{name}_id" in shape, name
    assert "'OFFICE'" in shape and "'COUNSELING'" in shape
    assert "'COUNSELOR_CASE_COORDINATION'" in shape
    assert "direct_first_user_id" in definitions["gm_direct_pair_ordered"]
    assert "direct_second_user_id" in definitions["gm_direct_pair_ordered"]
    assert definitions["gm_one_thread_per_referral"].startswith("CREATE UNIQUE INDEX")
    assert "relationship_referral_id" in definitions["gm_one_thread_per_referral"]
    assert "'REFERRAL_COORDINATION'" in definitions["gm_one_thread_per_referral"]
    assert "direct_first_user_id" in definitions["gm_direct_pair_unique"]
    assert "'COUNSELOR_DIRECT'" in definitions["gm_direct_pair_unique"]
    assert "relationship_case_grant_id" in definitions["gm_case_grant_subject_unique"]
    assert "student_subject_id" in definitions["gm_case_grant_subject_unique"]
    assert "'COUNSELOR_CASE_COORDINATION'" in definitions["gm_case_grant_subject_unique"]

    inquiry_index = definitions["gm_inquiry_requester_idx"]
    assert "gm_inquiry_requester_idx" in installed
    assert inquiry_index.startswith("CREATE INDEX gm_inquiry_requester_idx")
    assert "(requester_id, last_message_at DESC, id DESC)" in inquiry_index
    assert "'FACULTY_INQUIRY'" in inquiry_index
    # PostgreSQL normalizes the decompiled CHECK without quoting, so the branch text is matched raw.
    inquiry_branch = next(part for part in shape.split(" OR ") if "'FACULTY_INQUIRY'" in part)
    for column in ("student_id", "routing_college_id", "assigned_to_id", "counselor_id"):
        assert f"{column} IS NULL" in inquiry_branch, column
    assert "requester_id IS NOT NULL" in inquiry_branch


CASE_VIEW = "guidance_messages.case_coordination.view"
CASE_MANAGE = "guidance_messages.case_coordination.manage"
CASE_KIND = ThreadKind.COUNSELOR_CASE_COORDINATION


def test_no_reserved_kind_placeholder_remains():
    import compass

    root = __import__("pathlib").Path(compass.__file__).resolve().parent
    references = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "ReservedThreadKind" in path.read_text()
    ]
    assert references == []


def test_case_kind_rule_is_counselor_only_grant_scoped():
    rule = policy._RULES[CASE_KIND]
    assert rule.staff_roles == frozenset({"COUNSELOR"})
    assert rule.student_participant is False
    assert rule.case_grant_participant is True
    assert rule.direct_pair_participant is False
    assert rule.office_staff_recipients is False
    assert rule.staff_capability == "guidance_messages.case_coordination"
    assert rule.staff_capability_action_suffix is True


def test_case_kind_allow_deny_matrix_across_every_role(world):
    for actor in actors(world):
        if actor.role.code == "COUNSELOR":
            assert policy.require_actor(actor, kind=CASE_KIND) is None
            assert policy.require_actor(actor, manage=True, kind=CASE_KIND) is None
        else:
            with pytest.raises(MessagesPermissionDenied):
                policy.require_actor(actor, kind=CASE_KIND)
            with pytest.raises(MessagesPermissionDenied):
                policy.require_actor(actor, manage=True, kind=CASE_KIND)


def test_case_kind_view_and_manage_are_separately_scoped(world):
    override = UserCapabilityOverride.objects.create(
        user=world.counselor,
        capability=Capability.objects.get(code=CASE_MANAGE),
        effect="REVOKE",
        reason="Synthetic case matrix",
    )
    try:
        policy.require_actor(world.counselor, kind=CASE_KIND)
        with pytest.raises(MessagesPermissionDenied):
            policy.require_actor(world.counselor, manage=True, kind=CASE_KIND)
    finally:
        override.delete()
    view = UserCapabilityOverride.objects.create(
        user=world.counselor,
        capability=Capability.objects.get(code=CASE_VIEW),
        effect="REVOKE",
        reason="Synthetic case matrix",
    )
    try:
        with pytest.raises(MessagesPermissionDenied):
            policy.require_actor(world.counselor, kind=CASE_KIND)
    finally:
        view.delete()
