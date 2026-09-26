type CapabilityUser = { capabilities: readonly string[] };

// Privacy Governance follows effective capabilities, never the DPO designation
// itself (ADR-045, ADR-061). The backend still authorizes every operation.
export function canViewPrivacyGovernance(user: CapabilityUser): boolean {
  return user.capabilities.includes("privacy_governance.view");
}

export function canManagePrivacyGovernance(user: CapabilityUser): boolean {
  return user.capabilities.includes("privacy_governance.manage");
}

export function hasPrivacyGovernanceWorkspace(user: CapabilityUser): boolean {
  return canViewPrivacyGovernance(user) || canManagePrivacyGovernance(user);
}
