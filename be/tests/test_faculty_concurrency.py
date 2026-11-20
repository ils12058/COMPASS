"""Faculty assignment and catalog retirement serialize on real PostgreSQL connections."""

import pytest

from compass.account_management.faculty import set_faculty_affiliation
from compass.account_management.services import InvalidManagementInput, create_account
from compass.organization import catalog_services as catalog
from compass.organization.models import College, FacultyAffiliation
from tests.catalog_test_helpers import (
    authority,
    hierarchy,
    manager,
    retirement_preview,
    run_serialized_race,
)
from tests.test_faculty_foundation import person

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("retire_first", [False, True])
@pytest.mark.parametrize("writer", ["assignment", "creation"])
def test_faculty_assignment_and_college_retirement_cannot_both_commit(retire_first, writer):
    admin, issued = manager()
    auth = authority(admin, issued)
    campus, _, _ = hierarchy()
    college = College.objects.create(campus=campus, code="FAC", name="Faculty home")
    faculty = person()
    preview = retirement_preview(auth, college)

    def assign():
        if writer == "creation":
            return create_account(
                **{k: v for k, v in auth.items() if k != "basis"},
                institutional_id="FAC-RACE",
                email="race@synthetic.invalid",
                first_name="Faculty",
                last_name="Race",
                role="FACULTY",
                faculty_college_id=college.pk,
            )
        return set_faculty_affiliation(
            **auth,
            target_id=faculty.pk,
            college_id=college.pk,
            expected_resource_version=0,
        )

    def retire(observed=preview):
        return catalog.set_college_active(
            **auth,
            target_id=college.pk,
            expected_resource_version=1,
            is_active=False,
            **observed,
        )

    _, second = run_serialized_race(
        retire if retire_first else assign, assign if retire_first else retire
    )
    if retire_first:
        assert isinstance(second, InvalidManagementInput)
        assert not FacultyAffiliation.objects.filter(college=college).exists()
        college.refresh_from_db()
        assert college.is_retired and not college.is_active
        if writer == "creation":
            assert not type(faculty).objects.filter(email="race@synthetic.invalid").exists()
    else:
        assert isinstance(second, catalog.CatalogError)
        assert second.code == "catalog_stale_impact"
        assert College.objects.get(pk=college.pk).is_active
        affiliation = FacultyAffiliation.objects.get(college=college)
        saved = FacultyAffiliation.objects.filter(pk=affiliation.pk).values().get()
        impact = catalog.get_catalog_impact(actor=admin, model=College, target_id=college.pk)
        assert {issue.code: issue.count for issue in impact.warnings}[
            "active_faculty_affiliations"
        ] == 1
        assert not impact.blockers
        retire(retirement_preview(auth, college))
        college.refresh_from_db()
        assert college.is_retired and not college.is_active
        assert FacultyAffiliation.objects.filter(pk=affiliation.pk).values().get() == saved
        late_faculty = person(label="late")
        with pytest.raises(InvalidManagementInput):
            set_faculty_affiliation(
                **auth,
                target_id=late_faculty.pk,
                college_id=college.pk,
                expected_resource_version=0,
            )
        assert not FacultyAffiliation.objects.filter(faculty=late_faculty).exists()
