import { AnnouncementStatusValue, type AnnouncementManagementResponse } from "@/lib/api/generated/model";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
} from "@/lib/institutional-time";

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
    const published = `Published ${formatInstitutionalDateTime(item.published_at)}`;
    if (!item.expires_at) {
      return `${published} · ${INSTITUTION_TIME_ZONE_LABEL}`;
    }
    return `${published} · ${isAnnouncementExpired(item) ? "Expired" : "Expires"} ${formatInstitutionalDateTime(item.expires_at)} · ${INSTITUTION_TIME_ZONE_LABEL}`;
  }
  return `Last updated ${formatInstitutionalDateTime(item.updated_at)} · ${INSTITUTION_TIME_ZONE_LABEL}`;
}
