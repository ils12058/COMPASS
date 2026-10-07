import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
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
    ecounseling_not_found: "This E-Counseling session is unavailable.",
    ecounseling_not_permitted: "You don’t have access to this action.",
    ecounseling_appointment_not_eligible: "E-Counseling is no longer available for this Appointment.",
    ecounseling_consent_not_found: "That consent is no longer available. Refresh the session.",
    ecounseling_consent_not_approved: "The student must approve this media permission before you can start.",
    ecounseling_consent_conflict: "The consent changed. The session has been refreshed.",
    ecounseling_consent_scope_incompatible: "The session's media permission changed. Refresh the session.",
    ecounseling_artifact_not_ready: "The file is still being prepared or was not saved.",
    ecounseling_artifact_disposed: "This file was deleted under an approved retention rule.",
    ecounseling_artifact_unavailable: "The file isn't available right now. Try again.",
    ecounseling_media_conflict: "Recording or transcription changed. The session has been refreshed.",
    ecounseling_media_stop_pending: "Stopping is still being confirmed.",
    ecounseling_provider_disabled: "Recording and transcription are not available for video sessions right now. Counseling is unaffected.",
    ecounseling_provider_unavailable: "The video service could not confirm this change. Counseling is unaffected.",
    ecounseling_invalid_provider_response: "The video service could not confirm this change. Counseling is unaffected.",
  };
  return (code && messages[code]) || fallback;
}

// A withdrawn consent keeps decision APPROVED; withdrawn_at and effective describe it.
export function consentStatusLabel(
  row: Pick<ConsentResponse, "decision" | "effective" | "withdrawn_at">,
): string {
  if (row.withdrawn_at) return "Withdrawn";
  if (row.decision === ECounselingConsentDecision.APPROVED) {
    return row.effective ? "Approved" : "No longer valid";
  }
  if (row.decision === ECounselingConsentDecision.DENIED) return "Declined";
  return "Pending";
}

export const consentProjectionLabels: Record<ECounselingConsentStatus, string> = {
  [ECounselingConsentStatus.NOT_REQUESTED]: "Not requested",
  [ECounselingConsentStatus.PENDING]: "Waiting for consent",
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
  [ECounselingCaptureStatus.ERROR]: "Needs attention",
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

export function hasPreparingMediaFile(media: MediaWorkspaceState | undefined): boolean {
  return Boolean(media && [media.recording, media.transcription].some(
    (item) => item.artifact_status === "PENDING" || item.artifact_status === "PROCESSING" || item.artifact_status === "FAILED",
  ));
}

export function formatECounselingDateTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  return formatInstitutionalDateTime(value);
}
