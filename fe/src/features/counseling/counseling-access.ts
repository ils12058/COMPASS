import type { UserSummary } from "@/lib/api/generated/model";

export type CounselingAccess = {
  isCounselor: boolean;
  isStudent: boolean;
  canViewAssigned: boolean;
  canManageAssigned: boolean;
  canViewAssignedSummaries: boolean;
  canManageAssignedSummaries: boolean;
  canViewOwnSummaries: boolean;
  hasCounselorWorkspace: boolean;
  hasStudentWorkspace: boolean;
  hasWorkspace: boolean;
};

export function getCounselingAccess(user: UserSummary): CounselingAccess {
  const isCounselor = user.role === "COUNSELOR";
  const isStudent = user.role === "STUDENT";
  const capabilities = new Set(user.capabilities);
  const canViewAssigned =
    isCounselor && capabilities.has("counseling.view_assigned");
  const canManageAssigned =
    isCounselor && capabilities.has("counseling.manage_assigned");
  const canViewAssignedSummaries =
    isCounselor && capabilities.has("shared_summaries.view_assigned");
  const canManageAssignedSummaries =
    isCounselor && capabilities.has("shared_summaries.manage_assigned");
  const canViewOwnSummaries =
    isStudent && capabilities.has("shared_summaries.view_self");
  const hasCounselorWorkspace = canViewAssigned || canManageAssigned;
  const hasStudentWorkspace = canViewOwnSummaries;

  return {
    isCounselor,
    isStudent,
    canViewAssigned,
    canManageAssigned,
    canViewAssignedSummaries,
    canManageAssignedSummaries,
    canViewOwnSummaries,
    hasCounselorWorkspace,
    hasStudentWorkspace,
    hasWorkspace: hasCounselorWorkspace || hasStudentWorkspace,
  };
}
