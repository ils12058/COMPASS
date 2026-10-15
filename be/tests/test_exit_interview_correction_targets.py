"""FORM-CORR-1: encrypted Exit Interview correction targets on existing reopen events."""

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
from django.db.migrations.executor import MigrationExecutor
from pypdf import PdfReader

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.common.json_logging import JsonFormatter
from compass.confidential_data.crypto import encrypt_bound_json
from compass.exit_interviews import api as exit_api
from compass.exit_interviews import confidential_content as content
from compass.exit_interviews import services
from compass.exit_interviews.correction_targets import (
    TARGET_COVERAGE,
    ExitInterviewCorrectionTarget,
    allowed_correction_targets,
    normalize_correction_targets,
)
from compass.exit_interviews.errors import InvalidExitInterviewInput
from compass.exit_interviews.models import (
    CollegeFeedbackItem,
    ExitInterview,
    ExitInterviewCollegeFeedbackRating,
    ExitInterviewReopenEvent,
    ExitInterviewStatus,
    SelfAssessmentItem,
)
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.inventory import confidential_content as inventory_content
from compass.inventory.models import InventoryReopenEvent
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import Notification
from compass.notifications.push_policy import push_body_for
from tests.test_exit_interviews import (
    auth_client,
    csrf,
    ensure_api,
    make_head,
    make_inventory,
    make_user,
    make_year,
    put_api,
    submit_api,
    sync_policy,
    valid_payload,
)

T = ExitInterviewCorrectionTarget
K1, K2 = (base64.urlsafe_b64encode(bytes([n]) * 32).decode() for n in (141, 142))
INVENTORY_KEY = base64.urlsafe_b64encode(bytes([143]) * 32).decode()
REASON = "PRIVATE-EXIT-CORRECTION-REASON-SENTINEL"
PROGRAM_CHAIR_TARGETS = {
    T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_AVAILABILITY,
    T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_APPROACHABILITY,
    T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_CONCERN_FOR_STUDENTS,
    T.COLLEGE_FEEDBACK_COMMENTS_PROGRAM_CHAIR,
}
SELECTED = [
    T.SUGGESTIONS_SUGGESTIONS_RECOMMENDATIONS.value,
    T.COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_EFFICIENCY.value,
    T.GENERAL_HOME_ADDRESS.value,
    T.SELF_ASSESSMENT_SELF_ESTEEM.value,
    T.COLLEGE_FEEDBACK_DEAN_AVAILABILITY.value,
    T.GENERAL_HOME_ADDRESS.value,
    T.SECTION_COLLEGE_FEEDBACK.value,
]
CANONICAL = [
    T.GENERAL_HOME_ADDRESS.value,
    T.SELF_ASSESSMENT_SELF_ESTEEM.value,
    T.SECTION_COLLEGE_FEEDBACK.value,
    T.COLLEGE_FEEDBACK_DEAN_AVAILABILITY.value,
    T.COLLEGE_FEEDBACK_GUIDANCE_COUNSELOR_EFFICIENCY.value,
    T.SUGGESTIONS_SUGGESTIONS_RECOMMENDATIONS.value,
]


@pytest.fixture(autouse=True)
def ring(settings):
    settings.EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (INVENTORY_KEY,)


def submitted_record(email, year, *, legacy=False, feedback_zero=False):
    student = make_user(email)
    make_inventory(student, year)
    client = auth_client(student)
    assert ensure_api(client).status_code == 200
    item = ExitInterview.objects.get(student=student)
    if legacy:
        # Pre-cutover provenance: the full seven-category contract with Program Chair.
        item.form_revision = None
        item.save(update_fields=["form_revision"])
    saved = put_api(client, valid_payload(feedback_zero=feedback_zero, legacy=legacy))
    assert saved.status_code == 200, saved.json()
    assert submit_api(client).status_code == 200
    return student, ExitInterview.objects.get(pk=item.pk)


@pytest.fixture
def world(db):
    sync_policy()
    head = make_head("corr-exit-head@example.edu")
    year = make_year()
    student, item = submitted_record("corr-exit-f9@example.edu", year)
    return {"head": head, "student": student, "item": item, "year": year}


def reopen_api(user, item, body):
    client = auth_client(user)
    return client.post(
        f"/api/v1/exit-interviews/{item.pk}/reopen",
        data=json.dumps(body),
        content_type="application/json",
        **csrf(client),
    )


def raw_event(pk):
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT * FROM "{ExitInterviewReopenEvent._meta.db_table}" WHERE id = %s', [str(pk)]
        )
        return dict(zip([col.name for col in cursor.description], cursor.fetchone(), strict=True))


def resubmit(student, item):
    client = auth_client(student)
    response = client.post(f"/api/v1/exit-interviews/me/{item.pk}/submit", **csrf(client))
    assert response.status_code == 200, response.json()


def assert_no_target_or_reason(text, codes=CANONICAL):
    assert REASON not in text
    assert all(code not in text for code in codes)


# --- Catalog ---------------------------------------------------------------------------------


def test_catalog_is_unique_well_formed_and_uses_fixed_item_codes():
    values = [target.value for target in T]
    assert len(values) == len(set(values)) == 68
    assert {value for value in values if value.startswith("section.")} == {
        "section.general_information",
        "section.program_completion_and_plans",
        "section.self_assessment",
        "section.college_feedback",
        "section.suggestions",
    }
    for value in values:
        assert re.fullmatch(r"[a-z_]+(\.[A-Za-z_]+){1,2}", value), value
    assert {v.split(".", 1)[1] for v in values if v.startswith("self_assessment.")} == set(
        SelfAssessmentItem.values
    )
    assert {
        v.split(".", 1)[1]
        for v in values
        if v.startswith("college_feedback.") and not v.startswith("college_feedback.comments.")
    } == set(CollegeFeedbackItem.values)


def _editable_answer_keys() -> set[str]:
    payload = set(exit_api.ExitInterviewDraftPayload.model_fields)
    keys = payload - {"career_modes", "self_assessment_ratings", "college_feedback_ratings"}
    keys |= {"career_modes.WORK", "career_modes.STUDY"}
    keys |= {f"self_assessment_ratings.{code}" for code in SelfAssessmentItem.values}
    keys |= {f"college_feedback_ratings.{code}" for code in CollegeFeedbackItem.values}
    return keys


def test_every_editable_answer_maps_to_exactly_one_target():
    assert set(TARGET_COVERAGE) == set(T)
    covered: dict[str, ExitInterviewCorrectionTarget] = {}
    for target, keys in TARGET_COVERAGE.items():
        if target.value.startswith("section."):
            assert keys == frozenset()
            continue
        assert keys, target
        for key in keys:
            assert key not in covered, (key, covered.get(key), target)
            covered[key] = target
    assert set(covered) == _editable_answer_keys()


def test_allowed_targets_follow_the_saved_revision(world):
    f9 = world["item"]
    assert f9.form_revision_id is not None
    allowed = allowed_correction_targets(f9)
    assert len(allowed) == 64 and not allowed & PROGRAM_CHAIR_TARGETS
    _, legacy = submitted_record("corr-exit-legacy-allowed@example.edu", world["year"], legacy=True)
    assert allowed_correction_targets(legacy) == frozenset(T)


def test_normalization_dedupes_orders_bounds_and_never_echoes_input(world):
    allowed = allowed_correction_targets(world["item"])
    assert normalize_correction_targets(None, allowed=allowed) == ()
    assert normalize_correction_targets([], allowed=allowed) == ()
    assert [t.value for t in normalize_correction_targets(SELECTED, allowed=allowed)] == CANONICAL
    for bad in (["general.secret-unknown-code"], [3], [T.COLLEGE_FEEDBACK_COMMENTS_PROGRAM_CHAIR]):
        with pytest.raises(InvalidExitInterviewInput) as caught:
            normalize_correction_targets(bad, allowed=allowed)
        assert "secret-unknown" not in str(caught.value) and "program_chair" not in str(
            caught.value
        )
    with pytest.raises(InvalidExitInterviewInput, match="at most 30"):
        normalize_correction_targets([T.GENERAL_AGE.value] * 31, allowed=allowed)


# --- Lifecycle and API ------------------------------------------------------------------------


def test_head_reopens_f9_with_targets_and_history_carries_them(world):
    item = world["item"]
    response = reopen_api(world["head"], item, {"reason": REASON, "targets": SELECTED})
    assert response.status_code == 200
    assert_no_target_or_reason(response.content.decode())
    event = ExitInterviewReopenEvent.objects.get(exit_interview=item)
    stored = raw_event(event.pk)
    assert stored["targets_ciphertext"]
    assert_no_target_or_reason(json.dumps(stored, default=str))

    body = auth_client(world["student"]).get(f"/api/v1/exit-interviews/me/{item.pk}").json()
    assert body["reopen_events"] == [
        {
            "id": str(event.pk),
            "reopened_at": body["reopen_events"][0]["reopened_at"],
            "reopened_by": body["reopen_events"][0]["reopened_by"],
            "reason": REASON,
            "targets": CANONICAL,
        }
    ]
    assert body["reopen_events"][0]["reopened_by"]["display_name"] == "Head Guidance"


def test_f9_rejects_program_chair_targets_without_partial_reopen(world):
    item = world["item"]
    audits, notices = AuditEvent.objects.count(), Notification.objects.count()
    for target in PROGRAM_CHAIR_TARGETS:
        response = reopen_api(world["head"], item, {"reason": REASON, "targets": [target.value]})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_exit_interview_request"
        assert target.value not in response.content.decode()
        assert REASON not in response.content.decode()
    item.refresh_from_db()
    assert item.status == ExitInterviewStatus.SUBMITTED
    assert not ExitInterviewReopenEvent.objects.exists()
    assert (AuditEvent.objects.count(), Notification.objects.count()) == (audits, notices)


def test_legacy_null_revision_keeps_program_chair_targets_and_data(world):
    student, legacy = submitted_record("corr-exit-legacy@example.edu", world["year"], legacy=True)
    before = dict(
        ExitInterviewCollegeFeedbackRating.objects.filter(exit_interview=legacy).values_list(
            "item_code", "rating"
        )
    )
    targets = [target.value for target in PROGRAM_CHAIR_TARGETS]
    response = reopen_api(world["head"], legacy, {"reason": REASON, "targets": targets})
    assert response.status_code == 200
    legacy.refresh_from_db()
    assert legacy.form_revision_id is None
    after = dict(
        ExitInterviewCollegeFeedbackRating.objects.filter(exit_interview=legacy).values_list(
            "item_code", "rating"
        )
    )
    assert after == before and len(after) == 26
    body = auth_client(student).get(f"/api/v1/exit-interviews/me/{legacy.pk}").json()
    assert body["program_chair_comments"] == "Program Chair comment"
    assert body["reopen_events"][0]["targets"] == [
        T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_AVAILABILITY.value,
        T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_APPROACHABILITY.value,
        T.COLLEGE_FEEDBACK_PROGRAM_CHAIR_CONCERN_FOR_STUDENTS.value,
        T.COLLEGE_FEEDBACK_COMMENTS_PROGRAM_CHAIR.value,
    ]


def test_zero_rating_can_be_targeted_and_stays_zero_without_a_label(world):
    student, item = submitted_record(
        "corr-exit-zero@example.edu", world["year"], feedback_zero=True
    )
    zero_code = CollegeFeedbackItem.DEAN_AVAILABILITY
    rating = ExitInterviewCollegeFeedbackRating.objects.get(
        exit_interview=item, item_code=zero_code
    )
    assert rating.rating == 0
    target = f"college_feedback.{zero_code}"
    assert (
        reopen_api(world["head"], item, {"reason": REASON, "targets": [target]}).status_code == 200
    )
    rating.refresh_from_db()
    assert rating.rating == 0
    body = auth_client(student).get(f"/api/v1/exit-interviews/me/{item.pk}").json()
    row = next(row for row in body["college_feedback_ratings"] if row["item_code"] == zero_code)
    assert row["rating"] == 0 and set(row) == {"item_code", "item_label", "category", "rating"}
    assert body["reopen_events"][0]["targets"] == [target]
    # The draft can be resubmitted unchanged: a target never forces a different answer.
    resubmit(student, item)


def test_unsupported_saved_revision_cannot_be_reopened_into_an_unusable_draft(world):
    item = world["item"]
    unsupported = FormRevision.objects.create(
        family=FormFamily.objects.get(key="exit_interview"),
        official_code="UNSUPPORTED-F9",
        official_revision="99",
        internal_schema_version=99,
        status="INACTIVE",
    )
    ExitInterview.objects.filter(pk=item.pk).update(form_revision=unsupported)
    for body in ({"reason": REASON}, {"reason": REASON, "targets": [T.GENERAL_AGE.value]}):
        response = reopen_api(world["head"], item, body)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "exit_interview_conflict"
    item.refresh_from_db()
    assert item.status == ExitInterviewStatus.SUBMITTED
    assert not ExitInterviewReopenEvent.objects.exists()


def test_reopen_authorization_is_unchanged(world):
    item = world["item"]
    body = {"reason": REASON, "targets": [T.GENERAL_AGE.value]}
    counselor = make_user("corr-exit-counselor@example.edu", role="COUNSELOR")
    staff = make_user("corr-exit-gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    for actor in (world["student"], counselor, staff):
        response = reopen_api(actor, item, body)
        assert response.status_code == 403
        assert T.GENERAL_AGE.value not in response.content.decode()
    assert not ExitInterviewReopenEvent.objects.exists()


def test_reason_contract_requires_text_up_to_1000_characters(world):
    item = world["item"]
    for reason in ("", "x" * 1001):
        response = reopen_api(world["head"], item, {"reason": reason})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert reopen_api(world["head"], item, {"reason": "   "}).status_code == 422
    assert not ExitInterviewReopenEvent.objects.exists()
    assert reopen_api(world["head"], item, {"reason": "x" * 1000}).status_code == 200


def test_history_keeps_earlier_events_and_shows_targets_only_to_existing_readers(world):
    item, student = world["item"], world["student"]
    # An event written before this change: reason only, empty target column.
    services.reopen_for_correction(
        actor=world["head"],
        exit_interview_id=item.pk,
        reason="Earlier request",
        context=AuditContext.user(world["head"]),
    )
    resubmit(student, item)
    assert (
        reopen_api(world["head"], item, {"reason": REASON, "targets": SELECTED}).status_code == 200
    )
    resubmit(student, item)

    expected = [("Earlier request", []), (REASON, CANONICAL)]
    for reader in (student, world["head"]):
        path = (
            f"/api/v1/exit-interviews/me/{item.pk}"
            if reader is student
            else f"/api/v1/exit-interviews/{item.pk}"
        )
        events = auth_client(reader).get(path).json()["reopen_events"]
        assert [(event["reason"], event["targets"]) for event in events] == expected

    counselor = make_user("corr-exit-reader-counselor@example.edu", role="COUNSELOR")
    staff = make_user("corr-exit-reader-gss@example.edu", role="GUIDANCE_SERVICES_STAFF")
    other = make_user("corr-exit-other-student@example.edu")
    for actor, path, status in (
        (counselor, f"/api/v1/exit-interviews/{item.pk}", 403),
        (staff, f"/api/v1/exit-interviews/{item.pk}", 403),
        (other, f"/api/v1/exit-interviews/me/{item.pk}", 404),
    ):
        response = auth_client(actor).get(path)
        assert response.status_code == status
        assert_no_target_or_reason(response.content.decode())
    # Summary lists and opportunity management never carried correction content.
    for reader, path in (
        (world["head"], "/api/v1/exit-interviews"),
        (student, "/api/v1/exit-interviews/me"),
        (staff, "/api/v1/exit-interviews/opportunities"),
    ):
        response = auth_client(reader).get(path)
        assert response.status_code == 200
        assert_no_target_or_reason(response.content.decode())


def test_unknown_stored_codes_are_omitted_without_rewriting_ciphertext(world, caplog):
    item = world["item"]
    reopen_api(world["head"], item, {"reason": REASON})
    event = ExitInterviewReopenEvent.objects.get(exit_interview=item)
    future = "general.future_question"
    content.write_reopen_targets(event, [T.GENERAL_AGE.value, future])
    event.save(update_fields=["targets_ciphertext"])
    before = raw_event(event.pk)
    with caplog.at_level(logging.WARNING, logger="compass.exit_interviews.api"):
        body = auth_client(world["student"]).get(f"/api/v1/exit-interviews/me/{item.pk}").json()
    assert body["reopen_events"][0]["targets"] == [T.GENERAL_AGE.value]
    assert raw_event(event.pk) == before
    formatted = [JsonFormatter().format(record) for record in caplog.records]
    assert any("exit_interview_correction_targets_omitted" in line for line in formatted)
    assert all(future not in line and T.GENERAL_AGE.value not in line for line in formatted)


def test_unreadable_target_ciphertext_fails_closed_with_the_existing_generic_error(world):
    item = world["item"]
    reopen_api(world["head"], item, {"reason": REASON, "targets": SELECTED})
    ExitInterviewReopenEvent.objects.filter(exit_interview=item).update(
        targets_ciphertext="private-broken-token"
    )
    response = auth_client(world["student"]).get(f"/api/v1/exit-interviews/me/{item.pk}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "exit_interview_confidential_content_unavailable"
    assert "private-broken-token" not in response.content.decode()
    assert_no_target_or_reason(response.content.decode())


# --- Encryption ---------------------------------------------------------------------------------


def _event(**values):
    event = ExitInterviewReopenEvent(id=uuid4(), exit_interview_id=uuid4(), **values)
    content.write_reopen_reason(event, REASON)
    return event


def expect_unavailable(event, reader, reason):
    with pytest.raises(content.ExitInterviewConfidentialContentUnavailable) as caught:
        reader(event)
    assert caught.value.reason == reason
    assert "PRIVATE" not in str(caught.value)
    return caught.value


def test_target_envelope_is_separate_bound_and_leaves_the_reason_envelope_unchanged():
    event = _event()
    reason_token = event.reason_ciphertext
    content.write_reopen_targets(event, CANONICAL)
    assert json.loads(Fernet(K1).decrypt(event.targets_ciphertext.encode())) == {
        "schema_version": 1,
        "exit_interview_id": str(event.exit_interview_id),
        "reopen_event_id": str(event.pk),
        "content": "correction_targets",
        "payload": {"targets": CANONICAL},
    }
    assert json.loads(Fernet(K1).decrypt(reason_token.encode())) == {
        "schema_version": 1,
        "exit_interview_id": str(event.exit_interview_id),
        "reopen_event_id": str(event.pk),
        "payload": {"reason": REASON},
    }
    assert event.reason_ciphertext == reason_token
    assert content.read_reopen_reason(event) == REASON
    assert list(content.read_reopen_targets(event)) == CANONICAL


def test_target_ciphertext_cannot_be_transplanted_swapped_or_moved_across_domains(settings):
    source = _event()
    content.write_reopen_targets(source, CANONICAL)
    other_event = _event(targets_ciphertext=source.targets_ciphertext)
    other_event.exit_interview_id = source.exit_interview_id
    expect_unavailable(other_event, content.read_reopen_targets, "binding_mismatch")
    other_record = _event(targets_ciphertext=source.targets_ciphertext)
    other_record.id = source.pk
    failure = expect_unavailable(other_record, content.read_reopen_targets, "binding_mismatch")
    assert failure.content == "correction_targets" and failure.reopen_event_id == source.pk

    swapped = _event()
    swapped.id, swapped.exit_interview_id = source.pk, source.exit_interview_id
    swapped.targets_ciphertext = source.reason_ciphertext
    expect_unavailable(swapped, content.read_reopen_targets, "malformed")
    swapped.reason_ciphertext = source.targets_ciphertext
    expect_unavailable(swapped, content.read_reopen_reason, "malformed")

    # Inventory and Exit Interview use separate keyrings and different binding names.
    inventory_event = InventoryReopenEvent(id=source.pk, inventory_id=source.exit_interview_id)
    inventory_event.targets_ciphertext = source.targets_ciphertext
    with pytest.raises(inventory_content.InventoryConfidentialContentUnavailable) as caught:
        inventory_content.read_reopen_targets(inventory_event)
    assert caught.value.reason == "undecryptable"
    settings.INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K1,)
    with pytest.raises(inventory_content.InventoryConfidentialContentUnavailable) as caught:
        inventory_content.read_reopen_targets(inventory_event)
    assert caught.value.reason == "malformed"


@pytest.mark.parametrize(
    "payload",
    [
        {"targets": []},
        {"targets": ["general.age", "general.age"]},
        {"targets": [None]},
        {"targets": ["has space"]},
        {"targets": ["general.age"], "reason": REASON},
    ],
)
def test_malformed_target_payloads_fail_safely(payload):
    event = _event()
    event.targets_ciphertext = encrypt_bound_json(
        keyring=(K1,),
        schema_version=1,
        binding=content._targets_binding(event),
        payload=payload,
    )
    expect_unavailable(event, content.read_reopen_targets, "malformed")


# --- Rotation ------------------------------------------------------------------------------------


def test_rotation_rewraps_targets_and_reports_unreadable_ones(world, settings):
    item, student = world["item"], world["student"]
    reopen_api(world["head"], item, {"reason": REASON, "targets": SELECTED})
    resubmit(student, item)
    reopen_api(world["head"], item, {"reason": "Reason only"})
    with_targets, without_targets = ExitInterviewReopenEvent.objects.order_by("reopened_at")
    before = raw_event(with_targets.pk)["targets_ciphertext"]

    settings.EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = (K2, K1)
    out = StringIO()
    call_command("rotate_exit_interview_confidential_content", batch_size=1, stdout=out)
    assert (
        "Reopen Event correction targets: scanned 2; empty 1; current 0; rotated 1; failures 0"
        in out.getvalue()
    )
    after = raw_event(with_targets.pk)["targets_ciphertext"]
    assert Fernet(K1).decrypt(before.encode()) == Fernet(K2).decrypt(after.encode())
    assert Fernet(K1).extract_timestamp(before.encode()) == Fernet(K2).extract_timestamp(
        after.encode()
    )
    assert raw_event(without_targets.pk)["targets_ciphertext"] == ""
    assert_no_target_or_reason(out.getvalue())

    ExitInterviewReopenEvent.objects.filter(pk=without_targets.pk).update(
        targets_ciphertext="private-broken-token"
    )
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError, match="1 Exit Interview payload"):
        call_command(
            "rotate_exit_interview_confidential_content", batch_size=1, stdout=out, stderr=err
        )
    assert err.getvalue().splitlines() == [
        f"Unreadable: Exit Interview {item.pk}; Opportunity None; "
        f"Reopen Event {without_targets.pk} correction targets (undecryptable)"
    ]
    assert raw_event(without_targets.pk)["targets_ciphertext"] == "private-broken-token"
    assert raw_event(with_targets.pk)["targets_ciphertext"] == after
    assert "private-broken-token" not in out.getvalue() + err.getvalue()


# --- Migration -----------------------------------------------------------------------------------


EXIT_BEFORE = [("exit_interviews", "0005_saved_form_revision")]
EXIT_AFTER = [("exit_interviews", "0006_exitinterviewreopenevent_targets_ciphertext")]


@pytest.mark.django_db(transaction=True)
def test_migration_keeps_existing_reopen_events_and_adds_empty_targets_without_rewrite():
    from compass.institutional_forms.bootstrap import sync_institutional_forms

    sync_policy()
    sync_institutional_forms()
    head = make_head("corr-exit-migrate-head@example.edu")
    student, item = submitted_record("corr-exit-migrate@example.edu", make_year())
    services.reopen_for_correction(
        actor=head,
        exit_interview_id=item.pk,
        reason=REASON,
        context=AuditContext.user(head),
    )
    event = ExitInterviewReopenEvent.objects.get(exit_interview=item)
    table = ExitInterviewReopenEvent._meta.db_table
    reason_before = raw_event(event.pk)["reason_ciphertext"]

    def column():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'targets_ciphertext'",
                [table],
            )
            return cursor.fetchone()

    def filenode():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_relation_filenode(%s)", [table])
            return cursor.fetchone()[0]

    executor = MigrationExecutor(connection)
    try:
        executor.migrate(EXIT_BEFORE)
        assert column() is None
        node = filenode()
        executor = MigrationExecutor(connection)
        executor.migrate(EXIT_AFTER)
        assert filenode() == node
        assert column() == ("NO", None)
        row = raw_event(event.pk)
        assert row["reason_ciphertext"] == reason_before and row["targets_ciphertext"] == ""
        body = auth_client(student).get(f"/api/v1/exit-interviews/me/{item.pk}").json()
        assert body["reopen_events"][0]["reason"] == REASON
        assert body["reopen_events"][0]["targets"] == []
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


# --- Privacy -------------------------------------------------------------------------------------


def test_targets_and_reason_never_reach_notifications_audit_actions_logs_or_pdfs(world, caplog):
    item, student = world["item"], world["student"]
    with caplog.at_level(logging.DEBUG):
        assert (
            reopen_api(world["head"], item, {"reason": REASON, "targets": SELECTED}).status_code
            == 200
        )
        client = auth_client(student)
        assert client.get(f"/api/v1/exit-interviews/me/{item.pk}").status_code == 200
        actions = client.get("/api/v1/student-actions")
        assert actions.status_code == 200
        assert_no_target_or_reason(actions.content.decode())
    assert any(record.name == "compass.request" for record in caplog.records)
    for record in caplog.records:
        assert_no_target_or_reason(JsonFormatter().format(record))
        assert_no_target_or_reason(record.getMessage())

    notification = Notification.objects.get(recipient=student, event_code="exit_interview.reopened")
    assert_no_target_or_reason(f"{notification.title} {notification.message}")
    assert_no_target_or_reason(str(render_notification_email("exit_interview.reopened")))
    assert_no_target_or_reason(str(push_body_for("exit_interview.reopened")))
    audit = AuditEvent.objects.get(action="exit_interview.reopened", target_id=str(item.pk))
    assert not any("target" in key for key in audit.metadata)
    assert_no_target_or_reason(
        json.dumps(list(AuditEvent.objects.values_list("metadata", flat=True)))
    )

    resubmit(student, item)
    pdf = auth_client(student).get(f"/api/v1/exit-interviews/me/{item.pk}/pdf")
    assert pdf.status_code == 200
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert_no_target_or_reason(text)
