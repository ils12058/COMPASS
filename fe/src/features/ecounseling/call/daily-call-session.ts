import type { DailyEvent, DailyEventObject } from "@daily-co/daily-js";
import { browserTestRuntimeEnabled } from "@/lib/browser-test-runtime";

import {
  activeCallPhases,
  cameraProblem,
  emptyDevices,
  expiredCredentialFailure,
  fatalCallFailure,
  initialCallSnapshot,
  joinConnectionFailure,
  previewCallPhases,
  projectDevices,
  projectParticipants,
  sameParticipant,
  selectedDevices,
  type CallCredential,
  type CallSnapshot,
  type DailyCallClient,
  type DailyCallClientFactory,
} from "./call-model";

// Every Daily event the call subscribes to. Provider recording/transcription events are hints that
// only ask COMPASS to re-read its own session state; `transcription-message` (live transcript text)
// is deliberately never subscribed, so no transcript text enters the page (ADR-093).
export const subscribedCallEvents = [
  "joined-meeting",
  "left-meeting",
  "error",
  "nonfatal-error",
  "participant-joined",
  "participant-updated",
  "participant-left",
  "track-started",
  "track-stopped",
  "network-connection",
  "network-quality-change",
  "camera-error",
  "available-devices-updated",
  "selected-devices-updated",
  "local-audio-level",
  "recording-started",
  "recording-stopped",
  "recording-error",
  "transcription-started",
  "transcription-stopped",
  "transcription-error",
] as const satisfies readonly DailyEvent[];

const providerMediaEvents: ReadonlySet<DailyEvent> = new Set([
  "recording-started",
  "recording-stopped",
  "recording-error",
  "transcription-started",
  "transcription-stopped",
  "transcription-error",
]);

declare global {
  interface Window {
    // Local browser regressions use a fake Call Object and never reach Daily. Ordinary production
    // builds compile the seam away; explicit test builds still require a loopback page.
    __COMPASS_FAKE_DAILY__?: DailyCallClientFactory;
  }
}

async function loadDailyFactory(): Promise<DailyCallClientFactory> {
  // Keep the literal build guard here so ordinary production drops even the window seam read.
  if ((process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE === "1") && browserTestRuntimeEnabled() && window.__COMPASS_FAKE_DAILY__) {
    return window.__COMPASS_FAKE_DAILY__;
  }
  const daily = await import("@daily-co/daily-js");
  return daily.default;
}

function browserSupportsSpeakerSelection(): boolean {
  return typeof HTMLMediaElement !== "undefined" && typeof HTMLMediaElement.prototype.setSinkId === "function";
}

// Daily allows one live call object per page. A call that is still leaving and being destroyed is
// awaited before another is created, including one created by a newly mounted workspace.
let pendingTeardown: Promise<void> = Promise.resolve();

export type JoinRequest = {
  fetchCredential: () => Promise<CallCredential>;
  describeCredentialError: (error: unknown) => string;
};

export type CallSessionOptions = {
  loadFactory?: () => Promise<DailyCallClientFactory>;
  supportsSpeakerSelection?: () => boolean;
  now?: () => number;
};

// One E-Counseling call: a Daily Call Object, the events it reports, and the COMPASS projection the
// stage and the call dock render. It has no React dependency. The portal's E-Counseling runtime
// (ADR-094) owns the only instance and binds it to React with useSyncExternalStore, so the call
// outlives any one page.
//
// Each join or pre-join device preview is an attempt with its own number. Every asynchronous
// continuation and Daily event checks that its attempt is still current, so a late credential, a
// slow permission prompt, a slow join or an event from a call being destroyed can never replace
// newer state. Construction has no side effects and nothing starts devices or joins without explicit
// user action, so React Strict Mode's repeated renders and effects cannot create a second call
// object or a second join.
export class DailyCallSession {
  private snapshot: CallSnapshot = initialCallSnapshot;
  private readonly listeners = new Set<() => void>();
  private call: DailyCallClient | null = null;
  private unsubscribers: Array<() => void> = [];
  private attempt = 0;
  private onProviderMediaEvent: () => void = () => {};
  // A mute or camera toggle Daily has not reported back yet, so an unrelated participant update
  // carrying the previous state does not flip the control back.
  private requested: { microphone?: { on: boolean; at: number }; camera?: { on: boolean; at: number } } = {};
  // Ephemeral in-memory device and mute choices made during pre-join testing, carried into join().
  private preferred: {
    camera?: string;
    microphone?: string;
    speaker?: string;
    cameraOn?: boolean;
    microphoneOn?: boolean;
  } = {};
  private prePreviewPhase: "idle" | "left" = "idle";
  private readonly loadFactory: () => Promise<DailyCallClientFactory>;
  private readonly supportsSpeakerSelection: () => boolean;
  private readonly now: () => number;

  constructor(options: CallSessionOptions = {}) {
    this.loadFactory = options.loadFactory ?? loadDailyFactory;
    this.supportsSpeakerSelection = options.supportsSpeakerSelection ?? browserSupportsSpeakerSelection;
    this.now = options.now ?? Date.now;
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = () => this.snapshot;

  setProviderMediaEventHandler(handler: () => void) {
    this.onProviderMediaEvent = handler;
  }

  private update(changes: Partial<CallSnapshot>) {
    const next = { ...this.snapshot, ...changes };
    const keys = Object.keys(changes) as Array<keyof CallSnapshot>;
    if (keys.every((key) => Object.is(next[key], this.snapshot[key]))) return;
    this.snapshot = next;
    for (const listener of this.listeners) listener();
  }

  private isCurrent(attempt: number, call?: DailyCallClient) {
    return attempt === this.attempt && (call === undefined || call === this.call);
  }

  // Starts a strictly local pre-join device check on the single Call Object without requesting a
  // meeting credential or joining a Daily room.
  async startPreview(): Promise<void> {
    const phase = this.snapshot.phase;
    if (phase !== "idle" && phase !== "left" && phase !== "failed") return;
    this.prePreviewPhase = phase === "left" ? "left" : "idle";
    const attempt = ++this.attempt;
    const cameraOn = this.preferred.cameraOn ?? this.snapshot.cameraOn;
    const microphoneOn = this.preferred.microphoneOn ?? this.snapshot.microphoneOn;
    this.update({
      phase: "starting-preview",
      failure: null,
      local: null,
      remote: null,
      cameraOn,
      microphoneOn,
      localAudioLevel: 0,
      mediaProblem: null,
    });

    let call: DailyCallClient | null = null;
    try {
      await pendingTeardown;
      if (!this.isCurrent(attempt)) return;
      const factory = await this.loadFactory();
      if (!this.isCurrent(attempt)) return;
      const orphan = factory.getCallInstance?.();
      if (orphan && !orphan.isDestroyed()) await orphan.destroy().catch(() => undefined);
      if (!this.isCurrent(attempt)) return;
      call = factory.createCallObject({});
      this.call = call;
      this.bind(call, attempt);
      const { camera: preferredCamera, microphone: preferredMicrophone, speaker: preferredSpeaker } = this.preferred;
      if (preferredSpeaker && this.supportsSpeakerSelection()) {
        await call.setOutputDeviceAsync({ outputDeviceId: preferredSpeaker }).catch(() => undefined);
        this.preferred.speaker = preferredSpeaker;
      }
      if (!this.isCurrent(attempt, call)) {
        this.stopLocalTracks(call);
        return;
      }
      if (preferredCamera || preferredMicrophone) {
        await call.setInputDevicesAsync({
          ...(preferredCamera ? { videoDeviceId: preferredCamera } : {}),
          ...(preferredMicrophone ? { audioDeviceId: preferredMicrophone } : {}),
        }).catch(() => undefined);
      }
      if (!this.isCurrent(attempt, call)) {
        this.stopLocalTracks(call);
        return;
      }
      if (call.startCamera) {
        await call.startCamera({
          startVideoOff: !cameraOn,
          startAudioOff: !microphoneOn,
        });
      }
      if (!this.isCurrent(attempt, call)) {
        this.stopLocalTracks(call);
        if (!call.isDestroyed()) await call.destroy().catch(() => undefined);
        return;
      }
      if (!cameraOn) {
        this.requested.camera = { on: false, at: this.now() };
        call.setLocalVideo(false);
      }
      if (!microphoneOn) {
        this.requested.microphone = { on: false, at: this.now() };
        call.setLocalAudio(false);
      }
      if (call.startLocalAudioLevelObserver) {
        await call.startLocalAudioLevelObserver(100).catch(() => undefined);
      }
      if (!this.isCurrent(attempt, call)) {
        this.stopLocalTracks(call);
        return;
      }
      this.update({ phase: "preview", deviceCheckCompleted: true });
      this.refreshParticipants(call);
      await this.refreshDevices();
    } catch {
      if (!this.isCurrent(attempt)) {
        if (call) {
          this.stopLocalTracks(call);
          if (!call.isDestroyed()) await call.destroy().catch(() => undefined);
        }
        return;
      }
      const problem = this.snapshot.mediaProblem ?? {
        camera: true,
        microphone: true,
        source: "camera-error" as const,
        message: "Your camera and microphone couldn't be started.",
      };
      void this.teardown();
      this.update({
        phase: "preview",
        local: null,
        localAudioLevel: 0,
        deviceCheckCompleted: true,
        mediaProblem: problem,
      });
    }
  }

  // Closes a local device preview and releases its local media tracks and audio observer while
  // keeping the selected device and mute preferences in memory for the upcoming join. Never touches
  // an active or connecting call.
  async closePreview(): Promise<void> {
    if (!previewCallPhases.has(this.snapshot.phase)) return;
    this.attempt += 1;
    const done = this.teardown();
    this.requested = {};
    this.update({
      phase: this.prePreviewPhase,
      failure: null,
      local: null,
      remote: null,
      localAudioLevel: 0,
      mediaProblem: null,
    });
    await done;
  }

  async join({ fetchCredential, describeCredentialError }: JoinRequest): Promise<void> {
    const phase = this.snapshot.phase;
    if (phase !== "idle" && phase !== "left" && phase !== "failed" && !previewCallPhases.has(phase)) return;
    const cameraOn = this.preferred.cameraOn ?? this.snapshot.cameraOn;
    const microphoneOn = this.preferred.microphoneOn ?? this.snapshot.microphoneOn;
    const deviceCheckCompleted = this.snapshot.deviceCheckCompleted;
    const devices = this.snapshot.devices;
    const reusablePreviewCall = phase === "preview" && this.call && !this.call.isDestroyed() ? this.call : null;
    const attempt = ++this.attempt;
    if (reusablePreviewCall) {
      for (const unsubscribe of this.unsubscribers.splice(0)) unsubscribe();
      try {
        reusablePreviewCall.stopLocalAudioLevelObserver?.();
      } catch {
        // Best effort.
      }
      this.bind(reusablePreviewCall, attempt);
    } else if (this.call) {
      void this.teardown();
    }
    this.update({
      ...initialCallSnapshot,
      phase: "requesting",
      cameraOn,
      microphoneOn,
      deviceCheckCompleted,
      devices,
    });

    let credential: CallCredential | null;
    try {
      credential = await fetchCredential();
    } catch (error) {
      if (this.isCurrent(attempt)) {
        void this.teardown();
        this.update({
          ...initialCallSnapshot,
          cameraOn,
          microphoneOn,
          deviceCheckCompleted,
          devices,
          phase: "failed",
          failure: { kind: "credential", message: describeCredentialError(error) },
        });
      }
      return;
    }
    // A credential that arrives for a superseded attempt is dropped unused.
    if (!this.isCurrent(attempt)) return;
    const expiresAt = Date.parse(credential.expiresAt);
    if (!credential.roomUrl || !credential.token || !Number.isFinite(expiresAt) || expiresAt <= this.now()) {
      void this.teardown();
      this.update({
        ...initialCallSnapshot,
        cameraOn,
        microphoneOn,
        deviceCheckCompleted,
        devices,
        phase: "failed",
        failure: expiredCredentialFailure,
      });
      return;
    }

    let call: DailyCallClient | null = null;
    try {
      if (reusablePreviewCall && !reusablePreviewCall.isDestroyed() && this.call === reusablePreviewCall) {
        call = reusablePreviewCall;
      } else {
        await pendingTeardown;
        if (!this.isCurrent(attempt)) return;
        const factory = await this.loadFactory();
        if (!this.isCurrent(attempt)) return;
        // Defensive: never run beside a call object that an earlier page instance left behind.
        const orphan = factory.getCallInstance?.();
        if (orphan && !orphan.isDestroyed()) await orphan.destroy().catch(() => undefined);
        if (!this.isCurrent(attempt)) return;
        call = factory.createCallObject({});
        this.call = call;
        this.bind(call, attempt);
        const { camera: preferredCamera, microphone: preferredMicrophone, speaker: preferredSpeaker } = this.preferred;
        if (preferredSpeaker && this.supportsSpeakerSelection()) {
          await call.setOutputDeviceAsync({ outputDeviceId: preferredSpeaker }).catch(() => undefined);
          this.preferred.speaker = preferredSpeaker;
        }
        if (!this.isCurrent(attempt, call)) return;
        if (preferredCamera || preferredMicrophone) {
          await call.setInputDevicesAsync({
            ...(preferredCamera ? { videoDeviceId: preferredCamera } : {}),
            ...(preferredMicrophone ? { audioDeviceId: preferredMicrophone } : {}),
          }).catch(() => undefined);
        }
        if (!this.isCurrent(attempt, call)) return;
        if (!cameraOn) call.setLocalVideo(false);
        if (!microphoneOn) call.setLocalAudio(false);
      }
      if (!cameraOn) this.requested.camera = { on: false, at: this.now() };
      if (!microphoneOn) this.requested.microphone = { on: false, at: this.now() };
      this.update({ phase: "joining", localAudioLevel: 0 });
      const { roomUrl, token } = credential;
      // The credential is used once, by this join, and is not kept anywhere else.
      credential = null;
      await call.join({ url: roomUrl, token });
    } catch {
      credential = null;
      if (!this.isCurrent(attempt)) return;
      void this.teardown();
      this.update({
        ...initialCallSnapshot,
        cameraOn,
        microphoneOn,
        deviceCheckCompleted,
        phase: "failed",
        failure: joinConnectionFailure,
      });
      return;
    }
    if (call && this.isCurrent(attempt, call) && this.snapshot.phase === "joining") this.markJoined(call);
  }

  async leave(): Promise<void> {
    const call = this.call;
    if (!call || !activeCallPhases.has(this.snapshot.phase)) return;
    // Leaving supersedes the join attempt: its late result and the call's own events are ignored.
    const attempt = ++this.attempt;
    this.update({ phase: "leaving", localAudioLevel: 0 });
    try {
      await call.leave();
    } catch {
      // Leaving is best effort; destroy still runs.
    }
    if (!this.isCurrent(attempt)) return;
    await this.teardown();
    if (!this.isCurrent(attempt)) return;
    this.preferred = {};
    this.prePreviewPhase = "idle";
    this.update({ ...initialCallSnapshot, phase: "left" });
  }

  // Terminal cleanup: the portal runtime ending (unmount, sign-out, a confirmed lost session). It
  // supersedes any attempt, leaves and destroys the call, and resolves once destruction finishes.
  // The session object stays reusable, which is what React Strict Mode's simulated unmount and
  // remount expect. A page that merely stops showing the call never calls this.
  dispose(): Promise<void> {
    this.attempt += 1;
    const done = this.teardown();
    this.requested = {};
    this.preferred = {};
    this.prePreviewPhase = "idle";
    this.update(initialCallSnapshot);
    return done;
  }

  setMicrophone(on: boolean) {
    const phase = this.snapshot.phase;
    if (!activeCallPhases.has(phase) && !previewCallPhases.has(phase)) return;
    this.preferred.microphoneOn = on;
    const call = this.call;
    if (call && (activeCallPhases.has(phase) || phase === "preview")) {
      call.setLocalAudio(on);
      this.requested.microphone = { on, at: this.now() };
    }
    this.update({ microphoneOn: on, ...(on ? {} : { localAudioLevel: 0 }) });
  }

  setCamera(on: boolean) {
    const phase = this.snapshot.phase;
    if (!activeCallPhases.has(phase) && !previewCallPhases.has(phase)) return;
    this.preferred.cameraOn = on;
    const call = this.call;
    if (call && (activeCallPhases.has(phase) || phase === "preview")) {
      call.setLocalVideo(on);
      this.requested.camera = { on, at: this.now() };
    }
    this.update({ cameraOn: on });
  }

  async refreshDevices(): Promise<void> {
    const call = this.call;
    const attempt = this.attempt;
    if (!call) return;
    try {
      const [{ devices }, selected] = await Promise.all([call.enumerateDevices(), call.getInputDevices()]);
      if (!this.isCurrent(attempt, call)) return;
      const next = projectDevices(devices, selected, this.supportsSpeakerSelection(), this.preferred.speaker ?? this.snapshot.devices.speaker);
      if (this.preferred.camera && !next.cameras.some((option) => option.id === this.preferred.camera)) {
        this.preferred.camera = next.camera ?? undefined;
      }
      if (this.preferred.microphone && !next.microphones.some((option) => option.id === this.preferred.microphone)) {
        this.preferred.microphone = next.microphone ?? undefined;
      }
      if (this.preferred.speaker && !next.speakers.some((option) => option.id === this.preferred.speaker)) {
        this.preferred.speaker = next.speaker ?? undefined;
      }
      this.update({ devices: next, mediaProblem: this.deviceAvailabilityProblem(next) });
    } catch {
      // Device lists are refreshed again on the next device change; the call itself is unaffected.
    }
  }

  // A device disconnected during the call, or none of that kind is connected during pre-join check.
  // Daily moves to another device on its own when one remains; a notice is needed only when none of
  // that kind is left.
  private deviceAvailabilityProblem(devices: typeof emptyDevices) {
    const current = this.snapshot.mediaProblem;
    if (current && current.source === "camera-error") return current;
    const inPreview = previewCallPhases.has(this.snapshot.phase);
    const camera = devices.cameras.length === 0 && (inPreview || this.snapshot.devices.cameras.length > 0);
    const microphone = devices.microphones.length === 0 && (inPreview || this.snapshot.devices.microphones.length > 0);
    if (camera || microphone) {
      return { camera, microphone, source: "device-missing" as const, message: camera && microphone ? "No camera or microphone is connected." : camera ? "No camera is connected." : "No microphone is connected." };
    }
    if (current?.source === "device-missing" && (!current.camera || devices.cameras.length) && (!current.microphone || devices.microphones.length)) return null;
    return current;
  }

  async selectCamera(deviceId: string) {
    const call = this.requireCall();
    const attempt = this.attempt;
    const selected = await call.setInputDevicesAsync({ videoDeviceId: deviceId });
    if (this.isCurrent(attempt, call)) {
      const next = selectedDevices(this.snapshot.devices, selected);
      this.preferred.camera = next.camera ?? undefined;
      this.update({ devices: next });
    }
  }

  async selectMicrophone(deviceId: string) {
    const call = this.requireCall();
    const attempt = this.attempt;
    const selected = await call.setInputDevicesAsync({ audioDeviceId: deviceId });
    if (this.isCurrent(attempt, call)) {
      const next = selectedDevices(this.snapshot.devices, selected);
      this.preferred.microphone = next.microphone ?? undefined;
      this.update({ devices: next });
    }
  }

  // Daily records the output device; the stage also applies it to the remote audio element it owns.
  async selectSpeaker(deviceId: string) {
    const call = this.requireCall();
    const attempt = this.attempt;
    await call.setOutputDeviceAsync({ outputDeviceId: deviceId });
    if (this.isCurrent(attempt, call)) {
      this.preferred.speaker = deviceId;
      this.update({ devices: { ...this.snapshot.devices, speaker: deviceId } });
    }
  }

  private requireCall(): DailyCallClient {
    if (!this.call || (!activeCallPhases.has(this.snapshot.phase) && this.snapshot.phase !== "preview")) {
      throw new Error("The call is not active.");
    }
    return this.call;
  }

  private markJoined(call: DailyCallClient) {
    this.update({ phase: "joined", failure: null, localAudioLevel: 0 });
    this.refreshParticipants(call);
    void this.refreshDevices();
  }

  // Daily's report decides the control state, except that a toggle not yet reported back holds for a
  // moment; one Daily never confirms gives way to what Daily reports.
  private reportedToggle(kind: "microphone" | "camera", reported: boolean): boolean {
    const request = this.requested[kind];
    if (!request) return reported;
    if (request.on === reported || this.now() - request.at > 3000) {
      delete this.requested[kind];
      return reported;
    }
    return request.on;
  }

  private refreshParticipants(call: DailyCallClient) {
    const { local, remote } = projectParticipants(call.participants());
    const changes: Partial<CallSnapshot> = {};
    if (!sameParticipant(local, this.snapshot.local)) changes.local = local;
    if (!sameParticipant(remote, this.snapshot.remote)) changes.remote = remote;
    if (local) {
      changes.microphoneOn = this.reportedToggle("microphone", !local.audio.off);
      changes.cameraOn = this.reportedToggle("camera", !local.video.off);
    }
    this.update(changes);
  }

  private bind(call: DailyCallClient, attempt: number) {
    const listen = <T extends DailyEvent>(event: T, handler: (payload: DailyEventObject<T>) => void) => {
      const guarded = (payload: DailyEventObject<T>) => {
        if (this.isCurrent(attempt, call)) handler(payload);
      };
      call.on(event, guarded);
      this.unsubscribers.push(() => call.off(event, guarded));
    };
    const refresh = () => this.refreshParticipants(call);

    for (const event of subscribedCallEvents) {
      switch (event) {
        case "joined-meeting":
          listen(event, () => this.markJoined(call));
          break;
        case "left-meeting":
          listen(event, () => {
            // leave() finishes its own teardown; this is Daily ending the call by itself.
            if (this.snapshot.phase === "leaving" || this.snapshot.phase === "failed") return;
            void this.teardown();
            this.update({ ...initialCallSnapshot, phase: "left" });
          });
          break;
        case "error":
          listen(event, (payload) => {
            void this.teardown();
            this.update({ ...initialCallSnapshot, phase: "failed", failure: fatalCallFailure(payload) });
          });
          break;
        case "nonfatal-error":
          // Screen share, processors and live streaming are not used; input settings problems
          // surface through camera-error and the device list.
          listen(event, () => {});
          break;
        case "participant-joined":
        case "participant-updated":
        case "participant-left":
        case "track-started":
        case "track-stopped":
          listen(event, refresh);
          break;
        case "network-connection":
          listen(event, (payload) => {
            if (payload.event === "interrupted" && this.snapshot.phase === "joined") this.update({ phase: "reconnecting" });
            else if (payload.event === "connected" && this.snapshot.phase === "reconnecting") this.update({ phase: "joined" });
          });
          break;
        case "network-quality-change":
          listen(event, (payload) => this.update({ network: payload.networkState }));
          break;
        case "camera-error":
          listen(event, (payload) => this.update({ mediaProblem: cameraProblem(payload) }));
          break;
        case "available-devices-updated":
          listen(event, () => void this.refreshDevices());
          break;
        case "selected-devices-updated":
          listen(event, (payload) => {
            const next = selectedDevices(this.snapshot.devices, payload.devices);
            if (next.camera) this.preferred.camera = next.camera;
            if (next.microphone) this.preferred.microphone = next.microphone;
            if (next.speaker) this.preferred.speaker = next.speaker;
            this.update({ devices: next });
          });
          break;
        case "local-audio-level":
          listen(event, (payload) => {
            if (!previewCallPhases.has(this.snapshot.phase) || !this.snapshot.microphoneOn) return;
            const level = typeof payload.audioLevel === "number" && Number.isFinite(payload.audioLevel) ? Math.max(0, Math.min(1, payload.audioLevel)) : 0;
            this.update({ localAudioLevel: level });
          });
          break;
        default:
          if (providerMediaEvents.has(event)) listen(event, () => this.onProviderMediaEvent());
      }
    }
  }

  private stopLocalTracks(call: DailyCallClient) {
    try {
      call.stopLocalAudioLevelObserver?.();
    } catch {
      // Best effort.
    }
    try {
      const local = call.participants()?.local;
      const videoTrack = local?.tracks?.video?.persistentTrack ?? local?.tracks?.video?.track;
      const audioTrack = local?.tracks?.audio?.persistentTrack ?? local?.tracks?.audio?.track;
      videoTrack?.stop?.();
      audioTrack?.stop?.();
    } catch {
      // Best effort; Daily's destroy() also stops tracks.
    }
  }

  // Unsubscribes every listener, stops local preview tracks/observers, leaves when still connected,
  // and always destroys the call object.
  private teardown(): Promise<void> {
    const call = this.call;
    if (!call) return pendingTeardown;
    this.call = null;
    this.requested = {};
    for (const unsubscribe of this.unsubscribers.splice(0)) unsubscribe();
    this.stopLocalTracks(call);
    const done = (async () => {
      try {
        const state = call.meetingState();
        if (state === "joined-meeting" || state === "joining-meeting") await call.leave();
      } catch {
        // Best effort.
      }
      try {
        if (!call.isDestroyed()) await call.destroy();
      } catch {
        // Best effort; Daily refuses a second call object until destruction completes.
      }
    })();
    pendingTeardown = Promise.all([pendingTeardown, done]).then(() => undefined);
    return done;
  }
}
