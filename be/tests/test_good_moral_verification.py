"""Synthetic approved policy, exact physical attestations and prospective transition gates."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.policy import ROLE_CAPABILITY_GRANTS
from compass.accounts.services import set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.feedback.models import FeedbackOpportunity
from compass.good_moral import receipt_fee_policy as fees
from compass.good_moral import receipt_identity as receipts
from compass.good_moral import receipt_verification as inspections
from compass.good_moral.models import GoodMoralReceiptVerification as Verification
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import (
    GoodMoralConflict,
    GoodMoralNotPermitted,
    InvalidGoodMoralInput,
    cancel_request,
    issue_request,
    prepare_request,
)
from compass.notifications.models import Notification
from tests.test_good_moral import auth_client, csrf, sync_policy
from tests.test_good_moral_receipts import activate, edit, person, request_for

pytestmark = pytest.mark.django_db(transaction=True)


def synthetic_fee(*, item, assignment):
    # Explicit fiction, not an institutional effective date or deployed schedule.
    return fees.FeeDecision(
        policy_id="SYNTHETIC-ONLY",
        version="fixture-v1",
        currency="PHP",
        expected_amount=Decimal("80.00"),
        authority_reference="isolated-test-approval",
        variant=item.variant,
        reference_date=assignment.receipt_date,
        applicable_from=date(2000, 1, 1),
        applicable_through=date(2099, 12, 31),
    )


def grant(actor, code="good_moral.verify_receipt", effect="GRANT", expires_at=None):
    return set_user_capability_override(
        user=actor,
        capability=code,
        effect=effect,
        reason="Synthetic authorized fixture",
        expires_at=expires_at,
    )


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setattr(fees, "resolve_approved_fee", synthetic_fee)


@pytest.fixture
def scene(approved):
    sync_policy()
    actor = person("inspector", "COUNSELOR")
    grant(actor)
    item = request_for(
        official_receipt_number="OR-SYNTHETIC-0001",
        official_receipt_date=institution_today() - timedelta(days=1),
        official_receipt_amount=Decimal("80.00"),
    )
    activate()
    return actor, item


def intent(item, actor, **overrides):
    item.refresh_from_db()
    args = dict(
        actor=actor,
        request_id=item.pk,
        context=AuditContext.user(actor),
        expected_resource_version=item.updated_at.isoformat(),
        assignment_id=getattr(receipts.latest_revision(item), "pk", None),
        operation_id=uuid4(),
        method=inspections.METHOD,
    )
    args.update(overrides)
    return args


def verify(item, actor, **overrides):
    return inspections.verify_receipt(**intent(item, actor, **overrides))


def prepare(item, actor):
    item.refresh_from_db()
    return prepare_request(
        actor=actor,
        request_id=item.pk,
        context=AuditContext.user(actor),
        expected_resource_version=item.updated_at.isoformat(),
    )


def issue(item, actor, **overrides):
    item.refresh_from_db()
    assignment = receipts.latest_revision(item)
    verification = inspections.current_verification(assignment)
    args = dict(
        actor=actor,
        request_id=item.pk,
        context=AuditContext.user(actor),
        expected_preparation_version=item.prepared_at.isoformat() if item.prepared_at else None,
        expected_resource_version=item.updated_at.isoformat(),
        expected_receipt_revision=assignment.pk,
        expected_receipt_verification=verification.pk if verification else None,
    )
    args.update(overrides)
    return issue_request(**args)


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_full_workflow_and_issued_replay_preserve_provenance_and_effects(approved, variant):
    sync_policy()
    actor = person("inspector", "GUIDANCE_SERVICES_STAFF")
    counselor = person("issuer", "COUNSELOR")
    grant(actor)
    item = request_for(
        variant=variant,
        official_receipt_number="OR-POSITIVE",
        official_receipt_date=institution_today(),
        official_receipt_amount=Decimal("80.00"),
    )
    activate()
    with pytest.raises(inspections.ReceiptBlocked, match="inspect"):
        prepare(item, actor)
    assert not Verification.objects.exists()
    result = verify(item, actor)
    attestation = result.receipt_verification_result
    assert attestation.verified_by_id == actor.pk and timezone.is_aware(attestation.verified_at)
    assert attestation.fee_decision["reference_date"] == institution_today().isoformat()
    prepared = prepare(item, counselor)  # preparer need not be inspector
    assert prepared.prepared_receipt_verification_id == attestation.pk
    issued = issue(item, counselor)
    assert issued.issued_receipt_assignment_id == attestation.assignment_id
    assert issued.issued_receipt_verification_id == attestation.pk
    before = (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        FeedbackOpportunity.objects.count(),
    )
    assert (
        issue_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)).pk
        == item.pk
    )
    assert before == (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        FeedbackOpportunity.objects.count(),
    )
    assert FeedbackOpportunity.objects.filter(source_id=item.pk).count() == 1
    assert (
        AuditEvent.objects.filter(action="good_moral.issued", target_id=str(item.pk)).count() == 1
    )
    verified_event = AuditEvent.objects.get(action="good_moral.receipt_verified")
    assert set(verified_event.metadata) == {
        "revision_id",
        "verification_id",
        "policy_id",
        "policy_version",
        "method",
    }
    assert "OR-POSITIVE" not in str(verified_event.metadata)
    assert not {"amount", "official_receipt_amount", "official_receipt_number"}.intersection(
        verified_event.metadata
    )


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
@pytest.mark.parametrize(
    "facts,code",
    [
        ({"official_receipt_number": ""}, "missing"),
        ({"official_receipt_date": None}, "incomplete"),
        ({"official_receipt_amount": None}, "incomplete"),
        ({"official_receipt_amount": Decimal("0.00")}, "fee_mismatch"),
        ({"official_receipt_amount": Decimal("75.00")}, "fee_mismatch"),
        ({"official_receipt_amount": Decimal("100.00")}, "fee_mismatch"),
        ({"official_receipt_amount": Decimal("-1.00")}, "conflict"),
        ({"official_receipt_date": date(2098, 1, 1)}, "incomplete"),
    ],
)
def test_ineligible_imported_receipts_are_preserved_and_blocked(approved, variant, facts, code):
    sync_policy()
    actor = person("inspector", "COUNSELOR")
    grant(actor)
    original = dict(
        official_receipt_number="OR-MATRIX",
        official_receipt_date=date(2020, 1, 1),
        official_receipt_amount=Decimal("80.00"),
    )
    original.update(facts)
    item = request_for(variant=variant, **original)
    activate()
    with pytest.raises(inspections.ReceiptBlocked) as caught:
        verify(item, actor)
    assert caught.value.code == f"good_moral_receipt_{code}"
    with pytest.raises(inspections.ReceiptBlocked):
        prepare(item, actor)
    item.refresh_from_db()
    for name, value in original.items():
        assert getattr(item, name) == value
    assert not Verification.objects.exists()


@pytest.mark.parametrize(
    "value", [Decimal("-1.00"), Decimal("80.001"), Decimal("NaN"), Decimal("Infinity")]
)
def test_invalid_amount_input_rejected_before_revision(scene, value):
    actor, item = scene
    with pytest.raises(InvalidGoodMoralInput):
        edit(item, actor, {"official_receipt_amount": value})
    assert receipts.latest_revision(item).sequence == 1


@pytest.mark.parametrize(
    "role,explicit,allowed",
    [
        ("COUNSELOR", True, True),
        ("GUIDANCE_SERVICES_STAFF", True, True),
        ("COUNSELOR", False, False),
        ("GUIDANCE_SERVICES_STAFF", False, False),
        ("STUDENT", True, False),
        ("IT_ADMIN", True, False),
    ],
)
def test_explicit_capability_and_role_required(scene, role, explicit, allowed):
    _, item = scene
    actor = person("candidate", role)
    if explicit:
        grant(actor)
        grant(actor, "good_moral.prepare")
        grant(actor, "good_moral.view")
    if allowed:
        assert verify(item, actor).receipt_verification_result.verified_by_id == actor.pk
    else:
        with pytest.raises(GoodMoralNotPermitted):
            verify(item, actor)
    assert all(
        "good_moral.verify_receipt" not in codes for codes in ROLE_CAPABILITY_GRANTS.values()
    )


@pytest.mark.parametrize("change", ["dependency", "revoked", "expired", "inactive", "audit_actor"])
def test_fresh_authority_dependencies_expiry_and_attribution(scene, change):
    actor, item = scene
    kwargs = {}
    if change == "dependency":
        grant(actor, "good_moral.prepare", "REVOKE")
    elif change == "revoked":
        grant(actor, effect="REVOKE")
    elif change == "expired":
        grant(actor, expires_at=timezone.now() - timedelta(seconds=1))
    elif change == "inactive":
        User.objects.filter(pk=actor.pk).update(is_active=False)
    else:
        kwargs["context"] = AuditContext.user(item.student)
    with pytest.raises(GoodMoralNotPermitted):
        verify(item, actor, **kwargs)
    assert not Verification.objects.exists()


def test_head_designation_does_not_imply_inspection(scene):
    from compass.accounts.models import Designation, UserDesignation

    _, item = scene
    actor = person("head", "COUNSELOR")
    UserDesignation.objects.create(
        user=actor, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    with pytest.raises(GoodMoralNotPermitted):
        verify(item, actor)


@pytest.mark.parametrize("role", ["GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "STUDENT"])
def test_issue_role_fence_survives_unusual_override(scene, role):
    actor, item = scene
    verify(item, actor)
    prepare(item, actor)
    other = person("nonissuer", role)
    grant(other, "good_moral.issue")
    grant(other, "good_moral.view")
    with pytest.raises(GoodMoralNotPermitted):
        issue(item, other)
    item.refresh_from_db()
    assert item.status == "READY_FOR_ISSUANCE"


@pytest.mark.parametrize(
    "kind",
    [
        "absent",
        "not_approved",
        "wrong_variant",
        "unknown_range",
        "missing_range",
        "wrong_reference",
        "invalid_rule",
        "missing_authority",
    ],
)
def test_fee_provider_fail_closed(scene, monkeypatch, kind):
    actor, item = scene

    def provider(**kw):
        d = synthetic_fee(**kw)
        if kind == "absent":
            return None
        return replace(
            d,
            **{
                "not_approved": {"status": "TEAM_REPORTED"},
                "wrong_variant": {"variant": "CURRENT_STUDENT"},
                "unknown_range": {"applicable_from": date(2099, 1, 1)},
                "missing_range": {"applicable_from": None},
                "wrong_reference": {"reference_date": date(2001, 1, 1)},
                "invalid_rule": {"applicability_rule": "ASSUME_ALWAYS"},
                "missing_authority": {"authority_reference": ""},
            }[kind],
        )

    monkeypatch.setattr(fees, "resolve_approved_fee", provider)
    with pytest.raises(inspections.ReceiptBlocked) as caught:
        verify(item, actor)
    assert caught.value.code == "good_moral_receipt_policy_unresolved"
    with pytest.raises(inspections.ReceiptBlocked):
        prepare(item, actor)
    assert not Verification.objects.exists()


@pytest.mark.parametrize("change", ["number", "date", "amount", "display", "remove"])
def test_receipt_revision_invalidates_exact_attestation(scene, change):
    actor, item = scene
    args = intent(item, actor)
    result = inspections.verify_receipt(**args)
    verification = result.receipt_verification_result
    prepare(item, actor)
    changes = {
        "number": {"official_receipt_number": "OR-REPLACED"},
        "display": {"official_receipt_number": "or-synthetic-0001"},
        "date": {"official_receipt_date": institution_today()},
        "amount": {"official_receipt_amount": Decimal("75.00")},
        "remove": {"official_receipt_number": ""},
    }[change]
    result = edit(item, actor, changes)
    assert result.status == "REQUESTED" and result.prepared_receipt_verification_id is None
    verification.refresh_from_db()
    assert verification.invalidation_reason == "RECEIPT_REVISED"
    assert verification.invalidated_by_id == actor.pk
    replay = inspections.verify_receipt(**args)
    assert replay.receipt_verification_result.pk == verification.pk
    assert replay.receipt_verification_result.invalidated_at is not None
    assert Verification.objects.count() == 1
    assert AuditEvent.objects.filter(action="good_moral.receipt_verified").count() == 1
    assert (
        AuditEvent.objects.filter(action="good_moral.receipt_verification_invalidated").count() == 1
    )


def test_unrelated_correction_retains_inspection_but_requires_repreparation(scene):
    actor, item = scene
    verification = verify(item, actor).receipt_verification_result
    prepare(item, actor)
    result = edit(item, actor, {"degree_snapshot": "Bachelor of Arts"})
    assert result.status == "REQUESTED"
    assert receipts.latest_revision(item).pk == verification.assignment_id
    verification.refresh_from_db()
    assert verification.invalidated_at is None
    prepare(item, actor)
    assert issue(item, actor).issued_receipt_verification_id == verification.pk


def test_cancellation_invalidates_without_releasing_and_retry_cannot_revive(scene):
    actor, item = scene
    args = intent(item, actor)
    verification = inspections.verify_receipt(**args).receipt_verification_result
    cancel_request(
        actor=actor,
        request_id=item.pk,
        context=AuditContext.user(actor),
        reason="Synthetic",
        self_service=False,
    )
    verification.refresh_from_db()
    assert verification.invalidation_reason == "CANCELLED"
    assert inspections.verify_receipt(**args).status == "CANCELLED"
    assert receipts.latest_revision(item).identity.bound_request_id == item.pk
    with pytest.raises(GoodMoralConflict):
        verify(item, actor)


@pytest.mark.parametrize("stale", ["request", "revision", "operation", "actor", "method"])
def test_review_tokens_and_operation_intent_are_exact(scene, stale):
    actor, item = scene
    args = intent(item, actor)
    if stale == "request":
        edit(item, actor, {"degree_snapshot": "Changed degree"})
    elif stale == "revision":
        args["assignment_id"] = uuid4()
    elif stale == "method":
        args["method"] = "CASHIER_CONFIRMED"
    else:
        inspections.verify_receipt(**args)
        if stale == "operation":
            args["expected_resource_version"] = "different-intent"
        else:
            other = person("other", "COUNSELOR")
            grant(other)
            args.update(actor=other, context=AuditContext.user(other))
    with pytest.raises(
        (receipts.ReceiptChanged, receipts.ReceiptOperationConflict, InvalidGoodMoralInput)
    ):
        inspections.verify_receipt(**args)


def test_identical_replay_and_different_inspector_preserve_original(scene):
    actor, item = scene
    args = intent(item, actor)
    first = inspections.verify_receipt(**args).receipt_verification_result
    second = inspections.verify_receipt(**args).receipt_verification_result
    assert (first.pk, first.verified_by_id, first.verified_at) == (
        second.pk,
        second.verified_by_id,
        second.verified_at,
    )
    other = person("second-inspector", "COUNSELOR")
    grant(other)
    with pytest.raises(inspections.ReceiptBlocked) as caught:
        verify(item, other)
    assert caught.value.code == "good_moral_receipt_already_verified"
    assert Verification.objects.count() == 1


@pytest.mark.parametrize("changed", ["unavailable", "version", "applicability", "amount"])
def test_policy_change_before_issue_blocks_then_requires_deliberate_review(
    scene, monkeypatch, changed
):
    actor, item = scene
    original = verify(item, actor).receipt_verification_result
    prepare(item, actor)

    def provider(**kw):
        if changed == "unavailable":
            return None
        return replace(
            synthetic_fee(**kw),
            **{
                "version": {"version": "fixture-v2"},
                "applicability": {"applicable_through": date(2090, 1, 1)},
                "amount": {"expected_amount": Decimal("100.00")},
            }[changed],
        )

    monkeypatch.setattr(fees, "resolve_approved_fee", provider)
    with pytest.raises(inspections.ReceiptBlocked):
        issue(item, actor)
    original.refresh_from_db()
    assert original.invalidated_at is None  # history never reinterpreted
    assert not FeedbackOpportunity.objects.exists()
    if changed in {"version", "applicability"}:
        replacement = verify(item, actor).receipt_verification_result
        item.refresh_from_db()
        assert item.status == "REQUESTED"
        original.refresh_from_db()
        assert original.invalidation_reason == "POLICY_CHANGED"
        assert replacement.assignment_id == original.assignment_id
        prepare(item, actor)
        assert issue(item, actor).issued_receipt_verification_id == replacement.pk


@pytest.mark.parametrize(
    "field",
    [
        "expected_resource_version",
        "expected_receipt_revision",
        "expected_receipt_verification",
        "expected_preparation_version",
    ],
)
def test_active_issue_requires_each_review_token(scene, field):
    actor, item = scene
    verify(item, actor)
    prepare(item, actor)
    with pytest.raises(GoodMoralConflict):
        issue(item, actor, **{field: None})
    item.refresh_from_db()
    assert item.status == "READY_FOR_ISSUANCE"


@pytest.mark.parametrize("action", ["verification", "invalidation", "preparation", "issuance"])
def test_audit_failure_rolls_back_attestation_transition_and_side_effects(
    scene, monkeypatch, action
):
    actor, item = scene
    if action != "verification":
        verify(item, actor)
    if action == "issuance":
        prepare(item, actor)
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    count = AuditEvent.objects.count()

    def fail(**kwargs):
        raise RuntimeError("Synthetic Audit failure")

    module = (
        inspections
        if action in {"verification", "invalidation"}
        else __import__("compass.good_moral.services", fromlist=["record_event"])
    )
    monkeypatch.setattr(module, "record_event", fail)
    with pytest.raises(RuntimeError):
        if action == "verification":
            verify(item, actor)
        elif action == "invalidation":
            edit(item, actor, {"official_receipt_number": "OR-ROLLBACK"})
        elif action == "preparation":
            prepare(item, actor)
        else:
            issue(item, actor)
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    assert AuditEvent.objects.count() == count
    assert not FeedbackOpportunity.objects.exists()
    assert not Verification.objects.filter(invalidated_at__isnull=False).exists()
    assert Verification.objects.count() == (0 if action == "verification" else 1)


@pytest.mark.parametrize("mode", ["DORMANT", "FENCED"])
def test_no_inspection_bypasses_writer_state(approved, mode):
    from compass.good_moral.legacy_receipts import begin_import

    sync_policy()
    actor = person("inspector", "COUNSELOR")
    grant(actor)
    item = request_for()
    if mode == "FENCED":
        begin_import(batch_id=uuid4(), evidence_reference="synthetic")
    with pytest.raises(receipts.ReceiptCutoverRequired):
        inspections.verify_receipt(**intent(item, actor, assignment_id=uuid4()))
    assert not Verification.objects.exists()


def test_default_provider_has_no_approval_or_invented_effective_date():
    assert fees.resolve_approved_fee(item=None, assignment=None) is None
    assert fees.TEAM_REPORTED_AMOUNT == Decimal("80.00")
    assert not hasattr(fees, "EFFECTIVE_FROM")


@pytest.mark.parametrize(
    "mutation",
    [
        "delete",
        "actor",
        "timestamp",
        "assignment",
        "method",
        "policy",
        "fake_invalidation",
        "prepared_owner",
        "issued_pair",
    ],
)
def test_direct_database_rewrite_and_reference_bypass_refused(scene, mutation):
    actor, item = scene
    v = verify(item, actor).receipt_verification_result
    with pytest.raises(IntegrityError), transaction.atomic():
        if mutation == "delete":
            Verification.objects.filter(pk=v.pk).delete()
        elif mutation == "prepared_owner":
            other = request_for()
            GoodMoralRequest.objects.filter(pk=other.pk).update(prepared_receipt_verification=v)
        elif mutation == "issued_pair":
            GoodMoralRequest.objects.filter(pk=item.pk).update(
                issued_receipt_assignment=v.assignment
            )
        else:
            values = {
                "actor": {"verified_by": item.student},
                "timestamp": {"verified_at": timezone.now()},
                "assignment": {"assignment_id": uuid4()},
                "method": {"method": "CASHIER_CONFIRMED"},
                "policy": {"expected_amount": Decimal("75")},
                "fake_invalidation": {
                    "invalidated_at": timezone.now(),
                    "invalidated_by": actor,
                    "invalidation_reason": "CANCELLED",
                },
            }[mutation]
            Verification.objects.filter(pk=v.pk).update(**values)
    v.refresh_from_db()
    assert v.invalidated_at is None


def test_api_explicit_action_and_student_projection(scene):
    actor, item = scene
    client = auth_client(actor)
    response = client.get(f"/api/v1/good-moral/requests/{item.pk}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["receipt_inspection"]["can_verify"]
    assert not detail["actions"]["can_prepare"]
    payload = {
        "expected_resource_version": detail["actions"]["request_version"],
        "assignment_id": detail["receipt_identity"]["revision_id"],
        "operation_id": str(uuid4()),
        "method": inspections.METHOD,
    }
    response = client.post(
        f"/api/v1/good-moral/requests/{item.pk}/receipt/verify",
        payload,
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 200, response.content
    assert response.json()["receipt_inspection"]["status"] == "VERIFIED"
    assert response.json()["actions"]["can_prepare"]
    student = auth_client(item.student)
    detail = student.get(f"/api/v1/good-moral/me/{item.pk}")
    assert detail.status_code == 200, detail.content
    assert "receipt_inspection" not in detail.json() and "receipt_identity" not in detail.json()
    payload["verified_by_id"] = str(item.student_id)
    assert (
        client.post(
            f"/api/v1/good-moral/requests/{item.pk}/receipt/verify",
            payload,
            content_type="application/json",
            **csrf(client),
        ).status_code
        == 422
    )
    edit(item, actor, {"official_receipt_amount": Decimal("75.00")})
    response = client.get(f"/api/v1/good-moral/requests/{item.pk}")
    inspection = response.json()["receipt_inspection"]
    assert inspection["blocker"] == "good_moral_receipt_fee_mismatch"
    assert Decimal(str(inspection["expected_amount"])) == Decimal("80.00")
    assert not inspection["can_verify"] and not response.json()["actions"]["can_prepare"]


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_legacy_ready_requires_real_inspection_and_deliberate_repreparation(approved, variant):
    sync_policy()
    actor = person("legacy-reviewer", "COUNSELOR")
    grant(actor)
    item = request_for(
        variant=variant,
        official_receipt_number="OR-READY",
        official_receipt_date=date(2020, 1, 1),
        official_receipt_amount=Decimal("80.00"),
    )
    prepare_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor))
    item.refresh_from_db()
    old_prepared_at = item.prepared_at
    activate()
    with pytest.raises(inspections.ReceiptBlocked) as caught:
        issue(item, actor)
    assert caught.value.code == "good_moral_receipt_unverified"
    assert not Verification.objects.exists()
    verify(item, actor)
    item.refresh_from_db()
    assert item.status == "REQUESTED" and item.prepared_at is None
    prepare(item, actor)
    assert item.prepared_at != old_prepared_at
    assert issue(item, actor).status == "ISSUED"


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_new_revision_can_be_reinspected_and_prepared(scene, variant):
    actor, original = scene
    item = request_for(variant=variant)
    edit(
        item,
        actor,
        {
            "official_receipt_number": f"NEW-{variant}",
            "official_receipt_date": date(2020, 1, 1),
            "official_receipt_amount": Decimal("80.00"),
        },
    )
    first = verify(item, actor).receipt_verification_result
    prepare(item, actor)
    edit(item, actor, {"official_receipt_date": date(2020, 1, 2)})
    with pytest.raises(inspections.ReceiptBlocked):
        prepare(item, actor)
    second = verify(item, actor).receipt_verification_result
    assert second.pk != first.pk and second.assignment_id != first.assignment_id
    prepare(item, actor)
    assert issue(item, actor).issued_receipt_verification_id == second.pk
    assert not Verification.objects.filter(assignment__request=original).exists()


@pytest.mark.parametrize("condition", ["ambiguous", "disputed", "wrong_owner", "superseded"])
def test_identity_eligibility_cannot_be_bypassed(scene, condition):
    from django.db import connection

    actor, item = scene
    original = receipts.latest_revision(item)
    if condition == "superseded":
        args = intent(item, actor)
        edit(item, actor, {"official_receipt_number": "OR-REPLACEMENT"})
        args["expected_resource_version"] = GoodMoralRequest.objects.get(
            pk=item.pk
        ).updated_at.isoformat()
        with pytest.raises(receipts.ReceiptChanged):
            inspections.verify_receipt(**args)
    else:
        # Protected synthetic fixture for future reconciliation states. No runtime bypass exists.
        identity = original.identity
        state = (
            "LEGACY_AMBIGUOUS"
            if condition == "ambiguous"
            else "DISPUTED"
            if condition == "disputed"
            else "BOUND"
        )
        owner = (
            None
            if condition == "ambiguous"
            else request_for().pk
            if condition == "wrong_owner"
            else item.pk
        )
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE good_moral_goodmoralreceiptidentity "
                "DISABLE TRIGGER gm_receipt_identity_guard"
            )
            cursor.execute(
                "UPDATE good_moral_goodmoralreceiptidentity "
                "SET state=%s, bound_request_id=%s WHERE id=%s",
                [state, owner, identity.pk],
            )
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute(
                "ALTER TABLE good_moral_goodmoralreceiptidentity "
                "ENABLE TRIGGER gm_receipt_identity_guard"
            )
        with pytest.raises(inspections.ReceiptBlocked) as caught:
            verify(item, actor)
        assert caught.value.code == "good_moral_receipt_conflict"
    assert not Verification.objects.exists()


def test_actual_legacy_duplicate_identity_remains_ambiguous(approved):
    sync_policy()
    actor = person("inspector", "COUNSELOR")
    grant(actor)
    first = request_for(
        official_receipt_number="DUPLICATE",
        official_receipt_date=date(2020, 1, 1),
        official_receipt_amount=80,
    )
    request_for(
        official_receipt_number="duplicate",
        official_receipt_date=date(2020, 1, 1),
        official_receipt_amount=80,
    )
    activate()
    with pytest.raises(inspections.ReceiptBlocked):
        verify(first, actor)
    assert receipts.latest_revision(first).identity.bound_request_id is None
    assert not Verification.objects.exists()


@pytest.mark.parametrize(
    "illegal",
    [
        "duplicate",
        "wrong_revision",
        "no_approval",
        "invalid_method",
        "invalid_actor",
        "fee_mismatch",
    ],
)
def test_direct_insert_inspection_guards(scene, illegal):
    actor, item = scene
    first = verify(item, actor).receipt_verification_result
    values = {
        name: getattr(first, name)
        for name in [
            "assignment",
            "verified_by",
            "method",
            "policy_id",
            "policy_version",
            "expected_amount",
            "currency",
            "fee_decision",
            "fingerprint",
        ]
    }
    values["operation_id"] = uuid4()
    if illegal == "wrong_revision":
        values["assignment"] = receipts.latest_revision(request_for())  # no claim, NOT NULL refuses
    elif illegal == "no_approval":
        values["fee_decision"] = {**first.fee_decision, "status": "TEAM_REPORTED"}
    elif illegal == "invalid_method":
        values["method"] = "CASHIER_CONFIRMED"
    elif illegal == "invalid_actor":
        values["verified_by_id"] = uuid4()
        del values["verified_by"]
    elif illegal == "fee_mismatch":
        values["expected_amount"] = Decimal("100.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        Verification.objects.create(**values)
    assert Verification.objects.count() == 1


def test_issued_evidence_remains_historical_when_policy_unavailable(scene, monkeypatch):
    actor, item = scene
    v = verify(item, actor).receipt_verification_result
    prepare(item, actor)
    issued = issue(item, actor)
    monkeypatch.setattr(fees, "resolve_approved_fee", lambda **kw: None)
    assert inspections.operational_status(issued, actor)["status"] == "VERIFIED"
    assert (
        issue_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor)).pk
        == item.pk
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        GoodMoralRequest.objects.filter(pk=item.pk).update(
            issued_receipt_verification=None, issued_receipt_assignment=None
        )
    v.refresh_from_db()
    assert v.invalidated_at is None
