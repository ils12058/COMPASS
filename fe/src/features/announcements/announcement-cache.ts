import type { QueryClient } from "@tanstack/react-query";

import {
  getAnnouncementsGetManagedQueryKey,
  getAnnouncementsGetPublicQueryKey,
  getAnnouncementsGetVisibleQueryKey,
  getAnnouncementsListManagedQueryKey,
  getAnnouncementsListPublicQueryKey,
  getAnnouncementsListVisibleQueryKey,
  type announcementsGetManagedResponseSuccess,
} from "@/lib/api/generated/announcements/announcements";

export function storeManagedAnnouncement(
  queryClient: QueryClient,
  response: announcementsGetManagedResponseSuccess,
) {
  queryClient.setQueryData(getAnnouncementsGetManagedQueryKey(response.data.id), response);
}

// Reader lists and pages change only when published content changes.
export function refreshAnnouncementQueries(
  queryClient: QueryClient,
  announcementId: string,
  { readers }: { readers: boolean },
) {
  const keys: readonly (readonly unknown[])[] = [
    getAnnouncementsListManagedQueryKey(),
    ...(readers
      ? [
          getAnnouncementsListVisibleQueryKey(),
          getAnnouncementsListPublicQueryKey(),
          getAnnouncementsGetVisibleQueryKey(announcementId),
          getAnnouncementsGetPublicQueryKey(announcementId),
        ]
      : []),
  ];
  return Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}
