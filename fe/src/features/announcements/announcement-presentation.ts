import { AnnouncementStatusValue, type AnnouncementManagementResponse } from "@/lib/api/generated/model";
import { formatDateTime } from "@/lib/date-time";

// Expiry hides a published Announcement from readers without changing its
// status, so managers see the distinction here.
export function isAnnouncementExpired(
  item: Pick<AnnouncementManagementResponse, "expires_at">,
  now = new Date(),
): boolean {
  if (!item.expires_at) return false;
  const expires = new Date(item.expires_at).getTime();
  return !Number.isNaN(expires) && expires <= now.getTime();
}

export function announcementTimingLine(item: AnnouncementManagementResponse): string {
  if (item.status === AnnouncementStatusValue.PUBLISHED && item.published_at) {
    const published = `Published ${formatDateTime(item.published_at)}`;
    if (!item.expires_at) return published;
    return `${published} · ${isAnnouncementExpired(item) ? "Expired" : "Expires"} ${formatDateTime(item.expires_at)}`;
  }
  return `Last updated ${formatDateTime(item.updated_at)}`;
}
