"use client";

import { useEffect, useRef, useState } from "react";

import type { JoinCredentialResponse } from "@/lib/api/generated/model";

type CallClient = import("@daily-co/daily-js").DailyCall;

const cleanupByHost = new WeakMap<HTMLElement, Promise<void>>();

export function DailySessionFrame({
  credential,
  onJoined,
  onLeft,
  onFailed,
}: {
  credential: JoinCredentialResponse | null;
  onJoined: () => void;
  onLeft: () => void;
  onFailed: () => void;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  // Kept until join/failure so Strict Mode's effect replay can perform the actual join.
  const credentialRef = useRef<JoinCredentialResponse | null>(credential);
  const callbacksRef = useRef({ onJoined, onLeft, onFailed });
  const [state, setState] = useState<"loading" | "joining" | "joined" | "error">("loading");

  useEffect(() => {
    callbacksRef.current = { onJoined, onLeft, onFailed };
  }, [onJoined, onLeft, onFailed]);

  useEffect(() => {
    let cancelled = false;
    const hostElement = hostRef.current;
    let roomUrl = credentialRef.current?.room_url ?? "";
    let meetingToken = credentialRef.current?.meeting_token ?? "";
    let call: CallClient | null = null;
    let failed = false;

    function onCallJoined() {
      roomUrl = "";
      meetingToken = "";
      credentialRef.current = null;
      setState("joined");
      callbacksRef.current.onJoined();
    }

    function onCallLeft() {
      setState("loading");
      callbacksRef.current.onLeft();
    }

    function onCallFailure() {
      if (failed) return;
      failed = true;
      roomUrl = "";
      meetingToken = "";
      credentialRef.current = null;
      setState("error");
      callbacksRef.current.onFailed();
    }

    async function createAndJoin() {
      if (!hostElement || !roomUrl || !meetingToken) {
        onCallFailure();
        return;
      }
      try {
        const dailyModule = await import("@daily-co/daily-js");
        if (cancelled || !hostElement) return;
        const previousCleanup = cleanupByHost.get(hostElement);
        if (previousCleanup) await previousCleanup.catch(() => undefined);
        if (cancelled || !hostElement) return;
        call = dailyModule.default.createFrame(hostElement, {
          iframeStyle: { width: "100%", height: "100%", border: "0" },
        });
        const frame = call.iframe();
        if (frame) frame.title = "E-Counseling video session";
        call.on("joined-meeting", onCallJoined);
        call.on("left-meeting", onCallLeft);
        call.on("error", onCallFailure);
        call.on("load-attempt-failed", onCallFailure);
        setState("joining");
        await call.join({
          url: roomUrl,
          token: meetingToken,
          showLeaveButton: true,
          showFullscreenButton: true,
        });
      } catch {
        if (!cancelled) onCallFailure();
      }
    }

    void createAndJoin();

    return () => {
      cancelled = true;
      roomUrl = "";
      meetingToken = "";
      if (call) {
        call.off("joined-meeting", onCallJoined);
        call.off("left-meeting", onCallLeft);
        call.off("error", onCallFailure);
        call.off("load-attempt-failed", onCallFailure);
        const host = hostElement;
        const cleanup = (async () => {
          try {
            await call?.leave();
          } catch {
            // Leaving is best-effort during unmount; destroy still runs.
          }
          try {
            await call?.destroy();
          } catch {
            // Destroy is best-effort during unmount.
          }
        })();
        if (host) {
          cleanupByHost.set(host, cleanup);
          void cleanup.finally(() => {
            if (cleanupByHost.get(host) === cleanup) cleanupByHost.delete(host);
          });
        }
      }
    };
  }, []);

  return (
    <section aria-label="E-Counseling video session" className="min-w-0">
      <div className="relative aspect-video min-h-60 w-full overflow-hidden rounded-md border border-border bg-ink">
        <div ref={hostRef} className="absolute inset-0" />
        {state !== "joined" ? (
          <div className="absolute inset-x-0 bottom-0 bg-ink/90 px-4 py-3 text-sm text-on-brand" role={state === "error" ? "alert" : "status"}>
            {state === "error" ? "The video session could not be opened. Return to the session and request a fresh join." : state === "loading" ? "Preparing the secure session…" : "Connecting to the session…"}
          </div>
        ) : null}
      </div>
      <p className="sr-only" aria-live="polite">{state === "joined" ? "Connected to the session." : state === "error" ? "The video session could not be opened." : "Connecting to the session."}</p>
    </section>
  );
}
