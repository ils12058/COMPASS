"""Synthetic storage, authorization, rotation and migration evidence for ADR-080."""

from __future__ import annotations

import base64
import importlib
import json
import runpy
from datetime import timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Capability, Designation, UserCapabilityOverride, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling import shared_summary_content as content
from compass.counseling.context_access import resolve_counseling_context
from compass.counseling.context_services import list_context_history
from compass.counseling.management.commands import (
    rotate_counseling_shared_summary_encryption as rotation,
)
from compass.counseling.migrations import _shared_summary_content_v1 as frozen
from compass.counseling.models import CounselingSharedSummary
from compass.counseling.shared_summaries import (
    CounselingSharedSummaryEmpty,
    get_assigned_shared_summary,
    publish_assigned_shared_summary,
    put_assigned_shared_summary,
)
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification
from tests.test_counseling import make_appointment
from tests.test_shared_summaries import (
    auth_client,
    context,
    create_counseling_service,
    csrf,
    make_encounter,
    make_user,
    sync_policy,
)

# Public fixed test keys; independent of all deployment and other-domain test keys.
K1, K2, K3, K4, K5 = [
    base64.urlsafe_b64encode(c * 32).decode() for c in (b"s", b"t", b"u", b"v", b"w")
]
SETTING = content.KEYRING_SETTING
TABLE = CounselingSharedSummary._meta.db_table
SENTINEL = 'ULTRA-PRIVATE-SHARED-SUMMARY-SENTINEL\n  café 🌱 雪 "quoted" \\  '


@pytest.fixture(autouse=True)
def synthetic_ring(settings):
    settings.COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS = (K1,)


@pytest.fixture
def world(db):
    sync_policy()
    admin = make_user("summary-admin@example.edu", "IT_ADMIN")
    counselor = make_user("summary-counselor@example.edu", "COUNSELOR")
    student = make_user("summary-student@example.edu", "STUDENT")
    service = create_counseling_service(admin)
    encounter = make_encounter(counselor=counselor, student=student)
    return admin, counselor, student, service, encounter


def draft(world, body=SENTINEL):
    return put_assigned_shared_summary(encounter_id=world[4].pk, counselor=world[1], content=body)


def publish(world):
    return publish_assigned_shared_summary(
        encounter_id=world[4].pk, counselor=world[1], context=context(world[1])
    )


def raw_row(pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{TABLE}" WHERE id = %s', [pk])
        return dict(zip([c.name for c in cursor.description], cursor.fetchone(), strict=True))


def columns():
    with connection.cursor() as cursor:
        return {c.name for c in connection.introspection.get_table_description(cursor, TABLE)}


def envelope(summary_id, encounter_id, body=SENTINEL):
    return dict(
        schema_version=1,
        counseling_shared_summary_id=str(summary_id),
        encounter_id=str(encounter_id),
        payload={"content": body},
    )


def authentic(values):
    return Fernet(K1).encrypt(json.dumps(values).encode()).decode()


def assert_safe(error, *private):
    output = str(error) + repr(error) + repr(error.args)
    for secret in (K1, K2, SENTINEL, "ULTRA-PRIVATE-SHARED-SUMMARY-SENTINEL", *private):
        assert secret not in output
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__


@pytest.mark.parametrize("body", ["", " \n\t ", "normal", SENTINEL])
def test_exact_text_round_trip_and_frozen_compatibility(body):
    sid, eid = uuid4(), uuid4()
    token = content.encrypt_shared_summary_content(summary_id=sid, encounter_id=eid, content=body)
    assert content.decrypt_shared_summary_content(token, summary_id=sid, encounter_id=eid) == body
    ring = frozen.keyring()
    assert frozen.decrypt(ring, token, sid, eid) == body
    migrated = frozen.encrypt(ring, sid, eid, body)
    assert (
        content.decrypt_shared_summary_content(migrated, summary_id=sid, encounter_id=eid) == body
    )
    assert Fernet(K1).decrypt(token.encode()) == Fernet(K1).decrypt(migrated.encode())


@pytest.mark.parametrize("body", [None, 42, [], "private-NUL\x00", "private-surrogate\ud800"])
def test_invalid_text_rejected_without_exposing_input(body):
    with pytest.raises(content.InvalidSharedSummaryContent) as caught:
        content.encrypt_shared_summary_content(
            summary_id=uuid4(), encounter_id=uuid4(), content=body
        )
    assert_safe(caught.value, "private-NUL", "private-surrogate")
    with pytest.raises(RuntimeError, match="malformed"):
        frozen.validate_content(body, uuid4(), uuid4())


@pytest.mark.parametrize("binding", ["summary", "encounter"])
def test_token_cannot_be_transplanted(binding):
    sid, eid = uuid4(), uuid4()
    token = authentic(envelope(sid, eid))
    with pytest.raises(content.CounselingSharedSummaryContentUnavailable) as caught:
        content.decrypt_shared_summary_content(
            token,
            summary_id=uuid4() if binding == "summary" else sid,
            encounter_id=uuid4() if binding == "encounter" else eid,
        )
    assert caught.value.reason == "binding_mismatch"
    assert_safe(caught.value, token)


@pytest.mark.parametrize("damage", ["tamper", "truncate", "random", "non-ascii", "missing"])
def test_damaged_tokens_fail_closed(damage, caplog):
    sid, eid = uuid4(), uuid4()
    valid = authentic(envelope(sid, eid))
    i = len(valid) // 2
    token = {
        "tamper": valid[:i] + ("A" if valid[i] != "A" else "B") + valid[i + 1 :],
        "truncate": valid[:-16],
        "random": "untrusted-private-token",
        "non-ascii": "untrusted-🔒",
        "missing": None,
    }[damage]
    with pytest.raises(content.CounselingSharedSummaryContentUnavailable) as caught:
        content.decrypt_shared_summary_content(token, summary_id=sid, encounter_id=eid)
    assert caught.value.reason == ("missing" if damage == "missing" else "undecryptable")
    assert_safe(caught.value, "untrusted-private", valid)
    assert not caplog.records


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"schema_version": 2}, "unsupported_schema"),
        ({"schema_version": True}, "unsupported_schema"),
        ({"schema_version": "1"}, "unsupported_schema"),
        ({"schema_version": 1.0}, "unsupported_schema"),
        ({"remove": "payload"}, "malformed"),
        ({"extra": "private-extra"}, "malformed"),
        ({"remove": "encounter_id", "wrong_binding": "private"}, "malformed"),
        ({"payload": []}, "malformed"),
        ({"payload": {}}, "malformed"),
        ({"payload": {"content": SENTINEL, "extra": "private"}}, "malformed"),
        ({"payload": {"content": 42}}, "malformed"),
        ({"payload": {"content": "private\x00"}}, "malformed"),
        ({"payload": {"content": "private\ud800"}}, "malformed"),
    ],
)
def test_exact_envelope_and_payload_schema(change, reason):
    sid, eid = uuid4(), uuid4()
    values = envelope(sid, eid)
    changed = dict(change)
    removed = changed.pop("remove", None)
    if removed:
        values.pop(removed)
    values.update(changed)
    token = authentic(values)
    with pytest.raises(content.CounselingSharedSummaryContentUnavailable) as caught:
        content.decrypt_shared_summary_content(token, summary_id=sid, encounter_id=eid)
    assert caught.value.reason == reason
    assert_safe(caught.value, token, "private-extra")
    with pytest.raises(RuntimeError, match=reason):
        frozen.decrypt(frozen.keyring(), token, sid, eid)


def test_unbounded_failure_reason_rejected():
    with pytest.raises(ValueError) as caught:
        content.CounselingSharedSummaryContentUnavailable(
            summary_id=uuid4(), encounter_id=uuid4(), reason="private-reason"
        )
    assert_safe(caught.value, "private-reason")


def test_raw_storage_edit_publication_and_generic_side_effects(world):
    item = draft(world, "old-private-body")
    old_token = item.content_ciphertext
    item = draft(world)
    assert item.content_ciphertext != old_token
    stored = raw_row(item.pk)
    assert "content" not in stored and stored["content_ciphertext"]
    assert "ULTRA-PRIVATE-SHARED-SUMMARY-SENTINEL" not in json.dumps(stored, default=str)
    assert "old-private-body" not in json.dumps(stored, default=str)
    assert content.read_shared_summary_content(item) == SENTINEL
    published = publish(world)
    assert published.content_ciphertext == item.content_ciphertext
    assert publish(world).published_at == published.published_at
    assert (
        content.read_shared_summary_content(
            get_assigned_shared_summary(encounter_id=world[4].pk, counselor=world[1])
        )
        == SENTINEL
    )
    counselor = auth_client(world[1]).get(
        f"/api/v1/counseling/encounters/{world[4].pk}/shared-summary"
    )
    student = auth_client(world[2]).get(f"/api/v1/counseling/me/shared-summaries/{item.pk}")
    assert counselor.json()["content"] == student.json()["content"] == SENTINEL
    assert "content_ciphertext" not in student.json()
    event = AuditEvent.objects.get(action="counseling.shared_summary.published")
    notification = Notification.objects.get(event_code="counseling.shared_summary.published")
    rendered = render_notification_email(notification.event_code)
    exposed = json.dumps(event.metadata) + notification.title + notification.message
    exposed += rendered.text_body + rendered.html_body
    exposed += json.dumps(
        list(EmailDelivery.objects.filter(notification=notification).values()), default=str
    )
    assert "ULTRA-PRIVATE-SHARED-SUMMARY-SENTINEL" not in exposed
    assert item.content_ciphertext not in exposed


@pytest.mark.parametrize("body", ["", " \n\t "])
def test_empty_drafts_encrypted_and_cannot_publish(world, body):
    item = draft(world, body)
    assert item.content_ciphertext and content.read_shared_summary_content(item) == body
    with pytest.raises(CounselingSharedSummaryEmpty):
        publish(world)
    for value in ("", None):
        with pytest.raises(IntegrityError), transaction.atomic():
            CounselingSharedSummary.objects.filter(pk=item.pk).update(content_ciphertext=value)


@pytest.mark.parametrize("body", ["PRIVATE-INPUT-SENTINEL\x00", "PRIVATE-INPUT-SENTINEL\ud800"])
def test_api_rejects_unrepresentable_text_safely(world, body):
    client = auth_client(world[1])
    response = client.put(
        f"/api/v1/counseling/encounters/{world[4].pk}/shared-summary",
        data=json.dumps({"content": body}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 422
    assert "PRIVATE-INPUT-SENTINEL" not in response.content.decode()
    assert not CounselingSharedSummary.objects.exists()


def forbid_decrypt(*args, **kwargs):
    pytest.fail("Unauthorized or metadata-only path decrypted a Shared Summary")


def test_student_drafts_and_other_students_filtered_before_decryption(world, monkeypatch):
    item = draft(world)
    monkeypatch.setattr(content, "decrypt_shared_summary_content", forbid_decrypt)
    owner = auth_client(world[2])
    assert owner.get("/api/v1/counseling/me/shared-summaries").json()["items"] == []
    assert owner.get(f"/api/v1/counseling/me/shared-summaries/{item.pk}").status_code == 404
    CounselingSharedSummary.objects.filter(pk=item.pk).update(published_at=timezone.now())
    other = make_user("other-summary-student@example.edu", "STUDENT")
    assert (
        auth_client(other).get(f"/api/v1/counseling/me/shared-summaries/{item.pk}").status_code
        == 404
    )
    world[2].is_active = False
    world[2].save(update_fields=["is_active"])
    assert owner.get(f"/api/v1/counseling/me/shared-summaries/{item.pk}").status_code in {401, 403}


@pytest.mark.parametrize(
    "kind", ["other", "head", "gss", "admin", "dpo", "inactive", "revoked", "student-revoked"]
)
def test_denied_actors_never_decrypt(world, monkeypatch, kind):
    item = draft(world)
    publish(world)
    role = (
        "GUIDANCE_SERVICES_STAFF"
        if kind == "gss"
        else "IT_ADMIN"
        if kind in {"admin", "dpo"}
        else "STUDENT"
        if kind == "student-revoked"
        else "COUNSELOR"
    )
    actor = (
        world[1]
        if kind in {"inactive", "revoked"}
        else world[2]
        if kind == "student-revoked"
        else make_user(f"denied-{kind}@example.edu", role)
    )
    if kind in {"head", "dpo"}:
        UserDesignation.objects.create(
            user=actor,
            designation=Designation.objects.get(
                code="DPO" if kind == "dpo" else "HEAD_GUIDANCE_COUNSELOR"
            ),
        )
    capability = (
        "shared_summaries.view_self"
        if kind == "student-revoked"
        else "shared_summaries.view_assigned"
    )
    if kind in {"revoked", "student-revoked"}:
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=capability),
            effect="REVOKE",
            reason="synthetic",
        )
    client = auth_client(actor)
    if kind == "inactive":
        actor.is_active = False
        actor.save(update_fields=["is_active"])
    monkeypatch.setattr(content, "decrypt_shared_summary_content", forbid_decrypt)
    path = (
        f"/api/v1/counseling/me/shared-summaries/{item.pk}"
        if role == "STUDENT"
        else f"/api/v1/counseling/encounters/{world[4].pk}/shared-summary"
    )
    assert client.get(path).status_code in {401, 403, 404}


def test_authorized_corruption_stable_error_without_partial_content(world, caplog):
    item = draft(world)
    publish(world)
    damaged = "untrusted-private-ciphertext"
    CounselingSharedSummary.objects.filter(pk=item.pk).update(content_ciphertext=damaged)
    for actor, path in (
        (world[1], f"/api/v1/counseling/encounters/{world[4].pk}/shared-summary"),
        (world[2], f"/api/v1/counseling/me/shared-summaries/{item.pk}"),
        (world[2], "/api/v1/counseling/me/shared-summaries"),
    ):
        response = auth_client(actor).get(path)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "counseling_shared_summary_content_unavailable"
        assert (
            SENTINEL not in response.content.decode() and damaged not in response.content.decode()
        )
    assert all(damaged not in r.getMessage() for r in caplog.records)
    item.refresh_from_db()
    assert item.content_ciphertext == damaged


def test_corrupt_draft_cannot_publish_or_emit_side_effects(world):
    item = draft(world)
    CounselingSharedSummary.objects.filter(pk=item.pk).update(content_ciphertext="broken")
    with pytest.raises(content.CounselingSharedSummaryContentUnavailable):
        publish(world)
    item.refresh_from_db()
    assert item.published_at is None
    assert not AuditEvent.objects.filter(action="counseling.shared_summary.published").exists()
    assert not Notification.objects.filter(
        event_code="counseling.shared_summary.published"
    ).exists()


def test_context_filters_and_authorizes_before_decryption(world, monkeypatch):
    item = draft(world)
    publish(world)
    new_encounter = make_encounter(counselor=world[1], student=world[2])
    hidden = put_assigned_shared_summary(
        encounter_id=new_encounter.pk, counselor=world[1], content="draft-only"
    )
    other_student = make_user("context-other-summary@example.edu", "STUDENT")
    other_encounter = make_encounter(counselor=world[1], student=other_student)
    other = put_assigned_shared_summary(
        encounter_id=other_encounter.pk, counselor=world[1], content="other-only"
    )
    CounselingSharedSummary.objects.filter(pk__in=[hidden.pk, other.pk]).update(
        content_ciphertext="broken"
    )
    CounselingSharedSummary.objects.filter(pk=other.pk).update(published_at=timezone.now())
    appointment = make_appointment(student=world[2], provider=world[1], service=world[3])
    path = f"/api/v1/counseling/context/APPOINTMENT/{appointment.pk}/shared-summaries"
    seen = []
    original = content.decrypt_shared_summary_content

    def track(token, **kwargs):
        seen.append(kwargs["summary_id"])
        return original(token, **kwargs)

    monkeypatch.setattr(content, "decrypt_shared_summary_content", track)
    response = auth_client(world[1]).get(path)
    assert response.status_code == 200 and response.json()["items"][0]["content"] == SENTINEL
    assert seen == [item.pk]
    seen.clear()
    assert (
        auth_client(make_user("context-denied@example.edu", "COUNSELOR")).get(path).status_code
        == 404
    )
    type(appointment).objects.filter(pk=appointment.pk).update(
        starts_at=timezone.now() - timedelta(days=10), ends_at=timezone.now() - timedelta(days=9)
    )
    assert auth_client(world[1]).get(path).status_code == 404 and not seen
    type(appointment).objects.filter(pk=appointment.pk).update(
        starts_at=timezone.now() - timedelta(hours=2), ends_at=timezone.now() - timedelta(hours=1)
    )
    CounselingSharedSummary.objects.filter(pk=item.pk).update(content_ciphertext="broken")
    response = auth_client(world[1]).get(path)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "counseling_shared_summary_content_unavailable"


def test_metadata_queries_encounter_search_and_context_history_do_not_decrypt(world, monkeypatch):
    item = draft(world)
    publish(world)
    appointment = make_appointment(student=world[2], provider=world[1], service=world[3])
    access = resolve_counseling_context(
        actor=world[1], anchor_type="APPOINTMENT", anchor_id=appointment.pk
    )
    monkeypatch.setattr(content, "decrypt_shared_summary_content", forbid_decrypt)
    assert list(CounselingSharedSummary.objects.filter(published_at__isnull=False))[0].pk == item.pk
    client = auth_client(world[1])
    assert client.get("/api/v1/counseling/me/encounters?search=summary").status_code == 200
    assert client.get(f"/api/v1/counseling/encounters/{world[4].pk}").status_code == 200
    assert list_context_history(access)
    assert (
        client.get(f"/api/v1/counseling/context/APPOINTMENT/{appointment.pk}/history").status_code
        == 200
    )


def test_routine_and_feedback_lifecycle_do_not_decrypt_summaries(db, monkeypatch):
    from compass.counseling.services import update_encounter
    from tests.test_counseling_downstream_lifecycle import finalize_direct

    monkeypatch.setattr(content, "decrypt_shared_summary_content", forbid_decrypt)
    _, counselor, _, encounter, opportunity = finalize_direct("summary-no-implicit")
    summary = put_assigned_shared_summary(
        encounter_id=encounter.pk, counselor=counselor, content=SENTINEL
    )
    CounselingSharedSummary.objects.filter(pk=summary.pk).update(content_ciphertext="broken")
    update_encounter(
        encounter_id=encounter.pk,
        counselor=counselor,
        changes={"ended_at": encounter.ended_at - timedelta(minutes=1)},
        context=context(counselor),
    )
    opportunity.refresh_from_db()
    assert opportunity.service_completed_at == encounter.ended_at - timedelta(minutes=1)
    assert raw_row(summary.pk)["content_ciphertext"] == "broken"


@pytest.fixture
def settings_env(monkeypatch):
    for name in (
        SETTING,
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
    ):
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    for name, value in (
        (SETTING, K1),
        ("ROUTINE_INTERVIEW_ENCRYPTION_KEYS", K3),
        ("SECRET_KEY", "synthetic-django"),
        ("AUTH_TOTP_ENCRYPTION_KEY", K4),
        ("WEB_PUSH_STORAGE_KEY", K5),
        ("WEB_PUSH_ENABLED", "false"),
    ):
        monkeypatch.setenv(name, value)


def load_settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize("value", [None, "", "invalid-private-key", f"{K1},{K1}", f"{K1},,{K2}"])
def test_required_keyring_startup_fails_safely(settings_env, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(SETTING)
    else:
        monkeypatch.setenv(SETTING, value)
    with pytest.raises(ValueError, match=SETTING) as caught:
        load_settings()
    assert_safe(caught.value, "invalid-private-key")


@pytest.mark.parametrize(
    "other",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
    ],
)
def test_reuse_of_any_other_key_rejected(settings_env, monkeypatch, other):
    monkeypatch.setenv(other, f"{K3},{K1}" if other == "ROUTINE_INTERVIEW_ENCRYPTION_KEYS" else K1)
    with pytest.raises(ValueError, match=f"{SETTING} must not reuse") as caught:
        load_settings()
    assert_safe(caught.value)


def test_settings_preserve_order_and_file_keyring(settings_env, monkeypatch, tmp_path):
    assert load_settings()[SETTING] == (K1,)
    monkeypatch.setenv(SETTING, f" {K2} ,\n{K1}\n")
    assert load_settings()[SETTING] == (K2, K1)
    source = tmp_path / "synthetic-summary-ring"
    source.write_text(f" {K2} ,\n{K1}\n")
    monkeypatch.delenv(SETTING)
    monkeypatch.setenv(f"{SETTING}_FILE", str(source))
    assert load_settings()[SETTING] == (K2, K1)


def rotate(*args):
    out, err = StringIO(), StringIO()
    call_command("rotate_counseling_shared_summary_encryption", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_rotation_dry_run_rewrap_timestamp_and_idempotence(world):
    item = draft(world)
    publish(world)
    item.refresh_from_db()
    before = raw_row(item.pk)
    token = item.content_ciphertext
    timestamp = Fernet(K1).extract_timestamp(token.encode())
    counts = (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )
    with override_settings(COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS=(K2, K1)):
        output, _ = rotate("--dry-run", "--batch-size", "1")
        assert "payloads verified: 1" in output and "to re-encrypt: 1" in output
        assert raw_row(item.pk) == before
        assert "re-encrypted: 1" in rotate("--batch-size", "1")[0]
        item.refresh_from_db()
        assert content.read_shared_summary_content(item) == SENTINEL
        assert content.encrypted_with_primary_key(item.content_ciphertext)
        assert Fernet(K2).extract_timestamp(item.content_ciphertext.encode()) == timestamp
        assert Fernet(K2).decrypt(item.content_ciphertext.encode()) == Fernet(K1).decrypt(
            token.encode()
        )
        with pytest.raises(InvalidToken):
            Fernet(K1).decrypt(item.content_ciphertext.encode())
        after = raw_row(item.pk)
        assert {k: v for k, v in after.items() if k != "content_ciphertext"} == {
            k: v for k, v in before.items() if k != "content_ciphertext"
        }
        assert "re-encrypted: 0" in rotate()[0] and raw_row(item.pk) == after
    assert counts == (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )


@pytest.mark.django_db(transaction=True)
def test_interrupted_rotation_commits_completed_batch_and_resumes(world, monkeypatch):
    items = [draft(world)]
    for _ in range(2):
        encounter = make_encounter(counselor=world[1], student=world[2])
        items.append(
            put_assigned_shared_summary(
                encounter_id=encounter.pk, counselor=world[1], content=SENTINEL
            )
        )
    originals = {item.pk: item.content_ciphertext for item in items}
    original = rotation.read_shared_summary_content
    calls = 0

    def interrupt(item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original(item)

    with override_settings(COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS=(K2, K1)):
        with monkeypatch.context() as patch:
            patch.setattr(rotation, "read_shared_summary_content", interrupt)
            with pytest.raises(KeyboardInterrupt):
                rotate("--batch-size", "1")
        ordered = list(CounselingSharedSummary.objects.order_by("pk"))
        assert content.encrypted_with_primary_key(ordered[0].content_ciphertext)
        for item in ordered[1:]:
            assert item.content_ciphertext == originals[item.pk]
            assert not content.encrypted_with_primary_key(item.content_ciphertext)
            assert content.read_shared_summary_content(item) == SENTINEL
        assert "re-encrypted: 2" in rotate("--batch-size", "1")[0]
        assert "re-encrypted: 0" in rotate()[0]


def test_rotation_corruption_unchanged_and_non_success(world):
    item = draft(world)
    broken = "private-broken-token"
    CounselingSharedSummary.objects.filter(pk=item.pk).update(content_ciphertext=broken)
    for args in ((), ("--dry-run",)):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError):
            call_command(
                "rotate_counseling_shared_summary_encryption", *args, stdout=out, stderr=err
            )
        assert "Unreadable payloads: 1" in out.getvalue()
        assert str(item.pk) in err.getvalue() and str(item.encounter_id) in err.getvalue()
        assert broken not in out.getvalue() + err.getvalue()
        assert raw_row(item.pk)["content_ciphertext"] == broken
    with pytest.raises(CommandError, match="batch-size"):
        rotate("--batch-size", "1001")


BEFORE = [("counseling", "0003_service_name_snapshot")]
BACKFILLED = [("counseling", "0004_encrypt_shared_summary_content")]
AFTER = [("counseling", "0005_remove_plaintext_shared_summary_content")]


@pytest.fixture
def legacy(world, transactional_db):
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    Legacy = executor.loader.project_state(BEFORE).apps.get_model(
        "counseling", "CounselingSharedSummary"
    )
    try:
        yield Legacy, world
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_migration_forward_reverse_preserve_metadata_and_side_effect_counts(legacy):
    Legacy, world = legacy
    rows = [
        Legacy.objects.create(
            encounter_id=world[4].pk, content=SENTINEL, published_at=timezone.now()
        )
    ]
    for body in ("", "draft Unicode 🌱"):
        encounter = make_encounter(counselor=world[1], student=world[2])
        rows.append(Legacy.objects.create(encounter_id=encounter.pk, content=body))
    before = {row.pk: raw_row(row.pk) for row in rows}
    counts = (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )
    MigrationExecutor(connection).migrate(AFTER)
    assert "content" not in columns()
    for row in rows:
        assert (
            content.read_shared_summary_content(CounselingSharedSummary.objects.get(pk=row.pk))
            == before[row.pk]["content"]
        )
        for field in ("id", "encounter_id", "created_at", "updated_at", "published_at"):
            assert raw_row(row.pk)[field] == before[row.pk][field]
    assert (
        auth_client(world[2])
        .get(f"/api/v1/counseling/me/shared-summaries/{rows[0].pk}")
        .json()["content"]
        == SENTINEL
    )
    executor = MigrationExecutor(connection)
    executor.migrate(BACKFILLED)
    Restored = executor.loader.project_state(BACKFILLED).apps.get_model(
        "counseling", "CounselingSharedSummary"
    )
    for row in rows:
        assert Restored.objects.get(pk=row.pk).content == before[row.pk]["content"]
        for field in ("created_at", "updated_at", "published_at"):
            assert raw_row(row.pk)[field] == before[row.pk][field]
    assert counts == (
        AuditEvent.objects.count(),
        Notification.objects.count(),
        EmailDelivery.objects.count(),
    )
    MigrationExecutor(connection).migrate(BEFORE)
    assert (
        "content_ciphertext" not in columns()
        and Legacy.objects.get(pk=rows[0].pk).content == SENTINEL
    )


@pytest.mark.django_db(transaction=True)
def test_phase_b_reconciles_stale_plaintext_and_late_insert(legacy):
    Legacy, world = legacy
    early = Legacy.objects.create(encounter_id=world[4].pk, content="old-before-backfill")
    executor = MigrationExecutor(connection)
    executor.migrate(BACKFILLED)
    Backfilled = executor.loader.project_state(BACKFILLED).apps.get_model(
        "counseling", "CounselingSharedSummary"
    )
    for args in ((), ("--dry-run",)):
        with pytest.raises(CommandError, match="Legacy plaintext"):
            rotate(*args)
    Backfilled.objects.filter(pk=early.pk).update(content=SENTINEL)
    next_encounter = make_encounter(counselor=world[1], student=world[2])
    late = Backfilled.objects.create(encounter_id=next_encounter.pk, content="post-backfill insert")
    assert late.content_ciphertext is None
    metadata = {row.pk: raw_row(row.pk) for row in (early, late)}
    MigrationExecutor(connection).migrate(AFTER)
    assert (
        content.read_shared_summary_content(CounselingSharedSummary.objects.get(pk=early.pk))
        == SENTINEL
    )
    assert (
        content.read_shared_summary_content(CounselingSharedSummary.objects.get(pk=late.pk))
        == "post-backfill insert"
    )
    for row in (early, late):
        assert raw_row(row.pk)["updated_at"] == metadata[row.pk]["updated_at"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fault", ["invalid-keyring", "corrupt", "binding", "nul"])
def test_phase_b_fault_aborts_before_plaintext_destruction(legacy, monkeypatch, fault):
    Legacy, world = legacy
    row = Legacy.objects.create(encounter_id=world[4].pk, content=SENTINEL)
    executor = MigrationExecutor(connection)
    executor.migrate(BACKFILLED)
    Backfilled = executor.loader.project_state(BACKFILLED).apps.get_model(
        "counseling", "CounselingSharedSummary"
    )
    if fault == "corrupt":
        Backfilled.objects.filter(pk=row.pk).update(content_ciphertext="broken-private")
    elif fault == "binding":
        Backfilled.objects.filter(pk=row.pk).update(
            content_ciphertext=authentic(envelope(uuid4(), row.encounter_id))
        )
    before = raw_row(row.pk)
    # An earlier missing-token row is repaired before the corrupt later row is encountered;
    # both its repair and schema work must roll back together on failure.
    from uuid import UUID

    extra_encounter = make_encounter(counselor=world[1], student=world[2])
    repairable = Backfilled.objects.create(
        id=UUID(int=1), encounter_id=extra_encounter.pk, content="late repairable plaintext"
    )
    repairable_before = raw_row(repairable.pk)
    try:
        with monkeypatch.context() as patch:
            if fault == "nul":
                # PG cannot store NUL. Inject this legacy value at validation to verify that
                # unsupported content aborts the real transactional schema transition.
                phase_b = importlib.import_module(
                    "compass.counseling.migrations.0005_remove_plaintext_shared_summary_content"
                )

                def invalid_legacy(body, sid, eid):
                    return frozen.validate_content(body + "\x00", sid, eid)

                patch.setattr(phase_b, "validate_content", invalid_legacy)
            with override_settings(**{SETTING: () if fault == "invalid-keyring" else (K1,)}):
                with pytest.raises(RuntimeError) as caught:
                    MigrationExecutor(connection).migrate(AFTER)
            assert_safe(caught.value, "broken-private")
        assert {"content", "content_ciphertext"} <= columns()
        assert raw_row(row.pk) == before
        assert raw_row(repairable.pk) == repairable_before
        assert AFTER[0] not in MigrationExecutor(connection).loader.applied_migrations
    finally:
        Backfilled.objects.filter(pk=row.pk).delete()


@pytest.mark.django_db(transaction=True)
def test_reverse_aborts_without_blank_restoration(legacy):
    Legacy, world = legacy
    row = Legacy.objects.create(encounter_id=world[4].pk, content=SENTINEL)
    MigrationExecutor(connection).migrate(AFTER)
    good = raw_row(row.pk)["content_ciphertext"]
    CounselingSharedSummary.objects.filter(pk=row.pk).update(content_ciphertext="broken")
    try:
        with pytest.raises(RuntimeError, match="undecryptable"):
            MigrationExecutor(connection).migrate(BACKFILLED)
        assert "content" not in columns() and raw_row(row.pk)["content_ciphertext"] == "broken"
    finally:
        CounselingSharedSummary.objects.filter(pk=row.pk).update(content_ciphertext=good)
