import type { CaseClosureReason, CaseClosureOutcome, CaseReopenReason, CaseClosureBlockerKind } from "@/lib/api/generated/model";
import { caseErrorCode, caseErrorMessage } from "./case-presentation";

export const closureReasonLabels: Record<CaseClosureReason, string> = {
  PLANNED_SUPPORT_CONCLUDED: "Planned support concluded",
  STUDENT_DISCONTINUED: "Student chose to discontinue",
  CONTACT_NOT_REESTABLISHED: "Unable to re-establish contact after documented attempts",
  EXTERNAL_HANDOVER_CONFIRMED: "External service handover confirmed",
  ELIGIBILITY_ENDED: "Institutional service eligibility ended",
};

// Native option labels stay short; the full meaning appears below the field.
export const closureReasonOptions: Record<CaseClosureReason, string> = {
  PLANNED_SUPPORT_CONCLUDED: "Support concluded",
  STUDENT_DISCONTINUED: "Student discontinued",
  CONTACT_NOT_REESTABLISHED: "Contact not restored",
  EXTERNAL_HANDOVER_CONFIRMED: "External handover",
  ELIGIBILITY_ENDED: "Eligibility ended",
};

export const closureOutcomeLabels: Record<CaseClosureOutcome, string> = {
  GOALS_MET: "Goals met",
  GOALS_PARTLY_MET: "Goals partly met",
  GOALS_NOT_MET: "Goals not met",
  NOT_ASSESSED: "Not assessed",
};

export const reopenReasonLabels: Record<CaseReopenReason, string> = {
  SAME_CONCERN_RETURNED: "Same concern returned",
  FURTHER_SUPPORT_NEEDED: "Further support needed",
  CLOSED_IN_ERROR: "Closed in error",
};

export const closureBlockerLabels: Record<CaseClosureBlockerKind, string> = {
  TRANSFER: "Pending transfer",
  COVERAGE: "Pending or current coverage",
  DELEGATED_TASK: "Delegated action awaiting return",
  APPOINTMENT: "Upcoming linked Appointment",
  TASK: "Pending action without an after-closure plan",
};

export function closureSummary(reason: CaseClosureReason, outcome: CaseClosureOutcome): string {
  return reason === "PLANNED_SUPPORT_CONCLUDED" && outcome === "GOALS_MET"
    ? "Support concluded — goals met"
    : `${closureReasonLabels[reason]} · ${closureOutcomeLabels[outcome]}`;
}

export function closureNoteError(reason: CaseClosureReason, note: string): string | null {
  if (note.length > 4000) return "The closure note may contain at most 4,000 characters.";
  if (reason === "CONTACT_NOT_REESTABLISHED" && note.trim().length < 20) return "Describe the documented contact attempts in at least 20 characters.";
  return null;
}

export function closureError(error: unknown, fallback = "This case action couldn't be completed. Review the case and try again."): string {
  switch (caseErrorCode(error)) {
    case "counseling_case_close_blocked": return "Outstanding work prevents closure. Review the current blockers and resolve each through its own workflow.";
    case "counseling_case_close_invalid":
    case "counseling_case_closure_invalid": return "Check the closure reason, outcome and note, then try again.";
    case "counseling_case_reopen_invalid": return "Choose an available reopening reason.";
    case "counseling_case_not_closed": return "This case is already Active. The latest details are now shown.";
    case "case_not_active": return "This case is Closed. Review the latest details before acting.";
    case "counseling_case_post_closure_invalid": return "An after-closure action needs an eligible owner, a due date and confirmation that it is administrative.";
    default: return caseErrorMessage(error, fallback);
  }
}

export function closureRequiresReview(error: unknown): boolean {
  return ["counseling_case_changed", "counseling_case_closed", "case_not_active", "counseling_case_not_closed", "counseling_case_close_blocked"].includes(caseErrorCode(error) ?? "");
}
