"""Faculty assignment and catalog retirement serialize on real PostgreSQL connections."""

import pytest

from compass.account_management.faculty import set_faculty_affiliation
from compass.account_management.services import InvalidManagementInput, create_account
from compass.organization import catalog_services as catalog
from compass.organization.models import College, FacultyAffiliation
from tests.catalog_test_helpers import authority, hierarchy, manager, run_serialized_race
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

    def retire():
        return catalog.set_college_active(
            **auth,
            target_id=college.pk,
            expected_resource_version=1,
            is_active=False,
        )

    _, second = run_serialized_race(
        retire if retire_first else assign, assign if retire_first else retire
    )
    if retire_first:
        assert isinstance(second, InvalidManagementInput)
        assert not FacultyAffiliation.objects.filter(college=college).exists()
    else:
        assert isinstance(second, catalog.CatalogError)
        assert second.code == "catalog_deactivation_blocked"
        assert College.objects.get(pk=college.pk).is_active
