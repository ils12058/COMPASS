"""FAC-5 integrated actual-session cross-College lifecycle and domain boundary proof."""

import json

import pytest
from django.test import Client

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.accounts.policy import FACULTY_CAPABILITY_CEILING
from compass.accounts.services import effective_capabilities
from compass.audit.models import AuditEvent
from compass.referrals.confidential_content import read_referral_confidential_content
from compass.referrals.models import Referral, ReferralReferenceCounter
from tests.faculty_referral_helpers import submit
from tests.referral_administration_helpers import make_world

pytestmark = pytest.mark.django_db


def client_for(token):
    client = Client(enforce_csrf_checks=True)
    client.cookies["compass_session"] = token
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client, {"HTTP_X_CSRFTOKEN": csrf}


def post(client, headers, path, payload, **extra):
    return client.post(
        path, json.dumps(payload), content_type="application/json", **headers, **extra
    )


def test_cas_faculty_ccms_student_actual_sessions_through_closure_and_safe_tracking(monkeypatch):
    world = make_world(monkeypatch)
    faculty, headers = client_for(world.issued.token)
    gco, gco_headers = client_for(world.counselor_issued.token)
    root = "/api/v1/faculty/referrals"
    confirmation = post(
        faculty,
        headers,
        root + "/student-confirmation",
        {"institutional_id": world.student.institutional_id},
    )
    assert confirmation.status_code == 200 and confirmation.json()["confirmed"]
    body = {
        "confirmation": confirmation.json()["confirmation"],
        "course_year_block": "Synthetic CCMS class",
        "reason": "Synthetic FAC5 confidential narrative",
    }
    submitted = post(faculty, headers, root, body, HTTP_IDEMPOTENCY_KEY="fac5-integrated-intent")
    assert submitted.status_code == 201 and submitted.json()["state"] == "SUBMITTED"
    pk = submitted.json()["id"]
    row = Referral.objects.get(pk=pk)
    source = row.confidential_content_ciphertext
    assert "Synthetic FAC5 confidential narrative" not in source
    assert read_referral_confidential_content(row).reason == body["reason"]
    assert row.submitted_by_id == world.faculty.pk and row.recorded_by_id is None
    assert (
        row.faculty_home_college_id == world.cas.pk
        and row.student_college_at_submission_id == world.ccms.pk
    )
    original = (row.submitted_at, row.creation_key_digest, row.creation_request_fingerprint)
    assert row.received_at is None and ReferralReferenceCounter.objects.get().next_value == 2
    assert effective_capabilities(world.faculty) == FACULTY_CAPABILITY_CEILING
    own = root + "/" + pk
    operational = "/api/v1/referrals/" + pk
    denied, _ = client_for(world.other_counselor_issued.token)
    assert denied.get(operational + "/administration").status_code == 404
    foreign, _ = client_for(world.other_issued.token)
    assert foreign.get(own).status_code == 404
    receipt = post(gco, gco_headers, operational + "/acknowledgment", {"expected_version": 1})
    assert receipt.status_code == 200 and receipt.json()["acknowledged_by"]["id"] == str(
        world.counselor.pk
    )
    assert faculty.get(own).json()["state"] == "RECEIVED_BY_GCO"
    closed = post(
        gco,
        gco_headers,
        operational + "/administrative-closure",
        {"expected_version": 2, "obligations_reviewed": True},
    )
    assert closed.status_code == 200 and closed.json()["closed_by"]["id"] == str(world.counselor.pk)
    projection = faculty.get(own).json()
    assert projection["state"] == "ADMINISTRATIVELY_CLOSED"
    assert set(projection) == {
        "id",
        "reference_code",
        "submitted_at",
        "student",
        "state",
        "received_at",
        "closed_at",
    }
    assert (
        projection["received_at"] == receipt.json()["received_at"]
        and projection["closed_at"] == closed.json()["closed_at"]
    )
    assert set(projection["student"]) == {"display_name"}
    replay = post(faculty, headers, root, body, HTTP_IDEMPOTENCY_KEY="fac5-integrated-intent")
    assert replay.status_code == 200 and replay.json() == projection
    row.refresh_from_db()
    assert row.confidential_content_ciphertext == source
    assert (row.submitted_at, row.creation_key_digest, row.creation_request_fingerprint) == original
    assert ReferralReferenceCounter.objects.get().next_value == 2
    metadata = list(AuditEvent.objects.filter(target_id=pk).values_list("metadata", flat=True))
    assert body["reason"] not in json.dumps(metadata) and body["confirmation"] not in json.dumps(
        metadata
    )


@pytest.mark.parametrize(
    "path",
    [
        "/accounts",
        "/accounts/faculty-colleges",
        "/accounts/{id}/access",
        "/referrals",
        "/referrals/students",
        "/referrals/{id}",
        "/referrals/{id}/pdf",
        "/referrals/{id}/administration",
        "/call-slips",
        "/call-slips/{id}",
        "/call-slips/me",
        "/guidance-followups",
        "/counseling/students",
        "/counseling/encounters/{id}",
        "/counseling/continuity-grants",
        "/e-counseling/appointments/{id}",
        "/e-counseling/me/appointments/{id}",
        "/assessment-records",
        "/assessment-records/students",
        "/assessment-records/{id}",
    ],
)
def test_faculty_ceiling_denies_direct_confidential_and_administrative_apis_even_with_raw_grants(
    monkeypatch, path
):
    world = make_world(monkeypatch)
    value, _ = submit(world)
    for code in (
        "referrals.view",
        "referrals.manage",
        "accounts.view",
        "assessment_records.view",
        "counseling.view_assigned",
    ):
        capability = Capability.objects.filter(code=code).first()
        if capability:
            UserCapabilityOverride.objects.create(
                user=world.faculty,
                capability=capability,
                effect="GRANT",
                reason="Synthetic malformed privilege injection",
            )
    client, _ = client_for(world.issued.token)
    resource_id = value["id"]
    expected = 403
    if path.startswith("/e-counseling/"):
        from tests.test_ecounseling import create_counseling_service, make_appointment

        service = create_counseling_service(world.counselor)
        appointment = make_appointment(
            student=world.student, counselor=world.counselor, service=service
        )
        resource_id = appointment.pk
        owner, _ = client_for(world.counselor_issued.token)
        assert owner.get(f"/api/v1/e-counseling/appointments/{resource_id}").status_code == 200
        # Probe an existing, operationally readable Appointment, not a missing UUID.
        expected = 403
    response = client.get("/api/v1" + path.replace("{id}", str(resource_id)))
    assert response.status_code == expected, path
    assert "Synthetic confidential reason" not in response.content.decode()
    assert effective_capabilities(world.faculty) == FACULTY_CAPABILITY_CEILING
