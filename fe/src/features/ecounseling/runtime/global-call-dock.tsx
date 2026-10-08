"use client";

import { ArrowUpRight, ChevronDown, ChevronUp, LoaderCircle, Mic, MicOff, PhoneOff, Settings2, Video, VideoOff, WifiLow, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { CallControl, CallTray, callControlClass } from "@/features/ecounseling/call/call-control";
import { CaptureIndicators } from "@/features/ecounseling/call/capture-indicators";
import { DeviceDialog } from "@/features/ecounseling/call/device-dialog";
import { ParticipantVideo, PlayAudioPrompt } from "@/features/ecounseling/call/participant-media";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { ECounselingCaptureStatus } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

import { useActiveECounselingCall } from "./active-call-context";
import { consentEndedNotice, isConnected, pendingConsentCue, sessionPath } from "./runtime-model";

const iconButton = "inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// Keeps page content and the action status clear of the dock while it is on screen.
function useDockClearance(element: RefObject<HTMLElement | null>, shown: boolean) {
  useEffect(() => {
    const target = element.current;
    const root = document.documentElement;
    if (!shown || !target) {
      root.style.removeProperty("--call-dock-height");
      return;
    }
    const measure = () => root.style.setProperty("--call-dock-height", `${Math.ceil(target.getBoundingClientRect().height)}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(target);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--call-dock-height");
    };
  }, [element, shown]);
}

// The live call on every portal page other than its own session (ADR-094): who, whether it is
// connected, what COMPASS is capturing, and the immediate call controls. It is an in-app dock, not
// the browser's picture-in-picture. It never starts capture, never holds consent decisions, and
// shows no files, references or history; Return to session opens the full call. On narrow screens,
// and whenever the reader prefers, it folds to one row while the call and its audio continue.
export function GlobalCallDock({
  hidden,
  endedNotice,
  onDismissEnded,
}: {
  // The full session stage is on screen.
  hidden: boolean;
  endedNotice: string | null;
  onDismissEnded: () => void;
}) {
  const runtime = useActiveECounselingCall();
  const { call } = runtime;
  const [collapsed, setCollapsed] = useState(false);
  const [devicesOpen, setDevicesOpen] = useState(false);
  const bodyId = useId();
  const dockRef = useRef<HTMLElement>(null);
  const shown = runtime.live && !hidden && runtime.appointmentId !== null;
  useDockClearance(dockRef, shown || Boolean(endedNotice && !runtime.live));

  if (!runtime.live && endedNotice && !hidden && runtime.appointmentId) {
    return (
      <section ref={dockRef} aria-label="E-Counseling call ended" data-call-dock="ended" className="fixed inset-x-2 bottom-(--call-dock-offset) z-40 rounded-md border border-brand-line bg-surface-raised p-3 shadow-float md:inset-x-auto md:right-4 md:w-80 lg:right-6 print:hidden">
        <div className="flex items-start gap-2">
          <p role="status" className="min-w-0 flex-1 text-sm font-medium text-ink">{endedNotice}</p>
          <button type="button" aria-label="Dismiss" onClick={onDismissEnded} className={cn(iconButton, "-m-1.5 size-9")}>
            <X aria-hidden="true" size={16} />
          </button>
        </div>
        <GuardedPortalLink href={sessionPath(runtime.appointmentId)} onClick={onDismissEnded} className="mt-2 inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Return to session
        </GuardedPortalLink>
      </section>
    );
  }
  if (!shown || !runtime.appointmentId) return null;

  const name = runtime.participantName ?? "Your session";
  const connected = isConnected(call.phase);
  const status = call.phase === "reconnecting"
    ? "Reconnecting…"
    : call.phase === "leaving"
      ? "Leaving…"
      : connected
        ? call.remote ? "Connected" : `Waiting for ${name}…`
        : "Connecting…";
  const href = sessionPath(runtime.appointmentId);
  const cue = runtime.role === "STUDENT" ? pendingConsentCue(runtime.canonical.media) : null;
  const consentEnded = runtime.role === "COUNSELOR" ? consentEndedNotice(runtime.canonical.media) : null;
  const stops = (["recording", "transcription"] as const).filter((kind) => runtime.capture.canStop[kind]);
  const unstable = connected && (call.network === "warning" || call.network === "bad");

  const notices = (
    <>
      {runtime.audio.blocked ? <PlayAudioPrompt onPlay={runtime.audio.resume} /> : null}
      {cue ? (
        <div className="flex items-center justify-between gap-2 rounded-sm border border-brand-line bg-brand-wash px-2.5 py-1.5">
          <p className="text-sm font-semibold text-ink">{cue}</p>
          <GuardedPortalLink href={href} className="inline-flex min-h-9 items-center rounded-md px-2 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Review
          </GuardedPortalLink>
        </div>
      ) : null}
      {consentEnded ? <p className="text-sm text-ink">{consentEnded}</p> : null}
      {stops.length ? (
        <div className="flex flex-wrap gap-2">
          {stops.map((kind) => {
            // Stopping holds until COMPASS confirms the stop, as on the session page.
            const stopping = runtime.capture.stopping[kind] || runtime.canonical.media?.[kind].capture_status === ECounselingCaptureStatus.STOP_REQUESTED;
            return (
              <Button key={kind} variant="secondary" className="min-h-9 px-3 py-1" disabled={stopping} onClick={() => void runtime.capture.stop(kind)}>
                {stopping ? "Stopping…" : kind === "recording" ? "Stop recording" : "Stop transcription"}
              </Button>
            );
          })}
        </div>
      ) : null}
      {runtime.capture.error ? <p role="alert" className="text-sm text-danger">{runtime.capture.error}</p> : null}
      {!runtime.canonical.current && runtime.canonical.media ? <p className="text-xs text-muted">Showing the last confirmed session status.</p> : null}
      {connected && call.mediaProblem ? <p role="alert" className="text-sm text-danger">{call.mediaProblem.message}</p> : null}
    </>
  );

  return (
    <section
      ref={dockRef}
      aria-label="Active E-Counseling call"
      data-call-dock={collapsed ? "collapsed" : "expanded"}
      className="fixed inset-x-2 bottom-(--call-dock-offset) z-40 overflow-hidden rounded-md border border-brand-line bg-surface-raised shadow-float md:inset-x-auto md:right-4 md:w-80 lg:right-6 print:hidden"
    >
      <div className="flex items-center gap-1 py-1 pl-3 pr-1">
        <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", connected && call.phase !== "reconnecting" ? "bg-success" : "bg-warning")} />
        <p className="min-w-0 flex-1 truncate text-sm">
          <span className="font-semibold text-ink">{name}</span>
          <span className="text-muted"> · {status}</span>
        </p>
        {collapsed ? (
          <>
            <button type="button" aria-label="Microphone" aria-pressed={call.microphoneOn} disabled={!connected} onClick={() => call.setMicrophone(!call.microphoneOn)} className={cn(iconButton, !call.microphoneOn && "text-danger", "disabled:opacity-55")}>
              {call.microphoneOn ? <Mic aria-hidden="true" size={18} /> : <MicOff aria-hidden="true" size={18} />}
            </button>
            <GuardedPortalLink href={href} aria-label="Return to session" className={iconButton}>
              <ArrowUpRight aria-hidden="true" size={18} />
            </GuardedPortalLink>
          </>
        ) : null}
        <button type="button" aria-label={collapsed ? "Show call" : "Minimize call"} aria-expanded={!collapsed} aria-controls={bodyId} onClick={() => setCollapsed((value) => !value)} className={iconButton}>
          {collapsed ? <ChevronUp aria-hidden="true" size={18} /> : <ChevronDown aria-hidden="true" size={18} />}
        </button>
        {collapsed ? (
          <button type="button" aria-label="Leave session" onClick={runtime.requestLeave} className={cn(iconButton, "text-danger")}>
            <PhoneOff aria-hidden="true" size={18} />
          </button>
        ) : null}
      </div>

      {collapsed ? (
        <div id={bodyId} className="space-y-2 px-3 pb-2 empty:hidden">
          <CaptureIndicators media={runtime.canonical.media} className="[&_ul]:flex-row [&_ul]:flex-wrap [&_li]:bg-ink" />
          {notices}
        </div>
      ) : (
        <div id={bodyId}>
          <div className="relative aspect-video bg-ink text-on-brand">
            {connected && call.remote?.video.track && call.remote.video.playable ? (
              <ParticipantVideo track={call.remote.video.track} className="object-contain" />
            ) : (
              <div className="flex size-full flex-col items-center justify-center gap-1 px-3 text-center">
                {connected && call.remote ? <VideoOff aria-hidden="true" size={22} className="text-on-brand/70" /> : <LoaderCircle aria-hidden="true" size={22} className={cn("text-on-brand/70", !connected && "animate-spin motion-reduce:animate-none")} />}
                <p className="text-sm font-semibold">{connected && call.remote ? "Camera off" : status}</p>
              </div>
            )}
            <div className="absolute bottom-2 left-2 flex max-w-[85%] flex-col items-start gap-1">
              <CaptureIndicators media={runtime.canonical.media} />
              {call.phase === "reconnecting" ? <p className="rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold">Your call is reconnecting.</p> : null}
              {unstable ? <p className="inline-flex items-center gap-1 rounded-sm bg-ink/85 px-2 py-1 text-xs font-semibold"><WifiLow aria-hidden="true" size={14} />Connection unstable</p> : null}
            </div>
          </div>
          <div className="space-y-2 px-3 py-2 empty:hidden">{notices}</div>
          <CallTray className="p-1.5">
            <CallControl icon={call.microphoneOn ? Mic : MicOff} label="Mic" accessibleName="Microphone" aria-pressed={call.microphoneOn} tone={call.microphoneOn ? "default" : "off"} problem={Boolean(call.mediaProblem?.microphone)} disabled={!connected} onClick={() => call.setMicrophone(!call.microphoneOn)} />
            <CallControl icon={call.cameraOn ? Video : VideoOff} label="Camera" aria-pressed={call.cameraOn} tone={call.cameraOn ? "default" : "off"} problem={Boolean(call.mediaProblem?.camera)} disabled={!connected} onClick={() => call.setCamera(!call.cameraOn)} />
            <CallControl icon={Settings2} label="Devices" aria-haspopup="dialog" disabled={!connected} onClick={() => setDevicesOpen(true)} />
            <GuardedPortalLink href={href} aria-label="Return to session" className={callControlClass("default")}>
              <ArrowUpRight aria-hidden="true" size={20} />
              <span aria-hidden="true">Return</span>
            </GuardedPortalLink>
            <CallControl icon={PhoneOff} label="Leave" accessibleName="Leave session" tone="leave" onClick={runtime.requestLeave} />
          </CallTray>
        </div>
      )}
      <p aria-live="polite" className="sr-only">{call.phase === "reconnecting" ? "Your call is reconnecting." : ""}</p>
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
