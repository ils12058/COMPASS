"""FORM-CORR-1: encrypted Individual Inventory correction targets on existing reopen events."""

from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO, StringIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from pypdf import PdfReader

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.common.json_logging import JsonFormatter
from compass.inventory import api as inventory_api
from compass.inventory import confidential_content as content
from compass.inventory.correction_targets import (
    EXCLUDED_ANSWERS,
    MAX_CORRECTION_TARGETS,
    TARGET_COVERAGE,
    InventoryCorrectionTarget,
    normalize_correction_targets,
)
from compass.inventory.errors import InvalidInventoryInput
from compass.inventory.models import FamilyMemberKind, InventoryReopenEvent
from compass.inventory.services import (
    InventoryNotFound,
    InventoryNotPermitted,
    reopen_inventory_for_correction,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import Notification
from compass.notifications.push_policy import push_body_for
from tests.inventory_test_helpers import (
    ensure_inventory_form_revision,
    minimum_normalized_inventory_values,
)
from tests.test_inventory_counselor_review import (
    affiliate,
    auth_client,
    configure_year,
    context,
    csrf,
    make_head,
    make_org,
    make_user,
    submit_inventory,
    sync_policy,
)

T = InventoryCorrectionTarget
K1, K2 = (base64.urlsafe_b64encode(bytes([n]) * 32).decode() for n in (131, 132))
REASON = "PRIVATE-CORRECTION-REASON-SENTINEL"
# Sensitive-looking selections used to prove targets never leave the authorized read path.
SELECTED = [
    T.HEALTH_ILLNESS_THIS_YEAR.value,
    T.FAMILY_FOUR_PS_STATUS.value,
    T.PERSONAL_DATE_OF_BIRTH.value,
    T.HEALTH_ILLNESS_THIS_YEAR.value,
    T.BACKGROUND_SIBLINGS.value,
    T.SECTION_PLANS.value,
]
CANONICAL = [
    T.PERSONAL_DATE_OF_BIRTH.value,
    T.FAMILY_FOUR_PS_STATUS.value,
    T.BACKGROUND_SIBLINGS.value,
    T.HEALTH_ILLNESS_THIS_YEAR.value,
    T.SECTION_PLANS.value,
]
EXPECTED_SECTIONS = {
    "section.personal",
    "section.family",
    "section.background",
    "section.health",
    "section.education",
    "section.interests",
    "section.organizations",
    "section.plans",
}


@pytest.fixture(autouse=True)
def ring(settings):
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


@pytest.fixture
def world(db):
    sync_policy()
    ensure_inventory_form_revision()
    admin = make_user("corr-admin@example.edu", "IT_ADMIN")
    counselor = make_user("corr-counselor@example.edu", "COUNSELOR")
    outsider = make_user("corr-outside-counselor@example.edu", "COUNSELOR")
    student = make_user("corr-student@example.edu", "STUDENT", institutional_id="CORR-0001")
    _, college, program = make_org("CORR")
    _, other_college, _ = make_org("CORR-OTHER")
    affiliate(student, college, counselor)
    affiliate(make_user("corr-other-student@example.edu", "STUDENT"), other_college, outsider)
    configure_year(admin)
    item = submit_inventory(student=student, program=program)
    return {
        "admin": admin,
        "counselor": counselor,
        "outsider": outsider,
        "student": student,
        "program": program,
        "item": item,
    }


def reopen_api(user, item, body):
    client = auth_client(user)
    return client.post(
        f"/api/v1/inventory/records/{item.pk}/reopen",
        data=json.dumps(body),
        content_type="application/json",
        **csrf(client),
    )


def raw_event(pk):
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT * FROM "{InventoryReopenEvent._meta.db_table}" WHERE id = %s', [str(pk)]
        )
        return dict(zip([col.name for col in cursor.description], cursor.fetchone(), strict=True))


def resubmit(world):
    replace_current_inventory(
        student=world["student"],
        values=minimum_normalized_inventory_values(program_id=world["program"].pk),
    )
    return submit_current_inventory(student=world["student"], context=context(world["student"]))


def assert_no_target_or_reason(text, codes=CANONICAL):
    assert REASON not in text
    assert all(code not in text for code in codes)


# --- Catalog ---------------------------------------------------------------------------------


def test_catalog_is_unique_well_formed_and_never_positional():
    values = [target.value for target in T]
    assert len(values) == len(set(values)) == 148
    assert {value for value in values if value.startswith("section.")} == EXPECTED_SECTIONS
    for value in values:
        # Lowercase dotted names only: no digits, row ids, answer values, or element ids.
        assert re.fullmatch(r"[a-z_]+(\.[a-z_]+){1,2}", value), value
    assert not any(value.startswith("background.siblings.") for value in values)
    assert not any(
        value.startswith(("organizations.inside_school.", "organizations.outside_school."))
        for value in values
    )
    assert "personal.student_number" not in values
    assert "education.course_currently_enrolled" not in values


def _editable_answer_keys() -> set[str]:
    payload = inventory_api.InventoryPayload.model_fields
    collections = {
        "family_members",
        "siblings",
        "education_entries",
        "organization_memberships",
        "transportation_entries",
        "geographic_locations",
        "support_profile",
    }
    keys = set(payload) - collections
    keys |= {f"support_profile.{name}" for name in inventory_api.SupportProfilePayload.model_fields}
    keys |= {
        f"family_members.{kind}.{name}"
        for kind in FamilyMemberKind.values
        for name in inventory_api.FamilyMemberPayload.model_fields
        if name != "kind"
    }
    keys |= {f"siblings.{name}" for name in inventory_api.SiblingPayload.model_fields}
    keys |= {
        f"education_entries.{level}.{name}"
        for level in inventory_api.EducationLevelValue
        for name in inventory_api.EducationEntryPayload.model_fields
        if name != "level"
    }
    keys |= {
        f"organization_memberships.{scope}.{name}"
        for scope in inventory_api.OrganizationScopeValue
        for name in inventory_api.OrganizationMembershipPayload.model_fields
        if name != "scope"
    }
    keys.add("transportation_entries.mode")
    keys |= {
        f"transportation_entries.{mode}.{name}"
        for mode in inventory_api.TransportationModeValue
        for name in inventory_api.TransportationEntryPayload.model_fields
        if name != "mode"
    }
    keys |= {
        f"geographic_locations.{kind}.{name}"
        for kind in inventory_api.GeographicLocationKindValue
        for name in inventory_api.GeographicLocationPayload.model_fields
        if name != "kind"
    }
    return keys


def test_every_editable_answer_maps_to_exactly_one_target_or_an_explicit_exclusion():
    assert set(TARGET_COVERAGE) == set(T)
    covered: dict[str, InventoryCorrectionTarget] = {}
    for target, keys in TARGET_COVERAGE.items():
        if target.value.startswith("section."):
            assert keys == frozenset()
            continue
        assert keys, target
        for key in keys:
            assert key not in covered, (key, covered.get(key), target)
            covered[key] = target
    universe = _editable_answer_keys()
    assert set(EXCLUDED_ANSWERS) == {"student_number", "course_currently_enrolled"}
    assert not set(EXCLUDED_ANSWERS) & set(covered)
    assert set(covered) | set(EXCLUDED_ANSWERS) == universe


def test_normalization_dedupes_orders_bounds_and_never_echoes_input():
    assert normalize_correction_targets(None) == ()
    assert normalize_correction_targets([]) == ()
    assert [target.value for target in normalize_correction_targets(SELECTED)] == CANONICAL
    assert normalize_correction_targets(tuple(reversed(SELECTED))) == normalize_correction_targets(
        SELECTED
    )
    for bad in (["personal.secret-unknown-code"], [1], [None], ["siblings.0.name"]):
        with pytest.raises(InvalidInventoryInput) as caught:
            normalize_correction_targets(bad)
        assert "secret-unknown" not in str(caught.value) and "siblings.0" not in str(caught.value)
    with pytest.raises(InvalidInventoryInput):
        normalize_correction_targets("personal.nickname")
    many = [target.value for target in T][: MAX_CORRECTION_TARGETS + 1]
    with pytest.raises(InvalidInventoryInput, match="at most 30"):
        normalize_correction_targets(many)
    # The bound counts submitted selections, before repeats are dropped.
    with pytest.raises(InvalidInventoryInput, match="at most 30"):
        normalize_correction_targets([T.PERSONAL_SEX.value] * 31)
    assert len(normalize_correction_targets(many[:MAX_CORRECTION_TARGETS])) == 30


# --- Lifecycle and API ------------------------------------------------------------------------


def test_counselor_reopens_with_targets_and_student_reads_them_inside_latest_correction(world):
    item = world["item"]
    response = reopen_api(world["counselor"], item, {"reason": REASON, "targets": SELECTED})
    assert response.status_code == 200
    assert response.json()["correction_pending"] is True
    assert_no_target_or_reason(response.content.decode())

    event = InventoryReopenEvent.objects.get(inventory=item)
    stored = raw_event(event.pk)
    assert stored["targets_ciphertext"] and stored["reason_ciphertext"]
    assert_no_target_or_reason(json.dumps(stored, default=str))
    assert list(content.read_reopen_targets(event)) == CANONICAL

    client = auth_client(world["student"])
    status = client.get("/api/v1/inventory/me/status").json()
    current = client.get("/api/v1/inventory/me/current").json()
    detail = client.get(f"/api/v1/inventory/me/{item.pk}").json()
    for body in (status, current, detail):
        assert body["latest_correction"] == {
            "requested_at": body["latest_correction"]["requested_at"],
            "message": REASON,
            "targets": CANONICAL,
        }
        assert "targets" not in body
    history = client.get("/api/v1/inventory/me/history").json()["items"]
    assert_no_target_or_reason(json.dumps(history))

    # The editor sends the read response back without its envelope fields. Nesting targets in
    # latest_correction keeps that round trip valid under the strict update schema.
    envelope = {
        "id",
        "academic_year",
        "status",
        "program",
        "form_revision",
        "submitted_at",
        "first_submitted_at",
        "last_submitted_at",
        "correction_pending",
        "latest_correction",
    }
    payload = {key: value for key, value in current.items() if key not in envelope}
    saved = client.put(
        "/api/v1/inventory/me/current",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )
    assert saved.status_code == 200, saved.json()
    assert saved.json()["latest_correction"]["targets"] == CANONICAL


def test_reason_only_requests_still_work_and_store_no_target_ciphertext(world):
    item = world["item"]
    response = reopen_api(world["counselor"], item, {"reason": REASON})
    assert response.status_code == 200
    event = InventoryReopenEvent.objects.get(inventory=item)
    assert raw_event(event.pk)["targets_ciphertext"] == ""
    body = auth_client(world["student"]).get("/api/v1/inventory/me/status").json()
    assert body["latest_correction"]["message"] == REASON
    assert body["latest_correction"]["targets"] == []


def test_empty_target_column_needs_no_decryption(world, monkeypatch):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON, "targets": []})

    def fail(*args, **kwargs):
        raise AssertionError("an empty target column must not be decrypted")

    monkeypatch.setattr(content, "decrypt_bound_json", fail)
    assert content.read_reopen_targets(InventoryReopenEvent.objects.get(inventory=item)) == ()


@pytest.mark.parametrize(
    ("targets", "location"),
    [
        (["personal.secret-unknown-code"], "targets"),
        (["personal.student_number"], "targets"),
        ([value.value for value in T][:31], "targets"),
        ("personal.nickname", "targets"),
    ],
)
def test_invalid_targets_are_rejected_before_any_reopen_side_effect(world, targets, location):
    item = world["item"]
    audits, notices = AuditEvent.objects.count(), Notification.objects.count()
    response = reopen_api(world["counselor"], item, {"reason": REASON, "targets": targets})
    assert response.status_code == 422
    body = response.content.decode()
    assert response.json()["error"]["code"] == "validation_error"
    assert location in body and REASON not in body and "secret-unknown" not in body
    item.refresh_from_db()
    assert item.submitted_at is not None
    assert not InventoryReopenEvent.objects.filter(inventory=item).exists()
    assert (AuditEvent.objects.count(), Notification.objects.count()) == (audits, notices)


def test_service_rejects_unknown_targets_inside_the_transaction_without_partial_event(world):
    item = world["item"]
    with pytest.raises(InvalidInventoryInput) as caught:
        reopen_inventory_for_correction(
            actor=world["counselor"],
            inventory_id=item.pk,
            reason=REASON,
            targets=["personal.secret-unknown-code"],
            context=context(world["counselor"]),
        )
    assert "secret-unknown" not in str(caught.value) and REASON not in str(caught.value)
    item.refresh_from_db()
    assert item.submitted_at is not None
    assert not InventoryReopenEvent.objects.exists()


def test_reopen_authorization_and_scope_are_unchanged(world):
    item = world["item"]
    body = {"reason": REASON, "targets": [T.PERSONAL_NICKNAME.value]}
    staff = make_user("corr-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    for actor, expected in ((world["student"], 403), (staff, 403), (world["admin"], 403)):
        response = reopen_api(actor, item, body)
        assert response.status_code == expected
        assert_no_target_or_reason(response.content.decode(), [T.PERSONAL_NICKNAME.value])

    out_of_scope = reopen_api(world["outsider"], item, body)
    assert out_of_scope.status_code == 404
    with pytest.raises(InventoryNotFound):
        reopen_inventory_for_correction(
            actor=world["outsider"],
            inventory_id=item.pk,
            reason=REASON,
            targets=["personal.secret-unknown-code"],
            context=context(world["outsider"]),
        )

    revoked = make_user("corr-revoked-counselor@example.edu", "COUNSELOR")
    UserCapabilityOverride.objects.create(
        user=revoked,
        capability=Capability.objects.get(code="inventory.reopen"),
        effect="REVOKE",
        reason="synthetic",
    )
    assert reopen_api(revoked, item, body).status_code == 403
    with pytest.raises(InventoryNotPermitted):
        reopen_inventory_for_correction(
            actor=revoked,
            inventory_id=item.pk,
            reason=REASON,
            targets=[T.PERSONAL_NICKNAME.value],
            context=context(revoked),
        )
    assert not InventoryReopenEvent.objects.exists()

    head = make_head("corr-head@example.edu")
    assert reopen_api(head, item, body).status_code == 200


def test_resubmission_ends_pending_targets_and_adds_no_history_disclosure(world):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON, "targets": SELECTED})
    resubmit(world)

    student = auth_client(world["student"])
    for path in ("/api/v1/inventory/me/status", "/api/v1/inventory/me/current"):
        body = student.get(path).json()
        assert body["correction_pending"] is False and body["latest_correction"] is None
        assert_no_target_or_reason(json.dumps(body))
    counselor = auth_client(world["counselor"])
    for path in (
        f"/api/v1/inventory/records/{item.pk}",
        f"/api/v1/inventory/students/{world['student'].pk}/history",
        "/api/v1/inventory/students",
    ):
        response = counselor.get(path)
        assert response.status_code == 200
        assert_no_target_or_reason(response.content.decode())

    # A later reason-only request is pending on its own; earlier targets are not carried over.
    reopen_api(world["counselor"], item, {"reason": "Second request"})
    body = student.get("/api/v1/inventory/me/status").json()
    assert body["latest_correction"]["message"] == "Second request"
    assert body["latest_correction"]["targets"] == []
    assert InventoryReopenEvent.objects.filter(inventory=item).count() == 2


def test_unknown_stored_codes_are_omitted_without_rewriting_ciphertext(world, caplog):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON})
    event = InventoryReopenEvent.objects.get(inventory=item)
    future = "personal.future_question"
    content.write_reopen_targets(event, [T.PERSONAL_NICKNAME.value, future])
    event.save(update_fields=["targets_ciphertext"])
    before = raw_event(event.pk)
    with caplog.at_level(logging.WARNING, logger="compass.inventory.api"):
        body = auth_client(world["student"]).get("/api/v1/inventory/me/status").json()
    assert body["latest_correction"]["targets"] == [T.PERSONAL_NICKNAME.value]
    assert raw_event(event.pk) == before
    formatted = [JsonFormatter().format(record) for record in caplog.records]
    assert any("inventory_correction_targets_omitted" in line for line in formatted)
    assert all(future not in line and T.PERSONAL_NICKNAME.value not in line for line in formatted)


def test_unreadable_target_ciphertext_fails_closed_with_the_existing_generic_error(world):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON, "targets": SELECTED})
    InventoryReopenEvent.objects.filter(inventory=item).update(
        targets_ciphertext="private-broken-token"
    )
    response = auth_client(world["student"]).get("/api/v1/inventory/me/status")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "inventory_confidential_content_unavailable"
    assert "private-broken-token" not in response.content.decode()
    assert_no_target_or_reason(response.content.decode())


# --- Encryption ---------------------------------------------------------------------------------


def _event(**values):
    event = InventoryReopenEvent(id=uuid4(), inventory_id=uuid4(), **values)
    content.write_confidential_content(event, {"reason": REASON})
    return event


def test_target_envelope_is_separate_bound_and_leaves_the_reason_envelope_unchanged():
    event = _event()
    reason_token = event.reason_ciphertext
    content.write_reopen_targets(event, CANONICAL)
    envelope = json.loads(Fernet(K1).decrypt(event.targets_ciphertext.encode()))
    assert envelope == {
        "schema_version": 1,
        "inventory_id": str(event.inventory_id),
        "reopen_event_id": str(event.pk),
        "content": "correction_targets",
        "payload": {"targets": CANONICAL},
    }
    reason_envelope = json.loads(Fernet(K1).decrypt(reason_token.encode()))
    assert set(reason_envelope) == {"schema_version", "inventory_id", "reopen_event_id", "payload"}
    assert reason_envelope["payload"] == {"reason": REASON}
    assert event.reason_ciphertext == reason_token
    assert content.read_reopen_reason(event) == REASON


def test_target_ciphertext_cannot_be_transplanted_or_swapped():
    source = _event()
    content.write_reopen_targets(source, CANONICAL)

    def expect(event, reader, reason):
        with pytest.raises(content.InventoryConfidentialContentUnavailable) as caught:
            reader(event)
        assert caught.value.reason == reason
        assert "PRIVATE" not in str(caught.value)

    other_event = _event(targets_ciphertext=source.targets_ciphertext)
    other_event.inventory_id = source.inventory_id
    expect(other_event, content.read_reopen_targets, "binding_mismatch")
    other_record = _event(targets_ciphertext=source.targets_ciphertext)
    other_record.id = source.pk
    expect(other_record, content.read_reopen_targets, "binding_mismatch")
    swapped = _event()
    swapped.id, swapped.inventory_id = source.pk, source.inventory_id
    swapped.targets_ciphertext = source.reason_ciphertext
    expect(swapped, content.read_reopen_targets, "malformed")
    swapped.reason_ciphertext = source.targets_ciphertext
    expect(swapped, content.read_reopen_reason, "malformed")


@pytest.mark.parametrize(
    "payload",
    [
        {"targets": []},
        {"targets": ["personal.nickname", "personal.nickname"]},
        {"targets": [1]},
        {"targets": ["has space"]},
        {"targets": "personal.nickname"},
        {"targets": ["personal.nickname"], "extra": True},
        {"reason": REASON},
    ],
)
def test_malformed_target_payloads_fail_safely(payload):
    from compass.confidential_data.crypto import encrypt_bound_json

    event = _event()
    event.targets_ciphertext = encrypt_bound_json(
        keyring=(K1,),
        schema_version=1,
        binding=content._targets_binding(event),
        payload=payload,
    )
    with pytest.raises(content.InventoryConfidentialContentUnavailable) as caught:
        content.read_reopen_targets(event)
    assert caught.value.reason == "malformed"
    assert caught.value.family == content.TARGETS_FAMILY


def test_empty_selection_writes_no_ciphertext():
    event = _event()
    content.write_reopen_targets(event, [])
    assert event.targets_ciphertext == ""


# --- Rotation ------------------------------------------------------------------------------------


def rotate(**options):
    out, err = StringIO(), StringIO()
    call_command("rotate_inventory_confidential_content", stdout=out, stderr=err, **options)
    return out.getvalue(), err.getvalue()


def test_rotation_rewraps_targets_and_preserves_plaintext_binding_and_timestamp(world, settings):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON, "targets": SELECTED})
    resubmit(world)
    reopen_api(world["counselor"], item, {"reason": "Reason only"})
    with_targets, without_targets = InventoryReopenEvent.objects.order_by("reopened_at")
    before = raw_event(with_targets.pk)["targets_ciphertext"]

    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    out, err = rotate(dry_run=True, batch_size=1)
    assert (
        "InventoryReopenEventTargets: scanned 2; empty 1; current 0; needing rotation 1; "
        "failures 0" in out
    )
    assert not err and raw_event(with_targets.pk)["targets_ciphertext"] == before
    out, err = rotate(batch_size=1)
    assert "InventoryReopenEventTargets: scanned 2; empty 1; current 0; rotated 1" in out
    after = raw_event(with_targets.pk)["targets_ciphertext"]
    assert after != before
    assert Fernet(K1).decrypt(before.encode()) == Fernet(K2).decrypt(after.encode())
    assert Fernet(K1).extract_timestamp(before.encode()) == Fernet(K2).extract_timestamp(
        after.encode()
    )
    assert list(content.read_reopen_targets(InventoryReopenEvent.objects.get(pk=with_targets.pk)))
    assert raw_event(without_targets.pk)["targets_ciphertext"] == ""
    out, _ = rotate(batch_size=1)
    assert "InventoryReopenEventTargets: scanned 2; empty 1; current 1; rotated 0" in out
    assert_no_target_or_reason(out)


def test_rotation_reports_unreadable_targets_and_rotates_the_rest(world, settings):
    item = world["item"]
    reopen_api(world["counselor"], item, {"reason": REASON, "targets": SELECTED})
    valid = InventoryReopenEvent.objects.get(inventory=item)

    def extra_event(targets_ciphertext):
        # A readable reason, so only the target envelope is at fault.
        event = InventoryReopenEvent(
            inventory=item, reopened_by=world["counselor"], reopened_at=valid.reopened_at
        )
        content.write_confidential_content(event, {"reason": REASON})
        event.targets_ciphertext = targets_ciphertext
        event.save()
        return event

    corrupt = extra_event("private-broken-token")
    misbound = extra_event(valid.targets_ciphertext)
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_inventory_confidential_content", batch_size=1, stdout=out, stderr=err)
    assert "InventoryReopenEventTargets: scanned 3; empty 0; current 0; rotated 1; failures 2" in (
        out.getvalue()
    )
    unreadable = err.getvalue().splitlines()
    assert len(unreadable) == 2
    assert all("InventoryReopenEventTargets" in line for line in unreadable)
    assert {f"{corrupt.pk} (undecryptable)", f"{misbound.pk} (binding_mismatch)"} == {
        line.split("InventoryReopenEventTargets ", 1)[1] for line in unreadable
    }
    assert "private-broken-token" not in err.getvalue() + out.getvalue()
    assert_no_target_or_reason(err.getvalue() + out.getvalue())
    assert raw_event(corrupt.pk)["targets_ciphertext"] == "private-broken-token"
    assert raw_event(misbound.pk)["targets_ciphertext"] == valid.targets_ciphertext
    assert content.encrypted_with_primary_key(raw_event(valid.pk)["targets_ciphertext"])


# --- Migration -----------------------------------------------------------------------------------


# --- Privacy -------------------------------------------------------------------------------------


def test_targets_and_reason_never_reach_notifications_audit_actions_logs_or_pdfs(world, caplog):
    item = world["item"]
    with caplog.at_level(logging.DEBUG):
        assert (
            reopen_api(
                world["counselor"], item, {"reason": REASON, "targets": SELECTED}
            ).status_code
            == 200
        )
        student = auth_client(world["student"])
        assert student.get("/api/v1/inventory/me/status").status_code == 200
        actions = student.get("/api/v1/student-actions")
        assert actions.status_code == 200
        assert_no_target_or_reason(actions.content.decode())
    # Request logs from the reopen and the reads were captured, so the checks below are real.
    assert any(record.name == "compass.request" for record in caplog.records)
    for record in caplog.records:
        assert_no_target_or_reason(JsonFormatter().format(record))
        assert_no_target_or_reason(record.getMessage())

    notification = Notification.objects.get(
        recipient=world["student"], event_code="inventory.reopened"
    )
    assert_no_target_or_reason(f"{notification.title} {notification.message}")
    email = render_notification_email("inventory.reopened")
    assert_no_target_or_reason(str(email))
    assert_no_target_or_reason(str(push_body_for("inventory.reopened")))
    audit = AuditEvent.objects.get(action="inventory.reopened", target_id=str(item.pk))
    assert not any("target" in key for key in audit.metadata)
    assert_no_target_or_reason(
        json.dumps(list(AuditEvent.objects.values_list("metadata", flat=True)))
    )

    resubmit(world)
    pdf = student.get(f"/api/v1/inventory/me/{item.pk}/pdf")
    assert pdf.status_code == 200
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert_no_target_or_reason(text)
