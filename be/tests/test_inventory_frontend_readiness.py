from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.integrations.psgc import (
    PSGCConfigurationError,
    PSGCReference,
    PSGCReferenceNotFound,
)
from compass.inventory import services as inventory_services
from compass.inventory.services import (
    InvalidInventoryInput,
    InventoryStatus,
    ensure_current_inventory,
    get_current_inventory_status,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import Campus, College, Program
from tests.inventory_test_helpers import (
    ensure_inventory_form_revision,
    minimum_normalized_inventory_values,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Inventory",
        last_name="Student",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def configure_year(actor: User):
    year = create_academic_year(label="2026-2027", context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def configure_program() -> Program:
    campus = Campus.objects.create(code="PSGC-CAMP", name="PSGC Campus")
    college = College.objects.create(campus=campus, code="PSGC-COL", name="PSGC College")
    return Program.objects.create(college=college, code="PSGC-PROG", name="PSGC Program")


class CanonicalPSGC:
    def require_region(self, code: str):
        names = {
            "0500000000": "Bicol Region",
            "1300000000": "National Capital Region",
        }
        if code not in names:
            raise PSGCReferenceNotFound("The selected PSGC Region was not found.")
        return PSGCReference(code, names[code])

    def require_province(self, *, region_code: str, province_code: str):
        if (region_code, province_code) != ("0500000000", "0501600000"):
            raise PSGCReferenceNotFound(
                "The selected PSGC Province does not belong to the selected Region."
            )
        return PSGCReference(province_code, "Camarines Norte")

    def require_city_municipality(
        self,
        *,
        region_code: str,
        province_code: str | None,
        city_municipality_code: str,
    ):
        valid = {
            ("0500000000", "0501600000", "0501607000"): "Daet",
            ("1300000000", None, "1380600000"): "City of Manila",
        }
        key = (region_code, province_code, city_municipality_code)
        if key not in valid:
            raise PSGCReferenceNotFound(
                "The selected PSGC City/Municipality does not belong to the selected hierarchy."
            )
        return PSGCReference(city_municipality_code, valid[key])

    def require_barangay(self, *, city_municipality_code: str, barangay_code: str):
        if (city_municipality_code, barangay_code) != ("0501607000", "0501607001"):
            raise PSGCReferenceNotFound(
                "The selected PSGC Barangay does not belong to the selected City/Municipality."
            )
        return PSGCReference(barangay_code, "Barangay I")


@pytest.mark.django_db
def test_psgc_outage_does_not_block_inventory_draft_save_but_blocks_submission(monkeypatch):
    sync_policy()
    admin = make_user("psgc-draft-admin@example.edu", "IT_ADMIN")
    student = make_user("psgc-draft-student@example.edu", "STUDENT")
    configure_year(admin)
    program = configure_program()
    ensure_current_inventory(student=student, context=context(student))

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["nickname"] = "Saved while PSGC unavailable"
    values["geographic_locations"] = [
        {
            "kind": "CURRENT",
            "not_specified": False,
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "Unverified Region",
            "province_psgc_code": "0501600000",
            "province_name_snapshot": "Unverified Province",
            "city_municipality_psgc_code": "0501607000",
            "city_municipality_name_snapshot": "Unverified Locality",
            "barangay_psgc_code": "",
            "barangay_name_snapshot": "",
        }
    ]

    monkeypatch.setattr(
        inventory_services.PSGCClient,
        "from_settings",
        classmethod(
            lambda cls: (_ for _ in ()).throw(
                PSGCConfigurationError("test configuration unavailable")
            )
        ),
    )

    saved = replace_current_inventory(student=student, values=values)
    assert saved.nickname == "Saved while PSGC unavailable"
    assert saved.submitted_at is None
    assert saved.geographic_locations.get(kind="CURRENT").region_name_snapshot == (
        "Unverified Region"
    )

    client = auth_client(student)
    response = client.post(
        "/api/v1/inventory/me/current/submit",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "psgc_reference_unavailable"

    saved.refresh_from_db()
    assert saved.submitted_at is None
    assert get_current_inventory_status(student).status == InventoryStatus.DRAFT
    assert saved.nickname == "Saved while PSGC unavailable"
    assert saved.geographic_locations.get(kind="CURRENT").region_name_snapshot == (
        "Unverified Region"
    )


@pytest.mark.django_db
def test_inventory_submission_validates_hierarchy_and_canonicalizes_psgc_names(monkeypatch):
    sync_policy()
    admin = make_user("psgc-valid-admin@example.edu", "IT_ADMIN")
    student = make_user("psgc-valid-student@example.edu", "STUDENT")
    configure_year(admin)
    program = configure_program()
    ensure_current_inventory(student=student, context=context(student))

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["geographic_locations"] = [
        {
            "kind": "CURRENT",
            "not_specified": False,
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "Tampered Region",
            "province_psgc_code": "0501600000",
            "province_name_snapshot": "Tampered Province",
            "city_municipality_psgc_code": "0501607000",
            "city_municipality_name_snapshot": "Tampered Municipality",
            "barangay_psgc_code": "0501607001",
            "barangay_name_snapshot": "Tampered Barangay",
        },
        {
            "kind": "PERMANENT",
            "not_specified": False,
            "region_psgc_code": "1300000000",
            "region_name_snapshot": "Wrong NCR",
            "province_psgc_code": "",
            "province_name_snapshot": "",
            "city_municipality_psgc_code": "1380600000",
            "city_municipality_name_snapshot": "Wrong Manila",
            "barangay_psgc_code": "",
            "barangay_name_snapshot": "",
        },
    ]
    replace_current_inventory(student=student, values=values)

    fake = CanonicalPSGC()
    monkeypatch.setattr(
        inventory_services.PSGCClient,
        "from_settings",
        classmethod(lambda cls: fake),
    )

    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None

    current = submitted.geographic_locations.get(kind="CURRENT")
    assert current.region_name_snapshot == "Bicol Region"
    assert current.province_name_snapshot == "Camarines Norte"
    assert current.city_municipality_name_snapshot == "Daet"
    assert current.barangay_name_snapshot == "Barangay I"

    permanent = submitted.geographic_locations.get(kind="PERMANENT")
    assert permanent.region_name_snapshot == "National Capital Region"
    assert permanent.province_psgc_code == ""
    assert permanent.province_name_snapshot == ""
    assert permanent.city_municipality_name_snapshot == "City of Manila"


@pytest.mark.django_db
def test_inventory_submission_rejects_psgc_hierarchy_mismatch_and_stays_draft(monkeypatch):
    sync_policy()
    admin = make_user("psgc-mismatch-admin@example.edu", "IT_ADMIN")
    student = make_user("psgc-mismatch-student@example.edu", "STUDENT")
    configure_year(admin)
    program = configure_program()
    item = ensure_current_inventory(student=student, context=context(student))

    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["geographic_locations"] = [
        {
            "kind": "CURRENT",
            "not_specified": False,
            "region_psgc_code": "0500000000",
            "region_name_snapshot": "Bicol Region",
            "province_psgc_code": "0501600000",
            "province_name_snapshot": "Camarines Norte",
            "city_municipality_psgc_code": "1380600000",
            "city_municipality_name_snapshot": "City of Manila",
            "barangay_psgc_code": "",
            "barangay_name_snapshot": "",
        }
    ]
    replace_current_inventory(student=student, values=values)

    fake = CanonicalPSGC()
    monkeypatch.setattr(
        inventory_services.PSGCClient,
        "from_settings",
        classmethod(lambda cls: fake),
    )

    with pytest.raises(InvalidInventoryInput, match="does not belong"):
        submit_current_inventory(student=student, context=context(student))

    item.refresh_from_db()
    assert item.submitted_at is None
    assert get_current_inventory_status(student).status == InventoryStatus.DRAFT


@pytest.mark.django_db
def test_not_specified_geography_never_requires_psgc_lookup(monkeypatch):
    sync_policy()
    admin = make_user("psgc-skip-admin@example.edu", "IT_ADMIN")
    student = make_user("psgc-skip-student@example.edu", "STUDENT")
    configure_year(admin)
    program = configure_program()
    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )

    def fail_if_called(cls):
        raise AssertionError("PSGC must not be constructed for not_specified geography")

    monkeypatch.setattr(
        inventory_services.PSGCClient,
        "from_settings",
        classmethod(fail_if_called),
    )

    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db(transaction=True)
def test_psgc_verification_runs_before_inventory_locks_are_taken(monkeypatch):
    import threading

    from django.db import close_old_connections, connection

    sync_policy()
    # Transactional tests run after earlier flushes removed migration-seeded rows.
    ensure_inventory_form_revision()
    admin = make_user("psgc-lock-admin@example.edu", "IT_ADMIN")
    student = make_user("psgc-lock-student@example.edu", "STUDENT")
    configure_year(admin)
    program = configure_program()
    ensure_current_inventory(student=student, context=context(student))
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["geographic_locations"] = [
        {
            "kind": "CURRENT",
            "not_specified": False,
            "region_psgc_code": "1300000000",
            "region_name_snapshot": "Draft NCR",
            "province_psgc_code": "",
            "province_name_snapshot": "",
            "city_municipality_psgc_code": "1380600000",
            "city_municipality_name_snapshot": "Draft Manila",
            "barangay_psgc_code": "",
            "barangay_name_snapshot": "",
        }
    ]
    replace_current_inventory(student=student, values=values)
    observed: list[bool] = []

    class ProbingPSGC(CanonicalPSGC):
        def require_region(self, code: str):
            def probe():
                close_old_connections()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("BEGIN")
                        try:
                            cursor.execute(
                                "SELECT id FROM accounts_user WHERE id = %s FOR UPDATE NOWAIT",
                                [student.pk],
                            )
                            cursor.execute(
                                "SELECT id FROM organization_program WHERE id = %s "
                                "FOR UPDATE NOWAIT",
                                [program.pk],
                            )
                            observed.append(True)
                        except Exception:
                            observed.append(False)
                        finally:
                            cursor.execute("ROLLBACK")
                finally:
                    # Thread-local connections persist under CONN_MAX_AGE; close explicitly.
                    connection.close()

            worker = threading.Thread(target=probe)
            worker.start()
            worker.join(timeout=10)
            return super().require_region(code)

    monkeypatch.setattr(
        inventory_services.PSGCClient,
        "from_settings",
        classmethod(lambda cls: ProbingPSGC()),
    )

    submitted = submit_current_inventory(student=student, context=context(student))

    assert submitted.submitted_at is not None
    assert observed == [True]
    assert (
        submitted.geographic_locations.get(kind="CURRENT").city_municipality_name_snapshot
        == "City of Manila"
    )


@pytest.mark.django_db
def test_ensure_recovers_from_a_concurrent_insert_without_an_aborted_transaction(monkeypatch):
    from compass.inventory.models import StudentInventory

    sync_policy()
    admin = make_user("ensure-race-admin@example.edu", "IT_ADMIN")
    student = make_user("ensure-race-student@example.edu", "STUDENT")
    year = configure_year(admin)
    original_revision = inventory_services._active_inventory_revision
    inserted: list[object] = []

    def revision_after_concurrent_insert():
        revision = original_revision()
        # Simulate another request committing the same annual Inventory first.
        inserted.append(
            StudentInventory.objects.create(
                student=student,
                academic_year=year,
                form_revision=revision,
            )
        )
        return revision

    monkeypatch.setattr(
        inventory_services, "_active_inventory_revision", revision_after_concurrent_insert
    )

    item = ensure_current_inventory(student=student, context=context(student))

    assert item.pk == inserted[0].pk
    assert StudentInventory.objects.filter(student=student, academic_year=year).count() == 1
    assert item.support_profile is not None
