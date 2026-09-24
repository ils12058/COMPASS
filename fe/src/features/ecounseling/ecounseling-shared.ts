import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import type { MediaWorkspaceState } from "@/lib/api/generated/model";

export const ECounselingScope = {
  recording: "AUDIO_VIDEO_RECORDING",
  transcription: "LIVE_TRANSCRIPTION",
  storage: "TRANSCRIPT_STORAGE",
} as const;

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

export function consentStatusLabel(row: { decision: string; effective: boolean; withdrawn_at: string | null }): string {
  if (row.withdrawn_at || row.decision === "WITHDRAWN") return "Withdrawn";
  if (row.decision === "APPROVED" && row.effective) return "Approved";
  if (row.decision === "APPROVED") return "Not effective";
  if (row.decision === "DENIED") return "Declined";
  return row.decision === "PENDING" ? "Pending" : row.decision.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function captureStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    NOT_STARTED: "Not started",
    START_REQUESTED: "Starting",
    ACTIVE: "Active",
    STOP_REQUESTED: "Stopping",
    STOPPED: "Stopped",
    READY: "Completed",
    ERROR: "Provider state requires attention",
  };
  return labels[status] ?? "Status unavailable";
}

export function hasLiveOrTransitionalMedia(media: MediaWorkspaceState | undefined): boolean {
  const liveStates = new Set(["START_REQUESTED", "ACTIVE", "STOP_REQUESTED"]);
  return Boolean(media && (
    liveStates.has(media.recording.capture_status) || liveStates.has(media.transcription.capture_status)
  ));
}

export function formatECounselingDateTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
