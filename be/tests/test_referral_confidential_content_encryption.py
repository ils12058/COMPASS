"""Synthetic ADR-081 evidence: envelopes, disclosure, migration and resumable rotation."""

from __future__ import annotations

import base64
import json
import runpy
from dataclasses import asdict, replace
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone
from pypdf import PdfReader

from compass.accounts.models import Capability, Designation, UserCapabilityOverride, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling.context_services import list_context_history
from compass.notifications.models import EmailDelivery, Notification
from compass.referrals import confidential_content as content
from compass.referrals.management.commands import rotate_referral_confidential_content as rotation
from compass.referrals.migrations import _referral_confidential_content_v1 as frozen
from compass.referrals.models import Referral, ReferralAction, ReferralActionType
from compass.referrals.services import (
    InvalidReferralInput,
    ReferralActionConflict,
    ensure_call_slip_action,
    record_action,
    update_status_note,
    void_referral,
)
from tests.test_referrals import (
    auth_client,
    context,
    create_for,
    csrf,
    ensure_referral_form_revision,
    make_head,
    make_user,
    setup_scope,
    sync_policy,
)

# Public fixed synthetic keys, never deployment keys or provider credentials.
K1, K2, K3, K4, K5, K6 = [
    base64.urlsafe_b64encode(c * 32).decode() for c in (b"1", b"2", b"3", b"4", b"5", b"6")
]
SETTING = content.KEYRING_SETTING
PAYLOAD = content.ReferralConfidentialContent(
    reason='PRIVATE-REFERRAL-REASON-SENTINEL\n café 🌱 雪 "quote" \\',
    referrer_name="PRIVATE-REFERRER-SENTINEL",
    status_note="PRIVATE-STATUS-SENTINEL",
    void_reason="PRIVATE-VOID-SENTINEL",
)
REMARKS = "PRIVATE-ACTION-REMARKS-SENTINEL 🌱"
BEFORE = [("referrals", "0002_void_provenance")]
BACKFILLED = [("referrals", "0003_encrypt_confidential_content")]
AFTER = [("referrals", "0004_remove_plaintext_confidential_content")]


@pytest.fixture(autouse=True)
def ring(settings):
    settings.REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


@pytest.fixture
def world(db):
    sync_policy()
    ensure_referral_form_revision()
    return make_head("crypto-head@example.edu"), make_user("crypto-student@example.edu", "STUDENT")


def create(world, key="referral", **kwargs):
    return create_for(
        world[0],
        world[1],
        key=key,
        fingerprint="a" * 64,
        reason=PAYLOAD.reason,
        referrer_name=PAYLOAD.referrer_name,
        **kwargs,
    )


def action(world, item, action_type=ReferralActionType.CALL_PARENT_GUARDIAN, remarks=REMARKS):
    return record_action(
        actor=world[0],
        referral_id=item.pk,
        action_type=action_type,
        occurred_at=timezone.now() - timedelta(minutes=1),
        remarks=remarks,
        context=context(world[0]),
    )


def raw(model, pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{model._meta.db_table}" WHERE id = %s', [pk])
        return dict(zip([c.name for c in cursor.description], cursor.fetchone(), strict=True))


def columns(model):
    with connection.cursor() as cursor:
        return {
            c.name
            for c in connection.introspection.get_table_description(cursor, model._meta.db_table)
        }


def transient(action_type=None, voided=False):
    if action_type:
        return ReferralAction(referral_id=uuid4(), action_type=action_type)
    return Referral(voided_at=timezone.now() if voided else None)


def token(item, payload, version=1):
    envelope = {"schema_version": version, **content._binding(item), "payload": payload}
    return Fernet(K1).encrypt(json.dumps(envelope, ensure_ascii=True).encode()).decode()


def read(item):
    return (
        content.read_referral_action_remarks(item)
        if isinstance(item, ReferralAction)
        else content.read_referral_confidential_content(item)
    )


def write(item, value):
    if isinstance(item, ReferralAction):
        content.write_referral_action_remarks(item, value)
        return item.remarks_ciphertext
    content.write_referral_confidential_content(item, value)
    return item.confidential_content_ciphertext


def set_token(item, value):
    if isinstance(item, ReferralAction):
        item.remarks_ciphertext = value
    else:
        item.confidential_content_ciphertext = value


def safe(error, *private):
    output = str(error) + repr(error) + repr(error.args)
    for value in (K1, K2, REMARKS, *asdict(PAYLOAD).values(), *private):
        assert value not in output
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__


@pytest.mark.parametrize("is_action", [False, True])
@pytest.mark.parametrize("text", ["normal", "", " \n ", 'café 雪 🌱\n "quotes" \\'])
def test_exact_round_trip_and_frozen_interoperability(is_action, text):
    item = transient(ReferralActionType.CALL_PARENT_GUARDIAN if is_action else None)
    value = text if is_action else replace(PAYLOAD, status_note=text, void_reason="")
    saved = write(item, value)
    assert read(item) == value
    payload = frozen.decrypt(frozen.keyring(), item, saved, action=is_action)
    migrated = frozen.encrypt(frozen.keyring(), item, payload, action=is_action)
    assert Fernet(K1).decrypt(saved.encode()) == Fernet(K1).decrypt(migrated.encode())
    set_token(item, migrated)
    assert read(item) == value


@pytest.mark.parametrize("field,limit", [*content.CONTENT_LIMITS.items(), ("remarks", 4000)])
@pytest.mark.parametrize("fault", ["NUL", "surrogate", "type", "long"])
def test_input_limits_and_postgresql_text_boundary(field, limit, fault):
    value = {
        "NUL": "private-input\x00",
        "surrogate": "private-input\ud800",
        "type": 3,
        "long": "x" * (limit + 1),
    }[fault]
    with pytest.raises(InvalidReferralInput) as caught:
        content.validate_text(value, label=field, max_length=limit)
    safe(caught.value, "private-input")
    assert content.validate_text("x" * limit, label=field, max_length=limit) == "x" * limit


@pytest.mark.parametrize(
    "voided,void_reason,valid",
    [
        (False, "", True),
        (False, "reason", False),
        (True, "reason", True),
        (True, "", False),
        (True, " \n ", False),
    ],
)
def test_void_reason_lifecycle_invariant(voided, void_reason, valid):
    item = transient(voided=voided)
    payload = replace(PAYLOAD, void_reason=void_reason)
    if valid:
        write(item, payload)
        assert read(item) == payload
    else:
        with pytest.raises(InvalidReferralInput):
            write(item, payload)
        set_token(item, token(item, asdict(payload)))
        with pytest.raises(
            content.ReferralConfidentialContentUnavailable, match="unavailable"
        ) as caught:
            read(item)
        assert caught.value.reason == "malformed"


@pytest.mark.parametrize("is_action", [False, True])
@pytest.mark.parametrize("fault", ["tamper", "truncate", "random", "non-ascii", "missing"])
def test_unverifiable_tokens_fail_safely(is_action, fault, caplog):
    item = transient(ReferralActionType.CALL_PARENT_GUARDIAN if is_action else None)
    original = write(item, REMARKS if is_action else replace(PAYLOAD, void_reason=""))
    value = {
        "tamper": original[:-12] + "AAAAAAAAAAAA",
        "truncate": original[:40],
        "random": "private-token",
        "non-ascii": "雪",
        "missing": None,
    }[fault]
    set_token(item, value)
    with pytest.raises(content.ReferralConfidentialContentUnavailable) as caught:
        read(item)
    assert caught.value.reason == ("missing" if fault == "missing" else "undecryptable")
    safe(caught.value, original, "private-token")
    assert original not in caplog.text and REMARKS not in caplog.text


@pytest.mark.parametrize("binding", ["referral", "action", "parent", "type", "envelope"])
def test_authenticated_binding_and_distinct_envelope_types(binding):
    is_action = binding != "referral"
    item = transient(ReferralActionType.CALL_PARENT_GUARDIAN if is_action else None)
    saved = write(item, REMARKS if is_action else replace(PAYLOAD, void_reason=""))
    if binding in {"referral", "action"}:
        item.pk = uuid4()
    elif binding == "parent":
        item.referral_id = uuid4()
    elif binding == "type":
        item.action_type = ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT
    else:
        item = Referral(id=item.referral_id)
    set_token(item, saved)
    with pytest.raises(content.ReferralConfidentialContentUnavailable) as caught:
        read(item)
    assert caught.value.reason == ("malformed" if binding == "envelope" else "binding_mismatch")
    safe(caught.value, saved)


@pytest.mark.parametrize("is_action", [False, True])
@pytest.mark.parametrize(
    "fault", ["missing", "extra", "type", "NUL", "surrogate", "version", "boolean-version"]
)
def test_authenticated_but_invalid_payload_fails_closed(is_action, fault):
    item = transient(ReferralActionType.CALL_PARENT_GUARDIAN if is_action else None)
    payload = {"remarks": REMARKS} if is_action else asdict(replace(PAYLOAD, void_reason=""))
    field = "remarks" if is_action else "reason"
    version = 1
    if fault == "missing":
        del payload[field]
    elif fault == "extra":
        payload["private-extra"] = "private-input"
    elif fault in {"type", "NUL", "surrogate"}:
        payload[field] = {
            "type": 12,
            "NUL": "private-input\x00",
            "surrogate": "private-input\ud800",
        }[fault]
    else:
        version = 2 if fault == "version" else True
    saved = token(item, payload, version)
    set_token(item, saved)
    with pytest.raises(content.ReferralConfidentialContentUnavailable) as caught:
        read(item)
    assert caught.value.reason == ("unsupported_schema" if "version" in fault else "malformed")
    safe(caught.value, saved, "private-input")
    with pytest.raises(RuntimeError):
        frozen.decrypt(frozen.keyring(), item, saved, action=is_action)


def test_normal_writes_storage_contract_idempotency_noop_and_audit(world, caplog):
    item = create(world)
    original = item.confidential_content_ciphertext
    repeated = create(world)
    assert repeated.pk == item.pk and repeated.confidential_content_ciphertext == original
    updated = update_status_note(
        actor=world[0],
        referral_id=item.pk,
        status_note=f"  {PAYLOAD.status_note}  ",
        context=context(world[0]),
    )
    snapshot = raw(Referral, item.pk)
    noop = update_status_note(
        actor=world[0],
        referral_id=item.pk,
        status_note=PAYLOAD.status_note,
        context=context(world[0]),
    )
    assert (
        raw(Referral, item.pk) == snapshot
        and noop.confidential_content_ciphertext == updated.confidential_content_ciphertext
    )
    a = action(world, item)
    voided = void_referral(
        actor=world[0],
        referral_id=item.pk,
        reason=f"  {PAYLOAD.void_reason}  ",
        context=context(world[0]),
    )
    assert content.read_referral_confidential_content(voided) == PAYLOAD
    assert content.read_referral_action_remarks(a) == REMARKS
    assert not set(content.CONTENT_LIMITS).intersection(columns(Referral))
    assert "remarks" not in columns(ReferralAction)
    stored = str(raw(Referral, item.pk)) + str(raw(ReferralAction, a.pk))
    for marker in [*asdict(PAYLOAD).values(), REMARKS]:
        assert marker not in stored
    output = auth_client(world[0]).get(f"/api/v1/referrals/{item.pk}")
    assert output.status_code == 200
    for name, value in asdict(PAYLOAD).items():
        assert output.json()[name] == value
    assert output.json()["actions"][0]["remarks"] == REMARKS
    assert "ciphertext" not in output.content.decode()
    assert (
        auth_client(world[0])
        .get("/api/v1/referrals?include_voided=true")
        .json()["items"][0]["status_note"]
        == PAYLOAD.status_note
    )
    assert auth_client(world[0]).get(f"/api/v1/referrals/{item.pk}/pdf").status_code == 200
    audit = str(list(AuditEvent.objects.values())) + caplog.text
    for private in [
        *asdict(PAYLOAD).values(),
        REMARKS,
        a.remarks_ciphertext,
        voided.confidential_content_ciphertext,
    ]:
        assert private not in audit
    with pytest.raises(IntegrityError), transaction.atomic():
        Referral.objects.filter(pk=item.pk).update(confidential_content_ciphertext="")
    with pytest.raises(IntegrityError), transaction.atomic():
        ReferralAction.objects.filter(pk=a.pk).update(remarks_ciphertext="")


def test_pdf_and_detail_decrypt_once_per_payload_after_authorization(world, monkeypatch):
    item = create(world)
    actions = [
        action(world, item, kind, remarks="" if index == 0 else REMARKS)
        for index, kind in enumerate(ReferralActionType.values)
    ]
    seen, original = [], content._decrypt

    def track(obj, *args):
        seen.append(obj.pk)
        return original(obj, *args)

    monkeypatch.setattr(content, "_decrypt", track)
    client = auth_client(world[0])
    assert client.get(f"/api/v1/referrals/{item.pk}").status_code == 200
    assert seen.count(item.pk) == 1 and set(seen) == {item.pk, *(a.pk for a in actions)}
    seen.clear()
    pdf = client.get(f"/api/v1/referrals/{item.pk}/pdf")
    assert pdf.status_code == 200 and seen.count(item.pk) == 1 and len(seen) == 4
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    for marker in (
        "PRIVATE-REFERRAL-REASON-SENTINEL",
        PAYLOAD.referrer_name,
        "PRIVATE-ACTION-REMARKS-SENTINEL",
    ):
        assert marker in text.replace("\n", "")


def test_list_scope_filters_search_and_pagination_before_decrypt(world, monkeypatch):
    inside = [create(world, key=str(i)) for i in range(4)]
    counselor, outside_actor, _, student, outside_student, _ = setup_scope()
    outside = create_for(outside_actor, outside_student, key="outside", fingerprint="b" * 64)
    scoped = create_for(counselor, student, key="scoped", fingerprint="c" * 64)
    seen, original = [], content._decrypt

    def track(obj, *args):
        seen.append(obj.pk)
        return original(obj, *args)

    monkeypatch.setattr(content, "_decrypt", track)
    response = auth_client(world[0]).get(
        "/api/v1/referrals", {"page": 2, "page_size": 2, "student_id": str(world[1].pk)}
    )
    assert response.status_code == 200 and len(seen) == 2
    assert set(seen) == {UUID(row["id"]) for row in response.json()["items"]}
    assert set(seen).issubset({r.pk for r in inside})
    seen.clear()
    assert auth_client(counselor).get("/api/v1/referrals").status_code == 200 and seen == [
        scoped.pk
    ]
    seen.clear()
    assert (
        auth_client(counselor).get(f"/api/v1/referrals/{outside.pk}").status_code == 404
        and not seen
    )
    assert (
        auth_client(world[0])
        .get("/api/v1/referrals", {"search": PAYLOAD.referrer_name})
        .json()["items"]
        == []
        and not seen
    )
    assert auth_client(world[0]).get(
        "/api/v1/referrals", {"search": inside[0].reference_code}
    ).status_code == 200 and seen == [inside[0].pk]


def forbidden(*args, **kwargs):
    raise AssertionError("Unauthorized/metadata operations must not decrypt Referral content")


def test_denied_roles_inactive_and_missing_capability_never_decrypt(world, monkeypatch):
    item = create(world)
    student = world[1]
    admin = make_user("crypto-admin@example.edu", "IT_ADMIN")
    dpo = make_user("crypto-dpo@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(user=dpo, designation=Designation.objects.get(code="DPO"))
    revoked = make_head("revoked@example.edu")
    UserCapabilityOverride.objects.create(
        user=revoked,
        capability=Capability.objects.get(code="referrals.view"),
        effect="REVOKE",
        reason="synthetic",
    )
    inactive = make_head("inactive@example.edu")
    clients = [auth_client(u) for u in (student, admin, dpo, revoked, inactive)]
    inactive.is_active = False
    inactive.save(update_fields=["is_active", "updated_at"])
    monkeypatch.setattr(content, "_decrypt", forbidden)
    for client in clients:
        for path in (
            "/api/v1/referrals",
            f"/api/v1/referrals/{item.pk}",
            f"/api/v1/referrals/{item.pk}/pdf",
        ):
            assert client.get(path).status_code in {401, 403}


def test_context_history_ordinary_queries_and_call_slip_metadata_need_no_decrypt(
    world, monkeypatch
):
    from types import SimpleNamespace

    item = create(world)
    action(world, item)
    Referral.objects.filter(pk=item.pk).update(confidential_content_ciphertext="broken")
    monkeypatch.setattr(content, "_decrypt", forbidden)
    assert Referral.objects.filter(student_id=world[1].pk).count() == 1
    history = list_context_history(SimpleNamespace(student_id=world[1].pk))
    assert len(history) == 1 and history[0].reference_code == item.reference_code


@pytest.mark.parametrize("model_kind", ["referral", "action"])
def test_authorized_corruption_fails_detail_pdf_and_selected_list_without_leaks(
    world, model_kind, caplog
):
    item = create(world)
    a = action(world, item)
    model, pk, col = (
        (Referral, item.pk, "confidential_content_ciphertext")
        if model_kind == "referral"
        else (ReferralAction, a.pk, "remarks_ciphertext")
    )
    model.objects.filter(pk=pk).update(**{col: "private-corrupt-token"})
    client = auth_client(world[0])
    paths = [f"/api/v1/referrals/{item.pk}", f"/api/v1/referrals/{item.pk}/pdf"]
    if model_kind == "referral":
        paths.append("/api/v1/referrals")
    for path in paths:
        response = client.get(path)
        assert (
            response.status_code == 500
            and response.json()["error"]["code"] == "referral_confidential_content_unavailable"
        )
        assert (
            b"private-corrupt-token" not in response.content
            and REMARKS not in response.content.decode()
        )
    assert "private-corrupt-token" not in caplog.text
    assert raw(model, pk)[col] == "private-corrupt-token"


def test_call_slip_reconciliation_compares_plaintext_and_never_rewraps(world):
    item = create(world)
    a = action(world, item, ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT)
    original = a.remarks_ciphertext
    kwargs = dict(
        actor=world[0],
        referral_id=item.pk,
        occurred_at=a.occurred_at,
        remarks=f" {REMARKS} ",
        context=context(world[0]),
    )
    assert ensure_call_slip_action(**kwargs)[2] is False
    for change in ({"remarks": "different"}, {"occurred_at": a.occurred_at + timedelta(seconds=1)}):
        with pytest.raises(ReferralActionConflict):
            ensure_call_slip_action(**(kwargs | change))
    assert raw(ReferralAction, a.pk)["remarks_ciphertext"] == original


@pytest.fixture
def settings_env(monkeypatch):
    for name, value in (
        (SETTING, K1),
        ("COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS", K2),
        ("ROUTINE_INTERVIEW_ENCRYPTION_KEYS", K3),
        ("SECRET_KEY", "test-django"),
        ("AUTH_TOTP_ENCRYPTION_KEY", K4),
        ("WEB_PUSH_STORAGE_KEY", K5),
        ("WEB_PUSH_ENABLED", "false"),
    ):
        monkeypatch.delenv(f"{name}_FILE", raising=False)
        monkeypatch.setenv(name, value)


def load_settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize("value", [None, "", "private-invalid-key", f"{K1},{K1}", f"{K1},,{K2}"])
def test_required_keyring_startup_validation(settings_env, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(SETTING)
    else:
        monkeypatch.setenv(SETTING, value)
    with pytest.raises(ValueError, match=SETTING) as caught:
        load_settings()
    safe(caught.value, "private-invalid-key")


@pytest.mark.parametrize(
    "other",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
    ],
)
def test_all_other_key_entries_cannot_be_reused(settings_env, monkeypatch, other):
    monkeypatch.setenv(other, f"{K6},{K1}" if other.endswith("KEYS") else K1)
    with pytest.raises(ValueError, match=f"{SETTING} must not reuse") as caught:
        load_settings()
    safe(caught.value)


def test_pointer_loaded_order_preserved(settings_env, monkeypatch, tmp_path):
    pointer = tmp_path / "synthetic"
    pointer.write_text(f"{K2},{K1}\r\n")
    monkeypatch.delenv(SETTING)
    monkeypatch.setenv(f"{SETTING}_FILE", str(pointer))
    # Avoid intentionally reusing the existing summary key for this pointer-read case.
    monkeypatch.setenv("COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS", K6)
    assert load_settings()[SETTING] == (K2, K1)


def rotate(*args):
    out, err = StringIO(), StringIO()
    call_command("rotate_referral_confidential_content", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_rotation_both_envelopes_dry_run_exact_bytes_metadata_and_idempotency(world):
    item = create(world)
    a = action(world, item)
    before = [raw(Referral, item.pk), raw(ReferralAction, a.pk)]
    counts = AuditEvent.objects.count(), Notification.objects.count(), EmailDelivery.objects.count()
    with override_settings(REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS=(K2, K1)):
        out, err = rotate("--dry-run", "--batch-size", "1")
        assert out.count("needing rotation 1") == 2 and not err
        assert before == [raw(Referral, item.pk), raw(ReferralAction, a.pk)]
        assert rotate("--batch-size", "1")[0].count("rotated 1") == 2
        for model, row, column in (
            (Referral, item, "confidential_content_ciphertext"),
            (ReferralAction, a, "remarks_ciphertext"),
        ):
            row.refresh_from_db()
            previous = before[0 if model is Referral else 1]
            new = getattr(row, column)
            assert Fernet(K2).decrypt(new.encode()) == Fernet(K1).decrypt(previous[column].encode())
            assert Fernet(K2).extract_timestamp(new.encode()) == Fernet(K1).extract_timestamp(
                previous[column].encode()
            )
            with pytest.raises(InvalidToken):
                Fernet(K1).decrypt(new.encode())
            assert {k: v for k, v in raw(model, row.pk).items() if k != column} == {
                k: v for k, v in previous.items() if k != column
            }
            read(row)
        assert rotate()[0].count("rotated 0") == 2
    assert counts == (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["referral", "action"])
def test_interrupted_rotation_keeps_committed_batches_and_resumes(world, monkeypatch, kind):
    refs = [create(world, str(i)) for i in range(3)]
    acts = [action(world, r) for r in refs]
    target = (
        "read_referral_confidential_content"
        if kind == "referral"
        else "read_referral_action_remarks"
    )
    original, calls = getattr(rotation, target), 0

    def interrupt(row):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original(row)

    with override_settings(REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS=(K2, K1)):
        with monkeypatch.context() as patch:
            patch.setattr(rotation, target, interrupt)
            with pytest.raises(KeyboardInterrupt):
                rotate("--batch-size", "1")
        model, column = (
            (Referral, "confidential_content_ciphertext")
            if kind == "referral"
            else (ReferralAction, "remarks_ciphertext")
        )
        ordered = list(model.objects.order_by("pk"))
        assert content.encrypted_with_primary_key(getattr(ordered[0], column))
        assert all(
            not content.encrypted_with_primary_key(getattr(row, column)) for row in ordered[1:]
        )
        for row in [*Referral.objects.all(), *ReferralAction.objects.all()]:
            read(row)
        rotate("--batch-size", "1")
        assert rotate()[0].count("rotated 0") == 2
    assert len(refs) == len(acts) == 3


def test_rotation_corruption_is_unchanged_and_failures_bounded(world):
    item = create(world)
    a = action(world, item)
    Referral.objects.filter(pk=item.pk).update(confidential_content_ciphertext="private-broken")
    ReferralAction.objects.filter(pk=a.pk).update(remarks_ciphertext="private-broken")
    for args in ((), ("--dry-run",)):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError):
            call_command("rotate_referral_confidential_content", *args, stdout=out, stderr=err)
        assert out.getvalue().count("failures 1") == 2 and str(a.pk) in err.getvalue()
        assert "private-broken" not in out.getvalue() + err.getvalue()
        assert raw(Referral, item.pk)["confidential_content_ciphertext"] == "private-broken"
        assert raw(ReferralAction, a.pk)["remarks_ciphertext"] == "private-broken"
    with pytest.raises(CommandError, match="batch-size"):
        rotate("--batch-size", "1001")


@pytest.fixture
def legacy(world, transactional_db):
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    apps = executor.loader.project_state(BEFORE).apps
    try:
        yield apps, world
    finally:
        if "reason" in columns(Referral):
            # Test cleanup after deliberately corrupting a dual-field token; assertions precede it.
            with connection.cursor() as cursor:
                for model, column in (
                    (Referral, "confidential_content_ciphertext"),
                    (ReferralAction, "remarks_ciphertext"),
                ):
                    if column in columns(model):
                        cursor.execute(f'UPDATE "{model._meta.db_table}" SET "{column}" = NULL')
        MigrationExecutor(connection).migrate(AFTER)


def old_referral(legacy, *, voided=False, ref="REF-2000-000001"):
    apps, world = legacy
    from compass.institutional_forms.models import FormRevision

    return apps.get_model("referrals", "Referral").objects.create(
        reference_code=ref,
        student_id=world[1].pk,
        student_name_snapshot="Historical Student",
        course_year_block_snapshot="Historic 4A",
        referred_on=timezone.now().date(),
        form_revision_id=FormRevision.objects.get(family__key="referral_slip", status="ACTIVE").pk,
        recorded_by_id=world[0].pk,
        voided_at=timezone.now() if voided else None,
        voided_by_id=world[0].pk if voided else None,
        **asdict(PAYLOAD if voided else replace(PAYLOAD, status_note="", void_reason="")),
    )


def old_action(apps, ref, kind=ReferralActionType.CALL_PARENT_GUARDIAN, remarks=REMARKS):
    return apps.get_model("referrals", "ReferralAction").objects.create(
        referral_id=ref.pk, action_type=kind, occurred_at=timezone.now(), remarks=remarks
    )


@pytest.mark.django_db(transaction=True)
def test_migration_forward_controlled_reverse_preserves_all_content_and_metadata(legacy):
    r1 = old_referral(legacy)
    r2 = old_referral(legacy, voided=True, ref="REF-2000-000002")
    actions = [
        old_action(legacy[0], r2, kind, "" if i == 0 else REMARKS)
        for i, kind in enumerate(ReferralActionType.values)
    ]
    before = {r.pk: raw(Referral, r.pk) for r in (r1, r2)}
    action_before = {a.pk: raw(ReferralAction, a.pk) for a in actions}
    counts = AuditEvent.objects.count(), Notification.objects.count(), EmailDelivery.objects.count()
    MigrationExecutor(connection).migrate(AFTER)
    assert not set(content.CONTENT_LIMITS).intersection(
        columns(Referral)
    ) and "remarks" not in columns(ReferralAction)
    for row in Referral.objects.all():
        assert asdict(read(row)) == {k: before[row.pk][k] for k in content.CONTENT_LIMITS}
        for name, value in raw(Referral, row.pk).items():
            if name != "confidential_content_ciphertext":
                assert before[row.pk][name] == value
    for row in ReferralAction.objects.all():
        assert read(row) == action_before[row.pk]["remarks"]
    response = auth_client(legacy[1][0]).get(f"/api/v1/referrals/{r2.pk}")
    assert response.status_code == 200 and response.json()["void_reason"] == PAYLOAD.void_reason
    MigrationExecutor(connection).migrate(BACKFILLED)
    for row in (r1, r2):
        restored = raw(Referral, row.pk)
        assert all(restored[name] == value for name, value in before[row.pk].items())
    for row in actions:
        restored = raw(ReferralAction, row.pk)
        assert all(restored[name] == value for name, value in action_before[row.pk].items())
    MigrationExecutor(connection).migrate(BEFORE)
    assert "confidential_content_ciphertext" not in columns(Referral)
    assert counts == (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )


@pytest.mark.django_db(transaction=True)
def test_phase_b_reconciles_old_release_new_rows_status_void_and_actions(legacy):
    first = old_referral(legacy)
    existing_action = old_action(
        legacy[0], first, ReferralActionType.SEND_PARENT_NOTIFICATION_LETTER, "old remarks"
    )
    MigrationExecutor(connection).migrate(BACKFILLED)
    apps = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    Legacy = apps.get_model("referrals", "Referral")
    apps.get_model("referrals", "ReferralAction").objects.filter(pk=existing_action.pk).update(
        remarks=REMARKS
    )
    Legacy.objects.filter(pk=first.pk).update(
        status_note=PAYLOAD.status_note,
        void_reason=PAYLOAD.void_reason,
        voided_at=timezone.now(),
        voided_by_id=legacy[1][0].pk,
    )
    late = old_referral((apps, legacy[1]), ref="REF-2000-000003")
    a = old_action(apps, first)
    MigrationExecutor(connection).migrate(AFTER)
    assert read(Referral.objects.get(pk=first.pk)) == PAYLOAD
    assert read(Referral.objects.get(pk=late.pk)).void_reason == ""
    assert read(ReferralAction.objects.get(pk=a.pk)) == REMARKS
    assert read(ReferralAction.objects.get(pk=existing_action.pk)) == REMARKS


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["referral", "action"])
@pytest.mark.parametrize("fault", ["tamper", "binding", "schema"])
def test_phase_b_unverifiable_present_token_aborts_atomically(legacy, kind, fault):
    r = old_referral(legacy)
    a = old_action(legacy[0], r)
    MigrationExecutor(connection).migrate(BACKFILLED)
    model, row, column = (
        (Referral, r, "confidential_content_ciphertext")
        if kind == "referral"
        else (ReferralAction, a, "remarks_ciphertext")
    )
    saved = raw(model, row.pk)[column]
    envelope = json.loads(Fernet(K1).decrypt(saved.encode()))
    if fault == "binding":
        envelope["referral_id"] = str(uuid4())
    elif fault == "schema":
        envelope["schema_version"] = 99
    broken = (
        "private-corrupt"
        if fault == "tamper"
        else Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "{model._meta.db_table}" SET "{column}" = %s WHERE id = %s', [broken, row.pk]
        )
        # A stale Referral is rewritten before a later action failure; all changes must roll back.
        cursor.execute('UPDATE "referrals_referral" SET status_note = %s', ["old-release-status"])
    before = raw(Referral, r.pk), raw(ReferralAction, a.pk)
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(AFTER)
    safe(caught.value, broken)
    assert "reason" in columns(Referral) and "remarks" in columns(ReferralAction)
    assert before == (raw(Referral, r.pk), raw(ReferralAction, a.pk))


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["referral", "action"])
def test_reverse_corruption_rolls_back_schema_and_partial_restoration(legacy, kind):
    r = old_referral(legacy)
    a = old_action(legacy[0], r)
    MigrationExecutor(connection).migrate(AFTER)
    model, row, column = (
        (Referral, r, "confidential_content_ciphertext")
        if kind == "referral"
        else (ReferralAction, a, "remarks_ciphertext")
    )
    original = raw(model, row.pk)[column]
    model.objects.filter(pk=row.pk).update(**{column: "private-corrupt"})
    try:
        with pytest.raises(RuntimeError):
            MigrationExecutor(connection).migrate(BACKFILLED)
        assert "reason" not in columns(Referral) and "remarks" not in columns(ReferralAction)
        assert raw(model, row.pk)[column] == "private-corrupt"
    finally:
        model.objects.filter(pk=row.pk).update(**{column: original})


@pytest.mark.django_db(transaction=True)
def test_rotation_refuses_dual_schema_and_migration_bad_keyring(legacy):
    old_referral(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    for args in ((), ("--dry-run",)):
        with pytest.raises(CommandError, match="Legacy plaintext"):
            rotate(*args)
    for keys in ((), ("private-key",), (K1, K1)):
        with override_settings(REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS=keys):
            with pytest.raises(RuntimeError) as caught:
                MigrationExecutor(connection).migrate(AFTER)
            safe(caught.value, "private-key")
        assert "reason" in columns(Referral)


@pytest.mark.parametrize(
    "field", ["reason", "referrer_name", "status_note", "void_reason", "remarks"]
)
@pytest.mark.parametrize("bad", ["private-input\x00", "private-input\ud800"])
def test_services_reject_unrepresentable_confidential_input_atomically(world, field, bad):
    item = create(world)
    before = raw(Referral, item.pk), AuditEvent.objects.count(), ReferralAction.objects.count()
    with pytest.raises(InvalidReferralInput) as caught:
        if field in {"reason", "referrer_name"}:
            create_for(world[0], world[1], key="invalid-new", fingerprint="b" * 64, **{field: bad})
        elif field == "status_note":
            update_status_note(
                actor=world[0], referral_id=item.pk, status_note=bad, context=context(world[0])
            )
        elif field == "void_reason":
            void_referral(
                actor=world[0], referral_id=item.pk, reason=bad, context=context(world[0])
            )
        else:
            action(world, item, remarks=bad)
    safe(caught.value, "private-input")
    assert before == (
        raw(Referral, item.pk),
        AuditEvent.objects.count(),
        ReferralAction.objects.count(),
    )
    assert Referral.objects.count() == 1


def test_creation_uuid_exists_before_encryption_and_action_api_contract(world, monkeypatch):
    seen, original = [], content.crypto.encrypt_bound_json

    def track(**kwargs):
        seen.append(kwargs["binding"])
        return original(**kwargs)

    monkeypatch.setattr(content.crypto, "encrypt_bound_json", track)
    item = create(world)
    assert seen == [{"referral_id": str(item.pk)}]
    client = auth_client(world[0])
    response = client.post(
        f"/api/v1/referrals/{item.pk}/actions",
        data=json.dumps(
            {
                "action_type": ReferralActionType.CALL_PARENT_GUARDIAN,
                "occurred_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
                "remarks": f" {REMARKS} ",
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 201 and response.json()["remarks"] == REMARKS
    assert seen[-1] == {
        "referral_id": str(item.pk),
        "referral_action_id": response.json()["id"],
        "action_type": ReferralActionType.CALL_PARENT_GUARDIAN,
    }
    assert "ciphertext" not in response.content.decode()


def test_call_slip_corrupt_source_remarks_returns_generic_500_and_no_partial_issuance(world):
    from compass.call_slips.models import CallSlip
    from tests.test_call_slips import composite_payload

    item = create(world)
    a = action(world, item, ReferralActionType.SEND_CALL_SLIP_INTERVIEW_PERMIT)
    ReferralAction.objects.filter(pk=a.pk).update(remarks_ciphertext="private-broken-source")
    client = auth_client(world[0])
    payload = composite_payload(action_occurred_at=a.occurred_at, action_remarks=REMARKS)
    response = client.post(
        f"/api/v1/call-slips/from-referral/{item.pk}",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="source-error",
        **csrf(client),
    )
    assert (
        response.status_code == 500
        and response.json()["error"]["code"] == "referral_confidential_content_unavailable"
    )
    assert b"private-broken-source" not in response.content and CallSlip.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_phase_b_locks_both_tables_in_parent_order_and_blocks_old_writers(legacy, monkeypatch):
    import importlib

    from django.db import OperationalError

    phase = importlib.import_module(
        "compass.referrals.migrations.0004_remove_plaintext_confidential_content"
    )
    r = old_referral(legacy)
    old_action(legacy[0], r)
    MigrationExecutor(connection).migrate(BACKFILLED)
    original, seen = phase._lock, []

    def probe(apps, editor):
        original(apps, editor)
        probe_connection = connection.copy()
        try:
            with probe_connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '100ms'")
                for table in ("referrals_referral", "referrals_referralaction"):
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(f'UPDATE "{table}" SET created_at = created_at')
                    seen.append(table)
        finally:
            probe_connection.close()

    with monkeypatch.context() as patch:
        patch.setattr(phase, "_lock", probe)
        MigrationExecutor(connection).migrate(AFTER)
    assert seen == ["referrals_referral", "referrals_referralaction"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("field,value", [("reason", " \n "), ("status_note", "x" * 1001)])
def test_phase_b_invalid_latest_plaintext_aborts_before_destruction(legacy, field, value):
    r = old_referral(legacy)
    MigrationExecutor(connection).migrate(BACKFILLED)
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "referrals_referral" SET "{field}" = %s WHERE id = %s', [value, r.pk]
        )
    snapshot = raw(Referral, r.pk)
    try:
        with pytest.raises(RuntimeError, match="malformed"):
            MigrationExecutor(connection).migrate(AFTER)
        assert raw(Referral, r.pk) == snapshot and "reason" in columns(Referral)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE "referrals_referral" SET "{field}" = %s WHERE id = %s',
                [getattr(r, field), r.pk],
            )


def test_rotation_failure_output_is_bounded_across_both_tables(world):
    item = create(world)
    Referral.objects.bulk_create(
        [
            Referral(
                reference_code=f"REF-2000-{i:06d}",
                student_id=world[1].pk,
                student_name_snapshot="Synthetic",
                course_year_block_snapshot="4A",
                referred_on=timezone.now().date(),
                form_revision_id=item.form_revision_id,
                confidential_content_ciphertext="private-broken",
            )
            for i in range(25)
        ]
    )
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError):
        call_command("rotate_referral_confidential_content", stdout=out, stderr=err)
    assert err.getvalue().count("Unreadable:") == 20 and "... and 5 more" in err.getvalue()
    assert "private-broken" not in err.getvalue() + out.getvalue()
