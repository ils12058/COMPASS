"use client";

import { useInventoryGetMyStatus } from "@/lib/api/generated/inventory/inventory";
import { useExitInterviewsGetMyCurrent } from "@/lib/api/generated/exit-interviews/exit-interviews";
import { useGraduateTracerGetMyResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { useGoodMoralListRequests } from "@/lib/api/generated/good-moral/good-moral";
import {
  GoodMoralStatusValue,
  InventoryStatusValue,
  RoutineEvaluationStatus,
  RoutineIntakeStatus,
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

export type OverviewAttentionItem = {
  id: string;
  title: string;
  subject?: string;
  detail: string;
  href: string;
  actionLabel: string;
  onRetry?: () => void;
  isError?: boolean;
};

export type OverviewAttentionData = {
  items: OverviewAttentionItem[];
  isPending: boolean;
  isVisible: boolean;
  emptyMessage: string;
  staleNotices: string[];
};

function hasCount(value: number | null | undefined): value is number {
  return value !== null && value !== undefined;
}

function isAuthorizationFailure(error: unknown): boolean {
  return error instanceof CompassApiError && (error.status === 401 || error.status === 403);
}

function addErrorRow(
  items: OverviewAttentionItem[],
  id: string,
  title: string,
  detail: string,
  href: string,
  actionLabel: string,
  onRetry: () => void,
) {
  items.push({ id, title, detail, href, actionLabel, onRetry, isError: true });
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
  const exitEnabled = isStudent && exitAccess.canManageSelf;
  const graduateEnabled = isStudent && graduateAccess.canManageSelf;
  const counselorRoutineCount = summary?.guidance?.routine_evaluation_pending_count;
  const counselorRoutineEnabled =
    isCounselor &&
    routineAccess.canViewAssigned &&
    hasCount(counselorRoutineCount) &&
    counselorRoutineCount > 0;
  const goodMoralCount = summary?.guidance?.good_moral_requested_count;
  const goodMoralEnabled =
    isCounselor &&
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
      page: 1,
      page_size: 3,
    },
    { query: { enabled: counselorRoutineEnabled, retry: false } },
  );
  const goodMoralRequests = useGoodMoralListRequests(
    {
      status: GoodMoralStatusValue.REQUESTED,
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
      });
    } else if (current?.status === InventoryStatusValue.DRAFT) {
      items.push({
        id: "inventory-draft",
        title: "Individual Inventory",
        detail: "Your current Academic Year Inventory is still in draft.",
        href: "/portal/inventory/current",
        actionLabel: "Continue Individual Inventory",
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

    for (const draft of drafts) {
      items.push({
        id: "student-routine-" + draft.id,
        title: "Routine Interview",
        detail: "Your intake is still in draft.",
        href: "/portal/routine-interviews/" + draft.id,
        actionLabel: "Continue Routine Interview",
      });
    }
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
      );
    } else if (studentRoutines.isError && studentRoutines.data && !isAuthorizationFailure(studentRoutines.error)) {
      staleNotices.push("Routine Interview previews could not be refreshed. Showing the last confirmed items.");
    } else if (studentRoutines.isSuccess && drafts.length === 0) {
      items.push({
        id: "student-routine-summary",
        title: "Routine Interview drafts",
        detail: "Your Overview summary still reports drafts. Open the workspace to review them.",
        href: "/portal/routine-interviews",
        actionLabel: "Open Routine Interviews",
      });
    }
  }

  if (exitEnabled) {
    const exitErrorCode = exitInterviewErrorCode(currentExitInterview.error);
    const current = isAuthorizationFailure(currentExitInterview.error) ||
      exitErrorCode === "exit_interview_not_found"
      ? undefined
      : currentExitInterview.data?.data;
    if (current?.status === "DRAFT") {
      items.push({
        id: "exit-interview-" + current.id,
        title: "Exit Interview",
        detail: "Your Exit Interview is still in draft.",
        href: "/portal/exit-interviews/" + current.id,
        actionLabel: "Continue Exit Interview",
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
    for (const routine of records.slice(0, 3)) {
      items.push({
        id: "counselor-routine-" + routine.id,
        title: "Routine Interview",
        subject: routine.student.display_name,
        detail: "Student intake submitted; evaluation not finalized.",
        href: "/portal/routine-interviews/" + routine.id,
        actionLabel: "Review Routine Interview",
      });
    }
    if (
      counselorRoutines.isError &&
      (!counselorRoutines.data || isAuthorizationFailure(counselorRoutines.error))
    ) {
      addErrorRow(
        items,
        "counselor-routine-unavailable",
        "Routine evaluation preview",
        routineErrorMessage(counselorRoutines.error, "Routine evaluation previews could not be loaded."),
        "/portal/routine-interviews",
        "Open Routine Interviews",
        () => void counselorRoutines.refetch(),
      );
    } else if (counselorRoutines.isError && counselorRoutines.data && !isAuthorizationFailure(counselorRoutines.error)) {
      staleNotices.push("Routine evaluation previews could not be refreshed. Showing the last confirmed items.");
    } else if (counselorRoutines.isSuccess && records.length === 0) {
      items.push({
        id: "counselor-routine-summary",
        title: "Routine evaluations pending",
        detail: "Your Overview summary still reports pending evaluations. Open the workspace to review them.",
        href: "/portal/routine-interviews",
        actionLabel: "Open Routine Interviews",
      });
    }
  }

  if (goodMoralEnabled) {
    const records = isAuthorizationFailure(goodMoralRequests.error)
      ? []
      : goodMoralRequests.data?.data.items ?? [];
    for (const request of records.slice(0, 3)) {
      items.push({
        id: "good-moral-" + request.id,
        title: "Good Moral request",
        subject: request.applicant_name,
        detail: goodMoralVariantLabel(request.variant) + " request",
        href: "/portal/good-moral/" + request.id,
        actionLabel: "Review Good Moral request",
      });
    }
    if (
      goodMoralRequests.isError &&
      (!goodMoralRequests.data || isAuthorizationFailure(goodMoralRequests.error))
    ) {
      addErrorRow(
        items,
        "good-moral-unavailable",
        "Good Moral request preview",
        goodMoralErrorMessage(goodMoralRequests.error, "Good Moral request previews could not be loaded."),
        "/portal/good-moral",
        "Open Good Moral",
        () => void goodMoralRequests.refetch(),
      );
    } else if (goodMoralRequests.isError && goodMoralRequests.data && !isAuthorizationFailure(goodMoralRequests.error)) {
      staleNotices.push("Good Moral previews could not be refreshed. Showing the last confirmed items.");
    } else if (goodMoralRequests.isSuccess && records.length === 0) {
      items.push({
        id: "good-moral-summary",
        title: "Good Moral requests",
        detail: "Your Overview summary still reports requests awaiting issuance. Open the workspace to review them.",
        href: "/portal/good-moral",
        actionLabel: "Open Good Moral",
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
      detail = failedEmailCount + " failed · " + dueEmailCount + " due pending";
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
        " due and pending";
    } else {
      detail = "Email delivery requires review";
    }
    items.push({
      id: "email-delivery-attention",
      title: "Email delivery requires attention",
      detail,
      href: "/portal/platform/email-delivery",
      actionLabel: "Review email delivery",
    });
  }

  const studentAttentionScope =
    inventoryEnabled ||
    exitEnabled ||
    graduateEnabled ||
    (isStudent &&
      routineAccess.canViewSelf &&
      hasCount(summary?.student?.routine_intake_draft_count));
  const counselorAttentionScope =
    (isCounselor &&
      routineAccess.canViewAssigned &&
      hasCount(summary?.guidance?.routine_evaluation_pending_count)) ||
    (isCounselor &&
      goodMoralAccess.canViewOperational &&
      hasCount(summary?.guidance?.good_moral_requested_count));
  const platformAttentionScope =
    canViewEmailDeliveries &&
    ((platform?.email_failed_count !== null && platform?.email_failed_count !== undefined) ||
      (platform?.email_due_pending_count !== null && platform?.email_due_pending_count !== undefined));
  const isVisible =
    items.length > 0 ||
    studentAttentionScope ||
    counselorAttentionScope ||
    platformAttentionScope;

  const isPending =
    (inventoryEnabled && inventory.isPending) ||
    (studentRoutineEnabled && studentRoutines.isPending) ||
    (exitEnabled && currentExitInterview.isPending) ||
    (graduateEnabled && graduateResponse.isPending) ||
    (counselorRoutineEnabled && counselorRoutines.isPending) ||
    (goodMoralEnabled && goodMoralRequests.isPending);

  return {
    items,
    isPending,
    isVisible,
    emptyMessage: isStudent
      ? "No current forms require your attention."
      : "No current items require your attention.",
    staleNotices: Array.from(new Set(staleNotices)),
  };
}
