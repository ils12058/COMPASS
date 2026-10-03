"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { reconcileNotificationAuth } from "@/features/notifications/notification-auth";
import { cacheConfirmedAllRead } from "@/features/notifications/notification-cache";
import { NotificationRow } from "@/features/notifications/notification-center/notification-row";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
  useNotificationsGetUnreadCount,
  useNotificationsListMine,
  useNotificationsMarkAllRead,
} from "@/lib/api/generated/notifications/notifications";

const PAGE_SIZE = 20;

function NotificationSkeleton() {
  return (
    <LoadingRegion label="Loading notifications…" className="divide-y divide-border">
      {[0, 1, 2].map((item) => (
        <div key={item} className="px-4 py-5 sm:px-5">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-3/4" />
          <Skeleton className="mt-4 h-3 w-1/4" />
        </div>
      ))}
    </LoadingRegion>
  );
}

export function NotificationCenter({ page }: { page: number }) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const notifications = useNotificationsListMine({ page, page_size: PAGE_SIZE }, { query: { retry: false } });
  const unread = useNotificationsGetUnreadCount({ query: { retry: false } });
  const markAll = useNotificationsMarkAllRead();
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshingAfterMarkAll, setRefreshingAfterMarkAll] = useState(false);
  const data = notifications.data?.data;
  const hasUnread = (unread.data?.data.unread_count ?? 0) > 0 || (data?.items.some((item) => !item.is_read) ?? false);

  useEffect(() => {
    if (notifications.error) reconcileNotificationAuth(notifications.error, queryClient);
  }, [notifications.error, queryClient]);

  async function markAllRead() {
    setActionError(null);
    setRefreshingAfterMarkAll(true);
    try {
      await markAll.mutateAsync();
      cacheConfirmedAllRead(queryClient);
    } catch (caught) {
      reconcileNotificationAuth(caught, queryClient);
      setActionError("Notifications could not be marked as read. Please try again.");
      setRefreshingAfterMarkAll(false);
      return;
    }
    await Promise.allSettled([
      queryClient.invalidateQueries({ queryKey: getNotificationsListMineQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getNotificationsGetUnreadCountQueryKey() }),
    ]);
    setRefreshingAfterMarkAll(false);
  }

  return (
    <section aria-labelledby="notifications-heading">
      <PageHeader
        title="Notifications"
        headingId="notifications-heading"
        actions={hasUnread ? <Button variant="secondary" disabled={markAll.isPending || refreshingAfterMarkAll} onClick={() => void markAllRead()}>{markAll.isPending || refreshingAfterMarkAll ? "Marking as read…" : "Mark all as read"}</Button> : null}
      />
      {actionError ? <p role="alert" className="mb-4 text-sm text-danger">{actionError}</p> : null}
      {data && notifications.isError ? <Notice role="alert" tone="warning" className="mb-4" action={<Button variant="secondary" onClick={() => void notifications.refetch()}>Retry</Button>}>Notifications could not be refreshed. Showing the last loaded page.</Notice> : null}
      <Panel aria-labelledby="notifications-list-heading">
        <PanelHeader
          title="Your notifications"
          titleId="notifications-list-heading"
          context={notifications.isFetching && data ? "Refreshing notifications…" : null}
        />
        {!data && notifications.isPending ? <NotificationSkeleton /> : null}
        {!data && notifications.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void notifications.refetch()}>Retry</Button>}>
            Notifications could not be loaded.
          </PanelMessage>
        ) : null}
        {data ? (
          <>
            {data.items.length ? (
              <ol>
                {data.items.map((item) => <NotificationRow key={item.id} notification={item} currentUserId={user.id} />)}
              </ol>
            ) : <PanelMessage>{page === 1 ? "No notifications are available yet." : "No notifications are available on this page. Go back to a previous page."}</PanelMessage>}
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={data.page}
              hasNext={data.has_next}
              label="Notification pages"
              onPageChange={(nextPage) =>
                router.push(nextPage === 1 ? "/portal/notifications" : `/portal/notifications?page=${nextPage}`)
              }
            />
          </>
        ) : null}
      </Panel>
      {data ? <Link href="/portal/account/preferences" className="mt-4 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Manage email preference</Link> : null}
    </section>
  );
}
