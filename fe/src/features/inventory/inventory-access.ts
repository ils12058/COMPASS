import type { UserSummary } from "@/lib/api/generated/model";

export type InventoryAccess = {
  isStudent: boolean;
  isCounselor: boolean;
  canViewSelf: boolean;
  canManageSelf: boolean;
  canViewRoster: boolean;
  canReopen: boolean;
  isCurrentStudent: boolean;
  hasWorkspace: boolean;
};

export function getInventoryAccess(user: UserSummary): InventoryAccess {
  const isStudent = user.role === "STUDENT";
  const isCounselor = user.role === "COUNSELOR";
  const isCurrentStudent = user.student_lifecycle_status === "CURRENT";
  const canViewSelf =
    isStudent && user.capabilities.includes("inventory.view_self");
  const canManageSelf =
    isStudent &&
    isCurrentStudent &&
    user.capabilities.includes("inventory.manage_self");
  const canViewRoster =
    isCounselor && user.capabilities.includes("inventory.view");
  const canReopen =
    isCounselor && user.capabilities.includes("inventory.reopen");

  return {
    isStudent,
    isCounselor,
    canViewSelf,
    canManageSelf,
    canViewRoster,
    canReopen,
    isCurrentStudent,
    hasWorkspace: canViewSelf || canViewRoster,
  };
}
