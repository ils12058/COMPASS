import type { UserSummary } from "@/lib/api/generated/model";

export type ECounselingAccess = {
  isStudent: boolean;
  isCounselor: boolean;
  canViewSelf: boolean;
  canJoinSelf: boolean;
  canConsentSelf: boolean;
  canViewAssigned: boolean;
  canJoinAssigned: boolean;
  canManageMediaAssigned: boolean;
  hasWorkspace: boolean;
};

export function getECounselingAccess(user: UserSummary): ECounselingAccess {
  const isStudent = user.role === "STUDENT";
  const isCounselor = user.role === "COUNSELOR";
  const capabilities = new Set(user.capabilities);
  const canViewSelf = isStudent && capabilities.has("ecounseling.view_self");
  const canJoinSelf = isStudent && capabilities.has("ecounseling.join_self");
  const canConsentSelf = isStudent && capabilities.has("ecounseling.consent_self");
  const canViewAssigned = isCounselor && capabilities.has("ecounseling.view_assigned");
  const canJoinAssigned = isCounselor && capabilities.has("ecounseling.join_assigned");
  const canManageMediaAssigned = isCounselor && capabilities.has("ecounseling.manage_media_assigned");

  return {
    isStudent,
    isCounselor,
    canViewSelf,
    canJoinSelf,
    canConsentSelf,
    canViewAssigned,
    canJoinAssigned,
    canManageMediaAssigned,
    hasWorkspace: canViewSelf || canViewAssigned,
  };
}
