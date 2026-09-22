"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { reconcileNotificationAuth } from "@/features/notifications/notification-auth";
import { cacheConfirmedRead } from "@/features/notifications/notification-cache";
import { notificationDestination } from "@/features/notifications/notification-targets";
import { notificationTime } from "@/features/notifications/notification-time";
import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
  useNotificationsMarkRead,
} from "@/lib/api/generated/notifications/notifications";
import type { NotificationResponse } from "@/lib/api/generated/model";

export function NotificationRow({ notification, currentUserId }: { notification: NotificationResponse; currentUserId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const markRead = useNotificationsMarkRead();
  const [error, setError] = useState<string | null>(null);
  const destination = notificationDestination(notification, currentUserId);

  async function markAndMaybeOpen() {
    setError(null);
    if (notification.is_read) {
      if (destination) router.push(destination);
      return;
    }
    try {
      const response = await markRead.mutateAsync({ notificationId: notification.id });
      cacheConfirmedRead(queryClient, response.data);
    } catch (caught) {
      reconcileNotificationAuth(caught, queryClient);
      setError("This notification could not be marked as read. Please try again.");
      return;
    }
    await Promise.allSettled([
      queryClient.invalidateQueries({ queryKey: getNotificationsListMineQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getNotificationsGetUnreadCountQueryKey() }),
    ]);
    if (destination) router.push(destination);
  }

  return (
    <li className={`border-b border-border px-3 py-5 sm:px-4 ${notification.is_read ? "" : "bg-surface-subtle"}`}>
      <article aria-labelledby={`notification-${notification.id}`}>
        <div className="flex min-w-0 items-start gap-3">
          <span aria-hidden="true" className={`mt-2 size-2 shrink-0 rounded-full ${notification.is_read ? "bg-transparent" : "bg-brand"}`} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 id={`notification-${notification.id}`} className={`font-heading text-lg text-ink ${notification.is_read ? "font-semibold" : "font-bold"}`}>
                {notification.title}
              </h2>
              {!notification.is_read ? <span className="text-xs font-semibold text-brand">Unread</span> : null}
              {notification.policy === "MANDATORY_SECURITY" ? <span className="text-xs font-semibold text-support-strong">Security</span> : null}
            </div>
            <p className="mt-2 whitespace-pre-line text-sm leading-6 text-ink">{notification.message}</p>
            <time dateTime={notification.created_at} className="mt-3 block text-xs text-muted">{notificationTime(notification.created_at)}</time>
            {destination || !notification.is_read ? (
              <div className="mt-3">
                <Button variant="quiet" className="min-h-10 px-2" disabled={markRead.isPending} onClick={() => void markAndMaybeOpen()}>
                  {markRead.isPending ? "Marking as read…" : destination ? "Open Security" : "Mark as read"}
                </Button>
              </div>
            ) : null}
            {error ? <p role="alert" className="mt-2 text-sm text-danger">{error}</p> : null}
          </div>
        </div>
      </article>
    </li>
  );
}
