import { DesignationCode, type UserSummary } from "@/lib/api/generated/model";

export type AppointmentAccess = {
  canViewSelf: boolean;
  canManageSelf: boolean;
  canBook: boolean;
  canManage: boolean;
  hasWorkspace: boolean;
  isStudent: boolean;
  canManageSlots: boolean;
  canReviewCounselorRequests: boolean;
};

export function getAppointmentAccess(user: UserSummary): AppointmentAccess {
  const isStudent = user.role === "STUDENT";
  const hasSelfCapability = user.capabilities.includes("appointments.view_self");
  const canViewSelf =
    hasSelfCapability && (isStudent || user.role === "COUNSELOR");
  const canManageSelf =
    isStudent && user.capabilities.includes("appointments.manage_self");
  const isCurrentStudent = user.student_lifecycle_status === "CURRENT";
  const canManage = user.capabilities.includes("appointments.manage");
  const canManageSlots =
    canManage &&
    (user.role === "COUNSELOR" || user.role === "GUIDANCE_OFFICE_ASSISTANT");
  const canReviewCounselorRequests =
    canManage &&
    user.role === "COUNSELOR" &&
    user.designations.includes(DesignationCode.HEAD_GUIDANCE_COUNSELOR);

  return {
    canViewSelf,
    canManageSelf,
    canBook: canManageSelf && isCurrentStudent,
    canManage,
    hasWorkspace: canViewSelf || canManage,
    isStudent,
    canManageSlots,
    canReviewCounselorRequests,
  };
}
