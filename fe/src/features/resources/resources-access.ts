import type { UserSummary } from "@/lib/api/generated/model";

export function canManageResources(user: UserSummary): boolean {
  return user.capabilities.includes("resources.manage");
}
