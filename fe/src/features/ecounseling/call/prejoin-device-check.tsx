"use client";

import { Mic, MicOff, Square, Video, VideoOff, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { CallControls } from "@/features/ecounseling/runtime/active-call-context";
import { cn } from "@/lib/utils/cn";

import { DeviceField, type DeviceKind } from "./device-dialog";

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
async function startLocalTestTone(speakerId: string | null, onEnded: () => void): Promise<ActiveTone> {
  const Context = resolveAudioContext();
  if (!Context) throw new Error("Audio output is unavailable.");

  const context = new Context();
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let audioElement: HTMLAudioElement | null = null;

  const cleanup = () => {
    if (stopped) return;
    stopped = true;
    if (timer !== null) clearTimeout(timer);
    if (audioElement) {
      audioElement.pause();
      audioElement.srcObject = null;
      audioElement = null;
    }
    void context.close().catch(() => undefined);
  };

  try {
    if (context.state === "suspended") {
      await context.resume().catch(() => undefined);
    }

    const oscillator = context.createOscillator();
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
        audioElement.srcObject = destination.stream;
        await audioElement.play().catch(() => undefined);
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
        try {
          oscillator.stop();
        } catch {
          // Already stopped.
        }
        cleanup();
      },
    };
  } catch (error) {
    cleanup();
    throw error;
  }
}

export function PreJoinDeviceCheck({
  call,
  availability,
  joinAction,
  onClose,
}: {
  call: CallControls;
  availability: string | null;
  joinAction: ReactNode;
  onClose: () => void;
}) {
  const starting = call.phase === "starting-preview";
  const [speakerState, setSpeakerState] = useState<"idle" | "playing" | "played" | "failed">("idle");
  const activeToneRef = useRef<ActiveTone | null>(null);
  const micButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!starting) micButtonRef.current?.focus();
  }, [starting]);

  useEffect(() => {
    return () => {
      activeToneRef.current?.stop();
      activeToneRef.current = null;
    };
  }, []);

  const stopSpeakerTest = useCallback(() => {
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
    setSpeakerState("playing");
    try {
      const tone = await startLocalTestTone(call.devices.speaker, () => {
        activeToneRef.current = null;
        setSpeakerState("played");
      });
      activeToneRef.current = tone;
    } catch {
      activeToneRef.current = null;
      setSpeakerState("failed");
    }
  }

  function handleClose() {
    stopSpeakerTest();
    onClose();
  }

  const selectDevice = (kind: DeviceKind, id: string) =>
    kind === "camera"
      ? call.selectCamera(id)
      : kind === "microphone"
        ? call.selectMicrophone(id)
        : call.selectSpeaker(id);

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
    <div className="border-t border-brand-line bg-surface-raised">
      {call.mediaProblem ? (
        <p role="alert" className="border-b border-brand-line px-3 py-2 text-sm text-danger sm:px-4">
          {call.mediaProblem.message}
          {call.mediaProblem.camera && !call.mediaProblem.microphone ? " You can continue with audio." : ""}
        </p>
      ) : null}

      <div className="space-y-4 px-3 py-3 sm:px-4 sm:py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="group" aria-label="Pre-join device controls" className="flex flex-wrap items-center gap-2">
            <button
              ref={micButtonRef}
              type="button"
              aria-label="Microphone"
              aria-pressed={call.microphoneOn}
              disabled={starting}
              onClick={() => call.setMicrophone(!call.microphoneOn)}
              className={cn(
                "inline-flex min-h-11 items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-55",
                call.microphoneOn
                  ? "border-brand-line bg-surface text-ink hover:bg-surface-muted"
                  : "border-danger/40 bg-danger/10 text-danger hover:bg-danger/15",
              )}
            >
              {call.microphoneOn ? <Mic aria-hidden="true" size={16} /> : <MicOff aria-hidden="true" size={16} />}
              <span>{call.microphoneOn ? "Microphone on" : "Microphone off"}</span>
            </button>
            <button
              type="button"
              aria-label="Camera"
              aria-pressed={call.cameraOn}
              disabled={starting}
              onClick={() => call.setCamera(!call.cameraOn)}
              className={cn(
                "inline-flex min-h-11 items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-55",
                call.cameraOn
                  ? "border-brand-line bg-surface text-ink hover:bg-surface-muted"
                  : "border-danger/40 bg-danger/10 text-danger hover:bg-danger/15",
              )}
            >
              {call.cameraOn ? <Video aria-hidden="true" size={16} /> : <VideoOff aria-hidden="true" size={16} />}
              <span>{call.cameraOn ? "Camera on" : "Camera off"}</span>
            </button>
          </div>
          <p className="text-xs text-muted">
            Preview stays on this device. No one else can see or hear you until you join.
          </p>
        </div>

        <div className="grid gap-3 @[28rem]/stage:grid-cols-2">
          <div className="rounded-sm border border-brand-line bg-surface p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-ink">Microphone test</span>
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

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-brand-line bg-surface p-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-ink">Speaker test</p>
              <p
                role={speakerState === "failed" ? "alert" : "status"}
                className={cn("mt-0.5 text-xs", speakerState === "failed" ? "text-danger" : "text-muted")}
              >
                {speakerStatus}
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={starting}
              onClick={() => void toggleSpeakerTest()}
              className="shrink-0"
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
        </div>

        <div className="grid gap-3 @[32rem]/stage:grid-cols-3">
          <DeviceField
            kind="camera"
            label="Camera"
            options={call.devices.cameras}
            value={call.devices.camera}
            onSelect={selectDevice}
          />
          <DeviceField
            kind="microphone"
            label="Microphone"
            options={call.devices.microphones}
            value={call.devices.microphone}
            onSelect={selectDevice}
          />
          <DeviceField
            kind="speaker"
            label="Speaker"
            options={call.devices.speakerSelectable ? call.devices.speakers : []}
            value={call.devices.speaker}
            onSelect={selectDevice}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-brand-line pt-3">
          <p className="text-xs text-muted">
            {availability ?? "Your selected devices and camera/microphone settings will be used when you join."}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" onClick={handleClose}>
              Close preview
            </Button>
            {joinAction}
          </div>
        </div>
      </div>
    </div>
  );
}
