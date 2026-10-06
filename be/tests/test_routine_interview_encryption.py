"""Routine Interview content encryption at rest (ADR-066)."""

from __future__ import annotations

import base64
import json
import logging
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.models import AuditEvent
from compass.counseling.models import CounselingEncounter
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.inventory.models import StudentInventory
from compass.organization.models import AcademicYear
from compass.routine_interviews import content
from compass.routine_interviews.content import (
    EVALUATION_FIELDS,
    INTAKE_FIELDS,
    InvalidRoutineContent,
    empty_evaluation,
    empty_intake,
    read_evaluation,
    read_intake,
    write_evaluation,
    write_intake,
)
from compass.routine_interviews.crypto import (
    RoutineContentSection,
    keyring_reuses_secret,
    parse_keyring,
)
from compass.routine_interviews.errors import RoutineContentUnavailable
from compass.routine_interviews.management.commands import (
    rotate_routine_interview_encryption as rotation_command,
)
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    InvalidRoutineInterviewInput,
    finalize_assigned_evaluation,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from tests.inventory_encryption_helpers import create_inventory_row
from tests.test_routine_interviews import (
    auth_client,
    configure_year,
    context,
    create_counseling_service,
    csrf,
    direct_routine,
    make_user,
    submit_inventory,
    sync_policy,
)

K1 = Fernet.generate_key().decode("ascii")
K2 = Fernet.generate_key().decode("ascii")
SETTING = "ROUTINE_INTERVIEW_ENCRYPTION_KEYS"
TABLE = RoutineInterview._meta.db_table
CIPHERTEXT_COLUMNS = ("student_intake_ciphertext", "counselor_evaluation_ciphertext")

SENSITIVE_INTAKE = {
    **empty_intake(),
    "coping_with_college_challenges": "Highly private response",
    "college_experience": "Línea uno\nLínea dos — naïve café 🌧️\tend",
    "family_description": "  Leading and trailing spaces stay  ",
    "concerns": [
        "SUICIDAL_THOUGHT_TENDENCY",
        "PAST_PAINFUL_EXPERIENCE",
        "VICES",
        "LOVE_LIFE",
        "OTHER",
    ],
    "other_concern_specification": "Highly private other concern",
    "career_goals": "引き続き頑張ります",
}
SENSITIVE_EVALUATION = {
    **empty_evaluation(),
    "academic_adjustment_rating": 1,
    "physical_adjustment_rating": 10,
    "spiritual_adjustment_rating": 7,
    "emotional_adjustment_rating": 2,
    "special_concern": "Counselor-only special concern",
    "recommendations": "Counselor-only recommendation\nsecond line",
}
PLAINTEXT_SENTINELS = (
    "Highly private response",
    "Highly private other concern",
    "Counselor-only special concern",
    "Counselor-only recommendation",
    "SUICIDAL_THOUGHT_TENDENCY",
    "PAST_PAINFUL_EXPERIENCE",
    "Línea uno",
    "引き続き頑張ります",
)


def _noncanonical(key: str) -> str:
    # The final Base64 character carries two padding bits; flipping one keeps the same key bytes.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    return key[:42] + alphabet[alphabet.index(key[42]) ^ 1] + key[43:]


def _authentic_token(envelope: object) -> str:
    return Fernet(K1).encrypt(json.dumps(envelope).encode("utf-8")).decode("ascii")


def _tampered(token: str) -> str:
    index = len(token) // 2
    return token[:index] + ("A" if token[index] != "A" else "B") + token[index + 1 :]


def _raw_row(routine_interview_id) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{TABLE}" WHERE id = %s', [routine_interview_id])
        names = [column.name for column in cursor.description]
        return dict(zip(names, cursor.fetchone(), strict=True))


def _rotate(*args: str) -> tuple[str, str]:
    stdout, stderr = StringIO(), StringIO()
    try:
        call_command("rotate_routine_interview_encryption", *args, stdout=stdout, stderr=stderr)
    except CommandError as exc:
        raise CommandError(f"{exc}\n{stdout.getvalue()}\n{stderr.getvalue()}") from None
    return stdout.getvalue(), stderr.getvalue()


def _assert_safe_output(text: str, *tokens: str) -> None:
    for secret in (K1, K2, *tokens, *PLAINTEXT_SENTINELS):
        assert secret not in text


# --- Keyring -------------------------------------------------------------------------------


def test_keyring_keeps_configured_order_and_ignores_surrounding_whitespace():
    assert parse_keyring(f" {K2} ,\n{K1}\n") == (K2, K1)
    assert parse_keyring((K1,)) == (K1,)


@pytest.mark.parametrize(
    ("configured", "message"),
    [
        ("", "is required"),
        (" , ", "is required"),
        (f"{K1},,{K2}", "entry 2 is empty"),
        ("not-a-fernet-key", "entry 1 is not a valid Fernet key"),
        (base64.urlsafe_b64encode(b"x" * 16).decode(), "entry 1 is not a valid Fernet key"),
        (f"{K1},{_noncanonical(K1)}", "entry 2 is not a valid Fernet key"),
        (f"{K1},{K2},{K1}", "entry 3 repeats an earlier key"),
    ],
)
def test_keyring_rejects_unsafe_configuration_without_echoing_key_material(configured, message):
    with pytest.raises(ValueError, match=message) as exc:
        parse_keyring(configured, setting=SETTING)

    assert SETTING in str(exc.value)
    assert K1 not in str(exc.value)
    assert K2 not in str(exc.value)


def test_keyring_must_not_reuse_other_configured_secrets():
    assert keyring_reuses_secret((K2, K1), "unrelated-secret-key", K1)
    assert keyring_reuses_secret((K1,), f"  {K1}\n")
    assert not keyring_reuses_secret((K1,), "", "unrelated-secret-key", K2)


# --- Section content -----------------------------------------------------------------------


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
def test_sections_round_trip_exactly_and_ciphertext_reveals_nothing():
    item = RoutineInterview(id=uuid4())
    write_intake(item, SENSITIVE_INTAKE)
    write_evaluation(item, SENSITIVE_EVALUATION)

    intake = read_intake(item)
    evaluation = read_evaluation(item)
    assert intake == SENSITIVE_INTAKE
    assert list(intake) == list(INTAKE_FIELDS)
    assert intake["concerns"] == SENSITIVE_INTAKE["concerns"]
    assert evaluation == SENSITIVE_EVALUATION
    assert list(evaluation) == list(EVALUATION_FIELDS)
    assert type(evaluation["academic_adjustment_rating"]) is int
    assert evaluation["social_adjustment_rating"] is None

    tokens = (item.student_intake_ciphertext, item.counselor_evaluation_ciphertext)
    for token in tokens:
        Fernet(K1).decrypt(token.encode("ascii"))
        for sentinel in PLAINTEXT_SENTINELS:
            assert sentinel not in token
    assert "Highly private" not in repr(item)

    # Fernet uses a fresh IV, so equal content never produces comparable ciphertext.
    write_intake(item, SENSITIVE_INTAKE)
    assert item.student_intake_ciphertext != tokens[0]


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("tampered", id="tampered"),
        pytest.param("truncated", id="truncated"),
        pytest.param(json.dumps(SENSITIVE_INTAKE), id="plaintext-json"),
        pytest.param("", id="blank"),
    ],
)
def test_modified_or_plaintext_intake_is_rejected_instead_of_decoded(stored):
    item = RoutineInterview(id=uuid4())
    write_intake(item, SENSITIVE_INTAKE)
    token = item.student_intake_ciphertext
    item.student_intake_ciphertext = {
        "tampered": _tampered(token),
        "truncated": token[:-10],
    }.get(stored, stored)

    with pytest.raises(RoutineContentUnavailable) as exc:
        read_intake(item)

    assert exc.value.reason == ("missing" if stored == "" else "undecryptable")
    assert exc.value.routine_interview_id == item.pk
    assert exc.value.section == "student_intake"
    assert str(exc.value) == "The Routine Interview content is unavailable."
    # No cryptography or JSON error (which could describe the stored bytes) is chained.
    assert exc.value.__cause__ is None
    assert exc.value.__context__ is None or exc.value.__suppress_context__


def test_wrong_key_is_rejected():
    item = RoutineInterview(id=uuid4())
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,)):
        write_evaluation(item, SENSITIVE_EVALUATION)

    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2,)):
        with pytest.raises(RoutineContentUnavailable) as exc:
            read_evaluation(item)
    assert exc.value.reason == "undecryptable"


def test_previous_key_still_decrypts_and_primary_key_encrypts_new_content():
    item = RoutineInterview(id=uuid4())
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,)):
        write_intake(item, SENSITIVE_INTAKE)
    previous = item.student_intake_ciphertext

    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1)):
        assert read_intake(item) == SENSITIVE_INTAKE
        write_evaluation(item, SENSITIVE_EVALUATION)
        assert read_evaluation(item) == SENSITIVE_EVALUATION

    Fernet(K1).decrypt(previous.encode("ascii"))
    Fernet(K2).decrypt(item.counselor_evaluation_ciphertext.encode("ascii"))
    with pytest.raises(InvalidToken):
        Fernet(K1).decrypt(item.counselor_evaluation_ciphertext.encode("ascii"))


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
def test_ciphertext_is_bound_to_its_routine_interview_and_section():
    source = RoutineInterview(id=uuid4())
    write_intake(source, SENSITIVE_INTAKE)
    write_evaluation(source, SENSITIVE_EVALUATION)

    copied = RoutineInterview(
        id=uuid4(),
        student_intake_ciphertext=source.student_intake_ciphertext,
        counselor_evaluation_ciphertext=source.counselor_evaluation_ciphertext,
    )
    swapped = RoutineInterview(
        id=source.id,
        student_intake_ciphertext=source.counselor_evaluation_ciphertext,
        counselor_evaluation_ciphertext=source.student_intake_ciphertext,
    )
    for item, read in (
        (copied, read_intake),
        (copied, read_evaluation),
        (swapped, read_intake),
        (swapped, read_evaluation),
    ):
        with pytest.raises(RoutineContentUnavailable) as exc:
            read(item)
        assert exc.value.reason == "binding_mismatch"


def _envelope(item_id, **changes) -> dict[str, object]:
    payload = {**empty_intake(), **changes.pop("payload_changes", {})}
    for field in changes.pop("payload_removed", ()):
        payload.pop(field)
    return {
        "schema_version": 1,
        "routine_interview_id": str(item_id),
        "section": "student_intake",
        "payload": payload,
        **changes,
    }


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"schema_version": 2}, "unsupported_schema"),
        ({"schema_version": True}, "unsupported_schema"),
        ({"extra": "value"}, "malformed"),
        ({"payload": ["not", "an", "object"]}, "malformed"),
        ({"payload_removed": ("career_goals",)}, "invalid_payload"),
        ({"payload_changes": {"unexpected": ""}}, "invalid_payload"),
        ({"payload_changes": {"career_goals": None}}, "invalid_payload"),
        ({"payload_changes": {"concerns": ["NOT_A_SOURCE_VALUE"]}}, "invalid_payload"),
        ({"payload_changes": {"concerns": ["VICES", "VICES"]}}, "invalid_payload"),
    ],
)
def test_authentic_but_unexpected_content_fails_closed(changes, reason):
    item = RoutineInterview(id=uuid4())
    item.student_intake_ciphertext = _authentic_token(_envelope(item.id, **changes))

    with pytest.raises(RoutineContentUnavailable) as exc:
        read_intake(item)
    assert exc.value.reason == reason


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
@pytest.mark.parametrize("rating", [0, 11, "5", 5.0, True])
def test_stored_ratings_outside_the_schema_fail_closed(rating):
    item = RoutineInterview(id=uuid4())
    envelope = {
        "schema_version": 1,
        "routine_interview_id": str(item.id),
        "section": "counselor_evaluation",
        "payload": {**empty_evaluation(), "social_adjustment_rating": rating},
    }
    item.counselor_evaluation_ciphertext = _authentic_token(envelope)

    with pytest.raises(RoutineContentUnavailable) as exc:
        read_evaluation(item)
    assert exc.value.reason == "invalid_payload"


@override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,))
@pytest.mark.parametrize("value", ["contains\x00nul", "lone \ud800 surrogate", 42])
def test_writes_reject_values_that_cannot_round_trip(value):
    item = RoutineInterview(id=uuid4())
    with pytest.raises(InvalidRoutineContent, match="career_goals") as exc:
        write_intake(item, {**SENSITIVE_INTAKE, "career_goals": value})
    assert "Highly private" not in str(exc.value)
    assert item.student_intake_ciphertext == ""


# --- Workflow, storage, and authorization --------------------------------------------------


@pytest.fixture
def world(db):
    sync_policy()
    admin = make_user("enc-admin@example.edu", "IT_ADMIN")
    student = make_user("enc-student@example.edu", "STUDENT")
    counselor = make_user("enc-counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    return {"admin": admin, "student": student, "counselor": counselor, "service": service}


def complete_routine(world, *, key: str, finalize: bool = True) -> RoutineInterview:
    student, counselor = world["student"], world["counselor"]
    item = direct_routine(counselor=counselor, student=student, key=key)
    replace_my_intake(student=student, routine_interview_id=item.pk, values=SENSITIVE_INTAKE)
    submit_my_intake(student=student, routine_interview_id=item.pk, context=context(student))
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        values=SENSITIVE_EVALUATION,
    )
    if finalize:
        end = timezone.now() - timedelta(minutes=5)
        encounter = CounselingEncounter.objects.create(
            student=student,
            counselor=counselor,
            service=world["service"],
            appointment=None,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            started_at=end - timedelta(minutes=30),
            ended_at=end,
            created_by=counselor,
        )
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=item.pk,
            encounter_id=encounter.pk,
            context=context(counselor),
        )
    return RoutineInterview.objects.get(pk=item.pk)


class DecryptionSpy:
    def __init__(self, real):
        self.real = real
        self.calls: list[tuple[object, RoutineContentSection]] = []

    def __call__(self, token, *, routine_interview_id, section):
        self.calls.append((routine_interview_id, RoutineContentSection(section)))
        return self.real(token, routine_interview_id=routine_interview_id, section=section)


@pytest.fixture
def decryptions(monkeypatch):
    spy = DecryptionSpy(content.decrypt_section)
    monkeypatch.setattr(content, "decrypt_section", spy)
    return spy


@pytest.mark.django_db
def test_new_routine_interviews_start_with_encrypted_empty_sections(world):
    item = direct_routine(counselor=world["counselor"], student=world["student"], key="enc-new")

    stored = RoutineInterview.objects.get(pk=item.pk)
    assert read_intake(stored) == empty_intake()
    assert read_evaluation(stored) == empty_evaluation()
    detail = auth_client(world["student"]).get(f"/api/v1/routine-interviews/me/{item.pk}")
    assert detail.status_code == 200
    assert detail.json()["intake"] == empty_intake()

    # A blank content column is impossible, so it can never pass for an empty form.
    for column in CIPHERTEXT_COLUMNS:
        with pytest.raises(IntegrityError), transaction.atomic():
            RoutineInterview.objects.filter(pk=item.pk).update(**{column: ""})


@pytest.mark.django_db
def test_raw_database_storage_and_logs_contain_no_routine_plaintext(world, caplog):
    caplog.set_level(logging.DEBUG)
    item = complete_routine(world, key="enc-raw")
    counselor_client = auth_client(world["counselor"])
    detail = counselor_client.get(f"/api/v1/routine-interviews/{item.pk}")

    row = _raw_row(item.pk)
    assert set(row).isdisjoint({*INTAKE_FIELDS, *EVALUATION_FIELDS})
    stored = json.dumps(row, default=str)
    for sentinel in PLAINTEXT_SENTINELS:
        assert sentinel not in stored
    for column in CIPHERTEXT_COLUMNS:
        assert row[column].startswith("gAAAAA")

    # The assigned Counselor still receives exactly what was written.
    assert detail.status_code == 200
    assert detail.json()["intake"] == SENSITIVE_INTAKE
    assert detail.json()["evaluation"] == SENSITIVE_EVALUATION
    logged = "\n".join(json.dumps(record.__dict__, default=str) for record in caplog.records)
    for sentinel in PLAINTEXT_SENTINELS:
        assert sentinel not in logged


@pytest.mark.django_db
def test_denied_actors_and_draft_intakes_are_never_decrypted(world, decryptions):
    student, counselor = world["student"], world["counselor"]
    item = direct_routine(counselor=counselor, student=student, key="enc-authz")
    replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={
            "coping_with_college_challenges": "Highly private response",
            "concerns": ["SUICIDAL_THOUGHT_TENDENCY"],
        },
    )
    other_counselor = make_user("enc-other-counselor@example.edu", "COUNSELOR")
    head = make_user("enc-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    gss = make_user("enc-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    dpo = make_user("enc-dpo@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(user=dpo, designation=Designation.objects.get(code="DPO"))
    other_student = make_user("enc-other-student@example.edu", "STUDENT")
    decryptions.calls.clear()

    for actor, status in (
        (other_counselor, 404),
        (head, 404),
        (gss, 403),
        (world["admin"], 403),
        (dpo, 403),
    ):
        client = auth_client(actor)
        assert client.get(f"/api/v1/routine-interviews/{item.pk}").status_code == status
        saved = client.put(
            f"/api/v1/routine-interviews/{item.pk}/evaluation",
            data=json.dumps({"special_concern": "Not theirs"}),
            content_type="application/json",
            **csrf(client),
        )
        assert saved.status_code == status
    other_client = auth_client(other_student)
    assert other_client.get(f"/api/v1/routine-interviews/me/{item.pk}").status_code == 404
    replaced = other_client.put(
        f"/api/v1/routine-interviews/me/{item.pk}/intake",
        data=json.dumps({"career_goals": "Not theirs"}),
        content_type="application/json",
        **csrf(other_client),
    )
    assert replaced.status_code == 404
    assert decryptions.calls == []

    # The assigned Counselor sees the draft's status and the Evaluation, never the draft Intake.
    counselor_view = auth_client(counselor).get(f"/api/v1/routine-interviews/{item.pk}")
    assert counselor_view.status_code == 200
    assert counselor_view.json()["intake"] is None
    assert "Highly private" not in counselor_view.content.decode()
    assert decryptions.calls == [(item.pk, RoutineContentSection.COUNSELOR_EVALUATION)]

    # The Student reads their own Intake and never causes the Evaluation to be decrypted.
    decryptions.calls.clear()
    student_view = auth_client(student).get(f"/api/v1/routine-interviews/me/{item.pk}")
    assert student_view.json()["intake"]["coping_with_college_challenges"] == (
        "Highly private response"
    )
    assert "evaluation" not in student_view.json()
    assert decryptions.calls == [(item.pk, RoutineContentSection.STUDENT_INTAKE)]


@pytest.mark.django_db
def test_queues_filters_context_and_counts_never_decrypt(world, decryptions):
    student, counselor = world["student"], world["counselor"]
    student.institutional_id = "ENC-2026-001"
    student.save(update_fields=["institutional_id", "updated_at"])
    submitted = complete_routine(world, key="enc-queue-submitted", finalize=False)
    draft = direct_routine(counselor=counselor, student=student, key="enc-queue-draft")
    decryptions.calls.clear()

    client = auth_client(counselor)
    year_id = str(submitted.inventory.academic_year_id)
    expectations = (
        ({}, {draft.pk, submitted.pk}),
        ({"search": "ENC-2026-001"}, {draft.pk, submitted.pk}),
        ({"student_id": str(student.pk)}, {draft.pk, submitted.pk}),
        ({"academic_year_id": year_id}, {draft.pk, submitted.pk}),
        ({"delivery_mode": "IN_PERSON"}, {draft.pk, submitted.pk}),
        ({"delivery_mode": "ONLINE"}, set()),
        ({"intake_status": "DRAFT"}, {draft.pk}),
        ({"intake_status": "SUBMITTED"}, {submitted.pk}),
        ({"evaluation_status": "DRAFT"}, {draft.pk, submitted.pk}),
        ({"evaluation_status": "FINALIZED"}, set()),
    )
    for params, expected in expectations:
        response = client.get("/api/v1/routine-interviews", params)
        assert response.status_code == 200
        assert {row["id"] for row in response.json()["items"]} == {str(pk) for pk in expected}

    mine = auth_client(student).get("/api/v1/routine-interviews/me")
    assert {row["id"] for row in mine.json()["items"]} == {str(draft.pk), str(submitted.pk)}
    anchor = f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{submitted.pk}"
    overview = client.get(anchor)
    assert overview.status_code == 200
    assert overview.json()["routine_interview"]["intake_status"] == "SUBMITTED"
    assert client.get(f"{anchor}/history").status_code == 200
    guidance = client.get("/api/v1/overview").json()["guidance"]
    assert guidance["routine_evaluation_pending_count"] == 1
    student_summary = auth_client(student).get("/api/v1/overview").json()["student"]
    assert student_summary["routine_intake_draft_count"] == 1

    assert decryptions.calls == []


@pytest.mark.django_db
def test_rating_range_is_still_enforced_without_database_constraints(world):
    item = complete_routine(world, key="enc-ratings", finalize=False)
    stored = RoutineInterview.objects.get(pk=item.pk).counselor_evaluation_ciphertext
    client = auth_client(world["counselor"])

    for rating in (0, 11):
        response = client.put(
            f"/api/v1/routine-interviews/{item.pk}/evaluation",
            data=json.dumps({**SENSITIVE_EVALUATION, "social_adjustment_rating": rating}),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 422
        with pytest.raises(InvalidRoutineInterviewInput, match="social_adjustment_rating"):
            replace_assigned_evaluation(
                counselor=world["counselor"],
                routine_interview_id=item.pk,
                values={"social_adjustment_rating": rating},
            )
    assert RoutineInterview.objects.get(pk=item.pk).counselor_evaluation_ciphertext == stored
    assert read_evaluation(RoutineInterview.objects.get(pk=item.pk)) == SENSITIVE_EVALUATION


@pytest.mark.django_db
def test_unreadable_content_fails_closed_without_being_overwritten(world, caplog):
    item = complete_routine(world, key="enc-unreadable", finalize=False)
    tampered_intake = _tampered(item.student_intake_ciphertext)
    tampered_evaluation = _tampered(item.counselor_evaluation_ciphertext)
    RoutineInterview.objects.filter(pk=item.pk).update(
        student_intake_ciphertext=tampered_intake,
        counselor_evaluation_ciphertext=tampered_evaluation,
    )
    caplog.set_level(logging.ERROR, logger="compass.routine_interviews")
    student_client = auth_client(world["student"])
    counselor_client = auth_client(world["counselor"])

    responses = [
        student_client.get(f"/api/v1/routine-interviews/me/{item.pk}"),
        counselor_client.get(f"/api/v1/routine-interviews/{item.pk}"),
        counselor_client.put(
            f"/api/v1/routine-interviews/{item.pk}/evaluation",
            data=json.dumps({"special_concern": "Replacement"}),
            content_type="application/json",
            **csrf(counselor_client),
        ),
    ]
    for response in responses:
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "routine_interview_content_unavailable"
        assert response.json()["error"]["message"] == (
            "The Routine Interview content is unavailable."
        )
        _assert_safe_output(response.content.decode(), tampered_intake, tampered_evaluation)

    stored = RoutineInterview.objects.get(pk=item.pk)
    assert stored.student_intake_ciphertext == tampered_intake
    assert stored.counselor_evaluation_ciphertext == tampered_evaluation
    events = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "routine_interview_content_unavailable"
    ]
    assert [(record.section, record.reason) for record in events] == [
        ("student_intake", "undecryptable"),
        ("student_intake", "undecryptable"),
        ("counselor_evaluation", "undecryptable"),
    ]
    assert {record.routine_interview_id for record in events} == {str(item.pk)}
    _assert_safe_output(caplog.text, tampered_intake, tampered_evaluation)


@pytest.mark.django_db
def test_intake_text_that_cannot_be_stored_is_rejected_as_invalid_input(world):
    item = direct_routine(counselor=world["counselor"], student=world["student"], key="enc-nul")
    client = auth_client(world["student"])
    response = client.put(
        f"/api/v1/routine-interviews/me/{item.pk}/intake",
        data=json.dumps({"career_goals": "contains\u0000nul"}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "routine_interview_invalid"
    with pytest.raises(InvalidRoutineInterviewInput):
        replace_my_intake(
            student=world["student"],
            routine_interview_id=item.pk,
            values={"career_goals": "contains\x00nul"},
        )
    assert read_intake(RoutineInterview.objects.get(pk=item.pk)) == empty_intake()


# --- Rotation ------------------------------------------------------------------------------


def _tokens() -> dict[object, tuple[str, str]]:
    return {
        row.pk: (row.student_intake_ciphertext, row.counselor_evaluation_ciphertext)
        for row in RoutineInterview.objects.order_by("pk")
    }


@pytest.mark.django_db
def test_rotation_rewraps_previous_key_content_without_touching_timestamps_or_audit(world):
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,)):
        finalized = complete_routine(world, key="enc-rotate-finalized")
        direct_routine(counselor=world["counselor"], student=world["student"], key="enc-rotate")
    before = _tokens()
    timestamps = {
        row.pk: (row.updated_at, row.intake_submitted_at, row.evaluation_finalized_at)
        for row in RoutineInterview.objects.all()
    }
    audit_events = AuditEvent.objects.count()

    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1)):
        dry_run, _ = _rotate("--dry-run")
        assert "Student Intake payloads verified: 2; to re-encrypt: 2" in dry_run
        assert _tokens() == before

        output, errors = _rotate("--batch-size", "1")
        assert "Records scanned: 2" in output
        assert "Student Intake payloads verified: 2; re-encrypted: 2" in output
        assert "Counselor Evaluation payloads verified: 2; re-encrypted: 2" in output
        assert "Payloads already under the primary key: 0" in output
        assert "Unreadable payloads: 0" in output
        assert "Legacy plaintext columns: none" in output
        assert errors == ""
        _assert_safe_output(
            output + dry_run, *[token for pair in before.values() for token in pair]
        )

        after = _tokens()
        for pk, tokens in after.items():
            for old, new in zip(before[pk], tokens, strict=True):
                # The exact plaintext bytes survive; only the key changes.
                assert Fernet(K2).decrypt(new.encode()) == Fernet(K1).decrypt(old.encode())
                with pytest.raises(InvalidToken):
                    Fernet(K1).decrypt(new.encode())
        for row in RoutineInterview.objects.all():
            assert (
                row.updated_at,
                row.intake_submitted_at,
                row.evaluation_finalized_at,
            ) == timestamps[row.pk]
        assert AuditEvent.objects.count() == audit_events

        repeated, _ = _rotate()
        assert "re-encrypted: 0" in repeated
        assert "Payloads already under the primary key: 4" in repeated
        assert _tokens() == after

    # Once rotation is verified, the previous key is no longer needed to read live content.
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2,)):
        stored = RoutineInterview.objects.get(pk=finalized.pk)
        assert read_intake(stored) == SENSITIVE_INTAKE
        assert read_evaluation(stored) == SENSITIVE_EVALUATION


@pytest.mark.django_db
def test_interrupted_rotation_keeps_finished_batches_and_resumes(world, monkeypatch):
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,)):
        direct_routine(counselor=world["counselor"], student=world["student"], key="enc-resume-1")
        direct_routine(counselor=world["counselor"], student=world["student"], key="enc-resume-2")
    first_pk, second_pk = list(_tokens())
    real = rotation_command.reencrypt_with_primary_key
    calls = []

    def interrupted(token):
        calls.append(token)
        if len(calls) > 2:
            raise RuntimeError("simulated interruption")
        return real(token)

    monkeypatch.setattr(rotation_command, "reencrypt_with_primary_key", interrupted)
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1)):
        with pytest.raises(RuntimeError, match="simulated interruption"):
            _rotate("--batch-size", "1")
        committed = _tokens()
        for token in committed[first_pk]:
            Fernet(K2).decrypt(token.encode())
        for token in committed[second_pk]:
            Fernet(K1).decrypt(token.encode())

        monkeypatch.setattr(rotation_command, "reencrypt_with_primary_key", real)
        output, _ = _rotate("--batch-size", "1")
        assert "Payloads already under the primary key: 2" in output
        resumed = _tokens()
        assert resumed[first_pk] == committed[first_pk]
        for token in resumed[second_pk]:
            Fernet(K2).decrypt(token.encode())


@pytest.mark.django_db
def test_rotation_reports_unreadable_content_by_id_and_section_and_leaves_it_unchanged(world):
    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K1,)):
        readable = direct_routine(
            counselor=world["counselor"], student=world["student"], key="enc-readable"
        )
        unreadable = direct_routine(
            counselor=world["counselor"], student=world["student"], key="enc-unreadable-2"
        )
    tampered = _tampered(RoutineInterview.objects.get(pk=unreadable.pk).student_intake_ciphertext)
    RoutineInterview.objects.filter(pk=unreadable.pk).update(student_intake_ciphertext=tampered)

    with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=(K2, K1)):
        with pytest.raises(CommandError) as exc:
            _rotate()
    report = str(exc.value)
    assert "1 Routine Interview payload(s) could not be verified" in report
    assert f"Unreadable: Routine Interview {unreadable.pk} student_intake (undecryptable)" in report
    assert "Unreadable payloads: 1" in report
    _assert_safe_output(report, tampered)

    stored = RoutineInterview.objects.get(pk=unreadable.pk)
    assert stored.student_intake_ciphertext == tampered
    Fernet(K2).decrypt(stored.counselor_evaluation_ciphertext.encode())
    for token in _tokens()[readable.pk]:
        Fernet(K2).decrypt(token.encode())


def test_rotation_rejects_an_unbounded_batch_size():
    with pytest.raises(CommandError, match="--batch-size"):
        _rotate("--batch-size", "0")


# --- Migration -----------------------------------------------------------------------------

BEFORE = [("routine_interviews", "0001_initial")]
BACKFILLED = [("routine_interviews", "0002_encrypt_routine_content")]
AFTER = [("routine_interviews", "0003_remove_plaintext_routine_content")]


def _legacy_participants():
    student_role, _ = Role.objects.get_or_create(
        code="STUDENT", defaults={"name": "Student", "description": ""}
    )
    counselor_role, _ = Role.objects.get_or_create(
        code="COUNSELOR", defaults={"name": "Counselor", "description": ""}
    )
    suffix = uuid4().hex[:8]
    student = User.objects.create(
        email=f"legacy-routine-student-{suffix}@example.edu",
        password="!",
        role=student_role,
        first_name="Legacy",
        last_name="Student",
    )
    counselor = User.objects.create(
        email=f"legacy-routine-counselor-{suffix}@example.edu",
        password="!",
        role=counselor_role,
        first_name="Legacy",
        last_name="Counselor",
    )
    family = FormFamily.objects.create(key=f"legacy-routine-{suffix}", title="Legacy Inventory")
    revision = FormRevision.objects.create(
        family=family,
        official_code=f"LEGACY-{suffix}",
        official_revision="0",
        internal_schema_version=1,
    )
    inventory = create_inventory_row(
        StudentInventory,
        student=student,
        academic_year=AcademicYear.objects.create(label=f"L-{suffix}"),
        form_revision=revision,
    )
    return {"student_id": student.pk, "counselor_id": counselor.pk, "inventory_id": inventory.pk}


def _legacy_routine(apps, participants, **values):
    Legacy = apps.get_model("routine_interviews", "RoutineInterview")
    return Legacy.objects.create(
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=timezone.now() - timedelta(days=1),
        **participants,
        **values,
    )


def _table_shape() -> tuple[set[str], set[str]]:
    with connection.cursor() as cursor:
        columns = {c.name for c in connection.introspection.get_table_description(cursor, TABLE)}
        constraints = set(connection.introspection.get_constraints(cursor, TABLE))
    return columns, constraints


@pytest.mark.django_db(transaction=True)
def test_migration_encrypts_verifies_drops_plaintext_and_rolls_back_exactly():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old_apps = executor.loader.project_state(BEFORE).apps
    participants = _legacy_participants()
    sensitive = _legacy_routine(old_apps, participants, **SENSITIVE_INTAKE, **SENSITIVE_EVALUATION)
    blank = _legacy_routine(old_apps, participants)
    updated_at = {sensitive.pk: sensitive.updated_at, blank.pk: blank.updated_at}

    try:
        MigrationExecutor(connection).migrate(AFTER)

        columns, constraints = _table_shape()
        assert columns.isdisjoint({*INTAKE_FIELDS, *EVALUATION_FIELDS})
        assert not any(name.endswith("_rating_range") for name in constraints)
        assert {
            "routine_entry_appointment_consistent",
            "routine_finalized_requires_encounter",
            "routine_intake_ciphertext_present",
            "routine_evaluation_ciphertext_present",
        } <= constraints
        migrated = RoutineInterview.objects.get(pk=sensitive.pk)
        assert read_intake(migrated) == SENSITIVE_INTAKE
        assert read_evaluation(migrated) == SENSITIVE_EVALUATION
        empty = RoutineInterview.objects.get(pk=blank.pk)
        assert read_intake(empty) == empty_intake()
        assert read_evaluation(empty) == empty_evaluation()
        for row in RoutineInterview.objects.all():
            assert row.updated_at == updated_at[row.pk]
            stored = json.dumps(_raw_row(row.pk), default=str)
            for sentinel in PLAINTEXT_SENTINELS:
                assert sentinel not in stored
        verified, _ = _rotate("--dry-run")
        assert "Records scanned: 2" in verified
        assert "Unreadable payloads: 0" in verified

        # A controlled rollback restores exactly the same plaintext.
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        Restored = executor.loader.project_state(BEFORE).apps.get_model(
            "routine_interviews", "RoutineInterview"
        )
        restored = Restored.objects.get(pk=sensitive.pk)
        for field, value in {**SENSITIVE_INTAKE, **SENSITIVE_EVALUATION}.items():
            assert getattr(restored, field) == value
        assert "student_intake_ciphertext" not in _table_shape()[0]
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_migration_reencrypts_plaintext_written_after_the_backfill():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    participants = _legacy_participants()
    early = _legacy_routine(
        executor.loader.project_state(BEFORE).apps,
        participants,
        career_goals="Before the backfill",
    )

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(BACKFILLED)
        backfilled_apps = executor.loader.project_state(BACKFILLED).apps
        with pytest.raises(CommandError, match="legacy plaintext"):
            _rotate("--dry-run")

        # The previous release keeps writing plaintext while the migrations run.
        Backfilled = backfilled_apps.get_model("routine_interviews", "RoutineInterview")
        Backfilled.objects.filter(pk=early.pk).update(career_goals="Changed after the backfill")
        late = _legacy_routine(
            backfilled_apps,
            participants,
            coping_remarks="Created after the backfill",
            special_concern="Counselor-only special concern",
        )
        assert late.student_intake_ciphertext is None

        MigrationExecutor(connection).migrate(AFTER)
        assert read_intake(RoutineInterview.objects.get(pk=early.pk))["career_goals"] == (
            "Changed after the backfill"
        )
        refreshed = RoutineInterview.objects.get(pk=late.pk)
        assert read_intake(refreshed)["coping_remarks"] == "Created after the backfill"
        assert read_evaluation(refreshed)["special_concern"] == "Counselor-only special concern"
    finally:
        MigrationExecutor(connection).migrate(AFTER)


@pytest.mark.django_db(transaction=True)
def test_migration_aborts_before_dropping_plaintext_when_content_or_keyring_is_invalid():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    Legacy = executor.loader.project_state(BEFORE).apps.get_model(
        "routine_interviews", "RoutineInterview"
    )
    invalid = _legacy_routine(
        executor.loader.project_state(BEFORE).apps,
        _legacy_participants(),
        coping_remarks="Highly private response",
        concerns=["NOT_A_SOURCE_VALUE"],
    )

    try:
        with pytest.raises(RuntimeError, match=f"{invalid.pk} student_intake") as exc:
            MigrationExecutor(connection).migrate(AFTER)
        assert "Highly private" not in str(exc.value)
        assert "NOT_A_SOURCE_VALUE" not in str(exc.value)
        columns, constraints = _table_shape()
        assert {*INTAKE_FIELDS, *EVALUATION_FIELDS} <= columns
        assert "student_intake_ciphertext" not in columns
        assert "routine_academic_rating_range" in constraints
        assert Legacy.objects.get(pk=invalid.pk).coping_remarks == "Highly private response"

        Legacy.objects.filter(pk=invalid.pk).update(concerns=["FAMILY"])
        with override_settings(ROUTINE_INTERVIEW_ENCRYPTION_KEYS=()):
            with pytest.raises(RuntimeError, match="valid Fernet keyring"):
                MigrationExecutor(connection).migrate(AFTER)
        assert "student_intake_ciphertext" not in _table_shape()[0]
    finally:
        Legacy.objects.filter(pk=invalid.pk).delete()
        MigrationExecutor(connection).migrate(AFTER)
