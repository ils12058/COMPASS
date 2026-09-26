from __future__ import annotations

import base64
import json
import uuid
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
from compass.common.idempotency import (
    IdempotencyDecision,
    IdempotencyReservation,
    IdempotencyUnavailable,
    RedisIdempotencyStore,
)
from compass.feedback import api as feedback_api
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


def post_json(
    client: Client,
    path: str,
    payload: dict[str, object],
    *,
    idempotency_key: str | None = None,
):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=idempotency_key or f"feedback-{uuid.uuid4()}",
        **csrf(client),
    )


class FakeRedis:
    def __init__(self):
        self.records: dict[str, str] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.records:
            return False
        self.records[key] = value
        return True

    def get(self, key):
        return self.records.get(key)

    def eval(self, script, number_of_keys, key, owner_token, *args):
        record = json.loads(self.records[key])
        if record["owner_token"] != owner_token:
            return 0
        if not args:
            if record["state"] != "in_progress":
                return -2
            del self.records[key]
            return 1
        status_code, content_type, body_b64, ttl = args
        record.update(
            {
                "state": "completed",
                "status_code": int(status_code),
                "content_type": content_type,
                "body_b64": body_b64,
            }
        )
        self.records[key] = json.dumps(record)
        return 1


class ControlledIdempotencyStore:
    def __init__(
        self,
        *,
        outcome: str = "execute",
        begin_error: Exception | None = None,
        complete_error: Exception | None = None,
        abandon_error: Exception | None = None,
    ):
        self.outcome = outcome
        self.begin_error = begin_error
        self.complete_error = complete_error
        self.abandon_error = abandon_error
        self.begin_calls = 0
        self.complete_calls = 0
        self.abandon_calls = 0
        self.completed_response = None
        self.reservation = IdempotencyReservation("fake-feedback-key", "fake-owner")

    def begin(self, **kwargs):
        self.begin_calls += 1
        if self.begin_error is not None:
            raise self.begin_error
        if self.outcome == "in_progress":
            return IdempotencyDecision("in_progress")
        return IdempotencyDecision("execute", reservation=self.reservation)

    def complete(self, reservation, response):
        self.complete_calls += 1
        self.completed_response = response
        if self.complete_error is not None:
            raise self.complete_error

    def abandon(self, reservation):
        self.abandon_calls += 1
        if self.abandon_error is not None:
            raise self.abandon_error


def use_idempotency_store(monkeypatch, store) -> None:
    monkeypatch.setattr(
        feedback_api.RedisIdempotencyStore,
        "from_settings",
        classmethod(lambda cls: store),
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "payload_factory"),
    [
        ("/api/v1/feedback/customer-feedback", valid_f14_payload),
        ("/api/v1/feedback/csm", valid_csm_payload),
    ],
)
def test_feedback_submission_requires_idempotency_key(path, payload_factory):
    sync_policy()
    student = make_user("missing-idempotency-key@example.edu")
    client = auth_client(student)

    response = client.post(
        path,
        data=json.dumps(payload_factory()),
        content_type="application/json",
        **csrf(client),
    )

    assert response.status_code == 422
    assert CustomerFeedbackResponse.objects.count() == 0
    assert ClientSatisfactionResponse.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("instrument", ["customer_feedback", "csm"])
def test_feedback_exact_replay_returns_original_success_once(monkeypatch, instrument):
    sync_policy()
    student = make_user(f"replay-{instrument}@example.edu")
    client = auth_client(student)
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)

    if instrument == "customer_feedback":
        path = "/api/v1/feedback/customer-feedback"
        payload = valid_f14_payload()
        model = CustomerFeedbackResponse
        action = "feedback.customer_feedback_submitted"
    else:
        path = "/api/v1/feedback/csm"
        payload = valid_csm_payload()
        model = ClientSatisfactionResponse
        action = "feedback.csm_submitted"

    key = f"exact-replay-{instrument}"
    first = post_json(client, path, payload, idempotency_key=key)
    replay = post_json(client, path, payload, idempotency_key=key)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.content == first.content
    assert replay["Content-Type"] == first["Content-Type"]
    assert replay.json() == first.json()
    assert set(first.json()) == {"id", "submitted_at", "submitted"}
    assert first.json()["submitted"] is True
    assert model.objects.count() == 1
    assert AuditEvent.objects.filter(action=action).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("instrument", ["customer_feedback", "csm"])
def test_feedback_same_key_different_body_conflicts_without_second_mutation(
    monkeypatch, instrument
):
    sync_policy()
    student = make_user(f"conflict-{instrument}@example.edu")
    client = auth_client(student)
    store = RedisIdempotencyStore(FakeRedis(), ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)

    if instrument == "customer_feedback":
        path = "/api/v1/feedback/customer-feedback"
        first_payload = valid_f14_payload()
        second_payload = {**first_payload, "office_visit_count": 3}
        model = CustomerFeedbackResponse
        action = "feedback.customer_feedback_submitted"
    else:
        path = "/api/v1/feedback/csm"
        first_payload = valid_csm_payload()
        second_payload = {**first_payload, "age": 22}
        model = ClientSatisfactionResponse
        action = "feedback.csm_submitted"

    key = f"conflict-{instrument}"
    assert post_json(client, path, first_payload, idempotency_key=key).status_code == 201
    conflict = post_json(client, path, second_payload, idempotency_key=key)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_conflict"
    assert model.objects.count() == 1
    assert AuditEvent.objects.filter(action=action).count() == 1


@pytest.mark.django_db
def test_feedback_same_key_is_independent_across_actors(monkeypatch):
    sync_policy()
    first_student = make_user("same-key-actor-a@example.edu")
    second_student = make_user("same-key-actor-b@example.edu")
    store = RedisIdempotencyStore(FakeRedis(), ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)
    key = "same-key-different-actor"
    payload = valid_csm_payload()

    first = post_json(
        auth_client(first_student),
        "/api/v1/feedback/csm",
        payload,
        idempotency_key=key,
    )
    second = post_json(
        auth_client(second_student),
        "/api/v1/feedback/csm",
        payload,
        idempotency_key=key,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert ClientSatisfactionResponse.objects.count() == 2
    assert AuditEvent.objects.filter(action="feedback.csm_submitted").count() == 2


@pytest.mark.django_db
def test_feedback_same_key_is_independent_across_feedback_routes(monkeypatch):
    sync_policy()
    student = make_user("same-key-route@example.edu")
    client = auth_client(student)
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)
    key = "same-key-different-feedback-route"

    f14 = post_json(
        client,
        "/api/v1/feedback/customer-feedback",
        valid_f14_payload(),
        idempotency_key=key,
    )
    csm = post_json(
        client,
        "/api/v1/feedback/csm",
        valid_csm_payload(),
        idempotency_key=key,
    )

    assert f14.status_code == 201
    assert csm.status_code == 201
    assert CustomerFeedbackResponse.objects.count() == 1
    assert ClientSatisfactionResponse.objects.count() == 1
    assert len(redis.records) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("instrument", ["customer_feedback", "csm"])
def test_feedback_new_key_allows_new_legitimate_submission(monkeypatch, instrument):
    sync_policy()
    student = make_user(f"new-key-{instrument}@example.edu")
    client = auth_client(student)
    store = RedisIdempotencyStore(FakeRedis(), ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)

    if instrument == "customer_feedback":
        path = "/api/v1/feedback/customer-feedback"
        payload = valid_f14_payload()
        model = CustomerFeedbackResponse
    else:
        path = "/api/v1/feedback/csm"
        payload = valid_csm_payload()
        model = ClientSatisfactionResponse

    first = post_json(client, path, payload, idempotency_key=f"{instrument}-intent-a")
    second = post_json(client, path, payload, idempotency_key=f"{instrument}-intent-b")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert model.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "payload_factory"),
    [
        ("/api/v1/feedback/customer-feedback", valid_f14_payload),
        ("/api/v1/feedback/csm", valid_csm_payload),
    ],
)
def test_feedback_in_progress_request_does_not_mutate(monkeypatch, path, payload_factory):
    sync_policy()
    student = make_user("in-progress-feedback@example.edu")
    client = auth_client(student)
    store = ControlledIdempotencyStore(outcome="in_progress")
    use_idempotency_store(monkeypatch, store)

    response = post_json(
        client,
        path,
        payload_factory(),
        idempotency_key="feedback-in-progress",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_in_progress"
    assert store.begin_calls == 1
    assert store.complete_calls == 0
    assert store.abandon_calls == 0
    assert CustomerFeedbackResponse.objects.count() == 0
    assert ClientSatisfactionResponse.objects.count() == 0
    assert not AuditEvent.objects.filter(
        action__in=["feedback.customer_feedback_submitted", "feedback.csm_submitted"]
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "payload_factory"),
    [
        ("/api/v1/feedback/customer-feedback", valid_f14_payload),
        ("/api/v1/feedback/csm", valid_csm_payload),
    ],
)
def test_feedback_idempotency_unavailable_before_execution_fails_closed(
    monkeypatch,
    path,
    payload_factory,
):
    sync_policy()
    student = make_user("unavailable-feedback@example.edu")
    client = auth_client(student)
    store = ControlledIdempotencyStore(begin_error=IdempotencyUnavailable("Redis unavailable"))
    use_idempotency_store(monkeypatch, store)

    response = post_json(
        client,
        path,
        payload_factory(),
        idempotency_key="feedback-unavailable",
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "idempotency_unavailable"
    assert CustomerFeedbackResponse.objects.count() == 0
    assert ClientSatisfactionResponse.objects.count() == 0
    assert not AuditEvent.objects.filter(
        action__in=["feedback.customer_feedback_submitted", "feedback.csm_submitted"]
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "payload_factory"),
    [
        ("/api/v1/feedback/customer-feedback", valid_f14_payload),
        ("/api/v1/feedback/csm", valid_csm_payload),
    ],
)
def test_feedback_invalid_idempotency_key_does_not_mutate(
    monkeypatch,
    path,
    payload_factory,
):
    sync_policy()
    student = make_user("invalid-key-feedback@example.edu")
    client = auth_client(student)
    use_idempotency_store(
        monkeypatch,
        RedisIdempotencyStore(FakeRedis(), ttl_seconds=60),
    )

    response = post_json(
        client,
        path,
        payload_factory(),
        idempotency_key=" invalid-key ",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_idempotency_key"
    assert CustomerFeedbackResponse.objects.count() == 0
    assert ClientSatisfactionResponse.objects.count() == 0


@pytest.mark.django_db
def test_customer_feedback_domain_failure_abandons_key_for_retry(monkeypatch):
    sync_policy()
    student = make_user("f14-abandon@example.edu")
    client = auth_client(student)
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)
    revision = FormRevision.objects.get(family__key="customer_feedback")
    revision.status = "INACTIVE"
    revision.save(update_fields=["status", "updated_at"])
    key = "f14-domain-failure-release"
    payload = valid_f14_payload()

    failed = post_json(client, "/api/v1/feedback/customer-feedback", payload, idempotency_key=key)
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "feedback_configuration_conflict"
    assert redis.records == {}
    assert CustomerFeedbackResponse.objects.count() == 0

    revision.status = "ACTIVE"
    revision.save(update_fields=["status", "updated_at"])
    retried = post_json(client, "/api/v1/feedback/customer-feedback", payload, idempotency_key=key)

    assert retried.status_code == 201
    assert CustomerFeedbackResponse.objects.count() == 1
    assert AuditEvent.objects.filter(action="feedback.customer_feedback_submitted").count() == 1


@pytest.mark.django_db
def test_csm_domain_validation_abandons_key_for_corrected_retry(monkeypatch):
    sync_policy()
    student = make_user("csm-abandon@example.edu")
    client = auth_client(student)
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)
    key = "csm-domain-failure-release"
    invalid = valid_csm_payload()
    invalid.update({"cc1": 4, "cc2": 1, "cc3": 4})

    failed = post_json(client, "/api/v1/feedback/csm", invalid, idempotency_key=key)
    assert failed.status_code == 422
    assert failed.json()["error"]["code"] == "invalid_feedback_request"
    assert redis.records == {}
    assert ClientSatisfactionResponse.objects.count() == 0

    corrected = valid_csm_payload()
    corrected.update({"cc1": 4, "cc2": 5, "cc3": 4})
    retried = post_json(client, "/api/v1/feedback/csm", corrected, idempotency_key=key)

    assert retried.status_code == 201
    assert ClientSatisfactionResponse.objects.count() == 1
    assert AuditEvent.objects.filter(action="feedback.csm_submitted").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("instrument", ["customer_feedback", "csm"])
def test_feedback_complete_failure_returns_uncertain_503_without_rollback(
    monkeypatch,
    instrument,
):
    sync_policy()
    student = make_user(f"complete-failure-{instrument}@example.edu")
    client = auth_client(student)
    store = ControlledIdempotencyStore(
        complete_error=IdempotencyUnavailable("completion unavailable")
    )
    use_idempotency_store(monkeypatch, store)

    if instrument == "customer_feedback":
        path = "/api/v1/feedback/customer-feedback"
        payload = valid_f14_payload()
        model = CustomerFeedbackResponse
        action = "feedback.customer_feedback_submitted"
    else:
        path = "/api/v1/feedback/csm"
        payload = valid_csm_payload()
        model = ClientSatisfactionResponse
        action = "feedback.csm_submitted"

    response = post_json(
        client,
        path,
        payload,
        idempotency_key=f"complete-failure-{instrument}",
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "idempotency_unavailable"
    assert store.begin_calls == 1
    assert store.complete_calls == 1
    assert store.abandon_calls == 0
    assert model.objects.count() == 1
    assert AuditEvent.objects.filter(action=action).count() == 1


@pytest.mark.django_db
def test_feedback_abandon_failure_returns_idempotency_unavailable(monkeypatch):
    sync_policy()
    student = make_user("abandon-failure@example.edu")
    client = auth_client(student)
    store = ControlledIdempotencyStore(abandon_error=IdempotencyUnavailable("abandon unavailable"))
    use_idempotency_store(monkeypatch, store)
    invalid = valid_csm_payload()
    invalid.update({"cc1": 4, "cc2": 1, "cc3": 4})

    response = post_json(
        client,
        "/api/v1/feedback/csm",
        invalid,
        idempotency_key="abandon-failure",
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "idempotency_unavailable"
    assert store.abandon_calls == 1
    assert ClientSatisfactionResponse.objects.count() == 0
    assert not AuditEvent.objects.filter(action="feedback.csm_submitted").exists()


@pytest.mark.django_db
def test_feedback_replay_storage_contains_only_submission_response_and_digests(monkeypatch):
    sync_policy()
    student = make_user("privacy-replay@example.edu")
    student.current_address = "Sensitive Home Address"
    student.contact_number = "09991234567"
    student.save(update_fields=["current_address", "contact_number", "updated_at"])
    client = auth_client(student)
    redis = FakeRedis()
    store = RedisIdempotencyStore(redis, ttl_seconds=60)
    use_idempotency_store(monkeypatch, store)

    f14_payload = valid_f14_payload()
    f14_payload["additional_feedback"] = "Sensitive F14 answer"
    csm_payload = valid_csm_payload()
    csm_payload["suggestions"] = "Sensitive CSM suggestion"
    csm_payload["email"] = "optional-sensitive@example.edu"
    raw_key = "raw-feedback-key-must-not-persist"

    assert (
        post_json(
            client,
            "/api/v1/feedback/customer-feedback",
            f14_payload,
            idempotency_key=raw_key,
        ).status_code
        == 201
    )
    assert (
        post_json(
            client,
            "/api/v1/feedback/csm",
            csm_payload,
            idempotency_key=raw_key,
        ).status_code
        == 201
    )

    assert len(redis.records) == 2
    for redis_key, encoded in redis.records.items():
        record = json.loads(encoded)
        assert raw_key not in redis_key
        assert raw_key not in encoded
        assert len(record["fingerprint"]) == 64
        assert all(char in "0123456789abcdef" for char in record["fingerprint"])
        replay_body = json.loads(base64.b64decode(record["body_b64"]))
        assert set(replay_body) == {"id", "submitted_at", "submitted"}
        assert replay_body["submitted"] is True

    serialized_records = json.dumps(redis.records)
    for forbidden in (
        "Sensitive F14 answer",
        "Sensitive CSM suggestion",
        "optional-sensitive@example.edu",
        "Sensitive Home Address",
        "09991234567",
        student.email,
    ):
        assert forbidden not in serialized_records

    audit_metadata = json.dumps(
        list(
            AuditEvent.objects.filter(
                action__in=[
                    "feedback.customer_feedback_submitted",
                    "feedback.csm_submitted",
                ]
            ).values_list("metadata", flat=True)
        )
    )
    assert raw_key not in audit_metadata
    assert raw_key not in str(CustomerFeedbackResponse.objects.get().__dict__)
    assert raw_key not in str(ClientSatisfactionResponse.objects.get().__dict__)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "payload_factory", "service_name"),
    [
        ("/api/v1/feedback/customer-feedback", valid_f14_payload, "create_customer_feedback"),
        ("/api/v1/feedback/csm", valid_csm_payload, "create_csm_response"),
    ],
)
def test_unexpected_failure_releases_reservation_so_same_intent_can_retry(
    monkeypatch,
    path,
    payload_factory,
    service_name,
):
    sync_policy()
    student = make_user(f"unexpected-{service_name}@example.edu")
    client = auth_client(student)
    redis = FakeRedis()
    use_idempotency_store(monkeypatch, RedisIdempotencyStore(redis, ttl_seconds=60))
    original = getattr(feedback_api, service_name)

    def fail_once(**kwargs):
        monkeypatch.setattr(feedback_api, service_name, original)
        raise RuntimeError("unexpected database outage")

    monkeypatch.setattr(feedback_api, service_name, fail_once)
    client.raise_request_exception = False
    key = f"unexpected-{service_name}"

    failed = post_json(client, path, payload_factory(), idempotency_key=key)
    assert failed.status_code == 500
    assert redis.records == {}

    retried = post_json(client, path, payload_factory(), idempotency_key=key)
    assert retried.status_code == 201
