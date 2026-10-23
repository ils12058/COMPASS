import type { UserSummary } from "@/lib/api/generated/model";

export type CounselingAccess = {
  isCounselor: boolean;
  isStudent: boolean;
  canViewAssigned: boolean;
  canManageAssigned: boolean;
  canViewAssignedStudentSessionSummaries: boolean;
  canManageAssignedStudentSessionSummaries: boolean;
  canViewOwnStudentSessionSummaries: boolean;
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
  const canViewAssignedStudentSessionSummaries =
    isCounselor && capabilities.has("student_session_summaries.view_assigned");
  const canManageAssignedStudentSessionSummaries =
    isCounselor && capabilities.has("student_session_summaries.manage_assigned");
  const canViewOwnStudentSessionSummaries =
    isStudent && capabilities.has("student_session_summaries.view_self");
  const hasCounselorWorkspace = canViewAssigned;
  const hasStudentWorkspace = canViewOwnStudentSessionSummaries;

  return {
    isCounselor,
    isStudent,
    canViewAssigned,
    canManageAssigned,
    canViewAssignedStudentSessionSummaries,
    canManageAssignedStudentSessionSummaries,
    canViewOwnStudentSessionSummaries,
    hasCounselorWorkspace,
    hasStudentWorkspace,
    hasWorkspace: hasCounselorWorkspace || hasStudentWorkspace,
  };
}
