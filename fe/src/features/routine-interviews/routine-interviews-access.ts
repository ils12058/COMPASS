import type { UserSummary } from "@/lib/api/generated/model";

export type RoutineInterviewAccess = {
  isStudent: boolean;
  isCounselor: boolean;
  isCurrentStudent: boolean;
  canViewSelf: boolean;
  canManageSelf: boolean;
  canViewAssigned: boolean;
  canManageAssigned: boolean;
  hasWorkspace: boolean;
};

export function getRoutineInterviewAccess(
  user: UserSummary,
): RoutineInterviewAccess {
  const isStudent = user.role === "STUDENT";
  const isCounselor = user.role === "COUNSELOR";
  const isCurrentStudent = user.student_lifecycle_status === "CURRENT";
  const canViewSelf =
    isStudent && user.capabilities.includes("routine_interviews.view_self");
  const canManageSelf =
    isStudent &&
    isCurrentStudent &&
    user.capabilities.includes("routine_interviews.manage_self");
  const canViewAssigned =
    isCounselor &&
    user.capabilities.includes("routine_interviews.view_assigned");
  const canManageAssigned =
    isCounselor &&
    user.capabilities.includes("routine_interviews.manage_assigned");

  return {
    isStudent,
    isCounselor,
    isCurrentStudent,
    canViewSelf,
    canManageSelf,
    canViewAssigned,
    canManageAssigned,
    hasWorkspace:
      canViewSelf ||
      canManageSelf ||
      canViewAssigned ||
      canManageAssigned,
  };
}
