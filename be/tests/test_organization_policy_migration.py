"""Actual disposable PostgreSQL upgrades from the populated Organization 0001 schema."""

import copy
import importlib
import uuid
from datetime import date

import pytest
from django.db import connection, connections, migrations
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BASE = ("organization", "0001_canonical_baseline")
TARGET = ("organization", "0002_program_policy_and_catalog_initialization")
MODULE = "compass.organization.migrations.0002_program_policy_and_catalog_initialization"


@pytest.fixture
def upgrade_database(django_db_blocker):
    """Only the isolated test server is used; no source .env or deployed connection."""
    name = "org1_upgrade_" + uuid.uuid4().hex
    alias = name
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
        config = copy.deepcopy(connection.settings_dict)
        config["NAME"] = name
        connections.databases[alias] = config
        db = connections[alias]
        try:
            executor = MigrationExecutor(db)
            targets = [
                node for node in executor.loader.graph.leaf_nodes() if node[0] != "organization"
            ]
            targets.append(BASE)
            executor.migrate(targets)
            yield db, executor.loader.project_state(targets).apps
        finally:
            db.close()
            del connections[alias]
            del connections.databases[alias]
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE "{name}"')


def historical_fixture(db, apps):
    alias = db.alias

    def manager(app, model):
        return apps.get_model(app, model).objects.using(alias)

    campuses = {}
    colleges = {}
    programs = {}
    frozen = importlib.import_module(MODULE).FROZEN_PROGRAM_POLICIES
    for campus, college, code, *_ in frozen:
        if campus not in campuses:
            campuses[campus] = manager("organization", "Campus").create(
                code=campus, name=f"Official campus {campus}"
            )
        if (campus, college) not in colleges:
            colleges[campus, college] = manager("organization", "College").create(
                campus_id=campuses[campus].pk, code=college, name=f"Official unit {college}"
            )
        programs[campus, college, code] = manager("organization", "Program").create(
            college_id=colleges[campus, college].pk,
            code=code,
            name=f"Official renamed {code}",
            is_active=code not in {"BSIT", "DBA"},
        )
    # Missing baseline rows are never recreated by backfill.
    programs.pop(("ENTIENZA", "ENTIENZA", "BEED")).delete(using=alias)
    for code, active in [("UNKNOWN", True), ("OLD", False)]:
        manager("organization", "Program").create(
            college_id=colleges["MAIN", "CCMS"].pk,
            code=code,
            name="Bachelor of Science in Information Systems",
            is_active=active,
        )
    # Code/parent changes deliberately no longer match the frozen identity.
    manager("organization", "Program").filter(pk=programs["MAIN", "CAS", "BSAM"].pk).update(
        code="RENAMED_CODE"
    )
    manager("organization", "Program").filter(pk=programs["MAIN", "CAS", "BSBIOL"].pk).update(
        college_id=colleges["MAIN", "CCMS"].pk
    )
    people = {}
    for key, role in [
        ("student", "STUDENT"),
        ("counselor", "COUNSELOR"),
        ("staff", "GUIDANCE_SERVICES_STAFF"),
    ]:
        r = manager("accounts", "Role").create(code=role, name=role)
        people[key] = manager("accounts", "User").create(
            role_id=r.pk,
            email=key + "@synthetic.invalid",
            first_name=key,
            last_name="Fixture",
            profile_confidential_content_ciphertext="preservation-sentinel",
        )
    college = colleges["MAIN", "CCMS"]
    manager("organization", "StudentAffiliation").create(
        student_id=people["student"].pk, college_id=college.pk
    )
    manager("organization", "CounselorResponsibility").create(
        college_id=college.pk, counselor_id=people["counselor"].pk
    )
    manager("organization", "StaffSupervision").create(
        staff_id=people["staff"].pk, supervisor_id=people["counselor"].pk
    )
    year = manager("organization", "AcademicYear").create(label="2025-2026")
    family = manager("institutional_forms", "FormFamily").create(key="synthetic", title="Synthetic")
    revision = manager("institutional_forms", "FormRevision").create(
        family_id=family.pk, internal_schema_version=1
    )
    manager("inventory", "StudentInventory").create(
        student_id=people["student"].pk,
        academic_year_id=year.pk,
        form_revision_id=revision.pk,
        program_id=programs["MAIN", "CCMS", "BSIS"].pk,
        year_level=4,
        course_currently_enrolled="Historical submitted degree",
        submitted_at=timezone.now(),
        confidential_content_ciphertext="preservation-sentinel",
    )
    manager("good_moral", "GoodMoralRequest").create(
        student_id=people["student"].pk,
        variant="GRADUATE",
        status="ISSUED",
        degree_snapshot="Historical degree",
        applicant_name_snapshot="Historical name",
        graduation_date=date(2020, 1, 1),
        form_revision_id=revision.pk,
        issued_at=timezone.now(),
        issued_by_id=people["counselor"].pk,
        issued_by_name_snapshot="Historical issuer",
        document_template_key="good_moral_graduate",
        document_template_version=1,
    )
    manager("graduate_tracer", "GraduateTracerResponse").create(
        student_id=people["student"].pk,
        graduated_college_id=college.pk,
        graduated_program_id=programs["MAIN", "CCMS", "BSIS"].pk,
        confidential_content_ciphertext="preservation-sentinel",
    )
    return [
        ("organization", m)
        for m in [
            "Campus",
            "College",
            "Program",
            "StudentAffiliation",
            "CounselorResponsibility",
            "StaffSupervision",
        ]
    ] + [
        ("inventory", "StudentInventory"),
        ("good_moral", "GoodMoralRequest"),
        ("graduate_tracer", "GraduateTracerResponse"),
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("inject_failure", [False, True])
def test_populated_upgrade_is_frozen_and_preserves_all_original_fields(
    upgrade_database, inject_failure
):
    db, apps = upgrade_database
    models = historical_fixture(db, apps)
    before = {
        key: list(apps.get_model(*key).objects.using(db.alias).order_by("pk").values())
        for key in models
    }
    executor = MigrationExecutor(db)
    if inject_failure:
        operation = next(
            op
            for op in executor.loader.disk_migrations[TARGET].operations
            if isinstance(op, migrations.RunPython)
        )
        original = operation.code

        def fail_after_backfill(apps, editor):
            original(apps, editor)
            raise RuntimeError("synthetic backfill failure")

        operation.code = fail_after_backfill
        try:
            with pytest.raises(RuntimeError, match="synthetic backfill"):
                executor.migrate([TARGET])
        finally:
            operation.code = original
        assert TARGET not in MigrationExecutor(db).loader.applied_migrations
        with db.cursor() as cursor:
            columns = db.introspection.get_table_description(cursor, "organization_program")
            assert "academic_classification" not in {col.name for col in columns}
        assert (
            list(
                apps.get_model("organization", "Program")
                .objects.using(db.alias)
                .order_by("pk")
                .values()
            )
            == before["organization", "Program"]
        )
    executor = MigrationExecutor(db)
    executor.migrate([TARGET])
    after_apps = executor.loader.project_state(
        [TARGET]
        + [node for node in executor.loader.graph.leaf_nodes() if node[0] != "organization"]
    ).apps
    for key, rows in before.items():
        actual = after_apps.get_model(*key).objects.using(db.alias).order_by("pk")
        assert list(actual.values(*rows[0])) == rows
    Program = after_apps.get_model("organization", "Program")
    expected = {
        (c, k, p): (classification, status, levels)
        for c, k, p, classification, status, levels in importlib.import_module(
            MODULE
        ).FROZEN_PROGRAM_POLICIES
    }
    for item in Program.objects.using(db.alias).select_related("college__campus"):
        identity = (item.college.campus.code, item.college.code, item.code)
        assert (
            item.academic_classification,
            item.year_level_policy_status,
            item.applicable_year_levels,
        ) == expected.get(identity, (None, "PENDING_POLICY", None))
    assert Program.objects.using(db.alias).count() == 39
    assert (
        not after_apps.get_model("organization", "CatalogInitialization")
        .objects.using(db.alias)
        .exists()
    )
    before_repeat = list(Program.objects.using(db.alias).order_by("pk").values())
    assert not MigrationExecutor(db).migration_plan([TARGET])
    MigrationExecutor(db).migrate([TARGET])
    assert list(Program.objects.using(db.alias).order_by("pk").values()) == before_repeat
    with pytest.raises(IrreversibleError):
        MigrationExecutor(db).migrate([BASE])
