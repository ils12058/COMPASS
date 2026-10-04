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
from compass.institutional_forms.bootstrap import sync_institutional_forms
from compass.institutional_forms.canonical import CANONICAL_FORM_FAMILIES
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import (
    UnsupportedInstitutionalFormRevision,
    is_supported_form_revision,
    require_active_supported_form_revision,
)
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    InventoryFormRevisionNotConfigured,
    _active_inventory_revision,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import AcademicYear
from compass.referrals.services import ReferralConfigurationConflict, _active_referral_revision
from compass.routine_interviews.services import (
    RoutineInterviewFormRevisionUnsupported,
    _optional_form_revision,
)


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


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
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
def test_canonical_registry_preserves_exact_confirmed_controlled_form_identities():
    expected = {
        "individual_inventory": (
            "Individual Inventory",
            frozenset({1}),
            (("CNSC-OP-GCO-01F5", "0", 1, True),),
        ),
        "routine_interview": ("Routine Interview Form", frozenset({1}), ()),
        "referral_slip": (
            "Referral Slip",
            frozenset({1}),
            (("CNSC-OP-GTA-01F9", "1", 1, True),),
        ),
        "call_slip": (
            "Interview Permit / Call Slip",
            frozenset({1}),
            (("CNSC-OP-GTA-01F8", "0", 1, True),),
        ),
        "good_moral_current_student": (
            "Good Moral Character — Current Student",
            frozenset({1}),
            (("CNSC-OP-GCO-01F4", "0", 1, True),),
        ),
        "good_moral_graduate": (
            "Good Moral Character — Graduate",
            frozenset({1}),
            (("CNSC-OP-GCO-01F6", "0", 1, True),),
        ),
        "customer_feedback": (
            "Customer Feedback Form",
            frozenset({1}),
            (("CNSC-OP-GTA-01F14", "0", 1, True),),
        ),
    }
    actual = {
        family.key: (
            family.title,
            family.supported_schema_versions,
            tuple(
                (
                    revision.official_code,
                    revision.official_revision,
                    revision.internal_schema_version,
                    revision.active,
                )
                for revision in family.revisions
            ),
        )
        for family in CANONICAL_FORM_FAMILIES
    }
    assert actual == expected

    assert FormFamily.objects.count() == 7
    routine_family = FormFamily.objects.get(key="routine_interview")
    assert routine_family.title == "Routine Interview Form"
    assert not FormRevision.objects.filter(family=routine_family).exists()


@pytest.mark.django_db
def test_exact_identity_not_schema_version_alone_controls_runtime_support():
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
        canonical = FormRevision.objects.get(family__key=family_key, status="ACTIVE")
        canonical.status = "INACTIVE"
        canonical.save(update_fields=["status", "updated_at"])
        arbitrary = FormRevision.objects.create(
            family=canonical.family,
            official_code=f"UNCONFIRMED-{family_key}",
            official_revision="99",
            internal_schema_version=1,
            status="ACTIVE",
        )

        assert not is_supported_form_revision(arbitrary)
        with pytest.raises(UnsupportedInstitutionalFormRevision):
            require_active_supported_form_revision(family_key)
        with pytest.raises(expected_error):
            resolver()

        arbitrary.delete()
        canonical.status = "ACTIVE"
        canonical.save(update_fields=["status", "updated_at"])

    routine_family = FormFamily.objects.get(key="routine_interview")
    arbitrary_routine = FormRevision.objects.create(
        family=routine_family,
        official_code="UNCONFIRMED-ROUTINE",
        official_revision="1",
        internal_schema_version=1,
        status="ACTIVE",
    )
    assert not is_supported_form_revision(arbitrary_routine)
    with pytest.raises(RoutineInterviewFormRevisionUnsupported):
        _optional_form_revision()


@pytest.mark.django_db
def test_canonical_sync_repairs_drift_preserves_ids_and_historical_references():
    sync_policy()
    inventory_family = FormFamily.objects.get(key="individual_inventory")
    inventory_revision = FormRevision.objects.get(
        family=inventory_family,
        official_code="CNSC-OP-GCO-01F5",
        official_revision="0",
    )
    family_id = inventory_family.pk
    revision_id = inventory_revision.pk

    inventory_family.title = "Locally edited title"
    inventory_family.save(update_fields=["title", "updated_at"])
    inventory_revision.internal_schema_version = 999
    inventory_revision.status = "INACTIVE"
    inventory_revision.save(update_fields=["internal_schema_version", "status", "updated_at"])
    legacy = FormRevision.objects.create(
        family=inventory_family,
        official_code="LEGACY-LOCAL-FORM",
        official_revision="7",
        internal_schema_version=1,
        status="ACTIVE",
    )

    student = make_user("historical-form@example.edu", "STUDENT")
    year = AcademicYear.objects.create(label="2026-2027", is_current=False)
    historical_inventory = StudentInventory.objects.create(
        student=student,
        academic_year=year,
        form_revision=legacy,
    )

    routine_family = FormFamily.objects.get(key="routine_interview")
    routine_family.delete()

    referral_revision = FormRevision.objects.get(
        family__key="referral_slip",
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
    )
    referral_revision.delete()

    first = sync_institutional_forms()
    assert first.changed

    inventory_family.refresh_from_db()
    inventory_revision.refresh_from_db()
    legacy.refresh_from_db()
    historical_inventory.refresh_from_db()

    assert inventory_family.pk == family_id
    assert inventory_family.title == "Individual Inventory"
    assert inventory_revision.pk == revision_id
    assert inventory_revision.internal_schema_version == 1
    assert inventory_revision.status == "ACTIVE"
    assert legacy.status == "INACTIVE"
    assert historical_inventory.form_revision_id == legacy.pk
    assert FormRevision.objects.filter(pk=legacy.pk).exists()

    restored_routine = FormFamily.objects.get(key="routine_interview")
    assert not FormRevision.objects.filter(family=restored_routine).exists()
    restored_referral = FormRevision.objects.get(
        family__key="referral_slip",
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
    )
    assert restored_referral.internal_schema_version == 1
    assert restored_referral.status == "ACTIVE"

    for family in FormFamily.objects.filter(
        key__in=[definition.key for definition in CANONICAL_FORM_FAMILIES]
    ):
        assert FormRevision.objects.filter(family=family, status="ACTIVE").count() <= 1

    assert AuditEvent.objects.filter(action="institutional_forms.synced").count() == 1
    event = AuditEvent.objects.get(action="institutional_forms.synced")
    assert event.actor_type == "SYSTEM"
    assert set(event.metadata) == {
        "families_created",
        "families_updated",
        "revisions_created",
        "revisions_updated",
        "revisions_activated",
        "revisions_deactivated",
    }

    second = sync_institutional_forms()
    assert not second.changed
    assert AuditEvent.objects.filter(action="institutional_forms.synced").count() == 1


@pytest.mark.django_db
def test_configuration_capabilities_keep_forms_read_only():
    sync_policy()
    head = make_head()
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")

    assert head.has_capability("academic_years.view")
    assert head.has_capability("academic_years.manage")
    assert head.has_capability("institutional_forms.view")
    assert not head.has_capability("institutional_forms.manage")
    assert counselor.has_capability("academic_years.view")
    assert not counselor.has_capability("academic_years.manage")
    assert counselor.has_capability("institutional_forms.view")
    assert not counselor.has_capability("institutional_forms.manage")
    assert not admin.has_capability("academic_years.manage")
    assert not admin.has_capability("institutional_forms.manage")
    assert not student.has_capability("institutional_forms.view")


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
def test_institutional_forms_api_is_read_only_and_projects_exact_support():
    sync_policy()
    counselor = make_user("forms-reader@example.edu", "COUNSELOR")
    student = make_user("forms-denied@example.edu", "STUDENT")
    family = FormFamily.objects.get(key="individual_inventory")
    historical = FormRevision.objects.create(
        family=family,
        official_code="LEGACY-ONLY",
        official_revision="2",
        internal_schema_version=1,
        status="INACTIVE",
    )

    client = auth_client(counselor, recent_mfa=True)
    families = client.get("/api/v1/institutional-forms")
    assert families.status_code == 200
    assert [item["key"] for item in families.json()["items"]] == [
        "call_slip",
        "customer_feedback",
        "good_moral_current_student",
        "good_moral_graduate",
        "individual_inventory",
        "referral_slip",
        "routine_interview",
    ]
    by_key = {item["key"]: item for item in families.json()["items"]}
    assert by_key["routine_interview"]["revision_required"] is False
    assert by_key["routine_interview"]["configuration_state"] == "REVISION_NOT_REQUIRED"
    assert by_key["individual_inventory"]["revision_required"] is True
    assert by_key["individual_inventory"]["configuration_state"] == "READY"

    revisions = client.get("/api/v1/institutional-forms/individual_inventory/revisions")
    assert revisions.status_code == 200
    by_id = {item["id"]: item for item in revisions.json()["items"]}
    canonical = FormRevision.objects.get(
        family=family,
        official_code="CNSC-OP-GCO-01F5",
        official_revision="0",
    )
    assert by_id[str(canonical.pk)]["supported"] is True
    assert by_id[str(historical.pk)]["supported"] is False
    assert revisions.json()["items"][0]["id"] == str(canonical.pk)

    canonical.status = "INACTIVE"
    canonical.save(update_fields=["status", "updated_at"])
    missing = client.get("/api/v1/institutional-forms")
    missing_state = next(
        row for row in missing.json()["items"] if row["key"] == "individual_inventory"
    )["configuration_state"]
    assert missing_state == "MISSING_REQUIRED_REVISION"
    historical.status = "ACTIVE"
    historical.save(update_fields=["status", "updated_at"])
    drifted = client.get("/api/v1/institutional-forms")
    drifted_state = next(
        row for row in drifted.json()["items"] if row["key"] == "individual_inventory"
    )["configuration_state"]
    assert drifted_state == "ACTIVE_UNSUPPORTED"

    headers = csrf(client)
    removed_register = client.post(
        "/api/v1/institutional-forms/individual_inventory/revisions",
        data=json.dumps(
            {
                "official_code": "UNCONFIRMED",
                "official_revision": "9",
                "internal_schema_version": 1,
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert removed_register.status_code == 405
    removed_activate = client.post(
        f"/api/v1/institutional-forms/revisions/{canonical.pk}/activate",
        data=json.dumps({}),
        content_type="application/json",
        **headers,
    )
    removed_deactivate = client.post(
        f"/api/v1/institutional-forms/revisions/{canonical.pk}/deactivate",
        data=json.dumps({}),
        content_type="application/json",
        **headers,
    )
    assert removed_activate.status_code == 404
    assert removed_deactivate.status_code == 404

    denied = auth_client(student)
    assert denied.get("/api/v1/institutional-forms").status_code == 403


@pytest.mark.django_db
def test_academic_year_mutations_still_require_head_capability_and_recent_mfa():
    sync_policy()
    head = make_head()
    admin = make_user("admin-academic@example.edu", "IT_ADMIN")

    stale = auth_client(head, recent_mfa=False)
    denied_mfa = stale.post(
        "/api/v1/academic-years",
        data=json.dumps({"label": "2026-2027"}),
        content_type="application/json",
        **csrf(stale),
    )
    assert denied_mfa.status_code == 403
    assert denied_mfa.json()["error"]["code"] == "mfa_setup_required"

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
