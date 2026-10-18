"use client";

import { Clock, LoaderCircle, Maximize, Mic, MicOff, Minimize, PhoneOff, Settings2, Video, VideoOff, WifiLow } from "lucide-react";
import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { formatECounselingDateTime } from "@/features/ecounseling/ecounseling-shared";
import { ECounselingJoinState, type MediaWorkspaceState, type ProviderReadiness } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

import { CallControl, CallTray } from "./call-control";
import { activeCallPhases, previewCallPhases, type ParticipantView } from "./call-model";
import { CaptureIndicators } from "./capture-indicators";
import { DeviceDialog } from "./device-dialog";
import type { CallControls } from "@/features/ecounseling/runtime/active-call-context";
import type { ActiveECounselingTiming } from "@/features/ecounseling/runtime/session-timing";

import { ParticipantVideo, PlayAudioPrompt } from "./participant-media";
import { PreJoinDeviceCheck, PreJoinDeviceDiagnostics } from "./prejoin-device-check";
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
function callAnnouncement(call: CallControls, participantName: string): string {
  switch (call.phase) {
    case "starting-preview":
      return "Starting local device check.";
    case "preview":
      return "Checking devices. Local preview only; no one else can see or hear you.";
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
      return call.deviceCheckCompleted ? "Device check complete. Ready to join." : "";
  }
}

function CameraOff({ name, photoUrl, photoUpdatedAt, compact = false, status = "Camera off" }: { name: string; photoUrl?: string | null; photoUpdatedAt?: string | null; compact?: boolean; status?: string }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-1 bg-ink px-2 text-center text-on-brand">
      <PersonAvatar displayName={name} photoUrl={photoUrl} photoUpdatedAt={photoUpdatedAt} size={compact ? "compact" : "large"} />
      <VideoOff aria-hidden="true" size={compact ? 16 : 28} className="text-on-brand/70" />
      <p className={cn("font-semibold", compact ? "text-xs" : "text-lg")}>{name}</p>
      <p className={cn("text-on-brand/75", compact ? "text-[0.6875rem]" : "text-sm")}>{status}</p>
    </div>
  );
}

function RemoteParticipantStage({ remote, name, photoUrl, photoUpdatedAt }: { remote: ParticipantView | null; name: string; photoUrl?: string | null; photoUpdatedAt?: string | null }) {
  if (!remote) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-2 px-4 text-center">
        <p className="font-heading text-base font-semibold @[28rem]/stage:text-lg">Waiting for {name}…</p>
        <p className="hidden text-sm text-on-brand/75 @[28rem]/stage:block">You’re in the call. They’ll appear here when they join.</p>
      </div>
    );
  }
  return (
    <div className="relative size-full min-h-0 min-w-0">
      {remote.video.track && remote.video.playable ? (
        <ParticipantVideo key={remote.key} track={remote.video.track} className="object-contain" />
      ) : (
        <CameraOff name={name} photoUrl={photoUrl} photoUpdatedAt={photoUpdatedAt} />
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

function SelfView({ local, cameraOn, microphoneOn, name, photoUrl, photoUpdatedAt }: { local: ParticipantView | null; cameraOn: boolean; microphoneOn: boolean; name: string; photoUrl?: string | null; photoUpdatedAt?: string | null }) {
  const showVideo = cameraOn && local?.video.track && local.video.playable;
  return (
    <figure className="absolute bottom-2 right-2 aspect-video w-[28%] min-w-24 max-w-48 overflow-hidden rounded-sm border border-on-brand/40 bg-ink shadow-float sm:bottom-3 sm:right-3">
      {showVideo ? <ParticipantVideo track={local.video.track} mirrored className="object-cover" /> : <CameraOff name={name} photoUrl={photoUrl} photoUpdatedAt={photoUpdatedAt} compact />}
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

function StageMessage({ children, detail, action, alert = false }: { children: ReactNode; detail?: ReactNode; action?: ReactNode; alert?: boolean }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-3 px-6 py-6 text-center sm:gap-4">
      <div className="space-y-1">
        <p role={alert ? "alert" : undefined} className="max-w-md text-sm leading-6 text-on-brand/90 sm:text-base">{children}</p>
        {detail ? <p className="text-xs text-on-brand/75">{detail}</p> : null}
      </div>
      {action}
    </div>
  );
}

// The live session surface (ADR-093): the other participant as the dominant picture, this person's
// self view as a small inset, the call's state, what COMPASS is capturing, and the call controls.
// Daily supplies only media; everything here is COMPASS UI. It is a view of the portal's one call
// (ADR-094): mounting or unmounting it never joins or leaves, and the other person's audio plays
// from the portal runtime, not from here. The stage stays mounted at one place in the workspace,
// so layout presets only reflow it.
export function CallStage({
  call,
  participantName,
  participantPhotoUrl,
  participantPhotoUpdatedAt,
  selfName,
  selfPhotoUrl,
  selfPhotoUpdatedAt,
  readiness,
  canJoin,
  media,
  governedControls,
  devicesInTray = "always",
  onJoin,
  onLeave,
  joinBlocked,
  audio,
  timing,
  footer,
  className,
}: {
  call: CallControls;
  participantName: string;
  participantPhotoUrl?: string | null;
  participantPhotoUpdatedAt?: string | null;
  selfName: string;
  selfPhotoUrl?: string | null;
  selfPhotoUpdatedAt?: string | null;
  readiness: ProviderReadiness;
  canJoin: boolean;
  media: MediaWorkspaceState;
  // The assigned Counselor's Record and Transcript controls, which act through the COMPASS backend.
  governedControls?: ReactNode;
  // With six controls, Devices moves to the stage's top bar on narrow stages.
  devicesInTray?: "always" | "when-wide";
  onJoin: () => void;
  // Leave, with the portal runtime's warning when the Counselor's capture is still running.
  onLeave: () => void;
  // Shown instead of Join when this tab or another already has a call.
  joinBlocked?: ReactNode;
  audio?: { blocked: boolean; resume: () => void };
  // Scheduled-end warnings and overtime awareness projection (EC-1 Option A).
  timing?: ActiveECounselingTiming;
  // Session status that belongs with the call, such as the Counselor's media permission strip.
  footer?: ReactNode;
  className?: string;
}) {
  const stageRef = useRef<HTMLElement>(null);
  const checkDevicesButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusToCheckDevicesRef = useRef(false);
  const fullscreen = useFullscreen(stageRef);
  const [devicesOpen, setDevicesOpen] = useState(false);
  const inCall = activeCallPhases.has(call.phase);
  const inPreview = previewCallPhases.has(call.phase);
  const connected = call.phase === "joined" || call.phase === "reconnecting";
  const open = readiness.join_state === ECounselingJoinState.OPEN;
  const availability = joinAvailabilityMessage(readiness);
  const canCheckDevices =
    canJoin &&
    !joinBlocked &&
    readiness.join_state !== ECounselingJoinState.CLOSED &&
    readiness.join_state !== ECounselingJoinState.PROVIDER_DISABLED;

  useEffect(() => {
    if (inPreview && !canCheckDevices) {
      void call.closePreview();
    }
  }, [call, canCheckDevices, inPreview]);

  useEffect(() => {
    if (!inPreview && returnFocusToCheckDevicesRef.current) {
      returnFocusToCheckDevicesRef.current = false;
      checkDevicesButtonRef.current?.focus();
    }
  }, [inPreview]);

  const joinOnlyAction = (label: string) =>
    joinBlocked ?? (open && canJoin ? <Button className="ring-1 ring-on-brand/40" onClick={onJoin}>{label}</Button> : null);

  const checkDevicesButton = canCheckDevices ? (
    <Button
      ref={checkDevicesButtonRef}
      type="button"
      variant="secondary"
      className="border-on-brand/40 bg-transparent text-on-brand hover:bg-on-brand/10"
      onClick={() => void call.startPreview()}
    >
      Check devices
    </Button>
  ) : null;

  const stageActions = (label: string) => {
    if (joinBlocked) return joinBlocked;
    const primaryJoin = open && canJoin ? <Button className="ring-1 ring-on-brand/40" onClick={onJoin}>{label}</Button> : null;
    if (!primaryJoin && !checkDevicesButton) return null;
    return (
      <div className="flex flex-wrap items-center justify-center gap-2">
        {primaryJoin}
        {checkDevicesButton}
      </div>
    );
  };

  const deviceCheckSummary = call.deviceCheckCompleted
    ? `Device check complete · ${call.cameraOn ? "Camera on" : "Camera off"}, ${call.microphoneOn ? "Mic on" : "Mic off"}`
    : undefined;

  const networkNotice = connected
    ? call.network === "warning" || call.network === "bad"
      ? "Your connection is unstable"
      : call.remote?.network === "bad"
        ? `${participantName}’s connection is unstable`
        : null
    : null;

  function openDevices(event?: MouseEvent<HTMLButtonElement>) {
    // Safari does not focus buttons on pointer click; remember this opener for the dialog.
    event?.currentTarget.focus();
    leaveFullscreen();
    setDevicesOpen(true);
  }

  function requestLeave() {
    leaveFullscreen();
    onLeave();
  }

  function closePreviewAndRestoreFocus() {
    returnFocusToCheckDevicesRef.current = true;
    void call.closePreview();
  }

  let main: ReactNode;
  if (connected) {
    main = <RemoteParticipantStage remote={call.remote} name={participantName} photoUrl={participantPhotoUrl} photoUpdatedAt={participantPhotoUpdatedAt} />;
  } else if (call.phase === "requesting" || call.phase === "joining" || call.phase === "leaving") {
    main = (
      <div className="flex size-full flex-col items-center justify-center gap-3">
        <LoaderCircle aria-hidden="true" size={28} className="animate-spin text-on-brand/80 motion-reduce:animate-none" />
        <p className="text-sm font-semibold">{call.phase === "leaving" ? "Leaving…" : "Connecting…"}</p>
      </div>
    );
  } else if (inPreview) {
    if (call.phase === "starting-preview") {
      main = (
        <div className="flex size-full flex-col items-center justify-center gap-3">
          <LoaderCircle aria-hidden="true" size={28} className="animate-spin text-on-brand/80 motion-reduce:animate-none" />
          <p className="text-sm font-semibold">Checking devices…</p>
        </div>
      );
    } else {
      const previewVideoTrack = call.cameraOn && call.local?.video.playable ? call.local.video.track : null;
      main = previewVideoTrack ? (
        <ParticipantVideo track={previewVideoTrack} mirrored className="object-cover" />
      ) : (
        call.cameraOn && !call.mediaProblem?.camera ? (
          <div role="status" className="flex size-full flex-col items-center justify-center gap-3 bg-ink text-center text-on-brand">
            <LoaderCircle aria-hidden="true" size={28} className="animate-spin text-on-brand/80 motion-reduce:animate-none" />
            <p className="text-sm font-semibold">Checking devices…</p>
          </div>
        ) : (
          <CameraOff name={selfName} photoUrl={selfPhotoUrl} photoUpdatedAt={selfPhotoUpdatedAt} status={call.mediaProblem?.camera ? "Camera unavailable" : "Camera off"} />
        )
      );
    }
  } else if (call.phase === "failed") {
    main = <StageMessage alert action={stageActions("Try again")}>{call.failure?.message ?? "The video session isn’t connected."}{!open && availability ? ` ${availability}` : ""}</StageMessage>;
  } else if (call.phase === "left") {
    main = <StageMessage detail={deviceCheckSummary} action={stageActions("Rejoin")}>{open ? "You left the call. Leaving doesn’t end the Appointment." : availability}</StageMessage>;
  } else if (open) {
    main = canJoin
      ? <StageMessage detail={deviceCheckSummary} action={stageActions("Join session")}>Ready to join</StageMessage>
      : <StageMessage>Joining this session is unavailable to this account.</StageMessage>;
  } else {
    main = <StageMessage detail={deviceCheckSummary} action={checkDevicesButton}>{availability}</StageMessage>;
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
      {/* In fullscreen this flex item must shrink below a tall track's intrinsic height so the
          remote video's object-contain fit can letterbox it instead of clipping the controls. */}
      <div className="relative aspect-video max-h-(--call-stage-max-height) w-full min-h-0 min-w-0 bg-ink text-on-brand [:fullscreen>&]:aspect-auto [:fullscreen>&]:max-h-none [:fullscreen>&]:min-h-0 [:fullscreen>&]:flex-1">
        {main}

        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2 sm:p-3">
          {/* Names the other person once they are in the call; during local preview it states that
              the check is strictly local. */}
          <div className="flex min-w-0 flex-col items-start gap-1">
            {inPreview ? (
              <div className="min-w-0 rounded-sm bg-ink/85 px-2.5 py-1">
                <p className="text-sm font-semibold">Checking devices</p>
                <p className="text-xs text-on-brand/80">Local preview only · {participantName} cannot see or hear you</p>
              </div>
            ) : null}
            {connected && call.remote ? (
              <div className="min-w-0 rounded-sm bg-ink/85 px-2.5 py-1">
                <p className="truncate text-sm font-semibold">{participantName}</p>
                <p className="text-xs text-on-brand/80">{call.phase === "reconnecting" ? "Reconnecting…" : "Connected"}</p>
              </div>
            ) : null}
            {connected && timing?.notice ? (
              <div
                role="status"
                aria-label={timing.notice.title}
                data-timing-phase={timing.notice.phase}
                className={cn(
                  "pointer-events-auto max-w-xs rounded-sm bg-ink/85 px-2.5 py-1 text-xs text-on-brand shadow-sm @[28rem]/stage:max-w-md",
                  timing.notice.phase === "OVERTIME" || timing.notice.phase === "SCHEDULED_END_REACHED"
                    ? "border-l-2 border-warning"
                    : "border-l-2 border-brand"
                )}
              >
                <div className="flex items-center gap-1.5 font-semibold">
                  <Clock aria-hidden="true" size={13} className="shrink-0 text-on-brand/80" />
                  <span>{timing.notice.title}</span>
                </div>
                <p className="mt-0.5 text-[0.6875rem] leading-tight text-on-brand/80 @[28rem]/stage:text-xs">
                  {timing.notice.message}
                </p>
              </div>
            ) : null}
          </div>
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
          {connected && audio?.blocked ? <PlayAudioPrompt onPlay={audio.resume} /> : null}
        </div>

        {connected ? <SelfView local={call.local} cameraOn={call.cameraOn} microphoneOn={call.microphoneOn} name={selfName} photoUrl={selfPhotoUrl} photoUpdatedAt={selfPhotoUpdatedAt} /> : null}
      </div>

      <p aria-live="polite" className="sr-only">{callAnnouncement(call, participantName)}</p>

      {inPreview ? (
        <PreJoinDeviceCheck
          call={call}
          availability={!open ? availability : null}
          joinAction={joinOnlyAction("Join session")}
          onClose={closePreviewAndRestoreFocus}
          onOpenDevices={openDevices}
        />
      ) : null}

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
        open={devicesOpen && (connected || inPreview)}
        onOpenChange={setDevicesOpen}
        devices={call.devices}
        onRefresh={call.refreshDevices}
        onSelectCamera={call.selectCamera}
        onSelectMicrophone={call.selectMicrophone}
        onSelectSpeaker={call.selectSpeaker}
        description={inPreview ? "Changes apply to this local preview. They won’t connect you to the session." : undefined}
      >
        {inPreview ? <PreJoinDeviceDiagnostics call={call} /> : null}
      </DeviceDialog>
    </section>
  );
}
