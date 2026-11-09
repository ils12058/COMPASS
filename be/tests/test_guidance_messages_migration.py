"""Disposable PostgreSQL upgrades through guidance_messages 0006; synthetic sentinels only."""

from __future__ import annotations

import copy
import uuid
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BASE = ("guidance_messages", "0001_canonical_baseline")
TARGET_0002 = ("guidance_messages", "0002_kinds_and_participants")
TARGET = ("guidance_messages", "0003_faculty_inquiry")
TARGET_0004 = ("guidance_messages", "0004_referral_coordination")
TARGET_0005 = ("guidance_messages", "0005_counselor_direct")
TARGET_0006 = ("guidance_messages", "0006_case_coordination")
THREAD_TABLE = "guidance_messages_guidancethread"
INQUIRY_INDEX = "gm_inquiry_requester_idx"
KIND_CODES = (
    "OFFICE",
    "COUNSELING",
    "FACULTY_INQUIRY",
    "REFERRAL_COORDINATION",
    "COUNSELOR_DIRECT",
    "COUNSELOR_CASE_COORDINATION",
)
NEW_COLUMNS = (
    "requester_id",
    "direct_first_user_id",
    "direct_second_user_id",
    "student_subject_id",
    "relationship_referral_id",
    "relationship_case_grant_id",
)


@pytest.fixture
def baseline_database(django_db_blocker, request):
    """One throwaway database on the test server only; no deployed connection is opened."""
    name = "gm_kinds_" + uuid.uuid4().hex
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
        config = copy.deepcopy(connection.settings_dict)
        config["NAME"] = name
        connections.databases[name] = config
        db = connections[name]
        try:
            executor = MigrationExecutor(db)
            targets = other_leaves(executor) + [BASE]
            if hasattr(request, "param"):
                targets = [
                    request.param if node[0] == request.param[0] else node for node in targets
                ]
            executor.migrate(targets)
            yield db, executor.loader.project_state(targets).apps
        finally:
            db.close()
            del connections[name]
            del connections.databases[name]
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE "{name}"')


def seed_legacy_rows(db, apps):
    alias = db.alias

    def manager(app, model):
        return apps.get_model(app, model).objects.using(alias)

    student, _ = manager("accounts", "Role").get_or_create(
        code="STUDENT", defaults={"name": "Student"}
    )
    person = manager("accounts", "User").create(
        role_id=student.pk,
        email="gm-migration@example.invalid",
        first_name="Synthetic",
        last_name="Student",
        profile_confidential_content_ciphertext="preservation-sentinel",
    )
    campus = manager("organization", "Campus").create(code="GMMIG", name="Synthetic Campus")
    college = manager("organization", "College").create(
        campus_id=campus.pk, code="GMMIG-C", name="Synthetic College"
    )
    thread = manager("guidance_messages", "GuidanceThread").create(
        kind="OFFICE",
        status="OPEN",
        student_id=person.pk,
        routing_college_id=college.pk,
        created_by_id=person.pk,
        last_sequence=1,
    )
    message = manager("guidance_messages", "GuidanceMessage").create(
        thread_id=thread.pk,
        sender_id=person.pk,
        sequence=1,
        client_message_id=uuid.uuid4(),
        body_ciphertext="preservation-sentinel",
    )
    return thread.pk, message.pk


def seed_faculty_inquiry(db, apps):
    """A 0003-shaped inquiry: requester set, every other family column null, one message."""
    alias = db.alias

    def manager(app, model):
        return apps.get_model(app, model).objects.using(alias)

    faculty, _ = manager("accounts", "Role").get_or_create(
        code="FACULTY", defaults={"name": "Faculty"}
    )
    person = manager("accounts", "User").create(
        role_id=faculty.pk,
        email="gm-inquiry@example.invalid",
        first_name="Synthetic",
        last_name="Faculty",
        profile_confidential_content_ciphertext="preservation-sentinel",
    )
    thread = manager("guidance_messages", "GuidanceThread").create(
        kind="FACULTY_INQUIRY",
        status="OPEN",
        requester_id=person.pk,
        created_by_id=person.pk,
        last_sequence=1,
    )
    message = manager("guidance_messages", "GuidanceMessage").create(
        thread_id=thread.pk,
        sender_id=person.pk,
        sequence=1,
        client_message_id=uuid.uuid4(),
        body_ciphertext="preservation-sentinel",
    )
    return thread.pk, message.pk


def rows(db, apps, thread_pk, message_pk):
    thread_model = apps.get_model("guidance_messages", "GuidanceThread")
    message_model = apps.get_model("guidance_messages", "GuidanceMessage")
    return (
        thread_model.objects.using(db.alias).get(pk=thread_pk),
        message_model.objects.using(db.alias).get(pk=message_pk),
    )


def stored_fields(instance):
    return {key: value for key, value in instance.__dict__.items() if not key.startswith("_")}


def snapshot(db, apps, thread_pk, message_pk):
    thread, message = rows(db, apps, thread_pk, message_pk)
    return {"thread": stored_fields(thread), "message": stored_fields(message)}


def current_columns(db):
    with db.cursor() as cursor:
        description = db.introspection.get_table_description(cursor, THREAD_TABLE)
    return {column.name for column in description}


def constraint_names(db):
    """Both catalogs: CHECKs live in pg_constraint, partial uniqueness in pg_indexes."""
    with db.cursor() as cursor:
        cursor.execute(
            "select conname from pg_constraint where conrelid = %s::regclass"
            " union all select indexname from pg_indexes where tablename = %s",
            [THREAD_TABLE, THREAD_TABLE],
        )
        return {row[0] for row in cursor.fetchall()}


def column_nulls(db):
    with db.cursor() as cursor:
        description = db.introspection.get_table_description(cursor, THREAD_TABLE)
    return {column.name: column.null_ok for column in description}


def index_definitions(db):
    with db.cursor() as cursor:
        cursor.execute(
            "select indexname, indexdef from pg_indexes where tablename = %s",
            [THREAD_TABLE],
        )
        return dict(cursor.fetchall())


def family_shape_sql(db):
    """Decompiled text of the live allowlist CHECK; branches are AND-terms joined by ` OR `."""
    with db.cursor() as cursor:
        cursor.execute(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = %s",
            ["gm_thread_family_shape"],
        )
        return cursor.fetchone()[0]


def family_shape_branches(db):
    """Map kinds to live branches; 0002's inquiry omits assigned_to/routing_college."""
    return {
        kind: branch
        for branch in family_shape_sql(db).split(" OR ")
        for kind in KIND_CODES
        if f"'{kind}'" in branch
    }


def applied_guidance_messages(db):
    with db.cursor() as cursor:
        cursor.execute("select name from django_migrations where app = 'guidance_messages'")
        return {row[0] for row in cursor.fetchall()}


def other_leaves(executor):
    return [node for node in executor.loader.graph.leaf_nodes() if node[0] != "guidance_messages"]


def state_at(db, target):
    """The model state a database would see with `guidance_messages` pinned at `target`."""
    executor = MigrationExecutor(db)
    return executor.loader.project_state(other_leaves(executor) + [target]).apps


def legacy_only(thread):
    return {key: value for key, value in thread.items() if key not in NEW_COLUMNS}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "baseline_database", [("ecounseling", "0001_canonical_baseline")], indirect=True
)
def test_recording_only_upgrade_purges_the_migrated_database(baseline_database, monkeypatch):
    """Upgrading another database must purge its transcripts and preserve default recordings."""
    from compass.ecounseling.models import (
        ECounselingConsent,
        ECounselingMediaCapture,
        ECounselingRoom,
    )
    from tests.test_counseling import make_appointment
    from tests.test_counseling_finish import setup_domain

    _, counselor, student, service = setup_domain("recording-migration-isolation")
    appointment = make_appointment(student=student, provider=counselor, service=service)
    default_room = ECounselingRoom.objects.create(
        appointment=appointment, daily_room_name="default-recording-sentinel"
    )
    default_capture = ECounselingMediaCapture.objects.create(room=default_room, kind="RECORDING")
    default_consent = ECounselingConsent.objects.create(
        room=default_room, requested_by=student, scope="AUDIO_VIDEO_RECORDING"
    )
    default_snapshot = (
        ECounselingMediaCapture.objects.values().get(pk=default_capture.pk),
        ECounselingConsent.objects.values().get(pk=default_consent.pk),
    )

    db, apps = baseline_database
    thread_pk, _ = seed_legacy_rows(db, apps)
    thread = (
        apps.get_model("guidance_messages", "GuidanceThread")
        .objects.using(db.alias)
        .get(pk=thread_pk)
    )

    def manager(app, model):
        return apps.get_model(app, model).objects.using(db.alias)

    now = timezone.now()
    service = manager("service_catalog", "Service").create(
        code="RECORDING_MIGRATION", name="Synthetic recording migration"
    )
    appointment = manager("appointments", "Appointment").create(
        reference_code="RECORDING-MIGRATION",
        student_id=thread.student_id,
        provider_id=thread.student_id,
        service_id=service.pk,
        delivery_mode="ONLINE",
        starts_at=now,
        ends_at=now + timedelta(hours=1),
        created_by_id=thread.student_id,
    )
    room = manager("ecounseling", "ECounselingRoom").create(
        appointment_id=appointment.pk, daily_room_name="migrated-recording-sentinel"
    )
    captures = manager("ecounseling", "ECounselingMediaCapture")
    artifacts = manager("ecounseling", "ECounselingMediaArtifact")
    receipts = manager("ecounseling", "DailyWebhookReceipt")
    reconciliations = manager("ecounseling", "ECounselingCaptureReconciliation")
    consents = manager("ecounseling", "ECounselingConsent")
    transcription = captures.create(room_id=room.pk, kind="TRANSCRIPTION")
    recording = captures.create(room_id=room.pk, kind="RECORDING")
    artifacts.create(capture_id=transcription.pk, object_key="synthetic/transcript-to-delete")
    recording_artifact = artifacts.create(capture_id=recording.pk)
    receipts.create(
        capture_id=transcription.pk,
        provider_event_id="transcript-event",
        event_type="transcript.ready",
    )
    recording_receipt = receipts.create(
        capture_id=recording.pk, provider_event_id="recording-event", event_type="recording.started"
    )
    reconciliations.create(capture_id=transcription.pk, uncertainty_since=now)
    recording_reconciliation = reconciliations.create(
        capture_id=recording.pk, uncertainty_since=now
    )
    for scope in ("SESSION_MEDIA_CAPTURE", "LIVE_TRANSCRIPTION", "TRANSCRIPT_STORAGE"):
        consents.create(room_id=room.pk, requested_by_id=thread.student_id, scope=scope)

    deleted_keys = []

    class SyntheticStorage:
        def __init__(self, *, alias):
            pass

        def delete(self, key):
            deleted_keys.append(key)

    monkeypatch.setattr("compass.integrations.storage.ObjectStorage", SyntheticStorage)
    target = ("ecounseling", "0002_recording_only")
    MigrationExecutor(db).migrate([target])
    current = MigrationExecutor(db).loader.project_state([BASE, target]).apps

    def remaining(model):
        return current.get_model("ecounseling", model).objects.using(db.alias)

    assert deleted_keys == ["synthetic/transcript-to-delete"]
    assert list(remaining("ECounselingMediaCapture").values_list("pk", flat=True)) == [recording.pk]
    assert list(remaining("ECounselingMediaArtifact").values_list("pk", flat=True)) == [
        recording_artifact.pk
    ]
    assert list(remaining("DailyWebhookReceipt").values_list("pk", flat=True)) == [
        recording_receipt.pk
    ]
    assert list(remaining("ECounselingCaptureReconciliation").values_list("pk", flat=True)) == [
        recording_reconciliation.pk
    ]
    assert list(remaining("ECounselingConsent").values_list("scope", flat=True)) == [
        "AUDIO_VIDEO_RECORDING"
    ]
    assert (
        ECounselingMediaCapture.objects.values().get(pk=default_capture.pk),
        ECounselingConsent.objects.values().get(pk=default_consent.pk),
    ) == default_snapshot


@pytest.mark.django_db(transaction=True)
def test_upgrade_from_0001_preserves_legacy_rows_and_adds_constraints(baseline_database):
    db, apps = baseline_database
    thread_pk, message_pk = seed_legacy_rows(db, apps)
    before = snapshot(db, apps, thread_pk, message_pk)
    assert not set(NEW_COLUMNS) & current_columns(db)
    assert INQUIRY_INDEX not in index_definitions(db)
    assert column_nulls(db)["student_id"] is False

    MigrationExecutor(db).migrate([TARGET])
    after = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)

    assert legacy_only(after["thread"]) == before["thread"]
    assert all(after["thread"][name] is None for name in NEW_COLUMNS)
    assert after["message"] == before["message"]
    assert before["message"]["body_ciphertext"] == "preservation-sentinel"
    assert before["message"]["sequence"] == 1
    assert set(NEW_COLUMNS) <= current_columns(db)
    assert column_nulls(db)["student_id"] is True
    assert INQUIRY_INDEX in index_definitions(db)
    assert "FACULTY_INQUIRY" in index_definitions(db)[INQUIRY_INDEX].upper()
    assert {
        "gm_thread_family_shape",
        "gm_direct_pair_ordered",
        "gm_one_thread_per_referral",
        "gm_direct_pair_unique",
        "gm_case_grant_subject_unique",
        "gm_one_open_office_per_student",
        "gm_thread_resolution_shape",
    } <= constraint_names(db)


@pytest.mark.django_db(transaction=True)
def test_reverse_to_0001_and_reapply_is_lossless(baseline_database):
    db, apps = baseline_database
    thread_pk, message_pk = seed_legacy_rows(db, apps)
    before = snapshot(db, apps, thread_pk, message_pk)
    MigrationExecutor(db).migrate([TARGET])
    forward = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)

    MigrationExecutor(db).migrate([BASE])
    backward = snapshot(db, state_at(db, BASE), thread_pk, message_pk)
    assert legacy_only(backward["thread"]) == legacy_only(forward["thread"]) == before["thread"]
    assert backward["message"] == forward["message"]
    assert not set(NEW_COLUMNS) & current_columns(db)
    assert "gm_direct_pair_ordered" not in constraint_names(db)
    assert "gm_thread_family_shape" in constraint_names(db)

    MigrationExecutor(db).migrate([TARGET])
    reapplied = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)
    assert reapplied == forward
    assert all(reapplied["thread"][name] is None for name in NEW_COLUMNS)


@pytest.mark.django_db(transaction=True)
def test_reverse_to_0002_without_inquiries_is_lossless_and_reapplies(baseline_database):
    db, apps = baseline_database
    thread_pk, message_pk = seed_legacy_rows(db, apps)
    MigrationExecutor(db).migrate([TARGET])
    forward = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)

    MigrationExecutor(db).migrate([TARGET_0002])
    backward = snapshot(db, state_at(db, TARGET_0002), thread_pk, message_pk)
    assert backward == forward
    assert column_nulls(db)["student_id"] is False
    assert INQUIRY_INDEX not in index_definitions(db)
    inquiry_branch = family_shape_branches(db)["FACULTY_INQUIRY"]
    assert "routing_college_id" not in inquiry_branch
    assert "assigned_to_id" not in inquiry_branch
    assert applied_guidance_messages(db) == {
        "0001_canonical_baseline",
        "0002_kinds_and_participants",
    }

    MigrationExecutor(db).migrate([TARGET])
    assert snapshot(db, state_at(db, TARGET), thread_pk, message_pk) == forward
    assert column_nulls(db)["student_id"] is True
    assert INQUIRY_INDEX in index_definitions(db)
    inquiry_branch = family_shape_branches(db)["FACULTY_INQUIRY"]
    assert "(student_id IS NULL)" in inquiry_branch
    assert "(requester_id IS NOT NULL)" in inquiry_branch
    assert "(routing_college_id IS NULL)" in inquiry_branch
    assert "(assigned_to_id IS NULL)" in inquiry_branch
    assert applied_guidance_messages(db) == {
        "0001_canonical_baseline",
        "0002_kinds_and_participants",
        "0003_faculty_inquiry",
    }


@pytest.mark.django_db(transaction=True)
def test_reverse_with_an_inquiry_fails_and_leaves_row_and_schema_intact(baseline_database):
    db, apps = baseline_database
    legacy_pk, legacy_message_pk = seed_legacy_rows(db, apps)
    MigrationExecutor(db).migrate([TARGET])
    state = state_at(db, TARGET)
    inquiry_pk, inquiry_message_pk = seed_faculty_inquiry(db, state)
    inquiry_before = snapshot(db, state, inquiry_pk, inquiry_message_pk)
    legacy_before = snapshot(db, state, legacy_pk, legacy_message_pk)
    assert inquiry_before["thread"]["kind"] == "FACULTY_INQUIRY"
    assert inquiry_before["thread"]["student_id"] is None
    assert inquiry_before["message"]["body_ciphertext"] == "preservation-sentinel"

    with pytest.raises(RuntimeError, match="1 Faculty inquiry thread"):
        MigrationExecutor(db).migrate([TARGET_0002])

    after = state_at(db, TARGET)
    assert snapshot(db, after, inquiry_pk, inquiry_message_pk) == inquiry_before
    assert snapshot(db, after, legacy_pk, legacy_message_pk) == legacy_before
    threads = after.get_model("guidance_messages", "GuidanceThread").objects.using(db.alias)
    assert threads.count() == 2
    assert applied_guidance_messages(db) == {
        "0001_canonical_baseline",
        "0002_kinds_and_participants",
        "0003_faculty_inquiry",
    }
    assert column_nulls(db)["student_id"] is True
    assert INQUIRY_INDEX in index_definitions(db)
    inquiry_branch = family_shape_branches(db)["FACULTY_INQUIRY"]
    assert "(routing_college_id IS NULL)" in inquiry_branch
    assert "(assigned_to_id IS NULL)" in inquiry_branch


def seed_referral_source(db, apps):
    """A minimal legacy-shaped Referral plus the requester a referral thread needs."""
    alias = db.alias

    def manager(app, model):
        return apps.get_model(app, model).objects.using(alias)

    faculty, _ = manager("accounts", "Role").get_or_create(
        code="FACULTY", defaults={"name": "Faculty"}
    )
    requester = manager("accounts", "User").create(
        role_id=faculty.pk,
        email="gm-referral-requester@example.invalid",
        first_name="Synthetic",
        last_name="Faculty",
        profile_confidential_content_ciphertext="preservation-sentinel",
    )
    student = manager("accounts", "User").get(email="gm-migration@example.invalid")
    college = manager("organization", "College").get(code="GMMIG-C")
    family = manager("institutional_forms", "FormFamily").create(
        key="gm-migration-referral", title="Synthetic Referral Family"
    )
    revision = manager("institutional_forms", "FormRevision").create(
        family_id=family.pk, internal_schema_version=1
    )
    referral = manager("referrals", "Referral").create(
        reference_code="GMMIG-REF-1",
        student_id=student.pk,
        student_name_snapshot="Synthetic Student",
        course_year_block_snapshot="Synthetic Program 1-1",
        confidential_content_ciphertext="preservation-sentinel",
        referred_on=date(2026, 11, 6),
        form_revision_id=revision.pk,
        submission_channel="GCO_RECORDED",
    )
    return requester.pk, student.pk, college.pk, referral.pk


@pytest.mark.django_db(transaction=True)
def test_0004_activates_referral_coordination_without_schema_change(baseline_database):
    db, apps = baseline_database
    thread_pk, message_pk = seed_legacy_rows(db, apps)
    MigrationExecutor(db).migrate([TARGET])
    before = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)

    MigrationExecutor(db).migrate([TARGET_0004])
    state = state_at(db, TARGET_0004)
    assert applied_guidance_messages(db) == {
        "0001_canonical_baseline",
        "0002_kinds_and_participants",
        "0003_faculty_inquiry",
        "0004_referral_coordination",
    }
    thread_model = state.get_model("guidance_messages", "GuidanceThread")
    choices = dict(thread_model._meta.get_field("kind").choices)
    assert choices["REFERRAL_COORDINATION"] == "Referral coordination"
    assert snapshot(db, state, thread_pk, message_pk) == before

    requester_pk, student_pk, college_pk, referral_pk = seed_referral_source(db, state)
    threads = thread_model.objects.using(db.alias)
    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="REFERRAL_COORDINATION",
            requester_id=requester_pk,
            relationship_referral_id=referral_pk,
            routing_college_id=college_pk,
            created_by_id=requester_pk,
        )
    thread = threads.create(
        kind="REFERRAL_COORDINATION",
        requester_id=requester_pk,
        relationship_referral_id=referral_pk,
        student_subject_id=student_pk,
        routing_college_id=college_pk,
        created_by_id=requester_pk,
        last_sequence=1,
    )
    stored = threads.get(pk=thread.pk)
    assert stored.requester_id == requester_pk
    assert stored.relationship_referral_id == referral_pk
    assert stored.student_subject_id == student_pk
    assert stored.routing_college_id == college_pk

    MigrationExecutor(db).migrate([TARGET])
    assert applied_guidance_messages(db) == {
        "0001_canonical_baseline",
        "0002_kinds_and_participants",
        "0003_faculty_inquiry",
    }
    reversed_state = state_at(db, TARGET)
    kept = (
        reversed_state.get_model("guidance_messages", "GuidanceThread")
        .objects.using(db.alias)
        .get(pk=thread.pk)
    )
    assert kept.kind == "REFERRAL_COORDINATION"
    assert kept.relationship_referral_id == referral_pk


def seed_direct_counselors(db, apps):
    """Two synthetic COUNSELOR accounts through the historical model state."""
    alias = db.alias

    def manager(app, model):
        return apps.get_model(app, model).objects.using(alias)

    counselor, _ = manager("accounts", "Role").get_or_create(
        code="COUNSELOR", defaults={"name": "Counselor"}
    )
    pks = []
    for name in ("First", "Second"):
        person = manager("accounts", "User").create(
            role_id=counselor.pk,
            email=f"gm-direct-{name.lower()}@example.invalid",
            first_name="Synthetic",
            last_name=name,
            profile_confidential_content_ciphertext="preservation-sentinel",
        )
        pks.append(person.pk)
    return tuple(pks)


@pytest.mark.django_db(transaction=True)
def test_0005_activates_counselor_direct_without_schema_change(baseline_database):
    db, apps = baseline_database
    legacy_thread_pk, legacy_message_pk = seed_legacy_rows(db, apps)
    MigrationExecutor(db).migrate([TARGET_0004])
    state_0004 = state_at(db, TARGET_0004)
    requester_pk, student_pk, college_pk, referral_pk = seed_referral_source(db, state_0004)
    referral_thread_model = state_0004.get_model("guidance_messages", "GuidanceThread")
    referral_thread = referral_thread_model.objects.using(db.alias).create(
        kind="REFERRAL_COORDINATION",
        requester_id=requester_pk,
        relationship_referral_id=referral_pk,
        student_subject_id=student_pk,
        routing_college_id=college_pk,
        created_by_id=requester_pk,
        last_sequence=1,
    )
    referral_message = (
        state_0004.get_model("guidance_messages", "GuidanceMessage")
        .objects.using(db.alias)
        .create(
            thread_id=referral_thread.pk,
            sender_id=requester_pk,
            sequence=1,
            client_message_id=uuid.uuid4(),
            body_ciphertext="preservation-sentinel",
        )
    )
    before_legacy = snapshot(db, state_0004, legacy_thread_pk, legacy_message_pk)
    before_referral = snapshot(db, state_0004, referral_thread.pk, referral_message.pk)

    MigrationExecutor(db).migrate([TARGET_0005])
    state = state_at(db, TARGET_0005)
    assert "0005_counselor_direct" in applied_guidance_messages(db)
    thread_model = state.get_model("guidance_messages", "GuidanceThread")
    choices = dict(thread_model._meta.get_field("kind").choices)
    assert choices["COUNSELOR_DIRECT"] == "Counselor direct"
    assert snapshot(db, state, legacy_thread_pk, legacy_message_pk) == before_legacy
    assert snapshot(db, state, referral_thread.pk, referral_message.pk) == before_referral

    first_counselor_pk, second_counselor_pk = seed_direct_counselors(db, state)
    first_id, second_id = sorted((first_counselor_pk, second_counselor_pk))
    threads = thread_model.objects.using(db.alias)
    direct = threads.create(
        kind="COUNSELOR_DIRECT",
        direct_first_user_id=first_id,
        direct_second_user_id=second_id,
        created_by_id=first_id,
        last_sequence=1,
    )
    stored = threads.get(pk=direct.pk)
    assert stored.kind == "COUNSELOR_DIRECT"
    assert (stored.direct_first_user_id, stored.direct_second_user_id) == (first_id, second_id)
    assert stored.created_by_id == first_id
    for name in NEW_COLUMNS[:1] + NEW_COLUMNS[3:]:
        assert getattr(stored, name) is None, name

    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_DIRECT",
            direct_first_user_id=second_id,
            direct_second_user_id=first_id,
            created_by_id=first_id,
        )
    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_DIRECT",
            direct_first_user_id=first_id,
            direct_second_user_id=second_id,
            created_by_id=second_id,
        )
    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_DIRECT",
            direct_first_user_id=first_id,
            direct_second_user_id=second_id,
            student_id=student_pk,
            created_by_id=first_id,
        )

    MigrationExecutor(db).migrate([TARGET_0004])
    assert "0005_counselor_direct" not in applied_guidance_messages(db)
    reversed_state = state_at(db, TARGET_0004)
    kept = (
        reversed_state.get_model("guidance_messages", "GuidanceThread")
        .objects.using(db.alias)
        .get(pk=direct.pk)
    )
    assert kept.kind == "COUNSELOR_DIRECT"
    assert (kept.direct_first_user_id, kept.direct_second_user_id) == (first_id, second_id)


@pytest.mark.django_db(transaction=True)
def test_0006_activates_case_coordination_choices_and_shape(baseline_database):
    db, apps = baseline_database
    legacy_thread_pk, legacy_message_pk = seed_legacy_rows(db, apps)
    MigrationExecutor(db).migrate([TARGET_0005])
    before = snapshot(db, state_at(db, TARGET_0005), legacy_thread_pk, legacy_message_pk)
    assert "0006_case_coordination" not in applied_guidance_messages(db)

    MigrationExecutor(db).migrate([TARGET_0006])
    state = state_at(db, TARGET_0006)
    assert "0006_case_coordination" in applied_guidance_messages(db)
    thread_model = state.get_model("guidance_messages", "GuidanceThread")
    choices = dict(thread_model._meta.get_field("kind").choices)
    assert set(choices) == set(KIND_CODES)
    assert choices["COUNSELOR_CASE_COORDINATION"] == "Counselor case coordination"
    assert snapshot(db, state, legacy_thread_pk, legacy_message_pk) == before
    assert "gm_case_grant_subject_unique" in constraint_names(db)
    case_branch = family_shape_branches(db)["COUNSELOR_CASE_COORDINATION"]
    assert "(relationship_case_grant_id IS NOT NULL)" in case_branch
    assert "(student_subject_id IS NOT NULL)" in case_branch
    assert "(student_id IS NULL)" in case_branch
    assert "(routing_college_id IS NULL)" in case_branch
    assert "(assigned_to_id IS NULL)" in case_branch

    student_pk = (
        state.get_model("accounts", "User")
        .objects.using(db.alias)
        .get(email="gm-migration@example.invalid")
        .pk
    )
    first_counselor_pk, second_counselor_pk = seed_direct_counselors(db, state)
    now = timezone.now()
    grant_model = state.get_model("counseling", "CounselorCaseContinuityGrant")
    grant = grant_model.objects.using(db.alias).create(
        student_id=student_pk,
        original_counselor_id=first_counselor_pk,
        receiving_counselor_id=second_counselor_pk,
        coverage_kind="PLANNED_HANDOFF",
        reason_category="PLANNED_ABSENCE",
        requested_by_id=first_counselor_pk,
        requested_at=now,
        starts_at=now,
        expires_at=now + timedelta(hours=1),
        decision="REQUESTED",
        policy_version="synthetic-v1",
        policy_evidence="TEST-ONLY-MIGRATION",
        policy_digest="a" * 64,
        student_placement_marker="SYNTHETIC-MARKER",
        snapshot_digest="b" * 64,
        request_id=uuid.uuid4(),
    )
    assert grant.communication_purpose is None
    assert grant.communication_policy_digest == ""

    threads = thread_model.objects.using(db.alias)
    case_thread = threads.create(
        kind="COUNSELOR_CASE_COORDINATION",
        relationship_case_grant_id=grant.pk,
        student_subject_id=student_pk,
        created_by_id=first_counselor_pk,
        last_sequence=1,
    )
    stored = threads.get(pk=case_thread.pk)
    assert stored.kind == "COUNSELOR_CASE_COORDINATION"
    assert stored.relationship_case_grant_id == grant.pk
    assert stored.student_subject_id == student_pk
    assert stored.created_by_id == first_counselor_pk
    for name in (
        "student_id",
        "counselor_id",
        "requester_id",
        "direct_first_user_id",
        "direct_second_user_id",
        "relationship_referral_id",
        "relationship_appointment_id",
        "routing_college_id",
        "assigned_to_id",
    ):
        assert getattr(stored, name) is None, name

    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_CASE_COORDINATION",
            relationship_case_grant_id=grant.pk,
            created_by_id=first_counselor_pk,
        )
    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_CASE_COORDINATION",
            relationship_case_grant_id=grant.pk,
            student_subject_id=student_pk,
            student_id=student_pk,
            created_by_id=first_counselor_pk,
        )
    with pytest.raises(IntegrityError), transaction.atomic(using=db.alias):
        threads.create(
            kind="COUNSELOR_CASE_COORDINATION",
            relationship_case_grant_id=grant.pk,
            student_subject_id=student_pk,
            created_by_id=second_counselor_pk,
        )

    MigrationExecutor(db).migrate([TARGET_0005])
    assert "0006_case_coordination" not in applied_guidance_messages(db)
    reversed_state = state_at(db, TARGET_0005)
    reversed_model = reversed_state.get_model("guidance_messages", "GuidanceThread")
    assert "COUNSELOR_CASE_COORDINATION" not in dict(reversed_model._meta.get_field("kind").choices)
    kept = reversed_model.objects.using(db.alias).get(pk=case_thread.pk)
    assert kept.kind == "COUNSELOR_CASE_COORDINATION"
    assert kept.relationship_case_grant_id == grant.pk
    assert kept.student_subject_id == student_pk

    MigrationExecutor(db).migrate([TARGET_0006])
    reapplied_model = state_at(db, TARGET_0006).get_model("guidance_messages", "GuidanceThread")
    reapplied = reapplied_model.objects.using(db.alias).get(pk=case_thread.pk)
    assert reapplied.kind == "COUNSELOR_CASE_COORDINATION"
    assert reapplied.relationship_case_grant_id == grant.pk
    assert reapplied.student_subject_id == student_pk
    assert snapshot(db, state_at(db, TARGET_0006), legacy_thread_pk, legacy_message_pk) == before
