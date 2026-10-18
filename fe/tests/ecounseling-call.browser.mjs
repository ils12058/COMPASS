// The native E-Counseling call and compact session workspace (ADR-093) in a real browser. The page
// uses the fake Call Object (tests/support/fake-daily.mjs) with synthetic camera and microphone
// tracks, and every API call is answered with synthetic fixtures: no Daily room, credential,
// recording, transcript or institutional record is touched.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { readFile } from "node:fs/promises";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointmentId, consents, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("ecounseling-call");
const ePath = `/portal/e-counseling/${appointmentId}`;
const STUDENT = "Maria Santos";
const COUNSELOR = "Maria Reyes";
const AVATAR_IMAGE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%237c3aed'/%3E%3C/svg%3E";

// A session whose capture and consent state a test can change while the page is open.
function liveSession({ student = false, version = 2, recording = "NOT_STARTED", transcription = "NOT_STARTED", decision = "APPROVED", storage = null, artifact = null, context = false, joinState = "OPEN", roomProvisioned = true, joinAllowed = true, avatarPhotos = false, participantPhotoUrl = AVATAR_IMAGE } = {}) {
  const state = { recording, transcription, decision, storage, artifact, failWorkspace: false, joins: 0, workspaceReads: 0, joinState, roomProvisioned, joinAllowed };
  const prefix = `/api/v1/e-counseling/${student ? "me/" : ""}appointments/${appointmentId}`;
  const data = () => {
    const value = workspace();
    if (avatarPhotos) {
      value.student = { ...value.student, profile_photo_url: participantPhotoUrl, profile_photo_updated_at: "2026-10-17T00:00:00Z" };
      value.counselor = { ...value.counselor, profile_photo_url: participantPhotoUrl, profile_photo_updated_at: "2026-10-17T00:00:00Z" };
      value.appointment = { ...value.appointment, student: value.student, provider: value.counselor };
    }
    value.counseling_context_available = context;
    value.provider_readiness.join_state = state.joinState;
    value.provider_readiness.room_provisioned = state.roomProvisioned;
    value.provider_readiness.join_allowed = state.joinAllowed;
    value.media.media_policy_version = version;
    value.media.recording.capture_status = state.recording;
    value.media.transcription.capture_status = state.transcription;
    value.media.transcription.storage_consent_status = state.storage ?? "NOT_REQUESTED";
    for (const item of [value.media.recording, value.media.transcription]) {
      item.artifact_status = state.artifact;
      item.artifact_available = state.artifact === "STORED";
    }
    return value;
  };
  const rows = () => {
    const base = consents(state.decision)[0];
    if (version === 1) return consents(state.decision);
    const result = [{ ...base, id: "v2-media", scope: "SESSION_MEDIA_CAPTURE" }];
    if (state.storage) result.push({ ...consents(state.storage)[0], id: "v2-storage", scope: "TRANSCRIPT_STORAGE" });
    return result;
  };
  const overrides = {
    [prefix]: ({ reply }) => {
      state.workspaceReads += 1;
      return state.failWorkspace ? reply({ error: { code: "synthetic_unavailable", message: "Synthetic refresh failure" } }, 503) : reply(data());
    },
    [`${prefix}/consents`]: ({ reply }) => reply({ items: rows() }),
    [`POST /api/v1/e-counseling/appointments/${appointmentId}/join`]: ({ reply }) => {
      state.joins += 1;
      return reply({
        appointment_id: appointmentId,
        workspace_id: "synthetic-workspace",
        provider: "DAILY",
        room_url: "https://synthetic.daily.co/synthetic-room",
        meeting_token: `synthetic-meeting-token-${state.joins}`,
        token_expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
      });
    },
  };
  return { state, overrides };
}

const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const stage = (page) => page.getByRole("region", { name: "Video call" });
const tray = (page) => page.getByRole("group", { name: "Call controls" });
const attachedTrack = (locator) => locator.evaluate((element) => element.srcObject?.getTracks().map((track) => track.id) ?? []);
async function assertFullscreenVideoFit(page, source) {
  const metrics = await stage(page).locator("video").first().evaluate((video, expectedSource) => {
    const rect = video.getBoundingClientRect();
    const pane = video.parentElement.parentElement.getBoundingClientRect();
    const stageElement = video.closest("section[aria-label='Video call']");
    const stageRect = stageElement.getBoundingClientRect();
    const controls = stageElement.querySelector("[role='group'][aria-label='Call controls']").getBoundingClientRect();
    const ratio = expectedSource.width / expectedSource.height;
    const frameWidth = Math.min(rect.width, rect.height * ratio);
    const frameHeight = Math.min(rect.height, rect.width / ratio);
    return {
      source: [video.videoWidth, video.videoHeight],
      fit: getComputedStyle(video).objectFit,
      position: getComputedStyle(video).objectPosition,
      paneBottom: pane.bottom,
      controlsTop: controls.top,
      controlsBottom: controls.bottom,
      stageBottom: stageRect.bottom,
      frameWidth,
      frameHeight,
      frameCenterX: rect.left + rect.width / 2,
      frameCenterY: rect.top + rect.height / 2,
      boxCenterX: rect.left + rect.width / 2,
      boxCenterY: rect.top + rect.height / 2,
      viewport: [window.innerWidth, window.innerHeight],
    };
  }, source);
  assert.ok(
    (metrics.source[0] === 0 && metrics.source[1] === 0) ||
      (metrics.source[0] === source.width && metrics.source[1] === source.height),
    "When available, browser-reported synthetic track dimensions match the configured source",
  );
  assert.equal(metrics.fit, "contain", "The remote participant's entire frame stays visible");
  assert.match(metrics.position, /50%/);
  assert.ok(metrics.frameWidth > 0 && metrics.frameHeight > 0);
  assert.ok(metrics.paneBottom <= metrics.controlsTop + 1, "The video pane ends before the call controls");
  assert.ok(metrics.controlsBottom <= metrics.stageBottom + 1, "Call controls remain inside the fullscreen stage");
}
const fakeTrackIds = (page) => page.evaluate(() => {
  const call = window.__COMPASS_FAKE_DAILY__.instances.findLast((item) => !item.isDestroyed());
  return { localVideo: call.localTracks.video.id, localAudio: call.localTracks.audio.id, remoteVideo: call.remote?.videoTrack.id, remoteAudio: call.remote?.audioTrack.id };
});

async function joinCall(page, name = STUDENT) {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for ${name}…`, { exact: true }).first());
  await shown(tray(page));
}

await check("participant-avatars-camera-off-and-live-video", ePath, {
  fakeDaily: true,
  overrides: {
    ...liveSession({ avatarPhotos: true }).overrides,
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: "Example User", profile_photo_url: AVATAR_IMAGE, profile_photo_updated_at: "2026-10-17T00:00:00Z" }),
  },
}, async (page, { requests }) => {
  const callStage = stage(page);
  await shown(page.getByText("You · Example User", { exact: true }));
  const profileReadsBeforeCall = requests.filter((request) => request.pathname === "/api/v1/me/profile").length;
  assert.equal(await page.locator("[data-page-header] img").count(), 2, "The pre-join header shows both authorized people’s photos");
  const persisted = await page.evaluate(() => [localStorage, sessionStorage].flatMap((store) => Array.from({ length: store.length }, (_, index) => `${store.key(index)}=${store.getItem(store.key(index))}`)).join("\n"));
  assert.doesNotMatch(persisted, /data:image|profile_photo_url/);
  assert.doesNotMatch(page.url(), /data:image/);
  await joinCall(page);
  await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
  const remotePane = callStage.locator("div.relative.size-full").first();
  await shown(remotePane.locator("video"));
  assert.equal(await remotePane.locator("img").count(), 0, "A playable remote video is never covered by a profile photo");

  await fake(page, "remoteVideo", false);
  await shown(remotePane.getByText("Camera off", { exact: true }));
  await shown(remotePane.locator("img"));
  assert.ok(await remotePane.locator("img").evaluate((image) => image.naturalWidth > 0));
  await screenshot(page, "avatar-camera-off-and-live-video");

  await tray(page).getByRole("button", { name: "Camera", exact: true }).click();
  const selfView = callStage.locator("figure");
  await shown(selfView.getByText("You, camera off", { exact: true }));
  await shown(selfView.locator("img"));
  assert.equal(requests.filter((request) => request.pathname === "/api/v1/me/profile").length, profileReadsBeforeCall, "Camera state changes do not refetch the signed-in profile photo");
});

await check("participant-avatar-load-failure-falls-back-to-initials", ePath, {
  fakeDaily: true,
  beforeNavigate: async ({ context }) => {
    await context.route("**/__tests__/broken-avatar.png", (route) => route.fulfill({ status: 404, contentType: "image/png", body: "" }));
  },
  overrides: {
    ...liveSession({ avatarPhotos: true, participantPhotoUrl: "/__tests__/broken-avatar.png" }).overrides,
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: "Example User", profile_photo_url: AVATAR_IMAGE, profile_photo_updated_at: "2026-10-17T00:00:00Z" }),
  },
}, async (page) => {
  const pageHeader = page.locator("[data-page-header]");
  await shown(pageHeader.getByText("MS", { exact: true }));
  await joinCall(page);
  await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
  const remotePane = stage(page).locator("div.relative.size-full").first();
  await shown(remotePane.locator("video"));
  await fake(page, "remoteVideo", false);
  await shown(remotePane.getByText("Camera off", { exact: true }));
  await shown(remotePane.getByText("MS", { exact: true }));
  assert.equal(await remotePane.locator("img").count(), 0, "A failed image becomes initials, not a broken-image icon");
});

await check("participant-avatars-phone-layout", ePath, {
  device: "phone",
  fakeDaily: true,
  overrides: {
    ...liveSession({ avatarPhotos: true }).overrides,
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: "Example User", profile_photo_url: AVATAR_IMAGE, profile_photo_updated_at: "2026-10-17T00:00:00Z" }),
  },
}, async (page) => {
  await shown(page.getByText("You · Example User", { exact: true }));
  await shown(stage(page).getByText("Ready to join", { exact: true }));
  await noHorizontalOverflow(page);
  await screenshot(page, "avatar-prejoin-phone");
});

await check("counselor-native-call-desktop", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page, { requests }) => {
  await shown(stage(page).getByText("Ready to join", { exact: true }).first());
  await joinCall(page);
  assert.equal(await page.locator("iframe").count(), 0, "No provider frame is embedded");
  assert.equal(await fakeCount(page, "createCallObject"), 1, "Strict Mode creates one call object");
  assert.equal(await fakeCount(page, "join"), 1, "Strict Mode joins once");
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 1);

  const selfView = stage(page).locator("figure video");
  await shown(selfView);
  let ids = await fakeTrackIds(page);
  assert.deepEqual(await attachedTrack(selfView), [ids.localVideo]);
  assert.equal(await selfView.evaluate((element) => element.muted), true);

  await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
  await shown(stage(page).getByText("Connected", { exact: true }));
  ids = await fakeTrackIds(page);
  const remoteVideo = stage(page).locator("video").first();
  await page.waitForFunction((id) => [...document.querySelectorAll("section[aria-label='Video call'] video")].some((video) => video.srcObject?.getTracks()[0]?.id === id), ids.remoteVideo);
  const audioTracks = await page.locator("audio").evaluateAll((elements) => elements.flatMap((element) => element.srcObject?.getTracks().map((track) => track.id) ?? []));
  assert.deepEqual(audioTracks, [ids.remoteAudio], "Only the other participant is played");
  assert.equal(audioTracks.includes(ids.localAudio), false, "This participant never hears themself");

  const replacement = await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.replaceRemoteVideo().id);
  await page.waitForFunction((id) => [...document.querySelectorAll("section[aria-label='Video call'] video")].some((video) => video.srcObject?.getTracks()[0]?.id === id), replacement);
  assert.equal(await remoteVideo.isVisible(), true);

  await fake(page, "remoteVideo", false);
  await shown(stage(page).getByText("Camera off", { exact: true }).first());
  assert.deepEqual(await page.locator("audio").evaluateAll((elements) => elements.flatMap((element) => element.srcObject?.getTracks().map((track) => track.id) ?? [])), [ids.remoteAudio], "Audio continues with the camera off");

  await fake(page, "remoteLeave");
  await shown(stage(page).getByText(`Waiting for ${STUDENT}…`, { exact: true }).first());
  await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
  await shown(stage(page).getByText("Connected", { exact: true }));
  await screenshot(page, "counselor-call-desktop");
});

await check("call-controls-and-devices", ePath, { fakeDaily: true, initScripts: ["HTMLMediaElement.prototype.setSinkId = async function () {};"], overrides: liveSession().overrides }, async (page) => {
  await joinCall(page);
  const mic = tray(page).getByRole("button", { name: "Microphone", exact: true });
  const camera = tray(page).getByRole("button", { name: "Camera", exact: true });
  assert.equal(await mic.getAttribute("aria-pressed"), "true");
  await mic.click();
  assert.equal(await mic.getAttribute("aria-pressed"), "false");
  await camera.click();
  assert.equal(await camera.getAttribute("aria-pressed"), "false");
  await shown(stage(page).locator("figure").getByText("You, camera off", { exact: true }));
  assert.deepEqual(await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.log.filter(([method]) => method.startsWith("setLocal"))), [["setLocalAudio", false], ["setLocalVideo", false]]);
  await camera.click();
  await shown(stage(page).locator("figure video"));

  // Keyboard: the tiles are buttons in tab order with a visible focus ring.
  await mic.focus();
  await page.keyboard.press("Enter");
  assert.equal(await mic.getAttribute("aria-pressed"), "true");
  assert.notEqual(await mic.evaluate((element) => getComputedStyle(element).boxShadow), "none", "Focus is visible");

  const devices = tray(page).getByRole("button", { name: "Devices", exact: true });
  await devices.click();
  const dialog = page.getByRole("dialog", { name: "Devices", exact: true });
  await shown(dialog);
  assert.deepEqual(await dialog.getByLabel("Camera", { exact: true }).locator("option").allInnerTexts(), ["Built-in camera"]);
  await fake(page, "addDevice", { deviceId: "cam-2", kind: "videoinput", label: "USB camera" });
  await page.waitForFunction(() => [...document.querySelectorAll("option")].some((option) => option.textContent === "USB camera"));
  await dialog.getByLabel("Camera", { exact: true }).selectOption({ label: "USB camera" });
  await dialog.getByLabel("Speaker", { exact: true }).selectOption({ label: "Built-in speakers" });
  const deviceCalls = await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.log.filter(([method]) => method === "setInputDevicesAsync" || method === "setOutputDeviceAsync"));
  assert.deepEqual(deviceCalls, [["setInputDevicesAsync", { videoDeviceId: "cam-2" }], ["setOutputDeviceAsync", { outputDeviceId: "spk-1" }]]);
  assert.doesNotMatch(await dialog.innerText(), /cam-2|spk-1/, "Device IDs are never shown");
  await page.keyboard.press("Escape");
  await hidden(dialog);
  await page.waitForFunction((element) => element === document.activeElement, await devices.elementHandle());
});

await check("speaker-selection-fallback", ePath, {
  fakeDaily: { devices: [{ deviceId: "", kind: "videoinput", label: "", groupId: "x" }, { deviceId: "cam-a", kind: "videoinput", label: "", groupId: "a" }, { deviceId: "mic-a", kind: "audioinput", label: "", groupId: "a" }, { deviceId: "spk-a", kind: "audiooutput", label: "", groupId: "a" }] },
  initScripts: ["delete HTMLMediaElement.prototype.setSinkId;"],
  overrides: liveSession().overrides,
}, async (page) => {
  await joinCall(page);
  await tray(page).getByRole("button", { name: "Devices", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Devices", exact: true });
  await shown(dialog.getByText("Uses your system default", { exact: true }));
  assert.deepEqual(await dialog.getByLabel("Camera", { exact: true }).locator("option:not([disabled])").allInnerTexts(), ["Camera 1"], "Unnamed devices get numbered names");
  assert.deepEqual(await dialog.getByLabel("Microphone", { exact: true }).locator("option:not([disabled])").allInnerTexts(), ["Microphone 1"]);
});

await check("leave-and-rejoin-fresh-credential", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page, { requests }) => {
  await joinCall(page);
  await tray(page).getByRole("button", { name: "Leave session", exact: true }).click();
  await shown(stage(page).getByText(/You left the call\. Leaving doesn’t end the Appointment\./));
  assert.equal(await fakeCount(page, "leave") >= 1, true);
  assert.equal(await fakeCount(page, "destroy"), 1);
  await hidden(tray(page));
  await page.getByRole("button", { name: "Rejoin", exact: true }).click();
  await shown(tray(page));
  const tokens = await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.log.filter(([method]) => method === "join").map(([, value]) => value.token));
  assert.deepEqual(tokens, ["synthetic-meeting-token-1", "synthetic-meeting-token-2"]);
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 2);
  assert.equal(await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.instances.filter((call) => !call.isDestroyed()).length), 1);
  assert.equal(await page.evaluate(() => Object.keys(sessionStorage).length + Object.keys(localStorage).filter((key) => /token|daily|room/i.test(key)).length), 0, "No credential in browser storage");
  assert.doesNotMatch(page.url(), /token|room/);
});

{
  const session = liveSession();
  session.overrides[`POST /api/v1/e-counseling/appointments/${appointmentId}/recording/start`] = ({ reply }) => {
    session.state.recording = "ACTIVE";
    return reply({ kind: "RECORDING", status: "START_REQUESTED", storage_enabled: false });
  };
  session.overrides[`POST /api/v1/e-counseling/appointments/${appointmentId}/recording/stop`] = ({ reply }) => {
    session.state.recording = "STOP_REQUESTED";
    return reply({ kind: "RECORDING", status: "STOP_REQUESTED", storage_enabled: false });
  };
  await check("governed-recording-through-compass", ePath, { fakeDaily: true, overrides: session.overrides }, async (page, { requests }) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(page.getByText("Media permission · Approved", { exact: true }));
    await tray(page).getByRole("button", { name: "Start recording", exact: true }).click();
    const dialog = page.getByRole("alertdialog", { name: "Start recording?", exact: true });
    await shown(dialog);
    const text = await dialog.innerText();
    assert.match(text, /Audio and video from this session will be recorded\./);
    assert.match(text, /The student has approved media permission\./);
    assert.match(text, /may be downloaded by an authorized assigned Counselor/);
    await dialog.getByRole("button", { name: "Start recording", exact: true }).click();
    await hidden(dialog);
    await shown(stage(page).getByText("Recording", { exact: true }));
    await screenshot(page, "counselor-recording-active");
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/recording/start")).length, 1);

    await tray(page).getByRole("button", { name: "Stop recording", exact: true }).click();
    await shown(tray(page).getByRole("button", { name: "Stopping…", exact: true }));
    await shown(stage(page).getByText("Recording stopping…", { exact: true }));
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/recording/stop")).length, 1);
    for (const method of ["startRecording", "stopRecording", "startTranscription", "stopTranscription"]) assert.equal(await fakeCount(page, method), 0, `The browser never calls Daily ${method}`);
    await screenshot(page, "counselor-recording-governed");
  });
}

{
  const session = liveSession({ storage: "APPROVED" });
  let body = null;
  session.overrides[`POST /api/v1/e-counseling/appointments/${appointmentId}/transcription/start`] = ({ reply, request }) => {
    body = JSON.parse(request.postData());
    session.state.transcription = "ACTIVE";
    return reply({ kind: "TRANSCRIPTION", status: "START_REQUESTED", storage_enabled: body.store_transcript });
  };
  await check("governed-transcription-storage-choice", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await tray(page).getByRole("button", { name: "Start transcription", exact: true }).click();
    const dialog = page.getByRole("alertdialog", { name: "Start live transcription?", exact: true });
    await shown(dialog);
    const liveOnly = dialog.getByRole("radio", { name: /Live transcription only/ });
    const save = dialog.getByRole("radio", { name: /Live transcription \+ save transcript/ });
    assert.equal(await liveOnly.isChecked(), true, "Saving is never the implicit default");
    assert.match(await dialog.innerText(), /The student has allowed transcript storage\./);
    assert.match(await dialog.innerText(), /Transcript text isn’t shown here\./);
    await save.check();
    await dialog.getByRole("button", { name: "Start transcription", exact: true }).click();
    await hidden(dialog);
    assert.deepEqual(body, { store_transcript: true });
    await shown(stage(page).getByText("Transcription on", { exact: true }));
    assert.equal(await fakeCount(page, "startTranscription"), 0);
  });
}

{
  const session = liveSession();
  let body = null;
  session.overrides[`POST /api/v1/e-counseling/appointments/${appointmentId}/transcription/start`] = ({ reply, request }) => {
    body = JSON.parse(request.postData());
    return reply({ kind: "TRANSCRIPTION", status: "START_REQUESTED", storage_enabled: false });
  };
  await check("transcription-without-storage-consent", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await tray(page).getByRole("button", { name: "Start transcription", exact: true }).click();
    const dialog = page.getByRole("alertdialog", { name: "Start live transcription?", exact: true });
    await shown(dialog.getByText(/Live transcription only\. The student hasn’t allowed transcript storage/));
    assert.equal(await dialog.getByRole("radio").count(), 0);
    await dialog.getByRole("button", { name: "Start transcription", exact: true }).click();
    await hidden(dialog);
    assert.deepEqual(body, { store_transcript: false });
  });
}

{
  const session = liveSession();
  await check("provider-events-only-refresh", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    const before = session.state.workspaceReads;
    await fake(page, "providerEvent", "recording-started");
    await page.waitForFunction(() => true);
    for (let attempt = 0; attempt < 50 && session.state.workspaceReads === before; attempt++) await page.waitForTimeout(50);
    assert.ok(session.state.workspaceReads > before, "A provider event asks COMPASS for the session again");
    await page.waitForTimeout(300);
    assert.equal(await stage(page).getByText("Recording", { exact: true }).count(), 0, "COMPASS state, not the browser event, decides what is shown");
    await shown(tray(page).getByRole("button", { name: "Start recording", exact: true }));
    await fake(page, "transcriptMessage");
    assert.doesNotMatch(await page.locator("body").innerText(), /SYNTHETIC TRANSCRIPT TEXT/);
  });
}

await check("leave-warning-during-capture", ePath, { fakeDaily: true, overrides: liveSession({ recording: "ACTIVE", transcription: "ACTIVE" }).overrides }, async (page, { requests }) => {
  await joinCall(page);
  await shown(stage(page).getByText("Recording", { exact: true }));
  await shown(stage(page).getByText("Transcription on", { exact: true }));
  await tray(page).getByRole("button", { name: "Leave session", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Leave this session?", exact: true });
  assert.match(await dialog.innerText(), /Recording and transcription have not been confirmed as stopped\./);
  assert.match(await dialog.innerText(), /Leaving the call may not stop recording or transcription/);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await shown(tray(page));
  await tray(page).getByRole("button", { name: "Leave session", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Leave session", exact: true }).click();
  await shown(stage(page).getByRole("button", { name: "Rejoin", exact: true }));
  assert.equal(requests.filter((request) => request.method === "POST" && /\/(recording|transcription)\/stop$/.test(request.pathname)).length, 0, "Leaving never stops capture");
  assert.equal(await fakeCount(page, "stopRecording"), 0);
  // Capture still running outside the call keeps its stop where the Counselor can reach it.
  await shown(page.getByRole("button", { name: "Stop recording", exact: true }));
});

await check("camera-error-product-copy", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  await joinCall(page);
  await fake(page, "cameraError", { type: "cam-in-use", msg: "NotReadableError: Could not start video source" });
  await shown(page.getByRole("alert").filter({ hasText: "Your camera is being used by another application. You can continue with audio." }));
  assert.doesNotMatch(await page.locator("body").innerText(), /NotReadableError|DailyCam|Could not start video source/);
  await shown(tray(page).getByRole("button", { name: "Microphone", exact: true }));
});

await check("reconnecting-and-network", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  await joinCall(page);
  await fake(page, "connection", "interrupted");
  await shown(stage(page).getByText("Reconnecting…", { exact: true }).first());
  await shown(tray(page));
  assert.equal(await fakeCount(page, "destroy"), 0);
  await fake(page, "connection", "connected");
  await hidden(stage(page).getByText("Reconnecting…", { exact: true }).first());
  await fake(page, "network", "bad");
  await shown(stage(page).getByText("Your connection is unstable", { exact: true }));
  await fake(page, "network", "good");
  await hidden(stage(page).getByText("Your connection is unstable", { exact: true }));
});

await check("remote-audio-autoplay-blocked", ePath, {
  fakeDaily: true,
  initScripts: [`
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      if (this instanceof HTMLAudioElement && !window.__audioUnlocked) return Promise.reject(new DOMException("blocked", "NotAllowedError"));
      return play.call(this);
    };
  `],
  overrides: liveSession().overrides,
}, async (page) => {
  await joinCall(page);
  await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
  const playAudio = page.getByRole("button", { name: "Play audio", exact: true });
  await shown(page.getByText("Audio is ready", { exact: true }));
  await page.evaluate(() => { window.__audioUnlocked = true; });
  await playAudio.click();
  await hidden(playAudio);
  assert.doesNotMatch(await page.locator("body").innerText(), /NotAllowedError/);
});

{
  const session = liveSession();
  await check("refresh-failure-keeps-call-local-controls", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    session.state.failWorkspace = true;
    await fake(page, "providerEvent", "recording-error");
    await shown(page.getByText(/Session status couldn’t be refreshed\. Starting recording or transcription is paused/));
    await shown(stage(page).getByText(`Waiting for ${STUDENT}…`, { exact: true }).first());
    const mic = tray(page).getByRole("button", { name: "Microphone", exact: true });
    await mic.click();
    assert.equal(await mic.getAttribute("aria-pressed"), "false", "Local controls keep working");
    assert.equal(await tray(page).getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true, "Governed starts fail closed");
    assert.equal(await fakeCount(page, "destroy"), 0, "The call stays up");
  });
}

await check("fullscreen-stage", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  await joinCall(page);
  const enabled = await page.evaluate(() => document.fullscreenEnabled);
  const toggle = stage(page).getByRole("button", { name: "Full screen", exact: true });
  if (!enabled) {
    assert.equal(await toggle.count(), 0, "No control where full screen is unavailable");
    return;
  }
  await toggle.click();
  await page.waitForFunction(() => document.fullscreenElement?.getAttribute("aria-label") === "Video call");
  await tray(page).getByRole("button", { name: "Devices", exact: true }).click();
  await page.waitForFunction(() => !document.fullscreenElement);
  await shown(page.getByRole("dialog", { name: "Devices", exact: true }));
});

await check("fullscreen-video-fits-landscape-portrait-and-classic", ePath, {
  viewport: { width: 1280, height: 720 },
  fakeDaily: { remoteVideoSize: { width: 540, height: 960 }, videoFrameMarkers: true },
  overrides: liveSession().overrides,
}, async (page) => {
  await joinCall(page);
  assert.equal(await fakeCount(page, "join"), 1);
  await fake(page, "remoteJoin", { userId: "student", name: STUDENT });
  const portraitTrack = (await fakeTrackIds(page)).remoteVideo;
  await page.waitForFunction((trackId) => {
    const video = document.querySelector("section[aria-label='Video call'] video");
    return video?.srcObject?.getVideoTracks().some((track) => track.id === trackId);
  }, portraitTrack);

  const toggle = stage(page).getByRole("button", { name: "Full screen", exact: true });
  if (!(await page.evaluate(() => document.fullscreenEnabled))) return;
  await toggle.click();
  await page.waitForFunction(() => document.fullscreenElement?.getAttribute("aria-label") === "Video call");
  await assertFullscreenVideoFit(page, { width: 540, height: 960 });
  await screenshot(page, "fullscreen-video-portrait", stage(page));

  for (const [name, source] of [
    ["classic", { width: 800, height: 600 }],
    ["landscape", { width: 1280, height: 720 }],
  ]) {
    const replacement = await page.evaluate((dimensions) => window.__COMPASS_FAKE_DAILY__.replaceRemoteVideo(dimensions).id, source);
    await page.waitForFunction((id) => {
      const video = document.querySelector("section[aria-label='Video call'] video");
      return video?.srcObject?.getTracks()[0]?.id === id;
    }, replacement);
    await assertFullscreenVideoFit(page, source);
    await screenshot(page, `fullscreen-video-${name}`, stage(page));
  }

  await fake(page, "remoteVideo", false);
  await shown(stage(page).getByText("Camera off", { exact: true }).first());
  await shown(stage(page).getByRole("button", { name: "Exit full screen", exact: true }));
  await page.getByRole("button", { name: "Exit full screen", exact: true }).click();
  await page.waitForFunction(() => !document.fullscreenElement);
  assert.equal(await fakeCount(page, "createCallObject"), 1);
  assert.equal(await fakeCount(page, "join"), 1, "Orientation and fullscreen changes do not restart the call");
});

await check("layout-presets-desktop", ePath, { fakeDaily: true, overrides: liveSession({ artifact: "STORED", recording: "READY", transcription: "STOPPED", context: true }).overrides }, async (page) => {
  const group = page.getByRole("group", { name: "Session layout" });
  await shown(group);
  const width = async () => (await stage(page).boundingBox()).width;
  const pressed = (name) => group.getByRole("button", { name, exact: true }).getAttribute("aria-pressed");
  assert.equal(await pressed("Balanced"), "true");
  const balanced = await width();
  await shown(page.getByRole("tab", { name: "Overview", exact: true }));
  await screenshot(page, "layout-balanced");
  await group.getByRole("button", { name: "Compact", exact: true }).click();
  const compact = await width();
  await screenshot(page, "layout-compact");
  await group.getByRole("button", { name: "Focus", exact: true }).focus();
  await page.keyboard.press("Space");
  assert.equal(await pressed("Focus"), "true");
  const focus = await width();
  assert.ok(compact < balanced && balanced < focus, `Distinct widths: ${compact} < ${balanced} < ${focus}`);
  assert.ok(compact >= 320, "Compact keeps a usable video");
  const stageBox = await stage(page).boundingBox();
  const filesBox = await page.getByRole("button", { name: /^Session files/ }).boundingBox();
  assert.ok(filesBox.y > stageBox.y + stageBox.height, "Focus moves the work below the call");
  assert.equal(await page.getByRole("button", { name: /^Student information/ }).getAttribute("aria-expanded"), "false", "Secondary work collapses in Focus");
  await screenshot(page, "layout-focus");
  await noHorizontalOverflow(page);
});

await check("session-remains-mounted-with-collapsed-sidebar", ePath, { fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  const collapse = page.getByRole("button", { name: "Collapse navigation", exact: true });
  await shown(collapse);
  await shown(page.getByRole("navigation").getByRole("link", { name: "Overview", exact: true }));
  await joinCall(page);
  const joins = await fakeCount(page, "join");
  await collapse.click();
  await shown(page.getByRole("button", { name: "Expand navigation", exact: true }));
  await shown(stage(page).getByText(`Waiting for ${STUDENT}…`, { exact: true }).first());
  await noHorizontalOverflow(page);
  assert.equal(await fakeCount(page, "join"), joins, "Sidebar collapse does not rejoin the session");
  assert.equal(await fakeCount(page, "createCallObject"), 1);
  await screenshot(page, "counselor-call-collapsed-sidebar");
});

await check("laptop-1280-two-columns", ePath, { device: "laptop", fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  await shown(page.getByRole("group", { name: "Session layout" }));
  const stageBox = await stage(page).boundingBox();
  const encounter = await page.getByRole("button", { name: /^Counseling Encounter/ }).boundingBox();
  assert.ok(encounter.x > stageBox.x + stageBox.width - 1, "Work sits beside the call");
  await joinCall(page);
  await screenshot(page, "laptop-1280");
  await noHorizontalOverflow(page);
});

await check("tablet-stacked-no-presets", ePath, { device: "tablet", fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
  await shown(stage(page));
  assert.equal(await page.getByRole("group", { name: "Session layout" }).isVisible(), false, "Presets appear only where they change the layout");
  await joinCall(page);
  await noHorizontalOverflow(page);
  await screenshot(page, "tablet-counselor");
});

for (const device of ["phone", "narrowPhone"]) {
  await check(`counselor-mobile-tray-${device}`, ePath, { device, fakeDaily: true, overrides: liveSession().overrides }, async (page) => {
    assert.equal(await page.getByRole("group", { name: "Session layout" }).isVisible(), false);
    const viewport = page.viewportSize();
    const stageTop = (await stage(page).boundingBox()).y;
    assert.ok(stageTop < viewport.height / 2, `The call starts in the top half of the screen (${stageTop}px)`);
    await joinCall(page);
    for (const name of ["Microphone", "Camera", "Start recording", "Start transcription", "Leave session"]) {
      const box = await tray(page).getByRole("button", { name, exact: true }).boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= viewport.width, `${name} fits the screen`);
      assert.ok(box.width >= 44 && box.height >= 44, `${name} is a usable tap target`);
    }
    const trayBox = await tray(page).boundingBox();
    assert.ok(trayBox.height < 80, `One row of controls (${trayBox.height}px)`);
    await stage(page).getByRole("button", { name: "Devices", exact: true }).tap();
    await shown(page.getByRole("dialog", { name: "Devices", exact: true }));
    await page.keyboard.press("Escape");
    await noHorizontalOverflow(page);
    await screenshot(page, `counselor-${device}`);
  });
}

await check("student-mobile-v2", ePath, { device: "phone", role: "STUDENT", fakeDaily: true, overrides: liveSession({ student: true, decision: "PENDING", storage: "PENDING" }).overrides }, async (page) => {
  const viewport = page.viewportSize();
  const stageTop = (await stage(page).boundingBox()).y;
  assert.ok(stageTop < viewport.height / 2, `The call starts in the top half of the screen (${stageTop}px)`);
  await shown(page.getByRole("heading", { name: COUNSELOR, exact: true }));
  await joinCall(page, COUNSELOR);
  for (const name of ["Microphone", "Camera", "Devices", "Leave session"]) await shown(tray(page).getByRole("button", { name, exact: true }));
  assert.equal(await tray(page).getByRole("button", { name: /recording|transcription/i }).count(), 0, "The Student has no capture controls");

  await shown(page.getByRole("heading", { name: "Recording & live transcription", exact: true }));
  await shown(page.getByText("Recording creates a saved audio/video file.", { exact: true }));
  await shown(page.getByText("Allows a transcript file to be saved.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: /^Allow / }).count(), 2);
  assert.equal(await page.getByRole("button", { name: /^Decline / }).count(), 2);
  assert.equal(await page.getByText(/Live transcription is only saved when transcript storage is separately allowed/).isVisible(), false, "The longer explanation starts collapsed");
  await page.getByText("Details", { exact: true }).first().tap();
  await shown(page.getByText(/Live transcription is only saved when transcript storage is separately allowed/));
  await page.getByRole("button", { name: "Allow recording & live transcription", exact: true }).tap();
  const review = page.getByRole("alertdialog", { name: "Allow recording & live transcription?", exact: true });
  const text = await review.innerText();
  assert.match(text, /creates a saved audio\/video file/);
  assert.match(text, /live transcription/);
  assert.match(text, /Allowing doesn’t start either one/);
  assert.match(text, /doesn’t affect your access to Counseling/);
  await review.getByRole("button", { name: "Cancel", exact: true }).tap();
  await noHorizontalOverflow(page);
  await screenshot(page, "student-mobile-v2");
});

await check("student-withdrawal-consequence", ePath, { role: "STUDENT", fakeDaily: true, overrides: liveSession({ student: true, decision: "APPROVED" }).overrides }, async (page) => {
  await page.getByRole("button", { name: "Withdraw recording and live transcription permission", exact: true }).click();
  const review = page.getByRole("alertdialog");
  const text = await review.innerText();
  assert.match(text, /Recording or transcription that’s running will be asked to stop/);
  assert.match(text, /Withdrawing doesn’t delete files already created\. They remain subject to the University’s records and privacy requirements, and copies already downloaded can’t be recalled\./);
  assert.doesNotMatch(text, /retention rules|holds govern|deleted right away/);
  assert.match(text, /Counseling continues/);
  await review.getByRole("button", { name: "Cancel", exact: true }).click();
  await screenshot(page, "student-desktop-approved");
});

await check("student-v1-scopes-stay-distinct", ePath, { role: "STUDENT", decision: "PENDING" }, async (page) => {
  for (const name of ["Audio/video recording", "Session transcription", "Transcript storage"]) await shown(page.getByRole("heading", { name, exact: true }));
  await shown(page.getByRole("button", { name: "Allow audio/video recording", exact: true }));
  await shown(page.getByRole("button", { name: "Allow session transcription", exact: true }));
  assert.match(await page.locator("main").innerText(), /Not requested/);
  assert.doesNotMatch(await page.locator("main").innerText(), /Recording & live transcription/);
});

await check("help-keyboard-focus", ePath, {}, async (page) => {
  const help = page.getByRole("button", { name: "Help: About E-Counseling", exact: true });
  await shown(help);
  await help.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "About E-Counseling", exact: true });
  await shown(dialog);
  for (const name of ["Media consent", "Recording", "Transcription", "Transcript storage", "Encounter records", "Call and devices"]) await shown(dialog.getByRole("heading", { name, exact: true }));
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true);
  await page.keyboard.press("Tab");
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, "Focus stays in Help");
  await page.keyboard.press("Escape");
  await hidden(dialog);
  await page.waitForFunction((element) => element === document.activeElement, await help.elementHandle());
});

await check("visible-video-blocker", ePath, { disabledVideo: true }, async (page) => {
  await shown(stage(page).getByText(/^Video sessions are not available right now/));
  await hidden(page.getByRole("button", { name: "Join session", exact: true }));
  await hidden(page.getByRole("button", { name: "Start recording", exact: true }));
});

await check("active-capture-visible-before-joining", ePath, { role: "STUDENT", mediaStatus: "ACTIVE" }, async (page) => {
  await shown(stage(page).getByText("Recording", { exact: true }));
  await shown(stage(page).getByText("Transcription on", { exact: true }));
  assert.equal(await stage(page).getByRole("list", { name: "Session capture" }).count(), 1);
});

await check("encounter-separate-from-recording", ePath, {}, async (page) => {
  const trigger = page.getByRole("button", { name: "Record encounter", exact: true });
  await shown(trigger);
  await shown(page.getByRole("button", { name: /^Counseling Encounter.*Not yet recorded/ }));
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Record encounter", exact: true });
  await dialog.getByLabel("Actual start", { exact: true }).fill("2026-01-06T09:00");
  await dialog.getByLabel("Actual end", { exact: true }).fill("2026-01-06T10:00");
  await page.keyboard.press("Escape");
  await hidden(dialog);
  assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
  await trigger.click();
  assert.equal(await dialog.getByLabel("Actual start", { exact: true }).inputValue(), "2026-01-06T09:00");
});

let finishEncounter;
const encounterPending = new Promise((resolve) => { finishEncounter = resolve; });
await check("encounter-save-dismissal", ePath, { overrides: {
  "POST /api/v1/counseling/encounters": async ({ reply }) => { await encounterPending; await reply({ error: { code: "test_uncertain", message: "Synthetic uncertain result" } }, 500); },
} }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Record encounter", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Record encounter", exact: true });
  await dialog.getByLabel("Actual start", { exact: true }).fill("2026-01-06T09:00");
  await dialog.getByLabel("Actual end", { exact: true }).fill("2026-01-06T10:00");
  await dialog.getByRole("button", { name: "Record encounter", exact: true }).click();
  await shown(dialog.getByRole("button", { name: "Recording encounter…", exact: true }));
  await page.keyboard.press("Escape");
  await shown(dialog);
  finishEncounter();
  await shown(dialog.getByText(/Check your encounters before trying again/));
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/counseling/encounters")).length, 1);
});
finishEncounter();

await check("v2-session-files-preparing", ePath, { overrides: liveSession({ recording: "READY", transcription: "READY", artifact: "PROCESSING" }).overrides }, async (page) => {
  await shown(page.getByText("Preparing file…", { exact: true }).first());
  assert.equal(await page.getByText("Preparing file…", { exact: true }).count(), 2);
  await shown(page.getByRole("button", { name: /^Session files.*Recording preparing · Transcript preparing/ }));
  await hidden(page.getByRole("button", { name: "Download recording", exact: true }));
  await page.getByRole("button", { name: "Help: About E-Counseling", exact: true }).click();
  await shown(page.getByRole("dialog").getByRole("heading", { name: "Private files", exact: true }));
});

await check("v2-no-transcript-saved-copy", ePath, { overrides: liveSession({ recording: "READY", transcription: "READY", artifact: null }).overrides }, async (page) => {
  await shown(page.getByText("No transcript saved.", { exact: true }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Transcript storage\s*Off/);
});

let signedRequests = 0;
{
  // Use a real loopback attachment: WebKit does not reliably emit downloads for routed media.
  const transfers = [];
  const referrers = [];
  const bytes = Buffer.from("synthetic recording attachment");
  const attachment = createServer((request, response) => {
    transfers.push(new URL(request.url, "http://localhost").searchParams.get("token"));
    referrers.push(request.headers.referer ?? null);
    // These opaque text bytes are an attachment fixture, not an MP4. Linux WebKit sends a
    // video MIME type to its media plug-in even with attachment disposition, hiding downloads.
    response.writeHead(200, { "Content-Type": "application/octet-stream", "Content-Disposition": 'attachment; filename="synthetic.mp4"', "Cache-Control": "no-store" });
    response.end(bytes);
  });
  attachment.listen(0, "127.0.0.1");
  await once(attachment, "listening");
  const attachmentURL = `http://127.0.0.1:${attachment.address().port}/synthetic-media-download`;
  const session = liveSession({ recording: "READY", transcription: "READY", artifact: "STORED" });
  session.overrides[`/api/v1/e-counseling/appointments/${appointmentId}/media/RECORDING/access`] = ({ reply }) => reply({ url: `${attachmentURL}?token=${++signedRequests}`, expires_at: "2099-10-08T00:00:00Z" });
  await check("v2-fresh-download-per-click", ePath, { overrides: session.overrides }, async (page, { context, requests }) => {
    const button = page.getByRole("button", { name: "Download recording", exact: true });
    await shown(button);
    assert.equal(requests.filter((request) => request.pathname.endsWith("/access")).length, 0, "No link is fetched before the click");
    for (let count = 1; count <= 2; count++) {
      // WebKit delivers a target=_blank attachment on its new page; Chromium uses the opener.
      const download = new Promise((resolve, reject) => {
        const pages = new Set([page]);
        const cleanup = () => { clearTimeout(timer); context.off("page", opened); for (const source of pages) source.off("download", received); };
        const received = item => { cleanup(); resolve(item); };
        const opened = popup => { pages.add(popup); popup.once("download", received); };
        const timer = setTimeout(() => { cleanup(); reject(new Error("The media attachment did not download")); }, 12_000);
        page.once("download", received);
        context.on("page", opened);
      });
      const [result] = await Promise.all([download, button.click()]);
      assert.equal(result.suggestedFilename(), "synthetic.mp4");
      assert.deepEqual(await readFile(await result.path()), bytes);
      await result.delete();
      await shown(button);
      assert.equal(signedRequests, count);
      assert.deepEqual(transfers, Array.from({ length: count }, (_, index) => String(index + 1)));
      assert.deepEqual(referrers, Array(count).fill(null), "The signed download URL receives no referrer");
    }
    assert.doesNotMatch(await page.locator("main").innerText(), /token=|synthetic-media-download/);
    await screenshot(page, "v2-counselor-session-files");
  });
  await new Promise(resolve => attachment.close(resolve));
}

{
  const session = liveSession({ recording: "READY", artifact: "STORED" });
  session.overrides[`/api/v1/e-counseling/appointments/${appointmentId}/media/RECORDING/access`] = ({ reply }) => reply({ error: { code: "ecounseling_artifact_unavailable", message: "File unavailable" } }, 503);
  await check("v2-download-error", ePath, { overrides: session.overrides }, async (page) => {
    await page.getByRole("button", { name: "Download recording", exact: true }).click();
    await shown(page.getByRole("alert").filter({ hasText: "file" }));
  });
}

{
  const session = liveSession({ student: true, joinState: "TOO_EARLY", roomProvisioned: false, joinAllowed: false });
  await check("prejoin-device-check-student-too-early", ePath, { role: "STUDENT", fakeDaily: true, overrides: session.overrides }, async (page, { requests }) => {
    await shown(stage(page).getByText(/^You can join starting /));
    await hidden(page.getByRole("button", { name: "Join session", exact: true }));
    const trigger = stage(page).getByRole("button", { name: "Check devices", exact: true });
    await shown(trigger);
    await trigger.click();

    await shown(stage(page).getByText("Checking devices", { exact: true }));
    await shown(stage(page).getByText(`Local preview only · ${COUNSELOR} cannot see or hear you`, { exact: true }));
    await hidden(page.getByRole("button", { name: "Join session", exact: true }));
    await hidden(tray(page));
    const controls = stage(page).getByRole("group", { name: "Pre-join device controls" });
    for (const name of ["Microphone", "Camera", "Devices"]) await shown(controls.getByRole("button", { name, exact: true }));
    for (const name of ["Microphone", "Camera", "Devices"]) {
      const box = await controls.getByRole("button", { name, exact: true }).boundingBox();
      assert.equal(box.width, 56, `${name} uses a square 56px control`);
      assert.equal(box.height, 56, `${name} uses a square 56px control`);
    }
    await shown(stage(page).getByRole("list", { name: "Device readiness", exact: true }));
    await shown(stage(page).getByText("Microphone ready", { exact: true }));
    await shown(stage(page).getByText("Camera ready", { exact: true }));
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 0, "Device check never requests a meeting credential");
    assert.equal(await fakeCount(page, "startCamera"), 1);
    assert.equal(await fakeCount(page, "join"), 0);

    const previewVideo = stage(page).locator("video").first();
    await shown(previewVideo);
    const ids = await fakeTrackIds(page);
    assert.deepEqual(await attachedTrack(previewVideo), [ids.localVideo]);
    assert.equal(await previewVideo.evaluate((element) => element.muted), true);

    await controls.getByRole("button", { name: "Devices", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Devices", exact: true });
    await shown(dialog);
    assert.match(await dialog.innerText(), /Changes apply to this local preview/);
    await shown(dialog.getByRole("button", { name: "Refresh devices", exact: true }));
    const meter = dialog.getByRole("meter", { name: "Microphone level", exact: true });
    await shown(meter);
    await fake(page, "localAudioLevel", 0.75);
    await page.waitForFunction(() => document.querySelector("[role='meter'][aria-label='Microphone level']")?.getAttribute("aria-valuenow") === "75");
    await shown(dialog.getByText("Microphone is picking up sound", { exact: true }));
    await screenshot(page, "student-prejoin-advanced-devices");
    await page.keyboard.press("Escape");
    await hidden(dialog);

    await stage(page).getByRole("button", { name: "Close preview", exact: true }).click();
    await shown(stage(page).getByText(/^You can join starting /));
    await shown(stage(page).getByText("Device check complete · Camera on, Mic on", { exact: true }));
    assert.equal(await fakeCount(page, "destroy"), 1);
    assert.deepEqual(
      await page.evaluate(() => {
        const call = window.__COMPASS_FAKE_DAILY__.instances[0];
        return [call.localTracks.video.readyState, call.localTracks.audio.readyState];
      }),
      ["ended", "ended"],
      "Closing the preview stops local capture tracks"
    );
    await page.waitForFunction((element) => element === document.activeElement, await trigger.elementHandle());
    await noHorizontalOverflow(page);
    await screenshot(page, "student-prejoin-desktop-device-unavailable");
  });
}

await check("prejoin-device-check-and-join-transition", ePath, {
  fakeDaily: true,
  initScripts: [`
    window.__sinkIds = [];
    HTMLMediaElement.prototype.setSinkId = async function (id) {
      window.__sinkIds.push(id);
    };
    window.__testAudioContexts = [];
    if (window.AudioContext) {
      const AudioContextConstructor = window.AudioContext;
      window.AudioContext = new Proxy(AudioContextConstructor, {
        construct(target, args) {
          const context = Reflect.construct(target, args);
          window.__testAudioContexts.push(context);
          return context;
        },
      });
    }
  `],
  overrides: liveSession().overrides,
}, async (page, { requests }) => {
  await stage(page).getByRole("button", { name: "Check devices", exact: true }).click();
  await shown(stage(page).getByText("Checking devices", { exact: true }));
  const controls = stage(page).getByRole("group", { name: "Pre-join device controls" });
  const devices = page.getByRole("button", { name: "Devices", exact: true });
  await devices.click();
  const dialog = page.getByRole("dialog", { name: "Devices", exact: true });
  await shown(dialog);
  const toneContextStartIndex = await page.evaluate(() => window.__testAudioContexts.length);

  await fake(page, "addDevice", { deviceId: "cam-2", kind: "videoinput", label: "USB camera" });
  await fake(page, "addDevice", { deviceId: "mic-2", kind: "audioinput", label: "USB headset mic" });
  await fake(page, "addDevice", { deviceId: "spk-2", kind: "audiooutput", label: "External speakers" });
  await page.waitForFunction(() => [...document.querySelectorAll("option")].some((option) => option.textContent === "External speakers"));

  await dialog.getByRole("combobox", { name: "Camera", exact: true }).selectOption({ label: "USB camera" });
  await dialog.getByRole("combobox", { name: "Microphone", exact: true }).selectOption({ label: "USB headset mic" });
  await dialog.getByRole("combobox", { name: "Speaker", exact: true }).selectOption({ label: "External speakers" });
  assert.doesNotMatch(await dialog.innerText(), /cam-2|mic-2|spk-1|spk-2/, "Raw device IDs are never displayed");

  await page.evaluate(() => { window.__sinkIds = []; });
  const testSound = dialog.getByRole("button", { name: "Play test sound", exact: true });
  await testSound.click();
  const stopSound = dialog.getByRole("button", { name: "Stop test sound", exact: true });
  await shown(stopSound);
  assert.deepEqual(await page.evaluate(() => window.__sinkIds), ["spk-2"]);
  await stopSound.click();
  await shown(testSound);
  await testSound.click();
  await shown(stopSound);
  await screenshot(page, "counselor-prejoin-advanced-devices");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await hidden(dialog);
  try {
    await page.waitForFunction((startIndex) => {
      const toneContexts = window.__testAudioContexts.slice(startIndex);
      return toneContexts.length >= 2 && toneContexts.every((context) => context.state === "closed");
    }, toneContextStartIndex);
  } catch {
    throw new Error(`Speaker test contexts did not close after dialog dismissal: ${JSON.stringify(await page.evaluate((startIndex) => window.__testAudioContexts.slice(startIndex).map((context) => context.state), toneContextStartIndex))}`);
  }
  try {
    await page.waitForFunction((element) => element === document.activeElement, await devices.elementHandle());
  } catch {
    throw new Error("Focus did not return to the Devices button after dialog dismissal.");
  }
  await screenshot(page, "counselor-prejoin-simple");

  await controls.getByRole("button", { name: "Microphone", exact: true }).click();
  await controls.getByRole("button", { name: "Camera", exact: true }).click();
  await shown(stage(page).getByText("Camera off", { exact: true }).first());
  await shown(stage(page).getByText("Microphone off", { exact: true }));
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 0);

  await stage(page).getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for ${STUDENT}…`, { exact: true }).first());
  await shown(tray(page));
  assert.equal(await fakeCount(page, "createCallObject"), 1, "Joining from preview reuses the single Call Object");
  assert.equal(await fakeCount(page, "join"), 1);
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 1);
  assert.equal(await tray(page).getByRole("button", { name: "Microphone", exact: true }).getAttribute("aria-pressed"), "false");
  assert.equal(await tray(page).getByRole("button", { name: "Camera", exact: true }).getAttribute("aria-pressed"), "false");
  await shown(stage(page).locator("figure").getByText("You, camera off", { exact: true }));
  assert.equal(await page.evaluate(() => Object.keys(sessionStorage).length + Object.keys(localStorage).filter((key) => /device|cam|mic|spk|token|daily|room/i.test(key)).length), 0);
  await screenshot(page, "counselor-prejoin-joined-preferences");
});

await check("student-prejoin-mobile", ePath, { device: "narrowPhone", role: "STUDENT", fakeDaily: true, overrides: liveSession({ student: true }).overrides }, async (page) => {
  await stage(page).getByRole("button", { name: "Check devices", exact: true }).tap();
  const controls = stage(page).getByRole("group", { name: "Pre-join device controls" });
  await shown(controls);
  for (const name of ["Microphone", "Camera", "Devices"]) {
    const control = controls.getByRole("button", { name, exact: true });
    const box = await control.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 320, `${name} stays within the mobile stage`);
    assert.equal(box.width, 56);
    assert.equal(box.height, 56);
  }
  await shown(stage(page).getByRole("button", { name: "Join session", exact: true }));
  await shown(stage(page).getByRole("button", { name: "Close preview", exact: true }));
  const preview = stage(page).locator("video").first();
  await shown(preview);
  const box = await preview.boundingBox();
  assert.ok(Math.abs(box.width / box.height - 16 / 9) < 0.08, "Local preview keeps a stable video aspect ratio");
  await noHorizontalOverflow(page);
  await screenshot(page, "student-prejoin-mobile");
  for (const width of [375, 768]) {
    await page.setViewportSize({ width, height: 820 });
    await shown(stage(page).getByRole("button", { name: "Join session", exact: true }));
    await shown(stage(page).getByRole("button", { name: "Close preview", exact: true }));
    await noHorizontalOverflow(page);
  }
});

await check("prejoin-navigation-cancels-pending-permission", ePath, {
  fakeDaily: { holdPreview: true },
  overrides: liveSession().overrides,
}, async (page) => {
  await stage(page).getByRole("button", { name: "Check devices", exact: true }).click();
  await shown(stage(page).getByText("Checking devices…", { exact: true }));
  await page.getByRole("link", { name: "Back to appointment", exact: true }).click();
  await page.waitForFunction(() => window.location.pathname.startsWith("/portal/appointments/"));
  await fake(page, "releasePreview");
  await page.waitForFunction(() => window.__COMPASS_FAKE_DAILY__.instances[0]?.isDestroyed() === true);
  assert.deepEqual(
    await page.evaluate(() => {
      const call = window.__COMPASS_FAKE_DAILY__.instances[0];
      return [call.localTracks.video.readyState, call.localTracks.audio.readyState];
    }),
    ["ended", "ended"]
  );
});

await finish();
