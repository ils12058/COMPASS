"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useProjectionFocus } from "@/features/freshness/use-projection-focus";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { guidanceUnreadCountQueryKey } from "@/features/guidance-messages/guidance-messages-cache";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import {
  getGuidanceOperationsGetQueryKey,
  useGuidanceOperationsGet,
} from "@/lib/api/generated/guidance-operations/guidance-operations";
import {
  getGuidanceMessagesGetUnreadCountQueryKey,
  useGuidanceMessagesGetUnreadCount,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceOperationsBacklog, UserSummary } from "@/lib/api/generated/model";

export type NavigationAttentionBadge = {
  count: number;
  display: string;
  ariaDescription: string;
};

export function formatBadgeDisplay(count: number): string {
  return count > 99 ? "99+" : String(count);
}

export function calculateMyWorkBacklogCount(
  backlog?: GuidanceOperationsBacklog | null,
): number | null {
  if (!backlog) return null;
  let total = 0;
  if (backlog.guidance_messages?.count !== undefined) total += backlog.guidance_messages.count;
  if (backlog.routine_evaluations?.count !== undefined) total += backlog.routine_evaluations.count;
  if (backlog.good_moral_preparation?.count !== undefined) total += backlog.good_moral_preparation.count;
  if (backlog.good_moral_issuance?.count !== undefined) total += backlog.good_moral_issuance.count;
  if (backlog.call_slips_due?.count !== undefined) total += backlog.call_slips_due.count;
  return total;
}

export function getNavigationBadge(
  href: string,
  counts: { myWork: number | null; messages: number | null },
): NavigationAttentionBadge | null {
  if (href === "/portal/work") {
    const count = counts.myWork;
    if (typeof count !== "number" || count <= 0) return null;
    return {
      count,
      display: formatBadgeDisplay(count),
      ariaDescription: `${count} ${count === 1 ? "item" : "items"} requiring attention`,
    };
  }
  if (href === "/portal/messages") {
    const count = counts.messages;
    if (typeof count !== "number" || count <= 0) return null;
    return {
      count,
      display: formatBadgeDisplay(count),
      ariaDescription: `${count} unread ${count === 1 ? "conversation" : "conversations"}`,
    };
  }
  return null;
}

const guidanceOperationsQueryFamily = getGuidanceOperationsGetQueryKey();
const messagesUnreadCountQueryFamily = getGuidanceMessagesGetUnreadCountQueryKey();

export function useNavigationAttention(user: UserSummary | null | undefined) {
  const client = useQueryClient();
  const { generation } = useRealtimeStatus();
  const seenGeneration = useRef(generation);

  const canWork = user ? hasWorkQueue(user) : false;
  const canMessages = user ? getGuidanceMessagesAccess(user).hasWorkspace : false;

  const workQuery = useGuidanceOperationsGet({
    query: {
      enabled: canWork,
      retry: false,
      staleTime: 8_000,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });

  const messagesQuery = useGuidanceMessagesGetUnreadCount({
    query: {
      enabled: canMessages,
      retry: false,
      staleTime: 8_000,
      refetchInterval: 60_000,
      refetchIntervalInBackground: false,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
    },
  });

  useProjectionFocus(guidanceOperationsQueryFamily, canWork);
  useProjectionFocus(messagesUnreadCountQueryFamily, canMessages);

  // Invalidate on socket reconnection
  useEffect(() => {
    if (generation > seenGeneration.current) {
      if (canWork) void client.invalidateQueries({ queryKey: guidanceOperationsQueryFamily });
      if (canMessages) void client.invalidateQueries({ queryKey: guidanceUnreadCountQueryKey() });
    }
    seenGeneration.current = generation;
  }, [canMessages, canWork, client, generation]);

  // Invalidate on thread changed realtime hint
  useRealtimeEvent("messages.thread_changed", () => {
    if (canWork) void client.invalidateQueries({ queryKey: guidanceOperationsQueryFamily });
    if (canMessages) void client.invalidateQueries({ queryKey: guidanceUnreadCountQueryKey() });
  });

  // Calculate confirmed counts, respecting null vs 0
  const myWorkCount: number | null =
    canWork && workQuery.isSuccess && workQuery.data?.data?.backlog
      ? calculateMyWorkBacklogCount(workQuery.data.data.backlog)
      : null;

  const messagesCount: number | null =
    canMessages && messagesQuery.isSuccess && messagesQuery.data?.data?.unread_conversations_count !== undefined
      ? messagesQuery.data.data.unread_conversations_count
      : null;

  const counts = { myWork: myWorkCount, messages: messagesCount };

  return {
    counts,
    getBadge: (href: string) => getNavigationBadge(href, counts),
  };
}
