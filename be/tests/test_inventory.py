from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.appointments.models import Appointment, AppointmentReferenceCounter
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.services import replace_office_weekly, replace_provider_weekly
from compass.inventory.services import (
    CurrentAcademicYearNotConfigured,
    InvalidInventoryInput,
    InventoryConflict,
    InventoryStatus,
    ensure_current_inventory,
    get_current_inventory_status,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.service_catalog.services import create_service, set_service_active


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def configure_year(actor: User, label: str = "2026-2027"):
    year = create_academic_year(label=label, context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def active_service(actor: User, *, requires_inventory: bool):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        requires_current_inventory=requires_inventory,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def future_monday(hour: int = 10) -> datetime:
    zone = ZoneInfo("Asia/Manila")
    target = timezone.now().astimezone(zone).date() + timedelta(days=7)
    while target.weekday() != 0:
        target += timedelta(days=1)
    return datetime.combine(target, time(hour), tzinfo=zone)


def configure_availability(actor: User, provider: User) -> None:
    window = {
        "weekday": "MONDAY",
        "start_time": time(8),
        "end_time": time(17),
        "mode_scope": "ALL",
    }
    replace_office_weekly(windows=[window], context=context(actor))
    replace_provider_weekly(provider_id=provider.pk, windows=[window], context=context(actor))


@pytest.mark.django_db
def test_current_status_distinguishes_missing_configuration_from_missing_inventory():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    actor = make_user("actor@example.edu", "IT_ADMIN")

    with pytest.raises(CurrentAcademicYearNotConfigured):
        get_current_inventory_status(student)

    year = configure_year(actor)
    status = get_current_inventory_status(student)
    assert status.academic_year_id if False else status.academic_year.pk == year.pk
    assert status.status == InventoryStatus.MISSING
    assert status.inventory is None


@pytest.mark.django_db
def test_ensure_draft_snapshots_active_revision_and_annual_identity():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    actor = make_user("actor@example.edu", "IT_ADMIN")
    year = configure_year(actor)

    first = ensure_current_inventory(student=student, context=context(student))
    repeated = ensure_current_inventory(student=student, context=context(student))

    assert repeated.pk == first.pk
    assert first.academic_year_id == year.pk
    assert first.form_revision.family.key == "individual_inventory"
    assert first.form_revision.official_code == "CNSC-OP-GCO-01F5"
    assert first.form_revision.official_revision == "0"
    assert first.form_revision.internal_schema_version == 1
    assert first.submitted_at is None
    assert AuditEvent.objects.filter(action="inventory.created").count() == 1


@pytest.mark.django_db
def test_put_style_replacement_preserves_typed_nested_source_sections_and_submission_locks():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    actor = make_user("actor@example.edu", "IT_ADMIN")
    configure_year(actor)
    item = ensure_current_inventory(student=student, context=context(student))

    updated = replace_current_inventory(
        student=student,
        values={
            "full_name_snapshot": "Student Snapshot",
            "nickname": "Stu",
            "student_number": "2026-001",
            "parent_statuses": ["MOTHER_OFW"],
            "living_arrangement": "BOARDING_HOUSE",
            "boarding_exclusive": True,
            "boarding_landlord_name": "Land Lord",
            "boarding_address": "Daet",
            "immunizations": ["CHICKEN_POX", "OTHER"],
            "immunization_other": "Institutional source entry",
            "course_choice_reasons": ["INTEREST_APTITUDE"],
            "interests": ["PAINTING", "COOKING"],
            "prior_counseling_experience": False,
            "family_members": [
                {
                    "kind": "MOTHER",
                    "name": "Parent Snapshot",
                    "occupation": "Teacher",
                }
            ],
            "siblings": [
                {
                    "sort_order": 0,
                    "name": "Student Snapshot",
                    "sex": "MALE",
                    "age": 20,
                    "is_self": True,
                }
            ],
            "education_entries": [
                {
                    "level": "SENIOR_HIGH",
                    "school_attended_address": "School / Address",
                    "inclusive_years": "2022-2024",
                    "awards_received": "",
                }
            ],
            "organization_memberships": [
                {
                    "scope": "INSIDE_SCHOOL",
                    "sort_order": 0,
                    "organization_name": "Student Organization",
                    "position_title": "Member",
                }
            ],
            "transportation_entries": [{"mode": "TRICYCLE", "frequency": "Daily", "fare": "20.00"}],
        },
    )
    assert updated.pk == item.pk
    assert updated.full_name_snapshot == "Student Snapshot"
    assert updated.family_members.get().kind == "MOTHER"
    assert updated.siblings.get().is_self
    assert updated.education_entries.get().level == "SENIOR_HIGH"
    assert updated.organization_memberships.get().scope == "INSIDE_SCHOOL"
    assert str(updated.transportation_entries.get().fare) == "20.00"

    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None
    assert get_current_inventory_status(student).status == InventoryStatus.SUBMITTED
    assert AuditEvent.objects.filter(action="inventory.submitted").count() == 1

    with pytest.raises(InventoryConflict, match="locked"):
        replace_current_inventory(student=student, values={"nickname": "Changed"})


@pytest.mark.django_db
def test_submission_enforces_only_confirmed_conditional_consistency():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    actor = make_user("actor@example.edu", "IT_ADMIN")
    configure_year(actor)
    ensure_current_inventory(student=student, context=context(student))

    replace_current_inventory(
        student=student,
        values={
            "immunizations": ["OTHER"],
            "immunization_other": "",
            "family_members": [],
            "siblings": [],
            "education_entries": [],
            "organization_memberships": [],
            "transportation_entries": [],
        },
    )
    with pytest.raises(InvalidInventoryInput, match="immunization_other"):
        submit_current_inventory(student=student, context=context(student))

    replace_current_inventory(
        student=student,
        values={
            "immunizations": [],
            "prior_counseling_experience": None,
            "prior_counselor_name": "",
            "family_members": [],
            "siblings": [],
            "education_entries": [],
            "organization_memberships": [],
            "transportation_entries": [],
        },
    )
    with pytest.raises(InvalidInventoryInput, match="Prior Counselor"):
        replace_current_inventory(
            student=student,
            values={
                "immunizations": [],
                "prior_counseling_experience": False,
                "prior_counselor_name": "Should be empty",
                "family_members": [],
                "siblings": [],
                "education_entries": [],
                "organization_memberships": [],
                "transportation_entries": [],
            },
        )


@pytest.mark.django_db
def test_new_academic_year_creates_new_snapshot_without_moving_history():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    actor = make_user("actor@example.edu", "IT_ADMIN")
    first_year = configure_year(actor, "2026-2027")
    first = ensure_current_inventory(student=student, context=context(student))
    submit_current_inventory(student=student, context=context(student))

    second_year = create_academic_year(label="2027-2028", context=context(actor))
    set_current_academic_year(academic_year_id=second_year.pk, context=context(actor))
    second = ensure_current_inventory(student=student, context=context(student))

    first.refresh_from_db()
    assert first.academic_year_id == first_year.pk
    assert first.submitted_at is not None
    assert second.academic_year_id == second_year.pk
    assert second.pk != first.pk
    assert second.form_revision_id == first.form_revision_id


@pytest.mark.django_db
def test_inventory_api_is_student_self_service_only_and_does_not_require_idempotency_key():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    configure_year(admin)
    client = auth_client(student)

    ensured = client.post(
        "/api/v1/inventory/me/current",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert ensured.status_code == 200
    assert ensured.json()["status"] == "DRAFT"
    assert ensured.json()["sex"] is None
    assert ensured.json()["living_arrangement"] is None
    assert ensured.json()["handedness"] is None
    assert ensured.json()["ideal_monthly_allowance"] is None
    assert ensured.json()["intended_work_field"] is None

    status = client.get("/api/v1/inventory/me/status")
    assert status.status_code == 200
    assert status.json()["status"] == "DRAFT"

    admin_client = auth_client(admin)
    assert admin_client.get("/api/v1/inventory/me/status").status_code == 403


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_appointment_prerequisite_blocks_before_reference_then_allows_submitted_inventory():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, requires_inventory=True)
    configure_availability(actor, provider)
    start = future_monday()
    client = auth_client(student)
    headers = csrf(client)
    payload = {
        "service_id": str(service.pk),
        "provider_id": str(provider.pk),
        "delivery_mode": "IN_PERSON",
        "starts_at": start.isoformat(),
    }
    key = "inventory-prerequisite-retry"

    no_year = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert no_year.status_code == 409
    assert no_year.json()["error"]["code"] == "current_academic_year_not_configured"
    assert Appointment.objects.count() == 0
    assert AppointmentReferenceCounter.objects.count() == 0

    configure_year(actor)
    draft = ensure_current_inventory(student=student, context=context(student))
    blocked = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "current_inventory_required"
    assert Appointment.objects.count() == 0
    assert AppointmentReferenceCounter.objects.count() == 0
    assert not AuditEvent.objects.filter(action="appointment.created").exists()

    submit_current_inventory(student=student, context=context(student))
    draft.refresh_from_db()
    assert draft.submitted_at is not None
    retried = client.post(
        "/api/v1/appointments",
        data=json.dumps(payload, separators=(",", ":")),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
        **headers,
    )
    assert retried.status_code == 201
    assert Appointment.objects.count() == 1
    assert AppointmentReferenceCounter.objects.count() == 1


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_service_without_inventory_prerequisite_preserves_existing_booking_behavior():
    sync_policy()
    actor = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    provider = make_user("provider@example.edu", "COUNSELOR")
    service = active_service(actor, requires_inventory=False)
    configure_availability(actor, provider)
    client = auth_client(student)
    start = future_monday()

    response = client.post(
        "/api/v1/appointments",
        data=json.dumps(
            {
                "service_id": str(service.pk),
                "provider_id": str(provider.pk),
                "delivery_mode": "IN_PERSON",
                "starts_at": start.isoformat(),
            },
            separators=(",", ":"),
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="no-inventory-required",
        **csrf(client),
    )
    assert response.status_code == 201
