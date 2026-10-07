"""Identity/reference retrieval and historical revision filters stay inside domain scope."""

from __future__ import annotations

from datetime import time, timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.appointments.services import InvalidAppointmentInput, list_my_appointments
from compass.availability.models import ProviderAvailabilityWindow
from compass.counseling.services import create_encounter
from compass.good_moral.services import issue_request, prepare_request
from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.organization.models import AcademicYear
from compass.routine_interviews.services import ensure_for_appointment
from tests import test_appointments as apt
from tests import test_availability as avail
from tests import test_call_slips as slips
from tests import test_counseling as counseling
from tests import test_feedback as feedback
from tests import test_good_moral as gm
from tests import test_inventory_counselor_review as inv
from tests import test_referrals as referrals
from tests import test_routine_interviews as routine
from tests.inventory_encryption_helpers import create_inventory_row

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def policy():
    call_command("sync_identity_policy", verbosity=0)
    call_command("sync_institutional_forms", verbosity=0)


def ids(response, field="id"):
    assert response.status_code == 200, response.content
    return [row[field] for row in response.json()["items"]]


def revision_options(response):
    assert response.status_code == 200, response.content
    options = response.json()["filter_options"]["form_revisions"]
    assert all(set(option) == {"id", "official_code", "official_revision"} for option in options)
    return {option["id"] for option in options}


def historical_revision(family, *, code=None):
    active = FormRevision.objects.get(family__key=family, status="ACTIVE")
    return FormRevision.objects.create(
        family=active.family,
        official_code=code or active.official_code,
        official_revision="historical",
        internal_schema_version=1,
        status="INACTIVE",
    )


def revoke_forms(user):
    UserCapabilityOverride.objects.create(
        user=user,
        capability=Capability.objects.get(code="institutional_forms.view"),
        effect="REVOKE",
        reason="Operational retrieval needs no configuration access",
    )
    assert not user.has_capability("institutional_forms.view")


def test_my_appointment_reference_search_refines_self_filters_before_pagination():
    admin = apt.make_user("admin@example.edu", "IT_ADMIN")
    student = apt.make_user("student@example.edu", "STUDENT")
    other = apt.make_user("other@example.edu", "STUDENT")
    provider = apt.make_user("provider@example.edu", "COUNSELOR")
    service = apt.active_service(admin)
    start = apt.future_local_start()
    mine = apt.create_list_appointment(
        reference_code="APT-RETRIEVE-001",
        student=student,
        provider=provider,
        service=service,
        starts_at=start,
    )
    apt.create_list_appointment(
        reference_code="APT-RETRIEVE-002",
        student=student,
        provider=provider,
        service=service,
        starts_at=start + timedelta(hours=2),
        status="CANCELLED",
    )
    hidden = apt.create_list_appointment(
        reference_code="APT-RETRIEVE-SECRET",
        student=other,
        provider=provider,
        service=service,
        starts_at=start,
    )
    client = apt.auth_client(student)
    assert ids(client.get("/api/v1/appointments/me", {"search": "apt-retrieve-001"})) == [
        str(mine.pk)
    ]
    assert ids(client.get("/api/v1/appointments/me", {"search": hidden.reference_code})) == []
    assert ids(
        client.get(
            "/api/v1/appointments/me",
            {
                "search": "RETRIEVE",
                "status": "SCHEDULED",
                "upcoming": True,
                "from_date": start.date(),
                "to_date": start.date(),
                "ordering": "EARLIEST_START",
                "page_size": 1,
            },
        )
    ) == [str(mine.pk)]
    assert ids(client.get("/api/v1/appointments/me", {"search": student.first_name})) == []
    assert client.get("/api/v1/appointments/me", {"search": "x" * 161}).status_code == 422
    with pytest.raises(InvalidAppointmentInput):
        list_my_appointments(actor=student, search=7)


def test_provider_lookup_reuses_directory_eligibility_permission_and_tokenized_search():
    admin = avail.make_user("admin@example.edu", "IT_ADMIN")
    provider = avail.make_user("juan@example.edu", "COUNSELOR", first_name="Juan", last_name="Cruz")
    provider.middle_name = "Dela"
    provider.save(update_fields=["middle_name"])
    student = avail.make_user("student@example.edu", "STUDENT")
    clean = avail.make_user("clean@example.edu", "GUIDANCE_SERVICES_STAFF")
    legacy = avail.make_user("legacy@example.edu", "GUIDANCE_SERVICES_STAFF")
    ProviderAvailabilityWindow.objects.create(
        provider=legacy, weekday="MONDAY", start_time=time(8), end_time=time(12), mode_scope="ALL"
    )
    client = avail.auth_client(admin)
    for query in ("Juan Dela Cruz", "Dela Juan", provider.email):
        assert ids(client.get("/api/v1/availability/providers", {"search": query})) == [
            str(provider.pk)
        ]
    for user in (provider, legacy):
        response = client.get(f"/api/v1/availability/providers/{user.pk}")
        assert response.status_code == 200
        assert response.json()["id"] == str(user.pk)
        assert set(response.json()) == {"id", "full_name", "email", "role", "is_active"}
    for user_id in (student.pk, clean.pk, admin.pk, uuid4()):
        assert client.get(f"/api/v1/availability/providers/{user_id}").status_code == 404
    assert (
        avail.auth_client(provider).get(f"/api/v1/availability/providers/{provider.pk}").status_code
        == 403
    )
    provider.is_active = False
    provider.save(update_fields=["is_active"])
    assert client.get(f"/api/v1/availability/providers/{provider.pk}").json()["is_active"] is False


def test_assigned_routine_search_uses_linked_reference_tokens_and_counselor_scope():
    admin = routine.make_user("admin@example.edu", "IT_ADMIN")
    student = routine.make_user("student@example.edu", "STUDENT")
    student.first_name, student.middle_name, student.last_name = "Juan", "Dela", "Cruz"
    student.institutional_id = "RI-IDENTITY"
    student.save()
    counselor = routine.make_user("counselor@example.edu", "COUNSELOR")
    other = routine.make_user("other@example.edu", "COUNSELOR")
    year = routine.configure_year(admin)
    routine.submit_inventory(student, student)
    service = routine.create_counseling_service(admin)
    appointment = routine.make_appointment(student=student, counselor=counselor, service=service)
    mine = ensure_for_appointment(
        student=student, appointment_id=appointment.pk, context=routine.context(student)
    )
    hidden_apt = routine.make_appointment(student=student, counselor=other, service=service)
    ensure_for_appointment(
        student=student, appointment_id=hidden_apt.pk, context=routine.context(student)
    )
    client = routine.auth_client(counselor)
    for query in (
        "Juan Dela Cruz",
        "RI-IDENTITY",
        appointment.reference_code,
        "Juan " + appointment.reference_code,
    ):
        response = client.get(
            "/api/v1/routine-interviews",
            {
                "search": query,
                "academic_year_id": year.pk,
                "delivery_mode": "IN_PERSON",
                "intake_status": "DRAFT",
                "evaluation_status": "DRAFT",
                "student_id": student.pk,
            },
        )
        assert ids(response) == [str(mine.pk)]
        assert "intake" not in response.json()["items"][0]
    assert (
        ids(client.get("/api/v1/routine-interviews", {"search": hidden_apt.reference_code})) == []
    )
    assert client.get("/api/v1/routine-interviews", {"search": "x" * 161}).status_code == 422


def test_encounter_search_is_identity_only_and_collection_projection_is_narrow():
    admin = counseling.make_user("admin@example.edu", "IT_ADMIN")
    student = counseling.make_user("student@example.edu", "STUDENT", institutional_id="ENC-ID")
    student.first_name, student.middle_name, student.last_name = "Juan", "Dela", "Cruz"
    student.save()
    counselor = counseling.make_user("counselor@example.edu", "COUNSELOR")
    other = counseling.make_user("other@example.edu", "COUNSELOR")
    service = counseling.create_counseling_service(admin)
    appointment = counseling.make_appointment(student=student, provider=counselor, service=service)
    start, end = counseling.actual_times()
    mine = create_encounter(
        counselor=counselor,
        entry_mode="APPOINTMENT",
        appointment_id=appointment.pk,
        started_at=start,
        ended_at=end,
        context=counseling.context(counselor),
    )
    direct = create_encounter(
        counselor=counselor,
        entry_mode="WALK_IN",
        student_id=student.pk,
        delivery_mode="IN_PERSON",
        started_at=start,
        ended_at=end,
        context=counseling.context(counselor),
    )
    hidden_apt = counseling.make_appointment(student=student, provider=other, service=service)
    create_encounter(
        counselor=other,
        entry_mode="APPOINTMENT",
        appointment_id=hidden_apt.pk,
        started_at=start,
        ended_at=end,
        context=counseling.context(other),
    )
    client = counseling.auth_client(counselor)
    for query in ("Juan Dela Cruz", "ENC-ID"):
        assert set(ids(client.get("/api/v1/counseling/me/encounters", {"search": query}))) == {
            str(mine.pk),
            str(direct.pk),
        }
    response = client.get(
        "/api/v1/counseling/me/encounters",
        {
            "search": appointment.reference_code,
            "entry_mode": "APPOINTMENT",
            "delivery_mode": "IN_PERSON",
            "student_id": student.pk,
            "from_date": start.date(),
            "to_date": end.date(),
        },
    )
    assert ids(response) == [str(mine.pk)]
    assert response.json()["items"][0]["student"]["institutional_id"] == "ENC-ID"
    detail = client.get(f"/api/v1/counseling/encounters/{mine.pk}")
    assert "institutional_id" not in detail.json()["student"]
    assert (
        ids(client.get("/api/v1/counseling/me/encounters", {"search": hidden_apt.reference_code}))
        == []
    )
    assert (
        ids(client.get("/api/v1/counseling/me/encounters", {"search": "private narrative"})) == []
    )
    assert client.get("/api/v1/counseling/me/encounters", {"search": "x" * 161}).status_code == 422
    assert (
        counseling.auth_client(student)
        .get("/api/v1/counseling/me/encounters", {"search": "ENC-ID"})
        .status_code
        == 403
    )


def test_referral_revision_choices_and_exact_filter_remain_organization_scoped():
    counselor, other, gss, student, hidden_student, _ = referrals.setup_scope()
    revoke_forms(counselor)
    old = historical_revision("referral_slip")
    hidden_revision = historical_revision("referral_slip", code="HIDDEN-REF")
    first = referrals.create_for(counselor, student, key="first", fingerprint="a" * 64)
    second = referrals.create_for(counselor, student, key="second", fingerprint="b" * 64)
    hidden = referrals.create_for(other, hidden_student, key="hidden", fingerprint="c" * 64)
    type(first).objects.filter(pk=first.pk).update(form_revision=old)
    type(hidden).objects.filter(pk=hidden.pk).update(form_revision=hidden_revision)
    client = referrals.auth_client(counselor)
    response = client.get(
        "/api/v1/referrals",
        {
            "form_revision_id": old.pk,
            "search": first.reference_code,
            "from_date": first.referred_on,
            "to_date": first.referred_on,
        },
    )
    assert ids(response) == [str(first.pk)]
    assert revision_options(response) == {str(old.pk), str(second.form_revision_id)}
    assert ids(client.get("/api/v1/referrals", {"form_revision_id": hidden_revision.pk})) == []
    assert str(hidden_revision.pk) not in revision_options(client.get("/api/v1/referrals"))
    assert ids(
        referrals.auth_client(gss).get("/api/v1/referrals", {"form_revision_id": old.pk})
    ) == [str(first.pk)]
    assert client.get("/api/v1/referrals", {"form_revision_id": "invalid"}).status_code == 422


def test_call_slip_revision_filter_composes_with_lifecycle_search_and_scope():
    counselor, other, _, student, hidden_student, _ = referrals.setup_scope()
    revoke_forms(counselor)
    old = historical_revision("call_slip")
    first = slips.create_for(counselor, student, key="first", fingerprint="a" * 64)
    second = slips.create_for(counselor, student, key="second", fingerprint="b" * 64)
    hidden = slips.create_for(other, hidden_student, key="hidden", fingerprint="c" * 64)
    type(first).objects.filter(pk__in=[first.pk, hidden.pk]).update(form_revision=old)
    client = slips.auth_client(counselor)
    response = client.get(
        "/api/v1/call-slips",
        {
            "form_revision_id": old.pk,
            "state": "ACTIVE",
            "search": student.first_name,
            "destination_type": "GUIDANCE_OFFICE",
            "student_id": student.pk,
            "issued_by_id": counselor.pk,
            "from_date": timezone.localdate(),
            "to_date": timezone.localdate() + timedelta(days=2),
        },
    )
    assert ids(response) == [str(first.pk)]
    assert revision_options(response) == {str(old.pk), str(second.form_revision_id)}
    assert (
        ids(client.get("/api/v1/call-slips", {"form_revision_id": old.pk, "state": "COMPLETED"}))
        == []
    )
    assert "filter_options" not in slips.auth_client(student).get("/api/v1/call-slips/me").json()


def test_inventory_revision_is_bound_to_selected_year_and_excludes_missing():
    admin = inv.make_user("admin@example.edu", "IT_ADMIN")
    counselor = inv.make_user("counselor@example.edu", "COUNSELOR")
    revoke_forms(counselor)
    current = inv.configure_year(admin)
    historical = AcademicYear.objects.create(label="previous")
    _, college, program = inv.make_org("A")
    student = inv.make_user("student@example.edu", "STUDENT", institutional_id="INV-ID")
    inv.affiliate(student, college, counselor)
    missing = inv.make_user("missing@example.edu", "STUDENT")
    inv.affiliate(missing, college)
    record = inv.submit_inventory(student=student, program=program, year_level=2)
    old = historical_revision("individual_inventory")
    historical_record = create_inventory_row(
        StudentInventory, student=student, academic_year=historical, form_revision=old
    )
    client = inv.auth_client(counselor)
    current_response = client.get(
        "/api/v1/inventory/students",
        {
            "form_revision_id": record.form_revision_id,
            "academic_year_id": current.pk,
            "status": "SUBMITTED",
            "program_id": program.pk,
            "year_level": 2,
            "search": "INV-ID",
        },
    )
    assert ids(current_response, "inventory_id") == [str(record.pk)]
    assert revision_options(current_response) == {str(record.form_revision_id)}
    assert (
        ids(client.get("/api/v1/inventory/students", {"form_revision_id": old.pk}), "inventory_id")
        == []
    )
    assert (
        ids(
            client.get(
                "/api/v1/inventory/students",
                {"form_revision_id": record.form_revision_id, "status": "MISSING"},
            )
        )
        == []
    )
    response = client.get(
        "/api/v1/inventory/students",
        {"academic_year_id": historical.pk, "form_revision_id": old.pk, "status": "DRAFT"},
    )
    assert ids(response, "inventory_id") == [str(historical_record.pk)]
    assert revision_options(response) == {str(old.pk)}


def test_good_moral_receipt_identity_and_revision_filters_keep_nullable_and_family_semantics():
    counselor = gm.make_user("counselor@example.edu", role="COUNSELOR")
    revoke_forms(counselor)
    student = gm.make_user("graduate@example.edu", lifecycle="GRADUATED")
    student.first_name, student.middle_name, student.last_name = "Juan", "Dela", "Cruz"
    student.institutional_id = "GM-ID"
    student.save()
    request = gm.make_graduate_request(student)
    pending = gm.make_graduate_request(student)
    type(request).objects.filter(pk=request.pk).update(official_receipt_number="OR 123-456")
    prepare_request(actor=counselor, request_id=request.pk, context=gm.AuditContext.user(counselor))
    issued = issue_request(
        actor=counselor, request_id=request.pk, context=gm.AuditContext.user(counselor)
    )
    old = historical_revision("good_moral_graduate")
    type(request).objects.filter(pk=request.pk).update(form_revision=old)
    current_student = gm.make_user("current@example.edu")
    current_request, _ = gm.make_current_request(current_student)
    prepare_request(
        actor=counselor, request_id=current_request.pk, context=gm.AuditContext.user(counselor)
    )
    current_issued = issue_request(
        actor=counselor, request_id=current_request.pk, context=gm.AuditContext.user(counselor)
    )
    client = gm.auth_client(counselor)
    for query in ("123-456", "or 123-456"):
        response = client.get("/api/v1/good-moral/requests", {"search": query})
        assert ids(response) == [str(issued.pk)]
        assert response.json()["items"][0]["official_receipt_number"] == "OR 123-456"
        assert "official_receipt_amount" not in response.json()["items"][0]
    assert set(ids(client.get("/api/v1/good-moral/requests", {"search": "Juan Dela Cruz"}))) == {
        str(issued.pk),
        str(pending.pk),
    }
    assert set(ids(client.get("/api/v1/good-moral/requests", {"search": "GM-ID"}))) == {
        str(issued.pk),
        str(pending.pk),
    }
    response = client.get(
        "/api/v1/good-moral/requests",
        {"form_revision_id": old.pk, "variant": "GRADUATE", "status": "ISSUED"},
    )
    assert ids(response) == [str(issued.pk)]
    assert revision_options(response) == {str(old.pk), str(current_issued.form_revision_id)}
    assert (
        ids(
            client.get(
                "/api/v1/good-moral/requests", {"form_revision_id": old.pk, "status": "REQUESTED"}
            )
        )
        == []
    )
    assert (
        "official_receipt_number"
        not in gm.auth_client(student).get("/api/v1/good-moral/me").json()["items"][0]
    )


def test_customer_feedback_revision_filter_keeps_service_date_name_and_domain_authority():
    student = feedback.make_user("student@example.edu")
    client = feedback.auth_client(student)
    first = feedback.post_json(
        client, "/api/v1/feedback/customer-feedback", feedback.valid_f14_payload()
    )
    second = feedback.post_json(
        client, "/api/v1/feedback/customer-feedback", feedback.valid_f14_payload()
    )
    assert first.status_code == second.status_code == 201
    old = historical_revision("customer_feedback")
    feedback.CustomerFeedbackResponse.objects.filter(pk=first.json()["id"]).update(
        form_revision=old
    )
    head = feedback.make_head()
    revoke_forms(head)
    review = feedback.auth_client(head)
    response = review.get(
        "/api/v1/feedback/customer-feedback/responses",
        {
            "form_revision_id": old.pk,
            "search": "Feedback",
            "service": "COUNSELING",
            "submitted_from": timezone.localdate(),
            "submitted_to": timezone.localdate(),
        },
    )
    assert ids(response) == [first.json()["id"]]
    assert len(revision_options(response)) == 2
    assert str(old.pk) in revision_options(response)
    assert (
        ids(
            review.get(
                "/api/v1/feedback/customer-feedback/responses", {"form_revision_id": uuid4()}
            )
        )
        == []
    )
    assert (
        client.get(
            "/api/v1/feedback/customer-feedback/responses", {"form_revision_id": old.pk}
        ).status_code
        == 403
    )
    assert "filter_options" not in review.get("/api/v1/feedback/csm/responses").json()
