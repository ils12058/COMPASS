"""Targeted tests for ADR-121: separate solo-parent indicator from civil status."""

from __future__ import annotations

import importlib
import json
from copy import deepcopy
from datetime import date

import pytest
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.documents.rendering import render_document_html
from compass.inventory.confidential_content import (
    read_confidential_content,
    read_inventory_private_projection,
)
from compass.inventory.documents import build_inventory_render_context
from compass.inventory.models import CivilStatusCategory, StudentInventory
from compass.inventory.services import (
    InvalidInventoryInput,
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import (
    create_academic_year,
    set_current_academic_year,
)
from compass.organization.models import AcademicYear, Campus, College, Program
from compass.reports.pdf import (
    REPORT_PARTS,
    SECTION_ORDER,
    build_student_profiling_print_context,
)
from compass.reports.services import (
    GLOBAL_REPORT_ACCESS_SCOPE,
    LEGACY_UNSPECIFIED_KEY,
    LEGACY_UNSPECIFIED_LABEL,
    build_student_profiling_report,
)
from compass.reports.xlsx import SECTION_SPECS, build_student_profiling_workbook
from compass.student_academics.models import StudentAcademicProfile
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    SoloParentStatus,
    StudentSupportProfile,
)
from compass.student_support.services import build_student_support_context
from tests.inventory_encryption_helpers import update_inventory_private
from tests.inventory_test_helpers import minimum_normalized_inventory_values
from tests.test_student_profiling_report_aggregates import assert_report_reconciles
from tests.test_student_profiling_reports import (
    make_inventory,
    make_organization,
    make_revision,
    report_row,
)
from tests.test_student_profiling_reports import make_user as make_profile_student

backfill_migration = importlib.import_module(
    "compass.student_support.migrations.0003_backfill_solo_parent_status"
)

pytestmark = pytest.mark.usefixtures("inventory_psgc")


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def audit_ctx(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def make_user(email: str, role: str = "STUDENT") -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password-long-enough",
        role=Role.objects.get(code=role),
        first_name="Synthetic",
        last_name="Person",
    )


def make_head(email: str = "solo-head@example.edu") -> User:
    user = make_user(email, role="COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def setup_student_draft(code: str) -> tuple[User, Program]:
    sync_policy()
    admin = make_user(f"solo-admin-{code}@example.edu", "IT_ADMIN")
    student = make_user(f"solo-student-{code}@example.edu", "STUDENT")
    year = AcademicYear.objects.filter(label="2026-2027").first()
    if year is None:
        year = create_academic_year(label="2026-2027", context=audit_ctx(admin))
        set_current_academic_year(academic_year_id=year.pk, context=audit_ctx(admin))
    campus = Campus.objects.create(code=f"SP-C-{code}", name=f"Campus {code}")
    college = College.objects.create(campus=campus, code=f"SP-COL-{code}", name=f"College {code}")
    program = Program.objects.create(college=college, code=f"SP-P-{code}", name=f"Program {code}")
    StudentAcademicProfile.objects.create(student=student, current_college=college)
    ensure_current_inventory(student=student, context=audit_ctx(student))
    return student, program


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "expected_text", "detail", "needs_spouse"),
    [
        ("SINGLE", "Single", "", False),
        ("MARRIED", "Married", "", True),
        ("WIDOWED", "Widowed", "", False),
        ("SEPARATED", "Separated", "", False),
        ("ANNULLED", "Annulled", "", False),
        ("OTHER", "Legally separated pending decree", "Legally separated pending decree", False),
    ],
)
def test_new_civil_status_choices_save_submit_and_store_label_text(
    category,
    expected_text,
    detail,
    needs_spouse,
):
    student, program = setup_student_draft(category.lower())
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["civil_status_category"] = category
    values["civil_status"] = detail
    if needs_spouse:
        spouse = deepcopy(values["family_members"][1])
        spouse["kind"] = "SPOUSE"
        spouse["name"] = "Synthetic Spouse"
        values["family_members"].append(spouse)

    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=audit_ctx(student))

    assert submitted.civil_status_category == category
    private = read_confidential_content(submitted)
    assert private.civil_status == expected_text


@pytest.mark.django_db
def test_other_civil_status_requires_detail_and_legacy_solo_parent_is_rejected_for_new_input():
    student, program = setup_student_draft("reject")
    values = minimum_normalized_inventory_values(program_id=program.pk)

    # OTHER requires detail text.
    values["civil_status_category"] = "OTHER"
    values["civil_status"] = "   "
    with pytest.raises(InvalidInventoryInput, match="civil_status detail is required"):
        replace_current_inventory(student=student, values=values)

    # Service rejects legacy SOLO_PARENT for new input.
    values["civil_status_category"] = CivilStatusCategory.SOLO_PARENT
    values["civil_status"] = ""
    with pytest.raises(InvalidInventoryInput, match="Solo Parent is no longer a civil status"):
        replace_current_inventory(student=student, values=values)

    # API rejects legacy SOLO_PARENT with 422 before hitting storage.
    client = auth_client(student)
    response = client.put(
        "/api/v1/inventory/me/current",
        data=json.dumps({"civil_status_category": "SOLO_PARENT"}),
        content_type="application/json",
    )
    assert response.status_code == 422

    # A draft still carrying SOLO_PARENT in the DB cannot be submitted without choosing again.
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    StudentInventory.objects.filter(student=student).update(
        civil_status_category=CivilStatusCategory.SOLO_PARENT
    )
    with pytest.raises(InvalidInventoryInput, match="civil status"):
        submit_current_inventory(student=student, context=audit_ctx(student))


@pytest.mark.django_db
def test_solo_parent_question_is_nullable_on_draft_required_on_submit_and_saves_yes_and_no():
    student, program = setup_student_draft("spq")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["support_profile"]["solo_parent_status"] = None

    draft = replace_current_inventory(student=student, values=values)
    assert draft.support_profile.solo_parent_status is None

    with pytest.raises(InvalidInventoryInput, match="Answer whether you are a solo parent."):
        submit_current_inventory(student=student, context=audit_ctx(student))

    # Invalid value rejected by service and API.
    bad_values = deepcopy(values)
    bad_values["support_profile"]["solo_parent_status"] = "MAYBE"
    with pytest.raises(
        InvalidInventoryInput, match="Unsupported support_profile solo_parent_status"
    ):
        replace_current_inventory(student=student, values=bad_values)

    client = auth_client(student)
    bad_api = client.put(
        "/api/v1/inventory/me/current",
        data=json.dumps({"support_profile": {"solo_parent_status": "MAYBE"}}),
        content_type="application/json",
    )
    assert bad_api.status_code == 422

    # YES saves and submits alongside a real civil status such as Widowed.
    values["civil_status_category"] = CivilStatusCategory.WIDOWED
    values["support_profile"]["solo_parent_status"] = SoloParentStatus.YES
    replace_current_inventory(student=student, values=values)
    submitted = submit_current_inventory(student=student, context=audit_ctx(student))
    assert submitted.civil_status_category == CivilStatusCategory.WIDOWED
    assert submitted.support_profile.solo_parent_status == SoloParentStatus.YES

    # NO saves and submits cleanly for a second student.
    student_no, program_no = setup_student_draft("spq-no")
    no_values = minimum_normalized_inventory_values(program_id=program_no.pk)
    no_values["support_profile"]["solo_parent_status"] = SoloParentStatus.NO
    replace_current_inventory(student=student_no, values=no_values)
    submitted_no = submit_current_inventory(student=student_no, context=audit_ctx(student_no))
    assert submitted_no.support_profile.solo_parent_status == SoloParentStatus.NO


@pytest.mark.django_db
def test_legacy_draft_clears_civil_status_while_historical_submitted_record_stays_immutable():
    student, program = setup_student_draft("legacy-draft")
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values["support_profile"]["solo_parent_status"] = SoloParentStatus.YES
    draft = replace_current_inventory(student=student, values=values)
    StudentInventory.objects.filter(pk=draft.pk).update(
        civil_status_category=CivilStatusCategory.SOLO_PARENT
    )
    update_inventory_private(draft, civil_status="Solo Parent")

    client = auth_client(student)
    current = client.get("/api/v1/inventory/me/current")
    assert current.status_code == 200
    body = current.json()
    assert body["civil_status_category"] is None
    assert body["civil_status"] == ""
    assert body["support_profile"]["solo_parent_status"] == "YES"

    # Choosing a real civil status lets the student submit with solo_parent_status=YES.
    values["civil_status_category"] = CivilStatusCategory.SEPARATED
    replace_current_inventory(student=student, values=values)
    submitted_new = submit_current_inventory(student=student, context=audit_ctx(student))
    assert submitted_new.civil_status_category == CivilStatusCategory.SEPARATED
    assert submitted_new.support_profile.solo_parent_status == SoloParentStatus.YES

    # Official F5 printout prints "Separated" and does NOT add a solo-parent item.
    rendered_new, _ = render_document_html(
        template_key="individual_inventory",
        template_version=1,
        context=build_inventory_render_context(
            submitted_new, private=read_inventory_private_projection(submitted_new)
        ),
    )
    assert "Separated" in rendered_new
    assert "solo parent" not in rendered_new.lower()

    # Historical submitted records with legacy SOLO_PARENT remain readable and print as submitted.
    head = make_head("solo-legacy-head@example.edu")
    legacy_student, legacy_program = setup_student_draft("legacy-sub")
    legacy_values = minimum_normalized_inventory_values(program_id=legacy_program.pk)
    legacy_values["support_profile"]["solo_parent_status"] = SoloParentStatus.YES
    replace_current_inventory(student=legacy_student, values=legacy_values)
    legacy_item = submit_current_inventory(
        student=legacy_student, context=audit_ctx(legacy_student)
    )
    StudentInventory.objects.filter(pk=legacy_item.pk).update(
        civil_status_category=CivilStatusCategory.SOLO_PARENT
    )
    update_inventory_private(legacy_item, civil_status="Solo Parent")
    legacy_item.refresh_from_db()

    me_history = auth_client(legacy_student).get(f"/api/v1/inventory/me/{legacy_item.pk}")
    assert me_history.status_code == 200
    assert me_history.json()["civil_status_category"] == "SOLO_PARENT"
    assert me_history.json()["civil_status"] == "Solo Parent"
    assert me_history.json()["support_profile"]["solo_parent_status"] == "YES"

    head_record = auth_client(head).get(f"/api/v1/inventory/records/{legacy_item.pk}")
    assert head_record.status_code == 200
    assert head_record.json()["civil_status_category"] == "SOLO_PARENT"
    assert head_record.json()["civil_status"] == "Solo Parent"

    rendered_legacy, _ = render_document_html(
        template_key="individual_inventory",
        template_version=1,
        context=build_inventory_render_context(
            legacy_item, private=read_inventory_private_projection(legacy_item)
        ),
    )
    assert "Solo Parent" in rendered_legacy


@pytest.mark.django_db
def test_backfill_migration_sets_yes_only_for_legacy_rows_and_preserves_civil_status_text():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("backfill")
    _, _, program = make_organization("BF")

    # 1. Legacy SOLO_PARENT row with existing profile (unanswered).
    legacy_with_profile = make_inventory(
        student=make_profile_student("bf-legacy-1@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SOLO_PARENT,
        solo_parent_status=None,
    )
    update_inventory_private(legacy_with_profile, civil_status="Solo Parent")
    legacy_with_profile.refresh_from_db()
    original_ciphertext_1 = legacy_with_profile.confidential_content_ciphertext

    # 2. Legacy SOLO_PARENT row whose StudentSupportProfile row did not yet exist.
    legacy_without_profile = make_inventory(
        student=make_profile_student("bf-legacy-2@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SOLO_PARENT,
        solo_parent_status=None,
    )
    StudentSupportProfile.objects.filter(inventory=legacy_without_profile).delete()
    update_inventory_private(legacy_without_profile, civil_status="Solo Parent")
    legacy_without_profile.refresh_from_db()
    original_ciphertext_2 = legacy_without_profile.confidential_content_ciphertext

    # 3. Non-SOLO_PARENT rows (SINGLE, MARRIED, None) stay unanswered.
    single_row = make_inventory(
        student=make_profile_student("bf-single@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SINGLE,
        solo_parent_status=None,
    )
    married_row = make_inventory(
        student=make_profile_student("bf-married@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.MARRIED,
        solo_parent_status=None,
    )
    unanswered_row = make_inventory(
        student=make_profile_student("bf-none@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=None,
        solo_parent_status=None,
    )

    # 4. Pre-existing explicit NO on a legacy row is never overwritten.
    explicit_no_row = make_inventory(
        student=make_profile_student("bf-explicit-no@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SOLO_PARENT,
        solo_parent_status=SoloParentStatus.NO,
    )

    backfill_migration.backfill_solo_parent_status(apps, None)

    # Re-run to verify idempotency.
    backfill_migration.backfill_solo_parent_status(apps, None)

    legacy_with_profile.refresh_from_db()
    legacy_without_profile.refresh_from_db()
    assert legacy_with_profile.civil_status_category == CivilStatusCategory.SOLO_PARENT
    assert legacy_with_profile.confidential_content_ciphertext == original_ciphertext_1
    assert read_confidential_content(legacy_with_profile).civil_status == "Solo Parent"
    assert (
        StudentSupportProfile.objects.get(inventory=legacy_with_profile).solo_parent_status
        == SoloParentStatus.YES
    )

    assert legacy_without_profile.civil_status_category == CivilStatusCategory.SOLO_PARENT
    assert legacy_without_profile.confidential_content_ciphertext == original_ciphertext_2
    assert read_confidential_content(legacy_without_profile).civil_status == "Solo Parent"
    assert (
        StudentSupportProfile.objects.get(inventory=legacy_without_profile).solo_parent_status
        == SoloParentStatus.YES
    )

    for unchanged in (single_row, married_row, unanswered_row):
        assert StudentSupportProfile.objects.get(inventory=unchanged).solo_parent_status is None

    assert (
        StudentSupportProfile.objects.get(inventory=explicit_no_row).solo_parent_status
        == SoloParentStatus.NO
    )


@pytest.mark.django_db
def test_student_support_derives_solo_parent_indicator_from_new_field_not_civil_status():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("support-source")
    _, _, program = make_organization("SS")

    widowed_solo = make_profile_student("ss-widowed-yes@example.edu")
    make_inventory(
        student=widowed_solo,
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.WIDOWED,
        solo_parent_status=SoloParentStatus.YES,
    )

    single_not_solo = make_profile_student("ss-single-no@example.edu")
    make_inventory(
        student=single_not_solo,
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SINGLE,
        solo_parent_status=SoloParentStatus.NO,
    )

    # Legacy civil_status_category without solo_parent_status=YES does NOT trigger the indicator.
    unbackfilled_legacy = make_profile_student("ss-legacy-none@example.edu")
    item = make_inventory(
        student=unbackfilled_legacy,
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SOLO_PARENT,
        solo_parent_status=None,
    )
    StudentSupportProfile.objects.filter(inventory=item).update(
        four_ps_status=FourPsStatus.NOT_BENEFICIARY,
        indigenous_peoples_status=IndigenousPeoplesStatus.NOT_MEMBER,
        mother_life_status=ParentLifeStatus.LIVING,
        father_life_status=ParentLifeStatus.LIVING,
    )

    widowed_ctx = build_student_support_context(student=widowed_solo)
    assert [ind.code for ind in widowed_ctx.indicators] == ["SOLO_PARENT"]

    single_ctx = build_student_support_context(student=single_not_solo)
    assert [ind.code for ind in single_ctx.indicators] == []

    unbackfilled_ctx = build_student_support_context(student=unbackfilled_legacy)
    assert [ind.code for ind in unbackfilled_ctx.indicators] == []


@pytest.mark.django_db
def test_profiling_report_api_pdf_and_xlsx_include_solo_parent_after_pwd_and_handle_legacy_rows():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("report-sp")
    _, college, program_a = make_organization("RSP-A")
    program_b = Program.objects.create(college=college, code="P-RSP-B", name="Program B")

    rows_plan = [
        # Active civil statuses with explicit solo parent answers.
        (program_a, CivilStatusCategory.SINGLE, SoloParentStatus.NO),
        (program_a, CivilStatusCategory.WIDOWED, SoloParentStatus.YES),
        (program_a, CivilStatusCategory.SEPARATED, SoloParentStatus.YES),
        (program_b, CivilStatusCategory.ANNULLED, SoloParentStatus.NO),
        (program_b, CivilStatusCategory.MARRIED, SoloParentStatus.NO),
        (program_b, CivilStatusCategory.OTHER, SoloParentStatus.NO),
        # Backfilled legacy SOLO_PARENT row.
        (program_a, CivilStatusCategory.SOLO_PARENT, SoloParentStatus.YES),
        # Unbackfilled legacy row still counts as Yes (Solo Parent) and Not specified (Civil).
        (program_b, CivilStatusCategory.SOLO_PARENT, None),
        # Pre-update non-legacy row left unanswered (None) in Solo Parent Status.
        (program_b, CivilStatusCategory.SINGLE, None),
    ]
    for index, (program, civil_status, solo_status) in enumerate(rows_plan):
        make_inventory(
            student=make_profile_student(f"rsp-{index}@example.edu"),
            academic_year=year,
            revision=revision,
            program=program,
            civil_status_category=civil_status,
            solo_parent_status=solo_status,
            date_of_birth=date(2005, 1, 1 + index),
        )

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert_report_reconciles(report)

    # Section placement: immediately after physical_disadvantage.
    section_keys = list(report["sections"].keys())
    pwd_index = section_keys.index("physical_disadvantage")
    assert section_keys[pwd_index + 1] == "solo_parent_status"

    # Civil status rows: 6 active statuses + legacy Not specified, no SOLO_PARENT key.
    civil_section = report["sections"]["civil_status"]
    assert [row["key"] for row in civil_section["rows"]] == [
        "SINGLE",
        "MARRIED",
        "WIDOWED",
        "SEPARATED",
        "ANNULLED",
        "OTHER",
        LEGACY_UNSPECIFIED_KEY,
    ]
    assert report_row(civil_section, "SINGLE")["total_count"] == 2
    assert report_row(civil_section, "WIDOWED")["total_count"] == 1
    assert report_row(civil_section, "SEPARATED")["total_count"] == 1
    assert report_row(civil_section, "ANNULLED")["total_count"] == 1
    assert report_row(civil_section, LEGACY_UNSPECIFIED_KEY)["label"] == LEGACY_UNSPECIFIED_LABEL
    assert report_row(civil_section, LEGACY_UNSPECIFIED_KEY)["total_count"] == 2

    # Solo Parent Status rows: Yes (4 = 2 active + 2 legacy), No (4), Not specified (1 pre-update).
    solo_section = report["sections"]["solo_parent_status"]
    assert solo_section["label"] == "Distribution of Students based on Solo Parent Status"
    assert [row["key"] for row in solo_section["rows"]] == [
        "YES",
        "NO",
        LEGACY_UNSPECIFIED_KEY,
    ]
    assert report_row(solo_section, "YES")["label"] == "Yes"
    assert report_row(solo_section, "YES")["total_count"] == 4
    assert report_row(solo_section, "NO")["label"] == "No"
    assert report_row(solo_section, "NO")["total_count"] == 4
    assert report_row(solo_section, LEGACY_UNSPECIFIED_KEY)["label"] == LEGACY_UNSPECIFIED_LABEL
    assert report_row(solo_section, LEGACY_UNSPECIFIED_KEY)["total_count"] == 1

    # PDF places Solo Parent Status immediately after PWD Status.
    assert SECTION_ORDER[SECTION_ORDER.index("physical_disadvantage") + 1] == "solo_parent_status"
    demographics_keys = REPORT_PARTS[0][1]
    assert demographics_keys[demographics_keys.index("physical_disadvantage") + 1] == (
        "solo_parent_status"
    )
    pdf_context = build_student_profiling_print_context(report)
    pdf_tables = [
        table for part in pdf_context["student_profile"]["parts"] for table in part["tables"]
    ]
    pdf_keys = [table["key"] for table in pdf_tables]
    assert pdf_keys[pdf_keys.index("physical_disadvantage") + 1] == "solo_parent_status"
    pdf_solo = next(table for table in pdf_tables if table["key"] == "solo_parent_status")
    assert pdf_solo["title"] == "Distribution of Students by Solo Parent Status"
    assert [[cell["text"] for cell in row["cells"]] for row in pdf_solo["rows"]] == [
        ["Yes", "4", "44.44%"],
        ["No", "4", "44.44%"],
        [LEGACY_UNSPECIFIED_LABEL, "1", "11.11%"],
        ["Total", "9", "100.00%"],
    ]

    # XLSX places Solo Parent Status worksheet immediately after PWD Status.
    xlsx_keys = [spec[0] for spec in SECTION_SPECS]
    assert xlsx_keys[xlsx_keys.index("physical_disadvantage") + 1] == "solo_parent_status"
    workbook = build_student_profiling_workbook(report)
    assert workbook.sheetnames[workbook.sheetnames.index("PWD Status") + 1] == "Solo Parent Status"
    ws = workbook["Solo Parent Status"]
    assert ws.cell(row=2, column=1).value == "Yes"
    assert ws.cell(row=3, column=1).value == "No"
    assert ws.cell(row=4, column=1).value == LEGACY_UNSPECIFIED_LABEL


@pytest.mark.django_db
def test_profiling_report_omits_legacy_unspecified_row_when_no_legacy_or_unanswered_rows_exist():
    sync_policy()
    year = AcademicYear.objects.create(label="2026-2027", is_current=True)
    revision = make_revision("report-clean")
    _, _, program = make_organization("RCLEAN")

    make_inventory(
        student=make_profile_student("rclean-1@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.WIDOWED,
        solo_parent_status=SoloParentStatus.YES,
    )
    make_inventory(
        student=make_profile_student("rclean-2@example.edu"),
        academic_year=year,
        revision=revision,
        program=program,
        civil_status_category=CivilStatusCategory.SINGLE,
        solo_parent_status=SoloParentStatus.NO,
    )

    report = build_student_profiling_report(access_scope=GLOBAL_REPORT_ACCESS_SCOPE)
    assert_report_reconciles(report)
    assert LEGACY_UNSPECIFIED_KEY not in [
        row["key"] for row in report["sections"]["civil_status"]["rows"]
    ]
    assert [row["key"] for row in report["sections"]["solo_parent_status"]["rows"]] == [
        "YES",
        "NO",
    ]
