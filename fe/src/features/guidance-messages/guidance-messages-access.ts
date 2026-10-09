import type { UserSummary } from "@/lib/api/generated/model";

// Presentation only (ADR-102). The API decides every thread: College scope, supervision, Head
// fallback and exact Counseling participation are never repeated here. A Student reads their own
// conversations; Counselors and Guidance Services Staff read the ones their workload allows. IT
// Admin, Institutional Officers, Head and DPO designations add nothing.
export type GuidanceMessagesAccess = {
  isStudent: boolean;
  isStaff: boolean;
  /** Student: may open the workspace for their own conversations. */
  canViewSelf: boolean;
  /** Student: may write to the Guidance Office or a Counseling relationship. */
  canManageSelf: boolean;
  /** Counselor or Guidance Services Staff: may open the workspace for their workload. */
  canViewStaff: boolean;
  /** Counselor or Guidance Services Staff: may write, start Office conversations, resolve and reopen. */
  canManageStaff: boolean;
  hasWorkspace: boolean;
  /** Writing a Message, and marking a conversation read, need manage authority. */
  canWrite: boolean;
};

export function getGuidanceMessagesAccess(user: UserSummary): GuidanceMessagesAccess {
  const isStudent = user.role === "STUDENT";
  const isStaff = user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
  const canViewSelf = isStudent && user.capabilities.includes("guidance_messages.view_self");
  const canManageSelf = canViewSelf && user.capabilities.includes("guidance_messages.manage_self");
  const canViewStaff = isStaff && user.capabilities.includes("guidance_messages.view");
  const canManageStaff = canViewStaff && user.capabilities.includes("guidance_messages.manage");

  return {
    isStudent,
    isStaff,
    canViewSelf,
    canManageSelf,
    canViewStaff,
    canManageStaff,
    hasWorkspace: canViewSelf || canViewStaff,
    canWrite: canManageSelf || canManageStaff,
  };
}
