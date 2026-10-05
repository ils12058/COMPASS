import type { UserSummary } from "@/lib/api/generated/model";

export type ExitInterviewAccess = {
  isStudent: boolean;
  isCurrentStudent: boolean;
  canViewSelf: boolean;
  canManageSelf: boolean;
  canViewOperational: boolean;
  canReopen: boolean;
  canManageOpportunities: boolean;
  hasStudentWorkspace: boolean;
  hasOperationalWorkspace: boolean;
  hasWorkspace: boolean;
};

export function getExitInterviewAccess(user: UserSummary): ExitInterviewAccess {
  const isStudent = user.role === "STUDENT";
  const isCurrentStudent = user.student_lifecycle_status === "CURRENT";
  const canViewSelf =
    isStudent && user.capabilities.includes("exit_interviews.view_self");
  const canManageSelf =
    isStudent &&
    isCurrentStudent &&
    user.capabilities.includes("exit_interviews.manage_self");
  const canViewOperational = user.capabilities.includes("exit_interviews.view");
  const canReopen = user.capabilities.includes("exit_interviews.reopen");
  const canManageOpportunities = user.capabilities.includes("exit_interviews.manage_opportunities");
  const hasStudentWorkspace = canViewSelf && user.exit_interview_workspace_available === true;
  const hasOperationalWorkspace = canViewOperational || canManageOpportunities;

  return {
    isStudent,
    isCurrentStudent,
    canViewSelf,
    canManageSelf,
    canViewOperational,
    canReopen,
    canManageOpportunities,
    hasStudentWorkspace,
    hasOperationalWorkspace,
    hasWorkspace: hasStudentWorkspace || hasOperationalWorkspace,
  };
}
