import type { QueryClient } from "@tanstack/react-query";

import { getNotificationsListMineQueryKey, notificationsListMine } from "@/lib/api/generated/notifications/notifications";
import type { NotificationResponse } from "@/lib/api/generated/model";

type NotificationListResult = Awaited<ReturnType<typeof notificationsListMine>>;

export function cacheConfirmedRead(queryClient: QueryClient, changed: NotificationResponse) {
  queryClient.setQueriesData<NotificationListResult>(
    { queryKey: getNotificationsListMineQueryKey() },
    (cached) => cached ? {
      ...cached,
      data: { ...cached.data, items: cached.data.items.map((item) => item.id === changed.id ? changed : item) },
    } : cached,
  );
}

export function cacheConfirmedAllRead(queryClient: QueryClient) {
  queryClient.setQueriesData<NotificationListResult>(
    { queryKey: getNotificationsListMineQueryKey() },
    (cached) => cached ? {
      ...cached,
      data: { ...cached.data, items: cached.data.items.map((item) => ({ ...item, is_read: true })) },
    } : cached,
  );
}
