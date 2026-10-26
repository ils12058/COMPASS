import type { CapabilityCode, RoleCode } from "@/lib/api/generated/model";

type CapabilityUser = { capabilities: readonly CapabilityCode[]; role?: RoleCode };

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

function isCatalogStaff(user: CapabilityUser): boolean {
  return user.role === "IT_ADMIN" || user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
}

export function canManageOrganizationCatalog(user: CapabilityUser): boolean {
  return isCatalogStaff(user) && canViewOrganizationStructure(user) && hasCapability(user, "organization.catalog.manage");
}

// Reference access alone never gives Students an administrative workspace.
export function canEnterOrganization(user: CapabilityUser): boolean {
  return canManageOrganization(user) || (isCatalogStaff(user) && canViewOrganizationStructure(user));
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

export function hasInstitutionWorkspace(user: CapabilityUser): boolean {
  return (
    canEnterOrganization(user) ||
    canViewAcademicYears(user) ||
    canViewInstitutionalForms(user)
  );
}
