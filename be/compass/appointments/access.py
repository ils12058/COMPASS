"""Appointment resource-access policy and scoped queryset helpers."""

from __future__ import annotations

from enum import StrEnum

from django.db.models import Q

from compass.accounts.models import User
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.models import Service
from compass.student_academics.models import StudentAcademicProfile


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
    """Non-Head delegated, non-Counseling responsibility access only."""
    scope = resolve_operational_responsibility_scope(actor)
    if not scope.college_ids:
        return False
    return StudentAcademicProfile.objects.filter(
        student_id=student_id,
        current_college_id__in=scope.college_ids,
        current_college__is_active=True,
        current_college__campus__is_active=True,
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

    # Head Guidance has institution-wide general Guidance College visibility,
    # not institutional appointment ownership. Even explicit handled Colleges
    # and the unique-Head fallback cannot authorize someone else's appointment.
    if is_head_guidance(actor):
        return False

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

    # Mirror the single-resource Head rule before considering handled workload.
    # View-self remains a separate, provider/Student relationship capability.
    if is_head_guidance(actor):
        return queryset.filter(provider_id=actor.pk)

    allowed = Q(pk__in=[])
    if actor.role.code == "COUNSELOR":
        allowed |= Q(provider_id=actor.pk)

    scope = resolve_operational_responsibility_scope(actor)
    organizational = ~Q(service__code=COUNSELING_SERVICE_CODE)
    if scope.college_ids:
        allowed |= (
            organizational
            & Q(student__student_academic_profile__current_college_id__in=scope.college_ids)
            & Q(student__student_academic_profile__current_college__is_active=True)
            & Q(student__student_academic_profile__current_college__campus__is_active=True)
        )

    return queryset.filter(allowed).distinct()
