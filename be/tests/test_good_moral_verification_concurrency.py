# ruff: noqa: F811
"""Independent PostgreSQL connections and explicit request/account fence synchronization."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection, transaction

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.good_moral import receipt_fee_policy as fees
from compass.good_moral import receipt_identity as receipts
from compass.good_moral import receipt_verification as inspections
from compass.good_moral.models import GoodMoralReceiptVerification as Verification
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import GoodMoralConflict, GoodMoralNotPermitted, cancel_request
from tests.test_good_moral_receipts import edit, request_for
from tests.test_good_moral_verification import (
    approved,  # noqa: F401 fixture discovery
    grant,
    intent,
    issue,
    prepare,
    scene,  # noqa: F401 fixture discovery
    verify,
)

pytestmark = pytest.mark.django_db(transaction=True)


def worker(fn):
    close_old_connections()
    try:
        return fn()
    finally:
        connection.close()


def outcome(fn):
    try:
        result = fn()
        return "committed", getattr(result, "pk", None)
    except (GoodMoralConflict, GoodMoralNotPermitted) as exc:
        return type(exc).__name__, None


def serial_race(item, first, second):
    locked, release, attempted = Event(), Event(), Event()

    def leader():
        with transaction.atomic():
            GoodMoralRequest.objects.select_for_update().get(pk=item.pk)
            with transaction.atomic():
                result = outcome(first)
            locked.set()
            assert release.wait(15)
            return result

    def follower():
        attempted.set()
        return outcome(second)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, leader)
        assert locked.wait(15)
        f2 = pool.submit(worker, follower)
        assert attempted.wait(15)
        release.set()
        return f1.result(timeout=25), f2.result(timeout=25)


@pytest.mark.parametrize("action", ["correction", "prepare", "cancel", "issue"])
@pytest.mark.parametrize("verification_first", [True, False])
def test_inspection_competes_with_request_lifecycle(scene, action, verification_first):
    actor, item = scene
    args = intent(item, actor)
    if action == "issue":
        # A historical exact replay can acknowledge inspection after final issuance.
        inspections.verify_receipt(**args)
        prepare(item, actor)
    item.refresh_from_db()
    version = item.updated_at.isoformat()
    assignment = receipts.latest_revision(item).pk

    def inspection():
        return inspections.verify_receipt(**args)

    def other():
        if action == "correction":
            return edit(
                item,
                actor,
                {"official_receipt_number": "OR-CONCURRENT"},
                expected_resource_version=version,
                expected_receipt_revision=assignment,
            )
        if action == "prepare":
            from compass.good_moral.services import prepare_request

            return prepare_request(
                actor=actor,
                request_id=item.pk,
                context=AuditContext.user(actor),
                expected_resource_version=version,
            )
        if action == "cancel":
            return cancel_request(
                actor=actor,
                request_id=item.pk,
                reason="Synthetic",
                self_service=False,
                context=AuditContext.user(actor),
            )
        return issue(item, actor)

    first, second = (inspection, other) if verification_first else (other, inspection)
    results = serial_race(item, first, second)
    item.refresh_from_db()
    rows = list(Verification.objects.all())
    assert len(rows) <= 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_verified").count() == len(rows)
    if action == "cancel":
        assert item.status == "CANCELLED"
        assert all(v.invalidated_at is not None for v in rows)
    elif action == "correction":
        assert item.status == "REQUESTED"
        if verification_first:
            assert item.official_receipt_number == "OR-SYNTHETIC-0001" and len(rows) == 1
        else:
            assert item.official_receipt_number == "OR-CONCURRENT" and not rows
    elif action == "prepare":
        assert item.status == "REQUESTED" and len(rows) == 1
    else:
        assert item.status == "ISSUED" and item.issued_receipt_verification_id == rows[0].pk
        assert all(r[0] == "committed" for r in results)


@pytest.mark.parametrize("identical", [False, True])
def test_simultaneous_inspection_and_exact_replay_have_single_attestation(scene, identical):
    actor, item = scene
    args = intent(item, actor)
    barrier = Barrier(2)

    def attempt(op):
        barrier.wait(timeout=15)
        return outcome(lambda: inspections.verify_receipt(**{**args, "operation_id": op}))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, lambda op=op: attempt(op))
            for op in [args["operation_id"], args["operation_id"] if identical else uuid4()]
        ]
        results = [f.result(timeout=25)[0] for f in futures]
    assert results.count("committed") == (2 if identical else 1)
    assert Verification.objects.count() == 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_verified").count() == 1


def test_concurrent_global_operation_reuse_rolls_back_loser(scene, monkeypatch):
    actor, first = scene
    second = request_for()
    edit(
        second,
        actor,
        {
            "official_receipt_number": "OR-SECOND",
            "official_receipt_date": first.official_receipt_date,
            "official_receipt_amount": first.official_receipt_amount,
        },
    )
    # Different inspectors avoid serializing on the same account fence.
    from tests.test_good_moral_receipts import person

    other = person("second-inspector", "COUNSELOR")
    grant(other)
    operation_id = uuid4()
    barrier = Barrier(2)
    original = inspections.decision_for

    def synchronized(item, assignment):
        if not Verification.objects.filter(assignment=assignment).exists():
            barrier.wait(timeout=15)
        return original(item, assignment)

    monkeypatch.setattr(inspections, "decision_for", synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                worker,
                lambda item=item, a=a: outcome(lambda: verify(item, a, operation_id=operation_id)),
            )
            for item, a in [(first, actor), (second, other)]
        ]
        results = [f.result(timeout=30)[0] for f in futures]
    assert sorted(results) == ["ReceiptOperationConflict", "committed"]
    assert Verification.objects.count() == 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_verified").count() == 1


@pytest.mark.parametrize("change", ["revocation", "deactivation"])
def test_account_change_before_authority_fence_is_rechecked(scene, monkeypatch, change):
    actor, item = scene
    reached, resume = Event(), Event()
    original = inspections.authority

    def pause(*args, **kwargs):
        if kwargs.get("lock"):
            reached.set()
            assert resume.wait(15)
        return original(*args, **kwargs)

    monkeypatch.setattr(inspections, "authority", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(worker, lambda: outcome(lambda: verify(item, actor)))
        assert reached.wait(15)
        if change == "revocation":
            grant(actor, effect="REVOKE")
        else:
            User.objects.filter(pk=actor.pk).update(is_active=False)
        resume.set()
        result = future.result(timeout=25)
    assert result[0] == "GoodMoralNotPermitted"
    assert not Verification.objects.exists()


@pytest.mark.parametrize("change", ["revocation", "deactivation"])
def test_account_change_after_authority_fence_serializes_after_inspection(
    scene, monkeypatch, change
):
    actor, item = scene
    locked, resume, attempted = Event(), Event(), Event()
    original = inspections.eligible

    def pause(*args, **kwargs):
        result = original(*args, **kwargs)
        locked.set()
        assert resume.wait(15)
        return result

    monkeypatch.setattr(inspections, "eligible", pause)

    def account_change():
        attempted.set()
        if change == "revocation":
            grant(actor, effect="REVOKE")
        else:
            User.objects.filter(pk=actor.pk).update(is_active=False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, lambda: outcome(lambda: verify(item, actor)))
        assert locked.wait(15)
        second = pool.submit(worker, account_change)
        assert attempted.wait(15)
        resume.set()
        assert first.result(timeout=25)[0] == "committed"
        second.result(timeout=25)
    assert Verification.objects.count() == 1
    with pytest.raises(GoodMoralNotPermitted):
        verify(item, actor)


@pytest.mark.parametrize("first_action", ["issue", "correction"])
def test_final_issue_and_late_correction_keep_one_committed_history(scene, first_action):
    actor, item = scene
    verify(item, actor)
    prepare(item, actor)
    item.refresh_from_db()
    version, revision = item.updated_at.isoformat(), receipts.latest_revision(item).pk

    def correction():
        return edit(
            item,
            actor,
            {"official_receipt_amount": 75},
            expected_resource_version=version,
            expected_receipt_revision=revision,
        )

    first, second = (
        (lambda: issue(item, actor), correction)
        if first_action == "issue"
        else (correction, lambda: issue(item, actor))
    )
    serial_race(item, first, second)
    item.refresh_from_db()
    if first_action == "issue":
        assert item.status == "ISSUED" and item.official_receipt_amount == 80
        assert item.issued_receipt_verification_id
        assert Verification.objects.get().invalidated_at is None
    else:
        assert item.status == "REQUESTED" and item.official_receipt_amount == 75
        assert item.issued_receipt_verification_id is None
        assert Verification.objects.get().invalidated_at is not None


@pytest.mark.parametrize("transition", ["verify", "prepare", "issue"])
def test_policy_changes_during_transaction_roll_back_every_effect(scene, monkeypatch, transition):
    actor, item = scene
    if transition != "verify":
        verify(item, actor)
    if transition == "issue":
        prepare(item, actor)
    item.refresh_from_db()
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    module = (
        inspections
        if transition == "verify"
        else __import__("compass.good_moral.services", fromlist=["record_event"])
    )
    original = module.record_event

    def change_policy(**kw):
        result = original(**kw)
        monkeypatch.setattr(fees, "resolve_approved_fee", lambda **kwargs: None)
        return result

    monkeypatch.setattr(module, "record_event", change_policy)
    with pytest.raises(inspections.ReceiptBlocked):
        (verify if transition == "verify" else prepare if transition == "prepare" else issue)(
            item, actor
        )
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    assert Verification.objects.count() == (0 if transition == "verify" else 1)


def test_inspection_waits_for_real_dormant_to_fenced_transition(approved):
    from compass.good_moral.legacy_receipts import begin_import
    from compass.good_moral.models import GoodMoralReceiptLedger
    from tests.test_good_moral import sync_policy
    from tests.test_good_moral_receipts import person

    sync_policy()
    actor = person("inspector", "COUNSELOR")
    grant(actor)
    item = request_for()
    locked, resume, attempted = Event(), Event(), Event()

    def fence():
        with transaction.atomic():
            begin_import(batch_id=uuid4(), evidence_reference="synthetic-fence")
            locked.set()
            assert resume.wait(15)

    def inspection():
        attempted.set()
        return outcome(
            lambda: inspections.verify_receipt(**intent(item, actor, assignment_id=uuid4()))
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, fence)
        assert locked.wait(15)
        second = pool.submit(worker, inspection)
        assert attempted.wait(15)
        resume.set()
        first.result(timeout=25)
        assert second.result(timeout=25)[0] == "ReceiptCutoverRequired"
    assert GoodMoralReceiptLedger.objects.get(pk=1).mode == "FENCED"
    assert not Verification.objects.exists()


@pytest.mark.parametrize("lifecycle_first", [True, False])
def test_active_f4_issue_and_account_lifecycle_share_ordered_identity_fence(
    approved, lifecycle_first
):
    from compass.account_management.services import _lock_users
    from compass.good_moral.services import GoodMoralCurrentStudentRequired
    from tests.test_good_moral import sync_policy
    from tests.test_good_moral_receipts import activate, person

    sync_policy()
    actor = person("issuer", "COUNSELOR")
    grant(actor)
    item = request_for(variant="CURRENT_STUDENT")
    activate()
    from datetime import date

    edit(
        item,
        actor,
        {
            "official_receipt_number": "OR-F4-LOCKS",
            "official_receipt_date": date(2020, 1, 1),
            "official_receipt_amount": 80,
        },
    )
    verify(item, actor)
    prepare(item, actor)
    locked, resume, attempted = Event(), Event(), Event()

    def lifecycle():
        with transaction.atomic():
            _, student = _lock_users(actor_id=actor.pk, target_id=item.student_id)
            student.student_lifecycle_status = "GRADUATED"
            student.save(update_fields=["student_lifecycle_status", "updated_at"])
            if lifecycle_first:
                locked.set()
                assert resume.wait(15)

    def issuance():
        if lifecycle_first:
            attempted.set()
            try:
                return issue(item, actor).status
            except GoodMoralCurrentStudentRequired:
                return "student_changed"
        with transaction.atomic():
            result = issue(item, actor)
            locked.set()
            assert resume.wait(15)
            return result.status

    def late_lifecycle():
        attempted.set()
        return lifecycle()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, lifecycle if lifecycle_first else issuance)
        assert locked.wait(15)
        second = pool.submit(worker, issuance if lifecycle_first else late_lifecycle)
        assert attempted.wait(15)
        resume.set()
        results = [first.result(timeout=25), second.result(timeout=25)]
    item.refresh_from_db()
    if lifecycle_first:
        assert results[1] == "student_changed"
        assert item.status == "READY_FOR_ISSUANCE" and item.issued_receipt_verification_id is None
    else:
        assert results[0] == "ISSUED" and item.issued_receipt_verification_id
    assert User.objects.get(pk=item.student_id).student_lifecycle_status == "GRADUATED"
