type CapabilityUser = { capabilities: readonly string[] };

function hasCapability(user: CapabilityUser, capability: string): boolean {
  return user.capabilities.includes(capability);
}

export function canViewOrganization(user: CapabilityUser): boolean {
  return hasCapability(user, "organization.view");
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
    canViewOrganization(user) ||
    canManageOrganization(user) ||
    canViewAcademicYears(user) ||
    canViewInstitutionalForms(user)
  );
}
