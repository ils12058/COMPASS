"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmailPreferencePanel } from "@/features/notifications/components/email-preference-panel";
import { NotificationList } from "@/features/notifications/components/notification-list";
import { NotificationPagination } from "@/features/notifications/components/notification-pagination";
import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
  useNotificationsListMine,
} from "@/lib/api/generated/notifications/notifications";

const PAGE_SIZE = 20;

export function NotificationCenter() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const params = { page, page_size: PAGE_SIZE };

  const notifications = useNotificationsListMine(params, {
    query: {
      placeholderData: (previous) => previous,
    },
  });

  const data = notifications.data?.data;

  async function refreshAfterRead() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getNotificationsListMineQueryKey(params),
      }),
      queryClient.invalidateQueries({
        queryKey: getNotificationsGetUnreadCountQueryKey(),
      }),
    ]);
  }

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="font-heading text-3xl font-bold tracking-tight">Notifications</h1>
        <p className="max-w-2xl text-muted-foreground">
          Updates about your COMPASS account and services.
        </p>
      </header>

      {notifications.isPending ? (
        <section
          aria-busy="true"
          aria-label="Loading notifications"
          className="overflow-hidden rounded-xl border bg-card"
        >
          {[0, 1, 2].map((item) => (
            <div key={item} className="border-b p-5 last:border-b-0">
              <div className="h-4 w-48 animate-pulse rounded bg-muted" />
              <div className="mt-3 h-3 w-3/4 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </section>
      ) : notifications.isError || !data ? (
        <section className="rounded-xl border bg-card p-6">
          <h2 className="font-heading text-xl font-bold">Notifications are unavailable right now.</h2>
          <Button className="mt-4" variant="outline" onClick={() => void notifications.refetch()}>
            Try again
          </Button>
        </section>
      ) : data.items.length === 0 ? (
        <section className="rounded-xl border bg-card p-8 text-center">
          <h2 className="font-heading text-xl font-bold">No notifications yet.</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Updates about your COMPASS account and services will appear here.
          </p>
        </section>
      ) : (
        <NotificationList items={data.items} onReadStateChanged={refreshAfterRead} />
      )}

      {data ? (
        <NotificationPagination
          page={data.page}
          hasNext={data.has_next}
          pending={notifications.isFetching}
          onPrevious={() => setPage((current) => Math.max(1, current - 1))}
          onNext={() => setPage((current) => current + 1)}
        />
      ) : null}

      <EmailPreferencePanel />
    </div>
  );
}
