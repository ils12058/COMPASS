import type { CallPhase } from "@/features/ecounseling/call/call-model";
import {
  ECounselingCaptureStatus,
  ECounselingConsentStatus,
  type MediaWorkspaceState,
} from "@/lib/api/generated/model";

// The portal runtime's own state (ADR-094), separate from what COMPASS records about capture.
//   inactive      no call has been started in this portal session (or it was cleared)
//   activating    Join was pressed; checking that no other tab owns a call
//   joining       a credential is being requested or Daily is connecting
//   active        connected
//   reconnecting  connected, but the network is being restored
//   leaving       this person pressed Leave
//   ended         the call ended; the session page offers Rejoin
//   failed        the attempt or the call failed; the session page offers Try again
export type RuntimeState = "inactive" | "activating" | "joining" | "active" | "reconnecting" | "leaving" | "ended" | "failed";

export function runtimeState({ activated, claiming, phase }: { activated: boolean; claiming: boolean; phase: CallPhase }): RuntimeState {
  if (!activated) return "inactive";
  if (claiming) return "activating";
  switch (phase) {
    case "requesting":
    case "joining":
      return "joining";
    case "joined":
      return "active";
    case "reconnecting":
      return "reconnecting";
    case "leaving":
      return "leaving";
    case "left":
      return "ended";
    case "failed":
      return "failed";
    default:
      return "inactive";
  }
}

// A call exists, or is being started or left: the runtime keeps observing COMPASS state, keeps the
// tab's cross-tab lease, warns before the document unloads, and shows the dock off the session page.
export function isLiveRuntime(state: RuntimeState): boolean {
  return state === "activating" || state === "joining" || state === "active" || state === "reconnecting" || state === "leaving";
}

export function isConnected(phase: CallPhase): boolean {
  return phase === "joined" || phase === "reconnecting";
}

// The expanded session for an Appointment. The route identifies only the COMPASS resource; call
// state never enters the URL.
const SESSION_ROUTE = /^\/portal\/e-counseling\/([^/?#]+)\/?$/;

export function sessionPath(appointmentId: string): string {
  return `/portal/e-counseling/${encodeURIComponent(appointmentId)}`;
}

export function sessionAppointmentFromPath(pathname: string | null | undefined): string | null {
  const match = pathname ? SESSION_ROUTE.exec(pathname) : null;
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function isSessionRoute(pathname: string | null | undefined, appointmentId: string | null | undefined): boolean {
  return Boolean(appointmentId) && sessionAppointmentFromPath(pathname) === appointmentId;
}

// Whether Join is possible for an Appointment from this tab, and if not, why. One portal runtime
// holds at most one call; another tab's advisory lease also blocks a new one.
export type JoinAvailability = "available" | "this-session" | "other-session" | "other-tab";

export function joinAvailability({
  appointmentId,
  activeAppointmentId,
  state,
  otherTabActive,
}: {
  appointmentId: string;
  activeAppointmentId: string | null;
  state: RuntimeState;
  otherTabActive: boolean;
}): JoinAvailability {
  if (isLiveRuntime(state)) return activeAppointmentId === appointmentId ? "this-session" : "other-session";
  return otherTabActive ? "other-tab" : "available";
}

export const joinBlockedCopy: Record<"other-session" | "other-tab", string> = {
  "other-session": "You’re already in another E-Counseling session.",
  "other-tab": "Another COMPASS tab has an active E-Counseling session.",
};

export type CaptureSafetyState = "starting" | "active" | "stopping" | "uncertain" | "terminal";

// The workspace has no error certainty/cessation projection. ERROR therefore remains uncertain.
// Until EC-01 changes the backend, transcription STOPPED can mean only a REST acknowledgment.
export function captureSafetyState(kind: "recording" | "transcription", status: ECounselingCaptureStatus): CaptureSafetyState {
  switch (status) {
    case ECounselingCaptureStatus.START_REQUESTED: return "starting";
    case ECounselingCaptureStatus.ACTIVE: return "active";
    case ECounselingCaptureStatus.STOP_REQUESTED: return "stopping";
    case ECounselingCaptureStatus.ERROR: return "uncertain";
    case ECounselingCaptureStatus.STOPPED: return kind === "transcription" ? "uncertain" : "terminal";
    case ECounselingCaptureStatus.NOT_STARTED:
    case ECounselingCaptureStatus.READY: return "terminal";
    default: return "uncertain";
  }
}

// Only capture types, without names, references or other protected session details. Safe to retain
// as a warning when access is lost; local call cleanup is never evidence of capture cessation.
export function activeCaptureKinds(media: MediaWorkspaceState | undefined): Array<"recording" | "transcription"> {
  if (!media) return [];
  return (["recording", "transcription"] as const).filter((kind) => captureSafetyState(kind, media[kind].capture_status) !== "terminal");
}

export function captureCessationWarning(kinds: ReadonlyArray<"recording" | "transcription">, action: "leave" | "sign-out" | "access-loss"): string | null {
  if (!kinds.length) return null;
  const both = kinds.length > 1;
  const subject = both ? "Recording and transcription have" : kinds[0] === "recording" ? "Recording has" : "Transcription has";
  const capture = both ? "recording or transcription" : kinds[0];
  const consequence = action === "leave" ? "Leaving the call may not stop" : action === "sign-out" ? "Signing out may not stop" : "Ending your local call may not stop";
  return `${subject} not been confirmed as stopped. ${consequence} ${capture}. Please confirm ${both ? "their" : "its"} status.`;
}

// A decision the Student still has to make, from the COMPASS session state. The dock only points to
// it; the explanation and the decision stay on the session page and in its confirmation.
export function pendingConsentCue(media: MediaWorkspaceState | undefined): string | null {
  if (!media) return null;
  const pending = (status: ECounselingConsentStatus) => status === ECounselingConsentStatus.PENDING;
  if (pending(media.recording.consent_status) || pending(media.transcription.consent_status)) return "Media permission requested";
  if (pending(media.transcription.storage_consent_status)) return "Transcript storage permission requested";
  return null;
}

// The Student withdrew or declined while capture was still running: the dock says why it is stopping.
export function consentEndedNotice(media: MediaWorkspaceState | undefined): string | null {
  if (!media) return null;
  const ended = (status: ECounselingConsentStatus) => status === ECounselingConsentStatus.WITHDRAWN || status === ECounselingConsentStatus.DENIED;
  const stopping = [media.recording.capture_status, media.transcription.capture_status].some(
    (status) => status === ECounselingCaptureStatus.STOP_REQUESTED || status === ECounselingCaptureStatus.ACTIVE,
  );
  return stopping && (ended(media.recording.consent_status) || ended(media.transcription.consent_status)) ? "The student withdrew media permission." : null;
}
