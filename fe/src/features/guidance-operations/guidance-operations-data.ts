"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { hasGuidanceOperations } from "@/features/guidance-operations/guidance-operations-access";
import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import { getGuidanceOperationsGetQueryKey, useGuidanceOperationsGet } from "@/lib/api/generated/guidance-operations/guidance-operations";
import type { UserSummary } from "@/lib/api/generated/model";

const queryFamily = getGuidanceOperationsGetQueryKey();

export function useGuidanceOperations(user: UserSummary) {
  const enabled = hasGuidanceOperations(user);
  const client = useQueryClient();
  const { generation } = useRealtimeStatus();
  const seenGeneration = useRef(generation);
  const query = useGuidanceOperationsGet({ query: {
    enabled,
    retry: false,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: "always",
    refetchOnReconnect: "always",
  } });
  useProjectionFocus(queryFamily, enabled);
  useEffect(() => {
    if (enabled && generation > seenGeneration.current) {
      void client.invalidateQueries({ queryKey: queryFamily });
    }
    seenGeneration.current = generation;
  }, [client, enabled, generation]);
  useRealtimeEvent("messages.thread_changed", () => {
    if (enabled) void client.invalidateQueries({ queryKey: queryFamily });
  });
  return query;
}
