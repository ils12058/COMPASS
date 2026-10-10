"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
  useNotificationsListMine,
  useNotificationsMarkAllRead,
  useNotificationsMarkRead,
} from "@/lib/api/generated/notifications/notifications";

function formatNotificationDate(value: string) {
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function PortalNotificationsPage() {
  const queryClient = useQueryClient();
  const notificationsQuery = useNotificationsListMine(
    { page: 1, page_size: 20 },
    {
      query: {
        staleTime: 30_000,
      },
    },
  );
  const markAllRead = useNotificationsMarkAllRead({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getNotificationsListMineQueryKey({ page: 1, page_size: 20 }),
        });
        void queryClient.invalidateQueries({
          queryKey: getNotificationsGetUnreadCountQueryKey(),
        });
      },
    },
  });
  const markRead = useNotificationsMarkRead({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getNotificationsListMineQueryKey({ page: 1, page_size: 20 }),
        });
        void queryClient.invalidateQueries({
          queryKey: getNotificationsGetUnreadCountQueryKey(),
        });
      },
    },
  });

  const notifications = notificationsQuery.data?.data.items ?? [];
  const unreadCount = notifications.filter((item) => !item.is_read).length;

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
            Updates for you
          </p>
          <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight">
            Notifications
          </h1>
          <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
            Messages and reminders connected to your COMPASS workspace.
          </p>
        </div>
        {unreadCount > 0 ? (
          <Button
            variant="outline"
            disabled={markAllRead.isPending}
            onClick={() => markAllRead.mutate()}
          >
            <CheckCheck aria-hidden="true" className="size-4" />
            {markAllRead.isPending ? "Updating…" : "Mark all as read"}
          </Button>
        ) : null}
      </header>

      {notificationsQuery.isPending ? (
        <div className="space-y-3" aria-live="polite">
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="h-28 animate-pulse rounded-2xl border bg-card"
            />
          ))}
        </div>
      ) : notificationsQuery.isError ? (
        <div className="rounded-2xl border bg-card p-6 text-sm text-muted-foreground">
          <p>We couldn’t load your notifications right now.</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => void notificationsQuery.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : notifications.length === 0 ? (
        <div className="rounded-3xl border bg-card px-6 py-14 text-center shadow-sm">
          <Bell aria-hidden="true" className="mx-auto size-10 text-[var(--compass-support)]" />
          <h2 className="mt-4 font-heading text-2xl font-bold">You’re all caught up</h2>
          <p className="mx-auto mt-2 max-w-md leading-7 text-muted-foreground">
            New messages and reminders will appear here when there is something for you to see.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((notification) => (
            <article
              key={notification.id}
              className={`rounded-2xl border bg-card p-5 shadow-sm ${
                notification.is_read ? "" : "border-[var(--compass-brand-maroon)]/35"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {!notification.is_read ? (
                      <span
                        aria-label="Unread"
                        className="size-2 rounded-full bg-[var(--compass-brand-maroon)]"
                      />
                    ) : null}
                    <h2 className="font-heading text-lg font-bold">{notification.title}</h2>
                  </div>
                  <p className="mt-2 leading-7 text-muted-foreground">
                    {notification.message}
                  </p>
                </div>
                {!notification.is_read ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={markRead.isPending}
                    onClick={() => markRead.mutate({ notificationId: notification.id })}
                  >
                    Mark as read
                  </Button>
                ) : null}
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                {formatNotificationDate(notification.created_at)}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
