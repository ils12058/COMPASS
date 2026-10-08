"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { activeCallPhases, type CallPhase } from "@/features/ecounseling/call/call-model";
import { DailyCallSession } from "@/features/ecounseling/call/daily-call-session";
import { useRemoteAudioPlayback } from "@/features/ecounseling/call/participant-media";
import { getECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { ecounselingErrorMessage, isLiveOrTransitionalCapture, SESSION_REFRESH_MS } from "@/features/ecounseling/ecounseling-shared";
import { useCaptureStop } from "@/features/ecounseling/use-capture-stop";
import {
  eCounselingCreateJoinCredential,
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
  useECounselingGetAssignedWorkspace,
  useECounselingGetMyWorkspace,
} from "@/lib/api/generated/e-counseling/e-counseling";
import type { UserSummary } from "@/lib/api/generated/model";

import { ActiveECounselingCallContext, type ActiveECounselingCall, type CallControls } from "./active-call-context";
import { CrossTabCallCoordinator } from "./cross-tab-call-coordinator";
import { GlobalCallDock } from "./global-call-dock";
import { activeCaptureKinds, isLiveRuntime, joinAvailability, runtimeState } from "./runtime-model";

// The portal's authentication as PortalBoundary knows it. Only "signed-out" (the server answered that
// the session is gone) ends the call; "unverified" (the session couldn't be checked) keeps a working
// call while the portal fails closed around it.
export type PortalAuthState = "pending" | "confirmed" | "unverified" | "signed-out";

type Activation = { appointmentId: string; participantName: string };

function leaveWarning(active: ReadonlyArray<"recording" | "transcription">) {
  const both = active.length > 1;
  const subject = both ? "Recording and transcription are" : active[0] === "recording" ? "Recording is" : "Transcription is";
  return (
    <>
      <p>{subject} still active.</p>
      <p>Leaving the call doesn’t confirm that {both ? "they have" : "it has"} stopped. Stop {both ? "them" : "it"} first if {both ? "they’re" : "it’s"} no longer needed.</p>
    </>
  );
}

// The one E-Counseling call of an authenticated portal session (ADR-094). It owns the Daily Call
// Object for as long as the portal is open, so moving between portal pages never leaves or rejoins
// the call; the session page's full stage and the call dock are two views of it. It also owns:
//   - the session state COMPASS reports for the call, refreshed while the call lasts, through the
//     same generated query (and cache) the session page uses;
//   - the one element that plays the other person's audio;
//   - the leave warning while the Counselor's capture is running, and the protective stop;
//   - a tab's advisory lease, so a second COMPASS tab doesn't start another call.
// It ends the call on Leave, when the call itself ends, on sign-out, when the server confirms the
// session is gone, and when the portal unmounts. Nothing restores a call after a reload.
export function ActiveECounselingRuntimeProvider({
  user,
  authState,
  children,
}: {
  // The last confirmed portal user; it stays while a check of the session is pending or failing.
  user: UserSummary | null;
  authState: PortalAuthState;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const [session] = useState(() => new DailyCallSession());
  const [coordinator] = useState(() => new CrossTabCallCoordinator());
  const snapshot = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  const otherTabActive = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot, () => false);
  const [activation, setActivation] = useState<Activation | null>(null);
  const [claiming, setClaiming] = useState(false);
  const [stageCounts, setStageCounts] = useState<Record<string, number>>({});
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [endedNotice, setEndedNotice] = useState<string | null>(null);
  const access = user ? getECounselingAccess(user) : null;
  const role = access?.isStudent ? "STUDENT" : access?.isCounselor ? "COUNSELOR" : null;
  // A session the server confirmed is gone has no call, whatever was active a moment ago.
  const activated = activation !== null && authState !== "signed-out";
  const state = runtimeState({ activated, claiming, phase: snapshot.phase });
  const live = isLiveRuntime(state);
  const appointmentId = activation?.appointmentId ?? null;

  // COMPASS's own view of the call's session, kept fresh while the call lasts, wherever the person
  // is in the portal. The session page reads the same query, so both show one truth.
  const observedId = appointmentId ?? "";
  const studentSession = useECounselingGetMyWorkspace(observedId, { query: {
    enabled: live && role === "STUDENT" && appointmentId !== null,
    retry: false,
    refetchInterval: live ? SESSION_REFRESH_MS : false,
  } });
  const counselorSession = useECounselingGetAssignedWorkspace(observedId, { query: {
    enabled: live && role === "COUNSELOR" && appointmentId !== null,
    retry: false,
    refetchInterval: live ? SESSION_REFRESH_MS : false,
  } });
  const observed = role === "STUDENT" ? studentSession : counselorSession;
  const media = role === "STUDENT" ? studentSession.data?.data.media : counselorSession.data?.data.media;
  const sessionParticipant = role === "STUDENT" ? studentSession.data?.data.counselor.display_name : counselorSession.data?.data.student.display_name;
  const canonicalCurrent = observed.isSuccess;

  const refreshSession = useCallback(async () => {
    if (!appointmentId || !role) return;
    const queryKey = role === "STUDENT" ? getECounselingGetMyWorkspaceQueryKey(appointmentId) : getECounselingGetAssignedWorkspaceQueryKey(appointmentId);
    await queryClient.invalidateQueries({ queryKey });
  }, [appointmentId, queryClient, role]);

  // Daily's recording and transcription events only ask COMPASS to re-read the session.
  useEffect(() => {
    session.setProviderMediaEventHandler(() => void refreshSession());
  }, [refreshSession, session]);

  const capture = useCaptureStop(appointmentId, refreshSession);
  const canManageMedia = Boolean(access?.canManageMediaAssigned);
  // Students never get a stop: capture is the assigned Counselor's governed action.
  const canStop = {
    recording: canManageMedia && Boolean(media && isLiveOrTransitionalCapture(media.recording.capture_status)),
    transcription: canManageMedia && Boolean(media && isLiveOrTransitionalCapture(media.transcription.capture_status)),
  };

  const { ref: audioRef, blocked: audioBlocked, resume: resumeAudio } = useRemoteAudioPlayback(live ? snapshot.remote?.audio.track ?? null : null, snapshot.devices.speaker);

  // Portal lifetime: the coordinator joins the tab channel; unmounting the portal ends the call.
  useEffect(() => {
    coordinator.start();
    const release = () => coordinator.release();
    window.addEventListener("pagehide", release);
    return () => {
      window.removeEventListener("pagehide", release);
      coordinator.stop();
      void session.dispose();
    };
  }, [coordinator, session]);

  // A session the server confirmed is gone ends the call before the portal clears its data.
  useEffect(() => {
    if (authState !== "signed-out") return;
    coordinator.release();
    void session.dispose();
  }, [authState, coordinator, session]);

  // The tab's lease follows the call; a call that ended or never connected releases it.
  useEffect(() => {
    if (!live) coordinator.release();
  }, [coordinator, live]);

  // A reload or closing the tab cannot keep a call; the browser asks first (its own wording).
  useEffect(() => {
    if (!live) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [live]);

  // When the call ends on its own while the full stage isn't on screen, the dock area says so once.
  const [observedPhase, setObservedPhase] = useState<CallPhase>(snapshot.phase);
  if (observedPhase !== snapshot.phase) {
    setObservedPhase(snapshot.phase);
    const wasConnected = observedPhase === "joined" || observedPhase === "reconnecting";
    if (wasConnected && snapshot.phase === "failed") setEndedNotice(snapshot.failure?.message ?? "The video session ended.");
    else if (wasConnected && snapshot.phase === "left") setEndedNotice("The video session ended.");
    else if (activeCallPhases.has(snapshot.phase) || snapshot.phase === "requesting") setEndedNotice(null);
  }

  const join = useCallback(async (target: Activation) => {
    if (isLiveRuntime(runtimeState({ activated, claiming, phase: session.getSnapshot().phase }))) return;
    setEndedNotice(null);
    setActivation(target);
    setClaiming(true);
    const acquired = await coordinator.acquire();
    setClaiming(false);
    if (!acquired) {
      setActivation(null);
      return;
    }
    const studentRole = role === "STUDENT";
    await session.join({
      fetchCredential: async () => {
        // The credential is fetched without caching and used once by this join; it never enters
        // query caches, browser storage, the URL, logs or the other tabs.
        const result = await eCounselingCreateJoinCredential(target.appointmentId, { cache: "no-store" });
        return { roomUrl: result.data.room_url, token: result.data.meeting_token, expiresAt: result.data.token_expires_at };
      },
      describeCredentialError: (error) => ecounselingErrorMessage(error, "Couldn’t open the video session. Try again."),
    });
    const after = session.getSnapshot();
    if (!activeCallPhases.has(after.phase)) coordinator.release();
    if (after.failure?.kind === "credential") {
      const queryKey = studentRole ? getECounselingGetMyWorkspaceQueryKey(target.appointmentId) : getECounselingGetAssignedWorkspaceQueryKey(target.appointmentId);
      void queryClient.invalidateQueries({ queryKey });
    }
  }, [activated, claiming, coordinator, queryClient, role, session]);

  const activeCapture = role === "COUNSELOR" ? activeCaptureKinds(media) : [];
  const requestLeave = useCallback(() => {
    if (activeCapture.length) setLeaveOpen(true);
    else void session.leave();
  }, [activeCapture.length, session]);

  const end = useCallback(async () => {
    coordinator.release();
    await session.dispose();
  }, [coordinator, session]);

  const presentStage = useCallback((stageAppointmentId: string) => {
    setStageCounts((counts) => ({ ...counts, [stageAppointmentId]: (counts[stageAppointmentId] ?? 0) + 1 }));
    return () => setStageCounts((counts) => ({ ...counts, [stageAppointmentId]: Math.max(0, (counts[stageAppointmentId] ?? 1) - 1) }));
  }, []);

  // Stable for the life of the portal, so views (such as the device dialog) can depend on them.
  const actions = useMemo(() => ({
    setMicrophone: (on: boolean) => session.setMicrophone(on),
    setCamera: (on: boolean) => session.setCamera(on),
    refreshDevices: () => session.refreshDevices(),
    selectCamera: (id: string) => session.selectCamera(id),
    selectMicrophone: (id: string) => session.selectMicrophone(id),
    selectSpeaker: (id: string) => session.selectSpeaker(id),
  }), [session]);
  const call: CallControls = useMemo(() => ({ ...snapshot, ...actions }), [actions, snapshot]);

  const value: ActiveECounselingCall = {
    role,
    state,
    live,
    appointmentId,
    participantName: sessionParticipant ?? activation?.participantName ?? null,
    call,
    otherTabActive,
    availabilityFor: (target) => joinAvailability({ appointmentId: target, activeAppointmentId: appointmentId, state, otherTabActive }),
    join,
    requestLeave,
    end,
    audio: { blocked: audioBlocked, resume: () => void resumeAudio() },
    canonical: { media, current: canonicalCurrent },
    capture: { canStop, stopping: capture.stopping, error: capture.error, stop: capture.stop },
    presentStage,
  };
  const stagePresented = appointmentId !== null && (stageCounts[appointmentId] ?? 0) > 0;
  // The full stage already shows how the call ended; the dock area doesn't repeat it later.
  if (stagePresented && endedNotice) setEndedNotice(null);

  return (
    <ActiveECounselingCallContext.Provider value={value}>
      {children}
      {/* The one element that plays the other person, mounted for the whole portal session. */}
      <audio ref={audioRef} autoPlay className="hidden" />
      <GlobalCallDock hidden={stagePresented} endedNotice={stagePresented ? null : endedNotice} onDismissEnded={() => setEndedNotice(null)} />
      <ConsequentialActionDialog
        open={leaveOpen}
        title="Leave this session?"
        confirmLabel="Leave session"
        pendingLabel="Leaving…"
        pending={false}
        error={null}
        variant="danger"
        onOpenChange={setLeaveOpen}
        onConfirm={() => {
          setLeaveOpen(false);
          void session.leave();
        }}
      >
        {leaveWarning(activeCapture)}
      </ConsequentialActionDialog>
    </ActiveECounselingCallContext.Provider>
  );
}
