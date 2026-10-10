"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import { hasStudentActions } from "@/features/student-actions/student-actions-access";
import { getStudentActionsListQueryKey, useStudentActionsList } from "@/lib/api/generated/student-actions/student-actions";
import type { UserSummary } from "@/lib/api/generated/model";

const queryFamily = getStudentActionsListQueryKey();
export const studentActionsQueryFamily = () => queryFamily;

/** Canonical HTTP truth in the account-owned QueryClient. Hints contain no action data. */
export function useStudentActions(user: UserSummary, page = 1, pageSize = 20) {
  const enabled = hasStudentActions(user);
  const client = useQueryClient();
  const { generation } = useRealtimeStatus();
  const seenGeneration = useRef(generation);
  const query = useStudentActionsList({ page, page_size: pageSize }, {
    query: {
      enabled,
      retry: false,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });
  useProjectionFocus(queryFamily, enabled);
  useEffect(() => {
    if (generation > seenGeneration.current && enabled) {
      void client.invalidateQueries({ queryKey: queryFamily });
    }
    seenGeneration.current = generation;
  }, [client, enabled, generation]);
  const reconcile = () => {
    if (enabled) void client.invalidateQueries({ queryKey: queryFamily });
  };
  useRealtimeEvent("messages.thread_changed", reconcile);
  useRealtimeEvent("notifications.changed", reconcile);
  return query;
}
