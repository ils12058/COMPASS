"""FORM-REQ-1: submission requires the official F5 answers and no "prefer not to specify"."""

from __future__ import annotations

from copy import deepcopy

import pytest

from compass.inventory.correction_targets import InventoryCorrectionTarget as T
from compass.inventory.services import (
    InvalidInventoryInput,
    ensure_current_inventory,
    reopen_inventory_for_correction,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
)
from tests.inventory_test_helpers import minimum_normalized_inventory_values
from tests.test_inventory_counselor_review import (
    affiliate,
    configure_year,
    context,
    make_head,
    make_org,
    make_user,
    submit_inventory,
    sync_policy,
)

pytestmark = pytest.mark.usefixtures("inventory_psgc")


def set_path(values: dict, path: tuple[object, ...], value: object) -> None:
    target = values
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def make_draft(code: str) -> tuple[object, object]:
    sync_policy()
    admin = make_user(f"formreq-admin-{code}@example.edu", "IT_ADMIN")
    student = make_user(f"formreq-student-{code}@example.edu", "STUDENT")
    configure_year(admin)
    _, _, program = make_org(code)
    affiliate(student, program.college)
    ensure_current_inventory(student=student, context=context(student))
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    return student, program


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("support_profile", "four_ps_status"), "NOT_SURE"),
        (("family_members", 0, "annual_income_status"), "UNKNOWN"),
        (("family_members", 1, "annual_income_status"), "UNKNOWN"),
        (("support_profile", "father_life_status"), "UNKNOWN"),
        (("support_profile", "mother_life_status"), "UNKNOWN"),
    ],
)
def test_new_uncertain_choices_are_accepted_at_submission(path, value):
    student, program = make_draft("newchoice")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    set_path(values, path, value)
    replace_current_inventory(student=student, values=values)

    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_not_sure_and_unknown_choices_are_stored_and_returned_verbatim():
    student, program = make_draft("verbatim")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["support_profile"].update(
        four_ps_status=FourPsStatus.NOT_SURE,
        indigenous_peoples_status=IndigenousPeoplesStatus.NOT_MEMBER,
        father_life_status=ParentLifeStatus.UNKNOWN,
        mother_life_status=ParentLifeStatus.UNKNOWN,
    )
    values["family_members"][0]["annual_income_status"] = "UNKNOWN"
    values["family_members"][1]["annual_income_status"] = "UNKNOWN"
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))

    profile = submitted.support_profile
    assert profile.four_ps_status == FourPsStatus.NOT_SURE
    assert profile.father_life_status == ParentLifeStatus.UNKNOWN
    assert submitted.family_members.get(kind="FATHER").annual_income_status == "UNKNOWN"


# --- Change B: conditional rules, both ways --------------------------------------------------


@pytest.mark.django_db
def test_spouse_details_are_required_only_for_a_married_student():
    student, program = make_draft("spouse")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["civil_status_category"] = "MARRIED"
    replace_current_inventory(student=student, values=values)

    with pytest.raises(InvalidInventoryInput, match="Add your spouse's details."):
        submit_current_inventory(student=student, context=context(student))

    spouse = deepcopy(values["family_members"][1])
    spouse["kind"] = "SPOUSE"
    spouse["name"] = "Synthetic Spouse"
    values["family_members"].append(spouse)
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.civil_status_category == "MARRIED"
    assert submitted.family_members.filter(kind="SPOUSE").exists()


@pytest.mark.django_db
def test_boarding_details_are_required_only_for_a_boarding_house():
    student, program = make_draft("boarding")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        living_arrangement="BOARDING_HOUSE",
        boarding_exclusive=None,
        boarding_landlord_name="",
        boarding_address="",
    )
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="boarding room is exclusive"):
        submit_current_inventory(student=student, context=context(student))

    values.update(
        boarding_exclusive=True,
        boarding_landlord_name="Synthetic Landlord",
        boarding_address="Synthetic boarding address",
    )
    replace_current_inventory(student=student, values=values)
    assert submit_current_inventory(student=student, context=context(student)).submitted_at


@pytest.mark.django_db
def test_non_boarding_students_are_never_asked_for_boarding_details():
    student, program = make_draft("ownhouse")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        living_arrangement="OWN_HOUSE",
        boarding_exclusive=None,
        boarding_landlord_name="",
        boarding_address="",
    )
    replace_current_inventory(student=student, values=values)
    assert submit_current_inventory(student=student, context=context(student)).submitted_at


@pytest.mark.django_db
def test_deceased_or_unknown_parent_details_are_not_required():
    student, program = make_draft("absent-parent")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["family_members"] = values["family_members"][1:]
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="Add your father's details."):
        submit_current_inventory(student=student, context=context(student))

    values["support_profile"]["father_life_status"] = "DECEASED"
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_unknown_parent_life_status_never_requires_that_parents_details():
    student, program = make_draft("unknown-parent")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["family_members"] = values["family_members"][:1]
    values["support_profile"]["mother_life_status"] = "UNKNOWN"
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_prior_counseling_details_are_required_only_when_the_answer_is_yes():
    student, program = make_draft("prior")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        prior_counseling_experience=True,
        prior_counselor_name="",
        prior_counseling_when="",
        prior_counseling_where="",
    )
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="previous counselor's name"):
        submit_current_inventory(student=student, context=context(student))

    values.update(
        prior_counselor_name="Synthetic Counselor",
        prior_counseling_when="2024",
        prior_counseling_where="Synthetic Guidance Office",
    )
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_an_unsatisfied_schedule_requires_an_explanation():
    student, program = make_draft("schedule")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(schedule_satisfied=False, schedule_satisfaction_reason="")
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="why you are not satisfied"):
        submit_current_inventory(student=student, context=context(student))

    values["schedule_satisfaction_reason"] = "The subjects overlap."
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_accident_and_operation_effects_are_required_for_an_actual_experience():
    student, program = make_draft("accidents")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(accidents_experienced="Car accident", accidents_effect="")
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="effect of the accidents"):
        submit_current_inventory(student=student, context=context(student))

    values["accidents_effect"] = "A broken arm."
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_a_none_accident_and_operation_answer_needs_no_effect():
    student, program = make_draft("noaccidents")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        accidents_experienced="None",
        accidents_effect="",
        operations_experienced="None",
        operations_effect="",
    )
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None


@pytest.mark.django_db
def test_reopened_correction_is_not_blocked_by_non_target_answers():
    sync_policy()
    admin = make_user("formreq-corr-admin@example.edu", "IT_ADMIN")
    head = make_head("formreq-corr-head@example.edu")
    student = make_user("formreq-corr-student@example.edu", "STUDENT")
    configure_year(admin)
    _, college, program = make_org("CORR")
    affiliate(student, college, head)
    item = submit_inventory(student=student, program=program)

    reopen_inventory_for_correction(
        actor=head,
        inventory_id=item.pk,
        reason="Review the nickname.",
        targets=[T.PERSONAL_NICKNAME.value],
        context=context(head),
    )
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["guardian_contact_number"] = ""
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=context(student))
    assert submitted.submitted_at is not None

    item.refresh_from_db()
    reopen_inventory_for_correction(
        actor=head,
        inventory_id=item.pk,
        reason="Correct the guardian contact.",
        targets=[T.FAMILY_GUARDIAN_CONTACT_NUMBER.value],
        context=context(head),
    )
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["guardian_contact_number"] = ""
    replace_current_inventory(student=student, values=values)
    with pytest.raises(InvalidInventoryInput, match="guardian's contact number"):
        submit_current_inventory(student=student, context=context(student))
