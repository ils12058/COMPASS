"use client";

import type { OverviewSummaryResponse, UserSummary } from "@/lib/api/generated/model";
import { AttentionPriority, attentionKey, rankAttention, type AttentionRank } from "@/features/portal/home/overview-attention-ranking";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import { useWorkQueue } from "@/features/work-queue/work-queue-data";
import { presentWork } from "@/features/work-queue/work-queue-presentation";
import { hasStudentActions } from "@/features/student-actions/student-actions-access";
import { useStudentActions } from "@/features/student-actions/student-actions-data";
import { presentStudentAction } from "@/features/student-actions/student-actions-presentation";

export type OverviewAttentionItem = {
  id: string;
  title: string;
  subject?: string;
  detail: string;
  href: string;
  actionLabel: string;
  onRetry?: () => void;
  isError?: boolean;
  // Internal ranking facts; never shown (ADR-090).
  rank: AttentionRank;
};

export type OverviewAttentionData = {
  items: OverviewAttentionItem[];
  isPending: boolean;
  isVisible: boolean;
  staleNotices: string[];
  viewAllWork?: boolean;
  viewAllActions?: boolean;
  isCaughtUp?: boolean;
};

export function shouldShowOverviewAttention(
  itemCount: number,
  isPending: boolean,
  staleNoticeCount: number,
): boolean {
  return itemCount > 0 || isPending || staleNoticeCount > 0;
}

// A source that could not be read keeps its place in its own priority class.
function addErrorRow(
  items: OverviewAttentionItem[],
  id: string,
  title: string,
  detail: string,
  href: string,
  actionLabel: string,
  onRetry: () => void,
  priority: AttentionPriority,
) {
  items.push({
    id,
    title,
    detail,
    href,
    actionLabel,
    onRetry,
    isError: true,
    rank: { priority, stableKey: attentionKey(id, 0, id) },
  });
}

export function useOverviewAttention(
  user: UserSummary,
  summary: OverviewSummaryResponse | undefined,
): OverviewAttentionData {
  const studentEnabled = hasStudentActions(user);
  const studentActions = useStudentActions(user, 1, 5);
  const studentData = safeQueryData(studentActions)?.data;
  const workEnabled = hasWorkQueue(user);
  const work = useWorkQueue(user, 1, 5);
  const workData = safeQueryData(work)?.data;

  const items: OverviewAttentionItem[] = [];
  const staleNotices: string[] = [];

  if (studentEnabled) {
    for (const item of studentData?.items ?? []) {
      const row = presentStudentAction(item);
      items.push({ id: item.id, ...row, detail: [row.detail, row.timing].filter(Boolean).join(" "),
        rank: { priority: item.priority, dueAt: item.due_at, waitingSince: item.waiting_since, stableKey: item.id } });
    }
    if (studentActions.isError && !studentData) {
      addErrorRow(items, "student-actions-unavailable", "My actions could not be loaded",
        "Open My actions to retry.", "/portal/actions", "Open My actions", () => void studentActions.refetch(), AttentionPriority.ACTION_REQUIRED);
    } else if (studentActions.isError && studentData) {
      staleNotices.push("My actions could not be refreshed. Showing the last confirmed result.");
    }
  }

  if (workEnabled) {
    for (const item of workData?.items ?? []) {
      items.push({
        id: item.id, ...presentWork(item), subject: item.student.display_name,
        rank: {
          priority: item.priority === "TIME_SENSITIVE" ? AttentionPriority.TIME_SENSITIVE : AttentionPriority.ACTION_REQUIRED,
          dueAt: item.due_at, waitingSince: item.waiting_since, stableKey: item.id,
        },
      });
    }
    if (work.isError && !workData) {
      addErrorRow(items, "work-unavailable", "My work could not be loaded",
        "Open My work to retry.", "/portal/work", "Open My work", () => void work.refetch(), AttentionPriority.ACTION_REQUIRED);
    } else if (work.isError && workData) {
      staleNotices.push("My work could not be refreshed. Showing the last confirmed items.");
    }
  }

  const platform = summary?.platform;
  const canViewEmailDeliveries = user.capabilities.includes("platform_operations.view");
  const failedEmailCount = platform?.email_failed_count;
  const dueEmailCount = platform?.email_due_pending_count;
  const hasEmailNeedsAttention =
    (failedEmailCount !== null &&
      failedEmailCount !== undefined &&
      failedEmailCount > 0) ||
    (dueEmailCount !== null && dueEmailCount !== undefined && dueEmailCount > 0);
  if (
    canViewEmailDeliveries &&
    hasEmailNeedsAttention
  ) {
    let detail: string;
    if (
      failedEmailCount !== null &&
      failedEmailCount !== undefined &&
      failedEmailCount > 0 &&
      dueEmailCount !== null &&
      dueEmailCount !== undefined &&
      dueEmailCount > 0
    ) {
      detail = failedEmailCount + " failed · " + dueEmailCount + " due for a delivery attempt";
    } else if (
      failedEmailCount !== null &&
      failedEmailCount !== undefined &&
      failedEmailCount > 0
    ) {
      detail =
        failedEmailCount +
        " email " +
        (failedEmailCount === 1 ? "delivery is" : "deliveries are") +
        " currently failed";
    } else if (dueEmailCount !== null && dueEmailCount !== undefined) {
      detail =
        dueEmailCount +
        " email " +
        (dueEmailCount === 1 ? "delivery is" : "deliveries are") +
        " due for a delivery attempt";
    } else {
      detail = "Email delivery requires review";
    }
    items.push({
      id: "email-delivery-attention",
      title: "Email delivery requires attention",
      detail,
      href: "/portal/platform/email-delivery",
      actionLabel: "Review email delivery",
      // Failed deliveries need an operator; deliveries merely due are ordinary operational work.
      rank: {
        priority:
          failedEmailCount !== null && failedEmailCount !== undefined && failedEmailCount > 0
            ? AttentionPriority.CRITICAL
            : AttentionPriority.ACTION_REQUIRED,
        stableKey: "email-delivery:000",
      },
    });
  }

  const isPending = (studentEnabled && studentActions.isPending) || (workEnabled && work.isPending);
  const isVisible = shouldShowOverviewAttention(items.length, isPending, staleNotices.length);

  return {
    items: workEnabled || studentEnabled ? items : rankAttention(items),
    isPending,
    isVisible: workEnabled || studentEnabled || isVisible,
    viewAllWork: workEnabled,
    viewAllActions: studentEnabled,
    isCaughtUp: (workEnabled && work.isSuccess && workData?.items.length === 0) || (studentEnabled && studentActions.isSuccess && studentData?.items.length === 0),
    staleNotices: Array.from(new Set(staleNotices)),
  };
}
