"""Source-owned F5 projection for submitted Individual Inventory PDFs."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from compass.common.correlation import get_current_request_id
from compass.common.institutional_time import institution_date
from compass.documents.rendering import DocumentRenderError, render_document_pdf

from .confidential_content import InventoryPrivateProjection, read_inventory_private_projection
from .models import (
    EducationLevel,
    FamilyMemberKind,
    OrganizationScope,
    Sex,
    TransportationMode,
)
from .services import InventoryError, InventoryNotSubmitted, derive_age_on

logger = logging.getLogger(__name__)


class InventoryDocumentUnavailable(InventoryError):
    """The saved controlled form cannot be rendered safely by this build."""


def _date(value: date | None) -> str:
    return f"{value:%B} {value.day}, {value.year}" if value is not None else ""


def _money(value: Decimal | None) -> str:
    return f"{value:,.2f}" if value is not None else ""


def _family(member, content) -> dict[str, str]:
    if member is None:
        return {}
    return {
        "name": content.name,
        "date_of_birth": _date(content.date_of_birth),
        "place_of_birth": content.place_of_birth,
        "current_address": content.current_address,
        "permanent_address": content.permanent_address,
        "contact_number": content.contact_number,
        "email_address": content.email_address,
        "educational_attainment": content.educational_attainment,
        "occupation": content.occupation,
        "business_address": content.business_address,
        "business_telephone": content.business_telephone,
        "annual_income": _money(member.annual_income_previous_year),
        "languages_spoken": content.languages_spoken,
        "religion_raised_with": content.religion_raised_with,
        "current_religion": content.current_religion,
    }


def _sibling(row, content) -> dict[str, object]:
    return {
        "name": content.name,
        "sex": Sex(content.sex).label if content.sex else "",
        "age": content.age if content.age is not None else "",
        "educational_attainment": content.educational_attainment,
        "occupation": content.occupation,
        "is_self": row.is_self,
    }


def _education(row, content) -> dict[str, str]:
    if row is None:
        return {}
    return {
        "school": content.school_attended_address,
        "years": content.inclusive_years,
        "awards": content.awards_received,
    }


def _organization(row, content) -> dict[str, str]:
    if row is None:
        return {}
    return {"name": content.organization_name, "position": content.position_title}


def _transport(row, content) -> dict[str, str]:
    if row is None:
        return {}
    return {"frequency": content.frequency, "fare": _money(row.fare)}


def _project_row(mapper, row, private):
    return {} if row is None else mapper(row, private.children[row.pk])


def build_inventory_render_context(
    item, *, private: InventoryPrivateProjection
) -> dict[str, object]:
    """Map only source-visible F5 answers into their printed positions."""
    revision = item.form_revision
    if (
        revision.family.key != "individual_inventory"
        or revision.internal_schema_version != 1
        or revision.official_code != "CNSC-OP-GCO-01F5"
        or revision.official_revision != "0"
    ):
        raise InventoryDocumentUnavailable(
            "The saved Individual Inventory presentation version is unavailable."
        )
    if item.submitted_at is None:
        raise InventoryNotSubmitted(
            "Only a currently submitted Individual Inventory has an official PDF."
        )

    family = {row.kind: row for row in item.family_members.all()}
    siblings = list(item.siblings.all())
    organizations = list(item.organization_memberships.all())
    if len(siblings) > 12 or any(
        sum(row.scope == scope for row in organizations) > 3
        for scope in (OrganizationScope.INSIDE_SCHOOL, OrganizationScope.OUTSIDE_SCHOOL)
    ):
        raise InventoryDocumentUnavailable(
            "The saved Individual Inventory has more rows than the official form can display."
        )
    sibling_cells = [_sibling(row, private.children[row.pk]) for row in siblings] + [
        {} for _ in range(12 - len(siblings))
    ]
    education = {row.level: row for row in item.education_entries.all()}
    organization_groups = {
        scope: [
            _project_row(_organization, row, private)
            for row in sorted(
                (row for row in organizations if row.scope == scope),
                key=lambda row: row.sort_order,
            )
        ]
        for scope in (OrganizationScope.INSIDE_SCHOOL, OrganizationScope.OUTSIDE_SCHOOL)
    }
    for rows in organization_groups.values():
        rows.extend({} for _ in range(3 - len(rows)))
    transport = {row.mode: row for row in item.transportation_entries.all()}
    submitted_date = institution_date(item.submitted_at)
    form = {
        "name": item.full_name_snapshot,
        "nickname": private.root.nickname,
        "student_number": item.student_number,
        "age": derive_age_on(date_of_birth=item.date_of_birth, on_date=submitted_date)
        if item.date_of_birth
        else "",
        "date_of_birth": _date(item.date_of_birth),
        "place_of_birth": private.root.place_of_birth,
        "nationality": private.root.nationality,
        "sex": item.sex,
        "birth_order": private.root.birth_order_among_siblings,
        "civil_status": private.root.civil_status,
        "current_address": private.root.current_address,
        "permanent_address": private.root.permanent_address,
        "contact_number": private.root.contact_number,
        "email_address": private.root.email_address,
        "languages_home": private.root.languages_spoken_at_home,
        "languages_fluent": private.root.languages_most_fluent,
        "religion_birth": private.root.religion_from_birth,
        "current_religion": private.root.current_religion,
        "father": _project_row(_family, family.get(FamilyMemberKind.FATHER), private),
        "mother": _project_row(_family, family.get(FamilyMemberKind.MOTHER), private),
        "spouse": _project_row(_family, family.get(FamilyMemberKind.SPOUSE), private),
        "parent_statuses": item.parent_statuses,
        "guardian_name": private.root.guardian_name,
        "guardian_relationship": private.root.guardian_relationship,
        "guardian_address": private.root.guardian_address,
        "guardian_contact": private.root.guardian_contact_number,
        "emergency_name": private.root.emergency_contact_name,
        "emergency_contact": private.root.emergency_contact_number,
        "sibling_rows": [(sibling_cells[index], sibling_cells[index + 6]) for index in range(6)],
        "friends_school": private.root.friends_in_school,
        "friends_outside": private.root.friends_outside_school,
        "special_interest": private.root.special_interest,
        "special_skills": private.root.special_skills_talents,
        "hobbies": private.root.hobbies_recreation,
        "ambition": private.root.ambition_goal,
        "characteristics": private.root.characteristics,
        "living_arrangement": item.living_arrangement,
        "boarding_exclusive": item.boarding_exclusive,
        "landlord": private.root.boarding_landlord_name,
        "boarding_address": private.root.boarding_address,
        "people_in_place": item.present_place_people_count,
        "room_sharers": item.room_sharing_people_count,
        "accidents": private.root.accidents_experienced,
        "accidents_effect": private.root.accidents_effect,
        "operations": private.root.operations_experienced,
        "operations_effect": private.root.operations_effect,
        "immunizations": private.root.immunizations,
        "immunization_other": private.root.immunization_other,
        "height": private.root.height,
        "weight": private.root.weight,
        "physical_disadvantage": private.root.physical_disadvantage,
        "illness_this_year": private.root.illness_this_year,
        "previous_illness": private.root.previous_illness,
        "education": {
            level: _project_row(_education, education.get(level), private)
            for level in EducationLevel.values
        },
        "course": item.course_currently_enrolled,
        "major": item.major,
        "schedule_satisfied": item.schedule_satisfied,
        "schedule_why": private.root.schedule_satisfaction_reason,
        "first_choice": item.course_first_choice,
        "choice_reasons": item.course_choice_reasons,
        "choice_other": private.root.course_choice_other,
        "lowest_grades": private.root.lowest_subjects_grades,
        "highest_grades": private.root.highest_subjects_grades,
        "performing_arts": private.root.inclination_performing_arts,
        "sports": private.root.inclination_sports,
        "leadership": private.root.inclination_leadership,
        "interests": item.interests,
        "other_skills": private.root.other_skills_hobbies,
        "desired_activities": private.root.desired_extracurricular_activities,
        "reading": private.root.reading_preferences,
        "handedness": item.handedness,
        "daily_hours": [
            str(value) if value is not None else ""
            for value in (
                item.daily_hours_class,
                item.daily_hours_library,
                item.daily_hours_studying,
                item.daily_hours_rest,
                item.daily_hours_recreation,
                item.daily_hours_other,
            )
        ],
        "organizations": [
            (
                organization_groups[OrganizationScope.INSIDE_SCHOOL][index],
                organization_groups[OrganizationScope.OUTSIDE_SCHOOL][index],
            )
            for index in range(3)
        ],
        "transport": {
            mode: _project_row(_transport, transport.get(mode), private)
            for mode in TransportationMode.values
        },
        "allowance": item.ideal_monthly_allowance,
        "work_field": item.intended_work_field,
        "work_other": private.root.intended_work_other,
        "prior_counseling": private.root.prior_counseling_experience,
        "prior_counselor": private.root.prior_counselor_name,
        "prior_when": private.root.prior_counseling_when,
        "prior_where": private.root.prior_counseling_where,
        "concerns": private.root.current_concerns,
        "fears": private.root.current_fears,
        "submitted_date": _date(submitted_date),
    }
    return {
        "inventory_form": form,
        "controlled_form": {
            "official_code": revision.official_code,
            "official_revision": revision.official_revision,
        },
    }


def render_inventory_pdf(item) -> bytes:
    if item.submitted_at is None:
        raise InventoryNotSubmitted(
            "Only a currently submitted Individual Inventory has an official PDF."
        )
    private = read_inventory_private_projection(item)
    context = build_inventory_render_context(item, private=private)
    try:
        result = render_document_pdf(
            "individual_inventory", item.form_revision.internal_schema_version, context=context
        )
    except DocumentRenderError as exc:
        logger.warning(
            "Individual Inventory PDF rendering failed.",
            extra={
                "event": "inventory_pdf_render_failed",
                "request_id": get_current_request_id(),
                "error_type": type(exc).__name__,
                "error_reason": str(exc),
            },
        )
        raise InventoryDocumentUnavailable(
            "The Individual Inventory PDF is temporarily unavailable."
        ) from exc
    return result.pdf_bytes
