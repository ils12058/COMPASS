"""Institutional Faculty affiliation writes; callers take the catalog gate first."""

from uuid import UUID

from django.utils import timezone

from compass.account_management.services import (
    InvalidManagementInput,
    OrganizationRelationshipConflict,
    SelfTargetForbidden,
    _admin_mutation,
)
from compass.audit.actions import ACCOUNT_FACULTY_AFFILIATION_CHANGED
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.models import College, FacultyAffiliation


def validate_faculty_college(*, role, college_id):
    if college_id is None:
        return None
    if role != "FACULTY":
        raise InvalidManagementInput("Only Faculty accounts accept a Faculty home College.")
    try:
        college_id = UUID(str(college_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidManagementInput("Faculty home College must be a catalog UUID.") from exc
    college = College.objects.select_related("campus").filter(pk=college_id).first()
    if college is None or not college.is_active or not college.campus.is_active:
        raise InvalidManagementInput("Select an active College beneath an active Campus.")
    return college


def write_faculty_affiliation(*, target, actor, college, basis, context):
    """Write under caller's locked account; one audit event per actual change."""
    current = FacultyAffiliation.objects.select_for_update().filter(faculty=target).first()
    college_id = college.pk if college else None
    if current is None and college is None:
        return None
    if current is not None and current.college_id == college_id:
        return current
    previous_id = current.college_id if current else None
    if current is None:
        current = FacultyAffiliation(faculty=target)
    else:
        current.resource_version += 1
    current.college = college
    current.assigned_by = actor
    current.assigned_at = timezone.now()
    current.basis = basis
    current.save()
    record_event(
        context=context,
        action=ACCOUNT_FACULTY_AFFILIATION_CHANGED,
        outcome=AuditOutcome.SUCCESS,
        target_type="accounts.user",
        target_id=target.pk,
        metadata={
            "from_college_id": str(previous_id) if previous_id else None,
            "to_college_id": str(college_id) if college_id else None,
            "resource_version": current.resource_version,
            "basis": basis,
        },
    )
    return current


def set_faculty_affiliation(
    *,
    actor,
    actor_session,
    target_id,
    college_id,
    expected_resource_version,
    basis,
    context,
):
    if not isinstance(basis, str) or not basis.strip() or len(basis.strip()) > 500:
        raise InvalidManagementInput(
            "An institutional assignment basis (1–500 characters) is required."
        )
    if type(expected_resource_version) is not int or expected_resource_version < 0:
        raise InvalidManagementInput("An expected affiliation version is required.")
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (locked_actor, target):
        if target.pk == locked_actor.pk:
            raise SelfTargetForbidden("Faculty affiliation must be institutionally assigned.")
        if target.role.code != "FACULTY":
            raise InvalidManagementInput("The account must currently have the Faculty role.")
        current = FacultyAffiliation.objects.filter(faculty=target).first()
        version = current.resource_version if current else 0
        if version != expected_resource_version:
            raise OrganizationRelationshipConflict(
                "Faculty affiliation changed. Reload before reviewing again."
            )
        college = validate_faculty_college(role=target.role.code, college_id=college_id)
        write_faculty_affiliation(
            target=target,
            actor=locked_actor,
            college=college,
            basis=basis.strip(),
            context=context,
        )
        return target
