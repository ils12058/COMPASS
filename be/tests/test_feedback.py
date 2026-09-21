from __future__ import annotations

import json
from datetime import datetime

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.institutional_forms.models import FormFamily, FormRevision


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    lifecycle: str | None = StudentLifecycleStatus.CURRENT,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Feedback",
        last_name="Student",
    )
    if role == "STUDENT":
        user.student_lifecycle_status = lifecycle
        user.save(update_fields=["student_lifecycle_status", "updated_at"])
    return user


def make_head(email: str = "head-feedback@example.edu") -> User:
    user = make_user(email, role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def valid_f14_payload() -> dict[str, object]:
    return {
        "services_received": ["COUNSELING", "REQUEST_FOR_CERTIFICATION"],
        "other_service": "",
        "talked_to_guidance_counselor": True,
        "accommodated_by": None,
        "office_visit_count": 2,
        "personnel_accommodating_rating": 5,
        "personnel_job_knowledge_rating": 4,
        "personnel_flexibility_rating": 4,
        "personnel_information_accuracy_rating": 5,
        "personnel_appearance_rating": 4,
        "personnel_commitment_delivery_rating": 5,
        "transaction_duration": "About 15 minutes",
        "office_location_rating": 4,
        "office_cleanliness_rating": 5,
        "office_environment_rating": 4,
        "office_hours_rating": 4,
        "personnel_availability_rating": 5,
        "overall_satisfaction_rating": 5,
        "additional_feedback": "Helpful visit.",
        "future_service_improvement": "Keep the process clear.",
        "respondent_name": "",
        "course_year": "BS Information Systems / 4th Year",
        "address": "",
        "mobile_number": "",
    }


def valid_csm_payload() -> dict[str, object]:
    return {
        "client_type": "CITIZEN",
        "sex": "MALE",
        "age": 21,
        "region_of_residence": "Region V",
        "service_availed": "Guidance consultation",
        "cc1": 1,
        "cc2": 1,
        "cc3": 1,
        "sqd0": 5,
        "sqd1": 4,
        "sqd2": 5,
        "sqd3": 4,
        "sqd4": 4,
        "sqd5": 0,
        "sqd6": 5,
        "sqd7": 5,
        "sqd8": 5,
        "suggestions": "",
        "email": "",
    }


def post_json(client: Client, path: str, payload: dict[str, object]):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_customer_feedback_form_is_controlled_but_csm_is_not_registered_as_f14():
    family = FormFamily.objects.get(key="customer_feedback")
    revision = FormRevision.objects.get(family=family)
    assert family.title == "Customer Feedback Form"
    assert revision.official_code == "CNSC-OP-GTA-01F14"
    assert revision.official_revision == "0"
    assert revision.internal_schema_version == 1
    assert revision.status == "ACTIVE"
    assert not FormFamily.objects.filter(key="client_satisfaction_measurement").exists()
    assert not FormFamily.objects.filter(key="csm").exists()
    assert "form_revision" not in {field.name for field in ClientSatisfactionResponse._meta.fields}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lifecycle",
    [
        StudentLifecycleStatus.CURRENT,
        StudentLifecycleStatus.GRADUATED,
        StudentLifecycleStatus.FORMER,
    ],
)
def test_all_student_lifecycles_can_submit_both_feedback_instruments_without_prerequisites(
    lifecycle,
):
    sync_policy()
    student = make_user(f"{lifecycle.lower()}@example.edu", lifecycle=lifecycle)
    client = auth_client(student)

    f14 = post_json(client, "/api/v1/feedback/customer-feedback", valid_f14_payload())
    csm = post_json(client, "/api/v1/feedback/csm", valid_csm_payload())

    assert f14.status_code == 201
    assert csm.status_code == 201
    assert CustomerFeedbackResponse.objects.count() == 1
    assert ClientSatisfactionResponse.objects.count() == 1


@pytest.mark.django_db
def test_inactive_student_and_non_student_cannot_submit():
    sync_policy()
    student = make_user("inactive-feedback@example.edu")
    inactive_client = auth_client(student)
    student.is_active = False
    student.save(update_fields=["is_active", "updated_at"])
    counselor = make_user("counselor-feedback@example.edu", role="COUNSELOR", lifecycle=None)

    counselor_client = auth_client(counselor)
    assert post_json(
        inactive_client,
        "/api/v1/feedback/csm",
        valid_csm_payload(),
    ).status_code in {401, 403}
    assert (
        post_json(
            counselor_client,
            "/api/v1/feedback/customer-feedback",
            valid_f14_payload(),
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_f14_prefills_profile_snapshots_once_and_does_not_store_user_fk():
    sync_policy()
    student = make_user("profile-feedback@example.edu")
    student.current_address = "Initial Address"
    student.contact_number = "09171234567"
    student.save(update_fields=["current_address", "contact_number", "updated_at"])
    client = auth_client(student)

    response = post_json(client, "/api/v1/feedback/customer-feedback", valid_f14_payload())
    assert response.status_code == 201
    item = CustomerFeedbackResponse.objects.get()
    assert item.respondent_name_snapshot == "Feedback Student"
    assert item.address_snapshot == "Initial Address"
    assert item.mobile_number_snapshot == "09171234567"
    assert item.course_year_snapshot == "BS Information Systems / 4th Year"
    assert not any(field.name in {"user", "student", "respondent"} for field in item._meta.fields)

    student.first_name = "Changed"
    student.current_address = "Changed Address"
    student.contact_number = "09999999999"
    student.save(update_fields=["first_name", "current_address", "contact_number", "updated_at"])
    item.refresh_from_db()
    assert item.respondent_name_snapshot == "Feedback Student"
    assert item.address_snapshot == "Initial Address"
    assert item.mobile_number_snapshot == "09171234567"


@pytest.mark.django_db
def test_f14_other_service_and_counselor_contact_conditionals_are_enforced():
    sync_policy()
    student = make_user("f14-conditionals@example.edu")
    client = auth_client(student)

    other_missing = valid_f14_payload()
    other_missing["services_received"] = ["OTHER"]
    assert (
        post_json(
            client,
            "/api/v1/feedback/customer-feedback",
            other_missing,
        ).status_code
        == 422
    )

    other_valid = valid_f14_payload()
    other_valid["services_received"] = ["OTHER"]
    other_valid["other_service"] = "Document inquiry"
    other_valid["talked_to_guidance_counselor"] = False
    other_valid["accommodated_by"] = "STUDENT_ASSISTANT"
    assert (
        post_json(
            client,
            "/api/v1/feedback/customer-feedback",
            other_valid,
        ).status_code
        == 201
    )

    inconsistent = valid_f14_payload()
    inconsistent["talked_to_guidance_counselor"] = False
    inconsistent["accommodated_by"] = None
    assert (
        post_json(
            client,
            "/api/v1/feedback/customer-feedback",
            inconsistent,
        ).status_code
        == 422
    )


@pytest.mark.django_db
def test_f14_requires_active_supported_controlled_revision():
    sync_policy()
    student = make_user("f14-revision@example.edu")
    client = auth_client(student)
    revision = FormRevision.objects.get(family__key="customer_feedback")

    revision.status = "INACTIVE"
    revision.save(update_fields=["status", "updated_at"])
    missing = post_json(client, "/api/v1/feedback/customer-feedback", valid_f14_payload())
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "feedback_configuration_conflict"

    revision.status = "ACTIVE"
    revision.internal_schema_version = 999
    revision.save(update_fields=["status", "internal_schema_version", "updated_at"])
    unsupported = post_json(client, "/api/v1/feedback/customer-feedback", valid_f14_payload())
    assert unsupported.status_code == 409


@pytest.mark.django_db
def test_csm_is_data_minimized_and_does_not_copy_account_identity():
    sync_policy()
    student = make_user("identity-not-copied@example.edu")
    client = auth_client(student)
    response = post_json(client, "/api/v1/feedback/csm", valid_csm_payload())
    assert response.status_code == 201

    item = ClientSatisfactionResponse.objects.get()
    field_names = {field.name for field in item._meta.fields}
    assert {
        "user",
        "student",
        "respondent",
        "name",
        "lifecycle",
        "inventory",
        "academic_year",
        "college",
        "affiliation",
    }.isdisjoint(field_names)
    assert item.email == ""
    assert "identity-not-copied@example.edu" not in str(item.__dict__)
    assert item.instrument_schema_version == 1


@pytest.mark.django_db
def test_csm_cc_conditional_rules_are_enforced():
    sync_policy()
    student = make_user("cc-rules@example.edu")
    client = auth_client(student)

    cc4 = valid_csm_payload()
    cc4.update({"cc1": 4, "cc2": 5, "cc3": 4})
    assert post_json(client, "/api/v1/feedback/csm", cc4).status_code == 201

    bad_cc4 = valid_csm_payload()
    bad_cc4.update({"cc1": 4, "cc2": 1, "cc3": 4})
    assert post_json(client, "/api/v1/feedback/csm", bad_cc4).status_code == 422

    bad_substantive = valid_csm_payload()
    bad_substantive.update({"cc1": 2, "cc2": 5, "cc3": 1})
    assert post_json(client, "/api/v1/feedback/csm", bad_substantive).status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize("rating", [0, 1, 2, 3, 4, 5])
def test_csm_sqd_scale_accepts_every_source_value_including_na(rating):
    sync_policy()
    student = make_user(f"sqd-{rating}@example.edu")
    client = auth_client(student)
    payload = valid_csm_payload()
    payload["sqd5"] = rating
    response = post_json(client, "/api/v1/feedback/csm", payload)
    assert response.status_code == 201
    assert ClientSatisfactionResponse.objects.get().sqd5 == rating


@pytest.mark.django_db
def test_csm_rejects_unsupported_source_values_and_server_owned_fields():
    sync_policy()
    student = make_user("bad-csm@example.edu")
    client = auth_client(student)

    bad = valid_csm_payload()
    bad["sqd0"] = 9
    assert post_json(client, "/api/v1/feedback/csm", bad).status_code == 422

    extra = valid_csm_payload()
    extra["instrument_schema_version"] = 999
    extra["submitted_at"] = "2000-01-01T00:00:00Z"
    extra["user_id"] = str(student.pk)
    assert post_json(client, "/api/v1/feedback/csm", extra).status_code == 422
    assert ClientSatisfactionResponse.objects.count() == 0


@pytest.mark.django_db
def test_csm_optional_email_is_voluntary_and_validated_when_supplied():
    sync_policy()
    student = make_user("email-feedback@example.edu")
    client = auth_client(student)

    blank = post_json(client, "/api/v1/feedback/csm", valid_csm_payload())
    assert blank.status_code == 201
    assert ClientSatisfactionResponse.objects.get().email == ""

    valid = valid_csm_payload()
    valid["email"] = "respondent@example.com"
    assert post_json(client, "/api/v1/feedback/csm", valid).status_code == 201

    invalid = valid_csm_payload()
    invalid["email"] = "not-an-email"
    assert post_json(client, "/api/v1/feedback/csm", invalid).status_code == 422


@pytest.mark.django_db
def test_multiple_feedback_submissions_are_allowed_and_no_human_reference_is_created():
    sync_policy()
    student = make_user("multiple-feedback@example.edu")
    client = auth_client(student)
    for _ in range(2):
        assert (
            post_json(
                client,
                "/api/v1/feedback/customer-feedback",
                valid_f14_payload(),
            ).status_code
            == 201
        )
        assert post_json(client, "/api/v1/feedback/csm", valid_csm_payload()).status_code == 201
    assert CustomerFeedbackResponse.objects.count() == 2
    assert ClientSatisfactionResponse.objects.count() == 2
    assert not hasattr(CustomerFeedbackResponse.objects.first(), "reference_code")
    assert not hasattr(ClientSatisfactionResponse.objects.first(), "reference_code")


@pytest.mark.django_db
def test_feedback_audit_metadata_excludes_response_answers_and_identity_values():
    sync_policy()
    student = make_user("audit-feedback@example.edu")
    client = auth_client(student)
    assert (
        post_json(
            client,
            "/api/v1/feedback/customer-feedback",
            valid_f14_payload(),
        ).status_code
        == 201
    )
    assert post_json(client, "/api/v1/feedback/csm", valid_csm_payload()).status_code == 201

    f14_event = AuditEvent.objects.get(action="feedback.customer_feedback_submitted")
    assert set(f14_event.metadata) == {
        "family_key",
        "official_code",
        "official_revision",
        "internal_schema_version",
    }
    csm_event = AuditEvent.objects.get(action="feedback.csm_submitted")
    assert csm_event.metadata == {"instrument_schema_version": 1}
    combined = json.dumps([f14_event.metadata, csm_event.metadata])
    assert "Helpful visit" not in combined
    assert "audit-feedback@example.edu" not in combined
    assert "Region V" not in combined


@pytest.mark.django_db
def test_only_head_guidance_has_raw_feedback_review_by_default():
    sync_policy()
    student = make_user("raw-source@example.edu")
    client = auth_client(student)
    f14_id = post_json(
        client,
        "/api/v1/feedback/customer-feedback",
        valid_f14_payload(),
    ).json()["id"]
    csm_id = post_json(client, "/api/v1/feedback/csm", valid_csm_payload()).json()["id"]

    head = auth_client(make_head())
    counselor = auth_client(make_user("ordinary@example.edu", role="COUNSELOR", lifecycle=None))
    admin = auth_client(make_user("admin-feedback@example.edu", role="IT_ADMIN", lifecycle=None))
    gss = auth_client(
        make_user("gss-feedback@example.edu", role="GUIDANCE_SERVICES_STAFF", lifecycle=None)
    )
    dpo_user = make_user("dpo-feedback@example.edu", role="COUNSELOR", lifecycle=None)
    UserDesignation.objects.create(
        user=dpo_user,
        designation=Designation.objects.get(code="DPO"),
    )
    dpo = auth_client(dpo_user)

    assert head.get("/api/v1/feedback/customer-feedback/responses").status_code == 200
    assert head.get(f"/api/v1/feedback/customer-feedback/responses/{f14_id}").status_code == 200
    assert head.get("/api/v1/feedback/csm/responses").status_code == 200
    detail = head.get(f"/api/v1/feedback/csm/responses/{csm_id}")
    assert detail.status_code == 200
    assert detail.json()["sqd5"] == 0

    for denied in (counselor, admin, gss, dpo):
        assert denied.get("/api/v1/feedback/customer-feedback/responses").status_code == 403
        assert denied.get("/api/v1/feedback/csm/responses").status_code == 403


@pytest.mark.django_db
def test_operational_lists_are_paginated_and_csm_list_omits_raw_free_text_and_email():
    sync_policy()
    student = make_user("list-source@example.edu")
    client = auth_client(student)
    for client_type in ("CITIZEN", "BUSINESS", "GOVERNMENT"):
        payload = valid_csm_payload()
        payload["client_type"] = client_type
        payload["suggestions"] = "Private free text"
        payload["email"] = "optional@example.com"
        assert post_json(client, "/api/v1/feedback/csm", payload).status_code == 201

    head = auth_client(make_head())
    listed = head.get("/api/v1/feedback/csm/responses?page=1&page_size=2&client_type=CITIZEN")
    assert listed.status_code == 200
    body = listed.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 1
    assert "suggestions" not in body["items"][0]
    assert "email" not in body["items"][0]


@pytest.mark.django_db
def test_feedback_has_no_normal_update_or_delete_endpoints():
    sync_policy()
    student = make_user("immutable-feedback@example.edu")
    client = auth_client(student)
    f14_id = post_json(
        client,
        "/api/v1/feedback/customer-feedback",
        valid_f14_payload(),
    ).json()["id"]
    csm_id = post_json(client, "/api/v1/feedback/csm", valid_csm_payload()).json()["id"]

    head = auth_client(make_head())
    headers = csrf(head)
    assert head.patch(
        f"/api/v1/feedback/customer-feedback/responses/{f14_id}",
        data=json.dumps({"additional_feedback": "changed"}),
        content_type="application/json",
        **headers,
    ).status_code in {404, 405}
    assert head.delete(
        f"/api/v1/feedback/csm/responses/{csm_id}",
        **headers,
    ).status_code in {404, 405}


@pytest.mark.django_db
def test_customer_feedback_review_filters_name_service_dates_and_pagination():
    sync_policy()
    alpha = make_user("review-alpha-feedback@example.edu")
    alpha.first_name = "Alice"
    alpha.last_name = "Reviewer"
    alpha.save(update_fields=["first_name", "last_name", "updated_at"])
    alpha_client = auth_client(alpha)
    alpha_id = post_json(
        alpha_client,
        "/api/v1/feedback/customer-feedback",
        valid_f14_payload(),
    ).json()["id"]

    beta = make_user("review-beta-feedback@example.edu")
    beta.first_name = "Bruno"
    beta.last_name = "Reviewer"
    beta.save(update_fields=["first_name", "last_name", "updated_at"])
    beta_payload = valid_f14_payload()
    beta_payload["services_received"] = ["ADMISSION"]
    beta_id = post_json(
        auth_client(beta),
        "/api/v1/feedback/customer-feedback",
        beta_payload,
    ).json()["id"]

    zone = timezone.get_current_timezone()
    CustomerFeedbackResponse.objects.filter(pk=alpha_id).update(
        submitted_at=timezone.make_aware(datetime(2026, 9, 20, 23, 59), zone)
    )
    CustomerFeedbackResponse.objects.filter(pk=beta_id).update(
        submitted_at=timezone.make_aware(datetime(2026, 9, 21, 0, 0), zone)
    )

    head = auth_client(make_head("review-feedback-head@example.edu"))
    searched = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"search": "alice"},
    )
    assert searched.status_code == 200
    assert [row["id"] for row in searched.json()["items"]] == [alpha_id]

    service = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"service": "REQUEST_FOR_CERTIFICATION"},
    )
    assert service.status_code == 200
    assert [row["id"] for row in service.json()["items"]] == [alpha_id]

    from_date = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"submitted_from": "2026-09-21"},
    )
    assert [row["id"] for row in from_date.json()["items"]] == [beta_id]

    to_date = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"submitted_to": "2026-09-20"},
    )
    assert [row["id"] for row in to_date.json()["items"]] == [alpha_id]

    paged = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"page_size": 1},
    )
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["has_next"] is True

    reversed_range = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"submitted_from": "2026-09-22", "submitted_to": "2026-09-21"},
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "invalid_feedback_request"

    overlong = head.get(
        "/api/v1/feedback/customer-feedback/responses",
        {"search": "x" * 161},
    )
    assert overlong.status_code == 422
    assert head.get(f"/api/v1/feedback/customer-feedback/responses/{alpha_id}").status_code == 200


@pytest.mark.django_db
def test_csm_review_filters_service_dates_and_preserves_client_type_contract():
    sync_policy()
    student = make_user("review-csm@example.edu")
    client = auth_client(student)

    first = valid_csm_payload()
    first["client_type"] = "CITIZEN"
    first["service_availed"] = "Guidance Consultation and Counseling"
    first_id = post_json(client, "/api/v1/feedback/csm", first).json()["id"]

    second = valid_csm_payload()
    second["client_type"] = "BUSINESS"
    second["service_availed"] = "Document Certification"
    second_id = post_json(client, "/api/v1/feedback/csm", second).json()["id"]

    zone = timezone.get_current_timezone()
    ClientSatisfactionResponse.objects.filter(pk=first_id).update(
        submitted_at=timezone.make_aware(datetime(2026, 9, 20, 23, 59), zone)
    )
    ClientSatisfactionResponse.objects.filter(pk=second_id).update(
        submitted_at=timezone.make_aware(datetime(2026, 9, 21, 0, 0), zone)
    )

    head = auth_client(make_head("review-csm-head@example.edu"))
    service = head.get(
        "/api/v1/feedback/csm/responses",
        {"service": "gUiDaNcE"},
    )
    assert service.status_code == 200
    assert [row["id"] for row in service.json()["items"]] == [first_id]

    client_type = head.get(
        "/api/v1/feedback/csm/responses",
        {"client_type": "BUSINESS"},
    )
    assert [row["id"] for row in client_type.json()["items"]] == [second_id]

    from_date = head.get(
        "/api/v1/feedback/csm/responses",
        {"submitted_from": "2026-09-21"},
    )
    assert [row["id"] for row in from_date.json()["items"]] == [second_id]

    to_date = head.get(
        "/api/v1/feedback/csm/responses",
        {"submitted_to": "2026-09-20"},
    )
    assert [row["id"] for row in to_date.json()["items"]] == [first_id]

    paged = head.get("/api/v1/feedback/csm/responses", {"page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["has_next"] is True

    reversed_range = head.get(
        "/api/v1/feedback/csm/responses",
        {"submitted_from": "2026-09-22", "submitted_to": "2026-09-21"},
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "invalid_feedback_request"

    overlong_service = head.get(
        "/api/v1/feedback/csm/responses",
        {"service": "x" * 256},
    )
    assert overlong_service.status_code == 422
    assert head.get(f"/api/v1/feedback/csm/responses/{first_id}").status_code == 200
