import type { CapabilityCode } from "@/lib/api/generated/model";

type CapabilityUser = { capabilities: readonly CapabilityCode[] };

// Independent administrative capabilities; the backend authorizes every operation.
export function canViewPrivacyNotices(user: CapabilityUser): boolean {
  return user.capabilities.includes("privacy_governance.notices.view");
}

export function canManagePrivacyNotices(user: CapabilityUser): boolean {
  return canViewPrivacyNotices(user) && user.capabilities.includes("privacy_governance.notices.manage");
}

export function canViewPrivacyActivity(user: CapabilityUser): boolean {
  return user.capabilities.includes("privacy_governance.activity.view");
}

export function canExportPrivacyActivity(user: CapabilityUser): boolean {
  return canViewPrivacyActivity(user) && user.capabilities.includes("privacy_governance.activity.export");
}

export function hasPrivacyGovernanceWorkspace(user: CapabilityUser): boolean {
  return canViewPrivacyNotices(user) || canViewPrivacyActivity(user);
}
