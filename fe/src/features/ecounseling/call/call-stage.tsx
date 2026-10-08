"use client";

import { LoaderCircle, Maximize, Mic, MicOff, Minimize, PhoneOff, Settings2, Video, VideoOff, WifiLow } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { formatECounselingDateTime } from "@/features/ecounseling/ecounseling-shared";
import { ECounselingJoinState, type MediaWorkspaceState, type ProviderReadiness } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

import { CallControl, CallTray } from "./call-control";
import { activeCallPhases, type ParticipantView } from "./call-model";
import { CaptureIndicators } from "./capture-indicators";
import { DeviceDialog } from "./device-dialog";
import { ParticipantVideo, RemoteAudio } from "./participant-media";
import type { DailyCallControls } from "./use-daily-call";
import { leaveFullscreen, useFullscreen } from "./use-fullscreen";

export function joinAvailabilityMessage(readiness: ProviderReadiness): string | null {
  if (readiness.join_state === ECounselingJoinState.TOO_EARLY) {
    return `You can join starting ${formatECounselingDateTime(readiness.join_available_from)}.`;
  }
  if (readiness.join_state === ECounselingJoinState.CLOSED) return "This session can no longer be joined.";
  if (readiness.join_state === ECounselingJoinState.PROVIDER_DISABLED) {
    return "Video sessions are not available right now. Your Counseling appointment is still available.";
  }
  return null;
}

// What the screen reader hears when the call changes, once per change.
function callAnnouncement(call: DailyCallControls, participantName: string): string {
  switch (call.phase) {
    case "requesting":
    case "joining":
      return "Connecting to the session.";
    case "joined":
      return call.remote ? `Connected with ${participantName}.` : `Joined. Waiting for ${participantName}.`;
    case "reconnecting":
      return "Connection interrupted. Reconnecting.";
    case "left":
      return "You left the call.";
    case "failed":
      return call.failure?.message ?? "The video session isn't connected.";
    default:
      return "";
  }
}

function CameraOff({ name, compact = false }: { name: string; compact?: boolean }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-1 bg-ink px-2 text-center text-on-brand">
      <VideoOff aria-hidden="true" size={compact ? 16 : 28} className="text-on-brand/70" />
      <p className={cn("font-semibold", compact ? "text-xs" : "text-lg")}>{name}</p>
      <p className={cn("text-on-brand/75", compact ? "text-[0.6875rem]" : "text-sm")}>Camera off</p>
    </div>
  );
}

function RemoteParticipantStage({ remote, name }: { remote: ParticipantView | null; name: string }) {
  if (!remote) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-2 px-4 text-center">
        <p className="font-heading text-base font-semibold @[28rem]/stage:text-lg">Waiting for {name}…</p>
        <p className="hidden text-sm text-on-brand/75 @[28rem]/stage:block">You’re in the call. They’ll appear here when they join.</p>
      </div>
    );
  }
  return (
    <div className="relative size-full">
      {remote.video.track && remote.video.playable ? (
        <ParticipantVideo key={remote.key} track={remote.video.track} className="object-contain" />
      ) : (
        <CameraOff name={name} />
      )}
      {remote.audio.off ? (
        <p className="absolute right-2 top-14 inline-flex items-center gap-1 rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold text-on-brand sm:right-3">
          <MicOff aria-hidden="true" size={14} />
          Muted
        </p>
      ) : null}
    </div>
  );
}

function SelfView({ local, cameraOn, microphoneOn }: { local: ParticipantView | null; cameraOn: boolean; microphoneOn: boolean }) {
  const showVideo = cameraOn && local?.video.track && local.video.playable;
  return (
    <figure className="absolute bottom-2 right-2 aspect-video w-[28%] min-w-24 max-w-48 overflow-hidden rounded-sm border border-on-brand/40 bg-ink shadow-float sm:bottom-3 sm:right-3">
      {showVideo ? <ParticipantVideo track={local.video.track} mirrored className="object-cover" /> : <CameraOff name="You" compact />}
      <figcaption className="absolute bottom-1 left-1 inline-flex items-center gap-1 rounded-sm bg-ink/85 px-1.5 py-0.5 text-[0.6875rem] font-semibold text-on-brand">
        {showVideo ? "You" : <span className="sr-only">You, camera off</span>}
        {!microphoneOn ? (
          <>
            <MicOff aria-hidden="true" size={12} />
            <span className="sr-only">, muted</span>
          </>
        ) : null}
      </figcaption>
    </figure>
  );
}

function StageMessage({ children, action, alert = false }: { children: ReactNode; action?: ReactNode; alert?: boolean }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-3 px-6 py-6 text-center sm:gap-4">
      <p role={alert ? "alert" : undefined} className="max-w-md text-sm leading-6 text-on-brand/90 sm:text-base">{children}</p>
      {action}
    </div>
  );
}

// The live session surface (ADR-093): the other participant as the dominant picture, this person's
// self view as a small inset, the call's state, what COMPASS is capturing, and the call controls.
// Daily supplies only media; everything here is COMPASS UI. The stage stays mounted at one place
// in the workspace, so layout presets and dock changes only reflow it.
export function CallStage({
  call,
  participantName,
  readiness,
  canJoin,
  media,
  governedControls,
  devicesInTray = "always",
  onLeaveRequest,
  footer,
  className,
}: {
  call: DailyCallControls;
  participantName: string;
  readiness: ProviderReadiness;
  canJoin: boolean;
  media: MediaWorkspaceState;
  // The assigned Counselor's Record and Transcript controls, which act through the COMPASS backend.
  governedControls?: ReactNode;
  // With six controls, Devices moves to the stage's top bar on narrow stages.
  devicesInTray?: "always" | "when-wide";
  onLeaveRequest?: () => void;
  // Session status that belongs with the call, such as the Counselor's media permission strip.
  footer?: ReactNode;
  className?: string;
}) {
  const stageRef = useRef<HTMLElement>(null);
  const fullscreen = useFullscreen(stageRef);
  const [devicesOpen, setDevicesOpen] = useState(false);
  const inCall = activeCallPhases.has(call.phase);
  const connected = call.phase === "joined" || call.phase === "reconnecting";
  const open = readiness.join_state === ECounselingJoinState.OPEN;
  const availability = joinAvailabilityMessage(readiness);
  const joinAction = open && canJoin ? (label: string) => <Button className="ring-1 ring-on-brand/40" onClick={() => void call.join()}>{label}</Button> : () => null;
  const networkNotice = connected
    ? call.network === "warning" || call.network === "bad"
      ? "Your connection is unstable"
      : call.remote?.network === "bad"
        ? `${participantName}’s connection is unstable`
        : null
    : null;

  function openDevices() {
    leaveFullscreen();
    setDevicesOpen(true);
  }

  function requestLeave() {
    if (onLeaveRequest) {
      leaveFullscreen();
      onLeaveRequest();
    } else {
      void call.leave();
    }
  }

  let main: ReactNode;
  if (connected) {
    main = <RemoteParticipantStage remote={call.remote} name={participantName} />;
  } else if (call.phase === "requesting" || call.phase === "joining" || call.phase === "leaving") {
    main = (
      <div className="flex size-full flex-col items-center justify-center gap-3">
        <LoaderCircle aria-hidden="true" size={28} className="animate-spin text-on-brand/80 motion-reduce:animate-none" />
        <p className="text-sm font-semibold">{call.phase === "leaving" ? "Leaving…" : "Connecting…"}</p>
      </div>
    );
  } else if (call.phase === "failed") {
    main = <StageMessage alert action={joinAction("Try again")}>{call.failure?.message ?? "The video session isn’t connected."}{!open && availability ? ` ${availability}` : ""}</StageMessage>;
  } else if (call.phase === "left") {
    main = <StageMessage action={joinAction("Rejoin")}>{open ? "You left the call. Leaving doesn’t end the Appointment." : availability}</StageMessage>;
  } else if (open) {
    main = canJoin
      ? <StageMessage action={joinAction("Join session")}>Ready to join</StageMessage>
      : <StageMessage>Joining this session is unavailable to this account.</StageMessage>;
  } else {
    main = <StageMessage>{availability}</StageMessage>;
  }

  const devicesControl = (
    <CallControl
      icon={Settings2}
      label="Devices"
      aria-haspopup="dialog"
      disabled={!connected}
      onClick={openDevices}
      className={devicesInTray === "when-wide" ? "hidden @[30rem]/stage:inline-flex" : undefined}
    />
  );

  return (
    <section
      ref={stageRef}
      aria-label="Video call"
      className={cn(
        "@container/stage min-w-0 overflow-hidden rounded-sm border border-brand-line bg-surface-raised [&:fullscreen]:flex [&:fullscreen]:flex-col [&:fullscreen]:rounded-none [&:fullscreen]:border-0",
        className,
      )}
    >
      <div className="relative aspect-video max-h-(--call-stage-max-height) w-full bg-ink text-on-brand [:fullscreen>&]:aspect-auto [:fullscreen>&]:max-h-none [:fullscreen>&]:flex-1">
        {main}

        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2 sm:p-3">
          {/* Names the other person once they are in the call; before that the stage says what is
              happening in its centre. */}
          {connected && call.remote ? (
            <div className="min-w-0 rounded-sm bg-ink/85 px-2.5 py-1">
              <p className="truncate text-sm font-semibold">{participantName}</p>
              <p className="text-xs text-on-brand/80">{call.phase === "reconnecting" ? "Reconnecting…" : "Connected"}</p>
            </div>
          ) : <span />}
          <div className="pointer-events-auto flex shrink-0 gap-1">
            {devicesInTray === "when-wide" && connected ? (
              <button
                type="button"
                aria-haspopup="dialog"
                onClick={openDevices}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-ink/85 px-2.5 text-xs font-semibold hover:bg-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand @[30rem]/stage:hidden"
              >
                <Settings2 aria-hidden="true" size={16} />
                Devices
              </button>
            ) : null}
            {fullscreen.supported ? (
              <button
                type="button"
                onClick={() => void fullscreen.toggle()}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-ink/85 px-2.5 text-xs font-semibold hover:bg-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
              >
                {fullscreen.active ? <Minimize aria-hidden="true" size={16} /> : <Maximize aria-hidden="true" size={16} />}
                <span className={fullscreen.active ? undefined : "sr-only @[30rem]/stage:not-sr-only"}>{fullscreen.active ? "Exit full screen" : "Full screen"}</span>
              </button>
            ) : null}
          </div>
        </div>

        <div className="absolute bottom-2 left-2 flex max-w-[60%] flex-col items-start gap-1 sm:bottom-3 sm:left-3">
          <CaptureIndicators media={media} />
          {call.phase === "reconnecting" ? (
            <p className="inline-flex items-center gap-1.5 rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold"><LoaderCircle aria-hidden="true" size={14} className="animate-spin motion-reduce:animate-none" />Reconnecting…</p>
          ) : null}
          {networkNotice ? (
            <p className="inline-flex items-center gap-1.5 rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold"><WifiLow aria-hidden="true" size={14} />{networkNotice}</p>
          ) : null}
          {connected ? <RemoteAudio track={call.remote?.audio.track ?? null} speakerId={call.devices.speaker} /> : null}
        </div>

        {connected ? <SelfView local={call.local} cameraOn={call.cameraOn} microphoneOn={call.microphoneOn} /> : null}
      </div>

      <p aria-live="polite" className="sr-only">{callAnnouncement(call, participantName)}</p>

      {inCall ? (
        <CallTray>
          <CallControl
            icon={call.microphoneOn ? Mic : MicOff}
            label="Mic"
            accessibleName="Microphone"
            aria-pressed={call.microphoneOn}
            tone={call.microphoneOn ? "default" : "off"}
            problem={Boolean(call.mediaProblem?.microphone)}
            disabled={!connected}
            onClick={() => call.setMicrophone(!call.microphoneOn)}
          />
          <CallControl
            icon={call.cameraOn ? Video : VideoOff}
            label="Camera"
            aria-pressed={call.cameraOn}
            tone={call.cameraOn ? "default" : "off"}
            problem={Boolean(call.mediaProblem?.camera)}
            disabled={!connected}
            onClick={() => call.setCamera(!call.cameraOn)}
          />
          {devicesControl}
          {governedControls}
          <CallControl icon={PhoneOff} label="Leave" accessibleName="Leave session" tone="leave" onClick={requestLeave} />
        </CallTray>
      ) : null}

      {inCall && call.mediaProblem ? (
        <p role="alert" className="border-t border-brand-line px-3 py-2 text-sm text-danger sm:px-4">
          {call.mediaProblem.message}
          {call.mediaProblem.camera && !call.mediaProblem.microphone ? " You can continue with audio." : ""}
        </p>
      ) : null}

      {footer ? <div className="border-t border-brand-line">{footer}</div> : null}

      <DeviceDialog
        open={devicesOpen && connected}
        onOpenChange={setDevicesOpen}
        devices={call.devices}
        onRefresh={call.refreshDevices}
        onSelectCamera={call.selectCamera}
        onSelectMicrophone={call.selectMicrophone}
        onSelectSpeaker={call.selectSpeaker}
      />
    </section>
  );
}
