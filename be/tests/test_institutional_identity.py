from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.inventory.services import (
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import Campus, College, Program
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    institutional_id: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Identity",
        last_name="User",
        institutional_id=institutional_id,
    )


def admin_client() -> tuple[Client, User]:
    admin = make_user(
        "identity-admin@example.edu",
        role="IT_ADMIN",
        institutional_id="EMP-0001",
    )
    now = timezone.now()
    issued = create_auth_session(admin, mfa_verified_at=now, now=now)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client, admin


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


@pytest.mark.django_db
def test_institutional_id_normalizes_text_and_legacy_null_remains_valid():
    sync_policy()
    populated = make_user(
        "normalized-id@example.edu",
        institutional_id="  ucn-000123  ",
    )
    legacy = make_user("legacy-null-id@example.edu")

    assert populated.institutional_id == "UCN-000123"
    assert legacy.institutional_id is None

    legacy.institutional_id = "   "
    legacy.save(update_fields=["institutional_id", "updated_at"])
    legacy.refresh_from_db()
    assert legacy.institutional_id is None


@pytest.mark.django_db
def test_database_rejects_case_only_institutional_id_collision():
    sync_policy()
    role = Role.objects.get(code="STUDENT")
    make_user("first-id@example.edu", institutional_id="UCN-0042")

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.bulk_create(
            [
                User(
                    email="second-id@example.edu",
                    institutional_id="ucn-0042",
                    password="!",
                    role=role,
                    first_name="Second",
                    last_name="User",
                )
            ]
        )


@pytest.mark.django_db
def test_managed_create_search_correction_and_profile_are_institutional_id_safe():
    sync_policy()
    client, admin = admin_client()

    missing = client.post(
        "/api/v1/accounts",
        data=json.dumps(
            {
                "email": "missing-id@example.edu",
                "first_name": "Missing",
                "last_name": "Id",
                "role": "COUNSELOR",
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert missing.status_code == 422

    created_response = client.post(
        "/api/v1/accounts",
        data=json.dumps(
            {
                "institutional_id": " ucn-2026-001 ",
                "email": "managed@example.edu",
                "first_name": "Managed",
                "last_name": "User",
                "role": "COUNSELOR",
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert created_response.status_code == 201
    created = User.objects.get(email="managed@example.edu")
    assert created.institutional_id == "UCN-2026-001"
    assert created_response.json()["institutional_id"] == "UCN-2026-001"

    search = client.get("/api/v1/accounts?search=ucn-2026-001")
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["items"]] == [str(created.pk)]

    corrected = client.patch(
        f"/api/v1/accounts/{created.pk}/identity",
        data=json.dumps({"institutional_id": "ucn-2026-002"}),
        content_type="application/json",
        **csrf(client),
    )
    assert corrected.status_code == 200
    created.refresh_from_db()
    assert created.institutional_id == "UCN-2026-002"

    event = AuditEvent.objects.get(
        action="account.institutional_id.changed",
        actor_user=admin,
        target_id=str(created.pk),
    )
    assert event.metadata == {"changed_fields": ["institutional_id"]}
    assert "UCN-2026-001" not in str(event.metadata)
    assert "UCN-2026-002" not in str(event.metadata)

    issued = create_auth_session(created)
    profile_client = Client()
    profile_client.cookies["compass_session"] = issued.token
    profile = profile_client.get("/api/v1/me/profile")
    assert profile.status_code == 200
    assert profile.json()["institutional_id"] == "UCN-2026-002"

    forbidden = profile_client.patch(
        "/api/v1/me/profile",
        data=json.dumps({"institutional_id": "UCN-999999"}),
        content_type="application/json",
        **csrf(profile_client),
    )
    assert forbidden.status_code == 422
    created.refresh_from_db()
    assert created.institutional_id == "UCN-2026-002"


@pytest.mark.django_db
def test_csv_requires_and_matches_email_plus_institutional_id_without_merging():
    sync_policy()
    client, _admin = admin_client()
    existing = make_user(
        "csv-existing@example.edu",
        institutional_id="UCN-CSV-001",
    )

    def upload(text: str, *, dry_run: bool = True):
        return client.post(
            f"/api/v1/accounts/imports/csv?dry_run={'true' if dry_run else 'false'}",
            data={
                "file": SimpleUploadedFile(
                    "accounts.csv",
                    text.encode(),
                    content_type="text/csv",
                )
            },
            **csrf(client),
        )

    missing_header = upload("email,first_name,last_name,role\nnew@example.edu,New,User,STUDENT\n")
    assert missing_header.status_code == 422

    exact = upload(
        "institutional_id,email,first_name,last_name,role\n"
        "UCN-CSV-001,csv-existing@example.edu,Identity,User,STUDENT\n"
    )
    assert exact.status_code == 200
    assert exact.json()["rows"][0]["action"] == "SKIP"

    split = upload(
        "institutional_id,email,first_name,last_name,role\n"
        f"UCN-CSV-001,another@example.edu,{existing.first_name},{existing.last_name},STUDENT\n"
    )
    assert split.status_code == 200
    assert split.json()["valid"] is False
    assert split.json()["rows"][0]["action"] == "CONFLICT"

    duplicate = upload(
        "institutional_id,email,first_name,last_name,role\n"
        "UCN-DUP-001,one@example.edu,One,User,STUDENT\n"
        "ucn-dup-001,two@example.edu,Two,User,STUDENT\n"
    )
    assert duplicate.status_code == 422


@pytest.mark.django_db
def test_inventory_uses_canonical_id_for_draft_and_freezes_submitted_history():
    sync_policy()
    student = make_user(
        "snapshot-student@example.edu",
        institutional_id="UCN-OLD-001",
    )
    actor = make_user(
        "snapshot-admin@example.edu",
        role="IT_ADMIN",
        institutional_id="EMP-SNAPSHOT-1",
    )
    year = create_academic_year(label="2026-2027", context=AuditContext.user(actor))
    set_current_academic_year(academic_year_id=year.pk, context=AuditContext.user(actor))

    item = ensure_current_inventory(student=student, context=AuditContext.user(student))
    assert item.student_number == "UCN-OLD-001"

    student.institutional_id = "UCN-NEW-002"
    student.save(update_fields=["institutional_id", "updated_at"])
    item = replace_current_inventory(student=student, values={})
    assert item.student_number == "UCN-NEW-002"

    campus = Campus.objects.create(code="ID-CAMP", name="Identity Campus")
    college = College.objects.create(campus=campus, code="ID-COL", name="Identity College")
    program = Program.objects.create(college=college, code="ID-BSIS", name="BS Information Systems")
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    submitted = submit_current_inventory(
        student=student,
        context=AuditContext.user(student),
    )
    assert submitted.student_number == "UCN-NEW-002"

    student.institutional_id = "UCN-LATER-003"
    student.save(update_fields=["institutional_id", "updated_at"])
    submitted.refresh_from_db()
    assert submitted.student_number == "UCN-NEW-002"
