"use client";
import { useEffect, useRef } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

export function invalidateFollowups(client: QueryClient) {
  return Promise.all([
    client.invalidateQueries({ predicate: query => typeof query.queryKey[0] === "string" && query.queryKey[0].startsWith("/api/v1/guidance-followups") }),
    invalidateGuidanceWork(client),
  ]);
}
export function useFollowupsFreshness(enabled: boolean) {
  const client = useQueryClient(); const { generation } = useRealtimeStatus(); const seen = useRef(generation);
  useRealtimeEvent("followups.changed", () => { if (enabled) void invalidateFollowups(client); });
  useEffect(() => { if (enabled && generation > seen.current) void invalidateFollowups(client); seen.current = generation; }, [client, enabled, generation]);
}
export const followupQueryFreshness = { refetchInterval: 60_000, refetchIntervalInBackground: false, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } as const;
