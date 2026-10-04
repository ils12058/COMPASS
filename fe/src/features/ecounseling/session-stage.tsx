"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { DailySessionFrame } from "@/features/ecounseling/daily-session-frame";
import {
  captureStatusLabel,
  ecounselingErrorMessage,
  formatECounselingDateTime,
} from "@/features/ecounseling/ecounseling-shared";
import { useECounselingCreateJoinCredential } from "@/lib/api/generated/e-counseling/e-counseling";
import {
  ECounselingCaptureStatus,
  ECounselingJoinState,
  type JoinCredentialResponse,
  type MediaWorkspaceState,
  type ProviderReadiness,
} from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

function joinAvailabilityMessage(readiness: ProviderReadiness): string | null {
  if (readiness.join_state === ECounselingJoinState.TOO_EARLY) {
    return `You can join starting ${formatECounselingDateTime(readiness.join_available_from)}.`;
  }
  if (readiness.join_state === ECounselingJoinState.CLOSED) {
    return "This session can no longer be joined.";
  }
  if (readiness.join_state === ECounselingJoinState.PROVIDER_DISABLED) {
    return "Video sessions are not available right now. Your Counseling appointment is still available.";
  }
  return null;
}

function joinReadinessLabel(readiness: ProviderReadiness): string {
  if (readiness.join_state === ECounselingJoinState.TOO_EARLY) {
    return `Opens ${formatECounselingDateTime(readiness.join_available_from)}`;
  }
  if (readiness.join_state === ECounselingJoinState.OPEN) return "Ready to join";
  if (readiness.join_state === ECounselingJoinState.CLOSED) return "Closed";
  return "Unavailable right now";
}

export type SessionJoin = ReturnType<typeof useSessionJoin>;

// The join credential and the page's one Daily frame. A credential is requested only when the
// participant joins, is handed to a newly mounted frame, and is cleared as soon as that frame joins
// or fails; each join mounts a fresh frame (`frameGeneration`). `onCallChange` tells the workspace
// whether the call is joined, which keeps its session state refreshing during the call.
export function useSessionJoin({
  appointmentId,
  refetchWorkspace,
  onCallChange,
}: {
  appointmentId: string;
  refetchWorkspace: () => Promise<unknown>;
  onCallChange: (joined: boolean) => void;
}) {
  const [credential, setCredential] = useState<JoinCredentialResponse | null>(null);
  const [showDailyFrame, setShowDailyFrame] = useState(false);
  const [frameGeneration, setFrameGeneration] = useState(0);
  const [joinError, setJoinError] = useState<string | null>(null);
  const joinCredential = useECounselingCreateJoinCredential({ mutation: { retry: false } });
  const joinMutationRef = useRef(joinCredential);

  useEffect(() => { joinMutationRef.current = joinCredential; }, [joinCredential]);
  useEffect(() => () => joinMutationRef.current.reset(), []);

  async function requestJoin() {
    setJoinError(null);
    try {
      const result = await joinCredential.mutateAsync({ appointmentId });
      setCredential(result.data);
      setFrameGeneration((generation) => generation + 1);
      setShowDailyFrame(true);
    } catch (error) {
      joinCredential.reset();
      setJoinError(ecounselingErrorMessage(error, "A secure session could not be opened. Refresh the session state and try again."));
      void refetchWorkspace();
    }
  }

  return {
    credential,
    showDailyFrame,
    frameGeneration,
    joinError,
    joining: joinCredential.isPending,
    requestJoin,
    onJoined: () => {
      setCredential(null);
      joinCredential.reset();
      onCallChange(true);
    },
    onLeft: () => {
      onCallChange(false);
      setShowDailyFrame(false);
      setCredential(null);
      joinCredential.reset();
    },
    onFailed: () => {
      setJoinError("The video session could not be opened. Request a fresh join to try again.");
      onCallChange(false);
      setShowDailyFrame(false);
      setCredential(null);
      joinCredential.reset();
      void refetchWorkspace();
    },
  };
}

// A capture status, with an active capture marked so it is noticed. Recording uses the danger tone
// that people read as "recording"; transcription uses information.
export function CaptureState({ status, live }: { status: ECounselingCaptureStatus; live: "recording" | "transcription" }) {
  if (status === ECounselingCaptureStatus.ACTIVE) {
    return (
      <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
        <span aria-hidden="true" className={cn("size-2 rounded-full", live === "recording" ? "bg-danger" : "bg-info")} />
        Active
      </span>
    );
  }
  return (
    <span className={status === ECounselingCaptureStatus.ERROR ? "font-semibold text-danger" : "text-ink"}>
      {captureStatusLabel(status)}
    </span>
  );
}

// What the provider is capturing right now, from the canonical capture state. Consent alone never
// shows here as activity.
function SessionMediaStatus({ media }: { media: MediaWorkspaceState }) {
  return (
    <div className="border-t border-brand-line px-4 py-3 sm:px-5">
      <dl aria-live="polite" className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1.5 text-sm">
        <dt className="text-muted">Recording</dt>
        <dd><CaptureState status={media.recording.capture_status} live="recording" /></dd>
        <dt className="text-muted">Transcription</dt>
        <dd><CaptureState status={media.transcription.capture_status} live="transcription" /></dd>
      </dl>
      <p className="mt-2 text-xs leading-5 text-muted">
        COMPASS shows media status only. Transcript text, playback, and downloads are not available here.
      </p>
    </div>
  );
}

// The live part of the session: the video or the way into it, whether it can be joined, and what is
// being captured. On a wide workspace the feature keeps this in view (sticky) while its working
// area scrolls beside it. The Daily frame always renders at the same place in this tree, so layout
// changes around it, such as the portal dock collapsing, only reflow it.
export function SessionStage({
  readiness,
  media,
  canJoin,
  inCall,
  join,
  className,
}: {
  readiness: ProviderReadiness;
  media: MediaWorkspaceState;
  canJoin: boolean;
  inCall: boolean;
  join: SessionJoin;
  className?: string;
}) {
  const open = readiness.join_state === ECounselingJoinState.OPEN;
  const unavailableMessage = joinAvailabilityMessage(readiness);
  const label = join.showDailyFrame ? (inCall ? "In session" : "Connecting") : joinReadinessLabel(readiness);

  return (
    <Panel aria-labelledby="e-counseling-stage-heading" className={cn("overflow-hidden", className)}>
      <PanelHeader
        title="Session"
        titleId="e-counseling-stage-heading"
        actions={<p className="text-sm font-medium text-muted">{label}</p>}
      />
      <div className="p-3 sm:p-4">
        {join.showDailyFrame ? (
          <DailySessionFrame
            key={join.frameGeneration}
            credential={join.credential}
            onJoined={join.onJoined}
            onLeft={join.onLeft}
            onFailed={join.onFailed}
          />
        ) : open ? (
          // The join surface keeps the video's shape, so joining does not move the page.
          <div className="flex aspect-video min-h-48 flex-col items-center justify-center rounded-sm border border-brand-line bg-surface-muted px-5 text-center">
            <p className="max-w-sm text-sm leading-6 text-muted">The secure video room opens when you join.</p>
            <Button
              className="mt-3"
              disabled={!canJoin || join.joining || inCall}
              onClick={() => void join.requestJoin()}
            >
              {join.joining ? "Preparing secure session…" : "Join session"}
            </Button>
          </div>
        ) : unavailableMessage ? (
          <p role="status" className="rounded-sm bg-surface-subtle px-4 py-3 text-sm leading-6 text-ink">
            {unavailableMessage}
          </p>
        ) : null}
        {join.joinError ? <p role="alert" className="mt-3 text-sm text-danger">{join.joinError}</p> : null}
      </div>
      <SessionMediaStatus media={media} />
    </Panel>
  );
}
