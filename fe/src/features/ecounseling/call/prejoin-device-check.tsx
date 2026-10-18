"use client";

import { AlertTriangle, Check, LoaderCircle, Mic, MicOff, Settings2, Square, Video, VideoOff, Volume2, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { CallControls } from "@/features/ecounseling/runtime/active-call-context";
import { cn } from "@/lib/utils/cn";

import { CallControl } from "./call-control";

const TEST_TONE_DURATION_MS = 800;

type ActiveTone = {
  stop: () => void;
};

type AudioContextConstructor = typeof AudioContext;

function resolveAudioContext(): AudioContextConstructor | null {
  if (typeof window === "undefined") return null;
  const win = window as Window & typeof globalThis & { webkitAudioContext?: AudioContextConstructor };
  return win.AudioContext ?? win.webkitAudioContext ?? null;
}

// Plays a short, bounded two-note synthesized chime locally in the browser. It never uses the
// participant's microphone and never makes a network request. Where the browser supports output
// device routing (`setSinkId`), it routes through an audio element bound to the selected speaker.
async function startLocalTestTone(speakerId: string | null, signal: AbortSignal, onEnded: () => void): Promise<ActiveTone> {
  const Context = resolveAudioContext();
  if (!Context) throw new Error("Audio output is unavailable.");

  const context = new Context();
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let audioElement: HTMLAudioElement | null = null;
  let oscillator: OscillatorNode | null = null;

  const cleanup = () => {
    if (stopped) return;
    stopped = true;
    signal.removeEventListener("abort", cleanup);
    if (timer !== null) clearTimeout(timer);
    try {
      oscillator?.stop();
    } catch {
      // It may have completed naturally or not started yet.
    }
    if (audioElement) {
      audioElement.pause();
      audioElement.srcObject = null;
      audioElement = null;
    }
    void context.close().catch(() => undefined);
  };

  const checkAborted = () => {
    if (signal.aborted) throw new DOMException("Speaker test stopped.", "AbortError");
  };
  signal.addEventListener("abort", cleanup, { once: true });

  try {
    checkAborted();
    if (context.state === "suspended") {
      await context.resume().catch(() => undefined);
    }
    checkAborted();

    oscillator = context.createOscillator();
    const gain = context.createGain();
    const now = context.currentTime;

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(440, now);
    oscillator.frequency.setValueAtTime(554.37, now + 0.35);

    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.12, now + 0.04);
    gain.gain.setValueAtTime(0.12, now + 0.7);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + TEST_TONE_DURATION_MS / 1000);

    oscillator.connect(gain);

    let routedToSink = false;
    if (
      speakerId &&
      typeof document !== "undefined" &&
      typeof HTMLMediaElement !== "undefined" &&
      typeof HTMLMediaElement.prototype.setSinkId === "function" &&
      typeof context.createMediaStreamDestination === "function"
    ) {
      try {
        const destination = context.createMediaStreamDestination();
        gain.connect(destination);
        audioElement = document.createElement("audio");
        await audioElement.setSinkId(speakerId);
        checkAborted();
        audioElement.srcObject = destination.stream;
        await audioElement.play().catch(() => undefined);
        checkAborted();
        routedToSink = true;
      } catch {
        // If the chosen sink is unavailable, fall back to the system default output.
        routedToSink = false;
      }
    }

    if (!routedToSink) {
      gain.connect(context.destination);
    }

    oscillator.start(now);
    oscillator.stop(now + TEST_TONE_DURATION_MS / 1000);

    timer = setTimeout(() => {
      cleanup();
      onEnded();
    }, TEST_TONE_DURATION_MS);

    return {
      stop: () => {
        cleanup();
      },
    };
  } catch (error) {
    cleanup();
    throw error;
  }
}

export function PreJoinDeviceDiagnostics({ call }: { call: CallControls }) {
  const starting = call.phase === "starting-preview";
  const [speakerState, setSpeakerState] = useState<"idle" | "playing" | "played" | "failed">("idle");
  const activeToneRef = useRef<ActiveTone | null>(null);
  const toneControllerRef = useRef<AbortController | null>(null);
  const toneRequestRef = useRef(0);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      toneRequestRef.current += 1;
      toneControllerRef.current?.abort();
      toneControllerRef.current = null;
      activeToneRef.current?.stop();
      activeToneRef.current = null;
    };
  }, []);

  const stopSpeakerTest = useCallback(() => {
    toneRequestRef.current += 1;
    toneControllerRef.current?.abort();
    toneControllerRef.current = null;
    activeToneRef.current?.stop();
    activeToneRef.current = null;
    setSpeakerState("idle");
  }, []);

  async function toggleSpeakerTest() {
    if (speakerState === "playing") {
      stopSpeakerTest();
      return;
    }
    activeToneRef.current?.stop();
    activeToneRef.current = null;
    const request = ++toneRequestRef.current;
    const controller = new AbortController();
    toneControllerRef.current = controller;
    setSpeakerState("playing");
    try {
      const tone = await startLocalTestTone(call.devices.speaker, controller.signal, () => {
        activeToneRef.current = null;
        if (aliveRef.current && toneRequestRef.current === request) setSpeakerState("played");
      });
      if (!aliveRef.current || toneRequestRef.current !== request) {
        tone.stop();
        return;
      }
      activeToneRef.current = tone;
      toneControllerRef.current = null;
    } catch {
      if (!aliveRef.current || toneRequestRef.current !== request) return;
      toneControllerRef.current = null;
      activeToneRef.current = null;
      setSpeakerState("failed");
    }
  }

  const micUnavailable = Boolean(call.mediaProblem?.microphone) || (!starting && call.devices.microphones.length === 0);
  const micPercent = !call.microphoneOn || micUnavailable ? 0 : Math.round(Math.max(0, Math.min(1, call.localAudioLevel)) * 100);
  const micStatus = starting
    ? "Checking microphone…"
    : !call.microphoneOn
      ? "Microphone is off"
      : micUnavailable
        ? "Microphone unavailable"
        : micPercent >= 5
          ? "Microphone is picking up sound"
          : "Speak to test your microphone";

  const speakerStatus =
    speakerState === "playing"
      ? "Playing test sound…"
      : speakerState === "played"
        ? "Test sound played."
        : speakerState === "failed"
          ? "Couldn’t play the test sound on this browser."
          : call.devices.speakerSelectable
            ? "Plays a short tone on the selected speaker."
            : "Uses your system default speaker.";

  return (
    <section aria-label="Device tests" className="space-y-4 border-t border-brand-line pt-4">
      <div className="rounded-sm border border-brand-line bg-surface p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-ink">Microphone test</span>
          <span className="text-xs text-muted">{micStatus}</span>
        </div>
        <div
          role="meter"
          aria-label="Microphone level"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={micPercent}
          aria-valuetext={micStatus}
          className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-surface-muted"
        >
          <div
            className="h-full rounded-full bg-success transition-[width] duration-75 motion-reduce:transition-none"
            style={{ width: `${micPercent}%` }}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-brand-line bg-surface p-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink">Speaker test</p>
          <p
            role={speakerState === "failed" ? "alert" : "status"}
            className={cn("mt-0.5 text-sm", speakerState === "failed" ? "text-danger" : "text-muted")}
          >
            {speakerStatus}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={starting}
          onClick={() => void toggleSpeakerTest()}
          className="min-h-11 shrink-0"
        >
          {speakerState === "playing" ? (
            <>
              <Square aria-hidden="true" size={14} />
              Stop test sound
            </>
          ) : (
            <>
              <Volume2 aria-hidden="true" size={16} />
              Play test sound
            </>
          )}
        </Button>
      </div>
    </section>
  );
}

type ReadinessStatus = { label: string; Icon: LucideIcon; tone: string };

function deviceReadiness(kind: "microphone" | "camera", call: CallControls): ReadinessStatus {
  if (call.phase === "starting-preview") return { label: "Checking devices", Icon: LoaderCircle, tone: "text-muted" };
  const isMicrophone = kind === "microphone";
  const on = isMicrophone ? call.microphoneOn : call.cameraOn;
  if (!on) return { label: isMicrophone ? "Microphone off" : "Camera off", Icon: isMicrophone ? MicOff : VideoOff, tone: "text-muted" };
  const unavailable = Boolean(isMicrophone ? call.mediaProblem?.microphone : call.mediaProblem?.camera);
  if (unavailable) return { label: isMicrophone ? "Microphone unavailable" : "Camera unavailable", Icon: AlertTriangle, tone: "text-danger" };
  const devices = isMicrophone ? call.devices.microphones : call.devices.cameras;
  if (!devices.length) return { label: "Checking devices", Icon: LoaderCircle, tone: "text-muted" };
  return { label: isMicrophone ? "Microphone ready" : "Camera ready", Icon: Check, tone: "text-success" };
}

function ReadinessItem({ status }: { status: ReadinessStatus }) {
  const { Icon } = status;
  return (
    <li className={cn("inline-flex min-h-7 items-center gap-1.5 text-xs font-medium", status.tone)}>
      <Icon aria-hidden="true" size={14} className={status.Icon === LoaderCircle ? "animate-spin motion-reduce:animate-none" : undefined} />
      {status.label}
    </li>
  );
}

export function PreJoinDeviceCheck({
  call,
  availability,
  joinAction,
  onClose,
  onOpenDevices,
}: {
  call: CallControls;
  availability: string | null;
  joinAction: ReactNode;
  onClose: () => void;
  onOpenDevices: () => void;
}) {
  const starting = call.phase === "starting-preview";
  const micButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!starting) micButtonRef.current?.focus();
  }, [starting]);

  const micReadiness = deviceReadiness("microphone", call);
  const cameraReadiness = deviceReadiness("camera", call);

  return (
    <div className="border-t border-brand-line bg-surface-raised">
      {call.mediaProblem ? (
        <p role="alert" className="border-b border-brand-line px-3 py-2 text-sm text-danger sm:px-4">
          {call.mediaProblem.message}
          {call.mediaProblem.camera && !call.mediaProblem.microphone ? " You can continue with audio." : ""}
        </p>
      ) : null}

      <div className="space-y-3 px-3 py-3 sm:px-4 sm:py-4">
        <div role="group" aria-label="Pre-join device controls" className="flex justify-center gap-3">
          <CallControl
            ref={micButtonRef}
            icon={call.microphoneOn ? Mic : MicOff}
            label="Mic"
            accessibleName="Microphone"
            aria-pressed={call.microphoneOn}
            tone={call.microphoneOn ? "default" : "off"}
            disabled={starting}
            onClick={() => call.setMicrophone(!call.microphoneOn)}
            className="size-14 min-w-14 flex-none px-0"
          />
          <CallControl
            icon={call.cameraOn ? Video : VideoOff}
            label="Camera"
            aria-pressed={call.cameraOn}
            tone={call.cameraOn ? "default" : "off"}
            disabled={starting}
            onClick={() => call.setCamera(!call.cameraOn)}
            className="size-14 min-w-14 flex-none px-0"
          />
          <CallControl
            icon={Settings2}
            label="Devices"
            aria-haspopup="dialog"
            disabled={starting}
            onClick={onOpenDevices}
            className="size-14 min-w-14 flex-none px-0"
          />
        </div>

        <ul aria-label="Device readiness" className="flex flex-wrap justify-center gap-x-4 gap-y-1">
          <ReadinessItem status={micReadiness} />
          <ReadinessItem status={cameraReadiness} />
        </ul>

        {availability ? <p role="status" className="text-center text-sm text-muted">{availability}</p> : null}

        <div className="flex flex-wrap items-center justify-center gap-2 border-t border-brand-line pt-3">
          {joinAction}
          <Button type="button" variant="secondary" className="min-h-11" onClick={onClose}>
            Close preview
          </Button>
        </div>
        <p className="text-center text-xs text-muted">Local preview only. No one else can see or hear you until you join.</p>
      </div>
    </div>
  );
}
