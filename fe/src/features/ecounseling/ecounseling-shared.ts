import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import {
  ECounselingCaptureStatus,
  ECounselingConsentDecision,
  ECounselingConsentStatus,
  type ConsentResponse,
  type MediaWorkspaceState,
} from "@/lib/api/generated/model";

export function ecounselingErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function ecounselingErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const messages: Record<string, string> = {
    current_student_required: "Only a current Student can approve this consent. You can still decline it.",
    ecounseling_not_found: "This E-Counseling session is not available within your current access.",
    ecounseling_not_permitted: "This E-Counseling action is not available within your current access.",
    ecounseling_appointment_not_eligible: "This Appointment is no longer eligible for E-Counseling.",
    ecounseling_consent_not_found: "That consent is no longer available. Refresh the session state.",
    ecounseling_consent_not_approved: "The required consent is not currently effective.",
    ecounseling_consent_conflict: "The consent state changed. The current session state has been refreshed.",
    ecounseling_media_conflict: "The provider media state changed. The current session state has been refreshed.",
    ecounseling_media_stop_pending: "Media stop is still being reconciled.",
    ecounseling_provider_disabled: "Provider media controls are not enabled. Counseling access is unaffected.",
    ecounseling_provider_unavailable: "The provider could not confirm this media control. Counseling access is unaffected.",
    ecounseling_invalid_provider_response: "The provider could not confirm this media control. Counseling access is unaffected.",
  };
  return (code && messages[code]) || readApiErrorMessage(error.body) || fallback;
}

// A withdrawn consent keeps decision APPROVED; withdrawn_at and effective describe it.
export function consentStatusLabel(
  row: Pick<ConsentResponse, "decision" | "effective" | "withdrawn_at">,
): string {
  if (row.withdrawn_at) return "Withdrawn";
  if (row.decision === ECounselingConsentDecision.APPROVED) {
    return row.effective ? "Approved" : "Not effective";
  }
  if (row.decision === ECounselingConsentDecision.DENIED) return "Declined";
  return "Pending";
}

export const consentProjectionLabels: Record<ECounselingConsentStatus, string> = {
  [ECounselingConsentStatus.NOT_REQUESTED]: "Not requested",
  [ECounselingConsentStatus.PENDING]: "Pending",
  [ECounselingConsentStatus.APPROVED]: "Approved",
  [ECounselingConsentStatus.DENIED]: "Declined",
  [ECounselingConsentStatus.WITHDRAWN]: "Withdrawn",
};

const captureStatusLabels: Record<ECounselingCaptureStatus, string> = {
  [ECounselingCaptureStatus.NOT_STARTED]: "Not started",
  [ECounselingCaptureStatus.START_REQUESTED]: "Starting",
  [ECounselingCaptureStatus.ACTIVE]: "Active",
  [ECounselingCaptureStatus.STOP_REQUESTED]: "Stopping",
  [ECounselingCaptureStatus.STOPPED]: "Stopped",
  [ECounselingCaptureStatus.READY]: "Completed",
  [ECounselingCaptureStatus.ERROR]: "Provider state requires attention",
};

export function captureStatusLabel(status: ECounselingCaptureStatus): string {
  return captureStatusLabels[status];
}

const liveCaptureStates: ReadonlySet<ECounselingCaptureStatus> = new Set([
  ECounselingCaptureStatus.START_REQUESTED,
  ECounselingCaptureStatus.ACTIVE,
  ECounselingCaptureStatus.STOP_REQUESTED,
]);

export function isLiveOrTransitionalCapture(status: ECounselingCaptureStatus): boolean {
  return liveCaptureStates.has(status);
}

export function hasLiveOrTransitionalMedia(media: MediaWorkspaceState | undefined): boolean {
  return Boolean(media && (
    isLiveOrTransitionalCapture(media.recording.capture_status) ||
    isLiveOrTransitionalCapture(media.transcription.capture_status)
  ));
}

export function formatECounselingDateTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
