"""Source-owned F5 projection for submitted Individual Inventory PDFs."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from compass.common.correlation import get_current_request_id
from compass.documents.rendering import DocumentRenderError, render_document_pdf

from .models import (
    EducationLevel,
    FamilyMemberKind,
    OrganizationScope,
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


def _family(member) -> dict[str, str]:
    if member is None:
        return {}
    return {
        "name": member.name,
        "date_of_birth": _date(member.date_of_birth),
        "place_of_birth": member.place_of_birth,
        "current_address": member.current_address,
        "permanent_address": member.permanent_address,
        "contact_number": member.contact_number,
        "email_address": member.email_address,
        "educational_attainment": member.educational_attainment,
        "occupation": member.occupation,
        "business_address": member.business_address,
        "business_telephone": member.business_telephone,
        "annual_income": _money(member.annual_income_previous_year),
        "languages_spoken": member.languages_spoken,
        "religion_raised_with": member.religion_raised_with,
        "current_religion": member.current_religion,
    }


def _sibling(row) -> dict[str, object]:
    return {
        "name": row.name,
        "sex": row.get_sex_display() if row.sex else "",
        "age": row.age if row.age is not None else "",
        "educational_attainment": row.educational_attainment,
        "occupation": row.occupation,
        "is_self": row.is_self,
    }


def _education(row) -> dict[str, str]:
    if row is None:
        return {}
    return {
        "school": row.school_attended_address,
        "years": row.inclusive_years,
        "awards": row.awards_received,
    }


def _organization(row) -> dict[str, str]:
    if row is None:
        return {}
    return {"name": row.organization_name, "position": row.position_title}


def _transport(row) -> dict[str, str]:
    if row is None:
        return {}
    return {"frequency": row.frequency, "fare": _money(row.fare)}


def build_inventory_render_context(item) -> dict[str, object]:
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
    sibling_cells = [_sibling(row) for row in siblings] + [{} for _ in range(12 - len(siblings))]
    education = {row.level: row for row in item.education_entries.all()}
    organization_groups = {
        scope: [
            _organization(row)
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
    submitted_date = item.submitted_at.date()
    form = {
        "name": item.full_name_snapshot,
        "nickname": item.nickname,
        "student_number": item.student_number,
        "age": derive_age_on(date_of_birth=item.date_of_birth, on_date=submitted_date)
        if item.date_of_birth
        else "",
        "date_of_birth": _date(item.date_of_birth),
        "place_of_birth": item.place_of_birth,
        "nationality": item.nationality,
        "sex": item.sex,
        "birth_order": item.birth_order_among_siblings,
        "civil_status": item.civil_status,
        "current_address": item.current_address,
        "permanent_address": item.permanent_address,
        "contact_number": item.contact_number,
        "email_address": item.email_address,
        "languages_home": item.languages_spoken_at_home,
        "languages_fluent": item.languages_most_fluent,
        "religion_birth": item.religion_from_birth,
        "current_religion": item.current_religion,
        "father": _family(family.get(FamilyMemberKind.FATHER)),
        "mother": _family(family.get(FamilyMemberKind.MOTHER)),
        "spouse": _family(family.get(FamilyMemberKind.SPOUSE)),
        "parent_statuses": item.parent_statuses,
        "guardian_name": item.guardian_name,
        "guardian_relationship": item.guardian_relationship,
        "guardian_address": item.guardian_address,
        "guardian_contact": item.guardian_contact_number,
        "emergency_name": item.emergency_contact_name,
        "emergency_contact": item.emergency_contact_number,
        "sibling_rows": [(sibling_cells[index], sibling_cells[index + 6]) for index in range(6)],
        "friends_school": item.friends_in_school,
        "friends_outside": item.friends_outside_school,
        "special_interest": item.special_interest,
        "special_skills": item.special_skills_talents,
        "hobbies": item.hobbies_recreation,
        "ambition": item.ambition_goal,
        "characteristics": item.characteristics,
        "living_arrangement": item.living_arrangement,
        "boarding_exclusive": item.boarding_exclusive,
        "landlord": item.boarding_landlord_name,
        "boarding_address": item.boarding_address,
        "people_in_place": item.present_place_people_count,
        "room_sharers": item.room_sharing_people_count,
        "accidents": item.accidents_experienced,
        "accidents_effect": item.accidents_effect,
        "operations": item.operations_experienced,
        "operations_effect": item.operations_effect,
        "immunizations": item.immunizations,
        "immunization_other": item.immunization_other,
        "height": item.height,
        "weight": item.weight,
        "physical_disadvantage": item.physical_disadvantage,
        "illness_this_year": item.illness_this_year,
        "previous_illness": item.previous_illness,
        "education": {level: _education(education.get(level)) for level in EducationLevel.values},
        "course": item.course_currently_enrolled,
        "major": item.major,
        "schedule_satisfied": item.schedule_satisfied,
        "schedule_why": item.schedule_satisfaction_reason,
        "first_choice": item.course_first_choice,
        "choice_reasons": item.course_choice_reasons,
        "choice_other": item.course_choice_other,
        "lowest_grades": item.lowest_subjects_grades,
        "highest_grades": item.highest_subjects_grades,
        "performing_arts": item.inclination_performing_arts,
        "sports": item.inclination_sports,
        "leadership": item.inclination_leadership,
        "interests": item.interests,
        "other_skills": item.other_skills_hobbies,
        "desired_activities": item.desired_extracurricular_activities,
        "reading": item.reading_preferences,
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
        "transport": {mode: _transport(transport.get(mode)) for mode in TransportationMode.values},
        "allowance": item.ideal_monthly_allowance,
        "work_field": item.intended_work_field,
        "work_other": item.intended_work_other,
        "prior_counseling": item.prior_counseling_experience,
        "prior_counselor": item.prior_counselor_name,
        "prior_when": item.prior_counseling_when,
        "prior_where": item.prior_counseling_where,
        "concerns": item.current_concerns,
        "fears": item.current_fears,
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
    context = build_inventory_render_context(item)
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
