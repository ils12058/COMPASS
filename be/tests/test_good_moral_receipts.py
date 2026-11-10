"""Synthetic receipt ledger, database guards and PostgreSQL race evidence."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier, Event
from uuid import uuid4

import pytest
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    connection,
    transaction,
)

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.good_moral import receipt_identity as receipts
from compass.good_moral.models import (
    GoodMoralReceiptAssignment as Assignment,
)
from compass.good_moral.models import (
    GoodMoralReceiptIdentity as Identity,
)
from compass.good_moral.models import (
    GoodMoralReceiptMutation as Mutation,
)
from compass.good_moral.models import (
    GoodMoralRequest,
)
from compass.good_moral.services import (
    GoodMoralConflict,
    GoodMoralNotPermitted,
    InvalidGoodMoralInput,
    cancel_request,
    issue_request,
    prepare_request,
    update_request,
)
from compass.organization.models import AcademicYear
from tests.test_good_moral import (
    create_my_current_student,
    make_current_request,
    make_inventory,
    make_placement,
    sync_policy,
)


def person(name, role="STUDENT"):
    return User.objects.create_user(
        email=f"{name}-{uuid4()}@example.test",
        password=None,
        role=Role.objects.get(code=role),
        first_name=name,
        last_name="Synthetic",
    )


def request_for(student=None, variant="GRADUATE", **facts):
    student = student or person("applicant")
    actor = person("receipt-recorder", "COUNSELOR") if facts else None
    if variant == "CURRENT_STUDENT":
        year = AcademicYear.objects.filter(is_current=True).first()
        if year:
            make_placement(student)
            make_inventory(student, year)
            item = create_my_current_student(
                student=student, semester="First Semester", context=AuditContext.user(student)
            )
        else:
            item = make_current_request(student)[0]
        if facts:
            item = edit(item, actor, facts)
        return item
    item = GoodMoralRequest.objects.create(
        student=student,
        initiation_origin="STUDENT_SELF",
        initiated_by=student,
        variant="GRADUATE",
        applicant_name_snapshot="Synthetic Applicant",
        degree_snapshot="Bachelor of Science",
        graduation_date=date(2020, 1, 1),
    )
    return edit(item, actor, facts) if facts else item


def edit(item, actor, changes, **overrides):
    item.refresh_from_db()
    args = dict(
        actor=actor,
        request_id=item.pk,
        changes=changes,
        context=AuditContext.user(actor),
        expected_resource_version=item.updated_at.isoformat(),
        expected_receipt_revision=getattr(receipts.latest_revision(item), "pk", None),
        operation_id=uuid4(),
    )
    args.update(overrides)
    return update_request(**args)


@pytest.fixture
def world():
    sync_policy()
    actor = person("preparer", "COUNSELOR")
    item = request_for()
    return actor, item


@pytest.mark.parametrize(
    ("value", "display", "key"),
    [
        ("  or-00042  ", "or-00042", "OR-00042"),
        ("OR00042", "OR00042", "OR00042"),
        ("OR-42", "OR-42", "OR-42"),
        ("OR  00042", "OR  00042", "OR  00042"),
        ("pre/00042.A", "pre/00042.A", "PRE/00042.A"),
        ("a" * 96, "a" * 96, "A" * 96),
    ],
)
def test_normalization_preserves_printed_distinctions(value, display, key):
    assert receipts.normalize_number(value) == (display, key)
    assert receipts.NORMALIZATION_VERSION == "GM_OR_V1"


@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        True,
        "",
        "   ",
        "a" * 97,
        "\tOR",
        "OR\n",
        "OR\x00",
        "OR\x7f",
        "ＯＲ-42",
        "OR–42",
        "OR\u200b42",
        "OR\u202e42",
    ],
)
def test_normalization_rejects_unsupported_input(value):
    with pytest.raises(InvalidGoodMoralInput):
        receipts.normalize_number(value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("first_variant", "second_variant", "same_student"),
    [
        ("GRADUATE", "GRADUATE", False),
        ("CURRENT_STUDENT", "CURRENT_STUDENT", False),
        ("CURRENT_STUDENT", "GRADUATE", False),
        ("GRADUATE", "GRADUATE", True),
    ],
)
def test_shared_namespace_and_safe_duplicate(world, first_variant, second_variant, same_student):
    actor, _ = world
    first = request_for(variant=first_variant)
    second = request_for(first.student if same_student else None, second_variant)
    edit(first, actor, {"official_receipt_number": "  or-00042  "})
    with pytest.raises(receipts.ReceiptConflict) as caught:
        edit(second, actor, {"official_receipt_number": "OR-00042"})
    assert str(first.pk) not in str(caught.value) and str(first.student_id) not in str(caught.value)
    assert Identity.objects.count() == 1
    assert Assignment.objects.filter(origin="ORDINARY").count() == 1


@pytest.mark.django_db
def test_revisions_clearing_replacement_and_cancellation_never_release(world):
    actor, item = world
    other = request_for()
    edit(item, actor, {"official_receipt_number": "OR-1"})
    original = receipts.latest_revision(item)
    edit(item, actor, {"official_receipt_date": date(2020, 1, 1)})
    edit(item, actor, {"official_receipt_amount": Decimal("250")})
    assert Identity.objects.count() == 1  # No fee enforcement in this slice.
    edit(item, actor, {"official_receipt_number": "OR-2"})
    with pytest.raises(receipts.ReceiptConflict):
        edit(item, actor, {"official_receipt_number": "OR-1"})
    edit(
        item,
        actor,
        {
            "official_receipt_number": "",
            "official_receipt_date": None,
            "official_receipt_amount": None,
        },
    )
    assert not Assignment.objects.filter(request=item, is_current=True).exists()
    for value in ("OR-1", "OR-2"):
        with pytest.raises(receipts.ReceiptConflict):
            edit(other, actor, {"official_receipt_number": value})
    edit(item, actor, {"official_receipt_number": "OR-3"})
    cancel_request(
        actor=actor,
        request_id=item.pk,
        reason="Synthetic cancellation",
        self_service=False,
        context=AuditContext.user(actor),
    )
    with pytest.raises(receipts.ReceiptConflict):
        edit(other, actor, {"official_receipt_number": "OR-3"})
    with pytest.raises(GoodMoralConflict):
        edit(item, actor, {"official_receipt_number": "OR-4"})
    original.refresh_from_db()
    assert original.display_number == "OR-1" and original.closed_by_id == actor.pk
    rows = list(Assignment.objects.filter(request=item))
    assert [x.sequence for x in rows] == list(range(1, len(rows) + 1))
    assert [x.previous_id for x in rows[1:]] == [x.pk for x in rows[:-1]]


@pytest.mark.django_db
def test_exact_replay_and_noop_are_durable_and_stale_state_is_rejected(world):
    actor, item = world
    expected = item.updated_at.isoformat()
    previous = getattr(receipts.latest_revision(item), "pk", None)
    operation = uuid4()
    args = dict(
        expected_resource_version=expected,
        expected_receipt_revision=previous,
        operation_id=operation,
    )
    result = edit(item, actor, {"official_receipt_number": "OR-1"}, **args)
    revision = result.receipt_mutation_result.result_revision_id
    events = AuditEvent.objects.count()
    replay = edit(item, actor, {"official_receipt_number": "OR-1"}, **args)
    assert replay.receipt_mutation_result.result_revision_id == revision
    assert AuditEvent.objects.count() == events
    with pytest.raises(receipts.ReceiptOperationConflict):
        edit(item, actor, {"official_receipt_number": "OR-2"}, **args)
    with pytest.raises(receipts.ReceiptChanged):
        edit(item, actor, {"official_receipt_number": "OR-2"}, expected_resource_version=expected)
    with pytest.raises(receipts.ReceiptChanged):
        edit(item, actor, {"official_receipt_number": "OR-2"}, expected_receipt_revision=previous)
    count = Assignment.objects.count()
    edit(item, actor, {"official_receipt_number": "OR-1"})
    assert Assignment.objects.count() == count and Mutation.objects.count() == 2
    with pytest.raises(InvalidGoodMoralInput):
        update_request(
            actor=actor,
            request_id=item.pk,
            changes={"official_receipt_amount": 0},
            context=AuditContext.user(actor),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"])
def test_no_new_role_authority(world, role):
    _, item = world
    actor = person("denied", role)
    with pytest.raises(GoodMoralNotPermitted):
        edit(item, actor, {"official_receipt_number": "PRIVATE"})
    assert not Identity.objects.exists()


@pytest.mark.django_db
def test_actor_context_and_inactive_actor_are_not_fabricated(world):
    actor, item = world
    with pytest.raises(GoodMoralNotPermitted):
        edit(item, actor, {"official_receipt_number": "OR-1"}, context=AuditContext.system())
    User.objects.filter(pk=actor.pk).update(is_active=False)
    with pytest.raises(GoodMoralNotPermitted):
        edit(item, actor, {"official_receipt_number": "OR-1"})


@pytest.mark.django_db
def test_audit_failure_rolls_back_all_receipt_facts(world, monkeypatch):
    actor, item = world
    before = Assignment.objects.count()

    def fail(**kwargs):
        raise RuntimeError("Synthetic audit outage")

    monkeypatch.setattr(receipts, "record_event", fail)
    with pytest.raises(RuntimeError):
        edit(item, actor, {"official_receipt_number": "OR-1"})
    item.refresh_from_db()
    assert item.official_receipt_number == "" and not Identity.objects.exists()
    assert Assignment.objects.count() == before and not Mutation.objects.exists()


@pytest.mark.django_db
def test_other_integrity_errors_are_not_hidden_as_identity_conflicts(world, monkeypatch):
    actor, item = world

    def fail(**kwargs):
        raise IntegrityError("Synthetic unrelated constraint")

    monkeypatch.setattr(receipts, "finish_edit", fail)
    with pytest.raises(IntegrityError, match="unrelated"):
        edit(item, actor, {"official_receipt_number": "OR-1"})
    assert not Identity.objects.exists()
    assert not Assignment.objects.filter(origin="ORDINARY").exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "illegal",
    [
        "rekey",
        "identity_delete",
        "fact_update",
        "claim_delete",
        "reactivate",
        "projection",
        "operation_update",
        "closure_without_successor",
    ],
)
def test_database_guards_reject_alternative_writers(world, illegal):
    actor, item = world
    edit(item, actor, {"official_receipt_number": "OR-1"})
    first = receipts.latest_revision(item)
    if illegal == "reactivate":
        edit(item, actor, {"official_receipt_number": "OR-2"})
    with pytest.raises(IntegrityError), transaction.atomic():
        if illegal == "rekey":
            Identity.objects.filter(pk=first.identity_id).update(normalized_key="OR-OTHER")
        elif illegal == "identity_delete":
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM good_moral_goodmoralreceiptidentity WHERE id=%s",
                    [first.identity_id],
                )
        elif illegal == "fact_update":
            Assignment.objects.filter(pk=first.pk).update(amount=Decimal("9"))
        elif illegal == "claim_delete":
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM good_moral_goodmoralreceiptassignment WHERE id=%s", [first.pk]
                )
        elif illegal == "reactivate":
            Assignment.objects.filter(pk=first.pk).update(is_current=True)
        elif illegal == "projection":
            GoodMoralRequest.objects.filter(pk=item.pk).update(official_receipt_number="UNRESERVED")
        elif illegal == "operation_update":
            Mutation.objects.update(fingerprint="a" * 64)
        else:
            Assignment.objects.filter(pk=first.pk).update(
                is_current=False,
                closed_at=first.recorded_at + timedelta(seconds=1),
                closed_by=actor,
                closure_reason="REVISION",
            )
    item.refresh_from_db()
    assert item.official_receipt_number in {"OR-1", "OR-2"}
    assert Identity.objects.filter(pk=first.identity_id).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "illegal",
    [
        "owner",
        "predecessor",
        "sequence",
        "null_current",
        "two_current",
        "noncanonical",
        "null_owner",
    ],
)
def test_database_claim_and_identity_shapes(world, illegal):
    actor, item = world
    other = request_for()
    edit(item, actor, {"official_receipt_number": "OR-1"})
    old = receipts.latest_revision(item)
    kwargs = dict(
        request=other,
        identity_id=old.identity_id,
        display_number="OR-1",
        sequence=2,
        previous=receipts.latest_revision(other),
        recorded_by=actor,
        origin="ORDINARY",
        is_current=True,
        change_kind="ASSIGNED",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        if illegal == "noncanonical":
            Identity.objects.create(
                normalized_key="lower",
                bound_request=item,
                state="BOUND",
                origin="ORDINARY",
                recorded_by=actor,
            )
        elif illegal == "null_owner":
            Identity.objects.create(
                normalized_key="OR-2", state="BOUND", origin="ORDINARY", recorded_by=actor
            )
        else:
            if illegal == "predecessor":
                kwargs["previous"] = old
            if illegal == "sequence":
                kwargs["sequence"] = 3
            if illegal == "null_current":
                kwargs["identity_id"] = None
            if illegal == "two_current":
                kwargs.update(request=item, previous=old, sequence=old.sequence + 1)
            Assignment.objects.create(**kwargs)
    assert Assignment.objects.filter(origin="ORDINARY").count() == 1


def worker(callback):
    close_old_connections()
    try:
        return callback()
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("cross_variant", [False, True])
def test_real_postgresql_same_absent_key_has_exactly_one_winner(world, cross_variant, monkeypatch):
    actor, first = world
    second = request_for(variant="CURRENT_STUDENT" if cross_variant else "GRADUATE")
    initial = Assignment.objects.count()
    barrier = Barrier(2)
    create = Identity.objects.create

    def simultaneous_insert(**kwargs):
        if kwargs.get("normalized_key") == "OR-RACE":
            barrier.wait(timeout=10)
        return create(**kwargs)

    monkeypatch.setattr(Identity.objects, "create", simultaneous_insert)

    def attempt(item):
        try:
            return edit(item, actor, {"official_receipt_number": "OR-RACE"}).pk
        except receipts.ReceiptConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, lambda item=item: attempt(item)) for item in (first, second)]
        outcomes = [f.result(timeout=20) for f in futures]
    assert outcomes.count("conflict") == 1
    reservation = Identity.objects.get(normalized_key="OR-RACE")
    assert reservation.bound_request_id in outcomes
    assert Assignment.objects.count() == initial + 1 and Mutation.objects.count() == 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_assigned").count() == 1
    assert Assignment.objects.filter(identity=reservation, is_current=True).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_operation", [False, True])
def test_real_postgresql_same_request_edits_and_replays_serialize(world, same_operation):
    actor, item = world
    version, revision = (
        item.updated_at.isoformat(),
        getattr(receipts.latest_revision(item), "pk", None),
    )
    start = Barrier(2)
    shared_id = uuid4()

    def attempt(index):
        start.wait(timeout=10)
        try:
            result = edit(
                item,
                actor,
                {"official_receipt_number": "OR-SAME" if same_operation else f"OR-{index}"},
                expected_resource_version=version,
                expected_receipt_revision=revision,
                operation_id=shared_id if same_operation else uuid4(),
            )
            return str(result.receipt_mutation_result.result_revision_id)
        except receipts.ReceiptChanged:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            f.result(timeout=20)
            for f in [pool.submit(worker, lambda i=i: attempt(i)) for i in (1, 2)]
        ]
    assert (outcomes[0] == outcomes[1]) if same_operation else outcomes.count("stale") == 1
    assert Identity.objects.count() == 1 and Mutation.objects.count() == 1
    assert Assignment.objects.filter(origin="ORDINARY").count() == 1


@pytest.mark.django_db(transaction=True)
def test_simultaneous_replacement_reserves_only_winning_new_number(world):
    actor, item = world
    edit(item, actor, {"official_receipt_number": "OR-OLD"})
    item.refresh_from_db()
    version, revision = item.updated_at.isoformat(), receipts.latest_revision(item).pk
    start = Barrier(2)

    def attempt(number):
        start.wait(timeout=10)
        try:
            edit(
                item,
                actor,
                {"official_receipt_number": number},
                expected_resource_version=version,
                expected_receipt_revision=revision,
            )
            return "won"
        except receipts.ReceiptChanged:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=20)
            for f in [pool.submit(worker, lambda n=n: attempt(n)) for n in ("OR-NEW1", "OR-NEW2")]
        ]
    assert sorted(results) == ["stale", "won"]
    assert (
        Identity.objects.count() == 2 and Identity.objects.filter(normalized_key="OR-OLD").exists()
    )
    assert Assignment.objects.filter(request=item, is_current=True).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("action", ["cancel", "prepare", "issue"])
@pytest.mark.parametrize("correction_first", [False, True])
def test_lifecycle_competition_keeps_one_serial_history(world, action, correction_first):
    actor, item = world
    from tests.test_good_moral_verification import grant, prepare, verify

    grant(actor)
    edit(
        item,
        actor,
        {
            "official_receipt_number": "OR-OLD",
            "official_receipt_date": date(2020, 1, 1),
            "official_receipt_amount": Decimal("80.00"),
        },
    )
    verify(item, actor)
    if action == "issue":
        item = prepare(item, actor)
    item.refresh_from_db()
    version, revision = item.updated_at.isoformat(), receipts.latest_revision(item).pk
    prepared = item.prepared_at.isoformat() if item.prepared_at else None
    locked, release = Event(), Event()

    def change():
        return edit(
            item,
            actor,
            {"official_receipt_number": "OR-NEW"},
            expected_resource_version=version,
            expected_receipt_revision=revision,
        )

    def lifecycle():
        if action == "cancel":
            return cancel_request(
                actor=actor,
                request_id=item.pk,
                reason="Synthetic",
                self_service=False,
                context=AuditContext.user(actor),
            )
        if action == "prepare":
            return prepare_request(
                actor=actor,
                request_id=item.pk,
                context=AuditContext.user(actor),
                expected_resource_version=version,
            )
        return issue_request(
            actor=actor,
            request_id=item.pk,
            context=AuditContext.user(actor),
            expected_preparation_version=prepared,
            expected_resource_version=version,
            expected_receipt_revision=revision,
            expected_receipt_verification=item.prepared_receipt_verification_id,
        )

    first, second = (change, lifecycle) if correction_first else (lifecycle, change)

    def leader():
        with transaction.atomic():
            GoodMoralRequest.objects.select_for_update().get(pk=item.pk)
            result = first()
            locked.set()
            assert release.wait(10)
            return result.status

    def follower():
        try:
            return second().status
        except GoodMoralConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, leader)
        assert locked.wait(10)
        f2 = pool.submit(worker, follower)
        release.set()
        f1.result(timeout=20)
        second_result = f2.result(timeout=20)
    item.refresh_from_db()
    if correction_first:
        assert item.official_receipt_number == "OR-NEW"
        assert item.status == ("CANCELLED" if action == "cancel" else "REQUESTED")
    else:
        assert second_result == "conflict" and item.official_receipt_number == "OR-OLD"
        assert (
            item.status
            == {"cancel": "CANCELLED", "prepare": "READY_FOR_ISSUANCE", "issue": "ISSUED"}[action]
        )
    assert Identity.objects.count() == (2 if correction_first else 1)


@pytest.mark.django_db(transaction=True)
def test_receipt_lock_timeout_rolls_back_and_deliberate_retry_recovers(world):
    actor, item = world
    locked, release = Event(), Event()

    def holder():
        with transaction.atomic():
            GoodMoralRequest.objects.select_for_update().get(pk=item.pk)
            locked.set()
            assert release.wait(10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker, holder)
        assert locked.wait(10)
        with pytest.raises(OperationalError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout='50ms'")
            edit(item, actor, {"official_receipt_number": "OR-TIMEOUT"})
        release.set()
        future.result(timeout=10)
    assert not Identity.objects.exists() and not Mutation.objects.exists()
    edit(item, actor, {"official_receipt_number": "OR-TIMEOUT"})
    assert Identity.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_unclaimed_ordinary_reservation_cannot_commit(world):
    actor, item = world
    with pytest.raises(IntegrityError), transaction.atomic():
        Identity.objects.create(
            normalized_key="OR-ORPHAN",
            bound_request=item,
            state="BOUND",
            origin="ORDINARY",
            recorded_by=actor,
        )
    assert not Identity.objects.exists()


@pytest.mark.django_db
def test_api_requires_active_receipt_tokens_preserves_projection_and_replay(world):
    import json

    from tests.test_good_moral import auth_client, csrf

    actor, item = world
    other = request_for()
    client = auth_client(actor)
    path = f"/api/v1/good-moral/requests/{item.pk}"
    initial = client.get(path).json()
    revision = initial["receipt_identity"]["revision_id"]
    payload = {
        "official_receipt_number": "OR-PRIVATE",
        "expected_resource_version": initial["actions"]["request_version"],
        "expected_receipt_revision": revision,
        "receipt_operation_id": str(uuid4()),
    }

    def patch(url, data):
        return client.patch(
            url, data=json.dumps(data), content_type="application/json", **csrf(client)
        )

    assert patch(path, {"official_receipt_number": "OR-PRIVATE"}).status_code == 422
    result = patch(path, payload)
    assert result.status_code == 200
    assert result.json()["official_receipt_number"] == "OR-PRIVATE"
    committed = result.json()["receipt_mutation_result"]
    assert patch(path, payload).json()["receipt_mutation_result"] == committed
    stale = {**payload, "official_receipt_number": "OR-NEW", "receipt_operation_id": str(uuid4())}
    assert patch(path, stale).json()["error"]["code"] == "good_moral_receipt_changed"
    other_path = f"/api/v1/good-moral/requests/{other.pk}"
    detail = client.get(other_path).json()
    duplicate = patch(
        other_path,
        {
            **payload,
            "expected_resource_version": detail["actions"]["request_version"],
            "expected_receipt_revision": detail["receipt_identity"]["revision_id"],
            "receipt_operation_id": str(uuid4()),
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "good_moral_receipt_conflict"
    assert (
        str(item.student_id) not in duplicate.content.decode()
        and str(item.pk) not in duplicate.content.decode()
    )
    # Existing non-receipt corrections remain compatible without receipt tokens.
    assert patch(path, {"major": "Unrelated certificate change"}).status_code == 200
    student = auth_client(item.student)
    owned = student.get(f"/api/v1/good-moral/me/{item.pk}")
    assert owned.status_code == 200 and "receipt_identity" not in owned.json()


@pytest.mark.django_db
def test_active_draft_does_not_inspect_and_wrong_amount_blocks_preparation(world):
    from compass.accounts.policy import CAPABILITY_CODES, ROLE_CAPABILITY_GRANTS
    from compass.good_moral.receipt_verification import ReceiptBlocked

    actor, item = world
    staff = person("clerical", "GUIDANCE_OFFICE_ASSISTANT")
    edit(item, staff, {"official_receipt_amount": Decimal("0")})
    assert not Identity.objects.exists()
    with pytest.raises(ReceiptBlocked):
        prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    assert "good_moral.verify_receipt" in CAPABILITY_CODES
    for role in ("COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"):
        assert {
            "good_moral.view",
            "good_moral.prepare",
            "good_moral.verify_receipt",
        } <= ROLE_CAPABILITY_GRANTS[role]
    assert Mutation.objects.get(request=item).result_revision.amount == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_operation_uuid_reuse_cannot_leave_losing_identity(world, monkeypatch):
    actor, first = world
    second = request_for()
    operation = uuid4()
    barrier = Barrier(2)
    create = Mutation.objects.create

    def simultaneous_operation(**kwargs):
        barrier.wait(timeout=10)
        return create(**kwargs)

    monkeypatch.setattr(Mutation.objects, "create", simultaneous_operation)

    def attempt(item, number):
        try:
            edit(item, actor, {"official_receipt_number": number}, operation_id=operation)
            return "committed"
        except receipts.ReceiptOperationConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result(timeout=20)
            for f in [
                pool.submit(worker, lambda: attempt(first, "OR-ONE")),
                pool.submit(worker, lambda: attempt(second, "OR-TWO")),
            ]
        ]
    assert sorted(results) == ["committed", "conflict"]
    assert Mutation.objects.count() == 1 and Identity.objects.count() == 1
    assert Assignment.objects.filter(origin="ORDINARY").count() == 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_assigned").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
@pytest.mark.parametrize("assisted", [False, True])
def test_new_self_and_assisted_requests_still_start_without_receipts_after_cutover(
    world, variant, assisted
):
    from compass.good_moral.services import create_assisted_request
    from tests.test_good_moral import create_my_graduate, make_academic_year

    actor, _ = world
    student = person("new-applicant")
    if variant == "CURRENT_STUDENT":
        year = AcademicYear.objects.filter(is_current=True).first() or make_academic_year()
        make_placement(student)
        make_inventory(student, year)
        details = {"semester": "First Semester"}
    else:
        details = {
            "degree": "Bachelor of Science",
            "major": "",
            "graduation_date": date(2020, 1, 1),
        }
    if assisted:
        item = create_assisted_request(
            actor=actor,
            student_id=student.pk,
            variant=variant,
            details=details,
            idempotency_key=f"active-create-{uuid4()}",
            request_fingerprint="a" * 64,
            context=AuditContext.user(actor),
        )
    elif variant == "CURRENT_STUDENT":
        item = create_my_current_student(
            student=student, context=AuditContext.user(student), **details
        )
    else:
        item = create_my_graduate(student=student, context=AuditContext.user(student), **details)
    assert item.official_receipt_number == "" and receipts.latest_revision(item) is None
    assert not Identity.objects.exists()
    edit(item, actor, {"official_receipt_number": "OR-FIRST-AFTER-CUTOVER"})
    revision = receipts.latest_revision(item)
    assert revision.sequence == 1 and revision.previous_id is None and revision.is_current


@pytest.mark.django_db
def test_new_operation_rows_must_reference_the_current_result(world):
    actor, item = world
    edit(item, actor, {"official_receipt_number": "OR-1"})
    item.refresh_from_db()
    current = receipts.latest_revision(item)
    for result, version in (
        (None, item.updated_at.isoformat()),
        (current, "2000-01-01T00:00:00+00:00"),
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            Mutation.objects.create(
                operation_id=uuid4(),
                actor=actor,
                request=item,
                fingerprint="a" * 64,
                intended_revision=current,
                result_revision=result,
                result_request_version=version,
            )
    assert Mutation.objects.count() == 1


@pytest.mark.django_db
def test_fresh_schema_has_unconditional_guards_and_required_origin():
    tables = connection.introspection.table_names()
    assert "good_moral_goodmoralreceiptledger" not in tables
    assert "good_moral_goodmoralreceiptimportbatch" not in tables
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.proname, pg_get_functiondef(p.oid) FROM pg_proc p "
            "WHERE p.proname LIKE 'gm_receipt_%' OR p.proname LIKE 'gm_inspection_%'"
        )
        definitions = dict(cursor.fetchall())
        for definition in definitions.values():
            assert "goodmoralreceiptledger" not in definition
            assert "LEGACY_" not in definition
            assert "policy_id" not in definition
            assert "policy_version" not in definition
            assert "fee_decision" not in definition
            assert "PROVISIONAL" not in definition
        assert {
            "gm_receipt_identity_guard",
            "gm_receipt_projection_guard",
            "gm_inspection_request_guard",
        } <= definitions.keys()
        verification_guard = definitions["gm_receipt_verification_guard"]
        assert "NEW.currency IS DISTINCT FROM 'PHP'" in verification_guard
        assert "NEW.expected_amount IS DISTINCT FROM 80.00" in verification_guard
        assert "r.variant NOT IN ('CURRENT_STUDENT','GRADUATE')" in verification_guard
        cursor.execute(
            "SELECT column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name='good_moral_goodmoralrequest' AND column_name='initiation_origin'"
        )
        assert cursor.fetchone() == (None, "NO")
    assert not GoodMoralRequest._meta.get_field("initiation_origin").has_default()
