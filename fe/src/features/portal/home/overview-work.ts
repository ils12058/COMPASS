"use client";

import { useInventoryGetMyStatus } from "@/lib/api/generated/inventory/inventory";
import { useExitInterviewsGetMyCurrent } from "@/lib/api/generated/exit-interviews/exit-interviews";
import { useGraduateTracerGetMyResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { useGoodMoralListRequests } from "@/lib/api/generated/good-moral/good-moral";
import {
  GoodMoralOrdering,
  GoodMoralStatusValue,
  InventoryStatusValue,
  RoutineEvaluationStatus,
  RoutineIntakeStatus,
  RoutineInterviewOrdering,
  type OverviewSummaryResponse,
  type UserSummary,
} from "@/lib/api/generated/model";
import { useRoutineInterviewsListAssigned, useRoutineInterviewsListMine } from "@/lib/api/generated/routine-interviews/routine-interviews";
import { CompassApiError } from "@/lib/api/errors";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { goodMoralErrorMessage, goodMoralVariantLabel } from "@/features/good-moral/good-moral-shared";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { exitInterviewErrorCode, exitInterviewErrorMessage } from "@/features/exit-interviews/exit-interview-shared";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { graduateTracerErrorCode, graduateTracerErrorMessage } from "@/features/graduate-tracer/graduate-tracer-shared";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { inventoryErrorMessage } from "@/features/inventory/inventory-shared";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { routineErrorMessage } from "@/features/routine-interviews/routine-interviews-shared";
import { PENDING_ROUTINE_EVALUATIONS, REQUESTED_GOOD_MORAL } from "@/features/portal/home/overview-presentation";
import {
  AttentionPriority,
  attentionKey,
  rankAttention,
  type AttentionRank,
} from "@/features/portal/home/overview-attention-ranking";

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
};

export function shouldShowOverviewAttention(
  itemCount: number,
  isPending: boolean,
  staleNoticeCount: number,
): boolean {
  return itemCount > 0 || isPending || staleNoticeCount > 0;
}

function hasCount(value: number | null | undefined): value is number {
  return value !== null && value !== undefined;
}

function isAuthorizationFailure(error: unknown): boolean {
  return error instanceof CompassApiError && (error.status === 401 || error.status === 403);
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
  const isStudent = user.role === "STUDENT";
  const isCounselor = user.role === "COUNSELOR";
  const inventoryAccess = getInventoryAccess(user);
  const routineAccess = getRoutineInterviewAccess(user);
  const exitAccess = getExitInterviewAccess(user);
  const graduateAccess = getGraduateTracerAccess(user);
  const goodMoralAccess = getGoodMoralAccess(user);

  const inventoryEnabled = isStudent && inventoryAccess.canManageSelf;
  const studentRoutineCount = summary?.student?.routine_intake_draft_count;
  const studentRoutineEnabled =
    isStudent &&
    routineAccess.canViewSelf &&
    hasCount(studentRoutineCount) &&
    studentRoutineCount > 0;
  const exitEnabled = isStudent && exitAccess.canManageSelf && exitAccess.hasStudentWorkspace;
  const graduateEnabled = isStudent && graduateAccess.canManageSelf;
  const counselorRoutineCount = summary?.guidance?.routine_evaluation_pending_count;
  const counselorRoutineEnabled =
    isCounselor &&
    routineAccess.canViewAssigned &&
    hasCount(counselorRoutineCount) &&
    counselorRoutineCount > 0;
  const goodMoralCount = summary?.guidance?.good_moral_requested_count;
  const goodMoralEnabled =
    goodMoralAccess.canViewOperational &&
    hasCount(goodMoralCount) &&
    goodMoralCount > 0;

  const inventory = useInventoryGetMyStatus({
    query: { enabled: inventoryEnabled, retry: false },
  });
  const studentRoutines = useRoutineInterviewsListMine({
    query: { enabled: studentRoutineEnabled, retry: false },
  });
  const currentExitInterview = useExitInterviewsGetMyCurrent({
    query: { enabled: exitEnabled, retry: false },
  });
  const graduateResponse = useGraduateTracerGetMyResponse({
    query: { enabled: graduateEnabled, retry: false },
  });
  const counselorRoutines = useRoutineInterviewsListAssigned(
    {
      intake_status: RoutineIntakeStatus.SUBMITTED,
      evaluation_status: RoutineEvaluationStatus.DRAFT,
      // The queue's own order: the evaluations that have waited longest.
      ordering: RoutineInterviewOrdering.OLDEST_WAITING,
      page: 1,
      page_size: 3,
    },
    { query: { enabled: counselorRoutineEnabled, retry: false } },
  );
  const goodMoralRequests = useGoodMoralListRequests(
    {
      status: GoodMoralStatusValue.REQUESTED,
      // The queue's own order: the requests that have waited longest.
      ordering: GoodMoralOrdering.OLDEST_FIRST,
      page: 1,
      page_size: 3,
    },
    { query: { enabled: goodMoralEnabled, retry: false } },
  );

  const items: OverviewAttentionItem[] = [];
  const staleNotices: string[] = [];

  if (inventoryEnabled) {
    const current = isAuthorizationFailure(inventory.error)
      ? undefined
      : inventory.data?.data;
    if (current?.status === InventoryStatusValue.MISSING) {
      items.push({
        id: "inventory-missing",
        title: "Individual Inventory",
        detail: "No Individual Inventory has been started for the current Academic Year.",
        href: "/portal/inventory",
        actionLabel: "Open Individual Inventory",
        rank: { priority: AttentionPriority.INCOMPLETE_SELF_SERVICE, stableKey: "inventory:000" },
      });
    } else if (current?.status === InventoryStatusValue.DRAFT) {
      items.push({
        id: "inventory-draft",
        title: "Individual Inventory",
        detail: "Your current Academic Year Inventory is still in draft.",
        href: "/portal/inventory/current",
        actionLabel: "Continue Individual Inventory",
        rank: { priority: AttentionPriority.INCOMPLETE_SELF_SERVICE, stableKey: "inventory:000" },
      });
    }
    if (
      inventory.isError &&
      (!inventory.data || isAuthorizationFailure(inventory.error))
    ) {
      addErrorRow(
        items,
        "inventory-unavailable",
        "Individual Inventory status",
        inventoryErrorMessage(inventory.error, "The current Individual Inventory status could not be loaded."),
        "/portal/inventory",
        "Open Individual Inventory",
        () => void inventory.refetch(),
        AttentionPriority.INCOMPLETE_SELF_SERVICE,
      );
    } else if (inventory.isError && inventory.data && !isAuthorizationFailure(inventory.error)) {
      staleNotices.push("Individual Inventory status could not be refreshed. Showing the last confirmed state.");
    }
  }

  if (studentRoutineEnabled) {
    const records = isAuthorizationFailure(studentRoutines.error)
      ? []
      : studentRoutines.data?.data.items ?? [];
    const drafts = records
      .filter((record) => record.intake_status === RoutineIntakeStatus.DRAFT)
      .slice(0, 3);

    drafts.forEach((draft, position) => {
      items.push({
        id: "student-routine-" + draft.id,
        title: "Routine Interview",
        detail: "Your intake is still in draft.",
        href: "/portal/routine-interviews/" + draft.id,
        actionLabel: "Continue Routine Interview",
        rank: {
          priority: AttentionPriority.INCOMPLETE_SELF_SERVICE,
          waitingSince: draft.created_at,
          stableKey: attentionKey("student-routine", position, draft.id),
        },
      });
    });
    if (
      studentRoutines.isError &&
      (!studentRoutines.data || isAuthorizationFailure(studentRoutines.error))
    ) {
      addErrorRow(
        items,
        "student-routine-unavailable",
        "Routine Interview drafts",
        routineErrorMessage(studentRoutines.error, "Your Routine Interview drafts could not be loaded."),
        "/portal/routine-interviews",
        "Open Routine Interviews",
        () => void studentRoutines.refetch(),
        AttentionPriority.INCOMPLETE_SELF_SERVICE,
      );
    } else if (studentRoutines.isError && studentRoutines.data && !isAuthorizationFailure(studentRoutines.error)) {
      staleNotices.push("Routine Interview previews could not be refreshed. Showing the last confirmed items.");
    } else if (studentRoutines.isSuccess && drafts.length === 0) {
      items.push({
        id: "student-routine-summary",
        title: "Routine Interview drafts",
        detail: "You may still have drafts to finish. Open Routine Interviews to review them.",
        href: "/portal/routine-interviews",
        actionLabel: "Open Routine Interviews",
        rank: { priority: AttentionPriority.INCOMPLETE_SELF_SERVICE, stableKey: "student-routine:999" },
      });
    }
  }

  if (exitEnabled) {
    const exitErrorCode = exitInterviewErrorCode(currentExitInterview.error);
    const current = isAuthorizationFailure(currentExitInterview.error) ||
      exitErrorCode === "exit_interview_not_found"
      ? undefined
      : currentExitInterview.data?.data;
    if (current?.status === "DRAFT" && current.can_edit) {
      items.push({
        id: "exit-interview-" + current.id,
        title: "Exit Interview",
        detail: "Your Exit Interview is still in draft.",
        href: "/portal/exit-interviews/" + current.id,
        actionLabel: "Continue Exit Interview",
        rank: {
          priority: AttentionPriority.INCOMPLETE_SELF_SERVICE,
          waitingSince: current.created_at,
          stableKey: attentionKey("exit-interview", 0, current.id),
        },
      });
    }
    if (
      currentExitInterview.isError &&
      (!currentExitInterview.data || isAuthorizationFailure(currentExitInterview.error)) &&
      exitErrorCode !== "exit_interview_not_found"
    ) {
      addErrorRow(
        items,
        "exit-interview-unavailable",
        "Exit Interview status",
        exitInterviewErrorMessage(currentExitInterview.error, "The current Exit Interview status could not be loaded."),
        "/portal/exit-interviews",
        "Open Exit Interviews",
        () => void currentExitInterview.refetch(),
        AttentionPriority.INCOMPLETE_SELF_SERVICE,
      );
    } else if (
      currentExitInterview.isError &&
      currentExitInterview.data &&
      !isAuthorizationFailure(currentExitInterview.error) &&
      exitErrorCode !== "exit_interview_not_found"
    ) {
      staleNotices.push("Exit Interview status could not be refreshed. Showing the last confirmed state.");
    }
  }

  if (graduateEnabled) {
    const graduateErrorCode = graduateTracerErrorCode(graduateResponse.error);
    const current = isAuthorizationFailure(graduateResponse.error) ||
      graduateErrorCode === "graduate_tracer_not_found"
      ? undefined
      : graduateResponse.data?.data;
    if (current?.status === "DRAFT") {
      items.push({
        id: "graduate-tracer-" + current.id,
        title: "Graduate Tracer Survey",
        detail: "Your response is still in draft.",
        href: "/portal/graduate-tracer",
        actionLabel: "Continue Graduate Tracer Survey",
        rank: {
          priority: AttentionPriority.INCOMPLETE_SELF_SERVICE,
          waitingSince: current.created_at,
          stableKey: attentionKey("graduate-tracer", 0, current.id),
        },
      });
    }
    if (
      graduateResponse.isError &&
      (!graduateResponse.data || isAuthorizationFailure(graduateResponse.error)) &&
      graduateErrorCode !== "graduate_tracer_not_found"
    ) {
      addErrorRow(
        items,
        "graduate-tracer-unavailable",
        "Graduate Tracer status",
        graduateTracerErrorMessage(graduateResponse.error, "Your Graduate Tracer response could not be loaded."),
        "/portal/graduate-tracer",
        "Open Graduate Tracer Survey",
        () => void graduateResponse.refetch(),
        AttentionPriority.INCOMPLETE_SELF_SERVICE,
      );
    } else if (
      graduateResponse.isError &&
      graduateResponse.data &&
      !isAuthorizationFailure(graduateResponse.error) &&
      graduateErrorCode !== "graduate_tracer_not_found"
    ) {
      staleNotices.push("Graduate Tracer status could not be refreshed. Showing the last confirmed state.");
    }
  }

  if (counselorRoutineEnabled) {
    const records = isAuthorizationFailure(counselorRoutines.error)
      ? []
      : counselorRoutines.data?.data.items ?? [];
    records.slice(0, 3).forEach((routine, position) => {
      items.push({
        id: "counselor-routine-" + routine.id,
        title: "Routine Interview",
        subject: routine.student.display_name,
        detail: "Student intake submitted; evaluation not finalized.",
        href: "/portal/routine-interviews/" + routine.id,
        actionLabel: "Review Routine Interview",
        // The evaluation has waited since the Student submitted the intake.
        rank: {
          priority: AttentionPriority.ACTION_REQUIRED,
          waitingSince: routine.intake_submitted_at,
          stableKey: attentionKey("counselor-routine", position, routine.id),
        },
      });
    });
    if (
      counselorRoutines.isError &&
      (!counselorRoutines.data || isAuthorizationFailure(counselorRoutines.error))
    ) {
      addErrorRow(
        items,
        "counselor-routine-unavailable",
        "Routine evaluation preview",
        routineErrorMessage(counselorRoutines.error, "Routine evaluation previews could not be loaded."),
        PENDING_ROUTINE_EVALUATIONS,
        "Open Routine Interviews",
        () => void counselorRoutines.refetch(),
        AttentionPriority.ACTION_REQUIRED,
      );
    } else if (counselorRoutines.isError && counselorRoutines.data && !isAuthorizationFailure(counselorRoutines.error)) {
      staleNotices.push("Routine evaluation previews could not be refreshed. Showing the last confirmed items.");
    } else if (counselorRoutines.isSuccess && records.length === 0) {
      items.push({
        id: "counselor-routine-summary",
        title: "Routine evaluations pending",
        detail: "Evaluations may still need review. Open Routine Interviews to check them.",
        href: PENDING_ROUTINE_EVALUATIONS,
        actionLabel: "Open Routine Interviews",
        rank: { priority: AttentionPriority.ACTION_REQUIRED, stableKey: "counselor-routine:999" },
      });
    }
  }

  if (goodMoralEnabled) {
    const records = isAuthorizationFailure(goodMoralRequests.error)
      ? []
      : goodMoralRequests.data?.data.items ?? [];
    records.slice(0, 3).forEach((request, position) => {
      items.push({
        id: "good-moral-" + request.id,
        title: "Good Moral request",
        subject: request.applicant_name,
        detail: goodMoralVariantLabel(request.variant) + " request",
        href: "/portal/good-moral/" + request.id,
        actionLabel: "Review Good Moral request",
        // A requested certificate has waited since the request.
        rank: {
          priority: AttentionPriority.ACTION_REQUIRED,
          waitingSince: request.created_at,
          stableKey: attentionKey("good-moral", position, request.id),
        },
      });
    });
    if (
      goodMoralRequests.isError &&
      (!goodMoralRequests.data || isAuthorizationFailure(goodMoralRequests.error))
    ) {
      addErrorRow(
        items,
        "good-moral-unavailable",
        "Good Moral request preview",
        goodMoralErrorMessage(goodMoralRequests.error, "Good Moral request previews could not be loaded."),
        REQUESTED_GOOD_MORAL,
        "Open Good Moral",
        () => void goodMoralRequests.refetch(),
        AttentionPriority.ACTION_REQUIRED,
      );
    } else if (goodMoralRequests.isError && goodMoralRequests.data && !isAuthorizationFailure(goodMoralRequests.error)) {
      staleNotices.push("Good Moral previews could not be refreshed. Showing the last confirmed items.");
    } else if (goodMoralRequests.isSuccess && records.length === 0) {
      items.push({
        id: "good-moral-summary",
        title: "Good Moral requests",
        detail: "Requests may still be awaiting issuance. Open Good Moral to review them.",
        href: REQUESTED_GOOD_MORAL,
        actionLabel: "Open Good Moral",
        rank: { priority: AttentionPriority.ACTION_REQUIRED, stableKey: "good-moral:999" },
      });
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

  const isPending =
    (inventoryEnabled && inventory.isPending) ||
    (studentRoutineEnabled && studentRoutines.isPending) ||
    (exitEnabled && currentExitInterview.isPending) ||
    (graduateEnabled && graduateResponse.isPending) ||
    (counselorRoutineEnabled && counselorRoutines.isPending) ||
    (goodMoralEnabled && goodMoralRequests.isPending);
  const isVisible = shouldShowOverviewAttention(items.length, isPending, staleNotices.length);

  return {
    items: rankAttention(items),
    isPending,
    isVisible,
    staleNotices: Array.from(new Set(staleNotices)),
  };
}
