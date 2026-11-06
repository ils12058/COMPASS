"""Disposable PostgreSQL upgrades through guidance_messages 0002; synthetic sentinels only."""

from __future__ import annotations

import copy
import uuid

import pytest
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor

BASE = ("guidance_messages", "0001_canonical_baseline")
TARGET = ("guidance_messages", "0002_kinds_and_participants")
THREAD_TABLE = "guidance_messages_guidancethread"
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

    MigrationExecutor(db).migrate([TARGET])
    after = snapshot(db, state_at(db, TARGET), thread_pk, message_pk)

    assert legacy_only(after["thread"]) == before["thread"]
    assert all(after["thread"][name] is None for name in NEW_COLUMNS)
    assert after["message"] == before["message"]
    assert before["message"]["body_ciphertext"] == "preservation-sentinel"
    assert before["message"]["sequence"] == 1
    assert set(NEW_COLUMNS) <= current_columns(db)
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
