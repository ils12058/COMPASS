import type { QueryClient } from "@tanstack/react-query";

import { getNotificationsListMineQueryKey, notificationsListMine } from "@/lib/api/generated/notifications/notifications";
import type { NotificationResponse } from "@/lib/api/generated/model";

type NotificationListResult = Awaited<ReturnType<typeof notificationsListMine>>;

function notificationListBelongingTo(accountId: string, queryKey: readonly unknown[]): boolean {
  return queryKey[0] === getNotificationsListMineQueryKey()[0] && queryKey.at(-1) === accountId;
}

export function cacheConfirmedRead(
  queryClient: QueryClient,
  changed: NotificationResponse,
  accountId: string,
) {
  queryClient.setQueriesData<NotificationListResult>(
    { predicate: (query) => notificationListBelongingTo(accountId, query.queryKey) },
    (cached) => cached ? {
      ...cached,
      data: { ...cached.data, items: cached.data.items.map((item) => item.id === changed.id ? changed : item) },
    } : cached,
  );
}

export function cacheConfirmedAllRead(queryClient: QueryClient, accountId: string) {
  queryClient.setQueriesData<NotificationListResult>(
    { predicate: (query) => notificationListBelongingTo(accountId, query.queryKey) },
    (cached) => cached ? {
      ...cached,
      data: { ...cached.data, items: cached.data.items.map((item) => ({ ...item, is_read: true })) },
    } : cached,
  );
}
