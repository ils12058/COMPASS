"""Allowlisted read-only Faculty home affiliation, shared by managed/self views."""

from datetime import datetime
from uuid import UUID

from ninja import Schema

from compass.organization.models import FacultyAffiliation


class FacultyAffiliationResponse(Schema):
    college_id: UUID | None
    college_name: str | None
    campus_id: UUID | None
    campus_name: str | None
    active: bool
    resource_version: int
    assigned_at: datetime
    assigned_by_id: UUID | None


def faculty_affiliation_projection(user):
    if user.role.code != "FACULTY":
        return None
    affiliation = (
        FacultyAffiliation.objects.select_related("college__campus")
        .filter(faculty_id=user.pk)
        .first()
    )
    if affiliation is None:
        return None
    college = affiliation.college
    return {
        "college_id": affiliation.college_id,
        "college_name": college.name if college else None,
        "campus_id": college.campus_id if college else None,
        "campus_name": college.campus.name if college else None,
        "active": bool(
            user.is_active and college and college.is_active and college.campus.is_active
        ),
        "resource_version": affiliation.resource_version,
        "assigned_at": affiliation.assigned_at,
        "assigned_by_id": affiliation.assigned_by_id,
    }
