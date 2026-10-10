"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import type { RealtimeSnapshot } from "@/features/realtime/realtime-runtime";
import {
  getNotificationsGetUnreadCountQueryKey,
  getNotificationsListMineQueryKey,
} from "@/lib/api/generated/notifications/notifications";

// Hints are lossy. Polling and foreground reconciliation remain healing paths (ADR-101).
export const NOTIFICATION_FALLBACK_REFRESH_MS = 8_000;
export const NOTIFICATION_LIVE_SAFETY_REFRESH_MS = 60_000;

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
  let refreshRequestedAgain = false;
  let stopped = false;
  let generation = 0;
  let interval = NOTIFICATION_FALLBACK_REFRESH_MS;

  function canRefresh() {
    return !stopped && environment.document.visibilityState === "visible" && environment.navigator.onLine;
  }

  async function refresh() {
    if (!canRefresh() || refreshing) return;
    refreshing = true;
    refreshRequestedAgain = false;
    try {
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: getNotificationsGetUnreadCountQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getNotificationsListMineQueryKey() }),
      ]);
    } finally {
      refreshing = false;
      // All requests during this fetch collapse into one trailing reconciliation. If hidden or
      // offline, retain the request until a foreground/online refresh can obtain canonical state.
      if (refreshRequestedAgain && canRefresh()) void refresh();
    }
  }

  function requestRefresh() {
    if (stopped) return;
    refreshRequestedAgain = true;
    void refresh();
  }

  let timer = environment.window.setInterval(requestRefresh, interval);
  function setRealtimeStatus(snapshot: RealtimeSnapshot) {
    if (stopped) return;
    const nextInterval = snapshot.state === "live"
      ? NOTIFICATION_LIVE_SAFETY_REFRESH_MS
      : NOTIFICATION_FALLBACK_REFRESH_MS;
    if (nextInterval !== interval) {
      environment.window.clearInterval(timer);
      interval = nextInterval;
      timer = environment.window.setInterval(requestRefresh, interval);
    }
    if (snapshot.generation > generation) {
      generation = snapshot.generation;
      requestRefresh();
    }
  }

  const onVisible = () => { if (environment.document.visibilityState === "visible") requestRefresh(); };
  environment.document.addEventListener("visibilitychange", onVisible);
  environment.window.addEventListener("focus", onVisible);
  environment.window.addEventListener("online", requestRefresh);
  function stop() {
    stopped = true;
    refreshRequestedAgain = false;
    environment.window.clearInterval(timer);
    environment.document.removeEventListener("visibilitychange", onVisible);
    environment.window.removeEventListener("focus", onVisible);
    environment.window.removeEventListener("online", requestRefresh);
  }
  return { requestRefresh, setRealtimeStatus, stop };
}

export function useNotificationFreshness() {
  const queryClient = useQueryClient();
  const { state, generation } = useRealtimeStatus();
  const freshness = useRef<ReturnType<typeof startNotificationFreshness> | null>(null);

  useEffect(() => {
    const consumer = startNotificationFreshness(queryClient, { document, window, navigator });
    freshness.current = consumer;
    return () => {
      consumer.stop();
      freshness.current = null;
    };
  }, [queryClient]);
  useEffect(() => {
    freshness.current?.setRealtimeStatus({ state, generation });
  }, [queryClient, state, generation]);
  useRealtimeEvent("notifications.changed", () => freshness.current?.requestRefresh());
}

export function NotificationFreshness() {
  useNotificationFreshness();
  return null;
}
