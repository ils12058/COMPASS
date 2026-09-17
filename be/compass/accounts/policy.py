"""Version-controlled identity policy synchronized into PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class DesignationDefinition:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    code: str
    name: str
    description: str


ROLE_DEFINITIONS = (
    RoleDefinition(
        code="IT_ADMIN",
        name="IT Administrator",
        description="Technical administrator for COMPASS account and platform operations.",
    ),
    RoleDefinition(
        code="COUNSELOR",
        name="Counselor",
        description="Operational counseling role.",
    ),
    RoleDefinition(
        code="GUIDANCE_SERVICES_STAFF",
        name="Guidance Services Staff",
        description="Operational guidance services staff role.",
    ),
    RoleDefinition(
        code="STUDENT",
        name="Student",
        description="Student account role.",
    ),
)

DESIGNATION_DEFINITIONS = (
    DesignationDefinition(
        code="HEAD_GUIDANCE_COUNSELOR",
        name="Head Guidance Counselor",
        description="Institutional designation for the head guidance counselor appointment.",
    ),
    DesignationDefinition(
        code="DPO",
        name="Data Protection Officer",
        description="Institutional designation for the data protection officer appointment.",
    ),
)

CAPABILITY_DEFINITIONS = (
    CapabilityDefinition(
        code="accounts.view",
        name="View account identity",
        description="View account identity fields through an authorized COMPASS workflow.",
    ),
    CapabilityDefinition(
        code="accounts.manage",
        name="Manage accounts",
        description="Manage account identity and account status through an authorized workflow.",
    ),
    CapabilityDefinition(
        code="organization.view",
        name="View organization",
        description="View safe organizational structure through an authorized COMPASS workflow.",
    ),
    CapabilityDefinition(
        code="organization.manage",
        name="Manage organization",
        description="Manage organizational routing and responsibility configuration.",
    ),
    CapabilityDefinition(
        code="services.view",
        name="View service catalog",
        description="View the active Guidance and Counseling Office service catalog.",
    ),
    CapabilityDefinition(
        code="services.manage",
        name="Manage service catalog",
        description="Manage Guidance and Counseling Office service catalog configuration.",
    ),
    CapabilityDefinition(
        code="availability.view",
        name="View availability",
        description="View effective provider Availability through authorized workflows.",
    ),
    CapabilityDefinition(
        code="availability.manage",
        name="Manage availability",
        description="Administratively manage Office and provider Availability configuration.",
    ),
    CapabilityDefinition(
        code="availability.manage_self",
        name="Manage own availability",
        description="Manage the authenticated Counselor's own provider Availability.",
    ),
    CapabilityDefinition(
        code="appointments.view_self",
        name="View own appointments",
        description="View Appointments assigned to the authenticated Student or Provider.",
    ),
    CapabilityDefinition(
        code="appointments.manage_self",
        name="Manage own appointments",
        description="Create and cancel the authenticated Student's own Appointment reservations.",
    ),
    CapabilityDefinition(
        code="appointments.manage",
        name="Manage appointments",
        description="Manage Guidance-office Appointment reservations operationally.",
    ),
    CapabilityDefinition(
        code="counseling.view_assigned",
        name="View assigned counseling encounters",
        description="View Counseling Encounters assigned to the authenticated Counselor.",
    ),
    CapabilityDefinition(
        code="counseling.manage_assigned",
        name="Manage assigned counseling encounters",
        description=(
            "Create and correct Counseling Encounters assigned to the authenticated Counselor."
        ),
    ),
)

# Account identity is visible to operational actors through future, scoped workflows. Account
# management remains an IT_ADMIN responsibility. Scope and sensitive profile data are separate
# concerns and are intentionally not implied by these grants.
ROLE_CAPABILITY_GRANTS: dict[str, frozenset[str]] = {
    "IT_ADMIN": frozenset(
        {
            "accounts.view",
            "accounts.manage",
            "organization.view",
            "organization.manage",
            "services.view",
            "services.manage",
            "availability.view",
            "availability.manage",
        }
    ),
    "COUNSELOR": frozenset(
        {
            "accounts.view",
            "organization.view",
            "services.view",
            "availability.view",
            "availability.manage_self",
            "appointments.view_self",
            "counseling.view_assigned",
            "counseling.manage_assigned",
        }
    ),
    "GUIDANCE_SERVICES_STAFF": frozenset(
        {
            "accounts.view",
            "organization.view",
            "services.view",
            "availability.view",
            "appointments.view_self",
        }
    ),
    "STUDENT": frozenset(
        {
            "accounts.view",
            "organization.view",
            "services.view",
            "availability.view",
            "appointments.view_self",
            "appointments.manage_self",
        }
    ),
}

# Designations add only the explicitly confirmed domain authorities below. Head Guidance remains
# a Counselor for confidential Counseling records and receives no blanket Counseling-content grant.
DESIGNATION_CAPABILITY_GRANTS: dict[str, frozenset[str]] = {
    "HEAD_GUIDANCE_COUNSELOR": frozenset(
        {
            "organization.manage",
            "services.manage",
            "availability.manage",
            "appointments.manage",
        }
    ),
    "DPO": frozenset(),
}

ROLE_CODES = frozenset(definition.code for definition in ROLE_DEFINITIONS)
DESIGNATION_CODES = frozenset(definition.code for definition in DESIGNATION_DEFINITIONS)
CAPABILITY_CODES = frozenset(definition.code for definition in CAPABILITY_DEFINITIONS)


def _validate_policy() -> None:
    if set(ROLE_CAPABILITY_GRANTS) != ROLE_CODES:
        raise RuntimeError("role capability policy must define every canonical role exactly once")
    if set(DESIGNATION_CAPABILITY_GRANTS) != DESIGNATION_CODES:
        raise RuntimeError(
            "designation capability policy must define every canonical designation exactly once"
        )
    for role_code, capability_codes in ROLE_CAPABILITY_GRANTS.items():
        if role_code not in ROLE_CODES or not capability_codes <= CAPABILITY_CODES:
            raise RuntimeError(f"invalid role capability policy for {role_code}")
    for designation_code, capability_codes in DESIGNATION_CAPABILITY_GRANTS.items():
        if designation_code not in DESIGNATION_CODES or not capability_codes <= CAPABILITY_CODES:
            raise RuntimeError(f"invalid designation capability policy for {designation_code}")


_validate_policy()
