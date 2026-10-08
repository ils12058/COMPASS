// A deterministic stand-in for Daily's Call Object factory, for unit tests (node) and browser
// tests (installed into the page before COMPASS loads). It never contacts Daily.
//
// `installFakeDaily` must stay self-contained: browser tests serialize it with toString() and run
// it in the page, so it may not reference anything outside its own body.
export function installFakeDaily(target, options = {}) {
  const realTracks = Boolean(options.realTracks);
  const log = [];
  const instances = [];
  let trackCounter = 0;
  let sessionCounter = 0;
  let joinGate = null;

  function makeTrack(kind) {
    trackCounter += 1;
    if (realTracks && kind === "video") {
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 180;
      const context = canvas.getContext("2d");
      const hue = (trackCounter * 67) % 360;
      const paint = () => {
        context.fillStyle = `hsl(${hue} 45% 45%)`;
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = "white";
        context.font = "20px sans-serif";
        context.fillText(`Synthetic video ${trackCounter}`, 20, 95);
      };
      paint();
      const track = canvas.captureStream(5).getVideoTracks()[0];
      const timer = setInterval(paint, 200);
      track.addEventListener("ended", () => clearInterval(timer));
      return track;
    }
    if (realTracks && kind === "audio") {
      const audio = new AudioContext();
      const destination = audio.createMediaStreamDestination();
      const gain = audio.createGain();
      gain.gain.value = 0;
      const oscillator = audio.createOscillator();
      oscillator.connect(gain).connect(destination);
      oscillator.start();
      return destination.stream.getAudioTracks()[0];
    }
    return { id: `fake-${kind}-${trackCounter}`, kind, readyState: "live", stop() { this.readyState = "ended"; } };
  }

  function trackState(on, track) {
    if (!on) return { subscribed: true, state: "off", off: { byUser: true } };
    return { subscribed: true, state: "playable", track, persistentTrack: track };
  }
  const offTrack = { subscribed: true, state: "off", off: { byUser: true } };

  const devices = (options.devices ?? [
    { deviceId: "cam-1", kind: "videoinput", label: "Built-in camera", groupId: "a" },
    { deviceId: "mic-1", kind: "audioinput", label: "Built-in microphone", groupId: "a" },
    { deviceId: "spk-1", kind: "audiooutput", label: "Built-in speakers", groupId: "a" },
  ]).map((device) => ({ ...device }));

  class FakeCall {
    constructor(properties) {
      this.listeners = new Map();
      this.state = "new";
      this.destroyed = false;
      this.audioOn = true;
      this.videoOn = true;
      this.localTracks = { audio: makeTrack("audio"), video: makeTrack("video") };
      this.localSession = `local-session-${++sessionCounter}`;
      this.remote = null;
      this.selected = { camera: "cam-1", mic: "mic-1", speaker: "spk-1" };
      log.push(["createCallObject", properties ?? null]);
    }
    on(event, handler) {
      if (!this.listeners.has(event)) this.listeners.set(event, new Set());
      this.listeners.get(event).add(handler);
      log.push(["on", event]);
      return this;
    }
    off(event, handler) {
      this.listeners.get(event)?.delete(handler);
      log.push(["off", event]);
      return this;
    }
    listenerCount() {
      let count = 0;
      for (const handlers of this.listeners.values()) count += handlers.size;
      return count;
    }
    emit(event, payload = {}) {
      for (const handler of [...(this.listeners.get(event) ?? [])]) handler({ action: event, callClientId: "fake-call", ...payload });
    }
    localParticipant() {
      return {
        local: true,
        session_id: this.localSession,
        user_id: options.localUserId ?? "local-user",
        user_name: "Local",
        networkQualityState: "good",
        tracks: { audio: trackState(this.audioOn, this.localTracks.audio), video: trackState(this.videoOn, this.localTracks.video), screenAudio: offTrack, screenVideo: offTrack },
      };
    }
    remoteParticipant() {
      const remote = this.remote;
      if (!remote) return null;
      return {
        local: false,
        session_id: remote.sessionId,
        user_id: remote.userId,
        user_name: remote.name,
        networkQualityState: remote.network,
        tracks: { audio: trackState(remote.audioOn, remote.audioTrack), video: trackState(remote.videoOn, remote.videoTrack), screenAudio: offTrack, screenVideo: offTrack },
      };
    }
    participants() {
      const result = { local: this.localParticipant() };
      const remote = this.remoteParticipant();
      if (remote) result[remote.session_id] = remote;
      return result;
    }
    async join(properties) {
      log.push(["join", { url: properties?.url, token: properties?.token }]);
      this.state = "joining-meeting";
      if (joinGate) await joinGate.promise;
      if (options.joinFailure) {
        this.state = "error";
        throw new Error("Synthetic join failure");
      }
      if (this.destroyed) throw new Error("Call object was destroyed");
      this.state = "joined-meeting";
      this.emit("joined-meeting", { participants: this.participants() });
      return this.participants();
    }
    async leave() {
      log.push(["leave"]);
      if (this.state === "joined-meeting" || this.state === "joining-meeting") {
        this.state = "left-meeting";
        this.emit("left-meeting");
      }
    }
    async destroy() {
      log.push(["destroy"]);
      this.destroyed = true;
      this.state = "left-meeting";
    }
    isDestroyed() { return this.destroyed; }
    meetingState() { return this.state; }
    setLocalAudio(on) {
      log.push(["setLocalAudio", on]);
      this.audioOn = on;
      queueMicrotask(() => this.emit("participant-updated", { participant: this.localParticipant() }));
      return this;
    }
    setLocalVideo(on) {
      log.push(["setLocalVideo", on]);
      this.videoOn = on;
      queueMicrotask(() => this.emit("participant-updated", { participant: this.localParticipant() }));
      return this;
    }
    deviceInfo(kind, id) {
      return devices.find((device) => device.kind === kind && device.deviceId === id) ?? {};
    }
    async enumerateDevices() {
      log.push(["enumerateDevices"]);
      return { devices: devices.map((device) => ({ ...device })) };
    }
    async getInputDevices() {
      return { camera: this.deviceInfo("videoinput", this.selected.camera), mic: this.deviceInfo("audioinput", this.selected.mic), speaker: this.deviceInfo("audiooutput", this.selected.speaker) };
    }
    async setInputDevicesAsync(request) {
      log.push(["setInputDevicesAsync", request]);
      if (request.videoDeviceId) this.selected.camera = request.videoDeviceId;
      if (request.audioDeviceId) this.selected.mic = request.audioDeviceId;
      const selected = await this.getInputDevices();
      this.emit("selected-devices-updated", { devices: selected });
      return selected;
    }
    async setOutputDeviceAsync(request) {
      log.push(["setOutputDeviceAsync", request]);
      this.selected.speaker = request.outputDeviceId;
      return this.getInputDevices();
    }
    // The real Call Object has these; COMPASS must never call them (recording and transcription
    // start and stop only through the COMPASS backend).
    startRecording() { log.push(["startRecording"]); }
    stopRecording() { log.push(["stopRecording"]); }
    startTranscription() { log.push(["startTranscription"]); }
    stopTranscription() { log.push(["stopTranscription"]); }
  }

  const live = () => instances.find((call) => !call.destroyed);
  const current = () => {
    const call = live();
    if (!call) throw new Error("No live fake call object");
    return call;
  };
  const updateRemote = (event, changes) => {
    const call = current();
    Object.assign(call.remote, changes);
    call.emit(event, { participant: call.remoteParticipant() });
  };

  const controller = {
    log,
    instances,
    count: (name) => log.filter(([method]) => method === name).length,
    createCallObject(properties) {
      // Daily refuses a second live call object, and so does the fake.
      if (live()) throw new Error("Duplicate DailyIframe instances are not allowed");
      const call = new FakeCall(properties);
      instances.push(call);
      return call;
    },
    getCallInstance() { return live(); },
    holdJoin() {
      let release;
      const promise = new Promise((resolve) => { release = resolve; });
      joinGate = { promise, release };
    },
    releaseJoin() {
      joinGate?.release();
      joinGate = null;
    },
    liveListenerCount() { return live()?.listenerCount() ?? 0; },
    remoteJoin({ userId = "remote-user", name = "Remote", video = true, audio = true } = {}) {
      const call = current();
      call.remote = { userId, name, sessionId: `remote-session-${++sessionCounter}`, videoOn: video, audioOn: audio, videoTrack: makeTrack("video"), audioTrack: makeTrack("audio"), network: "good" };
      call.emit("participant-joined", { participant: call.remoteParticipant() });
      call.emit("track-started", { participant: call.remoteParticipant(), track: call.remote.videoTrack, type: "video" });
      return call.remote;
    },
    remoteVideo(on) { updateRemote("participant-updated", { videoOn: on }); },
    remoteAudio(on) { updateRemote("participant-updated", { audioOn: on }); },
    replaceRemoteVideo() {
      const track = makeTrack("video");
      updateRemote("track-started", { videoTrack: track });
      return track;
    },
    stopRemoteVideo() { updateRemote("track-stopped", { videoOn: false }); },
    remoteNetwork(state) { updateRemote("participant-updated", { network: state }); },
    remoteLeave() {
      const call = current();
      const participant = call.remoteParticipant();
      call.remote = null;
      call.emit("participant-left", { participant });
    },
    network(state) { current().emit("network-quality-change", { networkState: state, networkStateReasons: [], stats: {}, threshold: "good", quality: 100 }); },
    connection(event) { current().emit("network-connection", { type: "signaling", event }); },
    cameraError(error, errorMsg = { errorMsg: "NotReadableError: raw provider detail", audioOk: true, videoOk: false }) { current().emit("camera-error", { error, errorMsg }); },
    fatal(type) { current().emit("error", { errorMsg: `raw ${type}`, error: { type, msg: `raw ${type}` } }); },
    providerEvent(name) { current().emit(name, { instanceId: "synthetic", startedBy: "synthetic", updatedBy: "synthetic", language: "en", model: "synthetic" }); },
    transcriptMessage() { current().emit("transcription-message", { text: "SYNTHETIC TRANSCRIPT TEXT", participantId: "remote", timestamp: new Date(), rawResponse: {} }); },
    addDevice(device) {
      devices.push({ groupId: "hotplug", ...device });
      current().emit("available-devices-updated", { availableDevices: devices });
    },
    removeDevice(deviceId) {
      const index = devices.findIndex((device) => device.deviceId === deviceId);
      if (index >= 0) devices.splice(index, 1);
      const call = current();
      for (const key of ["camera", "mic", "speaker"]) {
        if (call.selected[key] === deviceId) {
          const kind = key === "camera" ? "videoinput" : key === "mic" ? "audioinput" : "audiooutput";
          call.selected[key] = devices.find((device) => device.kind === kind)?.deviceId ?? null;
        }
      }
      call.emit("available-devices-updated", { availableDevices: devices });
    },
  };
  target.__COMPASS_FAKE_DAILY__ = controller;
  return controller;
}

// Browser tests: an init script that installs the fake before the app loads.
export function fakeDailyInitScript(options = {}) {
  return `(${installFakeDaily.toString()})(window, ${JSON.stringify({ realTracks: true, ...options })});`;
}
