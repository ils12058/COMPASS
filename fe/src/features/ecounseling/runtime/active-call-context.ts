"use client";

import { createContext, useContext } from "react";

import type { CallSnapshot } from "@/features/ecounseling/call/call-model";
import type { MediaWorkspaceState } from "@/lib/api/generated/model";

import type { JoinAvailability, RuntimeState } from "./runtime-model";

// Local call controls: they act on the Call Object directly and never on institutional records.
export type CallControls = CallSnapshot & {
  setMicrophone: (on: boolean) => void;
  setCamera: (on: boolean) => void;
  refreshDevices: () => Promise<void>;
  selectCamera: (id: string) => Promise<void>;
  selectMicrophone: (id: string) => Promise<void>;
  selectSpeaker: (id: string) => Promise<void>;
};

export type CaptureKind = "recording" | "transcription";

export type ActiveECounselingCall = {
  role: "STUDENT" | "COUNSELOR" | null;
  state: RuntimeState;
  // A call exists, or is being started or left.
  live: boolean;
  // The Appointment of the current or last call in this portal session, kept in memory only.
  appointmentId: string | null;
  participantName: string | null;
  call: CallControls;
  otherTabActive: boolean;
  availabilityFor: (appointmentId: string) => JoinAvailability;
  join: (target: { appointmentId: string; participantName: string }) => Promise<void>;
  // Leave, with the Counselor's warning when capture is still running.
  requestLeave: () => void;
  // Ends the call without a warning, for sign-out and other confirmed endings.
  end: () => Promise<void>;
  audio: { blocked: boolean; resume: () => void };
  // The latest COMPASS session state for the call, and whether the last refresh confirmed it.
  canonical: { media: MediaWorkspaceState | undefined; current: boolean };
  // The Counselor's protective stop, through the COMPASS backend.
  capture: {
    canStop: Record<CaptureKind, boolean>;
    stopping: Record<CaptureKind, boolean>;
    error: string | null;
    stop: (kind: CaptureKind) => Promise<void>;
  };
  // The full session stage for the active Appointment is on screen; the dock steps aside.
  presentStage: (appointmentId: string) => () => void;
};

export const ActiveECounselingCallContext = createContext<ActiveECounselingCall | null>(null);

export function useActiveECounselingCall(): ActiveECounselingCall {
  const context = useContext(ActiveECounselingCallContext);
  if (!context) throw new Error("useActiveECounselingCall must be used inside the portal's E-Counseling runtime.");
  return context;
}

// For shared portal controls that can render without the runtime, such as in isolated tests.
export function useOptionalActiveECounselingCall(): ActiveECounselingCall | null {
  return useContext(ActiveECounselingCallContext);
}
