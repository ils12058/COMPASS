import type { UserSummary } from "@/lib/api/generated/model";

export type CallSlipAccess = {
  isStudent: boolean;
  isOperational: boolean;
  canViewSelf: boolean;
  canViewOperational: boolean;
  canManageOperational: boolean;
  hasWorkspace: boolean;
};

export function getCallSlipAccess(user: UserSummary): CallSlipAccess {
  const isStudent = user.role === "STUDENT";
  const isOperational =
    user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
  const canViewSelf =
    isStudent && user.capabilities.includes("call_slips.view_self");
  const canViewOperational =
    isOperational && user.capabilities.includes("call_slips.view");
  const canManageOperational =
    isOperational && user.capabilities.includes("call_slips.manage");

  return {
    isStudent,
    isOperational,
    canViewSelf,
    canViewOperational,
    canManageOperational,
    hasWorkspace: canViewSelf || canViewOperational || canManageOperational,
  };
}
