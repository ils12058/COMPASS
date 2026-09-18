from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.account_management.services import serialize_account
from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    User,
    UserDesignation,
)
from compass.accounts.profiles import (
    ADDRESS_MAX_LENGTH,
    PersonProfileContext,
    get_person_profile_context,
    update_my_profile,
)
from compass.activity.presenters import MY_ACTIVITY_PRESENTERS, SECURITY_ACTIVITY_PRESENTERS
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.models import AuthSession
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.inventory.models import StudentInventory
from compass.organization.api import _person
from compass.organization.models import AcademicYear
from compass.referrals.models import Referral

PROFILE_FIELDS = {
    "date_of_birth",
    "civil_status",
    "contact_number",
    "current_address",
    "permanent_address",
}


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(
    email: str,
    *,
    role: str = "STUDENT",
    first_name: str = "Profile",
    last_name: str = "User",
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name,
        last_name=last_name,
    )


def auth_client(user: User, *, mfa_verified_at=None) -> tuple[Client, AuthSession]:
    issued = create_auth_session(user, mfa_verified_at=mfa_verified_at, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client, issued.session


def csrf_headers(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def patch_profile(client: Client, payload: dict[str, object]):
    return client.patch(
        "/api/v1/me/profile",
        data=json.dumps(payload, default=str),
        content_type="application/json",
        **csrf_headers(client),
    )


@pytest.mark.django_db
def test_user_directly_owns_minimal_reusable_profile_fields_without_personalprofile_model():
    sync_policy()
    user = make_user("defaults@example.edu")

    assert user.date_of_birth is None
    assert user.civil_status == ""
    assert user.contact_number == ""
    assert user.current_address == ""
    assert user.permanent_address == ""
    assert user.profile_photo_object_key is None
    assert user.profile_photo_updated_at is None

    field_names = {field.name for field in User._meta.get_fields()}
    assert PROFILE_FIELDS <= field_names
    assert {
        "email",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "profile_photo_object_key",
        "profile_photo_updated_at",
    } <= field_names
    assert "age" not in field_names
    assert "course" not in field_names
    assert "program" not in field_names
    assert "major" not in field_names
    assert "year_level" not in field_names
    assert "block" not in field_names
    assert "student_number" not in field_names
    assert "college" not in field_names

    with pytest.raises(LookupError):
        apps.get_model("accounts", "PersonalProfile")


@pytest.mark.django_db
def test_profile_foundation_does_not_change_capability_policy_counts():
    sync_policy()
    assert Capability.objects.count() == 49
    assert RoleCapability.objects.count() == 58
    assert DesignationCapability.objects.count() == 12
    assert not Capability.objects.filter(code__startswith="profile.").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_code",
    ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN"],
)
def test_every_active_primary_role_can_get_only_its_own_profile(role_code):
    sync_policy()
    user = make_user(f"{role_code.lower()}@example.edu", role=role_code)
    user.date_of_birth = timezone.localdate() - timedelta(days=8000)
    user.civil_status = "Single"
    user.contact_number = "09171234567"
    user.current_address = "Current address"
    user.permanent_address = "Permanent address"
    user.save(
        update_fields=[
            "date_of_birth",
            "civil_status",
            "contact_number",
            "current_address",
            "permanent_address",
            "updated_at",
        ]
    )
    client, _session = auth_client(user)

    response = client.get("/api/v1/me/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.pk)
    assert body["email"] == user.email
    assert body["first_name"] == user.first_name
    assert body["last_name"] == user.last_name
    assert body["full_name"] == user.get_full_name()
    assert body["role"] == role_code
    assert body["date_of_birth"] == user.date_of_birth.isoformat()
    assert body["civil_status"] == "Single"
    assert body["contact_number"] == "09171234567"
    assert body["current_address"] == "Current address"
    assert body["permanent_address"] == "Permanent address"
    assert body["profile_photo_url"] is None
    assert body["profile_photo_updated_at"] is None
    assert "is_active" not in body
    assert "designations" not in body
    assert "profile_photo_object_key" not in body

    assert client.get(f"/api/v1/me/profile/{user.pk}").status_code == 404


@pytest.mark.django_db
def test_dpo_designation_has_self_profile_only_and_no_generic_profile_directory():
    sync_policy()
    dpo = make_user("dpo@example.edu", role="IT_ADMIN")
    other = make_user("other@example.edu")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    client, _session = auth_client(dpo)

    own = client.get("/api/v1/me/profile")
    assert own.status_code == 200
    assert own.json()["user_id"] == str(dpo.pk)

    assert client.get(f"/api/v1/accounts/{other.pk}/profile").status_code == 404
    assert (
        client.patch(
            f"/api/v1/accounts/{other.pk}/profile",
            data=json.dumps({"civil_status": "Single"}),
            content_type="application/json",
            **csrf_headers(client),
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_unauthenticated_profile_requests_are_rejected():
    client = Client()
    assert client.get("/api/v1/me/profile").status_code == 401
    response = client.patch(
        "/api/v1/me/profile",
        data=json.dumps({"civil_status": "Single"}),
        content_type="application/json",
        **csrf_headers(client),
    )
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_code",
    ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN"],
)
def test_each_role_can_patch_own_profile_without_recent_mfa_or_session_rotation(role_code):
    sync_policy()
    user = make_user(f"edit-{role_code.lower()}@example.edu", role=role_code)
    client, session = auth_client(user, mfa_verified_at=None)
    original_session_id = session.pk

    response = patch_profile(
        client,
        {
            "date_of_birth": (timezone.localdate() - timedelta(days=7000)).isoformat(),
            "civil_status": "  Single  ",
            "contact_number": "  +63 917 123 4567  ",
            "current_address": "  Line 1\nLine 2  ",
            "permanent_address": "  Home province  ",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["civil_status"] == "Single"
    assert body["contact_number"] == "+63 917 123 4567"
    assert body["current_address"] == "Line 1\nLine 2"
    assert body["permanent_address"] == "Home province"

    user.refresh_from_db()
    assert user.civil_status == "Single"
    assert user.current_address == "Line 1\nLine 2"

    session.refresh_from_db()
    assert session.pk == original_session_id
    assert session.revoked_at is None
    assert session.mfa_verified_at is None
    assert client.get("/api/v1/me/profile").status_code == 200


@pytest.mark.django_db
def test_profile_patch_is_true_partial_and_dob_can_be_explicitly_cleared():
    sync_policy()
    user = make_user("partial@example.edu")
    user.date_of_birth = timezone.localdate() - timedelta(days=9000)
    user.civil_status = "Single"
    user.contact_number = "old"
    user.current_address = "Current"
    user.permanent_address = "Permanent"
    user.save(
        update_fields=[
            "date_of_birth",
            "civil_status",
            "contact_number",
            "current_address",
            "permanent_address",
            "updated_at",
        ]
    )
    client, _session = auth_client(user)

    first = patch_profile(client, {"contact_number": " new "})
    assert first.status_code == 200
    user.refresh_from_db()
    assert user.contact_number == "new"
    assert user.civil_status == "Single"
    assert user.current_address == "Current"
    assert user.permanent_address == "Permanent"
    assert user.date_of_birth is not None

    cleared = patch_profile(
        client,
        {
            "date_of_birth": None,
            "civil_status": "   ",
            "current_address": " \n  ",
        },
    )
    assert cleared.status_code == 200
    user.refresh_from_db()
    assert user.date_of_birth is None
    assert user.civil_status == ""
    assert user.current_address == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "changed@example.edu"),
        ("first_name", "Changed"),
        ("last_name", "Changed"),
        ("role", "COUNSELOR"),
        ("is_active", False),
        ("profile_photo_object_key", "profile-photos/users/private.webp"),
        ("unknown_field", "value"),
    ],
)
def test_profile_patch_rejects_identity_security_photo_and_unknown_fields(field, value):
    sync_policy()
    user = make_user(f"forbid-{field.replace('_', '-')}@example.edu")
    client, _session = auth_client(user)

    response = patch_profile(client, {field: value})
    assert response.status_code == 422


@pytest.mark.django_db
def test_profile_validation_rejects_future_dob_but_allows_today_and_old_dates_without_age_rules():
    sync_policy()
    user = make_user("dob@example.edu")
    client, _session = auth_client(user)

    future = patch_profile(
        client,
        {"date_of_birth": (timezone.localdate() + timedelta(days=1)).isoformat()},
    )
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "invalid_profile_request"

    today = patch_profile(client, {"date_of_birth": timezone.localdate().isoformat()})
    assert today.status_code == 200

    old = patch_profile(
        client,
        {"date_of_birth": (timezone.localdate() - timedelta(days=365 * 120)).isoformat()},
    )
    assert old.status_code == 200


@pytest.mark.django_db
def test_profile_validation_preserves_multiline_address_and_rejects_oversized_values():
    sync_policy()
    user = make_user("bounds@example.edu")
    client, _session = auth_client(user)

    multiline = patch_profile(
        client,
        {"current_address": "  First line\nSecond line\n  Unit 3  "},
    )
    assert multiline.status_code == 200
    assert multiline.json()["current_address"] == "First line\nSecond line\n  Unit 3"

    oversized = patch_profile(
        client,
        {"permanent_address": "x" * (ADDRESS_MAX_LENGTH + 1)},
    )
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "invalid_profile_request"

    null_text = patch_profile(client, {"contact_number": None})
    assert null_text.status_code == 422


@pytest.mark.django_db
def test_profile_update_emits_one_safe_audit_event_and_noop_emits_none():
    sync_policy()
    user = make_user("audit-profile@example.edu")
    client, _session = auth_client(user)

    changed = patch_profile(
        client,
        {
            "date_of_birth": "2001-02-03",
            "civil_status": "Single",
            "contact_number": "09171234567",
            "current_address": "Very Private Current Address",
            "permanent_address": "Very Private Permanent Address",
        },
    )
    assert changed.status_code == 200

    events = AuditEvent.objects.filter(action="profile.updated", target_id=str(user.pk))
    assert events.count() == 1
    event = events.get()
    assert event.actor_user_id == user.pk
    assert event.target_type == "accounts.user"
    assert event.metadata == {
        "changed_fields": [
            "civil_status",
            "contact_number",
            "current_address",
            "date_of_birth",
            "permanent_address",
        ]
    }
    serialized = json.dumps(event.metadata)
    for sensitive in (
        "2001-02-03",
        "Single",
        "09171234567",
        "Very Private Current Address",
        "Very Private Permanent Address",
    ):
        assert sensitive not in serialized

    no_op = patch_profile(client, {"contact_number": "09171234567"})
    assert no_op.status_code == 200
    assert AuditEvent.objects.filter(action="profile.updated", target_id=str(user.pk)).count() == 1


@pytest.mark.django_db
def test_profile_update_is_generic_my_activity_but_not_security_activity():
    sync_policy()
    user = make_user("activity-profile@example.edu")
    client, _session = auth_client(user)

    assert patch_profile(client, {"civil_status": "Single"}).status_code == 200
    my_activity = client.get("/api/v1/me/activity")
    security_activity = client.get("/api/v1/me/security-activity")
    assert my_activity.status_code == security_activity.status_code == 200

    assert any(item["type"] == "profile.updated" for item in my_activity.json()["items"])
    assert all(item["type"] != "profile.updated" for item in security_activity.json()["items"])
    assert "profile.updated" in MY_ACTIVITY_PRESENTERS
    assert "profile.updated" not in SECURITY_ACTIVITY_PRESENTERS
    assert "Single" not in json.dumps(my_activity.json())


@pytest.mark.django_db
def test_person_profile_context_is_immutable_accounts_only_current_data(django_assert_num_queries):
    sync_policy()
    student = make_user(
        "resolver-student@example.edu",
        first_name="Current",
        last_name="Student",
    )
    student.date_of_birth = timezone.localdate() - timedelta(days=8000)
    student.civil_status = "Single"
    student.contact_number = "0917"
    student.current_address = "Current"
    student.permanent_address = "Permanent"
    student.save(
        update_fields=[
            "date_of_birth",
            "civil_status",
            "contact_number",
            "current_address",
            "permanent_address",
            "updated_at",
        ]
    )

    with django_assert_num_queries(0):
        context = get_person_profile_context(student)
    assert isinstance(context, PersonProfileContext)
    assert context.user_id == student.pk
    assert context.full_name == "Current Student"
    assert context.email == student.email
    assert context.date_of_birth == student.date_of_birth
    assert context.civil_status == "Single"
    assert context.contact_number == "0917"
    assert context.current_address == "Current"
    assert context.permanent_address == "Permanent"

    counselor = make_user("resolver-counselor@example.edu", role="COUNSELOR")
    with django_assert_num_queries(0):
        counselor_context = get_person_profile_context(counselor)
    assert counselor_context.full_name == counselor.get_full_name()
    assert counselor_context.date_of_birth is None
    assert counselor_context.contact_number == ""

    with pytest.raises((AttributeError, TypeError)):
        context.contact_number = "mutated"


@pytest.mark.django_db
def test_self_profile_uses_existing_signed_photo_projection_without_exposing_object_key():
    sync_policy()
    user = make_user("photo-profile@example.edu")
    user.profile_photo_object_key = f"profile-photos/users/{user.pk}/photo.webp"
    user.profile_photo_updated_at = timezone.now()
    user.save(
        update_fields=[
            "profile_photo_object_key",
            "profile_photo_updated_at",
            "updated_at",
        ]
    )
    client, _session = auth_client(user)

    signed = "https://signed.example.test/private.webp?signature=temporary"
    with patch("compass.accounts.profile_api.profile_photo_url", return_value=signed):
        response = client.get("/api/v1/me/profile")
    assert response.status_code == 200
    assert response.json()["profile_photo_url"] == signed
    assert response.json()["profile_photo_updated_at"] is not None
    assert "profile_photo_object_key" not in response.json()


@pytest.mark.django_db
def test_admin_and_organization_serializers_do_not_leak_current_profile_fields():
    sync_policy()
    user = make_user("privacy@example.edu")
    user.date_of_birth = timezone.localdate() - timedelta(days=9000)
    user.civil_status = "Private"
    user.contact_number = "Private phone"
    user.current_address = "Private address"
    user.permanent_address = "Private permanent address"
    user.save(
        update_fields=[
            "date_of_birth",
            "civil_status",
            "contact_number",
            "current_address",
            "permanent_address",
            "updated_at",
        ]
    )

    summary = serialize_account(user)
    detail = serialize_account(user, detail=True)
    organization_person = _person(user)
    for payload in (summary, detail, organization_person):
        assert PROFILE_FIELDS.isdisjoint(payload)
        assert "profile_photo_object_key" not in payload


@pytest.mark.django_db
def test_profile_edit_does_not_rewrite_inventory_referral_or_call_slip_history():
    sync_policy()
    student = make_user("snapshot-student@example.edu")
    counselor = make_user("snapshot-counselor@example.edu", role="COUNSELOR")

    family = FormFamily.objects.create(key="profile_snapshot_test", title="Profile snapshot test")
    revision = FormRevision.objects.create(
        family=family,
        official_code="TEST-PROFILE-SNAPSHOT",
        official_revision="0",
        internal_schema_version=1,
        status="ACTIVE",
    )
    academic_year = AcademicYear.objects.create(label="2098-2099")

    inventory = StudentInventory.objects.create(
        student=student,
        academic_year=academic_year,
        form_revision=revision,
        full_name_snapshot="Historical Student",
        date_of_birth=timezone.localdate() - timedelta(days=10000),
        civil_status="Historical",
        contact_number="old-contact",
        current_address="old-current-address",
        permanent_address="old-permanent-address",
    )
    referral = Referral.objects.create(
        reference_code="REF-2099-999998",
        student=student,
        student_name_snapshot="Historical Referral Student",
        course_year_block_snapshot="Historical Course / 4 / A",
        reason="Historical reason",
        referrer_name="Historical Referrer",
        referred_on=timezone.localdate(),
        form_revision=revision,
        recorded_by=counselor,
    )
    call_slip = CallSlip.objects.create(
        student=student,
        student_name_snapshot="Historical Call Slip Student",
        course_year_snapshot="Historical Course / 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(days=1),
        issued_by=counselor,
        issued_by_name_snapshot="Historical Counselor",
        form_revision=revision,
        recorded_by=counselor,
    )

    update_my_profile(
        user=student,
        changes={
            "date_of_birth": timezone.localdate() - timedelta(days=7000),
            "civil_status": "Current",
            "contact_number": "new-contact",
            "current_address": "new-current-address",
            "permanent_address": "new-permanent-address",
        },
        context=AuditContext.user(student),
    )

    inventory.refresh_from_db()
    referral.refresh_from_db()
    call_slip.refresh_from_db()

    assert inventory.full_name_snapshot == "Historical Student"
    assert inventory.civil_status == "Historical"
    assert inventory.contact_number == "old-contact"
    assert inventory.current_address == "old-current-address"
    assert inventory.permanent_address == "old-permanent-address"
    assert referral.student_name_snapshot == "Historical Referral Student"
    assert referral.course_year_block_snapshot == "Historical Course / 4 / A"
    assert call_slip.student_name_snapshot == "Historical Call Slip Student"
    assert call_slip.course_year_snapshot == "Historical Course / 4"
    assert call_slip.issued_by_name_snapshot == "Historical Counselor"
