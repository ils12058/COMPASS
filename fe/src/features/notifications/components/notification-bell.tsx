"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { reconcileNotificationAuth } from "@/features/notifications/notification-auth";
import { useNotificationsGetUnreadCount } from "@/lib/api/generated/notifications/notifications";

export function NotificationBell() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const unread = useNotificationsGetUnreadCount({
    query: { retry: false, refetchInterval: 60_000, staleTime: 30_000 },
  });
  const count = unread.data?.data.unread_count;
  const label = count && count > 0 ? `Notifications, ${count} unread` : "Notifications";

  useEffect(() => {
    if (unread.error) reconcileNotificationAuth(unread.error, queryClient);
  }, [queryClient, unread.error]);

  return (
    <Link
      href="/portal/notifications"
      aria-label={label}
      aria-current={pathname === "/portal/notifications" ? "page" : undefined}
      className="relative inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus aria-[current=page]:bg-surface-muted aria-[current=page]:text-brand"
    >
      <Bell size={21} aria-hidden="true" />
      {count && count > 0 ? (
        <span aria-hidden="true" className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-bold leading-none text-on-brand">
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </Link>
  );
}
