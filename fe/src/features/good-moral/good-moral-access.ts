import type { UserSummary } from "@/lib/api/generated/model";

export type GoodMoralAccess = {
  isStudent: boolean;
  isCounselor: boolean;
  canViewSelf: boolean;
  canRequestSelf: boolean;
  canViewOperational: boolean;
  canManageOperational: boolean;
  canIssue: boolean;
  hasStudentWorkspace: boolean;
  hasOperationalWorkspace: boolean;
  hasWorkspace: boolean;
};

export function getGoodMoralAccess(user: UserSummary): GoodMoralAccess {
  const isStudent = user.role === "STUDENT";
  const isCounselor = user.role === "COUNSELOR";
  const canViewSelf =
    isStudent && user.capabilities.includes("good_moral.view_self");
  const canRequestSelf =
    isStudent && user.capabilities.includes("good_moral.request_self");
  const canViewOperational =
    isCounselor && user.capabilities.includes("good_moral.view");
  const canManageOperational =
    isCounselor && user.capabilities.includes("good_moral.manage");
  const canIssue =
    isCounselor && user.capabilities.includes("good_moral.issue");
  const hasStudentWorkspace = canViewSelf || canRequestSelf;
  const hasOperationalWorkspace =
    canViewOperational || canManageOperational || canIssue;

  return {
    isStudent,
    isCounselor,
    canViewSelf,
    canRequestSelf,
    canViewOperational,
    canManageOperational,
    canIssue,
    hasStudentWorkspace,
    hasOperationalWorkspace,
    hasWorkspace: hasStudentWorkspace || hasOperationalWorkspace,
  };
}
