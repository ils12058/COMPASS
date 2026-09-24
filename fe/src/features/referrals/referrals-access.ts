import type { UserSummary } from "@/lib/api/generated/model";

export type ReferralAccess = {
  isOperational: boolean;
  canView: boolean;
  canManage: boolean;
  hasWorkspace: boolean;
};

export function getReferralAccess(user: UserSummary): ReferralAccess {
  const isOperational =
    user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
  const canView = isOperational && user.capabilities.includes("referrals.view");
  const canManage = isOperational && user.capabilities.includes("referrals.manage");

  return {
    isOperational,
    canView,
    canManage,
    hasWorkspace: canView || canManage,
  };
}
