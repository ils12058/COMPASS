"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { activeCallPhases, previewCallPhases, type CallPhase } from "@/features/ecounseling/call/call-model";
import { DailyCallSession } from "@/features/ecounseling/call/daily-call-session";
import { useRemoteAudioPlayback } from "@/features/ecounseling/call/participant-media";
import { getECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { ecounselingErrorMessage, isLiveOrTransitionalCapture } from "@/features/ecounseling/ecounseling-shared";
import { useECounselingFreshness } from "@/features/ecounseling/consent-freshness-provider";
import { useCaptureStop } from "@/features/ecounseling/use-capture-stop";
import { ecounselingResourceAccess, type ResourceDenial } from "@/features/ecounseling/ecounseling-resource-access";
import { useECounselingResourceDenial } from "@/features/ecounseling/use-ecounseling-resource-access";
import { safeQueryData, shouldHideProtectedData } from "@/features/freshness/query-freshness";
import {
  eCounselingCreateJoinCredential,
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
  useECounselingGetAssignedWorkspace,
  useECounselingGetMyWorkspace,
} from "@/lib/api/generated/e-counseling/e-counseling";
import type { UserSummary } from "@/lib/api/generated/model";
import { isOpaqueRealtimeId } from "@/features/realtime/realtime-protocol";

import { ActiveECounselingCallContext, type ActiveECounselingCall, type CallControls } from "./active-call-context";
import { CrossTabCallCoordinator } from "./cross-tab-call-coordinator";
import { GlobalCallDock } from "./global-call-dock";
import { activeCaptureKinds, captureCessationWarning, isLiveRuntime, joinAvailability, runtimeState } from "./runtime-model";
import {
  calculateTimingPhase,
  getNextTimingDelayMs,
  getSessionTimingNotice,
  getTimingTransitionAnnouncement,
  type ActiveECounselingTiming,
  type SessionTimingPhase,
} from "./session-timing";

const MAX_BROWSER_TIMEOUT_MS = 2_147_000_000;

// The portal's authentication as PortalBoundary knows it. Only "signed-out" (the server answered that
// the session is gone) ends the call; "unverified" (the session couldn't be checked) keeps a working
// call while the portal fails closed around it.
export type PortalAuthState = "pending" | "confirmed" | "unverified" | "signed-out";

type Activation = { appointmentId: string; participantName: string; endsAt?: string };

// The one E-Counseling call of an authenticated portal session (ADR-094). It owns the Daily Call
// Object for as long as the portal is open, so moving between portal pages never leaves or rejoins
// the call; the session page's full stage and the call dock are two views of it. It also owns:
//   - the session state COMPASS reports for the call, refreshed while the call lasts, through the
//     same generated query (and cache) the session page uses;
//   - the one element that plays the other person's audio;
//   - either participant's unresolved capture warning, and the Counselor's protective stop;
//   - a tab's advisory lease, so a second COMPASS tab doesn't start another call.
// It ends the call on Leave, when the call itself ends, on sign-out, when the server confirms the
// session is gone, on confirmed resource denial, and when the portal unmounts. Nothing restores a
// call after a reload or access recovery.
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
  const freshness = useECounselingFreshness();
  const resourceAccess = ecounselingResourceAccess(queryClient);
  const joinAttempt = useRef(0);
  const [session] = useState(() => new DailyCallSession());
  const [coordinator] = useState(() => new CrossTabCallCoordinator());
  const snapshot = useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
  const otherTabActive = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot, () => false);
  const [activation, setActivation] = useState<Activation | null>(null);
  const [previewAppointmentId, setPreviewAppointmentId] = useState<string | null>(null);
  const previewAppointmentRef = useRef<string | null>(null);
  const [claiming, setClaiming] = useState(false);
  const [stageCounts, setStageCounts] = useState<Record<string, number>>({});
  const stageCountsRef = useRef<Record<string, number>>({});
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [endedNotice, setEndedNotice] = useState<string | null>(null);
  const [dismissedDenial, setDismissedDenial] = useState<ResourceDenial | null>(null);
  const appointmentId = activation?.appointmentId ?? null;
  const trackedAppointmentId = appointmentId ?? previewAppointmentId;
  const denial = useECounselingResourceDenial(trackedAppointmentId);
  const access = user ? getECounselingAccess(user) : null;
  const role = access?.isStudent ? "STUDENT" : access?.isCounselor ? "COUNSELOR" : null;
  // A session the server confirmed is gone has no call, whatever was active a moment ago.
  const activated = activation !== null && authState !== "signed-out" && !denial;
  const state = runtimeState({ activated, claiming, phase: snapshot.phase });
  const live = isLiveRuntime(state);
  useEffect(() => {
    freshness?.setActiveCall(live ? appointmentId : null);
    return () => freshness?.setActiveCall(null);
  }, [freshness, live, appointmentId]);

  // COMPASS's own view of the call's session, kept fresh while the call lasts, wherever the person
  // is in the portal. The session page reads the same query, so both show one truth.
  const observedId = appointmentId ?? "";
  const studentSession = useECounselingGetMyWorkspace(observedId, { query: {
    enabled: live && role === "STUDENT" && appointmentId !== null,
    retry: false,
    refetchInterval: false,
  } });
  const counselorSession = useECounselingGetAssignedWorkspace(observedId, { query: {
    enabled: live && role === "COUNSELOR" && appointmentId !== null,
    retry: false,
    refetchInterval: false,
  } });
  const observed = role === "STUDENT" ? studentSession : counselorSession;
  const protectedUnavailable = Boolean(denial) || shouldHideProtectedData(observed.error);
  const media = protectedUnavailable ? undefined : role === "STUDENT" ? safeQueryData(studentSession)?.data.media : safeQueryData(counselorSession)?.data.media;
  const sessionParticipant = protectedUnavailable ? null : role === "STUDENT" ? safeQueryData(studentSession)?.data.counselor.display_name : safeQueryData(counselorSession)?.data.student.display_name;
  const canonicalCurrent = !protectedUnavailable && observed.isSuccess;
  const appointmentData = protectedUnavailable
    ? undefined
    : role === "STUDENT"
      ? safeQueryData(studentSession)?.data.appointment
      : safeQueryData(counselorSession)?.data.appointment;
  const canonicalEndsAt = appointmentData?.ends_at ?? activation?.endsAt ?? null;
  const connected = snapshot.phase === "joined" || snapshot.phase === "reconnecting";
  const inCall = live && connected;

  const [timingTick, setTimingTick] = useState(() => Date.now());
  const timingPhase: SessionTimingPhase = inCall && canonicalEndsAt
    ? calculateTimingPhase({ endsAt: canonicalEndsAt, now: timingTick, connected })
    : "NORMAL";

  const [prevTimingKey, setPrevTimingKey] = useState<string | null>(null);
  const [timingAnnouncement, setTimingAnnouncement] = useState<string | null>(null);

  const currentTimingKey = inCall && canonicalEndsAt && timingPhase !== "NORMAL"
    ? `${appointmentId}:${canonicalEndsAt}:${timingPhase}`
    : null;

  if (prevTimingKey !== currentTimingKey) {
    setPrevTimingKey(currentTimingKey);
    if (!currentTimingKey) {
      setTimingAnnouncement(null);
    } else {
      const prevPhase = prevTimingKey ? (prevTimingKey.split(":")[2] as SessionTimingPhase) : null;
      const announcement = getTimingTransitionAnnouncement({
        previousPhase: prevPhase,
        currentPhase: timingPhase,
      });
      setTimingAnnouncement(announcement);
    }
  }

  useEffect(() => {
    if (!live || !appointmentId || !canonicalEndsAt) return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const scheduleNext = () => {
      if (cancelled) return;
      const now = Date.now();
      const delay = getNextTimingDelayMs({ endsAt: canonicalEndsAt, now });
      if (delay === null) return;

      timer = setTimeout(() => {
        setTimingTick(Date.now());
        scheduleNext();
      }, Math.min(delay, MAX_BROWSER_TIMEOUT_MS));
    };

    scheduleNext();

    const handleWake = () => {
      setTimingTick(Date.now());
      scheduleNext();
    };

    window.addEventListener("visibilitychange", handleWake);
    window.addEventListener("focus", handleWake);
    window.addEventListener("online", handleWake);

    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
      window.removeEventListener("visibilitychange", handleWake);
      window.removeEventListener("focus", handleWake);
      window.removeEventListener("online", handleWake);
    };
  }, [appointmentId, canonicalEndsAt, live]);

  const timingNotice = inCall ? getSessionTimingNotice(timingPhase) : null;
  const timing: ActiveECounselingTiming = useMemo(
    () => ({
      phase: inCall ? timingPhase : "NORMAL",
      notice: timingNotice,
      endsAt: canonicalEndsAt,
    }),
    [canonicalEndsAt, inCall, timingNotice, timingPhase]
  );

  const refreshSession = useCallback(async () => {
    if (!appointmentId || !role || resourceAccess.getDenial(appointmentId)) return;
    const queryKey = role === "STUDENT" ? getECounselingGetMyWorkspaceQueryKey(appointmentId) : getECounselingGetAssignedWorkspaceQueryKey(appointmentId);
    if (freshness && isOpaqueRealtimeId(appointmentId)) await freshness.refreshWorkspace(appointmentId);
    else await queryClient.invalidateQueries({ queryKey, exact: true }, { cancelRefetch: false });
  }, [appointmentId, freshness, queryClient, resourceAccess, role]);

  // Daily's recording and transcription events only ask COMPASS to re-read the session.
  useEffect(() => {
    session.setProviderMediaEventHandler(() => void refreshSession());
  }, [refreshSession, session]);

  const capture = useCaptureStop(appointmentId, refreshSession);
  const canManageMedia = Boolean(access?.canManageMediaAssigned);
  // Students never get a stop: capture is the assigned Counselor's governed action.
  const canStop = {
    recording: !protectedUnavailable && canManageMedia && Boolean(media && isLiveOrTransitionalCapture(media.recording.capture_status)),
    transcription: !protectedUnavailable && canManageMedia && Boolean(media && isLiveOrTransitionalCapture(media.transcription.capture_status)),
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
      joinAttempt.current += 1;
      void session.dispose();
    };
  }, [coordinator, session]);

  // A session the server confirmed is gone ends the call before the portal clears its data.
  useEffect(() => {
    if (authState !== "signed-out") return;
    joinAttempt.current += 1;
    coordinator.release();
    previewAppointmentRef.current = null;
    void session.dispose();
  }, [authState, coordinator, session]);

  // A resource denial is independent of the account session. dispose() immediately supersedes
  // pending credentials/Daily callbacks and clears local tracks; destruction finishes asynchronously.
  useEffect(() => {
    if (!denial) return;
    joinAttempt.current += 1;
    coordinator.release();
    previewAppointmentRef.current = null;
    void session.dispose();
  }, [coordinator, denial, session]);

  useEffect(() => resourceAccess.subscribe(() => {
    const currentTracked = appointmentId ?? previewAppointmentRef.current;
    if (!resourceAccess.getDenial(currentTracked)) return;
    joinAttempt.current += 1;
    coordinator.release();
    setLeaveOpen(false);
    previewAppointmentRef.current = null;
    setPreviewAppointmentId(null);
    setActivation((current) => current ? { ...current, participantName: "Your session" } : null);
    void session.dispose();
  }), [appointmentId, coordinator, resourceAccess, session]);

  // Another tab acquiring a live call closes any local device preview in this tab.
  useEffect(() => {
    if (otherTabActive && previewCallPhases.has(snapshot.phase)) {
      void session.closePreview();
    }
  }, [otherTabActive, session, snapshot.phase]);

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

  const startPreview = useCallback(async (targetAppointmentId: string) => {
    if (authState === "signed-out" || resourceAccess.getDenial(targetAppointmentId) || otherTabActive) return;
    if (isLiveRuntime(runtimeState({ activated, claiming, phase: session.getSnapshot().phase }))) return;
    if (previewAppointmentRef.current && previewAppointmentRef.current !== targetAppointmentId) {
      await session.dispose();
    }
    previewAppointmentRef.current = targetAppointmentId;
    setPreviewAppointmentId(targetAppointmentId);
    await session.startPreview();
  }, [activated, authState, claiming, otherTabActive, resourceAccess, session]);

  const closePreview = useCallback(async (targetAppointmentId?: string) => {
    if (targetAppointmentId && previewAppointmentRef.current && previewAppointmentRef.current !== targetAppointmentId) return;
    await session.closePreview();
  }, [session]);

  const join = useCallback(async (target: Activation) => {
    if (authState === "signed-out" || resourceAccess.getDenial(target.appointmentId)) return;
    if (isLiveRuntime(runtimeState({ activated, claiming, phase: session.getSnapshot().phase }))) return;
    const attempt = ++joinAttempt.current;
    if (previewAppointmentRef.current && previewAppointmentRef.current !== target.appointmentId) {
      previewAppointmentRef.current = null;
      setPreviewAppointmentId(null);
      await session.dispose();
      if (attempt !== joinAttempt.current || resourceAccess.getDenial(target.appointmentId)) return;
    }
    const epoch = resourceAccess.epoch(target.appointmentId);
    setEndedNotice(null);
    setActivation(target);
    setClaiming(true);
    const acquired = await coordinator.acquire();
    if (attempt !== joinAttempt.current || resourceAccess.getDenial(target.appointmentId)) {
      if (acquired) coordinator.release();
      setClaiming(false);
      return;
    }
    setClaiming(false);
    if (!acquired) {
      setActivation(null);
      void session.closePreview();
      return;
    }
    const studentRole = role === "STUDENT";
    await session.join({
      fetchCredential: async () => {
        resourceAccess.assertAuthorized(target.appointmentId, epoch);
        // The credential is fetched without caching and used once by this join; it never enters
        // query caches, browser storage, the URL, logs or the other tabs.
        let result;
        try {
          result = await eCounselingCreateJoinCredential(target.appointmentId, { cache: "no-store" });
        } catch (error) {
          resourceAccess.requestFailed(error);
          throw error;
        }
        resourceAccess.assertAuthorized(target.appointmentId, epoch);
        return { roomUrl: result.data.room_url, token: result.data.meeting_token, expiresAt: result.data.token_expires_at };
      },
      describeCredentialError: (error) => ecounselingErrorMessage(error, "Couldn’t open the video session. Try again."),
    });
    const after = session.getSnapshot();
    if (!activeCallPhases.has(after.phase)) coordinator.release();
    if (after.failure?.kind === "credential" && !resourceAccess.getDenial(target.appointmentId)) {
      const queryKey = studentRole ? getECounselingGetMyWorkspaceQueryKey(target.appointmentId) : getECounselingGetAssignedWorkspaceQueryKey(target.appointmentId);
      void queryClient.invalidateQueries({ queryKey });
    }
  }, [activated, authState, claiming, coordinator, queryClient, resourceAccess, role, session]);

  const activeCapture = denial?.captureKinds ?? (media ? activeCaptureKinds(media) : resourceAccess.captureWarnings(appointmentId));
  const requestLeave = useCallback(() => {
    if (activeCapture.length) setLeaveOpen(true);
    else void session.leave();
  }, [activeCapture.length, session]);

  const end = useCallback(async () => {
    joinAttempt.current += 1;
    coordinator.release();
    previewAppointmentRef.current = null;
    setPreviewAppointmentId(null);
    await session.dispose();
  }, [coordinator, session]);

  const presentStage = useCallback((stageAppointmentId: string) => {
    stageCountsRef.current[stageAppointmentId] = (stageCountsRef.current[stageAppointmentId] ?? 0) + 1;
    setStageCounts((counts) => ({ ...counts, [stageAppointmentId]: (counts[stageAppointmentId] ?? 0) + 1 }));
    return () => {
      const next = Math.max(0, (stageCountsRef.current[stageAppointmentId] ?? 1) - 1);
      stageCountsRef.current[stageAppointmentId] = next;
      setStageCounts((counts) => ({ ...counts, [stageAppointmentId]: next }));
      queueMicrotask(() => {
        if ((stageCountsRef.current[stageAppointmentId] ?? 0) === 0 && previewAppointmentRef.current === stageAppointmentId) {
          void session.closePreview();
        }
      });
    };
  }, [session]);

  // Stable for the life of the portal, so views (such as the device dialog) can depend on them.
  const actions = useMemo(() => ({
    startPreview: () => session.startPreview(),
    closePreview: () => session.closePreview(),
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
    previewAppointmentId: authState !== "signed-out" && !denial ? previewAppointmentId : null,
    participantName: protectedUnavailable ? null : sessionParticipant ?? activation?.participantName ?? null,
    call,
    otherTabActive,
    availabilityFor: (target) => joinAvailability({ appointmentId: target, activeAppointmentId: appointmentId, state, otherTabActive }),
    startPreview,
    closePreview,
    join,
    timing,
    requestLeave,
    end,
    audio: { blocked: audioBlocked, resume: () => void resumeAudio() },
    canonical: { media, current: canonicalCurrent },
    captureWarnings: activeCapture,
    capture: { canStop, stopping: capture.stopping, failed: capture.failed, error: capture.error, stop: capture.stop },
    presentStage,
  };
  const stagePresented = appointmentId !== null && (stageCounts[appointmentId] ?? 0) > 0;
  const denialNotice = denial && dismissedDenial !== denial
    ? `This E-Counseling session is unavailable. ${captureCessationWarning(activeCapture, "access-loss") ?? ""}`.trim()
    : null;
  // The full stage already shows how the call ended; the dock area doesn't repeat it later.
  if (stagePresented && endedNotice) setEndedNotice(null);

  return (
    <ActiveECounselingCallContext.Provider value={value}>
      {children}
      {/* Polite announcement for timing transitions (EC-1 Option A), announced once per portal runtime. */}
      <p aria-live="polite" className="sr-only">{timingAnnouncement}</p>
      {/* The one element that plays the other person, mounted for the whole portal session. */}
      <audio ref={audioRef} autoPlay className="hidden" />
      <GlobalCallDock
        hidden={!denial && stagePresented}
        endedNotice={denial ? denialNotice : stagePresented ? null : endedNotice}
        onDismissEnded={() => { setEndedNotice(null); setDismissedDenial(denial); }}
      />
      <ConsequentialActionDialog
        open={leaveOpen && !denial}
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
        <p>{captureCessationWarning(activeCapture, "leave")}</p>
      </ConsequentialActionDialog>
    </ActiveECounselingCallContext.Provider>
  );
}
