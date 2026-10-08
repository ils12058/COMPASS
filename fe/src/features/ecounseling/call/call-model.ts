import type {
  DailyCall,
  DailyDeviceInfos,
  DailyEventObjectCameraError,
  DailyEventObjectFatalError,
  DailyFactoryOptions,
  DailyMediaDeviceInfo,
  DailyParticipant,
  DailyParticipantsObject,
  DailyTrackState,
} from "@daily-co/daily-js";

// The Daily Call Object methods COMPASS uses (ADR-093). Daily is the media engine; COMPASS renders
// every visible part of the call. Recording and transcription methods are deliberately absent:
// those are institutional actions that only start or stop through the COMPASS backend (ADR-092).
export type DailyCallClient = Pick<
  DailyCall,
  | "join"
  | "leave"
  | "destroy"
  | "isDestroyed"
  | "meetingState"
  | "participants"
  | "setLocalAudio"
  | "setLocalVideo"
  | "enumerateDevices"
  | "getInputDevices"
  | "setInputDevicesAsync"
  | "setOutputDeviceAsync"
  | "on"
  | "off"
>;

export type DailyCallClientFactory = {
  createCallObject(options?: DailyFactoryOptions): DailyCallClient;
  getCallInstance?(): DailyCallClient | undefined;
};

// The short-lived join credential from the COMPASS backend. It lives only inside one join attempt.
export type CallCredential = { roomUrl: string; token: string; expiresAt: string };

// One closed lifecycle for the call, so the stage never derives its state from loose flags.
export type CallPhase =
  | "idle" // not in the call; the stage offers Join when the session is open
  | "requesting" // asking the COMPASS backend for a fresh join credential
  | "joining" // Daily is connecting
  | "joined"
  | "reconnecting" // the connection dropped and Daily is restoring it
  | "leaving"
  | "left" // this person left; Rejoin asks the backend again
  | "failed"; // the attempt or the call ended with an error; Try again asks the backend again

export const activeCallPhases: ReadonlySet<CallPhase> = new Set(["joining", "joined", "reconnecting"]);

export type CallFailureKind = "credential" | "connection" | "expired" | "replaced" | "unavailable" | "full" | "unsupported" | "unknown";
export type CallFailure = { kind: CallFailureKind; message: string };

export type NetworkState = "good" | "warning" | "bad" | "unknown";

export type TrackView = {
  // Daily's persistent track: the same MediaStreamTrack across mute and unmute, so a media
  // element is not reattached each time (Daily's recommendation for custom call UIs).
  track: MediaStreamTrack | null;
  // Media is flowing and can be shown or heard.
  playable: boolean;
  // Turned off by the participant: ordinary state, not a problem.
  off: boolean;
  // Blocked by permissions, a missing device or a device in use.
  blocked: boolean;
};

export type ParticipantView = {
  // Stable across rejoins: the COMPASS user UUID that the backend puts in the meeting token as
  // Daily `user_id`. Daily's `session_id` changes on every join, so it only identifies this join.
  key: string;
  sessionId: string;
  video: TrackView;
  audio: TrackView;
  network: NetworkState;
};

export type DeviceOption = { id: string; label: string };

export type CallDevices = {
  cameras: DeviceOption[];
  microphones: DeviceOption[];
  speakers: DeviceOption[];
  // What Daily reports as selected, never a remembered UI choice.
  camera: string | null;
  microphone: string | null;
  speaker: string | null;
  // Output selection is offered only where this browser supports it.
  speakerSelectable: boolean;
};

export type MediaProblem = {
  camera: boolean;
  microphone: boolean;
  message: string;
  // A missing device can clear itself when one is connected; a blocked or busy device needs the
  // person to act.
  source: "device-missing" | "camera-error";
};

export type CallSnapshot = {
  phase: CallPhase;
  failure: CallFailure | null;
  local: ParticipantView | null;
  remote: ParticipantView | null;
  // What this person turned on or off. A problem with the device is reported separately.
  microphoneOn: boolean;
  cameraOn: boolean;
  network: NetworkState;
  devices: CallDevices;
  mediaProblem: MediaProblem | null;
};

export const emptyDevices: CallDevices = {
  cameras: [],
  microphones: [],
  speakers: [],
  camera: null,
  microphone: null,
  speaker: null,
  speakerSelectable: false,
};

export const initialCallSnapshot: CallSnapshot = {
  phase: "idle",
  failure: null,
  local: null,
  remote: null,
  microphoneOn: true,
  cameraOn: true,
  network: "unknown",
  devices: emptyDevices,
  mediaProblem: null,
};

function trackView(state: DailyTrackState | undefined, local: boolean): TrackView {
  if (!state) return { track: null, playable: false, off: true, blocked: false };
  const off = state.state === "off";
  const blocked = state.state === "blocked";
  // A local track the camera produces is "sendable" before Daily reports it "playable".
  const playable = state.state === "playable" || (local && state.state === "sendable");
  return { track: off || blocked ? null : state.persistentTrack ?? state.track ?? null, playable, off, blocked };
}

function participantView(participant: DailyParticipant): ParticipantView {
  return {
    key: participant.user_id || participant.session_id,
    sessionId: participant.session_id,
    video: trackView(participant.tracks?.video, participant.local),
    audio: trackView(participant.tracks?.audio, participant.local),
    network: participant.networkQualityState ?? "unknown",
  };
}

// The two people in a COMPASS session: this participant and the other one. A room holds at most
// two participants and unique user IDs (ADR-024); if Daily ever reports more, the first is shown.
export function projectParticipants(participants: DailyParticipantsObject): { local: ParticipantView | null; remote: ParticipantView | null } {
  const local = participants.local ? participantView(participants.local) : null;
  const other = Object.entries(participants).find(([key, participant]) => key !== "local" && !participant.local)?.[1];
  return { local, remote: other ? participantView(other) : null };
}

function sameTrack(a: TrackView, b: TrackView) {
  return a.track === b.track && a.playable === b.playable && a.off === b.off && a.blocked === b.blocked;
}

export function sameParticipant(a: ParticipantView | null, b: ParticipantView | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.key === b.key && a.sessionId === b.sessionId && a.network === b.network && sameTrack(a.video, b.video) && sameTrack(a.audio, b.audio);
}

const fallbackLabels = { videoinput: "Camera", audioinput: "Microphone", audiooutput: "Speaker" } as const;

function options(devices: readonly MediaDeviceInfo[], kind: keyof typeof fallbackLabels): DeviceOption[] {
  // Browsers hide device names until camera or microphone permission is granted; a numbered name
  // stands in, and the raw device ID is never shown.
  return devices
    .filter((device) => device.kind === kind && device.deviceId)
    .map((device, index) => ({ id: device.deviceId, label: device.label.trim() || `${fallbackLabels[kind]} ${index + 1}` }));
}

function selectedId(info: DailyDeviceInfos[keyof DailyDeviceInfos] | undefined, available: DeviceOption[]): string | null {
  const id = info && "deviceId" in info ? info.deviceId : null;
  return id && available.some((option) => option.id === id) ? id : null;
}

export function projectDevices(
  devices: readonly DailyMediaDeviceInfo[],
  selected: DailyDeviceInfos | null,
  speakerSelectable: boolean,
  currentSpeaker: string | null,
): CallDevices {
  const cameras = options(devices, "videoinput");
  const microphones = options(devices, "audioinput");
  const speakers = speakerSelectable ? options(devices, "audiooutput") : [];
  const speaker = selected ? selectedId(selected.speaker, speakers) : null;
  return {
    cameras,
    microphones,
    speakers,
    camera: selected ? selectedId(selected.camera, cameras) : null,
    microphone: selected ? selectedId(selected.mic, microphones) : null,
    speaker: speaker ?? (currentSpeaker && speakers.some((option) => option.id === currentSpeaker) ? currentSpeaker : null),
    speakerSelectable: speakerSelectable && speakers.length > 0,
  };
}

export function selectedDevices(current: CallDevices, selected: DailyDeviceInfos): CallDevices {
  return {
    ...current,
    camera: selectedId(selected.camera, current.cameras),
    microphone: selectedId(selected.mic, current.microphones),
    speaker: selectedId(selected.speaker, current.speakers) ?? current.speaker,
  };
}

function mediaNames(camera: boolean, microphone: boolean): string {
  if (camera && microphone) return "camera and microphone";
  return camera ? "camera" : "microphone";
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Product copy for Daily's camera-error categories. The provider's own message stays out of the UI.
export function cameraProblem(event: Pick<DailyEventObjectCameraError, "error" | "errorMsg">): MediaProblem {
  const error = event.error;
  const affects = (media: ReadonlyArray<"video" | "audio"> | undefined) => ({
    camera: media ? media.includes("video") : !event.errorMsg?.videoOk,
    microphone: media ? media.includes("audio") : !event.errorMsg?.audioOk,
  });
  switch (error?.type) {
    case "permissions": {
      const { camera, microphone } = affects(error.blockedMedia);
      return { camera, microphone, source: "camera-error", message: `${capitalized(mediaNames(camera, microphone))} access is blocked in your browser. Allow access in the browser's site settings, then rejoin.` };
    }
    case "not-found": {
      const { camera, microphone } = affects(error.missingMedia);
      return { camera, microphone, source: "camera-error", message: `No ${mediaNames(camera, microphone)} was found.` };
    }
    case "cam-in-use":
      return { camera: true, microphone: false, source: "camera-error", message: "Your camera is being used by another application." };
    case "mic-in-use":
      return { camera: false, microphone: true, source: "camera-error", message: "Your microphone is being used by another application." };
    case "cam-mic-in-use":
      return { camera: true, microphone: true, source: "camera-error", message: "Your camera and microphone are being used by another application." };
    case "constraints": {
      const { camera, microphone } = affects(error.failedMedia);
      return { camera, microphone, source: "camera-error", message: `Your ${mediaNames(camera, microphone)} couldn't be started with its current settings. Choose another device.` };
    }
    case "undefined-mediadevices":
      return { camera: true, microphone: true, source: "camera-error", message: "This browser can't use a camera or microphone on this page." };
    default: {
      const { camera, microphone } = affects(undefined);
      const both = camera || microphone ? { camera, microphone } : { camera: true, microphone: true };
      return { ...both, source: "camera-error", message: `Your ${mediaNames(both.camera, both.microphone)} couldn't be started.` };
    }
  }
}

// Product copy for Daily's fatal call errors. Rejoining always asks the COMPASS backend for a new
// credential, which applies the Appointment's join window.
export function fatalCallFailure(event: Pick<DailyEventObjectFatalError, "error">): CallFailure {
  switch (event.error?.type) {
    case "ejected":
      return { kind: "replaced", message: "You joined this session from another window or device, so this window left the call." };
    case "nbf-room":
    case "nbf-token":
      return { kind: "expired", message: "This session isn't open yet." };
    case "exp-room":
    case "exp-token":
      return { kind: "expired", message: "This session's join link expired. Join again to get a new one." };
    case "meeting-full":
      return { kind: "full", message: "This session already has two participants." };
    case "end-of-life":
      return { kind: "unsupported", message: "This browser version can't join video sessions. Update your browser, then join again." };
    case "connection-error":
      return { kind: "connection", message: "The connection to the session was lost." };
    case "no-room":
    case "not-allowed":
      return { kind: "unavailable", message: "This session can't be joined right now." };
    default:
      return { kind: "unknown", message: "The video session stopped unexpectedly." };
  }
}

export const joinConnectionFailure: CallFailure = {
  kind: "connection",
  message: "Couldn't connect to the video session. Check your connection, then try again.",
};

export const expiredCredentialFailure: CallFailure = {
  kind: "expired",
  message: "The join link expired before the call connected. Try again.",
};
