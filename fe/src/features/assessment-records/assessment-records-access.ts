import type { UserSummary } from "@/lib/api/generated/model";

// The confirmed portal session supplies active identity; backend rechecks it on every request.
export function getAssessmentRecordsAccess(user: UserSummary) {
  const canView =
    user.role === "COUNSELOR" &&
    user.capabilities.includes("assessment_records.view");
  const canManage =
    canView && user.capabilities.includes("assessment_records.manage");
  return {
    canView,
    canManage,
    canManageTypes:
      canManage && user.designations.includes("HEAD_GUIDANCE_COUNSELOR"),
  };
}
