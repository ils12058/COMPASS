from __future__ import annotations

import pytest
from django.core.management import call_command

from compass.accounts.models import Role, User
from compass.audit.actions import ORGANIZATION_CATALOG_INITIALIZED
from compass.audit.models import AuditEvent
from compass.organization.bootstrap import (
    CanonicalOrganizationSyncError,
    sync_organization_catalog,
)
from compass.organization.canonical import (
    CANONICAL_CAMPUSES,
    CANONICAL_COLLEGE_IDENTITIES,
    CANONICAL_PROGRAM_IDENTITIES,
    AcademicClassification,
    YearLevelPolicyStatus,
)
from compass.organization.models import (
    Campus,
    College,
    Program,
)


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

    catalog_programs = [
        program
        for campus in CANONICAL_CAMPUSES
        for college in campus.colleges
        for program in college.programs
    ]
    assert all(program.academic_classification for program in catalog_programs)
    assert all(
        program.applicable_year_levels == (1, 2, 3, 4)
        for program in catalog_programs
        if program.academic_classification == AcademicClassification.BACHELORS
    )
    assert all(
        program.applicable_year_levels is None
        for program in catalog_programs
        if program.academic_classification
        in {AcademicClassification.MASTERS, AcademicClassification.DOCTORAL}
    )

    main_programs = {
        (college.code, program.code): program
        for college in main.colleges
        for program in college.programs
    }
    assert main_programs["CCMS", "MIT"].academic_classification == (AcademicClassification.MASTERS)
    assert main_programs["CCMS", "MIT"].year_level_policy_status == (
        YearLevelPolicyStatus.PENDING_POLICY
    )
    assert main_programs["GS", "DBA"].academic_classification == (AcademicClassification.DOCTORAL)
    assert main_programs["GS", "MBA"].academic_classification == (AcademicClassification.MASTERS)
    assert main_programs["CCMS", "BSIS"].academic_classification == (
        AcademicClassification.BACHELORS
    )
    assert main_programs["CCMS", "BSIS"].applicable_year_levels == (1, 2, 3, 4)


@pytest.mark.django_db
def test_seed_is_exact_and_repeat_never_reconciles_managed_values():
    from compass.organization.models import CatalogInitialization

    first = sync_organization_catalog()
    assert (first.campuses_created, first.colleges_created, first.programs_created) == (6, 10, 38)
    before = list(Program.objects.values_list("id", flat=True))
    Campus.objects.filter(code="ABANO").update(name="Official campus rename", is_active=False)
    College.objects.filter(code="COED").update(name="Official unit rename", is_active=False)
    Program.objects.filter(code="BSED").update(name="Official degree rename", is_active=False)
    college = College.objects.get(code="CCMS")
    additional = Program.objects.create(
        college=college,
        code="NEW",
        name="New approved degree",
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 3, 5],
    )
    call_command("sync_organization_catalog")
    call_command("initialize_organization_catalog", "--seed")
    call_command("initialize_organization_catalog", "--check")
    assert Campus.objects.get(code="ABANO").name == "Official campus rename"
    assert not College.objects.get(code="COED").is_active
    assert not Program.objects.filter(code="BSED", is_active=True).exists()
    additional.refresh_from_db()
    assert additional.is_active and additional.applicable_year_levels == [1, 3, 5]
    assert set(before) < set(Program.objects.values_list("id", flat=True))
    assert CatalogInitialization.objects.get().source == "SEEDED"
    assert AuditEvent.objects.filter(action=ORGANIZATION_CATALOG_INITIALIZED).count() == 1


@pytest.mark.django_db
def test_nonempty_catalog_requires_explicit_adoption_without_top_up():
    from compass.organization.bootstrap import initialize_organization_catalog
    from compass.organization.models import CatalogInitialization

    campus = Campus.objects.create(code="CUSTOM", name="Official", is_active=False)
    before = Campus.objects.values().get()
    with pytest.raises(CanonicalOrganizationSyncError, match="Refusing seed"):
        sync_organization_catalog()
    assert not CatalogInitialization.objects.exists()
    result = initialize_organization_catalog(action="adopt", reference="Synthetic approval")
    assert result.changed and result.receipt.source == "ADOPTED"
    assert Campus.objects.values().get() == before
    assert Campus.objects.get().pk == campus.pk
    assert not College.objects.exists() and not Program.objects.exists()
    assert not initialize_organization_catalog(action="adopt").changed
    assert not sync_organization_catalog().changed
    assert AuditEvent.objects.filter(action="organization.catalog_adopted").count() == 1


@pytest.mark.django_db
def test_empty_adoption_is_deliberate_and_receipt_is_not_a_reseed_switch():
    from compass.organization.bootstrap import initialize_organization_catalog
    from compass.organization.models import CatalogInitialization

    with pytest.raises(CanonicalOrganizationSyncError, match="allow-empty"):
        initialize_organization_catalog(action="adopt")
    initialize_organization_catalog(action="adopt", allow_empty_adoption=True)
    assert not sync_organization_catalog().changed
    assert Campus.objects.count() == 0
    receipt = CatalogInitialization.objects.get()
    for operation in (
        lambda: receipt.delete(),
        lambda: CatalogInitialization.objects.all().delete(),
        lambda: CatalogInitialization.objects.update(source="SEEDED"),
        receipt.save,
    ):
        with pytest.raises(TypeError):
            operation()


@pytest.mark.django_db
def test_failed_audit_rolls_back_seed_and_receipt(monkeypatch):
    from django.db import DatabaseError

    from compass.organization import bootstrap
    from compass.organization.models import CatalogInitialization

    def fail(**kwargs):
        raise DatabaseError("Synthetic failure")

    monkeypatch.setattr(bootstrap, "record_event", fail)
    with pytest.raises(CanonicalOrganizationSyncError, match="atomically"):
        sync_organization_catalog()
    assert not Campus.objects.exists()
    assert not CatalogInitialization.objects.exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("action", ["seed", "adopt"])
def test_concurrent_initialization_has_one_receipt_and_one_audit(action):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connections

    from compass.organization.bootstrap import initialize_organization_catalog
    from compass.organization.models import CatalogInitialization

    if action == "adopt":
        Campus.objects.create(code="OFFICIAL", name="Keep this name")
    barrier = Barrier(2)

    def initialize():
        try:
            barrier.wait(timeout=10)
            return initialize_organization_catalog(action=action).changed
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(initialize) for _ in range(2)]
        assert sorted(future.result(timeout=30) for future in futures) == [False, True]
    assert CatalogInitialization.objects.count() == 1
    assert (
        AuditEvent.objects.filter(
            action__in=["organization.catalog_initialized", "organization.catalog_adopted"]
        ).count()
        == 1
    )
    assert Campus.objects.count() == (6 if action == "seed" else 1)


@pytest.mark.django_db
def test_deployment_bootstrap_commands_preserve_adopted_catalog_and_policy():
    import re
    import shlex
    from pathlib import Path

    script = (Path(__file__).parents[1] / "deploy/staging/deploy.sh").read_text()
    commands = re.findall(
        r"python manage.py (initialize_organization_catalog.*?)\s*</dev/null", script
    )
    assert len(commands) == 2 and "sync_organization_catalog" not in script

    def bootstrap(action):
        for command in commands:
            argv = shlex.split(
                command.replace("$ORG_CATALOG_ACTION", action).replace("$DEPLOY_SHA", "a" * 40)
            )
            call_command(*argv)

    bootstrap("seed")
    Campus.objects.filter(code="MAIN").update(name="Institutionally renamed", is_active=False)
    College.objects.filter(code="CCMS").update(name="Renamed college", is_active=False)
    Program.objects.filter(code="BSIS").update(
        name="Renamed degree", is_active=False, applicable_year_levels=[1, 3, 5]
    )
    extra = Program.objects.create(
        college=College.objects.get(code="CCMS"), code="EXTRA", name="Additional"
    )
    before = {
        model: list(model.objects.order_by("pk").values()) for model in [Campus, College, Program]
    }
    bootstrap("check")
    bootstrap("adopt")
    call_command("sync_organization_catalog")
    assert extra.pk in Program.objects.values_list("id", flat=True)
    for model, rows in before.items():
        assert list(model.objects.order_by("pk").values()) == rows


@pytest.mark.django_db
def test_seeder_prerequisites_do_not_initialize_or_reconcile_catalog():
    from compass.organization.models import CatalogInitialization
    from compass.staging_seed.seed import sync_prerequisites
    from compass.staging_seed.support import StagingSeedError

    with pytest.raises(StagingSeedError, match="not initialized"):
        sync_prerequisites()
    assert not Campus.objects.exists() and not CatalogInitialization.objects.exists()
    sync_organization_catalog()
    Program.objects.filter(code="BSIS").update(
        name="Official renamed degree", is_active=False, applicable_year_levels=[1, 4, 5]
    )
    extra = Program.objects.create(
        college=College.objects.get(code="CCMS"), code="ADDED", name="Added"
    )
    before = list(Program.objects.order_by("pk").values())
    sync_prerequisites()
    sync_prerequisites()
    assert list(Program.objects.order_by("pk").values()) == before
    assert Program.objects.get(pk=extra.pk).is_active


@pytest.mark.django_db
def test_initializer_refuses_an_unapplied_schema_even_with_a_receipt():
    from django.db.migrations.recorder import MigrationRecorder

    from compass.organization.bootstrap import initialize_organization_catalog

    sync_organization_catalog()
    MigrationRecorder.Migration.objects.filter(
        app="organization", name="0002_program_policy_and_catalog_initialization"
    ).delete()
    with pytest.raises(CanonicalOrganizationSyncError, match="schema is incompatible"):
        initialize_organization_catalog(action="check")
