"""Appointment resource-access policy and scoped queryset helpers."""

from __future__ import annotations

from enum import StrEnum

from django.db.models import Q

from compass.accounts.models import User
from compass.organization.access_scope import resolve_organizational_access_scope
from compass.organization.models import StudentAffiliation
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import Service


class AppointmentAccessPolicy(StrEnum):
    ORGANIZATIONAL = "ORGANIZATIONAL"
    RELATIONSHIP_ONLY = "RELATIONSHIP_ONLY"


def appointment_access_policy_for_service(service: Service) -> AppointmentAccessPolicy:
    if service.code == COUNSELING_SERVICE_CODE:
        return AppointmentAccessPolicy.RELATIONSHIP_ONLY
    return AppointmentAccessPolicy.ORGANIZATIONAL


def _is_provider_relationship(actor: User, appointment) -> bool:
    return (
        bool(getattr(actor, "pk", None))
        and actor.is_active
        and actor.role.code == "COUNSELOR"
        and appointment.provider_id == actor.pk
    )


def _student_in_organizational_scope(actor: User, student_id) -> bool:
    scope = resolve_organizational_access_scope(actor)
    if scope.institution_wide:
        return True
    if not scope.college_ids:
        return False
    return StudentAffiliation.objects.filter(
        student_id=student_id,
        college_id__in=scope.college_ids,
        college__is_active=True,
        college__campus__is_active=True,
    ).exists()


def appointment_management_access_allowed(actor: User, appointment) -> bool:
    """Check Appointment management resource scope after the capability boundary."""

    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability("appointments.manage")
    ):
        return False

    if _is_provider_relationship(actor, appointment):
        return True

    if (
        appointment_access_policy_for_service(appointment.service)
        == AppointmentAccessPolicy.RELATIONSHIP_ONLY
    ):
        return False

    return _student_in_organizational_scope(actor, appointment.student_id)


def scope_managed_appointments(queryset, actor: User):
    """Scope the managed Appointment surface before caller-supplied filters are applied."""

    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability("appointments.manage")
    ):
        return queryset.none()

    allowed = Q(pk__in=[])
    if actor.role.code == "COUNSELOR":
        allowed |= Q(provider_id=actor.pk)

    scope = resolve_organizational_access_scope(actor)
    organizational = ~Q(service__code=COUNSELING_SERVICE_CODE)
    if scope.institution_wide:
        allowed |= organizational
    elif scope.college_ids:
        allowed |= (
            organizational
            & Q(student__organization_student_affiliation__college_id__in=scope.college_ids)
            & Q(student__organization_student_affiliation__college__is_active=True)
            & Q(student__organization_student_affiliation__college__campus__is_active=True)
        )

    return queryset.filter(allowed).distinct()
