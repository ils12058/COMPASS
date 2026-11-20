"""One-step Good Moral preparation: combined receipt + inspection + prepare, and defaults.

These tests exercise the combined ``prepare-with-receipt`` endpoint and the assisted
prefill projection. They assert that the single transaction keeps every guarantee of
the step-by-step path (Official Receipt uniqueness, attributable inspection, version
checks, idempotent replay, and one audit record per underlying action) and that a
failure in any step rolls back all of them.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.good_moral import fees
from compass.good_moral import receipt_identity as receipts
from compass.good_moral.models import (
    GoodMoralReceiptAssignment,
    GoodMoralReceiptMutation,
    GoodMoralReceiptVerification,
    GoodMoralStatus,
)
from tests.test_good_moral import (
    auth_client,
    csrf,
    issue_request,
    make_academic_year,
    make_inventory,
    make_placement,
    record_inspected_receipt,
    sync_policy,
)
from tests.test_good_moral_receipts import edit, person, request_for


def setup_scene(*, graduate=False):
    sync_policy()
    staff = person("onestep-goa", "GUIDANCE_OFFICE_ASSISTANT")
    counselor = person("onestep-counselor", "COUNSELOR")
    item = request_for(variant="GRADUATE" if graduate else "CURRENT_STUDENT")
    return staff, counselor, item


def one_step_payload(item, **overrides):
    item.refresh_from_db()
    revision = receipts.latest_revision(item)
    payload = {
        "expected_resource_version": item.updated_at.isoformat(),
        "expected_receipt_revision": str(revision.pk) if revision else None,
        "receipt_operation_id": str(uuid4()),
        "inspection_operation_id": str(uuid4()),
        "official_receipt_number": f"OR-ONE-{item.pk.int}",
        "official_receipt_date": "2026-01-15",
        "official_receipt_amount": "80.00",
        "diploma_tor_checked": True,
    }
    payload.update(overrides)
    return payload


def post_one_step(client, item, payload):
    return client.post(
        f"/api/v1/good-moral/requests/{item.pk}/prepare-with-receipt",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


def actions_for(item):
    return sorted(AuditEvent.objects.filter(target_id=item.pk).values_list("action", flat=True))


@pytest.mark.django_db
@pytest.mark.parametrize("graduate", [False, True])
def test_one_step_records_receipt_inspection_and_preparation(graduate):
    staff, counselor, item = setup_scene(graduate=graduate)
    payload = one_step_payload(item)
    response = post_one_step(auth_client(staff), item, payload)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "READY_FOR_ISSUANCE"
    assert body["prepared_by"]["id"] == str(staff.pk)
    assert body["receipt_inspection"]["status"] == "VERIFIED"
    assert body["official_receipt_number"] == payload["official_receipt_number"]
    # The Guidance Office Assistant prepares but never issues.
    assert body["actions"]["can_issue"] is False
    assert body["actions"]["can_prepare"] is False

    item.refresh_from_db()
    assert item.status == GoodMoralStatus.READY_FOR_ISSUANCE
    assert item.prepared_receipt_verification_id is not None
    actions = actions_for(item)
    assert actions.count("good_moral.request_updated") == 1
    assert actions.count("good_moral.receipt_assigned") == 1
    assert actions.count("good_moral.receipt_verified") == 1
    assert actions.count("good_moral.prepared") == 1
    if graduate:
        prepared = AuditEvent.objects.get(target_id=item.pk, action="good_moral.prepared")
        assert prepared.metadata["diploma_tor_checked"] is True
        assert prepared.metadata["document_checked_by_id"] == str(staff.pk)

    # The combined result is immediately issuable by an authorized Counselor.
    issued = issue_request(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )
    assert issued.status == GoodMoralStatus.ISSUED


@pytest.mark.django_db
def test_one_step_audit_trail_matches_the_separate_path():
    staff, _counselor, item = setup_scene()
    separate = request_for(variant="CURRENT_STUDENT")

    assert post_one_step(auth_client(staff), item, one_step_payload(item)).status_code == 200
    # Separate path: record + inspect the receipt, then prepare.
    separate = record_inspected_receipt(separate, staff)
    from compass.good_moral.services import prepare_request

    prepare_request(
        actor=staff,
        request_id=separate.pk,
        context=AuditContext.user(staff),
        expected_resource_version=separate.updated_at.isoformat(),
        diploma_tor_checked=True,
    )
    assert actions_for(item) == actions_for(separate)


@pytest.mark.django_db
def test_one_step_fills_receipt_date_and_amount_defaults():
    staff, _counselor, item = setup_scene()
    payload = one_step_payload(item)
    del payload["official_receipt_date"]
    del payload["official_receipt_amount"]
    response = post_one_step(auth_client(staff), item, payload)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["official_receipt_date"] == institution_today().isoformat()
    assert Decimal(str(body["official_receipt_amount"])) == fees.GOOD_MORAL_FEE
    assert Decimal(str(body["receipt_fee"]["expected_amount"])) == fees.GOOD_MORAL_FEE
    assert body["receipt_fee"]["currency"] == "PHP"


@pytest.mark.django_db
def test_one_step_duplicate_or_rolls_back_every_step():
    staff, _counselor, item = setup_scene()
    # Bind the number to the first request through the normal correction path.
    edit(
        item,
        staff,
        {
            "official_receipt_number": "OR-SHARED",
            "official_receipt_date": date(2026, 1, 15),
            "official_receipt_amount": Decimal("80.00"),
        },
    )
    other = request_for(variant="CURRENT_STUDENT")
    payload = one_step_payload(other, official_receipt_number="OR-SHARED")
    response = post_one_step(auth_client(staff), other, payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_receipt_conflict"

    other.refresh_from_db()
    assert other.status == GoodMoralStatus.REQUESTED
    assert other.official_receipt_number == ""
    assert other.prepared_at is None
    assert other.prepared_receipt_verification_id is None
    assert not GoodMoralReceiptAssignment.objects.filter(request=other).exists()
    assert not GoodMoralReceiptVerification.objects.filter(assignment__request=other).exists()
    assert not GoodMoralReceiptMutation.objects.filter(request=other).exists()
    # The combined operation added no audit rows; only the original creation remains.
    assert not (
        AuditEvent.objects.filter(target_id=other.pk)
        .exclude(action="good_moral.request_created")
        .exists()
    )


@pytest.mark.django_db
def test_one_step_rejects_a_stale_resource_version():
    staff, _counselor, item = setup_scene()
    payload = one_step_payload(item)
    # A concurrent clerical correction moves the request past the reviewed version.
    edit(item, staff, {"major_snapshot": "Changed Major"})
    response = post_one_step(auth_client(staff), item, payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_receipt_changed"
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.official_receipt_number == ""
    assert item.prepared_at is None


@pytest.mark.django_db
@pytest.mark.parametrize("graduate", [False, True])
def test_one_step_retry_is_idempotent(graduate):
    staff, _counselor, item = setup_scene(graduate=graduate)
    client = auth_client(staff)
    payload = one_step_payload(item)
    first = post_one_step(client, item, payload)
    assert first.status_code == 200, first.content

    item.refresh_from_db()
    version_after = item.updated_at.isoformat()
    prepared_at = item.prepared_at
    verification_id = item.prepared_receipt_verification_id
    audit_count = AuditEvent.objects.filter(target_id=item.pk).count()
    assignments = GoodMoralReceiptAssignment.objects.filter(request=item).count()
    verifications = GoodMoralReceiptVerification.objects.filter(assignment__request=item).count()

    # Replaying the exact same reviewed payload must not duplicate or move anything.
    second = post_one_step(client, item, payload)
    assert second.status_code == 200, second.content
    assert second.json()["status"] == "READY_FOR_ISSUANCE"
    item.refresh_from_db()
    assert item.updated_at.isoformat() == version_after
    assert item.prepared_at == prepared_at
    assert item.prepared_receipt_verification_id == verification_id
    assert AuditEvent.objects.filter(target_id=item.pk).count() == audit_count
    assert GoodMoralReceiptAssignment.objects.filter(request=item).count() == assignments
    assert (
        GoodMoralReceiptVerification.objects.filter(assignment__request=item).count()
        == verifications
    )


@pytest.mark.django_db
def test_one_step_graduate_document_check_required_rolls_back_receipt():
    staff, _counselor, item = setup_scene(graduate=True)
    payload = one_step_payload(item, diploma_tor_checked=False)
    response = post_one_step(auth_client(staff), item, payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "good_moral_graduate_document_check_required"
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.prepared_at is None
    # The receipt and inspection recorded earlier in the same transaction are undone.
    assert item.official_receipt_number == ""
    assert not GoodMoralReceiptAssignment.objects.filter(request=item).exists()
    assert not GoodMoralReceiptVerification.objects.filter(assignment__request=item).exists()


@pytest.mark.django_db
def test_one_step_counselor_may_also_prepare():
    _staff, counselor, item = setup_scene()
    response = post_one_step(auth_client(counselor), item, one_step_payload(item))
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "READY_FOR_ISSUANCE"
    assert body["prepared_by"]["id"] == str(counselor.pk)
    assert body["actions"]["can_issue"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["STUDENT", "IT_ADMIN"])
def test_one_step_denied_for_non_operational_roles(role):
    sync_policy()
    item = request_for(variant="CURRENT_STUDENT")
    actor = person("onestep-denied", role)
    response = post_one_step(auth_client(actor), item, one_step_payload(item))
    assert response.status_code == 403
    item.refresh_from_db()
    assert item.status == GoodMoralStatus.REQUESTED
    assert item.official_receipt_number == ""


@pytest.mark.django_db
def test_student_options_academic_context_prefills_records_and_leaves_gaps_empty():
    sync_policy()
    staff = person("options-goa", "GUIDANCE_OFFICE_ASSISTANT")
    year = make_academic_year()

    student = person("options-applicant")
    make_placement(student)
    make_inventory(
        student,
        year,
        course="Bachelor of Science in Information Systems",
        major="Information Systems",
        year_level=4,
    )
    bare = person("options-bare")
    make_placement(bare)  # A College placement but no submitted Inventory.
    graduate = person("options-grad")
    graduate.student_lifecycle_status = "GRADUATED"
    graduate.save(update_fields=["student_lifecycle_status", "updated_at"])

    client = auth_client(staff)

    def option_for(term, target):
        response = client.get("/api/v1/good-moral/student-options", {"search": term})
        assert response.status_code == 200, response.content
        return next(o for o in response.json()["items"] if o["id"] == str(target.pk))

    full = option_for("options-applicant", student)["academic_context"]
    assert full == {
        "year_level": "4th Year",
        "college": "CCMS College",
        "course": "Bachelor of Science in Information Systems",
        "major": "Information Systems",
        "academic_year": "2026-2027",
    }
    # Missing records leave the corresponding fact empty; the system never guesses.
    partial = option_for("options-bare", bare)["academic_context"]
    assert partial == {
        "year_level": None,
        "college": "CCMS College",
        "course": None,
        "major": None,
        "academic_year": None,
    }
    grad_option = option_for("options-grad", graduate)
    assert grad_option["variant"] == "GRADUATE"
    assert grad_option["academic_context"] is None


@pytest.mark.django_db
def test_operational_detail_exposes_configured_fee_before_any_receipt():
    staff, _counselor, item = setup_scene()
    response = auth_client(staff).get(f"/api/v1/good-moral/requests/{item.pk}")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["receipt_inspection"]["status"] == "MISSING"
    assert Decimal(str(body["receipt_fee"]["expected_amount"])) == fees.GOOD_MORAL_FEE
    assert body["receipt_fee"]["currency"] == "PHP"
