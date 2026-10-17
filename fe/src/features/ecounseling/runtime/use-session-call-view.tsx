"use client";

import { useEffect } from "react";

import { buttonVariants } from "@/components/ui/button";
import { initialCallSnapshot } from "@/features/ecounseling/call/call-model";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";

import { useActiveECounselingCall, type CallControls } from "./active-call-context";
import { joinBlockedCopy, sessionPath } from "./runtime-model";

const idleCall: CallControls = {
  ...initialCallSnapshot,
  startPreview: async () => {},
  closePreview: async () => {},
  setMicrophone: () => {},
  setCamera: () => {},
  refreshDevices: async () => {},
  selectCamera: async () => {},
  selectMicrophone: async () => {},
  selectSpeaker: async () => {},
};

// The session page's view of the portal's one call (ADR-094). For the Appointment whose call is
// live (or just ended) it is that call; for any other Appointment it is an idle call whose Join
// starts one, unless this tab or another already has a call. While this page shows the full stage
// for the live call, the call dock steps aside. Opening the page never starts a call or device
// preview by itself.
export function useSessionCallView({
  appointmentId,
  participantName,
  endsAt,
}: {
  appointmentId: string;
  participantName: string;
  endsAt?: string;
}) {
  const runtime = useActiveECounselingCall();
  const { presentStage } = runtime;
  const ownsCall = runtime.appointmentId === appointmentId && runtime.state !== "inactive";
  const ownsPreview = runtime.state === "inactive" && runtime.previewAppointmentId === appointmentId;
  const owns = ownsCall || ownsPreview;
  const availability = runtime.availabilityFor(appointmentId);

  useEffect(() => presentStage(appointmentId), [appointmentId, presentStage]);

  const baseCall: CallControls = owns
    ? runtime.state === "activating" ? { ...runtime.call, phase: "requesting" } : runtime.call
    : idleCall;
  const call: CallControls = {
    ...baseCall,
    startPreview: () => runtime.startPreview(appointmentId),
    closePreview: () => runtime.closePreview(appointmentId),
  };
  const blocked = availability === "other-session" || availability === "other-tab" ? availability : null;

  return {
    call,
    // This page's Appointment has the live call: the portal runtime keeps its session state fresh.
    inCall: ownsCall && runtime.live,
    join: () => void runtime.join({ appointmentId, participantName, endsAt }),
    leave: runtime.requestLeave,
    timing: ownsCall ? runtime.timing : { phase: "NORMAL" as const, notice: null, endsAt: endsAt ?? null },
    audio: ownsCall ? runtime.audio : undefined,
    joinBlocked: blocked ? (
      <div className="flex flex-col items-center gap-3">
        <p role="status" className="text-sm font-semibold">{joinBlockedCopy[blocked]}</p>
        {blocked === "other-session" && runtime.appointmentId ? (
          <GuardedPortalLink href={sessionPath(runtime.appointmentId)} className={buttonVariants({ variant: "secondary", className: "border-on-brand/40 bg-transparent text-on-brand hover:bg-on-brand/10" })}>
            Return to active session
          </GuardedPortalLink>
        ) : null}
      </div>
    ) : undefined,
  };
}
