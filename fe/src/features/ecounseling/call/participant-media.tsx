"use client";

import { Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils/cn";

type MediaTarget = { srcObject: MediaProvider | null };

// Points a media element at one track through a fresh single-track stream and returns the detach.
// The detach clears the element only while it still shows this stream, so a replacement track
// attached in between is never cleared by the stale cleanup, and no stream outlives its track.
export function attachTrack(
  element: MediaTarget,
  track: MediaStreamTrack,
  createStream: (track: MediaStreamTrack) => MediaStream = (value) => new MediaStream([value]),
): () => void {
  const stream = createStream(track);
  element.srcObject = stream;
  return () => {
    if (element.srcObject === stream) element.srcObject = null;
  };
}

// A participant's camera. Always muted: sound plays through ParticipantAudio, so a remote
// participant stays audible with their camera off and this participant never hears themself.
export function ParticipantVideo({ track, mirrored = false, className }: { track: MediaStreamTrack | null; mirrored?: boolean; className?: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element || !track) return;
    const detach = attachTrack(element, track);
    // A muted video may always autoplay; a rejected play() leaves the last frame, not an error.
    void element.play().catch(() => undefined);
    return detach;
  }, [track]);
  return (
    <video
      ref={ref}
      aria-hidden="true"
      autoPlay
      muted
      playsInline
      className={cn("size-full bg-ink", mirrored && "-scale-x-100", className)}
    />
  );
}

// The other participant's sound, rendered by COMPASS and only for the remote participant. When the
// browser refuses to start audio without a click (autoplay policy), a compact "Play audio" control
// appears instead of leaving the person unable to hear.
export function RemoteAudio({ track, speakerId }: { track: MediaStreamTrack | null; speakerId: string | null }) {
  const ref = useRef<HTMLAudioElement>(null);
  const [blockedTrack, setBlockedTrack] = useState<MediaStreamTrack | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || !track) return;
    const detach = attachTrack(element, track);
    let current = true;
    element.play().then(
      () => {
        if (current) setBlockedTrack(null);
      },
      (error: unknown) => {
        if (current && error instanceof DOMException && error.name === "NotAllowedError") setBlockedTrack(track);
      },
    );
    return () => {
      current = false;
      element.pause();
      detach();
    };
  }, [track]);

  useEffect(() => {
    const element = ref.current;
    if (!element || !speakerId || typeof element.setSinkId !== "function") return;
    // The output device may have gone away; the system default keeps playing.
    void element.setSinkId(speakerId).catch(() => undefined);
  }, [speakerId, track]);

  async function resume() {
    const element = ref.current;
    if (!element) return;
    try {
      await element.play();
      setBlockedTrack(null);
    } catch {
      // Still blocked: the control stays so the person can try again.
    }
  }

  return (
    <>
      <audio ref={ref} autoPlay className="hidden" />
      {blockedTrack && blockedTrack === track ? (
        <div role="status" className="flex items-center gap-2 rounded-sm bg-ink/85 py-1 pl-3 pr-1 text-sm text-on-brand">
          <span>Audio is ready</span>
          <button
            type="button"
            onClick={() => void resume()}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-md bg-on-brand px-3 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            <Volume2 aria-hidden="true" size={16} />
            Play audio
          </button>
        </div>
      ) : null}
    </>
  );
}
