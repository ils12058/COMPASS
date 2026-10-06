from __future__ import annotations

import pytest
from django.core.management import call_command

from compass.accounts.models import Role, User
from compass.audit.actions import ORGANIZATION_CATALOG_SYNCED
from compass.audit.models import AuditActorType, AuditEvent
from compass.institutional_forms.models import FormRevision, FormRevisionStatus
from compass.inventory.models import StudentInventory
from compass.organization.bootstrap import (
    CanonicalOrganizationSyncError,
    sync_organization_catalog,
)
from compass.organization.canonical import (
    CANONICAL_CAMPUSES,
    CANONICAL_COLLEGE_IDENTITIES,
    CANONICAL_PROGRAM_IDENTITIES,
)
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    Program,
    StudentAffiliation,
)
from tests.inventory_encryption_helpers import create_inventory_row


def _sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def _student(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password="test-password",
        role=Role.objects.get(code="STUDENT"),
        first_name="Test",
        last_name="Student",
    )


def test_canonical_registry_pins_current_ucn_catalog_and_program_major_boundary():
    assert len(CANONICAL_CAMPUSES) == 6
    assert len(CANONICAL_COLLEGE_IDENTITIES) == 10
    assert len(CANONICAL_PROGRAM_IDENTITIES) == 38

    campus_by_code = {campus.code: campus for campus in CANONICAL_CAMPUSES}
    assert campus_by_code["ABANO"].name == "Abaño Campus"
    assert "SANTA_ELENA" not in campus_by_code

    main = campus_by_code["MAIN"]
    main_colleges = {college.code: college for college in main.colleges}
    assert main_colleges["GS"].name == "Graduate School"
    assert main_colleges["CCMS"].name == "College of Computing and Multimedia Studies"

    mercedes = campus_by_code["MERCEDES"]
    cfast = mercedes.colleges[0]
    assert cfast.code == "CFAST"
    assert cfast.name == "College of Fisheries, Aquatic Sciences, and Technology"

    entienza = campus_by_code["ENTIENZA"]
    assert entienza.name == "Ret. Judge Antonio C. Entienza Campus"
    assert len(entienza.colleges) == 1
    assert entienza.colleges[0].code == "ENTIENZA"
    assert entienza.colleges[0].name == entienza.name

    assert ("ABANO", "COED", "BSED") in CANONICAL_PROGRAM_IDENTITIES
    assert ("ENTIENZA", "ENTIENZA", "BSED") in CANONICAL_PROGRAM_IDENTITIES

    program_names = [
        program.name
        for campus in CANONICAL_CAMPUSES
        for college in campus.colleges
        for program in college.programs
    ]
    assert "Bachelor of Science in Business Administration" in program_names
    assert not any("Marketing Management" in name for name in program_names)
    assert not any("Crop Science" in name for name in program_names)


@pytest.mark.django_db
def test_sync_creates_exact_catalog_preserves_ids_and_is_idempotent():
    first = sync_organization_catalog()

    assert first.campuses_created == 6
    assert first.colleges_created == 10
    assert first.programs_created == 38
    assert Campus.objects.count() == 6
    assert College.objects.count() == 10
    assert Program.objects.count() == 38

    main_id = Campus.objects.get(code="MAIN").pk
    ccms_id = College.objects.get(campus__code="MAIN", code="CCMS").pk
    bsis_id = Program.objects.get(
        college__campus__code="MAIN",
        college__code="CCMS",
        code="BSIS",
    ).pk

    audit = AuditEvent.objects.get(action=ORGANIZATION_CATALOG_SYNCED)
    assert audit.actor_type == AuditActorType.SYSTEM
    assert audit.metadata["campuses_created"] == 6
    assert audit.metadata["colleges_created"] == 10
    assert audit.metadata["programs_created"] == 38

    second = sync_organization_catalog()
    assert not second.changed
    assert Campus.objects.get(code="MAIN").pk == main_id
    assert College.objects.get(campus__code="MAIN", code="CCMS").pk == ccms_id
    assert (
        Program.objects.get(
            college__campus__code="MAIN",
            college__code="CCMS",
            code="BSIS",
        ).pk
        == bsis_id
    )
    assert AuditEvent.objects.filter(action=ORGANIZATION_CATALOG_SYNCED).count() == 1


@pytest.mark.django_db
def test_sync_repairs_canonical_name_and_active_state_without_replacing_uuid():
    sync_organization_catalog()
    campus = Campus.objects.get(code="ABANO")
    college = College.objects.get(campus=campus, code="COED")
    program = Program.objects.get(college=college, code="BSED")
    ids = (campus.pk, college.pk, program.pk)

    Campus.objects.filter(pk=campus.pk).update(name="Abano Drift", is_active=False)
    College.objects.filter(pk=college.pk).update(name="Education Drift", is_active=False)
    Program.objects.filter(pk=program.pk).update(name="BSED Drift", is_active=False)

    result = sync_organization_catalog()
    assert result.campuses_updated == 1
    assert result.colleges_updated == 1
    assert result.programs_updated == 1

    campus.refresh_from_db()
    college.refresh_from_db()
    program.refresh_from_db()
    assert (campus.pk, college.pk, program.pk) == ids
    assert campus.name == "Abaño Campus"
    assert campus.is_active
    assert college.name == "College of Education"
    assert college.is_active
    assert program.name == "Bachelor of Secondary Education"
    assert program.is_active


@pytest.mark.django_db
def test_sync_deactivates_legacy_program_but_preserves_inventory_foreign_key():
    _sync_policy()
    call_command("sync_institutional_forms", verbosity=0)
    sync_organization_catalog()

    ccms = College.objects.get(campus__code="MAIN", code="CCMS")
    legacy = Program.objects.create(
        college=ccms,
        code="LEGACY",
        name="Historical Local Program",
    )
    academic_year = AcademicYear.objects.create(label="2025-2026", is_current=True)
    revision = FormRevision.objects.get(
        family__key="individual_inventory",
        status=FormRevisionStatus.ACTIVE,
    )
    inventory = create_inventory_row(
        StudentInventory,
        student=_student("legacy-program@example.edu"),
        academic_year=academic_year,
        form_revision=revision,
        program=legacy,
    )

    result = sync_organization_catalog()
    legacy.refresh_from_db()
    inventory.refresh_from_db()

    assert result.programs_deactivated == 1
    assert not legacy.is_active
    assert inventory.program_id == legacy.pk
    assert Program.objects.filter(pk=legacy.pk).exists()


@pytest.mark.django_db
def test_sync_fails_instead_of_breaking_live_noncanonical_college_relationships():
    _sync_policy()
    sync_organization_catalog()
    main = Campus.objects.get(code="MAIN")
    legacy = College.objects.create(
        campus=main,
        code="LEGACY",
        name="Legacy Routing Unit",
    )
    student = _student("legacy-affiliation@example.edu")
    StudentAffiliation.objects.create(student=student, college=legacy)

    with pytest.raises(CanonicalOrganizationSyncError, match="LEGACY"):
        sync_organization_catalog()

    legacy.refresh_from_db()
    assert legacy.is_active
    assert StudentAffiliation.objects.filter(student=student, college=legacy).exists()


@pytest.mark.django_db
def test_sync_never_merges_by_display_name_alone():
    legacy = Campus.objects.create(code="OLDMAIN", name="Main Campus")

    sync_organization_catalog()

    canonical = Campus.objects.get(code="MAIN")
    legacy.refresh_from_db()
    assert canonical.pk != legacy.pk
    assert canonical.name == legacy.name
    assert not legacy.is_active
