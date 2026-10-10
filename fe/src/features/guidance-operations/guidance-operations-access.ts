import type { UserSummary } from "@/lib/api/generated/model";

export function hasGuidanceOperations(user: Pick<UserSummary, "role">): boolean {
  return user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF";
}
