import {
  AnnouncementManagementOrdering,
  AnnouncementOrdering,
  AnnouncementStatusValue,
  type AnnouncementManagementResponse,
} from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
} from "@/lib/institutional-time";

// Expiry hides a published Announcement from readers without changing its
// status, so managers see the distinction here.
// Readers see the editorial order by default: pinned first, then the newest published. The full
// index may be browsed another way; Overview always keeps the editorial order (ADR-090).
export const announcementReaderOrderingOptions: readonly SortOption<AnnouncementOrdering>[] = [
  { value: AnnouncementOrdering.RECOMMENDED, label: "Recommended (pinned first)" },
  { value: AnnouncementOrdering.NEWEST, label: "Newest first" },
  { value: AnnouncementOrdering.OLDEST, label: "Oldest first" },
  { value: AnnouncementOrdering.TITLE_ASC, label: "Title A–Z" },
  { value: AnnouncementOrdering.TITLE_DESC, label: "Title Z–A" },
];

export const announcementManagementOrderingOptions: readonly SortOption<AnnouncementManagementOrdering>[] = [
  { value: AnnouncementManagementOrdering.RECENTLY_UPDATED, label: "Recently updated first" },
  { value: AnnouncementManagementOrdering.OLDEST_UPDATED, label: "Oldest updated first" },
  { value: AnnouncementManagementOrdering.NEWEST_PUBLISHED, label: "Newest published first" },
  { value: AnnouncementManagementOrdering.OLDEST_PUBLISHED, label: "Oldest published first" },
  { value: AnnouncementManagementOrdering.TITLE_ASC, label: "Title A–Z" },
  { value: AnnouncementManagementOrdering.TITLE_DESC, label: "Title Z–A" },
];

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
