"use client";

import { Bell } from "lucide-react";
import Link from "next/link";

import { unreadLabel } from "@/features/notifications/presentation";
import { useNotificationsGetUnreadCount } from "@/lib/api/generated/notifications/notifications";

export function NotificationBell() {
  const query = useNotificationsGetUnreadCount({
    query: {
      refetchInterval: 60_000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  });

  const unreadCount = query.data?.data.unread_count ?? 0;
  const badge = unreadCount >= 100 ? "99+" : String(unreadCount);

  return (
    <Link
      href="/portal/notifications"
      aria-label={unreadLabel(unreadCount)}
      className="relative inline-flex size-10 items-center justify-center rounded-lg border border-transparent text-foreground no-underline hover:bg-muted"
    >
      <Bell aria-hidden="true" className="size-5" />
      {unreadCount > 0 ? (
        <span
          aria-hidden="true"
          className="absolute -right-1 -top-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold leading-none text-primary-foreground"
        >
          {badge}
        </span>
      ) : null}
    </Link>
  );
}
