"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { NotificationPolicyBadge } from "@/features/notifications/components/notification-policy-badge";
import { notificationDestination } from "@/features/notifications/notification-destination";
import { formatNotificationDate } from "@/features/notifications/presentation";
import { CompassApiError } from "@/lib/api/client";
import { useNotificationsMarkRead } from "@/lib/api/generated/notifications/notifications";
import type { NotificationResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

export function NotificationRow({
  item,
  onReadStateChanged,
}: {
  item: NotificationResponse;
  onReadStateChanged: () => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [markReadError, setMarkReadError] = useState(false);
  const markRead = useNotificationsMarkRead();
  const destination = notificationDestination(item);
  const detailsId = `notification-${item.id}-details`;

  async function markAsRead() {
    if (item.is_read || markRead.isPending) {
      return;
    }

    setMarkReadError(false);

    try {
      await markRead.mutateAsync({ notificationId: item.id });
      await onReadStateChanged();
    } catch (caught) {
      if (caught instanceof CompassApiError && caught.status === 404) {
        await onReadStateChanged();
        return;
      }
      setMarkReadError(true);
    }
  }

  function toggleExpanded() {
    const nextExpanded = !expanded;
    setExpanded(nextExpanded);

    if (nextExpanded && !item.is_read) {
      void markAsRead();
    }
  }

  return (
    <article
      className={cn(
        "border-b last:border-b-0",
        !item.is_read && "bg-accent/35",
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={detailsId}
        onClick={toggleExpanded}
        className="flex w-full items-start gap-3 px-4 py-4 text-left hover:bg-muted/60 sm:px-5"
      >
        <span className="mt-2 flex size-2 shrink-0" aria-hidden="true">
          {!item.is_read ? <span className="size-2 rounded-full bg-primary" /> : null}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className={cn("font-semibold", !item.is_read && "font-bold")}>
              <span className="sr-only">
                {!item.is_read ? "Unread notification: " : "Read notification: "}
              </span>
              {item.title}
            </span>
            <NotificationPolicyBadge policy={item.policy} />
          </span>
          {!expanded ? (
            <span className="mt-1 block overflow-hidden text-ellipsis whitespace-nowrap text-sm text-muted-foreground">
              {item.message}
            </span>
          ) : null}
        </span>

        <span className="flex shrink-0 items-start gap-2 text-xs text-muted-foreground">
          <time dateTime={item.created_at} className="hidden sm:inline">
            {formatNotificationDate(item.created_at)}
          </time>
          {expanded ? (
            <ChevronUp aria-hidden="true" className="size-4" />
          ) : (
            <ChevronDown aria-hidden="true" className="size-4" />
          )}
        </span>
      </button>

      {expanded ? (
        <div id={detailsId} className="px-4 pb-5 pl-9 sm:px-5 sm:pl-10">
          <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">{item.message}</p>
          <time dateTime={item.created_at} className="mt-3 block text-xs text-muted-foreground sm:hidden">
            {formatNotificationDate(item.created_at)}
          </time>

          {destination ? (
            <Link
              href={destination.href}
              className="mt-4 inline-flex min-h-10 items-center rounded-lg border bg-card px-4 py-2 text-sm font-semibold no-underline hover:bg-muted"
            >
              {destination.label}
            </Link>
          ) : null}

          {markRead.isPending ? (
            <p role="status" className="mt-3 text-xs text-muted-foreground">
              Marking as read…
            </p>
          ) : null}

          {markReadError ? (
            <div role="alert" className="mt-3 flex flex-wrap items-center gap-3 text-sm text-destructive">
              <span>We couldn’t mark this notification as read.</span>
              <Button variant="outline" size="sm" onClick={() => void markAsRead()}>
                Try again
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
