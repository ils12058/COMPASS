"""Persisted policy rejects bypasses and is authoritative independently of seed identity."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from compass.good_moral.services import F4AcademicEligibility, _f4_academic_context
from compass.inventory.services import InvalidInventoryInput, _validate_program_year_level
from compass.organization.models import Campus, College, Program
from compass.organization.program_policy import get_program_policy, validate_program_policy
from compass.organization.selection import active_programs


def program(**policy):
    campus = Campus.objects.create(code="NEW", name="New campus")
    college = College.objects.create(campus=campus, code="NEW", name="New unit")
    return Program.objects.create(college=college, code="NEW", name="Reported program", **policy)


@pytest.mark.parametrize(
    "classification,status,levels",
    [
        ("INVALID", "PENDING_POLICY", None),
        ("BACHELORS", "INVALID", None),
        (None, "CONFIGURED", [1]),
        ("BACHELORS", "CONFIGURED", None),
        ("BACHELORS", "CONFIGURED", []),
        ("BACHELORS", "PENDING_POLICY", []),
        ("BACHELORS", "CONFIGURED", [True]),
        ("BACHELORS", "CONFIGURED", [1.0]),
        ("BACHELORS", "CONFIGURED", [None]),
        ("BACHELORS", "CONFIGURED", [0]),
        ("BACHELORS", "CONFIGURED", [11]),
        ("BACHELORS", "CONFIGURED", [2, 1]),
        ("BACHELORS", "CONFIGURED", [1, 1]),
        ("BACHELORS", "CONFIGURED", [[1]]),
    ],
)
def test_shared_validation_rejects_without_coercion(classification, status, levels):
    with pytest.raises(ValidationError):
        validate_program_policy(classification, status, levels)
    item = Program(
        academic_classification=classification,
        year_level_policy_status=status,
        applicable_year_levels=levels,
    )
    with pytest.raises(ValidationError):
        item.clean_fields()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "assignment",
    [
        "academic_classification='INVALID'",
        "year_level_policy_status='INVALID'",
        "academic_classification=NULL",
        "applicable_year_levels=NULL",
        "applicable_year_levels='{}'::smallint[]",
        "year_level_policy_status='PENDING_POLICY'",
        "applicable_year_levels=ARRAY[0]::smallint[]",
        "applicable_year_levels=ARRAY[11]::smallint[]",
        "applicable_year_levels=ARRAY[1,1]::smallint[]",
        "applicable_year_levels=ARRAY[2,1]::smallint[]",
        "applicable_year_levels=ARRAY[1,NULL]::smallint[]",
        "applicable_year_levels=ARRAY[[1,2],[3,4]]::smallint[]",
        "applicable_year_levels='[0:1]={1,2}'::smallint[]",
    ],
)
def test_postgresql_rejects_policy_bypasses(assignment):
    item = program(
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 2, 3, 4],
    )
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        # assignment is a closed, source-owned parameter set, never request input.
        cursor.execute(f"UPDATE organization_program SET {assignment} WHERE id=%s", [item.pk])
    item.refresh_from_db()
    assert item.applicable_year_levels == [1, 2, 3, 4]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "classification,configured",
    [
        (classification, configured)
        for classification in ["BACHELORS", "MASTERS", "DOCTORAL", None]
        for configured in [False, True]
        if classification is not None or not configured
    ],
)
def test_persisted_states_and_inventory_compatibility(classification, configured):
    item = program(
        academic_classification=classification,
        year_level_policy_status="CONFIGURED" if configured else "PENDING_POLICY",
        applicable_year_levels=[1, 3, 5] if configured else None,
    )
    assert get_program_policy(item).academic_classification == classification
    _validate_program_year_level(item, 3)
    if configured:
        with pytest.raises(InvalidInventoryInput):
            _validate_program_year_level(item, 2)
    else:
        _validate_program_year_level(item, 10)
    status = _f4_academic_context(program=item, year_level=3).status
    assert status == (
        F4AcademicEligibility.UNCLASSIFIED_PROGRAM
        if classification is None
        else F4AcademicEligibility.POSTGRADUATE_PROGRAM
        if classification != "BACHELORS"
        else F4AcademicEligibility.ELIGIBLE
        if configured
        else F4AcademicEligibility.UNSUPPORTED_YEAR_LEVEL
    )
    assert _f4_academic_context(program=item, year_level=5).status != F4AcademicEligibility.ELIGIBLE


@pytest.mark.django_db
def test_active_selection_and_historical_lookup_are_distinct():
    item = program()
    assert active_programs().get().pk == item.pk
    Campus.objects.filter(pk=item.college.campus_id).update(is_active=False)
    assert not active_programs().exists()
    assert Program.objects.get(pk=item.pk).pk == item.pk


@pytest.mark.django_db
def test_noncanonical_program_api_and_degree_options_follow_database_policy():
    from compass.organization.canonical import CANONICAL_PROGRAM_IDENTITIES
    from tests.test_good_moral import auth_client, make_user, sync_policy

    sync_policy()
    student = make_user("catalog-reader@synthetic.invalid")
    item = program(
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 4, 5],
    )
    assert ("NEW", "NEW", "NEW") not in CANONICAL_PROGRAM_IDENTITIES
    client = auth_client(student)
    response = client.get(f"/api/v1/organization/programs/{item.pk}")
    assert response.status_code == 200
    assert response.json()["academic_classification"] == "BACHELORS"
    assert response.json()["applicable_year_levels"] == [1, 4, 5]
    assert client.get("/api/v1/good-moral/degree-options").json()["items"] == [item.name]
    Program.objects.filter(pk=item.pk).update(name="New official name")
    assert client.get("/api/v1/good-moral/degree-options").json()["items"] == ["New official name"]
    College.objects.filter(pk=item.college_id).update(is_active=False)
    assert client.get("/api/v1/good-moral/degree-options").json()["items"] == []
    # Historical reference reads remain available even with an inactive parent.
    assert client.get(f"/api/v1/organization/programs/{item.pk}").status_code == 200


@pytest.mark.django_db
def test_new_database_bachelor_submits_inventory_and_creates_f4_with_frozen_facts():
    from compass.audit.context import AuditContext
    from compass.good_moral.services import create_my_current_student
    from compass.inventory.services import (
        ensure_current_inventory,
        replace_current_inventory,
        submit_current_inventory,
    )
    from compass.organization.models import StudentAffiliation
    from tests.inventory_test_helpers import minimum_normalized_inventory_values
    from tests.test_good_moral import make_user, sync_policy
    from tests.test_inventory import configure_year

    sync_policy()
    student = make_user("new-bachelor@synthetic.invalid")
    actor = make_user("admin@synthetic.invalid", role="IT_ADMIN")
    configure_year(actor)
    item = program(
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 4, 5],
    )
    StudentAffiliation.objects.create(student=student, college=item.college)
    ensure_current_inventory(student=student, context=AuditContext.user(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=item.pk, year_level=4),
    )
    inventory = submit_current_inventory(student=student, context=AuditContext.user(student))
    certificate = create_my_current_student(
        student=student,
        semester="First Semester",
        context=AuditContext.user(student),
        idempotency_key="org-1-new-bachelor",
        request_fingerprint="a" * 64,
    )
    assert certificate.course_snapshot == item.name
    assert certificate.year_level_snapshot == "4th Year"
    Program.objects.filter(pk=item.pk).update(
        name="Later rename", is_active=False, academic_classification="MASTERS"
    )
    inventory.refresh_from_db()
    certificate.refresh_from_db()
    assert inventory.course_currently_enrolled == item.name
    assert certificate.course_snapshot == item.name
