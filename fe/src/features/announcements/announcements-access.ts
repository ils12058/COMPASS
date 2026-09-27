import type { UserSummary } from "@/lib/api/generated/model";

export function canManageAnnouncements(user: UserSummary): boolean {
  return user.capabilities.includes("announcements.manage");
}
