import type { UserSummary } from "@/lib/api/generated/model";

// The backend requires both the Counselor role and the capability; a
// capability override alone does not grant Student Support Context.
export function canViewStudentSupportContext(user: UserSummary): boolean {
  return user.role === "COUNSELOR" && user.capabilities.includes("student_support.view");
}
