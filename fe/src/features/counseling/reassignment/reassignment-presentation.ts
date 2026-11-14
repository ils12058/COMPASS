import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import type { CaseReassignmentResponse, CaseReassignmentStateValue } from "@/lib/api/generated/model";

export const reassignmentHref = (id: string) => `/portal/counseling/reassignments/${id}`;

const stateLabels: Record<CaseReassignmentStateValue, string> = {
  PENDING: "Waiting for Head approval",
  APPROVED: "Approved",
  DECLINED: "Declined",
  WITHDRAWN: "Withdrawn",
  EXPIRED: "No longer current",
};

export function reassignmentStateLabel(state: CaseReassignmentStateValue): string {
  return stateLabels[state] ?? state;
}

const routeLabels: Record<CaseReassignmentResponse["route"], string> = {
  INDEPENDENT_HEAD: "Independent Head approval",
  DIRECT_OUTGOING_HEAD: "The Head's own case",
  OWNER_TO_HEAD: "Case owner's request to the Head",
};

export function reassignmentRouteLabel(route: CaseReassignmentResponse["route"]): string {
  return routeLabels[route] ?? route;
}

const errorMessages: Record<string, string> = {
  case_continuity_reassignment_request_required:
    "This Appointment is part of a counseling case. Request the reassignment so it follows the case-continuity approval.",
  case_continuity_reassignment_acknowledgement_required: "Confirm that the case stays with its Counselor.",
  case_continuity_reassignment_reason_required: "Enter the reason.",
  case_continuity_reassignment_reason_too_long: "The reason is too long. Shorten it and try again.",
  case_continuity_reassignment_pending: "A reassignment for this Appointment is already waiting for the Head.",
  case_continuity_reassignment_direct: "Reassign it directly. This Counselor needs no case-continuity approval.",
  case_continuity_reassignment_not_case_linked: "This Appointment isn't part of an Active case. Reassign it directly.",
  case_continuity_no_independent_approver:
    "No independent Head is available to approve this. Reschedule or cancel the Appointment instead.",
  case_continuity_receiver_ineligible: "Choose another active Counselor.",
  case_continuity_reassignment_changed: "This request changed. Review the latest version.",
  case_continuity_reassignment_not_pending: "This request has already been decided.",
  case_continuity_reassignment_approval_denied: "Only an independent current Head can decide this request.",
  case_continuity_reassignment_expired:
    "The Appointment or case changed after this request, so it no longer applies. Ask for a new request if the session still needs another Counselor.",
  case_continuity_reassignment_not_found: "This reassignment request isn't available.",
  appointment_time_unavailable: "The selected Counselor isn't available at the Appointment time.",
  appointment_time_conflict: "The selected Counselor already has something scheduled at that time.",
  permission_denied: "You don't have access to this reassignment.",
};

/** Known refusals in plain words; anything else falls back to the caller's message. */
export function reassignmentError(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && Object.hasOwn(errorMessages, code) && errorMessages[code]) || fallback;
}

/** A refusal that means the screen is out of date and should be read again. */
export function reassignmentStale(error: unknown): boolean {
  if (!(error instanceof CompassApiError)) return false;
  const code = readApiErrorCode(error.body);
  return Boolean(
    code &&
      [
        "case_continuity_reassignment_changed",
        "case_continuity_reassignment_not_pending",
        "case_continuity_reassignment_expired",
        "case_continuity_reassignment_pending",
        "case_continuity_reassignment_request_required",
      ].includes(code),
  );
}

/** What the Appointment page says about a pending or just-sent request. */
export function pendingReassignmentNotice(item: Pick<CaseReassignmentResponse, "to_provider" | "from_provider">): string {
  return `Reassignment to ${item.to_provider.display_name} is waiting for Head approval. The Appointment stays with ${item.from_provider.display_name} until then.`;
}

export function caseSessionNotice(caseOwnerName: string): string {
  return `Part of ${caseOwnerName}'s counseling case. Case records stay with ${caseOwnerName}.`;
}
