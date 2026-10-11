import type { UserSummary } from "@/lib/api/generated/model";

// The confirmed portal session supplies active identity and resolved effective capabilities;
// backend rechecks both on every request. Head Guidance is a default grantee, not a gate.
export function getAssessmentRecordsAccess(user: UserSummary) {
  const canView =
    user.role === "COUNSELOR" &&
    user.capabilities.includes("assessment_records.view");
  const canManage =
    canView && user.capabilities.includes("assessment_records.manage");
  return {
    canView,
    canManage,
    // The Assessment Type catalog shares the effective manage capability with records.
    canManageTypes: canManage,
  };
}
