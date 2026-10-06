"""ADR-082 disclosure, storage, recovery and rotation regressions; synthetic keys only."""

from __future__ import annotations

import base64
import importlib
import json
import runpy
from dataclasses import asdict
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone
from pypdf import PdfReader

from compass.accounts.models import Capability, Designation, UserCapabilityOverride, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.exit_interviews import api, documents, services
from compass.exit_interviews import confidential_content as content
from compass.exit_interviews.management.commands import (
    rotate_exit_interview_confidential_content as rotation,
)
from compass.exit_interviews.migrations import _exit_interview_confidential_content_v1 as frozen
from compass.exit_interviews.models import (
    ExitInterview,
    ExitInterviewOpportunity,
    ExitInterviewReopenEvent,
)
from compass.exit_interviews.opportunities import open_opportunity, revoke_opportunity
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification
from tests.test_exit_interview_opportunities import request_f4
from tests.test_exit_interviews import (
    auth_client,
    csrf,
    make_head,
    make_inventory,
    make_user,
    make_year,
    sync_policy,
    valid_payload,
)
from tests.test_good_moral import make_affiliation

K1, K2, K3, K4, K5, K6, K7, K8 = (
    base64.urlsafe_b64encode(bytes([n]) * 32).decode("ascii") for n in range(101, 109)
)
SETTING = content.KEYRING_SETTING
BEFORE = [("exit_interviews", "0002_exitinterviewopportunity_exitinterview_opportunity_and_more")]
BACKFILLED = [("exit_interviews", "0003_encrypt_confidential_content")]
AFTER = [("exit_interviews", "0004_remove_plaintext_confidential_content")]
FAMILIES = (
    (
        ExitInterview,
        "confidential_content_ciphertext",
        content.read_exit_interview_confidential_content,
    ),
    (ExitInterviewOpportunity, "note_ciphertext", content.read_opportunity_note),
    (ExitInterviewReopenEvent, "reason_ciphertext", content.read_reopen_reason),
)
PAYLOAD = content.ExitInterviewConfidentialContent(
    email_snapshot="PRIVATE-EXIT-EMAIL-SENTINEL@example.edu",
    home_address_snapshot="PRIVATE-EXIT-ADDRESS-SENTINEL\n雪 café",
    contact_number_snapshot="PRIVATE-EXIT-CONTACT-SENTINEL",
    delay_other="PRIVATE-DELAY-OTHER-SENTINEL",
    significant_learning_other="PRIVATE-LEARNING-OTHER-SENTINEL",
    **{
        name: f"PRIVATE-{name.upper()}-SENTINEL"
        for name in content.CONTENT_LIMITS
        if name.endswith("comments")
    },
    suggestions_recommendations="PRIVATE-EXIT-SUGGESTION-SENTINEL",
)
NOTE = "PRIVATE-OPPORTUNITY-NOTE-SENTINEL"
REASON = "PRIVATE-REOPEN-REASON-SENTINEL"
SENTINELS = [*asdict(PAYLOAD).values(), NOTE, REASON]


@pytest.fixture(autouse=True)
def ring(settings):
    settings.EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)


@pytest.fixture
def world(db):
    sync_policy()
    student = make_user("encrypted-exit-student@example.edu")
    head = make_head("encrypted-exit-head@example.edu")
    year = make_year()
    inventory = make_inventory(student, year, admit=False)
    opp = open_opportunity(
        actor=head,
        student_id=student.pk,
        academic_year_id=year.pk,
        source="GRADUATION",
        note=NOTE,
        context=AuditContext.user(head),
    )
    return {"student": student, "head": head, "year": year, "inventory": inventory, "opp": opp}


def safe(value, *extras):
    text = str(value)
    assert all(secret not in text for secret in [*SENTINELS, K1, K2, *extras])


def payload_values():
    values = valid_payload(feedback_zero=True)
    for name, value in asdict(PAYLOAD).items():
        logical = {
            "email_snapshot": "email_address",
            "home_address_snapshot": "home_address",
            "contact_number_snapshot": "contact_number",
        }.get(name, name)
        values[logical] = value
    values.update(
        program_completion="WITH_SOME_DELAY",
        extra_terms_count=2,
        delay_reasons=["OTHER"],
        significant_learning_experiences=["OTHER"],
    )
    return values


def record(world, *, submitted=False):
    student = world["student"]
    item = services.ensure_my_current(student=student, context=AuditContext.user(student))
    item = services.replace_my_current(
        student=student,
        values=api._payload_values(api.ExitInterviewDraftPayload(**payload_values())),
    )
    if submitted:
        item = services.submit_my_current(student=student, context=AuditContext.user(student))
    return item


def reopen(world, item):
    services.reopen_for_correction(
        actor=world["head"],
        exit_interview_id=item.pk,
        reason=REASON,
        context=AuditContext.user(world["head"]),
    )
    return ExitInterviewReopenEvent.objects.get(exit_interview=item)


def raw(model, pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{model._meta.db_table}" WHERE id = %s', [pk])
        return dict(zip([col.name for col in cursor.description], cursor.fetchone(), strict=True))


def columns(model):
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, model._meta.db_table)
        }


def example(kind):
    if kind == "response":
        item = ExitInterview(
            program_completion="WITH_SOME_DELAY",
            extra_terms_count=2,
            delay_reasons=["OTHER"],
            significant_learning_experiences=["OTHER"],
        )
        content.write_exit_interview_confidential_content(item, PAYLOAD)
        return (
            item,
            "confidential_content_ciphertext",
            content.read_exit_interview_confidential_content,
        )
    if kind == "opportunity":
        item = ExitInterviewOpportunity(student_id=uuid4(), academic_year_id=uuid4())
        content.write_opportunity_note(item, NOTE)
        return item, "note_ciphertext", content.read_opportunity_note
    item = ExitInterviewReopenEvent(exit_interview_id=uuid4())
    content.write_reopen_reason(item, REASON)
    return item, "reason_ciphertext", content.read_reopen_reason


@pytest.mark.parametrize("kind", ["response", "opportunity", "reopen"])
def test_runtime_and_frozen_v1_are_compatible_and_uuid_precedes_encryption(kind):
    item, column, read = example(kind)
    token = getattr(item, column)
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    assert set(envelope) == {"schema_version", "payload", *frozen.binding(item, kind)}
    assert envelope["schema_version"] == 1
    assert envelope["payload"] == frozen.decrypt(frozen.keyring(), item, token, kind)
    setattr(item, column, frozen.encrypt(frozen.keyring(), item, envelope["payload"], kind))
    assert read(item) == (
        PAYLOAD if kind == "response" else NOTE if kind == "opportunity" else REASON
    )
    assert not any(hasattr(item, name) for name in content.CONTENT_LIMITS)


@pytest.mark.parametrize("kind", ["response", "opportunity", "reopen"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "tamper",
        "truncate",
        "nonascii",
        "random",
        "schema",
        "boolean-version",
        "missing-field",
        "extra-field",
        "type",
        "nul",
        "surrogate",
    ],
)
def test_all_envelope_families_reject_unreadable_or_invalid_payloads_safely(kind, fault):
    item, column, read = example(kind)
    token = getattr(item, column)
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    field = next(iter(envelope["payload"]))
    if fault == "schema":
        envelope["schema_version"] = 99
    elif fault == "boolean-version":
        envelope["schema_version"] = True
    elif fault == "missing-field":
        envelope["payload"].pop(field)
    elif fault == "extra-field":
        envelope["payload"]["extra"] = "private"
    elif fault == "type":
        envelope["payload"][field] = 12
    elif fault == "nul":
        envelope["payload"][field] = "private\x00"
    elif fault == "surrogate":
        envelope["payload"][field] = "private\ud800"
    if fault == "missing":
        broken = ""
    elif fault == "tamper":
        broken = token[:30] + ("A" if token[30] != "A" else "B") + token[31:]
    elif fault == "truncate":
        broken = token[:-15]
    elif fault == "nonascii":
        broken = "雪"
    elif fault == "random":
        broken = Fernet(K2).encrypt(b"{}").decode()
    else:
        broken = Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
    setattr(item, column, broken)
    with pytest.raises(content.ExitInterviewConfidentialContentUnavailable) as caught:
        read(item)
    safe(caught.value, broken if broken else "not-present-sentinel")
    assert caught.value.reason in {"missing", "undecryptable", "malformed", "unsupported_schema"}


@pytest.mark.parametrize(
    "kind,field",
    [
        ("response", "id"),
        ("opportunity", "id"),
        ("opportunity", "student_id"),
        ("opportunity", "academic_year_id"),
        ("reopen", "id"),
        ("reopen", "exit_interview_id"),
    ],
)
def test_each_authenticated_binding_prevents_transplants(kind, field):
    item, _column, read = example(kind)
    setattr(item, field, uuid4())
    with pytest.raises(content.ExitInterviewConfidentialContentUnavailable) as caught:
        read(item)
    assert caught.value.reason == "binding_mismatch"


@pytest.mark.parametrize(
    "field,limit", list(content.CONTENT_LIMITS.items()) + [("note", 1000), ("reason", 1000)]
)
@pytest.mark.parametrize("bad", ["nul", "surrogate", "type", "length"])
def test_exact_text_schema_preserves_limits_and_postgresql_input_boundary(field, limit, bad):
    value = {
        "nul": "private\x00",
        "surrogate": "private\ud800",
        "type": 3,
        "length": "x" * (limit + 1),
    }[bad]
    with pytest.raises(services.InvalidExitInterviewInput) as caught:
        content.validate_text(value, field, limit)
    safe(caught.value, "private")
    assert content.validate_text("é" * limit, field, limit) == "é" * limit


@pytest.mark.parametrize("kind", ["opportunity", "reopen"])
def test_empty_note_is_authenticated_but_reopen_reason_is_required(kind):
    item, column, _read = example(kind)
    if kind == "opportunity":
        content.write_opportunity_note(item, "")
        assert getattr(item, column) and content.read_opportunity_note(item) == ""
    else:
        with pytest.raises(services.InvalidExitInterviewInput):
            content.write_reopen_reason(item, " \n ")


def test_storage_has_only_ciphertext_and_survey_dimensions_remain_queryable(world):
    item = record(world, submitted=True)
    event = reopen(world, item)
    assert not set(content.CONTENT_LIMITS) & columns(ExitInterview)
    assert "note" not in columns(ExitInterviewOpportunity) and "reason" not in columns(
        ExitInterviewReopenEvent
    )
    for model, obj in [
        (ExitInterview, item),
        (ExitInterviewOpportunity, world["opp"]),
        (ExitInterviewReopenEvent, event),
    ]:
        safe(json.dumps(raw(model, obj.pk), default=str))
    item.refresh_from_db()
    assert content.read_exit_interview_confidential_content(item) == PAYLOAD
    assert content.read_reopen_reason(event) == REASON
    assert content.read_opportunity_note(world["opp"]) == NOTE
    saved = raw(ExitInterview, item.pk)
    assert saved["program_completion"] == "WITH_SOME_DELAY" and saved["extra_terms_count"] == 2
    assert saved["delay_reasons"] == ["OTHER"] and saved["significant_learning_experiences"] == [
        "OTHER"
    ]
    assert saved["career_modes"] == ["WORK", "STUDY"] and saved["work_choices"] == saved[
        "study_choices"
    ] == ["RELATED_FIELD"]
    assert ExitInterview.objects.filter(
        student_name_snapshot="Form Local Student", delay_reasons__contains=["OTHER"]
    ).exists()
    assert item.self_assessment_ratings.filter(rating=5).count() == 15
    assert item.college_feedback_ratings.filter(rating=0).count() == 1
    for model, column, _reader in FAMILIES:
        obj = model.objects.first()
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.filter(pk=obj.pk).update(**{column: ""})


def fail_decrypt(*args, **kwargs):
    raise AssertionError("metadata/denied path must not decrypt")


def patch_readers(monkeypatch):
    for module in (api, content, services, documents):
        for name in (
            "read_exit_interview_confidential_content",
            "read_opportunity_note",
            "read_reopen_reason",
        ):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, fail_decrypt)


def test_lists_search_history_status_and_good_moral_prerequisite_need_no_decryption(
    world, monkeypatch
):
    item = record(world, submitted=True)
    world["student"].institutional_id = "PRIVATE-STRUCTURED-ID"
    world["student"].save(update_fields=["institutional_id", "updated_at"])
    make_affiliation(world["student"])
    patch_readers(monkeypatch)
    head = auth_client(world["head"])
    for term in ["PRIVATE-STRUCTURED-ID", "Exit", "Form Local Student"]:
        body = head.get("/api/v1/exit-interviews", {"search": term}).json()
        assert [row["id"] for row in body["items"]] == [str(item.pk)]
        safe(json.dumps(body))
    owner = auth_client(world["student"])
    assert owner.get("/api/v1/exit-interviews/me").status_code == 200
    assert owner.get("/api/v1/exit-interviews/me/status").status_code == 200
    # Even absence of the domain ring at this service call cannot affect eligibility.
    with override_settings(EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS=()):
        first = request_f4(world["student"])
        assert (
            first.exit_interview_id == item.pk
            and first.graduation_opportunity_id == world["opp"].pk
        )
        checked = first.exit_interview_submitted_at
    assert checked == item.last_submitted_at


@pytest.mark.parametrize(
    "actor_kind", ["other-student", "head-draft", "gss", "counselor", "it", "dpo", "revoked-owner"]
)
def test_unauthorized_detail_pdf_and_draft_edits_fail_before_decryption(
    world, monkeypatch, actor_kind
):
    item = record(world)
    if actor_kind == "head-draft":
        actor = world["head"]
    elif actor_kind == "revoked-owner":
        actor = world["student"]
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code="exit_interviews.view_self"),
            effect="REVOKE",
            reason="synthetic",
        )
    else:
        role = {
            "other-student": "STUDENT",
            "gss": "GUIDANCE_SERVICES_STAFF",
            "counselor": "COUNSELOR",
            "it": "IT_ADMIN",
            "dpo": "INSTITUTIONAL_OFFICER",
        }[actor_kind]
        actor = make_user(f"denied-{actor_kind}@example.edu", role=role)
        if actor_kind == "dpo":
            UserDesignation.objects.create(
                user=actor, designation=Designation.objects.get(code="DPO")
            )
    patch_readers(monkeypatch)
    prefix = (
        "/api/v1/exit-interviews/me"
        if actor_kind in {"other-student", "revoked-owner"}
        else "/api/v1/exit-interviews"
    )
    expected = 404 if actor_kind == "other-student" else 409 if actor_kind == "head-draft" else 403
    client = auth_client(actor)
    assert client.get(f"{prefix}/{item.pk}").status_code == expected
    assert client.get(f"{prefix}/{item.pk}/pdf").status_code == expected
    if actor_kind == "other-student":
        response = client.put(
            f"{prefix}/{item.pk}",
            data=json.dumps(payload_values()),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 404


def test_owner_head_submitted_and_reopen_privacy_preserve_exact_logical_detail(world):
    item = record(world, submitted=True)
    head, owner = auth_client(world["head"]), auth_client(world["student"])
    expected = payload_values()
    for client, prefix in [
        (head, "/api/v1/exit-interviews"),
        (owner, "/api/v1/exit-interviews/me"),
    ]:
        body = client.get(f"{prefix}/{item.pk}").json()
        for field in [
            "email_address",
            "home_address",
            "contact_number",
            *list(content.CONTENT_LIMITS)[3:],
        ]:
            assert body[field] == expected[field]
        assert "ciphertext" not in json.dumps(body)
    event = reopen(world, item)
    assert head.get(f"/api/v1/exit-interviews/{item.pk}").status_code == 409
    body = owner.get(f"/api/v1/exit-interviews/me/{item.pk}").json()
    assert body["reopen_events"][0]["reason"] == REASON and body["status"] == "DRAFT"
    before = raw(ExitInterview, item.pk)["confidential_content_ciphertext"]
    values = payload_values()
    values["dean_comments"] = " Changed confidential comment "
    result = owner.put(
        f"/api/v1/exit-interviews/me/{item.pk}",
        data=json.dumps(values),
        content_type="application/json",
        **csrf(owner),
    )
    assert (
        result.status_code == 200
        and result.json()["dean_comments"] == "Changed confidential comment"
    )
    assert raw(ExitInterview, item.pk)["confidential_content_ciphertext"] != before
    safe(json.dumps(list(AuditEvent.objects.values_list("metadata", flat=True))))
    safe(str(list(Notification.objects.values_list("message", flat=True))))
    email = render_notification_email("exit_interview.reopened")
    safe(str(email))
    assert (
        event.pk == ExitInterviewReopenEvent.objects.get().pk and EmailDelivery.objects.count() == 1
    )


@pytest.mark.parametrize("family", ["response", "reopen", "opportunity"])
def test_authorized_unreadable_content_has_generic_500_no_partial_or_repair(world, family, caplog):
    item = record(world, submitted=True)
    event = reopen(world, item)
    services.submit_mine(
        student=world["student"],
        exit_interview_id=item.pk,
        context=AuditContext.user(world["student"]),
    )
    model, row, column = (
        (ExitInterview, item, "confidential_content_ciphertext")
        if family == "response"
        else (ExitInterviewReopenEvent, event, "reason_ciphertext")
        if family == "reopen"
        else (ExitInterviewOpportunity, world["opp"], "note_ciphertext")
    )
    model.objects.filter(pk=row.pk).update(**{column: "private-corrupt-token"})
    client = auth_client(world["head"])
    urls = (
        [f"/api/v1/exit-interviews/{item.pk}"]
        if family != "opportunity"
        else [
            f"/api/v1/exit-interviews/opportunities/{row.pk}",
            "/api/v1/exit-interviews/opportunities",
        ]
    )
    if family == "response":
        urls.append(f"/api/v1/exit-interviews/{item.pk}/pdf")
    for url in urls:
        response = client.get(url)
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "exit_interview_confidential_content_unavailable"
        safe(response.content.decode(), "private-corrupt-token")
    assert raw(model, row.pk)[column] == "private-corrupt-token"
    safe(caplog.text, "private-corrupt-token")
    assert not AuditEvent.objects.filter(action="document.download_released").exists()


def test_full_draft_put_does_not_repair_corrupt_existing_content(world):
    item = record(world)
    ExitInterview.objects.filter(pk=item.pk).update(
        confidential_content_ciphertext="private-corrupt-token"
    )
    before = raw(ExitInterview, item.pk), item.self_assessment_ratings.count()
    client = auth_client(world["student"])
    response = client.put(
        f"/api/v1/exit-interviews/me/{item.pk}",
        data=json.dumps(payload_values()),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 500 and before == (
        raw(ExitInterview, item.pk),
        item.self_assessment_ratings.count(),
    )


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "IT_ADMIN", "INSTITUTIONAL_OFFICER"])
def test_opportunity_manager_authorization_precedes_note_decryption(world, monkeypatch, role):
    actor = make_user(f"note-denied-{role}@example.edu", role=role)
    if role == "INSTITUTIONAL_OFFICER":
        UserDesignation.objects.create(user=actor, designation=Designation.objects.get(code="DPO"))
    monkeypatch.setattr(api, "read_opportunity_note", fail_decrypt)
    client = auth_client(actor)
    assert client.get("/api/v1/exit-interviews/opportunities").status_code == 403
    assert client.get(f"/api/v1/exit-interviews/opportunities/{world['opp'].pk}").status_code == 403


def test_opportunity_idempotency_revoked_reopening_gss_and_page_selection(world, monkeypatch):
    item = record(world)
    original = raw(ExitInterviewOpportunity, world["opp"].pk)
    assert (
        open_opportunity(
            actor=world["head"],
            student_id=world["student"].pk,
            academic_year_id=world["year"].pk,
            source="GRADUATION",
            note=f" {NOTE} ",
            context=AuditContext.user(world["head"]),
        ).pk
        == world["opp"].pk
    )
    assert original == raw(ExitInterviewOpportunity, world["opp"].pk)
    with pytest.raises(services.ExitInterviewOpportunityConflict):
        open_opportunity(
            actor=world["head"],
            student_id=world["student"].pk,
            academic_year_id=world["year"].pk,
            source="GRADUATION",
            note="different",
            context=AuditContext.user(world["head"]),
        )
    revoke_opportunity(
        actor=world["head"],
        opportunity_id=world["opp"].pk,
        context=AuditContext.user(world["head"]),
    )
    reopened = open_opportunity(
        actor=world["head"],
        student_id=world["student"].pk,
        academic_year_id=world["year"].pk,
        source="GRADUATION",
        note=NOTE,
        context=AuditContext.user(world["head"]),
    )
    assert reopened.note_ciphertext == original["note_ciphertext"]
    staff = make_user("note-gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    other = make_user("other-opportunity@example.edu")
    late = open_opportunity(
        actor=staff,
        student_id=other.pk,
        academic_year_id=world["year"].pk,
        source="MANUAL",
        note="",
        context=AuditContext.user(staff),
    )
    ExitInterviewOpportunity.objects.filter(pk=late.pk).update(
        note_ciphertext="private-broken-outside"
    )
    monkeypatch.setattr(api, "read_exit_interview_confidential_content", fail_decrypt)
    monkeypatch.setattr(api, "read_reopen_reason", fail_decrypt)
    client = auth_client(staff)
    response = client.get(
        "/api/v1/exit-interviews/opportunities",
        {"student_id": str(world["student"].pk), "page_size": 1},
    )
    assert response.status_code == 200 and response.json()["items"][0]["note"] == NOTE
    assert (
        "PRIVATE-EXIT" not in response.content.decode()
        and "ciphertext" not in response.content.decode()
    )
    assert client.get(f"/api/v1/exit-interviews/{item.pk}").status_code == 403
    UserCapabilityOverride.objects.create(
        user=staff,
        capability=Capability.objects.get(code="exit_interviews.manage_opportunities"),
        effect="REVOKE",
        reason="synthetic",
    )
    monkeypatch.setattr(api, "read_opportunity_note", fail_decrypt)
    assert client.get("/api/v1/exit-interviews/opportunities").status_code == 403


def test_real_pdf_discloses_exact_saved_content_once_and_release_audit_is_content_free(
    world, monkeypatch
):
    item = record(world, submitted=True)
    world["student"].email = "changed-account@example.edu"
    world["student"].save(update_fields=["email", "updated_at"])
    seen = []
    original = documents.read_exit_interview_confidential_content

    def track(row):
        seen.append(row.pk)
        return original(row)

    monkeypatch.setattr(documents, "read_exit_interview_confidential_content", track)
    client = auth_client(world["student"])
    response = client.get(f"/api/v1/exit-interviews/me/{item.pk}/pdf")
    assert response.status_code == 200 and seen == [item.pk]
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    # PDF line wrapping is presentation; exact logical source values are separately verified above.
    compact = text.replace("\n", "").replace(" ", "")
    for value in asdict(PAYLOAD).values():
        assert value.replace("\n", "").replace(" ", "") in compact
    assert "changed-account@example.edu" not in text
    audit = AuditEvent.objects.get(action="document.download_released")
    assert audit.metadata == {"document_type": "exit_interview", "access_mode": "SELF"}
    safe(audit.metadata, item.confidential_content_ciphertext)


@pytest.fixture
def settings_env(monkeypatch):
    for name, value in {
        "SECRET_KEY": "test-only-django-secret",
        "AUTH_TOTP_ENCRYPTION_KEY": K3,
        "WEB_PUSH_STORAGE_KEY": K4,
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS": K5,
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS": K6,
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS": K7,
        SETTING: K1,
        "WEB_PUSH_ENABLED": "false",
    }.items():
        monkeypatch.setenv(name, value)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


def load_settings():
    return runpy.run_path(str(Path(__file__).parents[1] / "config/settings.py"))


@pytest.mark.parametrize("value", [None, "", "invalid-private-key", f"{K1},{K1}", f"{K1},"])
def test_required_ordered_keyring_rejects_missing_invalid_duplicates(
    settings_env, monkeypatch, value
):
    if value is None:
        monkeypatch.delenv(SETTING)
    else:
        monkeypatch.setenv(SETTING, value)
    with pytest.raises(ValueError) as caught:
        load_settings()
    safe(caught.value, "invalid-private-key")


@pytest.mark.parametrize(
    "domain",
    [
        "SECRET_KEY",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "WEB_PUSH_STORAGE_KEY",
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
    ],
)
def test_keyring_rejects_reuse_including_previous_domain_keys(settings_env, monkeypatch, domain):
    monkeypatch.setenv(domain, f"{K8},{K1}" if domain.endswith("_KEYS") else K1)
    with pytest.raises(ValueError, match="must not reuse") as caught:
        load_settings()
    safe(caught.value)


def test_file_keyring_preserves_primary_previous_order(settings_env, monkeypatch, tmp_path):
    path = tmp_path / "synthetic-exit-ring"
    path.write_text(f"{K2},{K1}\r\n")
    monkeypatch.delenv(SETTING)
    monkeypatch.setenv(f"{SETTING}_FILE", str(path))
    assert load_settings()[SETTING] == (K2, K1)


def rotate(**options):
    out, err = StringIO(), StringIO()
    call_command("rotate_exit_interview_confidential_content", stdout=out, stderr=err, **options)
    safe(out.getvalue())
    safe(err.getvalue())
    return out.getvalue(), err.getvalue()


def snapshots():
    return {
        (model, item.pk): raw(model, item.pk)
        for model, _, _ in FAMILIES
        for item in model.objects.all()
    }


def effects():
    return tuple(model.objects.count() for model in (AuditEvent, Notification, EmailDelivery))


def test_rotation_all_families_preserves_exact_bytes_timestamps_and_business_metadata(world):
    item = record(world, submitted=True)
    reopen(world, item)
    before, counts = snapshots(), effects()
    with override_settings(**{SETTING: (K2, K1)}):
        out, err = rotate(dry_run=True, batch_size=1)
        assert out.count("needing rotation 1; failures 0") == 3 and not err
        assert snapshots() == before
        out, err = rotate(batch_size=1)
        assert out.count("rotated 1; failures 0") == 3 and not err
        after = snapshots()
        for model, column, read in FAMILIES:
            for row in model.objects.all():
                old, new = before[model, row.pk], after[model, row.pk]
                assert {k: v for k, v in old.items() if k != column} == {
                    k: v for k, v in new.items() if k != column
                }
                assert Fernet(K1).decrypt(old[column].encode()) == Fernet(K2).decrypt(
                    new[column].encode()
                )
                assert Fernet(K1).extract_timestamp(old[column].encode()) == Fernet(
                    K2
                ).extract_timestamp(new[column].encode())
                with pytest.raises(InvalidToken):
                    Fernet(K1).decrypt(new[column].encode())
                read(row)
        out, _ = rotate(batch_size=1)
        assert out.count("rotated 0; failures 0") == 3 and snapshots() == after
    assert effects() == counts


@pytest.mark.parametrize("family", [0, 1, 2])
def test_interrupted_rotation_commits_one_batch_then_resumes_without_rewrapping(
    world, monkeypatch, family
):
    item = record(world, submitted=True)
    reopen(world, item)
    model, column, read = FAMILIES[family]
    for index in range(2):
        if family == 0:
            row = ExitInterview(
                student=world["student"],
                academic_year=make_year(f"203{index}-203{index + 1}", current=False),
                inventory=world["inventory"],
            )
            content.write_exit_interview_confidential_content(
                row, content.ExitInterviewConfidentialContent()
            )
        elif family == 1:
            row = ExitInterviewOpportunity(
                student=world["student"],
                academic_year=make_year(f"203{index}-203{index + 1}", current=False),
                source="MANUAL",
                opened_by=world["head"],
                opened_at=timezone.now(),
            )
            content.write_opportunity_note(row, NOTE)
        else:
            row = ExitInterviewReopenEvent(
                exit_interview=item, reopened_by=world["head"], reopened_at=timezone.now()
            )
            content.write_reopen_reason(row, REASON)
        row.save(force_insert=True)
    original, seen = rotation.reencrypt_confidential_content, []

    def interrupt(row):
        if isinstance(row, model):
            seen.append(row.pk)
            if len(seen) == 2:
                raise KeyboardInterrupt
        return original(row)

    monkeypatch.setattr(rotation, "reencrypt_confidential_content", interrupt)
    with override_settings(**{SETTING: (K2, K1)}):
        with pytest.raises(KeyboardInterrupt):
            rotate(batch_size=1)
        rows = list(model.objects.order_by("pk"))
        assert [content.encrypted_with_primary_key(getattr(row, column)) for row in rows] == [
            True,
            False,
            False,
        ]
        first = getattr(rows[0], column)
        for row in rows:
            read(row)
        monkeypatch.setattr(rotation, "reencrypt_confidential_content", original)
        rotate(batch_size=1)
        assert getattr(model.objects.get(pk=rows[0].pk), column) == first
        assert all(
            content.encrypted_with_primary_key(getattr(row, column)) for row in model.objects.all()
        )
        out, _ = rotate(batch_size=1)
        assert out.count("rotated 0; failures 0") == 3


def test_rotation_corruption_is_bounded_safe_nonzero_and_never_repaired(world):
    item = record(world, submitted=True)
    reopen(world, item)
    for model, column, _ in FAMILIES:
        model.objects.update(**{column: "broken-private-token"})
    for _ in range(24):
        ExitInterviewReopenEvent.objects.create(
            exit_interview=item,
            reopened_by=world["head"],
            reopened_at=timezone.now(),
            reason_ciphertext="broken-private-token",
        )
    before = snapshots()
    for dry_run in (True, False):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError, match="27 Exit Interview payload") as caught:
            call_command(
                "rotate_exit_interview_confidential_content",
                dry_run=dry_run,
                batch_size=1,
                stdout=out,
                stderr=err,
            )
        assert err.getvalue().count("Unreadable:") == 20 and "and 7 more" in err.getvalue()
        safe(out.getvalue(), "broken-private-token")
        safe(err.getvalue(), "broken-private-token")
        safe(caught.value, "broken-private-token")
        assert snapshots() == before
    for batch_size in (0, 1001):
        with pytest.raises(CommandError, match="between 1 and 1000"):
            rotate(batch_size=batch_size)


@pytest.fixture
def legacy(world, transactional_db):
    initial = MigrationExecutor(connection).loader.graph.leaf_nodes()
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    try:
        yield executor.loader.project_state(BEFORE).apps, world
    finally:
        # Only reset synthetic dual-schema tokens after deliberately corrupt migration cases.
        # The tests assert refusal/atomicity before teardown; production never repairs them.
        for model, column, _ in FAMILIES:
            existing = columns(model)
            legacy_field = (
                next(iter(content.CONTENT_LIMITS))
                if model is ExitInterview
                else ("note" if model is ExitInterviewOpportunity else "reason")
            )
            if column in existing and legacy_field in existing:
                with connection.cursor() as cursor:
                    cursor.execute(f'UPDATE "{model._meta.db_table}" SET "{column}" = NULL')
        MigrationExecutor(connection).migrate(initial)


def old_response(apps, world, index=0, variant="filled"):
    model = apps.get_model("exit_interviews", "ExitInterview")
    values = asdict(PAYLOAD) if variant != "empty" else dict.fromkeys(content.CONTENT_LIMITS, "")
    if variant == "unicode":
        values["home_address_snapshot"] = '  雪 café\n"quotes" \\ path  '
    year = world["year"] if index == 0 else make_year(f"204{index}-204{index + 1}", current=False)
    submitted = variant in ("submitted", "reopened")
    return model.objects.create(
        student_id=world["student"].pk,
        academic_year_id=year.pk,
        inventory_id=world["inventory"].pk,
        opportunity_id=world["opp"].pk if index == 0 else None,
        student_name_snapshot="historical searchable name",
        status="SUBMITTED" if variant == "submitted" else "DRAFT",
        first_submitted_at=timezone.now() if submitted else None,
        last_submitted_at=timezone.now() if submitted else None,
        program_completion="WITH_SOME_DELAY" if variant != "empty" else "",
        extra_terms_count=2 if variant != "empty" else None,
        delay_reasons=["OTHER"] if variant != "empty" else [],
        significant_learning_experiences=["OTHER"] if variant != "empty" else [],
        **values,
    )


def old_event(apps, world, item, reason=REASON):
    return apps.get_model("exit_interviews", "ExitInterviewReopenEvent").objects.create(
        exit_interview_id=item.pk,
        reopened_by_id=world["head"].pk,
        reopened_at=timezone.now(),
        reason=reason,
    )


def all_raw():
    result = {}
    for model, _, _ in FAMILIES:
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM "{model._meta.db_table}" ORDER BY id')
            names = [col.name for col in cursor.description]
            result[model] = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    return result


def test_forward_reverse_restores_exact_all_content_and_preserves_metadata_ratings(legacy):
    apps, world = legacy
    variants = ["filled", "submitted", "reopened", "empty", "unicode"]
    items = [old_response(apps, world, i, variant) for i, variant in enumerate(variants)]
    old_event(apps, world, items[2])
    old_event(apps, world, items[2], "second correction 雪")
    opp_model = apps.get_model("exit_interviews", "ExitInterviewOpportunity")
    for i, status in enumerate(("OPEN", "COMPLETED", "REVOKED")):
        year = make_year(f"205{i}-205{i + 1}", current=False)
        opp_model.objects.create(
            student_id=world["student"].pk,
            academic_year_id=year.pk,
            source="MANUAL",
            status=status,
            note="" if i == 0 else NOTE,
            opened_by_id=world["head"].pk,
            opened_at=timezone.now(),
            completed_at=timezone.now() if status == "COMPLETED" else None,
            revoked_at=timezone.now() if status == "REVOKED" else None,
            revoked_by_id=world["head"].pk if status == "REVOKED" else None,
        )
    rating_model = apps.get_model("exit_interviews", "ExitInterviewSelfAssessmentRating")
    rating = rating_model.objects.create(
        exit_interview_id=items[0].pk, item_code="LEADERSHIP", rating=5
    )
    feedback_model = apps.get_model("exit_interviews", "ExitInterviewCollegeFeedbackRating")
    feedback = feedback_model.objects.create(
        exit_interview_id=items[0].pk, item_code="DEAN_AVAILABILITY", rating=0
    )
    before, counts = all_raw(), effects()
    MigrationExecutor(connection).migrate(AFTER)
    for model, column, read in FAMILIES:
        for historical in before[model]:
            row = model.objects.get(pk=historical["id"])
            logical = read(row)
            expected = (
                {name: historical[name] for name in content.CONTENT_LIMITS}
                if model is ExitInterview
                else historical["note" if model is ExitInterviewOpportunity else "reason"]
            )
            assert (asdict(logical) if model is ExitInterview else logical) == expected
            ordinary = {
                name: value
                for name, value in historical.items()
                if name
                not in (
                    set(content.CONTENT_LIMITS)
                    if model is ExitInterview
                    else {"note" if model is ExitInterviewOpportunity else "reason"}
                )
            }
            assert {
                name: value for name, value in raw(model, row.pk).items() if name != column
            } == ordinary
    assert rating_model.objects.get(pk=rating.pk).rating == 5
    assert feedback_model.objects.get(pk=feedback.pk).rating == 0
    MigrationExecutor(connection).migrate(BACKFILLED)
    restored = all_raw()
    for model, column, _ in FAMILIES:
        assert [
            {name: value for name, value in row.items() if name != column}
            for row in restored[model]
        ] == before[model]
    MigrationExecutor(connection).migrate(BEFORE)
    assert all_raw() == before and effects() == counts
    assert rating_model.objects.get(pk=rating.pk).rating == 5
    assert feedback_model.objects.get(pk=feedback.pk).rating == 0


def test_phase_b_reconciles_old_release_changes_and_missing_late_rows_under_fence(legacy):
    apps, world = legacy
    item = old_response(apps, world, variant="empty")
    event = old_event(apps, world, item, "original")
    apps.get_model("exit_interviews", "ExitInterviewOpportunity").objects.filter(
        pk=world["opp"].pk
    ).update(status="REVOKED", revoked_at=timezone.now(), revoked_by_id=world["head"].pk)
    MigrationExecutor(connection).migrate(BACKFILLED)
    apps = MigrationExecutor(connection).loader.project_state(BACKFILLED).apps
    model = apps.get_model("exit_interviews", "ExitInterview")
    model.objects.filter(pk=item.pk).update(
        **asdict(PAYLOAD),
        program_completion="WITH_SOME_DELAY",
        extra_terms_count=2,
        delay_reasons=["OTHER"],
        significant_learning_experiences=["OTHER"],
    )
    apps.get_model("exit_interviews", "ExitInterviewOpportunity").objects.filter(
        pk=world["opp"].pk
    ).update(
        status="OPEN",
        revoked_at=None,
        revoked_by_id=None,
        opened_at=timezone.now(),
        note="changed old-release note",
    )
    apps.get_model("exit_interviews", "ExitInterviewReopenEvent").objects.filter(
        pk=event.pk
    ).update(reason="changed old-release reason")
    late = old_response(apps, world, index=1)
    late_event = old_event(apps, world, late)
    late_opp = apps.get_model("exit_interviews", "ExitInterviewOpportunity").objects.create(
        student_id=world["student"].pk,
        academic_year_id=make_year("2060-2061", current=False).pk,
        source="MANUAL",
        status="OPEN",
        opened_by_id=world["head"].pk,
        opened_at=timezone.now(),
        note=NOTE,
    )
    assert model.objects.get(pk=late.pk).confidential_content_ciphertext is None
    MigrationExecutor(connection).migrate(AFTER)
    assert all(
        content.read_exit_interview_confidential_content(row) == PAYLOAD
        for row in ExitInterview.objects.all()
    )
    assert (
        content.read_opportunity_note(ExitInterviewOpportunity.objects.get(pk=world["opp"].pk))
        == "changed old-release note"
    )
    assert (
        content.read_opportunity_note(ExitInterviewOpportunity.objects.get(pk=late_opp.pk)) == NOTE
    )
    assert (
        content.read_reopen_reason(ExitInterviewReopenEvent.objects.get(pk=event.pk))
        == "changed old-release reason"
    )
    assert (
        content.read_reopen_reason(ExitInterviewReopenEvent.objects.get(pk=late_event.pk)) == REASON
    )


@pytest.mark.parametrize("family", [0, 1, 2])
@pytest.mark.parametrize("fault", ["tamper", "binding", "schema", "payload", "undecryptable"])
def test_present_corrupt_phase_a_token_aborts_without_repair_or_partial_ddl(legacy, family, fault):
    apps, world = legacy
    item = old_response(apps, world)
    event = old_event(apps, world, item)
    MigrationExecutor(connection).migrate(BACKFILLED)
    model, column, _ = FAMILIES[family]
    pk = (item.pk, world["opp"].pk, event.pk)[family]
    token = raw(model, pk)[column]
    envelope = json.loads(Fernet(K1).decrypt(token.encode()))
    if fault == "binding":
        envelope[next(name for name in envelope if name.endswith("_id"))] = str(uuid4())
    elif fault == "schema":
        envelope["schema_version"] = 2
    elif fault == "payload":
        envelope["payload"]["unrecognized"] = "private"
    broken = (
        token[:-20]
        if fault == "tamper"
        else (
            Fernet(K2).encrypt(b"{}").decode()
            if fault == "undecryptable"
            else Fernet(K1).encrypt(json.dumps(envelope).encode()).decode()
        )
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE "{model._meta.db_table}" SET "{column}" = %s WHERE id = %s', [broken, pk]
        )
        cursor.execute(
            f'UPDATE "{ExitInterview._meta.db_table}" SET dean_comments = %s',
            ["stale newest comment"],
        )
    before = all_raw()
    with pytest.raises(RuntimeError) as caught:
        MigrationExecutor(connection).migrate(AFTER)
    safe(caught.value, broken)
    assert all_raw() == before
    assert set(content.CONTENT_LIMITS) <= columns(ExitInterview)
    assert "note" in columns(ExitInterviewOpportunity) and "reason" in columns(
        ExitInterviewReopenEvent
    )


@pytest.mark.parametrize("family", [0, 1, 2])
def test_corrupt_reverse_is_atomic_and_restores_no_blank_plaintext(legacy, family):
    apps, world = legacy
    item = old_response(apps, world)
    event = old_event(apps, world, item)
    MigrationExecutor(connection).migrate(AFTER)
    model, column, _ = FAMILIES[family]
    pk = (item.pk, world["opp"].pk, event.pk)[family]
    token = raw(model, pk)[column]
    model.objects.filter(pk=pk).update(**{column: "unreadable-private-token"})
    try:
        before = all_raw()
        with pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(BACKFILLED)
        safe(caught.value, "unreadable-private-token")
        assert all_raw() == before
        assert not set(content.CONTENT_LIMITS).intersection(columns(ExitInterview))
        assert "note" not in columns(ExitInterviewOpportunity) and "reason" not in columns(
            ExitInterviewReopenEvent
        )
    finally:
        model.objects.filter(pk=pk).update(**{column: token})


def test_rotation_refuses_dual_schema_and_migration_requires_valid_keyring(legacy):
    apps, world = legacy
    old_response(apps, world)
    MigrationExecutor(connection).migrate(BACKFILLED)
    for dry_run in (True, False):
        with pytest.raises(CommandError, match="Legacy plaintext"):
            rotate(dry_run=dry_run)
    for keys in ((), ("invalid-private-key",), (K1, K1)):
        with override_settings(**{SETTING: keys}), pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(AFTER)
        safe(caught.value, "invalid-private-key")
    assert set(content.CONTENT_LIMITS) <= columns(ExitInterview)


def test_phase_b_fences_every_old_writer_before_reading_any_content(legacy, monkeypatch):
    apps, world = legacy
    old_event(apps, world, old_response(apps, world))
    MigrationExecutor(connection).migrate(BACKFILLED)
    phase = importlib.import_module(
        "compass.exit_interviews.migrations.0004_remove_plaintext_confidential_content"
    )
    original, seen = phase._lock, []

    def probe(apps, editor):
        original(apps, editor)
        writer = connection.copy()
        try:
            with writer.cursor() as cursor:
                cursor.execute("SET lock_timeout = '100ms'")
                for name, _, _ in frozen.FAMILIES:
                    table = apps.get_model("exit_interviews", name)._meta.db_table
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(f'UPDATE "{table}" SET id = id')
                    seen.append(name)
        finally:
            writer.close()

    monkeypatch.setattr(phase, "_lock", probe)
    MigrationExecutor(connection).migrate(AFTER)
    assert seen == [name for name, _, _ in frozen.FAMILIES]


@pytest.mark.parametrize(
    "source,target",
    [
        (a, b)
        for a in ("response", "opportunity", "reopen")
        for b in ("response", "opportunity", "reopen")
        if a != b
    ],
)
def test_cross_envelope_family_transplants_are_rejected(source, target):
    source_row, source_column, _ = example(source)
    target_row, target_column, read = example(target)
    setattr(target_row, target_column, getattr(source_row, source_column))
    with pytest.raises(content.ExitInterviewConfidentialContentUnavailable) as caught:
        read(target_row)
    safe(caught.value, getattr(source_row, source_column))


@pytest.mark.parametrize("field", list(content.CONTENT_LIMITS))
@pytest.mark.parametrize("bad", ["nul", "surrogate"])
def test_normal_draft_service_rejects_invalid_text_without_changing_any_stored_data(
    world, field, bad
):
    item = record(world)
    before, counts = snapshots(), effects()
    values = api._payload_values(api.ExitInterviewDraftPayload(**payload_values()))
    values[field] = "PRIVATE-INVALID-TEXT" + ("\x00" if bad == "nul" else "\ud800")
    with pytest.raises(services.InvalidExitInterviewInput) as caught:
        services.replace_mine(student=world["student"], exit_interview_id=item.pk, values=values)
    safe(caught.value, "PRIVATE-INVALID-TEXT")
    assert snapshots() == before and effects() == counts


@pytest.mark.parametrize("kind", ["opportunity", "reopen"])
@pytest.mark.parametrize("value", ["PRIVATE-INVALID-NOTE\x00", "PRIVATE-INVALID-NOTE\ud800"])
def test_operator_text_validation_remains_atomic(world, kind, value):
    item = record(world, submitted=True)
    before, counts = snapshots(), effects()
    with pytest.raises(services.InvalidExitInterviewInput) as caught:
        if kind == "opportunity":
            open_opportunity(
                actor=world["head"],
                student_id=world["student"].pk,
                academic_year_id=world["year"].pk,
                source="GRADUATION",
                note=value,
                context=AuditContext.user(world["head"]),
            )
        else:
            services.reopen_for_correction(
                actor=world["head"],
                exit_interview_id=item.pk,
                reason=value,
                context=AuditContext.user(world["head"]),
            )
    safe(caught.value, "PRIVATE-INVALID-NOTE")
    assert snapshots() == before and effects() == counts


def test_selected_page_does_not_read_lookahead_or_outside_page_notes(world, monkeypatch):
    other = make_user("page-other@example.edu")
    outside = open_opportunity(
        actor=world["head"],
        student_id=other.pk,
        academic_year_id=world["year"].pk,
        source="MANUAL",
        note="",
        context=AuditContext.user(world["head"]),
    )
    ExitInterviewOpportunity.objects.filter(pk=outside.pk).update(
        opened_at=world["opp"].opened_at - timedelta(days=1), note_ciphertext="broken-outside-page"
    )
    original, seen = api.read_opportunity_note, []

    def track(row):
        seen.append(row.pk)
        assert row.pk != outside.pk
        return original(row)

    monkeypatch.setattr(api, "read_opportunity_note", track)
    response = auth_client(world["head"]).get(
        "/api/v1/exit-interviews/opportunities", {"page_size": 1}
    )
    assert response.status_code == 200 and response.json()["has_next"]
    assert seen == [world["opp"].pk] and response.json()["items"][0]["note"] == NOTE


def test_resubmit_keeps_main_ciphertext_and_exposes_historical_reason_only_after_authorization(
    world,
):
    item = record(world, submitted=True)
    event = reopen(world, item)
    original = ExitInterview.objects.get(pk=item.pk).confidential_content_ciphertext
    item = services.submit_mine(
        student=world["student"],
        exit_interview_id=item.pk,
        context=AuditContext.user(world["student"]),
    )
    assert item.confidential_content_ciphertext == original
    response = auth_client(world["head"]).get(f"/api/v1/exit-interviews/{item.pk}")
    assert response.status_code == 200
    assert response.json()["reopen_events"][0]["id"] == str(event.pk)
    assert response.json()["reopen_events"][0]["reason"] == REASON
    for field, value in asdict(PAYLOAD).items():
        assert (
            response.json()[
                {
                    "email_snapshot": "email_address",
                    "home_address_snapshot": "home_address",
                    "contact_number_snapshot": "contact_number",
                }.get(field, field)
            ]
            == value
        )


@pytest.mark.parametrize("fault", ["over-limit", "invalid-email", "other-mismatch", "blank-reason"])
def test_invalid_latest_plaintext_aborts_phase_b_before_destructive_changes(legacy, fault):
    apps, world = legacy
    item = old_response(apps, world)
    event = old_event(apps, world, item)
    MigrationExecutor(connection).migrate(BACKFILLED)
    with connection.cursor() as cursor:
        if fault == "blank-reason":
            cursor.execute(
                f'UPDATE "{ExitInterviewReopenEvent._meta.db_table}" SET reason = %s WHERE id = %s',
                [" ", event.pk],
            )
        else:
            field, value = {
                "over-limit": ("dean_comments", "x" * 4001),
                "invalid-email": ("email_snapshot", "invalid-sensitive-email"),
                "other-mismatch": ("delay_other", ""),
            }[fault]
            cursor.execute(
                f'UPDATE "{ExitInterview._meta.db_table}" SET "{field}" = %s WHERE id = %s',
                [value, item.pk],
            )
    before = all_raw()
    try:
        with pytest.raises(RuntimeError) as caught:
            MigrationExecutor(connection).migrate(AFTER)
        safe(caught.value, "invalid-sensitive-email")
        assert all_raw() == before and set(content.CONTENT_LIMITS) <= columns(ExitInterview)
    finally:
        with connection.cursor() as cursor:
            if fault == "blank-reason":
                cursor.execute(
                    f'UPDATE "{ExitInterviewReopenEvent._meta.db_table}" '
                    "SET reason = %s WHERE id = %s",
                    [REASON, event.pk],
                )
            else:
                cursor.execute(
                    f'UPDATE "{ExitInterview._meta.db_table}" SET "{field}" = %s WHERE id = %s',
                    [asdict(PAYLOAD)[field], item.pk],
                )


def test_phase_b_retains_identical_readable_tokens_without_randomized_rewrite(legacy):
    apps, world = legacy
    old_event(apps, world, old_response(apps, world))
    MigrationExecutor(connection).migrate(BACKFILLED)
    before = all_raw()
    MigrationExecutor(connection).migrate(AFTER)
    after = all_raw()
    for model, column, _ in FAMILIES:
        assert [(row["id"], row[column]) for row in before[model]] == [
            (row["id"], row[column]) for row in after[model]
        ]
