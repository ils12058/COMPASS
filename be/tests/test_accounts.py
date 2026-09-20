from datetime import timedelta
from importlib import import_module
from io import StringIO
from unittest.mock import patch

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import UUIDField
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    StudentLifecycleStatus,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.policy import CAPABILITY_CODES, designation_role_compatible
from compass.accounts.services import (
    effective_capabilities,
    is_current_student,
    set_user_capability_override,
)

User = get_user_model()


def sync_policy() -> None:
    call_command("sync_identity_policy", stdout=StringIO())


def make_user(*, role: Role | str = "STUDENT", email: str = "student@example.edu"):
    if isinstance(role, str):
        role = Role.objects.get(code=role)
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=role,
        first_name="Test",
        last_name="User",
    )


@pytest.mark.django_db
def test_custom_user_uses_uuid_email_identity_and_no_django_permission_fields():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert isinstance(User._meta.get_field("id"), UUIDField)
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []
    assert not hasattr(User, "username")
    assert not hasattr(User, "groups")
    assert not hasattr(User, "user_permissions")
    assert not hasattr(User, "is_staff")
    assert not hasattr(User, "is_superuser")

    role = Role.objects.create(code="TEST_ROLE", name="Test role")
    user = User.objects.create_user(
        email="  Reynan@Example.edu ",
        password="correct horse battery staple",
        role=role,
        first_name="Reynan",
        last_name="Test",
    )

    assert user.email == "reynan@example.edu"
    assert user.get_username() == user.email
    assert user.check_password("correct horse battery staple")
    assert user.password != "correct horse battery staple"
    assert User.objects.get_by_natural_key("REYNAN@EXAMPLE.EDU") == user


@pytest.mark.django_db
def test_postgresql_expression_constraint_rejects_case_only_email_collision():
    role = Role.objects.create(code="TEST_ROLE", name="Test role")
    User.objects.bulk_create(
        [
            User(
                email="Reynan@Example.edu",
                password=make_password("password"),
                first_name="Reynan",
                last_name="Test",
                role=role,
            )
        ]
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.bulk_create(
                [
                    User(
                        email="reynan@example.edu",
                        password=make_password("password"),
                        first_name="Another",
                        last_name="Test",
                        role=role,
                    )
                ]
            )


@pytest.mark.django_db
def test_user_manager_requires_a_known_primary_role():
    with pytest.raises(ValueError, match="primary role is required"):
        User.objects.create_user(
            email="missing-role@example.edu",
            password="password",
            first_name="Missing",
            last_name="Role",
        )
    with pytest.raises(ValueError, match="unknown primary role"):
        User.objects.create_user(
            email="unknown-role@example.edu",
            password="password",
            role="NOT_A_ROLE",
            first_name="Unknown",
            last_name="Role",
        )


@pytest.mark.django_db
def test_policy_sync_is_idempotent_and_does_not_create_django_model_permissions():
    first_output = StringIO()
    call_command("sync_identity_policy", stdout=first_output)

    assert set(Role.objects.values_list("code", flat=True)) == {
        "IT_ADMIN",
        "COUNSELOR",
        "GUIDANCE_SERVICES_STAFF",
        "STUDENT",
        "INSTITUTIONAL_OFFICER",
    }
    assert set(Designation.objects.values_list("code", flat=True)) == {
        "HEAD_GUIDANCE_COUNSELOR",
        "DPO",
    }
    assert set(Capability.objects.values_list("code", flat=True)) == set(CAPABILITY_CODES)
    assert RoleCapability.objects.count() == 77
    assert DesignationCapability.objects.count() == 18
    assert Permission.objects.filter(content_type__app_label="accounts").count() == 0

    second_output = StringIO()
    call_command("sync_identity_policy", stdout=second_output)
    assert "roles created=0 updated=0" in second_output.getvalue()
    assert "designations created=0 updated=0" in second_output.getvalue()
    assert "capabilities created=0 updated=0" in second_output.getvalue()
    assert "role grants created=0" in second_output.getvalue()
    assert Role.objects.count() == 5
    assert Designation.objects.count() == 2
    assert Capability.objects.count() == 67
    assert RoleCapability.objects.count() == 77
    assert DesignationCapability.objects.count() == 18


@pytest.mark.django_db
def test_counselor_baseline_adds_scoped_authority_without_admin_expansion():
    sync_policy()
    counselor = make_user(role="COUNSELOR", email="baseline-counselor@example.edu")
    expected = {
        "appointments.manage",
        "academic_years.view",
        "institutional_forms.view",
        "reports.view",
        "inventory.view",
        "inventory.reopen",
    }
    denied = {
        "availability.manage",
        "academic_years.manage",
        "institutional_forms.manage",
        "organization.manage",
        "services.manage",
        "document_branding.manage",
        "feedback.view_customer_feedback",
        "feedback.view_csm",
        "graduate_tracer.view",
        "exit_interviews.view",
        "exit_interviews.reopen",
        "platform_operations.view",
        "privacy_governance.view",
    }

    assert all(counselor.has_capability(code) for code in expected)
    assert all(not counselor.has_capability(code) for code in denied)

    gss = make_user(role="GUIDANCE_SERVICES_STAFF", email="baseline-gss@example.edu")
    assert not gss.has_capability("reports.view")
    assert not gss.has_capability("academic_years.view")
    assert not gss.has_capability("institutional_forms.view")


@pytest.mark.django_db
def test_user_has_one_primary_role_and_designation_assignment_is_non_duplicate():
    sync_policy()
    user = make_user(role="COUNSELOR")
    head = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    UserDesignation.objects.create(user=user, designation=head)

    assert list(user.designations.values_list("code", flat=True)) == ["HEAD_GUIDANCE_COUNSELOR"]
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserDesignation.objects.create(user=user, designation=head)


@pytest.mark.django_db
def test_effective_capabilities_combine_role_designation_and_overrides():
    sync_policy()
    user = make_user(role="COUNSELOR")
    head = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    manage = Capability.objects.get(code="accounts.manage")
    UserDesignation.objects.create(user=user, designation=head)
    DesignationCapability.objects.create(designation=head, capability=manage)

    assert effective_capabilities(user) == {
        "accounts.view",
        "accounts.manage",
        "organization.view",
        "organization.manage",
        "academic_years.view",
        "academic_years.manage",
        "institutional_forms.view",
        "institutional_forms.manage",
        "document_branding.view",
        "document_branding.manage",
        "exit_interviews.view",
        "exit_interviews.reopen",
        "services.view",
        "services.manage",
        "availability.view",
        "availability.manage",
        "availability.manage_self",
        "appointments.view_self",
        "appointments.manage",
        "counseling.view_assigned",
        "counseling.manage_assigned",
        "student_support.view",
        "shared_summaries.view_assigned",
        "shared_summaries.manage_assigned",
        "routine_interviews.view_assigned",
        "routine_interviews.manage_assigned",
        "referrals.view",
        "referrals.manage",
        "call_slips.view",
        "call_slips.manage",
        "good_moral.view",
        "good_moral.manage",
        "good_moral.issue",
        "announcements.manage",
        "resources.manage",
        "feedback.view_customer_feedback",
        "feedback.view_csm",
        "graduate_tracer.view",
        "reports.view",
        "ecounseling.view_assigned",
        "ecounseling.join_assigned",
        "ecounseling.manage_media_assigned",
    }
    assert user.has_capability("accounts.view")
    assert user.has_capability("accounts.manage")

    revoke = set_user_capability_override(
        user=user,
        capability="accounts.manage",
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Temporary separation of duties",
    )
    assert revoke.reason == "Temporary separation of duties"
    assert user.has_capability("accounts.view")
    assert user.has_capability("organization.view")
    assert user.has_capability("organization.manage")
    assert user.has_capability("academic_years.view")
    assert user.has_capability("academic_years.manage")
    assert user.has_capability("institutional_forms.view")
    assert user.has_capability("institutional_forms.manage")
    assert user.has_capability("document_branding.view")
    assert user.has_capability("document_branding.manage")
    assert user.has_capability("services.view")
    assert user.has_capability("services.manage")
    assert user.has_capability("availability.view")
    assert user.has_capability("availability.manage")
    assert user.has_capability("availability.manage_self")
    assert user.has_capability("appointments.view_self")
    assert user.has_capability("appointments.manage")
    assert user.has_capability("counseling.view_assigned")
    assert user.has_capability("counseling.manage_assigned")
    assert user.has_capability("shared_summaries.view_assigned")
    assert user.has_capability("shared_summaries.manage_assigned")
    assert user.has_capability("routine_interviews.view_assigned")
    assert user.has_capability("routine_interviews.manage_assigned")
    assert user.has_capability("referrals.view")
    assert user.has_capability("referrals.manage")
    assert user.has_capability("call_slips.view")
    assert user.has_capability("call_slips.manage")
    assert user.has_capability("good_moral.view")
    assert user.has_capability("good_moral.manage")
    assert user.has_capability("good_moral.issue")
    assert user.has_capability("graduate_tracer.view")
    assert user.has_capability("reports.view")
    assert user.has_capability("ecounseling.view_assigned")
    assert user.has_capability("ecounseling.join_assigned")
    assert user.has_capability("ecounseling.manage_media_assigned")
    assert not user.has_capability("accounts.manage")

    grant = set_user_capability_override(
        user=user,
        capability=manage,
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Approved exception",
    )
    assert grant.pk == revoke.pk
    assert user.has_capability("accounts.manage")

    expired = set_user_capability_override(
        user=user,
        capability=manage,
        effect=UserCapabilityOverride.Effect.REVOKE,
        reason="Expired exception",
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert expired.pk == revoke.pk
    assert user.has_capability("accounts.manage")
    assert not user.has_capability("accounts.future")

    unknown = Capability.objects.create(code="accounts.future", name="Unknown future action")
    RoleCapability.objects.create(role=user.role, capability=unknown)
    assert "accounts.future" not in effective_capabilities(user)
    assert not user.has_capability("accounts.future")

    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    assert effective_capabilities(user) == frozenset()
    assert not user.has_capability("accounts.view")


@pytest.mark.django_db
def test_student_media_consent_capability_is_explicit():
    sync_policy()
    student = make_user(role="STUDENT")
    assert student.has_capability("ecounseling.consent_self")
    assert student.has_capability("call_slips.view_self")
    assert student.has_capability("good_moral.view_self")
    assert student.has_capability("good_moral.request_self")
    assert student.has_capability("feedback.submit_customer_feedback")
    assert student.has_capability("feedback.submit_csm")
    assert student.has_capability("graduate_tracer.view_self")
    assert student.has_capability("graduate_tracer.manage_self")
    assert not student.has_capability("graduate_tracer.view")
    assert not student.has_capability("reports.view")
    assert not student.has_capability("feedback.view_customer_feedback")
    assert not student.has_capability("feedback.view_csm")
    assert not student.has_capability("good_moral.view")
    assert not student.has_capability("good_moral.manage")
    assert not student.has_capability("good_moral.issue")
    assert not student.has_capability("call_slips.view")
    assert not student.has_capability("call_slips.manage")
    assert not student.has_capability("ecounseling.manage_media_assigned")


@pytest.mark.django_db
def test_override_requires_a_reason_and_known_capability():
    sync_policy()
    user = make_user()
    with pytest.raises(ValueError, match="reason is required"):
        set_user_capability_override(
            user=user,
            capability="accounts.view",
            effect=UserCapabilityOverride.Effect.GRANT,
            reason="   ",
        )
    with pytest.raises(ValueError, match="unknown capability"):
        set_user_capability_override(
            user=user,
            capability="not-in-policy",
            effect=UserCapabilityOverride.Effect.GRANT,
            reason="Should not authorize unknown policy",
        )


@pytest.mark.django_db
def test_create_it_admin_bootstraps_hashed_password_and_is_safe_on_repeat():
    sync_policy()
    output = StringIO()
    with patch(
        "compass.accounts.management.commands.create_it_admin.getpass.getpass",
        side_effect=["a-secure-password", "a-secure-password"],
    ):
        call_command(
            "create_it_admin",
            "--email",
            "IT.Admin@Example.edu",
            "--first-name",
            "IT",
            "--last-name",
            "Administrator",
            stdout=output,
        )

    user = User.objects.get()
    assert user.email == "it.admin@example.edu"
    assert user.role.code == "IT_ADMIN"
    assert user.check_password("a-secure-password")
    assert "a-secure-password" not in output.getvalue()

    with pytest.raises(CommandError, match="already exists"):
        call_command(
            "create_it_admin",
            "--email",
            "it.admin@example.edu",
            "--first-name",
            "Changed",
            "--last-name",
            "Name",
        )

    repeat_output = StringIO()
    call_command(
        "create_it_admin",
        "--email",
        "IT.ADMIN@EXAMPLE.EDU",
        "--first-name",
        "Changed",
        "--last-name",
        "Name",
        "--idempotent",
        stdout=repeat_output,
    )
    assert "no changes made" in repeat_output.getvalue()
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_create_it_admin_requires_policy_sync():
    with pytest.raises(CommandError, match="sync_identity_policy first"):
        call_command(
            "create_it_admin",
            "--email",
            "it-admin@example.edu",
            "--first-name",
            "IT",
            "--last-name",
            "Admin",
        )


def test_django_admin_route_remains_unavailable(client):
    response = client.get("/admin/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_student_lifecycle_defaults_constraint_and_current_student_predicate():
    sync_policy()
    student = make_user(role="STUDENT", email="lifecycle-student@example.edu")
    counselor = make_user(role="COUNSELOR", email="lifecycle-counselor@example.edu")

    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert counselor.student_lifecycle_status is None
    assert is_current_student(student)
    assert not is_current_student(counselor)

    student.student_lifecycle_status = StudentLifecycleStatus.GRADUATED
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    assert not is_current_student(student)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.filter(pk=student.pk).update(student_lifecycle_status="NOT_VALID")


@pytest.mark.django_db
def test_student_lifecycle_migration_backfills_only_existing_students():
    sync_policy()
    student = make_user(role="STUDENT", email="legacy-student@example.edu")
    counselor = make_user(role="COUNSELOR", email="legacy-counselor@example.edu")
    User.objects.filter(pk=student.pk).update(student_lifecycle_status=None)

    migration = import_module("compass.accounts.migrations.0003_user_student_lifecycle_status")
    migration.backfill_student_lifecycle_status(apps, None)

    student.refresh_from_db()
    counselor.refresh_from_db()
    assert student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    assert counselor.student_lifecycle_status is None


@pytest.mark.django_db
def test_institutional_officer_is_neutral_and_dpo_adds_only_privacy_capabilities():
    sync_policy()
    officer = make_user(
        role="INSTITUTIONAL_OFFICER",
        email="dpo.officer@example.edu",
    )
    assert effective_capabilities(officer) == frozenset()

    UserDesignation.objects.create(
        user=officer,
        designation=Designation.objects.get(code="DPO"),
    )
    assert effective_capabilities(officer) == frozenset(
        {
            "privacy_governance.view",
            "privacy_governance.manage",
        }
    )
    assert not officer.has_capability("accounts.manage")
    assert not officer.has_capability("institutional_designations.manage")
    assert not officer.has_capability("organization.manage")
    assert not officer.has_capability("reports.view")
    assert not officer.has_capability("student_support.view")


def test_designation_role_compatibility_fails_closed_for_unknown_codes():
    assert designation_role_compatible(
        designation_code="DPO",
        role_code="INSTITUTIONAL_OFFICER",
    )
    assert not designation_role_compatible(
        designation_code="DPO",
        role_code="IT_ADMIN",
    )
    assert not designation_role_compatible(
        designation_code="UNKNOWN_DESIGNATION",
        role_code="INSTITUTIONAL_OFFICER",
    )
    assert not designation_role_compatible(
        designation_code="DPO",
        role_code="UNKNOWN_ROLE",
    )
