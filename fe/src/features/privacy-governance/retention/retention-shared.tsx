"use client";

import type { QueryClient } from "@tanstack/react-query";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  canApproveDisposition,
  canManageRetention,
  canViewRetention,
} from "../privacy-governance-access";
import { CompassApiError } from "@/lib/api/errors";
import type {
  DispositionCaseResponse,
  DispositionState,
  RetentionCategory,
} from "@/lib/api/generated/model";
import {
  getPrivacyGovernanceListDispositionCasesQueryKey,
  getPrivacyGovernanceListRetentionRulesQueryKey,
  getPrivacyGovernanceRetentionSummaryQueryKey,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

export const categoryLabels: Record<RetentionCategory, string> = {
  GRADUATE_TRACER: "Graduate Tracer",
  ECOUNSELING_RECORDING: "E-Counseling recordings",
  ECOUNSELING_TRANSCRIPT: "E-Counseling stored transcripts",
};

export const stateLabels: Record<DispositionState, string> = {
  READY: "Needs review",
  ON_HOLD: "On hold",
  BLOCKED: "Blocked",
  NO_LONGER_ELIGIBLE: "No longer eligible",
  APPROVED: "Approved",
  QUEUED: "Queued",
  PROCESSING: "Processing",
  COMPLETED: "Completed",
  FAILED: "Failed",
  RECONCILIATION_REQUIRED: "Reconciliation required",
};

export function dispositionConsequence(
  item: Pick<DispositionCaseResponse, "category">,
): string {
  return item.category === "GRADUATE_TRACER"
    ? "Direct identity, identifying contact information, free text, and detailed education, exam, and training history will be removed. Current aggregate survey information will remain available. The removed identifying information cannot be restored."
    : "The provider artifact will be deleted after provider verification. Consent decisions and minimized lifecycle evidence will remain. The deleted recording or stored transcript cannot be restored through COMPASS.";
}

export function useRetentionAccess() {
  const { user } = usePortalSession();
  return {
    canView: canViewRetention(user),
    canManage: canManageRetention(user),
    canApprove: canApproveDisposition(user),
  };
}

export function isRetentionConflict(error: unknown): boolean {
  return error instanceof CompassApiError && error.status === 409;
}

export function canConfirmDispositionReview(
  reviewedRevision: number,
  currentRevision: number,
  fresh: boolean,
): boolean {
  return fresh && reviewedRevision === currentRevision;
}

export async function invalidateRetention(client: QueryClient) {
  await Promise.all([
    client.invalidateQueries({
      queryKey: getPrivacyGovernanceListDispositionCasesQueryKey(),
    }),
    client.invalidateQueries({
      queryKey: getPrivacyGovernanceListRetentionRulesQueryKey(),
    }),
    client.invalidateQueries({
      queryKey: getPrivacyGovernanceRetentionSummaryQueryKey(),
    }),
  ]);
}
