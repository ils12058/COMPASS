from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.call_slips.services import (
    CallSlipConfigurationConflict,
    _active_call_slip_revision,
)
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import (
    SUPPORTED_SCHEMA_VERSIONS,
    InstitutionalFormConflict,
    activate_form_revision,
    deactivate_form_revision,
    register_form_revision,
)
from compass.inventory.services import (
    InventoryFormRevisionNotConfigured,
    _active_inventory_revision,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import AcademicYear
from compass.referrals.services import ReferralConfigurationConflict, _active_referral_revision
from compass.routine_interviews.services import _optional_form_revision


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


def make_head() -> User:
    user = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User, *, recent_mfa: bool) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


@pytest.mark.django_db
def test_initial_inventory_revision_preserves_confirmed_qms_identity():
    family = FormFamily.objects.get(key="individual_inventory")
    revision = FormRevision.objects.get(family=family, internal_schema_version=1)

    assert family.title == "Individual Inventory"
    assert revision.official_code == "CNSC-OP-GCO-01F5"
    assert revision.official_revision == "0"
    assert revision.status == "ACTIVE"
    assert FormFamily.objects.count() == 6

    routine_family = FormFamily.objects.get(key="routine_interview")
    assert routine_family.title == "Routine Interview Form"
    assert not FormRevision.objects.filter(family=routine_family).exists()
    assert SUPPORTED_SCHEMA_VERSIONS["routine_interview"] == frozenset({1})

    referral_family = FormFamily.objects.get(key="referral_slip")
    referral_revision = FormRevision.objects.get(
        family=referral_family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
    )
    assert referral_family.title == "Referral Slip"
    assert referral_revision.internal_schema_version == 1
    assert referral_revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["referral_slip"] == frozenset({1})

    call_slip_family = FormFamily.objects.get(key="call_slip")
    call_slip_revision = FormRevision.objects.get(
        family=call_slip_family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="0",
    )
    assert call_slip_family.title == "Interview Permit / Call Slip"
    assert call_slip_revision.internal_schema_version == 1
    assert call_slip_revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["call_slip"] == frozenset({1})

    current_good_moral = FormFamily.objects.get(key="good_moral_current_student")
    current_revision = FormRevision.objects.get(
        family=current_good_moral,
        official_code="CNSC-OP-GCO-01F4",
        official_revision="0",
    )
    assert current_good_moral.title == "Good Moral Character — Current Student"
    assert current_revision.internal_schema_version == 1
    assert current_revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["good_moral_current_student"] == frozenset({1})

    graduate_good_moral = FormFamily.objects.get(key="good_moral_graduate")
    graduate_revision = FormRevision.objects.get(
        family=graduate_good_moral,
        official_code="CNSC-OP-GCO-01F6",
        official_revision="0",
    )
    assert graduate_good_moral.title == "Good Moral Character — Graduate"
    assert graduate_revision.internal_schema_version == 1
    assert graduate_revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["good_moral_graduate"] == frozenset({1})


@pytest.mark.django_db
def test_required_form_consumers_reject_unsupported_active_revision_and_routine_is_optional():
    assert _optional_form_revision() is None

    cases = (
        (
            "individual_inventory",
            _active_inventory_revision,
            InventoryFormRevisionNotConfigured,
        ),
        ("referral_slip", _active_referral_revision, ReferralConfigurationConflict),
        ("call_slip", _active_call_slip_revision, CallSlipConfigurationConflict),
    )
    for family_key, resolver, expected_error in cases:
        revision = FormRevision.objects.get(family__key=family_key, status="ACTIVE")
        FormRevision.objects.filter(pk=revision.pk).update(internal_schema_version=999)
        with pytest.raises(expected_error):
            resolver()
        FormRevision.objects.filter(pk=revision.pk).update(internal_schema_version=1)


@pytest.mark.django_db
def test_configuration_capabilities_keep_head_business_authority_explicit():
    sync_policy()
    head = make_head()
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")

    assert head.has_capability("academic_years.view")
    assert head.has_capability("academic_years.manage")
    assert head.has_capability("institutional_forms.view")
    assert head.has_capability("institutional_forms.manage")
    assert not counselor.has_capability("academic_years.view")
    assert not counselor.has_capability("academic_years.manage")
    assert not counselor.has_capability("institutional_forms.view")
    assert not counselor.has_capability("institutional_forms.manage")
    assert not admin.has_capability("academic_years.manage")
    assert not admin.has_capability("institutional_forms.manage")
    assert not student.has_capability("academic_years.manage")


@pytest.mark.django_db
def test_academic_year_switch_is_explicit_transactional_and_audited():
    sync_policy()
    head = make_head()
    first = create_academic_year(label="2026-2027", context=context(head))
    second = create_academic_year(label="2027-2028", context=context(head))

    set_current_academic_year(academic_year_id=first.pk, context=context(head))
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_current
    assert not second.is_current

    set_current_academic_year(academic_year_id=second.pk, context=context(head))
    first.refresh_from_db()
    second.refresh_from_db()
    assert not first.is_current
    assert second.is_current
    assert AcademicYear.objects.filter(is_current=True).count() == 1

    event = AuditEvent.objects.filter(action="academic_year.current_changed").latest("occurred_at")
    assert event.metadata == {
        "old_label": "2026-2027",
        "new_label": "2027-2028",
    }


@pytest.mark.django_db
def test_form_revision_registration_is_append_only_and_activation_checks_code_support():
    sync_policy()
    head = make_head()
    family = FormFamily.objects.get(key="individual_inventory")
    old = FormRevision.objects.get(family=family, internal_schema_version=1)

    unsupported = register_form_revision(
        family_key=family.key,
        official_code="CNSC-OP-GCO-01F5",
        official_revision="1",
        internal_schema_version=2,
        context=context(head),
    )
    assert unsupported.status == "INACTIVE"
    with pytest.raises(InstitutionalFormConflict, match="does not support"):
        activate_form_revision(revision_id=unsupported.pk, context=context(head))

    deactivate_form_revision(revision_id=old.pk, context=context(head))
    old.refresh_from_db()
    unsupported.refresh_from_db()
    assert old.status == "INACTIVE"
    assert unsupported.status == "INACTIVE"
    assert AuditEvent.objects.filter(action="institutional_form.revision_registered").count() == 1


@pytest.mark.django_db
def test_operational_configuration_mutations_require_head_capability_and_recent_mfa():
    sync_policy()
    head = make_head()
    admin = make_user("admin@example.edu", "IT_ADMIN")

    stale = auth_client(head, recent_mfa=False)
    denied_mfa = stale.post(
        "/api/v1/academic-years",
        data=json.dumps({"label": "2026-2027"}),
        content_type="application/json",
        **csrf(stale),
    )
    assert denied_mfa.status_code == 403
    assert denied_mfa.json()["error"]["code"] == "recent_mfa_required"

    admin_client = auth_client(admin, recent_mfa=True)
    denied_role = admin_client.post(
        "/api/v1/academic-years",
        data=json.dumps({"label": "2026-2027"}),
        content_type="application/json",
        **csrf(admin_client),
    )
    assert denied_role.status_code == 403

    client = auth_client(head, recent_mfa=True)
    created = client.post(
        "/api/v1/academic-years",
        data=json.dumps({"label": "2026-2027"}),
        content_type="application/json",
        **csrf(client),
    )
    assert created.status_code == 201
    year_id = created.json()["id"]
    current = client.post(
        f"/api/v1/academic-years/{year_id}/set-current",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert current.status_code == 200
    assert current.json()["is_current"] is True

    listed = client.get("/api/v1/institutional-forms")
    assert listed.status_code == 200
    assert [item["key"] for item in listed.json()["items"]] == [
        "call_slip",
        "good_moral_current_student",
        "good_moral_graduate",
        "individual_inventory",
        "referral_slip",
        "routine_interview",
    ]
