"""CW-6: shared Counselor About summary and authorized Messages context. Synthetic data only."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.utils import timezone

from compass.accounts.models import Designation, Role, User
from compass.appointments.models import Appointment
from compass.organization.models import Campus, College, CounselorResponsibility
from compass.service_catalog.models import BookingPathwayCode, ServiceBookingPathway
from tests.test_guidance_messages import BASE, counseling, deny, office, world  # noqa: F401
from tests.test_notifications import auth_client

pytestmark = pytest.mark.django_db


def about(viewer, counselor_id):
    return auth_client(viewer).get(f"/api/v1/organization/counselors/{counselor_id}/about")


def colleges(payload):
    return [
        (campus["code"], college["code"], college["basis"])
        for campus in payload["campuses"]
        for college in campus["colleges"]
    ]


# ── About: content ───────────────────────────────────────────────────────────────────────────


def test_student_sees_their_counselor_assignment_without_administration_fields(world):  # noqa: F811
    response = about(world.student, world.counselor.pk)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"
    payload = response.json()
    assert set(payload) == {"counselor", "campuses", "checked_at"}
    assert set(payload["counselor"]) == {
        "id",
        "display_name",
        "profile_photo_url",
        "profile_photo_updated_at",
    }
    assert payload["counselor"]["id"] == str(world.counselor.pk)
    assert payload["counselor"]["display_name"] == world.counselor.get_full_name()
    assert payload["campuses"] == [
        {
            "id": str(world.campus.pk),
            "code": "GM",
            "name": "Synthetic Campus",
            "colleges": [
                {
                    "id": str(world.colleges[0].pk),
                    "code": "GM-0",
                    "name": "Synthetic College 0",
                    "basis": "ASSIGNED",
                }
            ],
        }
    ]
    text = response.content.decode()
    for leaked in ("email", "@example.edu", "designation", "HEAD_GUIDANCE", "capabilit", "role"):
        assert leaked not in text


def test_head_fallback_is_reported_separately_from_direct_assignment(world):  # noqa: F811
    payload = about(world.counselor, world.head.pk).json()
    # GM-2 is the Head's own assignment; GM-3 has no valid Counselor, so the unique Head covers it.
    assert colleges(payload) == [("GM", "GM-2", "ASSIGNED"), ("GM", "GM-3", "HEAD_FALLBACK")]
    # An assignment to an inactive Counselor also falls back to the Head, never to the old name.
    world.other.is_active = False
    world.other.save(update_fields=["is_active"])
    payload = about(world.counselor, world.head.pk).json()
    assert colleges(payload) == [
        ("GM", "GM-1", "HEAD_FALLBACK"),
        ("GM", "GM-2", "ASSIGNED"),
        ("GM", "GM-3", "HEAD_FALLBACK"),
    ]


def test_ambiguous_head_configuration_claims_no_fallback(world):  # noqa: F811
    second = User.objects.create_user(
        email="gm-second-head@example.edu",
        password=None,
        role=Role.objects.get(code="COUNSELOR"),
        first_name="Synthetic",
        last_name="second-head",
    )
    second.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    assert colleges(about(world.counselor, world.head.pk).json()) == [("GM", "GM-2", "ASSIGNED")]
    assert about(world.counselor, second.pk).json()["campuses"] == []


def test_inactive_college_and_campus_are_not_current_assignments(world):  # noqa: F811
    other_campus = Campus.objects.create(code="GN", name="Second Campus")
    second = College.objects.create(campus=other_campus, code="GN-0", name="Second College")
    CounselorResponsibility.objects.create(college=second, counselor=world.counselor)
    payload = about(world.goa, world.counselor.pk).json()
    assert colleges(payload) == [("GM", "GM-0", "ASSIGNED"), ("GN", "GN-0", "ASSIGNED")]
    other_campus.is_active = False
    other_campus.save(update_fields=["is_active"])
    College.objects.filter(pk=world.colleges[0].pk).update(is_active=False)
    assert about(world.goa, world.counselor.pk).json()["campuses"] == []


def test_counselor_without_assignment_has_an_honest_empty_summary(world):  # noqa: F811
    CounselorResponsibility.objects.filter(counselor=world.other).delete()
    response = about(world.counselor, world.other.pk)
    assert response.status_code == 200
    assert response.json()["campuses"] == []


# ── About: who may open it ──────────────────────────────────────────────────────────────────


def test_student_cannot_open_a_counselor_they_are_not_offered(world):  # noqa: F811
    response = about(world.student, world.other.pk)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "counselor_about_unavailable"
    assert response["Cache-Control"] == "no-store, private"
    # Once the Counselor is offered in booking, About opens for the same Student.
    world.service.is_active = True
    world.service.save(update_fields=["is_active"])
    ServiceBookingPathway.objects.create(
        service=world.service, code=BookingPathwayCode.FLEXIBLE_APPOINTMENT
    )
    assert about(world.student, world.other.pk).status_code == 200


def test_reassigned_appointment_offers_the_new_provider(world):  # noqa: F811
    Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.other)
    assert about(world.student, world.other.pk).status_code == 200
    # Another Student with no relationship still cannot open it.
    assert about(world.other_student, world.other.pk).status_code == 404


@pytest.mark.parametrize("viewer", ["counselor", "other", "head", "goa", "head_goa"])
def test_guidance_staff_can_open_any_active_counselor(world, viewer):  # noqa: F811
    for target in (world.counselor, world.other, world.head):
        assert about(getattr(world, viewer), target.pk).status_code == 200


@pytest.mark.parametrize("target", ["unknown", "inactive", "goa", "student"])
def test_unknown_inactive_or_non_counselor_is_unavailable(world, target):  # noqa: F811
    if target == "inactive":
        world.other.is_active = False
        world.other.save(update_fields=["is_active"])
        target_id = world.other.pk
    elif target == "unknown":
        target_id = uuid4()
    else:
        target_id = getattr(world, target).pk
    response = about(world.counselor, target_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "counselor_about_unavailable"


@pytest.mark.parametrize("viewer", ["admin", "officer"])
def test_roles_without_an_about_surface_are_refused(world, viewer):  # noqa: F811
    response = about(getattr(world, viewer), world.counselor.pk)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_capabilities_not_role_alone_decide_access(world):  # noqa: F811
    for code in (
        "appointments.view_self",
        "appointments.manage_self",
        "guidance_messages.view_self",
    ):
        deny(world.student, code)
    assert about(world.student, world.counselor.pk).status_code == 403
    for code in (
        "guidance_messages.view",
        "appointments.manage",
        "counseling.view_assigned",
        "counseling.continuity.view",
        "counseling.continuity.request",
    ):
        if world.goa.has_capability(code):
            deny(world.goa, code)
    assert about(world.goa, world.counselor.pk).status_code == 403


def test_anonymous_request_is_rejected(world, client):  # noqa: F811
    response = client.get(f"/api/v1/organization/counselors/{world.counselor.pk}/about")
    assert response.status_code == 401


# ── Messages: counselor photo and authorized appointment summary ─────────────────────────────


def thread_json(viewer, thread):
    response = auth_client(viewer).get(f"{BASE}/threads/{thread.pk}")
    assert response.status_code == 200
    return response.json()


def test_counseling_thread_carries_photo_identity_and_appointment_summary(world):  # noqa: F811
    thread, _ = counseling(world)
    for viewer in (world.student, world.counselor):
        payload = thread_json(viewer, thread)
        assert set(payload["counselor"]) == {
            "id",
            "display_name",
            "profile_photo_url",
            "profile_photo_updated_at",
        }
        assert payload["relationship_appointment"] == {
            "id": str(world.appointment.pk),
            "reference_code": "GM-APPOINTMENT",
            "service_name": world.appointment.service_name_snapshot,
            "starts_at": payload["relationship_appointment"]["starts_at"],
            "ends_at": payload["relationship_appointment"]["ends_at"],
            "status": "SCHEDULED",
        }
    listed = auth_client(world.student).get(f"{BASE}/threads").json()["items"]
    assert listed[0]["relationship_appointment"]["reference_code"] == "GM-APPOINTMENT"


def test_reassigned_counselor_keeps_the_conversation_but_not_the_appointment(world):  # noqa: F811
    thread, _ = counseling(world)
    Appointment.objects.filter(pk=world.appointment.pk).update(provider=world.other)
    # The persisted participant still reads the thread; a historical link discloses nothing more.
    assert thread_json(world.counselor, thread)["relationship_appointment"] is None
    assert thread_json(world.student, thread)["relationship_appointment"]["id"] == str(
        world.appointment.pk
    )
    # The new provider is not added to the old conversation.
    assert auth_client(world.other).get(f"{BASE}/threads/{thread.pk}").status_code == 404


def test_appointment_summary_follows_current_student_capability(world):  # noqa: F811
    thread, _ = counseling(world)
    deny(world.student, "appointments.view_self")
    deny(world.student, "appointments.manage_self")
    assert thread_json(world.student, thread)["relationship_appointment"] is None


def test_lifecycle_status_is_current_not_historical(world):  # noqa: F811
    thread, _ = counseling(world)
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status="CANCELLED", cancelled_at=timezone.now()
    )
    assert thread_json(world.student, thread)["relationship_appointment"]["status"] == "CANCELLED"


def test_office_thread_keeps_office_identity_and_has_no_appointment(world):  # noqa: F811
    thread, _ = office(world)
    payload = thread_json(world.student, thread)
    assert payload["kind"] == "OFFICE"
    assert payload["counselor"] is None
    assert payload["relationship_appointment"] is None


def test_recipient_options_distinguish_appointments_with_one_counselor(world):  # noqa: F811
    response = auth_client(world.student).get(f"{BASE}/recipient-options")
    assert response.status_code == 200
    (option,) = response.json()["counseling_relationships"]
    assert set(option) == {
        "appointment_id",
        "counselor",
        "starts_at",
        "reference_code",
        "service_name",
        "status",
    }
    assert set(option["counselor"]) == {
        "id",
        "display_name",
        "profile_photo_url",
        "profile_photo_updated_at",
    }
    assert option["reference_code"] == "GM-APPOINTMENT"
    assert option["status"] == "SCHEDULED"
