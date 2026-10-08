// The native E-Counseling call (ADR-093): Call Object lifecycle, participant/track projection,
// local controls, devices, network and the governance boundary. A fake Call Object stands in for
// Daily; no test reaches Daily.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { DailyCallSession, subscribedCallEvents } from "../src/features/ecounseling/call/daily-call-session.ts";
import { cameraProblem, fatalCallFailure, projectDevices } from "../src/features/ecounseling/call/call-model.ts";
import { attachTrack } from "../src/features/ecounseling/call/participant-media.tsx";
import { installFakeDaily } from "./support/fake-daily.mjs";

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function setup({ speaker = true, now = Date.now, ...fakeOptions } = {}) {
  const daily = installFakeDaily({}, fakeOptions);
  const session = new DailyCallSession({ loadFactory: async () => daily, supportsSpeakerSelection: () => speaker, now: () => now() });
  let issued = 0;
  const credential = (overrides = {}) => ({
    roomUrl: "https://example.daily.co/synthetic-room",
    token: `synthetic-token-${++issued}`,
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    ...overrides,
  });
  const join = (overrides) => session.join({ fetchCredential: async () => credential(overrides), describeCredentialError: () => "This session can’t be joined right now." });
  return { daily, session, join, issued: () => issued };
}

test("joining creates one call object and one join, and the credential is used only by that join", async () => {
  const { daily, session, join } = setup();
  await Promise.all([join(), join()]);
  assert.equal(session.getSnapshot().phase, "joined");
  assert.equal(daily.count("createCallObject"), 1);
  assert.equal(daily.count("join"), 1);
  assert.deepEqual(daily.log.find(([method]) => method === "join")[1], { url: "https://example.daily.co/synthetic-room", token: "synthetic-token-1" });
  assert.doesNotMatch(JSON.stringify(session.getSnapshot()), /synthetic-token|synthetic-room/);
  // A second Join while joined does nothing.
  await join();
  assert.equal(daily.count("join"), 1);
});

test("Strict Mode's simulated unmount before Join leaves the session reusable, with no call object", async () => {
  const { daily, session, join } = setup();
  session.dispose();
  assert.equal(daily.count("createCallObject"), 0);
  await join();
  assert.equal(daily.count("createCallObject"), 1);
  assert.equal(daily.count("join"), 1);
  assert.equal(session.getSnapshot().phase, "joined");
});

test("every Daily listener is registered once and removed; leaving leaves, then destroys", async () => {
  const { daily, session, join } = setup();
  await join();
  assert.equal(daily.liveListenerCount(), subscribedCallEvents.length);
  assert.equal(daily.count("on"), subscribedCallEvents.length);
  const call = daily.instances[0];
  await session.leave();
  assert.equal(call.listenerCount(), 0);
  assert.equal(daily.count("off"), subscribedCallEvents.length);
  const order = daily.log.map(([method]) => method).filter((method) => method === "leave" || method === "destroy");
  assert.deepEqual(order, ["leave", "destroy"]);
  assert.equal(call.isDestroyed(), true);
  assert.equal(session.getSnapshot().phase, "left");
});

test("unmounting while the credential is requested drops it unused and creates nothing", async () => {
  const { daily, session } = setup();
  let deliver;
  const pending = session.join({ fetchCredential: () => new Promise((resolve) => { deliver = resolve; }), describeCredentialError: () => "x" });
  session.dispose();
  deliver({ roomUrl: "https://example.daily.co/r", token: "late-token", expiresAt: new Date(Date.now() + 60_000).toISOString() });
  await pending;
  assert.equal(daily.count("createCallObject"), 0);
  assert.equal(session.getSnapshot().phase, "idle");
});

test("unmounting during join destroys the call, and the late join result cannot change state", async () => {
  const { daily, session, join } = setup();
  daily.holdJoin();
  const pending = join();
  while (!daily.count("join")) await tick();
  session.dispose();
  daily.releaseJoin();
  await pending;
  await tick();
  assert.equal(session.getSnapshot().phase, "idle");
  assert.equal(daily.instances[0].isDestroyed(), true);
  assert.equal(daily.count("destroy"), 1);
  // The next join waits for that destruction, so two call objects are never live together.
  await join();
  assert.equal(session.getSnapshot().phase, "joined");
  assert.equal(daily.instances.filter((call) => !call.isDestroyed()).length, 1);
});

test("rejoining asks the backend for a fresh credential", async () => {
  const { daily, session, join, issued } = setup();
  await join();
  await session.leave();
  await join();
  assert.equal(issued(), 2);
  const tokens = daily.log.filter(([method]) => method === "join").map(([, value]) => value.token);
  assert.deepEqual(tokens, ["synthetic-token-1", "synthetic-token-2"]);
  assert.equal(daily.instances[0].isDestroyed(), true);
  assert.equal(daily.count("createCallObject"), 2);
});

test("an expired credential is never used, and refused or failed joins say what happened in product words", async () => {
  const expired = setup();
  await expired.join({ expiresAt: new Date(Date.now() - 1000).toISOString() });
  assert.equal(expired.session.getSnapshot().failure.kind, "expired");
  assert.equal(expired.daily.count("createCallObject"), 0);

  const refused = setup();
  await refused.session.join({ fetchCredential: async () => { throw new Error("raw backend detail"); }, describeCredentialError: () => "This session can’t be joined right now." });
  assert.deepEqual(refused.session.getSnapshot().failure, { kind: "credential", message: "This session can’t be joined right now." });

  const failing = setup({ joinFailure: true });
  await failing.join();
  assert.equal(failing.session.getSnapshot().phase, "failed");
  assert.equal(failing.session.getSnapshot().failure.kind, "connection");
  assert.doesNotMatch(failing.session.getSnapshot().failure.message, /Synthetic join failure/);
  await tick();
  assert.equal(failing.daily.instances[0].isDestroyed(), true);
});

test("remote video and audio project separately and follow track replacement, stop and leave", async () => {
  const { daily, session, join } = setup();
  await join();
  assert.equal(session.getSnapshot().remote, null);
  const remote = daily.remoteJoin({ userId: "student-uuid", name: "Maria", video: false });
  let snapshot = session.getSnapshot();
  assert.equal(snapshot.remote.key, "student-uuid");
  assert.equal(snapshot.remote.video.track, null);
  assert.equal(snapshot.remote.video.off, true);
  assert.equal(snapshot.remote.audio.track, remote.audioTrack, "Audio stays available with the camera off");

  daily.remoteVideo(true);
  assert.equal(session.getSnapshot().remote.video.track, remote.videoTrack);
  assert.equal(session.getSnapshot().remote.video.playable, true);
  const replacement = daily.replaceRemoteVideo();
  assert.equal(session.getSnapshot().remote.video.track, replacement);
  daily.stopRemoteVideo();
  assert.equal(session.getSnapshot().remote.video.track, null);

  const firstSession = session.getSnapshot().remote.sessionId;
  daily.remoteLeave();
  assert.equal(session.getSnapshot().remote, null);
  daily.remoteJoin({ userId: "student-uuid", name: "Maria" });
  snapshot = session.getSnapshot();
  assert.equal(snapshot.remote.key, "student-uuid", "A rejoin maps to the same person by user ID");
  assert.notEqual(snapshot.remote.sessionId, firstSession);
});

test("mic and camera use Daily's local controls immediately, and the self view follows the camera", async () => {
  let clock = 0;
  const { daily, session, join } = setup({ now: () => clock });
  await join();
  assert.equal(session.getSnapshot().local.video.playable, true);
  session.setMicrophone(false);
  session.setCamera(false);
  assert.deepEqual(daily.log.filter(([method]) => method.startsWith("setLocal")), [["setLocalAudio", false], ["setLocalVideo", false]]);
  assert.equal(session.getSnapshot().microphoneOn, false);
  assert.equal(session.getSnapshot().cameraOn, false);
  await tick();
  assert.equal(session.getSnapshot().local.video.track, null);
  session.setCamera(true);
  await tick();
  assert.equal(session.getSnapshot().local.video.playable, true);
});

test("a toggle Daily hasn't reported back yet holds against a stale update, then gives way", async () => {
  let clock = 0;
  const { daily, session, join } = setup({ now: () => clock });
  await join();
  const call = daily.instances[0];
  session.setMicrophone(false);
  // A participant update that still carries the old state does not flip the control back…
  call.audioOn = true;
  call.emit("participant-updated", { participant: call.localParticipant() });
  assert.equal(session.getSnapshot().microphoneOn, false);
  // …but one Daily never confirms gives way to what Daily reports.
  clock = 5000;
  call.emit("participant-updated", { participant: call.localParticipant() });
  assert.equal(session.getSnapshot().microphoneOn, true);
});

test("devices use Daily's device APIs, never show raw IDs, follow hot-plug and degrade speaker choice", async () => {
  const { daily, session, join } = setup({
    devices: [
      { deviceId: "cam-1", kind: "videoinput", label: "", groupId: "a" },
      { deviceId: "mic-1", kind: "audioinput", label: "Headset microphone", groupId: "a" },
      { deviceId: "spk-1", kind: "audiooutput", label: "", groupId: "a" },
    ],
  });
  await join();
  await tick();
  let devices = session.getSnapshot().devices;
  assert.deepEqual(devices.cameras, [{ id: "cam-1", label: "Camera 1" }]);
  assert.deepEqual(devices.speakers, [{ id: "spk-1", label: "Speaker 1" }]);
  assert.equal(devices.speakerSelectable, true);
  assert.equal(devices.camera, "cam-1");

  daily.addDevice({ deviceId: "cam-2", kind: "videoinput", label: "USB camera" });
  await tick();
  assert.deepEqual(session.getSnapshot().devices.cameras.map((option) => option.label), ["Camera 1", "USB camera"]);
  daily.removeDevice("cam-1");
  await tick();
  devices = session.getSnapshot().devices;
  assert.equal(devices.camera, "cam-2", "The selection is what Daily reports, not a stale choice");

  await session.selectMicrophone("mic-1");
  await session.selectCamera("cam-2");
  await session.selectSpeaker("spk-1");
  assert.deepEqual(daily.log.filter(([method]) => method === "setInputDevicesAsync").map(([, value]) => value), [{ audioDeviceId: "mic-1" }, { videoDeviceId: "cam-2" }]);
  assert.deepEqual(daily.log.find(([method]) => method === "setOutputDeviceAsync")[1], { outputDeviceId: "spk-1" });

  daily.removeDevice("mic-1");
  await tick();
  assert.equal(session.getSnapshot().mediaProblem.message, "No microphone is connected.");
  daily.addDevice({ deviceId: "mic-2", kind: "audioinput", label: "USB microphone" });
  await tick();
  assert.equal(session.getSnapshot().mediaProblem, null);

  const noSpeaker = setup({ speaker: false });
  await noSpeaker.join();
  await tick();
  assert.equal(noSpeaker.session.getSnapshot().devices.speakerSelectable, false);
  assert.deepEqual(noSpeaker.session.getSnapshot().devices.speakers, []);
  assert.deepEqual(projectDevices([], null, false, null).speakers, []);
});

test("network quality and interruptions are projected, and the call reconnects rather than ending", async () => {
  const { daily, session, join } = setup();
  await join();
  daily.network("warning");
  assert.equal(session.getSnapshot().network, "warning");
  daily.connection("interrupted");
  assert.equal(session.getSnapshot().phase, "reconnecting");
  assert.equal(daily.count("destroy"), 0);
  daily.connection("connected");
  assert.equal(session.getSnapshot().phase, "joined");
});

test("camera and microphone errors use product copy, never provider messages or error class names", () => {
  const raw = /NotReadableError|DailyCam|raw provider/;
  const cases = [
    [{ type: "permissions", blockedBy: "browser", blockedMedia: ["video"], msg: "raw provider" }, /^Camera access is blocked in your browser/],
    [{ type: "not-found", missingMedia: ["audio"], msg: "raw provider" }, /^No microphone was found\.$/],
    [{ type: "cam-in-use", msg: "NotReadableError" }, /^Your camera is being used by another application\.$/],
    [{ type: "constraints", reason: "invalid", failedMedia: ["video"], msg: "DailyCamConstraintsError" }, /^Your camera couldn't be started with its current settings/],
    [{ type: "unknown", msg: "raw provider" }, /couldn't be started\.$/],
  ];
  for (const [error, expected] of cases) {
    const problem = cameraProblem({ error, errorMsg: { errorMsg: "NotReadableError: raw provider", audioOk: true, videoOk: false } });
    assert.match(problem.message, expected);
    assert.doesNotMatch(problem.message, raw);
  }
  assert.equal(cameraProblem({ error: { type: "cam-in-use", msg: "x" } }).microphone, false, "A camera problem leaves audio usable");
  for (const type of ["ejected", "exp-token", "nbf-room", "meeting-full", "end-of-life", "connection-error", "not-allowed", "something-new"]) {
    assert.doesNotMatch(fatalCallFailure({ error: { type, msg: "raw" } }).message, /raw|exp-token|ejected/);
  }
});

test("a fatal call error ends the call in product words and destroys the call object", async () => {
  const { daily, session, join } = setup();
  await join();
  daily.fatal("exp-token");
  assert.equal(session.getSnapshot().phase, "failed");
  assert.match(session.getSnapshot().failure.message, /expired/);
  await tick();
  assert.equal(daily.instances[0].isDestroyed(), true);
});

test("provider recording and transcription events only ask COMPASS to refresh; transcript text is never received", async () => {
  const { daily, session, join } = setup();
  let refreshes = 0;
  session.setProviderMediaEventHandler(() => { refreshes += 1; });
  await join();
  const before = session.getSnapshot();
  for (const event of ["recording-started", "recording-stopped", "recording-error", "transcription-started", "transcription-stopped", "transcription-error"]) daily.providerEvent(event);
  assert.equal(refreshes, 6);
  assert.equal(session.getSnapshot(), before, "Provider events never change the call's own state");
  assert.equal(subscribedCallEvents.includes("transcription-message"), false);
  daily.transcriptMessage();
  assert.equal(daily.log.some(([method, event]) => method === "on" && event === "transcription-message"), false);
  assert.doesNotMatch(JSON.stringify(session.getSnapshot()), /SYNTHETIC TRANSCRIPT/);
});

test("the browser call never starts or stops recording or transcription itself", async () => {
  const { daily, session, join } = setup();
  await join();
  daily.remoteJoin();
  session.setMicrophone(false);
  await session.leave();
  for (const method of ["startRecording", "stopRecording", "startTranscription", "stopTranscription"]) assert.equal(daily.count(method), 0, method);
  const callDirectory = new URL("../src/features/ecounseling/call/", import.meta.url);
  for (const file of readdirSync(callDirectory)) {
    const source = readFileSync(new URL(file, callDirectory), "utf8");
    assert.doesNotMatch(source, /\.(startRecording|stopRecording|startTranscription|stopTranscription|updateTranscription)\(/, file);
    assert.doesNotMatch(source, /createFrame|daily-react/, file);
  }
});

test("attaching a replacement track never lets the old cleanup clear it, and no stale stream remains", () => {
  const streams = [];
  const createStream = (track) => {
    const stream = { tracks: [track] };
    streams.push(stream);
    return stream;
  };
  const element = { srcObject: null };
  const detachFirst = attachTrack(element, { id: "first" }, createStream);
  assert.deepEqual(element.srcObject.tracks.map((track) => track.id), ["first"]);
  const detachSecond = attachTrack(element, { id: "second" }, createStream);
  detachFirst();
  assert.deepEqual(element.srcObject.tracks.map((track) => track.id), ["second"], "The stale cleanup leaves the new stream");
  detachSecond();
  assert.equal(element.srcObject, null);
  assert.equal(streams.length, 2);
});
