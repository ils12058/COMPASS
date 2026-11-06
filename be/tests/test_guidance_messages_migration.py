"""Disposable PostgreSQL upgrades through guidance_messages 0003; synthetic sentinels only."""

from __future__ import annotations

import copy
import uuid

import pytest
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor

BASE = ("guidance_messages", "0001_canonical_baseline")
TARGET_0002 = ("guidance_messages", "0002_kinds_and_participants")
TARGET = ("guidance_messages", "0003_faculty_inquiry")
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
def baseline_database(django_db_blocker):
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
    """kind -> its live allowlist branch; 0002's inquiry branch omits assigned_to/routing_college."""
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
