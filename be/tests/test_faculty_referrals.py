"""FAC-2 policy-gated functional intake and explicit privacy/authorization regressions."""

import json
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Capability, Role, UserCapabilityOverride
from compass.accounts.policy import FACULTY_CAPABILITY_CEILING
from compass.accounts.services import effective_capabilities
from compass.audit.models import AuditEvent
from compass.common.rate_limit import RateLimitUnavailable
from compass.organization.models import FacultyAffiliation, StudentAffiliation
from compass.referrals import faculty_policy, faculty_services
from compass.referrals.confidential_content import read_referral_confidential_content
from compass.referrals.faculty_policy import FacultyReferralError
from compass.referrals.models import Referral, ReferralAction, ReferralReferenceCounter
from compass.referrals.services import ReferralCreationConflict, ReferralNotFound
from tests.faculty_referral_helpers import confirm, make_world, seal, submit

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch):
    return make_world(monkeypatch)


@pytest.mark.parametrize("missing", ["both", "lookup", "submission", "neither"])
def test_advisory_availability_keeps_policy_authorities_independent(world, monkeypatch, missing):
    if missing in {"both", "lookup"}:
        monkeypatch.setattr(faculty_policy, "get_approved_lookup_policy", lambda: None)
    if missing in {"both", "submission"}:
        monkeypatch.setattr(faculty_policy, "get_approved_submission_policy", lambda: None)
    result = faculty_services.referral_availability(
        actor=world.faculty, actor_session=world.issued.session
    )
    assert result["can_confirm_student"] == (missing not in {"both", "lookup"})
    assert result["can_view_submissions"] == (missing not in {"both", "submission"})
    assert result["can_submit_referral"] == (missing == "neither")
    assert set(result) == {
        "can_confirm_student",
        "can_submit_referral",
        "can_view_submissions",
        "valid_until",
    }
    assert not Referral.objects.exists() and not world.limiter.counts
    if missing == "both":
        assert result["valid_until"] is None
    else:
        assert result["valid_until"] <= world.issued.session.expires_at


def test_availability_does_not_convert_own_read_into_submission_permission(world):
    from compass.institutional_forms.models import FormRevision

    args = dict(actor=world.faculty, actor_session=world.issued.session)
    FormRevision.objects.filter(family__key="referral_slip").update(status="INACTIVE")
    assert faculty_services.referral_availability(**args)["can_submit_referral"] is False
    UserCapabilityOverride.objects.create(
        user=world.faculty,
        capability=Capability.objects.get(code="referrals.submit_self"),
        effect="REVOKE",
        reason="Synthetic read-only",
    )
    value = faculty_services.referral_availability(**args)
    assert value["can_view_submissions"] is True
    assert value["can_confirm_student"] is False and value["can_submit_referral"] is False


def test_availability_reloads_session_role_and_home_before_advising(world):
    args = dict(actor=world.faculty, actor_session=world.issued.session)
    FacultyAffiliation.objects.filter(faculty=world.faculty).update(college=None)
    assert not faculty_services.referral_availability(**args)["can_submit_referral"]
    world.faculty.role = Role.objects.get(code="STUDENT")
    world.faculty.save(update_fields=["role"])
    with pytest.raises(FacultyReferralError):
        faculty_services.referral_availability(**args)


def test_availability_api_requires_real_faculty_session_and_projects_only_safe_facts(world):
    client = Client()
    path = "/api/v1/faculty/referrals/availability"
    assert client.get(path).status_code == 401
    client.cookies["compass_session"] = world.issued.token
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["can_submit_referral"] is True
    assert set(response.json()) == {
        "can_confirm_student",
        "can_submit_referral",
        "can_view_submissions",
        "valid_until",
    }
    world.issued.session.revoked_at = timezone.now()
    world.issued.session.save(update_fields=["revoked_at"])
    assert client.get(path).status_code == 401


def test_cross_college_submission_encrypted_and_server_provenance(world):
    confirmation = confirm(world)
    assert confirmation["confirmed"]
    assert confirmation["student"] == {"display_name": world.student.get_full_name()}
    result, created = submit(world, confirmation["confirmation"])
    assert created and result["state"] == "SUBMITTED"
    row = Referral.objects.get(pk=result["id"])
    assert row.submitted_by_id == world.faculty.pk
    assert row.faculty_home_college_id == world.cas.pk
    assert row.student_college_at_submission_id == world.ccms.pk
    assert row.recorded_by_id is None and row.received_at is None
    assert row.submission_channel == "FACULTY_PORTAL"
    assert row.submission_policy_digest == world.submission.digest
    assert row.submission_policy_event_id == world.submission.activation_event_id
    content = read_referral_confidential_content(row)
    assert content.reason == "Synthetic confidential reason"
    assert content.referrer_name == world.faculty.get_full_name()
    assert content.reason not in row.confidential_content_ciphertext
    assert content.referrer_name not in row.confidential_content_ciphertext
    assert set(result) == {
        "id",
        "reference_code",
        "submitted_at",
        "state",
        "student",
        "received_at",
        "closed_at",
    }
    assert not ReferralAction.objects.exists()
    assert (
        AuditEvent.objects.filter(
            action="referral.faculty.submitted", target_id=str(row.pk)
        ).count()
        == 1
    )


def test_actual_provider_defaults_deny_digital_form_and_lookup(world, monkeypatch):
    ticket = confirm(world)["confirmation"]
    monkeypatch.setattr(faculty_policy, "get_approved_lookup_policy", lambda: None)
    with pytest.raises(FacultyReferralError, match="unavailable") as exc:
        confirm(world)
    assert exc.value.code.endswith("lookup_policy_unconfirmed")
    monkeypatch.setattr(faculty_policy, "get_approved_submission_policy", lambda: None)
    with pytest.raises(FacultyReferralError) as exc:
        submit(world, ticket)
    assert exc.value.code.endswith("submission_policy_unconfirmed")
    assert not Referral.objects.exists()
    assert not ReferralReferenceCounter.objects.exists()


def test_capability_ceiling_and_dependency_revocation(world):
    assert effective_capabilities(world.faculty) == FACULTY_CAPABILITY_CEILING
    for code in (
        "accounts.manage",
        "referrals.manage",
        "referrals.view",
        "counseling.view_assigned",
    ):
        UserCapabilityOverride.objects.create(
            user=world.faculty,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic malformed override",
        )
    assert effective_capabilities(world.faculty) == FACULTY_CAPABILITY_CEILING
    UserCapabilityOverride.objects.create(
        user=world.faculty,
        capability=Capability.objects.get(code="referrals.view_submitted_self"),
        effect="REVOKE",
        reason="Synthetic",
    )
    assert effective_capabilities(world.faculty) == frozenset()
    with pytest.raises(FacultyReferralError):
        confirm(world)


@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "inactive",
        "wrong_role",
        "no_placement",
        "retired_college",
        "retired_campus",
        "out_of_policy",
    ],
)
def test_exact_confirmation_uniform_negatives_no_account_or_placement_leak(world, invalid):
    identifier = world.student.institutional_id
    if invalid == "missing":
        identifier = "DOES-NOT-EXIST"
    elif invalid == "inactive":
        world.student.is_active = False
        world.student.save(update_fields=["is_active"])
    elif invalid == "wrong_role":
        world.student.role = Role.objects.get(code="FACULTY")
        world.student.save(update_fields=["role"])
    elif invalid == "no_placement":
        StudentAffiliation.objects.filter(student=world.student).delete()
    elif invalid == "retired_college":
        world.ccms.is_active = False
        world.ccms.save(update_fields=["is_active"])
    elif invalid == "out_of_policy":
        world.lookup = seal(
            replace(world.lookup, student_college_ids=frozenset({world.cas.pk})),
            "STUDENT_CONFIRMATION",
        )
    else:
        world.campus.is_active = False
        world.campus.save(update_fields=["is_active"])
        # Keep Faculty home independently valid beneath another active Campus.
        from compass.organization.models import Campus

        other = Campus.objects.create(code="OTHER", name="Other")
        world.cas.campus = other
        world.cas.save(update_fields=["campus"])
    result = faculty_services.confirm_student(
        actor=world.faculty,
        actor_session=world.issued.session,
        institutional_id=identifier,
        ip_address="127.0.0.1",
    )
    assert result == {"confirmed": False, "student": None, "confirmation": None, "expires_at": None}
    assert not Referral.objects.exists()


def test_confirmation_rate_limit_is_per_actor_and_ip_and_always_fail_closed(
    world, monkeypatch, settings
):
    world.lookup = seal(replace(world.lookup, actor_attempt_limit=1), "STUDENT_CONFIRMATION")
    assert confirm(world)["confirmed"]
    with pytest.raises(FacultyReferralError) as exc:
        confirm(world)
    assert exc.value.status == 429
    assert world.student.institutional_id not in repr(world.limiter.counts)
    settings.RATE_LIMITER_FAIL_OPEN = True

    def unavailable(*args):
        raise RateLimitUnavailable()

    monkeypatch.setattr(world.limiter, "consume", unavailable)
    with pytest.raises(FacultyReferralError) as exc:
        confirm(world)
    assert exc.value.status == 503


def test_policy_requires_current_evidence_exact_form_and_eligible_actor(world):
    ticket = confirm(world)["confirmation"]
    for change in (
        {"activation_event_id": uuid4()},
        {"form_revision": "2"},
        {"valid_until": timezone.now() - timedelta(seconds=1)},
        {"faculty_ids": frozenset({world.other_faculty.pk})},
    ):
        old = world.submission
        world.submission = replace(old, **change)
        with pytest.raises(FacultyReferralError):
            submit(world, ticket)
        world.submission = old
    assert not Referral.objects.exists()


@pytest.mark.parametrize(
    "change",
    [
        "inactive",
        "role",
        "home",
        "session",
        "student_placement",
        "student_id",
        "expiry",
        "other_actor",
        "tamper",
    ],
)
def test_confirmation_never_bypasses_current_account_affiliation_or_student_state(world, change):
    ticket = confirm(world)["confirmation"]
    args = {}
    if change == "inactive":
        world.faculty.is_active = False
        world.faculty.save(update_fields=["is_active"])
    elif change == "role":
        world.faculty.role = Role.objects.get(code="STUDENT")
        world.faculty.save(update_fields=["role"])
    elif change == "home":
        FacultyAffiliation.objects.filter(faculty=world.faculty).update(resource_version=2)
    elif change == "session":
        world.issued.session.revoked_at = timezone.now()
        world.issued.session.save(update_fields=["revoked_at"])
    elif change == "student_placement":
        StudentAffiliation.objects.filter(student=world.student).delete()
    elif change == "student_id":
        world.student.institutional_id = "CHANGED-ID"
        world.student.save(update_fields=["institutional_id", "updated_at"])
    elif change == "other_actor":
        args = dict(actor=world.other_faculty, actor_session=world.other_issued.session)
    elif change == "tamper":
        ticket += "tampered"
    else:
        from django.core import signing

        payload = signing.Signer(salt=faculty_services.CONFIRMATION_SALT).unsign_object(ticket)
        payload["issued_at"] -= 301
        ticket = signing.Signer(salt=faculty_services.CONFIRMATION_SALT).sign_object(payload)
    with pytest.raises(FacultyReferralError):
        submit(world, ticket, **args)
    assert not Referral.objects.exists()


def test_idempotency_identical_replay_stays_stable_and_changed_payload_conflicts(world):
    ticket = confirm(world)["confirmation"]
    initial, created = submit(world, ticket)
    assert created
    again, created = submit(world, ticket)
    assert not created and again == initial
    assert Referral.objects.count() == 1
    assert ReferralReferenceCounter.objects.get().next_value == 2
    assert AuditEvent.objects.filter(action="referral.faculty.submitted").count() == 1
    with pytest.raises(ReferralCreationConflict):
        submit(world, ticket, reason="Changed concern")


def test_own_submission_queries_never_read_another_faculty_or_operational_details(world):
    result, _ = submit(world)
    own = dict(actor=world.faculty, actor_session=world.issued.session)
    other = dict(actor=world.other_faculty, actor_session=world.other_issued.session)
    assert faculty_services.list_own_submissions(**own)["items"] == [result]
    assert faculty_services.list_own_submissions(**other)["items"] == []
    with pytest.raises(ReferralNotFound):
        faculty_services.get_own_submission(**other, referral_id=result["id"])
    assert faculty_services.get_own_submission(**own, referral_id=result["id"]) == result
    with pytest.raises(ReferralNotFound):
        faculty_services.get_own_submission(**own, referral_id=uuid4())
    Referral.objects.filter(pk=result["id"]).update(voided_at=timezone.now())
    assert faculty_services.list_own_submissions(**own)["items"] == []


@pytest.mark.parametrize(
    "field",
    [
        "submitted_by_id",
        "submitted_at",
        "faculty_home_college_id",
        "student_college_at_submission_id",
        "submission_policy_digest",
        "submission_channel",
        "student_id",
        "reference_code",
    ],
)
def test_database_rejects_rewriting_digital_provenance(world, field):
    result, _ = submit(world)
    row = Referral.objects.get(pk=result["id"])
    replacement = {
        "submitted_by_id": world.other_faculty.pk,
        "submitted_at": timezone.now() + timedelta(seconds=1),
        "faculty_home_college_id": world.ccms.pk,
        "student_college_at_submission_id": world.cas.pk,
        "submission_policy_digest": "a" * 64,
        "submission_channel": "GCO_RECORDED",
        "student_id": world.other_faculty.pk,
        "reference_code": "CHANGED",
    }[field]
    with pytest.raises(IntegrityError), transaction.atomic():
        Referral.objects.filter(pk=row.pk).update(**{field: replacement})
    assert Referral.objects.get(pk=row.pk).reference_code == row.reference_code


def test_failed_audit_rolls_back_ciphertext_reference_and_submission(world, monkeypatch):
    ticket = confirm(world)["confirmation"]

    def failed(**kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(faculty_services, "record_event", failed)
    with pytest.raises(RuntimeError):
        submit(world, ticket)
    assert not Referral.objects.exists() and not ReferralReferenceCounter.objects.exists()
    assert not AuditEvent.objects.filter(action="referral.created").exists()


def test_strict_api_safe_dtos_csrf_and_no_gco_or_directory_authority(world):
    client = Client(enforce_csrf_checks=True)
    client.cookies["compass_session"] = world.issued.token
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    headers = {"HTTP_X_CSRFTOKEN": csrf}

    def post(path, data, **extra):
        return client.post(
            path, json.dumps(data), content_type="application/json", **headers, **extra
        )

    path = "/api/v1/faculty/referrals"
    assert (
        client.post(
            path + "/student-confirmation",
            json.dumps({"institutional_id": world.student.institutional_id}),
            content_type="application/json",
        ).status_code
        == 403
    )
    response = post(
        path + "/student-confirmation", {"institutional_id": world.student.institutional_id}
    )
    assert response.status_code == 200
    data = {
        "confirmation": response.json()["confirmation"],
        "course_year_block": "Declared course",
        "reason": "Secret API reason",
    }
    for field in (
        "student_id",
        "submitted_by",
        "submitted_at",
        "referrer_name",
        "received_at",
        "faculty_home_college_id",
        "state",
        "recorded_by",
        "form_revision_id",
    ):
        assert (
            post(
                path, {**data, field: str(uuid4())}, HTTP_IDEMPOTENCY_KEY="api-identity"
            ).status_code
            == 422
        )
    response = post(path, data, HTTP_IDEMPOTENCY_KEY="api-referral")
    assert response.status_code == 201
    assert "reason" not in response.json() and "Secret API reason" not in response.content.decode()
    assert post(path, data, HTTP_IDEMPOTENCY_KEY="api-referral").status_code == 200
    assert client.get(path).json()["items"] == [response.json()]
    for endpoint in (
        "/api/v1/accounts",
        "/api/v1/referrals",
        "/api/v1/referrals/students",
        "/api/v1/guidance-followups",
        f"/api/v1/referrals/{response.json()['id']}",
        f"/api/v1/referrals/{response.json()['id']}/pdf",
    ):
        assert client.get(endpoint).status_code == 403
    assert post(path + "/student-confirmation", {"search": "Student"}).status_code == 422
    gco_path = f"/api/v1/referrals/{response.json()['id']}"
    assert (
        client.patch(
            gco_path + "/status",
            json.dumps({"status_note": "Unauthorized"}),
            content_type="application/json",
            **headers,
        ).status_code
        == 403
    )
    assert post(gco_path + "/void", {"reason": "Unauthorized"}).status_code == 403
    assert (
        post(
            gco_path + "/actions",
            {
                "action_type": "CALL_PARENT_GUARDIAN",
                "occurred_at": timezone.now().isoformat(),
                "remarks": "Unauthorized",
            },
        ).status_code
        == 403
    )
    row = Referral.objects.get(pk=response.json()["id"])
    assert row.voided_at is None and not row.actions.exists()


def test_paper_referrer_name_never_creates_faculty_ownership(world):
    from compass.audit.context import AuditContext
    from compass.organization.models import CounselorResponsibility
    from compass.referrals.services import create_referral
    from tests.faculty_referral_helpers import person

    counselor = person("paper-encoder", "COUNSELOR")
    CounselorResponsibility.objects.create(counselor=counselor, college=world.ccms)
    row = create_referral(
        actor=counselor,
        student_id=world.student.pk,
        course_year_block="Paper",
        reason="Paper reason",
        referrer_name=world.faculty.get_full_name(),
        referred_on=timezone.localdate(),
        received_at=None,
        idempotency_key="paper-matching-name",
        request_fingerprint="e" * 64,
        context=AuditContext.user(counselor),
    )
    assert row.submitted_by_id is None and row.submission_channel == "GCO_RECORDED"
    assert row.recorded_by_id == counselor.pk
    args = dict(actor=world.faculty, actor_session=world.issued.session)
    assert faculty_services.list_own_submissions(**args)["items"] == []
    with pytest.raises(ReferralNotFound):
        faculty_services.get_own_submission(**args, referral_id=row.pk)


@pytest.mark.parametrize(
    "role", ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]
)
def test_other_roles_cannot_use_faculty_contracts_even_with_raw_grants(world, role):
    from compass.authentication.sessions import create_auth_session
    from tests.faculty_referral_helpers import person

    actor = person("denied-" + role, role)
    for code in FACULTY_CAPABILITY_CEILING:
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic incompatible grant",
        )
    assert FACULTY_CAPABILITY_CEILING.isdisjoint(effective_capabilities(actor))
    with pytest.raises(FacultyReferralError):
        confirm(world, actor=actor, issued=create_auth_session(actor))


def test_reference_uses_philippine_year_not_utc_year(world, monkeypatch):
    from datetime import UTC, datetime

    from compass.authentication.models import AuthSession

    instant = datetime(2026, 12, 31, 16, 5, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    AuthSession.objects.filter(pk=world.issued.session.pk).update(
        expires_at=instant + timedelta(days=1)
    )
    world.lookup = seal(
        replace(
            world.lookup,
            valid_from=instant - timedelta(days=1),
            valid_until=instant + timedelta(days=1),
        ),
        "STUDENT_CONFIRMATION",
    )
    world.submission = seal(
        replace(
            world.submission,
            valid_from=world.lookup.valid_from,
            valid_until=world.lookup.valid_until,
            lookup_policy_digest=world.lookup.digest,
        ),
        "DIGITAL_SUBMISSION",
    )
    result, created = submit(world)
    assert created and result["reference_code"] == "REF-2027-000001"
    row = Referral.objects.get(pk=result["id"])
    assert row.referred_on.isoformat() == "2027-01-01" and row.submitted_at == instant


def test_identical_replay_after_confirmation_expiry_or_home_change_does_not_resubmit(
    world, monkeypatch
):
    ticket = confirm(world)["confirmation"]
    initial, _ = submit(world, ticket)
    later = timezone.now() + timedelta(seconds=301)
    monkeypatch.setattr(timezone, "now", lambda: later)
    FacultyAffiliation.objects.filter(faculty=world.faculty).update(
        college=world.ccms, resource_version=2
    )
    result, created = submit(world, ticket)
    assert not created and result == initial
    assert Referral.objects.get().faculty_home_college_id == world.cas.pk


def test_approval_expiring_during_reference_contention_rolls_back_allocation(world, monkeypatch):
    ticket = confirm(world)["confirmation"]
    original = faculty_services._allocate_reference

    def allocate(*, at):
        reference = original(at=at)
        world.submission = replace(
            world.submission, valid_until=timezone.now() - timedelta(seconds=1)
        )
        return reference

    monkeypatch.setattr(faculty_services, "_allocate_reference", allocate)
    with pytest.raises(FacultyReferralError):
        submit(world, ticket)
    assert not Referral.objects.exists() and not ReferralReferenceCounter.objects.exists()


@pytest.mark.parametrize("invalid", ["missing", "retired_college", "retired_campus"])
def test_faculty_home_eligibility_cannot_be_replaced_by_capabilities(world, invalid):
    if invalid == "missing":
        FacultyAffiliation.objects.filter(faculty=world.faculty).update(college=None)
    elif invalid == "retired_college":
        world.cas.is_active = False
        world.cas.save(update_fields=["is_active"])
    else:
        world.campus.is_active = False
        world.campus.save(update_fields=["is_active"])
    assert effective_capabilities(world.faculty) == FACULTY_CAPABILITY_CEILING
    with pytest.raises(FacultyReferralError) as error:
        confirm(world)
    assert error.value.code == "faculty_referral_affiliation_unavailable"


def test_approved_policy_for_other_faculty_does_not_admit_current_actor(world):
    ticket = confirm(world)["confirmation"]
    world.submission = seal(
        replace(world.submission, faculty_ids=frozenset({world.other_faculty.pk})),
        "DIGITAL_SUBMISSION",
    )
    with pytest.raises(FacultyReferralError) as error:
        submit(world, ticket)
    assert error.value.code == "faculty_referral_not_permitted"


def test_shared_ip_attempt_bound_applies_across_eligible_faculty(world):
    world.lookup = seal(replace(world.lookup, ip_attempt_limit=1), "STUDENT_CONFIRMATION")
    assert confirm(world)["confirmed"]
    with pytest.raises(FacultyReferralError) as error:
        confirm(world, actor=world.other_faculty, issued=world.other_issued)
    assert error.value.status == 429


def test_read_only_faculty_can_keep_own_projection_without_submission_authority(world):
    result, _ = submit(world)
    UserCapabilityOverride.objects.create(
        user=world.faculty,
        capability=Capability.objects.get(code="referrals.submit_self"),
        effect="REVOKE",
        reason="Synthetic read-only",
    )
    assert effective_capabilities(world.faculty) == frozenset({"referrals.view_submitted_self"})
    assert (
        faculty_services.get_own_submission(
            actor=world.faculty, actor_session=world.issued.session, referral_id=result["id"]
        )
        == result
    )
    with pytest.raises(FacultyReferralError):
        confirm(world)


def test_completed_replay_keeps_saved_form_when_current_form_configuration_changes(world):
    from compass.institutional_forms.models import FormRevision
    from compass.referrals.services import ReferralConfigurationConflict

    ticket = confirm(world)["confirmation"]
    result, _ = submit(world, ticket)
    FormRevision.objects.filter(pk=Referral.objects.get().form_revision_id).update(
        status="INACTIVE"
    )
    assert submit(world, ticket) == (result, False)
    with pytest.raises(ReferralConfigurationConflict):
        submit(world, ticket, idempotency_key="new-after-form-retirement")
    assert Referral.objects.count() == 1


def test_stale_browser_session_after_deactivation_cannot_submit(world):
    ticket = confirm(world)["confirmation"]
    client = Client()
    client.cookies["compass_session"] = world.issued.token
    world.faculty.is_active = False
    world.faculty.save(update_fields=["is_active"])
    response = client.post(
        "/api/v1/faculty/referrals",
        json.dumps(
            {
                "confirmation": ticket,
                "course_year_block": "Declared course",
                "reason": "Confidential reason",
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="stale-browser",
    )
    assert response.status_code == 401
    assert not Referral.objects.exists()


def test_submission_emits_no_operational_or_student_side_effects(world):
    from compass.appointments.models import Appointment
    from compass.guidance_followups.models import GuidanceFollowUp
    from compass.notifications.models import EmailDelivery, Notification

    submit(world)
    assert not Appointment.objects.exists()
    assert not GuidanceFollowUp.objects.exists()
    assert not ReferralAction.objects.exists()
    assert not Notification.objects.exists() and not EmailDelivery.objects.exists()


def test_gco_can_process_faculty_origin_without_changing_origin_or_own_projection(world):
    from compass.audit.context import AuditContext
    from compass.organization.models import CounselorResponsibility
    from compass.referrals import services
    from tests.faculty_referral_helpers import person

    result, _ = submit(world)
    counselor = person("processing-counselor", "COUNSELOR")
    CounselorResponsibility.objects.create(counselor=counselor, college=world.ccms)
    args = dict(actor=counselor, referral_id=result["id"], context=AuditContext.user(counselor))
    row = services.update_status_note(**args, status_note="Private GCO handling")
    services.record_action(
        **args,
        action_type="CALL_PARENT_GUARDIAN",
        occurred_at=timezone.now(),
        remarks="Private operational remarks",
    )
    source = services.build_referral_render_context(
        services.get_referral(
            actor=counselor,
            referral_id=row.pk,
        )
    )["referral"]
    assert source["reason"] == "Synthetic confidential reason"
    assert source["referrer_name"] == world.faculty.get_full_name()
    assert source["status_note"] == "Private GCO handling"
    assert (
        faculty_services.get_own_submission(
            actor=world.faculty,
            actor_session=world.issued.session,
            referral_id=row.pk,
        )
        == result
    )
    row = services.void_referral(**args, reason="Authorized GCO correction")
    assert row.submitted_by_id == world.faculty.pk and row.recorded_by_id is None
    assert row.submission_policy_digest == world.submission.digest and row.received_at is None
    content = read_referral_confidential_content(row)
    assert content.reason == "Synthetic confidential reason"
    assert content.referrer_name == world.faculty.get_full_name()
    with pytest.raises(ReferralNotFound):
        faculty_services.get_own_submission(
            actor=world.faculty,
            actor_session=world.issued.session,
            referral_id=row.pk,
        )
