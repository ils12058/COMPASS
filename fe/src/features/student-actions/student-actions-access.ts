import type { UserSummary } from "@/lib/api/generated/model";

export function hasStudentActions(user: Pick<UserSummary, "role">): boolean {
  return user.role === "STUDENT";
}
