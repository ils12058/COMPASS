import type { CapabilityCode } from "@/lib/api/generated/model";

type CapabilityUser = { capabilities: readonly CapabilityCode[] };

function hasCapability(user: CapabilityUser, capability: CapabilityCode): boolean {
  return user.capabilities.includes(capability);
}

// Reference read of Campus, College, and Program structure for selectors and
// other workflows. It does not grant the Organization workspace (ADR-059).
export function canViewOrganizationStructure(user: CapabilityUser): boolean {
  return hasCapability(user, "organization.structure.view");
}

export function canManageOrganization(user: CapabilityUser): boolean {
  return hasCapability(user, "organization.manage");
}

export function canViewAcademicYears(user: CapabilityUser): boolean {
  return hasCapability(user, "academic_years.view");
}

export function canManageAcademicYears(user: CapabilityUser): boolean {
  return hasCapability(user, "academic_years.manage");
}

export function canViewInstitutionalForms(user: CapabilityUser): boolean {
  return hasCapability(user, "institutional_forms.view");
}

export function canManageInstitutionalForms(user: CapabilityUser): boolean {
  return hasCapability(user, "institutional_forms.manage");
}

export function hasInstitutionWorkspace(user: CapabilityUser): boolean {
  return (
    canManageOrganization(user) ||
    canViewAcademicYears(user) ||
    canViewInstitutionalForms(user)
  );
}
