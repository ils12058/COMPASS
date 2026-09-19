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
    RoleDefinition(
        code="INSTITUTIONAL_OFFICER",
        name="Institutional Officer",
        description=(
            "Neutral institutional account role for university-level officers without an "
            "operational GCO or platform-administration identity."
        ),
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
        code="institutional_designations.manage",
        name="Manage institutional designations",
        description=(
            "Record or remove high-trust institutional appointments in COMPASS through an "
            "authorized account-management workflow."
        ),
    ),
    CapabilityDefinition(
        code="platform_operations.view",
        name="View platform operations",
        description=(
            "View safe COMPASS platform health, configuration diagnostics, and operator guidance."
        ),
    ),
    CapabilityDefinition(
        code="platform_operations.manage",
        name="Manage platform operations",
        description=(
            "Manage controlled COMPASS runtime operations such as Maintenance Mode and eligible "
            "delivery recovery actions."
        ),
    ),
    CapabilityDefinition(
        code="privacy_governance.view",
        name="View privacy governance",
        description=(
            "View COMPASS privacy-governance records and curated privacy/security oversight "
            "activity."
        ),
    ),
    CapabilityDefinition(
        code="privacy_governance.manage",
        name="Manage privacy governance",
        description=(
            "Manage COMPASS privacy-governance records, reviews, and privacy incident "
            "documentation."
        ),
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
        code="academic_years.view",
        name="View academic years",
        description="View institution-wide Academic Year configuration.",
    ),
    CapabilityDefinition(
        code="academic_years.manage",
        name="Manage academic years",
        description="Create and select the institution-wide current Academic Year.",
    ),
    CapabilityDefinition(
        code="institutional_forms.view",
        name="View institutional form metadata",
        description="View recorded QMS-issued institutional Form Family and Revision metadata.",
    ),
    CapabilityDefinition(
        code="institutional_forms.manage",
        name="Manage institutional form metadata",
        description="Register and activate QMS-issued institutional Form Revision metadata.",
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
    CapabilityDefinition(
        code="shared_summaries.view_self",
        name="View own shared counseling summaries",
        description="View published Counseling Shared Summaries belonging to the Student.",
    ),
    CapabilityDefinition(
        code="shared_summaries.view_assigned",
        name="View assigned shared counseling summaries",
        description="View Shared Summaries for Counseling Encounters assigned to the Counselor.",
    ),
    CapabilityDefinition(
        code="shared_summaries.manage_assigned",
        name="Manage assigned shared counseling summaries",
        description="Draft and publish Shared Summaries for assigned Counseling Encounters.",
    ),
    CapabilityDefinition(
        code="inventory.view_self",
        name="View own individual inventory",
        description="View the authenticated Student's own annual Individual Inventory records.",
    ),
    CapabilityDefinition(
        code="inventory.manage_self",
        name="Manage own individual inventory",
        description="Create, edit, and submit the authenticated Student's current Inventory.",
    ),
    CapabilityDefinition(
        code="student_support.view",
        name="View Student Support context",
        description=(
            "View privacy-minimized Student Support indicators within authorized Guidance scope."
        ),
    ),
    CapabilityDefinition(
        code="reports.view",
        name="View aggregate reports",
        description="View privacy-bounded aggregate Guidance and Counseling Office reports.",
    ),
    CapabilityDefinition(
        code="exit_interviews.view_self",
        name="View own Exit Interviews",
        description="View the authenticated Student's own Exit Interview records.",
    ),
    CapabilityDefinition(
        code="exit_interviews.manage_self",
        name="Manage own Exit Interview",
        description="Create, edit, and submit the authenticated Student's Exit Interview.",
    ),
    CapabilityDefinition(
        code="exit_interviews.view",
        name="View Exit Interviews",
        description="View identifiable Exit Interview records for Head Guidance oversight.",
    ),
    CapabilityDefinition(
        code="exit_interviews.reopen",
        name="Reopen Exit Interviews",
        description="Reopen a submitted Exit Interview for controlled Student correction.",
    ),
    CapabilityDefinition(
        code="routine_interviews.view_self",
        name="View own routine interviews",
        description="View the authenticated Student's own Routine Interview records.",
    ),
    CapabilityDefinition(
        code="routine_interviews.manage_self",
        name="Manage own routine interview intake",
        description=(
            "Create, edit, and submit the authenticated Student's Routine Interview Intake."
        ),
    ),
    CapabilityDefinition(
        code="routine_interviews.view_assigned",
        name="View assigned routine interviews",
        description="View Routine Interviews assigned to the authenticated Counselor.",
    ),
    CapabilityDefinition(
        code="routine_interviews.manage_assigned",
        name="Manage assigned routine interviews",
        description="Create direct Routine Interviews and manage assigned Counselor Evaluations.",
    ),
    CapabilityDefinition(
        code="referrals.view",
        name="View scoped referrals",
        description=(
            "View Referral records within the authenticated Guidance actor's resource scope."
        ),
    ),
    CapabilityDefinition(
        code="referrals.manage",
        name="Manage scoped referrals",
        description=(
            "Create and manage Referral records within the Guidance actor's resource scope."
        ),
    ),
    CapabilityDefinition(
        code="call_slips.view",
        name="View scoped Call Slips",
        description=(
            "View Call Slip records within the authenticated Guidance actor's resource scope."
        ),
    ),
    CapabilityDefinition(
        code="call_slips.manage",
        name="Manage scoped Call Slips",
        description=(
            "Create and complete Call Slip records within the Guidance actor's resource scope."
        ),
    ),
    CapabilityDefinition(
        code="call_slips.view_self",
        name="View own Call Slips",
        description="View the authenticated Student's own Call Slip records.",
    ),
    CapabilityDefinition(
        code="good_moral.view_self",
        name="View own Good Moral requests",
        description=(
            "View the authenticated Student's own Good Moral requests and issued certificates."
        ),
    ),
    CapabilityDefinition(
        code="good_moral.request_self",
        name="Request own Good Moral certificate",
        description="Initiate an eligible Good Moral request for the authenticated Student.",
    ),
    CapabilityDefinition(
        code="good_moral.view",
        name="View Good Moral requests",
        description="View identifiable Good Moral requests in the GCO operational queue.",
    ),
    CapabilityDefinition(
        code="good_moral.manage",
        name="Manage Good Moral requests",
        description="Correct certificate-local Good Moral request facts before issuance.",
    ),
    CapabilityDefinition(
        code="good_moral.issue",
        name="Issue Good Moral certificates",
        description="Issue source-controlled Good Moral certificates as an authorized Counselor.",
    ),
    CapabilityDefinition(
        code="feedback.submit_customer_feedback",
        name="Submit Customer Feedback",
        description="Submit the authenticated Student's Customer Feedback Form response.",
    ),
    CapabilityDefinition(
        code="feedback.view_customer_feedback",
        name="View Customer Feedback",
        description="View identifiable Customer Feedback responses for Head Guidance oversight.",
    ),
    CapabilityDefinition(
        code="feedback.submit_csm",
        name="Submit Client Satisfaction Measurement",
        description="Submit the authenticated Student's Client Satisfaction Measurement response.",
    ),
    CapabilityDefinition(
        code="feedback.view_csm",
        name="View Client Satisfaction Measurement",
        description=(
            "View raw Client Satisfaction Measurement responses for Head Guidance oversight."
        ),
    ),
    CapabilityDefinition(
        code="graduate_tracer.view_self",
        name="View own Graduate Tracer response",
        description="View the authenticated Student's own Graduate Tracer response.",
    ),
    CapabilityDefinition(
        code="graduate_tracer.manage_self",
        name="Manage own Graduate Tracer response",
        description=(
            "Create, edit, and submit the eligible Graduate's own Graduate Tracer response."
        ),
    ),
    CapabilityDefinition(
        code="graduate_tracer.view",
        name="View Graduate Tracer responses",
        description="View submitted Graduate Tracer responses for Head Guidance oversight.",
    ),
    CapabilityDefinition(
        code="document_branding.view",
        name="View document branding",
        description="View the approved institutional and GCO document identity configuration.",
    ),
    CapabilityDefinition(
        code="document_branding.manage",
        name="Manage document branding",
        description="Manage the approved institutional and GCO document identity configuration.",
    ),
    CapabilityDefinition(
        code="ecounseling.view_self",
        name="View own E-Counseling workspace",
        description="View the authenticated Student's own eligible E-Counseling workspace.",
    ),
    CapabilityDefinition(
        code="ecounseling.join_self",
        name="Join own E-Counseling session",
        description="Receive a short-lived join credential for the Student's own eligible session.",
    ),
    CapabilityDefinition(
        code="ecounseling.consent_self",
        name="Decide own E-Counseling media consent",
        description=(
            "View, decide, and withdraw the authenticated Student's session-specific media consent."
        ),
    ),
    CapabilityDefinition(
        code="ecounseling.view_assigned",
        name="View assigned E-Counseling workspace",
        description="View E-Counseling workspaces assigned to the authenticated Counselor.",
    ),
    CapabilityDefinition(
        code="ecounseling.join_assigned",
        name="Join assigned E-Counseling session",
        description="Receive a short-lived join credential for the Counselor's assigned session.",
    ),
    CapabilityDefinition(
        code="ecounseling.manage_media_assigned",
        name="Manage assigned E-Counseling media",
        description=(
            "Request consent and control provider media capture for assigned E-Counseling sessions."
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
            "institutional_designations.manage",
            "platform_operations.view",
            "platform_operations.manage",
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
            "student_support.view",
            "shared_summaries.view_assigned",
            "shared_summaries.manage_assigned",
            "routine_interviews.view_assigned",
            "routine_interviews.manage_assigned",
            "referrals.view",
            "referrals.manage",
            "call_slips.view",
            "call_slips.manage",
            "good_moral.view",
            "good_moral.manage",
            "good_moral.issue",
            "ecounseling.view_assigned",
            "ecounseling.join_assigned",
            "ecounseling.manage_media_assigned",
        }
    ),
    "GUIDANCE_SERVICES_STAFF": frozenset(
        {
            "accounts.view",
            "organization.view",
            "services.view",
            "availability.view",
            "appointments.view_self",
            "referrals.view",
            "referrals.manage",
            "call_slips.view",
            "call_slips.manage",
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
            "inventory.view_self",
            "inventory.manage_self",
            "exit_interviews.view_self",
            "exit_interviews.manage_self",
            "routine_interviews.view_self",
            "routine_interviews.manage_self",
            "ecounseling.view_self",
            "ecounseling.join_self",
            "ecounseling.consent_self",
            "shared_summaries.view_self",
            "call_slips.view_self",
            "good_moral.view_self",
            "good_moral.request_self",
            "feedback.submit_customer_feedback",
            "feedback.submit_csm",
            "graduate_tracer.view_self",
            "graduate_tracer.manage_self",
        }
    ),
    "INSTITUTIONAL_OFFICER": frozenset(),
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
            "academic_years.view",
            "academic_years.manage",
            "institutional_forms.view",
            "institutional_forms.manage",
            "document_branding.view",
            "document_branding.manage",
            "exit_interviews.view",
            "exit_interviews.reopen",
            "feedback.view_customer_feedback",
            "feedback.view_csm",
            "graduate_tracer.view",
            "reports.view",
        }
    ),
    "DPO": frozenset(
        {
            "privacy_governance.view",
            "privacy_governance.manage",
        }
    ),
}

DESIGNATION_ROLE_COMPATIBILITY: dict[str, frozenset[str]] = {
    "HEAD_GUIDANCE_COUNSELOR": frozenset({"COUNSELOR"}),
    "DPO": frozenset({"INSTITUTIONAL_OFFICER"}),
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
    if set(DESIGNATION_ROLE_COMPATIBILITY) != DESIGNATION_CODES:
        raise RuntimeError(
            "designation compatibility policy must define every canonical designation exactly once"
        )
    for designation_code, capability_codes in DESIGNATION_CAPABILITY_GRANTS.items():
        if designation_code not in DESIGNATION_CODES or not capability_codes <= CAPABILITY_CODES:
            raise RuntimeError(f"invalid designation capability policy for {designation_code}")
    for designation_code, role_codes in DESIGNATION_ROLE_COMPATIBILITY.items():
        if designation_code not in DESIGNATION_CODES or not role_codes:
            raise RuntimeError(f"invalid designation compatibility policy for {designation_code}")
        if not role_codes <= ROLE_CODES:
            raise RuntimeError(
                f"designation compatibility references unknown role for {designation_code}"
            )


def designation_role_compatible(*, designation_code: str, role_code: str) -> bool:
    if designation_code not in DESIGNATION_CODES or role_code not in ROLE_CODES:
        return False
    allowed_roles = DESIGNATION_ROLE_COMPATIBILITY.get(designation_code)
    return allowed_roles is not None and role_code in allowed_roles


_validate_policy()
