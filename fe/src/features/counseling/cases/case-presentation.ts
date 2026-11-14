import type { SortOption } from "@/components/ui/sort-field";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  CounselingCaseOrdering,
  type CounselingCaseEventResponse,
  type CounselingCaseDetailResponse,
  type CounselingCaseOrigin,
  type CounselingCaseSessionRemovalReason,
  type CounselingCaseStatus,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export const CASES_PATH = "/portal/counseling";
export const SESSION_RECORDS_PATH = "/portal/counseling/encounters";

// The backend offers only explicit authorized source relationships. The same session may be
// both an origin session and a linked Appointment's session, so offer it once by record ID.
export function caseSessionOffers(item: Pick<CounselingCaseDetailResponse, "unlinked_origin_session" | "unlinked_appointment_sessions">) {
  const candidates = item.unlinked_origin_session
    ? [item.unlinked_origin_session, ...item.unlinked_appointment_sessions]
    : item.unlinked_appointment_sessions;
  return candidates.filter((candidate, index) => candidates.findIndex(other => other.encounter_id === candidate.encounter_id) === index);
}

export function caseHref(caseId: string): string {
  return `/portal/counseling/cases/${caseId}`;
}

// Opening always starts from a context the Counselor is already authorized for: their own
// Appointment, recorded session or Routine Interview, or a Student chosen through the Counseling
// Student search.
export function openCaseHref(
  context?:
    | { origin: Exclude<CounselingCaseOrigin, "INTAKE">; sourceId: string }
    | { origin: "INTAKE"; studentId?: string },
): string {
  const base = "/portal/counseling/cases/new";
  if (!context) return base;
  if (context.origin === "INTAKE") {
    return context.studentId ? `${base}?student=${encodeURIComponent(context.studentId)}` : base;
  }
  return `${base}?origin=${context.origin}&source=${encodeURIComponent(context.sourceId)}`;
}

// Cases are ongoing work: the one with the latest activity comes first (ADR-090).
export const caseOrderingOptions: readonly SortOption<CounselingCaseOrdering>[] = [
  { value: CounselingCaseOrdering.LATEST_ACTIVITY, label: "Latest activity first" },
  { value: CounselingCaseOrdering.LATEST_OPENED, label: "Newest case first" },
  { value: CounselingCaseOrdering.OLDEST_OPENED, label: "Oldest case first" },
  { value: CounselingCaseOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: CounselingCaseOrdering.STUDENT_DESC, label: "Student Z–A" },
];

export function caseStatusLabel(status: CounselingCaseStatus | string): string {
  switch (status) {
    case "ACTIVE": return "Active";
    case "CLOSED": return "Closed";
    default: return "Not available";
  }
}

export function caseOriginLabel(origin: CounselingCaseOrigin | string): string {
  switch (origin) {
    case "INTAKE": return "Counseling intake";
    case "APPOINTMENT": return "Appointment";
    case "ENCOUNTER": return "Recorded session";
    case "ROUTINE_INTERVIEW": return "Routine Interview";
    default: return "Not available";
  }
}

export const caseSessionRemovalReasons: readonly { value: CounselingCaseSessionRemovalReason; label: string }[] = [
  { value: "BELONGS_TO_ANOTHER_CASE", label: "It belongs to another case" },
  { value: "NOT_PART_OF_THIS_CASE", label: "It isn't part of this case" },
  { value: "LINKED_BY_MISTAKE", label: "It was added by mistake" },
];

function removalReasonPhrase(code: string | null): string {
  switch (code) {
    case "BELONGS_TO_ANOTHER_CASE": return "it belongs to another case";
    case "NOT_PART_OF_THIS_CASE": return "it isn't part of this case";
    case "LINKED_BY_MISTAKE": return "it was added by mistake";
    default: return "";
  }
}

export function sessionCountLabel(count: number): string {
  return count === 1 ? "1 completed session" : `${count} completed sessions`;
}

// One line of case history, written from the event's own facts. Nothing is inferred from the
// case's current state.
export function caseEventSummary(event: Pick<CounselingCaseEventResponse, "kind" | "detail_code" | "encounter_started_at">): string {
  const session = event.encounter_started_at
    ? `Session of ${formatInstitutionalDateTime(event.encounter_started_at)}`
    : "A session";
  switch (event.kind) {
    case "OPENED":
      return event.detail_code ? `Case opened from ${originArticle(event.detail_code)}` : "Case opened";
    case "SESSION_LINKED":
      return `${session} added to the case`;
    case "SESSION_UNLINKED": {
      const reason = removalReasonPhrase(event.detail_code);
      return reason ? `${session} removed from the case: ${reason}` : `${session} removed from the case`;
    }
    default:
      return "Case updated";
  }
}

function originArticle(origin: string): string {
  switch (origin) {
    case "INTAKE": return "a Counseling intake";
    case "APPOINTMENT": return "an Appointment";
    case "ENCOUNTER": return "a recorded session";
    case "ROUTINE_INTERVIEW": return "a Routine Interview";
    default: return "an authorized record";
  }
}

const caseErrors: Record<string, string> = {
  permission_denied: "You can't use Counseling cases.",
  counseling_case_not_found: "You don't have access to this case.",
  counseling_case_source_not_found: "You don't have access to the record this case would start from.",
  counseling_case_session_not_found: "This session isn't available to add or remove. Refresh the case and try again.",
  counseling_case_invalid_request: "Some case details need attention. Review them and try again.",
  counseling_case_source_invalid: "A case can't be opened from this record now.",
  counseling_case_review_required: "Your active cases for this Student changed. Review them before opening a case.",
  counseling_case_closed: "This case is closed, so its sessions can't be changed.",
  counseling_case_changed: "This case changed before your action completed. The latest details are now shown.",
  counseling_case_session_already_linked: "This session already belongs to a case.",
  counseling_case_session_student_mismatch: "This session is for a different Student than the case.",
  counseling_case_reference_exhausted: "A case can't be opened right now. Contact your IT Administrator.",
  counseling_service_not_configured: "Cases can't be opened until the Counseling Service is set up.",
  counseling_not_permitted: "You can't perform this counseling action.",
};

export function caseErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function caseErrorMessage(error: unknown, fallback: string): string {
  const code = caseErrorCode(error);
  return (code && caseErrors[code]) || fallback;
}

// A failed connection or server error doesn't prove the change failed.
export function isUncertainCaseResult(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

// The record changed underneath the reader: reload it and let them review again.
export function isStaleCaseError(error: unknown): boolean {
  const code = caseErrorCode(error);
  return code === "counseling_case_changed" || code === "counseling_case_closed";
}
