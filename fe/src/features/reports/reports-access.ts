import type { UserSummary } from "@/lib/api/generated/model";

export function canAttemptReports(user: UserSummary): boolean {
  return (
    user.role === "COUNSELOR" &&
    user.capabilities.includes("reports.view")
  );
}
