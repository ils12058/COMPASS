"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import { getWorkQueueListQueryKey, useWorkQueueList } from "@/lib/api/generated/work/work";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import type { UserSummary } from "@/lib/api/generated/model";

export const workQueueQueryFamily = () => getWorkQueueListQueryKey();

/** One canonical query family in the account-owned QueryClient; no separate store or socket. */
export function useWorkQueue(user: UserSummary, page = 1, pageSize = 20) {
  const enabled = hasWorkQueue(user);
  const client = useQueryClient();
  const { generation } = useRealtimeStatus();
  const seenGeneration = useRef(generation);
  const query = useWorkQueueList({ page, page_size: pageSize }, {
    query: {
      enabled,
      retry: false,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });
  useEffect(() => {
    if (!enabled) return;
    const refresh = () => {
      if (document.visibilityState === "visible" && navigator.onLine) {
        void client.invalidateQueries({ queryKey: workQueueQueryFamily() });
      }
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [client, enabled]);
  useEffect(() => {
    if (generation > seenGeneration.current && enabled) {
      void client.invalidateQueries({ queryKey: workQueueQueryFamily() });
    }
    seenGeneration.current = generation;
  }, [client, enabled, generation]);
  useRealtimeEvent("messages.thread_changed", () => {
    if (enabled) void client.invalidateQueries({ queryKey: workQueueQueryFamily() });
  });
  return query;
}
