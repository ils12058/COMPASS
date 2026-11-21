import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { CounselorBookingRequestState } from "@/lib/api/generated/model";

export const COUNSELOR_BOOKING_HELP_TEXT =
  "You can book with your College's counselor. To see a different counselor, ask the Head Guidance Counselor.";

export const COUNSELOR_REQUEST_PENDING_LABEL = "Waiting for the Head Guidance Counselor";

const requestErrorMessages: Record<string, string> = {
  appointment_counselor_not_permitted:
    "You can book only with your College's counselor or a counselor approved by the Head Guidance Counselor.",
  head_guidance_unavailable:
    "Requests for a different counselor aren't available right now. Please contact the Guidance Office.",
  counselor_request_pending:
    "You already have a request waiting for the Head Guidance Counselor.",
  counselor_request_changed:
    "This record was updated before your action completed. The latest details are now shown.",
  counselor_request_conflict:
    "This request or approval can no longer be updated.",
  counselor_request_not_found:
    "This counselor request or approval could not be found.",
  counselor_request_content_unavailable:
    "The confidential reason couldn't be loaded right now. Try again later.",
  invalid_counselor_request:
    "Review your selection and try again.",
  permission_denied:
    "You don't have permission to perform this action.",
};

export function counselorRelationshipLabel(counselor: {
  is_default: boolean;
  is_head_approved?: boolean;
}): string | null {
  if (counselor.is_default) return "Assigned to you";
  if (counselor.is_head_approved) return "Approved by the Head Guidance Counselor";
  return null;
}

export function counselorRequestStateLabel(state: string): string {
  switch (state) {
    case CounselorBookingRequestState.PENDING:
      return COUNSELOR_REQUEST_PENDING_LABEL;
    case CounselorBookingRequestState.APPROVED:
      return "Approved";
    case CounselorBookingRequestState.DECLINED:
      return "Declined";
    default:
      return "Status unavailable";
  }
}

export function studentCollegeLabel(student: {
  college_name: string | null;
  campus_name: string | null;
}): string {
  if (student.college_name && student.campus_name) {
    return `${student.college_name} · ${student.campus_name}`;
  }
  return student.college_name ?? "No current College recorded";
}

export function counselorRequestErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code && requestErrorMessages[code]) return requestErrorMessages[code];
  return fallback;
}

export function isCounselorRequestStaleError(error: unknown): boolean {
  if (!(error instanceof CompassApiError)) return false;
  const code = readApiErrorCode(error.body);
  return code === "counselor_request_changed" || code === "counselor_request_conflict";
}
