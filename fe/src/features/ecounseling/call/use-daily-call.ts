"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { ecounselingErrorMessage } from "@/features/ecounseling/ecounseling-shared";
import { eCounselingCreateJoinCredential } from "@/lib/api/generated/e-counseling/e-counseling";

import { DailyCallSession } from "./daily-call-session";

export type DailyCallControls = ReturnType<typeof useDailyCall>;

// The page's one E-Counseling call. The session object is created once per mounted workspace and
// does nothing until the person presses Join. Joining asks the COMPASS backend for a fresh,
// short-lived credential with the generated imperative client, so the room URL and meeting token
// never enter the TanStack query or mutation caches, browser storage, the URL or logs. Unmounting
// leaves the call and destroys the call object.
export function useDailyCall({
  appointmentId,
  onProviderMediaEvent,
  onJoinFailed,
}: {
  appointmentId: string;
  // Daily reported a recording or transcription change: re-read the COMPASS session, which stays
  // the only authority on what is being captured.
  onProviderMediaEvent: () => void;
  // The backend refused or could not issue a credential, for example after the join window closed.
  onJoinFailed: () => void;
}) {
  const [session] = useState(() => new DailyCallSession());
  const snapshot = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  const callbacks = useRef({ onProviderMediaEvent, onJoinFailed });

  useEffect(() => {
    callbacks.current = { onProviderMediaEvent, onJoinFailed };
  }, [onProviderMediaEvent, onJoinFailed]);

  useEffect(() => {
    session.setProviderMediaEventHandler(() => callbacks.current.onProviderMediaEvent());
    return () => session.dispose();
  }, [session]);

  const join = useCallback(async () => {
    await session.join({
      fetchCredential: async () => {
        const result = await eCounselingCreateJoinCredential(appointmentId, { cache: "no-store" });
        return { roomUrl: result.data.room_url, token: result.data.meeting_token, expiresAt: result.data.token_expires_at };
      },
      describeCredentialError: (error) => ecounselingErrorMessage(error, "Couldn’t open the video session. Try again."),
    });
    if (session.getSnapshot().failure?.kind === "credential") callbacks.current.onJoinFailed();
  }, [appointmentId, session]);

  const actions = useMemo(() => ({
    join,
    leave: () => session.leave(),
    setMicrophone: (on: boolean) => session.setMicrophone(on),
    setCamera: (on: boolean) => session.setCamera(on),
    refreshDevices: () => session.refreshDevices(),
    selectCamera: (id: string) => session.selectCamera(id),
    selectMicrophone: (id: string) => session.selectMicrophone(id),
    selectSpeaker: (id: string) => session.selectSpeaker(id),
  }), [join, session]);

  return { ...snapshot, ...actions };
}
