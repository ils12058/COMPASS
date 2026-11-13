import {
  CaseContinuityReason, CaseTaskDisposition, CaseAppointmentDisposition,
  CaseAppointmentRetentionReason, CaseArrangementDecisionReason,
  type CaseTransferSummary, type CaseAuthorizationRoute,
} from "@/lib/api/generated/model";
import { caseErrorCode } from "@/features/counseling/cases/case-presentation";

export const transferHref = (id: string) => `/portal/counseling/transfers/${encodeURIComponent(id)}`;
export const transferPrepareHref = (caseId: string) => `/portal/counseling/cases/${encodeURIComponent(caseId)}/transfer`;
export const continuityReasonLabels: Record<CaseContinuityReason, string> = {
  IMPARTIALITY_CONCERN: "Potential conflict of interest or impartiality concern",
  PLANNED_ABSENCE: "Planned absence", UNEXPECTED_ABSENCE: "Unexpected absence",
  TEMPORARY_SUPPORT: "Temporary support", SERVICE_RESPONSIBILITY_CHANGE: "Service responsibility change",
};
export const taskDispositionLabels: Record<CaseTaskDisposition, string> = {
  TRANSFER: "Transfer with the case", RETAIN: "Retain with the current assignee",
  HAND_OVER_AS_NEW: "Hand over as a new case action", RESOLVE_FIRST: "Complete or cancel first",
};
export const appointmentDispositionLabels: Record<CaseAppointmentDisposition, string> = {
  REASSIGN: "Reassign through Appointments", RESCHEDULE: "Reschedule through Appointments",
  CANCEL: "Cancel through Appointments", RETAIN_WITH_PROVIDER: "Retain with the provider",
};
export const retentionReasonLabels: Record<CaseAppointmentRetentionReason, string> = {
  CONTINUING_SUPPORT: "Continuing support with this provider",
  ARRANGED_WITH_STUDENT: "Arrangement made with the Student", SEPARATE_SERVICE_WORK: "Separate planned work",
};
export const decisionReasonLabels: Record<CaseArrangementDecisionReason, string> = {
  NO_CAPACITY: "Unable to take the work", INFORMATION_INCOMPLETE: "More information is needed",
  ARRANGEMENT_NOT_SUITABLE: "Another arrangement is needed", REQUEST_WITHDRAWN: "Request withdrawn",
  REVIEW_WINDOW_ENDED: "Review window ended",
};
export function arrangementLabel(item: CaseTransferSummary) {
  if (item.state === "PREPARED") return item.waiting_for ? "Waiting for Head approval" : "Prepared — ready for review";
  if (item.state === "AUTHORIZED") return `Waiting for ${item.receiving_counselor.display_name} to accept`;
  return ({ ACCEPTED: "Accepted", DECLINED: "Declined — another arrangement is needed", CANCELLED: "Cancelled — another arrangement is needed", EXPIRED: "Expired — another arrangement is needed" })[item.state];
}
export function authorizationLabel(route: CaseAuthorizationRoute | null) {
  if (route === "OWNER_TO_HEAD") return "Personally requested by the primary Counselor; no independent Head authorization.";
  if (route === "DIRECT_OUTGOING_HEAD") return "The Head directly authorizes her own outgoing case.";
  return "An independent Head authorizes this arrangement before the receiving Counselor accepts.";
}
export function enumChoice<T extends string>(options: readonly T[], value: string): T | undefined {
  return options.find(option => option === value);
}
const errorMessages: Record<string, string> = {
  case_continuity_handoff_required: "Submit the structured handoff or have an eligible Head record why it is unavailable.",
  case_continuity_handoff_content_invalid: "Review the handoff text and keep the total narrative within 12,000 characters.",
  case_continuity_handoff_content_required: "Include the concern and purpose, and what the receiver should do next.",
  case_continuity_handoff_immutable: "The submitted handoff is immutable. Add an attributed addendum.",
  case_continuity_handoff_not_found: "The protected handoff is unavailable to this account or the review ended.",
  case_continuity_handoff_unavailable: "The protected handoff is unavailable. Try again when access is restored.",
  case_continuity_handoff_write_denied: "Only the current outgoing Counselor can write this handoff.",
  case_continuity_handoff_addendum_denied: "An authorized author or current case owner must add this information.",
  case_continuity_handoff_exception_denied: "An eligible Head must record the exception. The receiving Head cannot record it.",
  case_continuity_session_unavailable: "Sign in again to open this protected handoff.",
  case_continuity_no_independent_approver: "No independent approver is available.",
  case_continuity_receiver_ineligible: "The receiving Counselor is no longer eligible. Choose another Counselor.",
  case_continuity_changed: "This arrangement changed. The latest details are now shown; review them before acting.",
  case_continuity_case_changed: "This case changed. Review its latest pending work before saving.",
  case_continuity_owner_changed: "The primary Counselor changed. Another arrangement is needed.",
  case_continuity_case_not_active: "This case is no longer Active.",
  case_continuity_case_not_found: "You don't have access to prepare an arrangement for this case.",
  case_continuity_arrangement_not_found: "This arrangement isn't available to your account.",
  case_continuity_access_denied: "Case continuity is unavailable to your account.",
  case_continuity_review_expired: "The review window ended. Another arrangement is needed.",
  case_continuity_terminal_arrangement: "This review ended. Another arrangement is needed.",
  case_continuity_authorization_changed: "The authorization route changed. Arrange a fresh review.",
  case_continuity_review_required: "This arrangement needs fresh authorization before acceptance.",
  case_continuity_coverage_conflict: "Conflicting coverage must end explicitly or expire before this transfer can be accepted.",
  case_continuity_task_plan_incomplete: "Every pending case action needs a reviewed disposition.",
  case_continuity_task_changed: "A case action changed. Review the task plan again.",
  case_continuity_task_resolution_required: "Complete or cancel actions marked Complete or cancel first through Follow-ups before acceptance.",
  case_continuity_appointment_plan_incomplete: "Every upcoming linked Appointment needs a reviewed plan.",
  case_continuity_appointment_changed: "An Appointment changed. Review the appointment plan again.",
  case_continuity_appointment_action_required: "Complete the reviewed reassignment, reschedule or cancellation through Appointments before acceptance.",
  case_continuity_conflicted_provider: "An impartiality-related transfer cannot retain the outgoing Counselor as provider.",
  case_continuity_task_disposition_forbidden: "A task disposition is no longer available. Review the plan.",
  case_continuity_work_busy: "The case's work is being changed. Review it again.",
  case_continuity_authority_busy: "Account authority is being updated. Review the arrangement again.",
};
export function continuityError(error: unknown, fallback = "The arrangement couldn't be saved. Review the details and try again.") {
  const code = caseErrorCode(error);
  return code && Object.hasOwn(errorMessages, code) ? errorMessages[code] : fallback;
}
export function continuityStale(error: unknown) {
  const code = caseErrorCode(error);
  return Boolean(code && ["case_continuity_changed", "case_continuity_owner_changed", "case_continuity_review_expired", "case_continuity_terminal_arrangement", "case_continuity_authorization_changed", "case_continuity_case_not_active"].includes(code));
}
