"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
} from "@/lib/api/generated/notifications/notifications";

// The staging API uses two synchronous WSGI workers. Short, bounded requests
// give foreground clients near-realtime freshness without pinning workers.
export const NOTIFICATION_REFRESH_MS = 8_000;

type FreshnessEnvironment = {
  document: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  window: Pick<Window, "setInterval" | "clearInterval" | "addEventListener" | "removeEventListener">;
  navigator: Pick<Navigator, "onLine">;
};

export function startNotificationFreshness(
  queryClient: Pick<QueryClient, "invalidateQueries">,
  environment: FreshnessEnvironment,
) {
  let refreshing = false;
  let stopped = false;
  async function refresh() {
    if (stopped || refreshing || environment.document.visibilityState !== "visible" || !environment.navigator.onLine) return;
    refreshing = true;
    try {
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: getNotificationsGetUnreadCountQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getNotificationsListMineQueryKey() }),
      ]);
    } finally {
      refreshing = false;
    }
  }
  const timer = environment.window.setInterval(() => void refresh(), NOTIFICATION_REFRESH_MS);
  const onVisible = () => { if (environment.document.visibilityState === "visible") void refresh(); };
  const onOnline = () => void refresh();
  environment.document.addEventListener("visibilitychange", onVisible);
  environment.window.addEventListener("focus", onVisible);
  environment.window.addEventListener("online", onOnline);
  return () => {
    stopped = true;
    environment.window.clearInterval(timer);
    environment.document.removeEventListener("visibilitychange", onVisible);
    environment.window.removeEventListener("focus", onVisible);
    environment.window.removeEventListener("online", onOnline);
  };
}

export function useNotificationFreshness() {
  const queryClient = useQueryClient();
  useEffect(() => startNotificationFreshness(queryClient, { document, window, navigator }), [queryClient]);
}

export function NotificationFreshness() {
  useNotificationFreshness();
  return null;
}
