"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { reconcileNotificationAuth } from "@/features/notifications/notification-auth";
import { cacheConfirmedAllRead } from "@/features/notifications/notification-cache";
import { NotificationRow } from "@/features/notifications/notification-center/notification-row";
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
    <div role="status" className="mt-7 border-t border-border"><span className="sr-only">Loading notifications…</span>
      {[0, 1, 2].map((item) => (
        <div key={item} className="border-b border-border py-6">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-3/4" />
          <Skeleton className="mt-4 h-3 w-1/4" />
        </div>
      ))}
      <span className="sr-only">Loading notifications…</span>
    </div>
  );
}

export function NotificationCenter({ page }: { page: number }) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="notifications-heading" className="font-heading text-3xl font-bold text-ink">Notifications</h1>
        {hasUnread ? <Button variant="secondary" disabled={markAll.isPending || refreshingAfterMarkAll} onClick={() => void markAllRead()}>{markAll.isPending || refreshingAfterMarkAll ? "Marking as read…" : "Mark all as read"}</Button> : null}
      </div>
      {actionError ? <p role="alert" className="mt-4 text-sm text-danger">{actionError}</p> : null}
      {!data && notifications.isPending ? <NotificationSkeleton /> : null}
      {!data && notifications.isError ? (
        <div role="alert" className="mt-7 border-t border-border pt-6">
          <p className="text-sm text-danger">Notifications could not be loaded.</p>
          <Button variant="secondary" className="mt-3" onClick={() => void notifications.refetch()}>Retry</Button>
        </div>
      ) : null}
      {data ? (
        <>
          {notifications.isFetching ? <p role="status" className="mt-3 text-xs text-muted">Refreshing notifications…</p> : null}
          {notifications.isError ? <div role="alert" className="mt-3 text-sm text-danger"><span>Notifications could not be refreshed. Showing the last loaded page.</span> <Button variant="quiet" className="min-h-0 px-1 py-0" onClick={() => void notifications.refetch()}>Retry</Button></div> : null}
          {data.items.length ? (
            <ol className="mt-7 border-t border-border">
              {data.items.map((item) => <NotificationRow key={item.id} notification={item} currentUserId={user.id} />)}
            </ol>
          ) : <p className="mt-7 border-t border-border py-7 text-sm text-muted">{page === 1 ? "No notifications are available yet." : "No notifications are available on this page. Go back to a previous page."}</p>}
          <nav aria-label="Notification pages" className="mt-6 flex items-center justify-between gap-3">
            {page > 1 ? <Link href={page === 2 ? "/portal/notifications" : `/portal/notifications?page=${page - 1}`} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Previous</Link> : <span />}
            <span className="text-sm text-muted">Page {data.page}</span>
            {data.has_next ? <Link href={`/portal/notifications?page=${page + 1}`} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Next</Link> : <span />}
          </nav>
          <Link href="/portal/account/preferences" className="mt-8 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Manage email preference</Link>
        </>
      ) : null}
    </section>
  );
}
