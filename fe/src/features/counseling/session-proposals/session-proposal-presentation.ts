import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  SessionProposalPurposeValue,
  SessionProposalStateValue,
} from "@/lib/api/generated/model";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";

export const purposeOptions: readonly { value: SessionProposalPurposeValue; label: string }[] = [
  { value: SessionProposalPurposeValue.FOLLOW_UP_SESSION, label: "Follow-up session" },
  { value: SessionProposalPurposeValue.CHECK_IN, label: "Check-in" },
  { value: SessionProposalPurposeValue.CONTINUING_SESSION, label: "Continuing session" },
];

export function purposeLabel(value: SessionProposalPurposeValue | string): string {
  return purposeOptions.find((option) => option.value === value)?.label ?? "Counseling session";
}

const staffStateLabels: Record<SessionProposalStateValue, string> = {
  PENDING: "Waiting for the Student",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn",
  EXPIRED: "Expired without an answer",
};

const studentStateLabels: Record<SessionProposalStateValue, string> = {
  PENDING: "Waiting for your answer",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn by your Counselor",
  EXPIRED: "No longer open",
};

export function proposalStateLabel(state: SessionProposalStateValue | string, audience: "staff" | "student" = "staff"): string {
  const labels = audience === "student" ? studentStateLabels : staffStateLabels;
  return labels[state as SessionProposalStateValue] ?? "Unknown";
}

const errors: Record<string, string> = {
  permission_denied: "You can't propose sessions for this case.",
  counseling_case_not_found: "You don't have access to this case.",
  counseling_case_closed: "This case is closed. Sessions can't be proposed.",
  counseling_case_changed: "This case changed before your proposal was sent. Review the latest details.",
  session_proposal_not_found: "This session proposal isn't available.",
  session_proposal_invalid: "Some proposal details need attention. Review them and try again.",
  session_proposal_open: "This case already has a proposal waiting for the Student. Withdraw it before proposing other times.",
  session_proposal_closed: "This proposal is no longer open.",
  session_proposal_changed: "This proposal changed. The latest details are now shown.",
  session_proposal_unavailable: "This proposal can no longer be used. Contact the Guidance Office.",
  session_proposal_time_unavailable: "That time is no longer available. Choose another time.",
  session_proposal_student_action_required: "Something needs your attention before you can accept.",
};

export function proposalErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

function errorDetails(error: unknown): Record<string, unknown> | null {
  if (!(error instanceof CompassApiError)) return null;
  const body = error.body as { error?: { details?: unknown } } | null;
  const details = body?.error?.details;
  return details && typeof details === "object" ? (details as Record<string, unknown>) : null;
}

/** The 1-based proposed time the backend refused, when it named one. */
export function refusedOption(error: unknown): number | null {
  const option = errorDetails(error)?.option;
  return typeof option === "number" ? option : null;
}

export function proposalErrorMessage(error: unknown, fallback: string): string {
  const code = proposalErrorCode(error);
  if (code === "session_proposal_time_unavailable") {
    const option = refusedOption(error);
    if (option) return `Time ${option} is no longer available. Choose another time.`;
  }
  if (code === "session_proposal_student_action_required") {
    const reason = errorDetails(error)?.reason;
    if (reason === "current_inventory_required") return "Submit your Individual Inventory for this Academic Year, then accept a time.";
    if (reason === "current_academic_year_not_configured") return "Appointments can't be booked until the Academic Year is set up. Contact the Guidance Office.";
  }
  return (code && errors[code]) || fallback;
}

// A failed connection or server error doesn't prove the change failed.
export function isUncertainProposalResult(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function isStaleProposalError(error: unknown): boolean {
  const code = proposalErrorCode(error);
  return code === "session_proposal_changed" || code === "session_proposal_closed";
}

export function proposeSessionHref(caseId: string, returnTo: string, followUpId?: string | null): string {
  const query = followUpId ? `?follow_up_id=${encodeURIComponent(followUpId)}` : "";
  return withWorkflowReturn(`/portal/counseling/cases/${caseId}/propose-session${query}`, returnTo);
}

export function caseCallSlipHref({
  studentId,
  caseId,
  appointmentId,
  reportAt,
  followUpId,
  returnTo,
}: {
  studentId: string;
  caseId?: string | null;
  appointmentId?: string | null;
  reportAt?: string | null;
  followUpId?: string | null;
  returnTo: string;
}): string {
  const params = new URLSearchParams({ student_id: studentId });
  if (caseId) params.set("case_id", caseId);
  if (appointmentId) params.set("appointment_id", appointmentId);
  if (reportAt) params.set("report_at", reportAt);
  if (followUpId && !caseId) params.set("follow_up_id", followUpId);
  return withWorkflowReturn(`/portal/call-slips/new?${params}`, returnTo);
}

export function studentProposalHref(proposalId: string): string {
  return `/portal/appointments/proposals/${proposalId}`;
}

export function messageThreadHref(threadId: string, returnTo: string): string {
  return withWorkflowReturn(`/portal/messages/${threadId}`, returnTo);
}
