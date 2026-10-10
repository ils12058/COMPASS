// The persistent E-Counseling runtime and call dock (ADR-094) in a real browser: one call that
// follows the person across portal pages. The page uses the fake Call Object and synthetic API
// fixtures; no Daily room, credential, recording or institutional record is touched.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { fakeDailyInitScript } from "./support/fake-daily.mjs";
import { appointmentId, consents, user, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("ecounseling-runtime");
const ePath = `/portal/e-counseling/${appointmentId}`;
const ROUTINE = "routine-runtime-test";
const OTHER = "appointment-other-session";
const STUDENT = "Maria Santos";
const COUNSELOR = "Maria Reyes";

const evaluation = {
  academic_adjustment_rating: null, physical_adjustment_rating: null, social_adjustment_rating: null,
  spiritual_adjustment_rating: null, financial_adjustment_rating: null, emotional_adjustment_rating: null,
  other_adjustment: "", special_concern: "", recommendations: "",
};
const routineBase = {
  id: ROUTINE, academic_year: null, appointment: { id: appointmentId, reference_code: "APT-TEST-1024", starts_at: "2026-10-08T02:00:00Z", ends_at: "2026-10-08T03:00:00Z" },
  counseling_encounter: null, created_at: "2026-10-07T00:00:00Z", delivery_mode: "ONLINE", entry_mode: "APPOINTMENT",
  form_revision: null, inventory_context: null, workflow_state: "ACTIVE", intake_submitted_at: null,
};

// A session whose state a test can change while the pages are open, for both roles, with the
// Routine Interview pages the call should survive.
function liveSession({ student = false, recording = "NOT_STARTED", transcription = "NOT_STARTED", consent = "APPROVED" } = {}) {
  const state = { recording, transcription, consent, storage: "NOT_REQUESTED", joins: 0, workspaceStatus: 200, sessionStatus: 200, maintenance: false, evaluationSaves: [], intakeSaves: [], logouts: 0 };
  const prefix = `/api/v1/e-counseling/${student ? "me/" : ""}appointments`;
  // The synthetic user can also work on the session's Routine Interview.
  const base = user(student ? "STUDENT" : "COUNSELOR");
  const sessionUser = { ...base, capabilities: [...base.capabilities, ...(student ? ["routine_interviews.view_self", "routine_interviews.manage_self"] : ["routine_interviews.view_assigned", "routine_interviews.manage_assigned"])] };
  const data = (id) => {
    const value = workspace();
    value.appointment = { ...value.appointment, id };
    value.media.media_policy_version = 2;
    value.media.recording.capture_status = state.recording;
    value.media.transcription.capture_status = state.transcription;
    value.media.recording.consent_status = state.consent;
    value.media.transcription.consent_status = state.consent;
    value.media.transcription.storage_consent_status = state.storage;
    value.routine_interview = student ? { id: ROUTINE, intake_status: "DRAFT" } : { id: ROUTINE, intake_status: "SUBMITTED", evaluation_status: "DRAFT" };
    return value;
  };
  const workspaceReply = (id) => ({ reply }) => {
    if (state.maintenance) return reply({ error: { code: "maintenance_mode", message: "Synthetic maintenance" } }, 503);
    if (state.workspaceStatus !== 200) return reply({ error: { code: "synthetic", message: "Synthetic failure" } }, state.workspaceStatus);
    return reply(data(id));
  };
  const overrides = {
    [`${prefix}/${appointmentId}`]: workspaceReply(appointmentId),
    [`${prefix}/${OTHER}`]: workspaceReply(OTHER),
    [`${prefix}/${appointmentId}/consents`]: ({ reply }) => reply({ items: [{ ...consents(state.consent)[0], id: "v2-media", scope: "SESSION_MEDIA_CAPTURE" }] }),
    [`${prefix}/${OTHER}/consents`]: ({ reply }) => reply({ items: [] }),
    [`POST /api/v1/e-counseling/appointments/${appointmentId}/join`]: ({ reply }) => {
      state.joins += 1;
      return reply({ appointment_id: appointmentId, workspace_id: "w", provider: "DAILY", room_url: "https://synthetic.daily.co/room", meeting_token: `synthetic-meeting-token-${state.joins}`, token_expires_at: new Date(Date.now() + 900_000).toISOString() });
    },
    [`POST /api/v1/e-counseling/appointments/${appointmentId}/recording/stop`]: ({ reply }) => {
      state.recording = "STOP_REQUESTED";
      return reply({ kind: "RECORDING", status: "STOP_REQUESTED", storage_enabled: false });
    },
    "/api/v1/auth/session": ({ reply }) => state.sessionStatus === 200
      ? reply({ user: sessionUser, session: { id: "test-session", expires_at: "2099-10-07T00:00:00Z", is_current: true } })
      : reply({ error: { code: state.sessionStatus === 401 ? "authentication_required" : "synthetic", message: "Synthetic" } }, state.sessionStatus),
    "POST /api/v1/auth/logout": ({ reply }) => { state.logouts += 1; return reply({}); },
    "/api/v1/platform/status": ({ reply }) => reply(state.maintenance
      ? { status: "maintenance_active", starts_at: "2026-10-08T00:00:00Z", ends_at: null, message: "Synthetic maintenance" }
      : { status: "operational", starts_at: null, ends_at: null, message: null }),
    [`/api/v1/routine-interviews/${ROUTINE}`]: { ...routineBase, counseling_context_available: false, evaluation, evaluation_finalized_at: null, evaluation_status: "DRAFT", intake: { coping_with_college_challenges: "Synthetic answer" }, intake_status: "SUBMITTED", intake_submitted_at: "2026-10-07T00:00:00Z", student: { id: "student", display_name: STUDENT } },
    [`PUT /api/v1/routine-interviews/${ROUTINE}/evaluation`]: ({ reply, request }) => {
      state.evaluationSaves.push(JSON.parse(request.postData()));
      return reply({ ...routineBase, counseling_context_available: false, evaluation: JSON.parse(request.postData()), evaluation_finalized_at: null, evaluation_status: "DRAFT", intake: { coping_with_college_challenges: "Synthetic answer" }, intake_status: "SUBMITTED", intake_submitted_at: "2026-10-07T00:00:00Z", student: { id: "student", display_name: STUDENT } });
    },
    [`/api/v1/routine-interviews/${ROUTINE}/encounter-candidates`]: { items: [], page: 1, page_size: 20, has_next: false },
    [`/api/v1/routine-interviews/me/${ROUTINE}`]: { ...routineBase, counselor: { id: "counselor", display_name: COUNSELOR }, intake: {}, intake_status: "DRAFT" },
    [`PUT /api/v1/routine-interviews/me/${ROUTINE}/intake`]: ({ reply, request }) => {
      state.intakeSaves.push(JSON.parse(request.postData()));
      return reply({ ...routineBase, counselor: { id: "counselor", display_name: COUNSELOR }, intake: JSON.parse(request.postData()), intake_status: "DRAFT" });
    },
  };
  return { state, overrides };
}

const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const dock = (page) => page.getByRole("region", { name: "Active E-Counseling call" });
const stage = (page) => page.getByRole("region", { name: "Video call" });
const remoteTrackIds = (page) => page.evaluate(() => {
  const call = window.__COMPASS_FAKE_DAILY__.instances.findLast((item) => !item.isDestroyed());
  return { video: call.remote?.videoTrack.id, audio: call.remote?.audioTrack.id };
});
const playingAudio = (page) => page.locator("audio").evaluateAll((elements) => elements.flatMap((element) => element.srcObject?.getTracks().map((track) => track.id) ?? []));

async function joinCall(page, waitingFor = STUDENT) {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for ${waitingFor}…`, { exact: true }).first());
}

async function openRoutineFromSession(page) {
  await page.getByRole("button", { name: /^Session details/ }).click();
  await page.getByRole("link", { name: "Open Routine Interview", exact: true }).click();
  await page.waitForURL(new RegExp(`/portal/routine-interviews/${ROUTINE}$`));
}

{
  const session = liveSession();
  await check("counselor-call-follows-routine-interview", ePath, { fakeDaily: true, overrides: session.overrides }, async (page, { requests }) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));
    assert.equal(await dock(page).count(), 0, "The dock steps aside on the active session page");
    await page.evaluate(() => { window.__audioOwner = document.querySelector("audio"); });

    await openRoutineFromSession(page);
    await shown(dock(page));
    await shown(dock(page).getByText(`${STUDENT}`, { exact: false }).first());
    const ids = await remoteTrackIds(page);
    await page.waitForFunction((id) => [...document.querySelectorAll("section[aria-label='Active E-Counseling call'] video")].some((video) => video.srcObject?.getTracks()[0]?.id === id), ids.video);
    assert.deepEqual(await playingAudio(page), [ids.audio], "One element plays the other person");
    assert.equal(await page.evaluate(() => document.querySelector("audio") === window.__audioOwner), true, "The same audio element kept playing across the page change");
    assert.equal(await page.evaluate(() => document.querySelectorAll("audio").length), 1);

    // The Counselor Evaluation stays on its own page and saves normally during the call.
    await page.getByLabel("Recommendations", { exact: true }).fill("Synthetic follow-up next week.");
    await page.getByRole("button", { name: "Save evaluation", exact: true }).click();
    await shown(page.getByText("Saved", { exact: true }));
    assert.equal(session.state.evaluationSaves.at(-1).recommendations, "Synthetic follow-up next week.");
    await screenshot(page, "counselor-evaluation-with-dock");
    assert.equal(await fakeCount(page, "join"), 1);
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 1);
  });
}

{
  const session = liveSession();
  await check("counselor-return-to-session-no-rejoin", ePath, { fakeDaily: true, overrides: session.overrides }, async (page, { requests }) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await openRoutineFromSession(page);
    await shown(dock(page));
    await dock(page).getByRole("link", { name: "Return to session", exact: true }).click();
    await page.waitForURL(new RegExp(`/portal/e-counseling/${appointmentId}$`));
    await shown(stage(page).getByText("Connected", { exact: true }));
    await hidden(dock(page));
    assert.equal(await fakeCount(page, "createCallObject"), 1, "One call object for the whole portal session");
    assert.equal(await fakeCount(page, "join"), 1, "No second join");
    assert.equal(await fakeCount(page, "destroy"), 0);
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/join")).length, 1, "No new meeting token for moving between pages");
    const ids = await remoteTrackIds(page);
    await page.waitForFunction((id) => [...document.querySelectorAll("section[aria-label='Video call'] video")].some((video) => video.srcObject?.getTracks()[0]?.id === id), ids.video);
  });
}

{
  const session = liveSession({ recording: "ACTIVE" });
  await check("dock-controls-capture-and-leave", ePath, { fakeDaily: true, overrides: session.overrides }, async (page, { requests }) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await openRoutineFromSession(page);
    const call = dock(page);
    await shown(call.getByText("Recording", { exact: true }));
    assert.equal(await call.getByRole("button", { name: /Start recording|Start transcription|^Record$|^Transcript$/ }).count(), 0, "Capture never starts from the dock");
    assert.equal(await call.getByRole("link", { name: /download/i }).count() + await call.getByRole("button", { name: /download/i }).count(), 0, "No files in the dock");
    assert.doesNotMatch(await call.innerText(), /APT-TEST|Appointment reference|consent history|Daily/i);

    const mic = call.getByRole("button", { name: "Microphone", exact: true });
    await mic.click();
    assert.equal(await mic.getAttribute("aria-pressed"), "false");
    await call.getByRole("button", { name: "Camera", exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.log.filter(([method]) => method.startsWith("setLocal"))), [["setLocalAudio", false], ["setLocalVideo", false]]);

    await call.getByRole("button", { name: "Devices", exact: true }).click();
    const devices = page.getByRole("dialog", { name: "Devices", exact: true });
    await shown(devices);
    const box = await call.boundingBox();
    const covering = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest("section[aria-label='Active E-Counseling call']") === null, { x: box.x + 10, y: box.y + 10 });
    assert.equal(covering, true, "Modal dialogs sit above the dock");
    await page.keyboard.press("Escape");
    await hidden(devices);

    await call.getByRole("button", { name: "Stop recording", exact: true }).click();
    await shown(call.getByText("Recording stopping…", { exact: true }));
    assert.equal(await call.getByRole("button", { name: "Stopping…", exact: true }).isDisabled(), true, "Stopping holds until COMPASS confirms");
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/recording/stop")).length, 1, "The stop goes through COMPASS");
    for (const method of ["startRecording", "stopRecording", "startTranscription", "stopTranscription"]) assert.equal(await fakeCount(page, method), 0, method);
    await screenshot(page, "dock-capture-stopping");

    session.state.recording = "ACTIVE";
    await fake(page, "providerEvent", "recording-started");
    await shown(call.getByText("Recording", { exact: true }));
    await call.getByRole("button", { name: "Leave session", exact: true }).click();
    const warning = page.getByRole("alertdialog", { name: "Leave this session?", exact: true });
    assert.match(await warning.innerText(), /Recording is still active\.[\s\S]*doesn’t confirm that it has stopped/);
    await warning.getByRole("button", { name: "Leave session", exact: true }).click();
    await hidden(call);
    assert.equal(await fakeCount(page, "destroy"), 1);
    assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/recording/stop")).length, 1, "Leaving never stops capture");
    assert.equal(await page.getByRole("region", { name: "E-Counseling call ended" }).count(), 0, "Leaving on purpose needs no ended notice");
  });
}

{
  const session = liveSession({ student: true, consent: "APPROVED" });
  await check("student-mobile-dock-collapse-and-intake", ePath, { device: "phone", role: "STUDENT", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, COUNSELOR);
    await fake(page, "remoteJoin", { userId: "counselor", name: "Maria" });
    await openRoutineFromSession(page);
    const call = dock(page);
    await shown(call);
    assert.equal(await call.getByRole("button", { name: /Stop recording|Stop transcription/ }).count(), 0, "Students have no stop");
    await call.getByRole("button", { name: "Minimize call", exact: true }).tap();
    const show = call.getByRole("button", { name: "Show call", exact: true });
    assert.equal(await show.getAttribute("aria-expanded"), "false");
    assert.equal(await call.locator("video").count(), 0, "The folded dock shows no video");
    const ids = await remoteTrackIds(page);
    assert.deepEqual(await playingAudio(page), [ids.audio], "Audio continues while folded");
    assert.ok((await call.boundingBox()).height < 80, "Folded to one row");
    await shown(call.getByRole("button", { name: "Leave session", exact: true }));
    await shown(call.getByRole("link", { name: "Return to session", exact: true }));

    // The Intake form stays usable, and its save button is not covered by the dock.
    const answer = page.getByLabel(/How are you\? How are you coping with the challenges in college\?/);
    await answer.fill("Synthetic intake answer.");
    await page.getByRole("button", { name: "Save progress", exact: true }).tap();
    await page.waitForFunction(() => true);
    for (let attempt = 0; attempt < 40 && !session.state.intakeSaves.length; attempt++) await page.waitForTimeout(50);
    assert.equal(session.state.intakeSaves.length, 1);
    await noHorizontalOverflow(page);
    await screenshot(page, "student-intake-folded-dock");
    await call.getByRole("link", { name: "Return to session", exact: true }).tap();
    await page.waitForURL(new RegExp(`/portal/e-counseling/${appointmentId}$`));
    await hidden(call);
    assert.equal(await fakeCount(page, "join"), 1);
  });
}

{
  const session = liveSession({ student: true, consent: "NOT_REQUESTED" });
  await check("student-pending-consent-cue", ePath, { role: "STUDENT", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, COUNSELOR);
    await openRoutineFromSession(page);
    const call = dock(page);
    await shown(call);
    session.state.consent = "PENDING";
    await fake(page, "providerEvent", "recording-started");
    await shown(call.getByText("Media permission requested", { exact: true }));
    assert.equal(await call.getByRole("button", { name: /Allow|Decline/ }).count(), 0, "Decisions stay on the session page");
    await call.getByRole("link", { name: "Review", exact: true }).click();
    await page.waitForURL(new RegExp(`/portal/e-counseling/${appointmentId}$`));
    await shown(page.getByRole("heading", { name: "Media permissions", exact: true }));
    await hidden(call);
    await screenshot(page, "student-consent-review");
  });
}

{
  const session = liveSession();
  await check("another-appointment-keeps-active-call", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await openRoutineFromSession(page);
    // A client-side navigation to another Appointment's session page (a full load would end the call).
    await page.evaluate((path) => window.next.router.push(path), `/portal/e-counseling/${OTHER}`);
    await page.waitForURL(new RegExp(`/portal/e-counseling/${OTHER}$`));
    await shown(page.getByText("You’re already in another E-Counseling session.", { exact: true }));
    await shown(page.getByRole("link", { name: "Return to active session", exact: true }));
    assert.equal(await page.getByRole("button", { name: "Join session", exact: true }).count(), 0);
    await shown(dock(page));
    assert.equal(await fakeCount(page, "createCallObject"), 1);
    await page.getByRole("link", { name: "Return to active session", exact: true }).click();
    await page.waitForURL(new RegExp(`/portal/e-counseling/${appointmentId}$`));
    await hidden(dock(page));
  });
}

{
  const session = liveSession();
  await check("second-tab-blocked-and-released", ePath, { fakeDaily: true, overrides: session.overrides }, async (page, { context }) => {
    await joinCall(page);
    const second = await context.newPage();
    await second.addInitScript({ content: fakeDailyInitScript() });
    await second.addInitScript({ content: `
      window.__callChannel = [];
      const channel = new BroadcastChannel("compass-ecounseling-call");
      channel.addEventListener("message", (event) => window.__callChannel.push(event.data));
    ` });
    await second.goto(page.url());
    await shown(second.getByText("Another COMPASS tab has an active E-Counseling session.", { exact: true }));
    assert.equal(await second.getByRole("button", { name: "Join session", exact: true }).count(), 0);
    const messages = JSON.stringify(await second.evaluate(() => window.__callChannel));
    assert.doesNotMatch(messages, /token|room|appointment|Maria|https?:/i, "Only tab IDs and lease timing cross tabs");
    await stage(page).getByRole("group", { name: "Call controls" }).getByRole("button", { name: "Leave session", exact: true }).click();
    await shown(second.getByRole("button", { name: "Join session", exact: true }));
    await second.close();
  });
}

{
  const session = liveSession({ recording: "ACTIVE" });
  await check("sign-out-ends-call-after-confirmation", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await openRoutineFromSession(page);
    await page.getByRole("button", { name: /Account menu|Example User/ }).first().click();
    await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
    const confirm = page.getByRole("alertdialog", { name: "Sign out and end this call?", exact: true });
    assert.match(await confirm.innerText(), /Signing out ends your E-Counseling call\.[\s\S]*Recording is still[\s\S]*active\. Ending your call doesn’t confirm that it has stopped\./);
    await confirm.getByRole("button", { name: "Cancel", exact: true }).click();
    await shown(dock(page));
    assert.equal(await fakeCount(page, "destroy"), 0, "Cancelling keeps the call");
    await page.getByRole("button", { name: /Account menu|Example User/ }).first().click();
    await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL((url) => url.pathname === "/");
    assert.equal(await fakeCount(page, "destroy"), 1);
    assert.equal(session.state.logouts, 1);
    assert.equal(session.state.recording, "ACTIVE", "Signing out doesn’t claim capture stopped");
  });
}

{
  const session = liveSession();
  await check("confirmed-signed-out-ends-call", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await openRoutineFromSession(page);
    session.state.workspaceStatus = 401;
    session.state.sessionStatus = 401;
    await fake(page, "providerEvent", "recording-started");
    await page.waitForURL(/\/login/);
    assert.equal(await fakeCount(page, "destroy"), 1, "A session the server confirms is gone ends the call");
  });
}

{
  const session = liveSession();
  await check("unverified-session-keeps-call", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await openRoutineFromSession(page);
    session.state.workspaceStatus = 401;
    session.state.sessionStatus = 503;
    await fake(page, "providerEvent", "recording-started");
    await shown(page.getByRole("heading", { name: "We could not verify your session.", exact: true }));
    const call = dock(page);
    await shown(call);
    await call.getByRole("button", { name: "Microphone", exact: true }).click();
    assert.equal(await call.getByRole("button", { name: "Microphone", exact: true }).getAttribute("aria-pressed"), "false", "Local controls keep working");
    assert.equal(await fakeCount(page, "destroy"), 0, "A session that couldn’t be checked doesn’t end the call");
    session.state.workspaceStatus = 200;
    session.state.sessionStatus = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByLabel("Recommendations", { exact: true }));
    await shown(call);
    assert.equal(await fakeCount(page, "join"), 1);
    await screenshot(page, "unverified-session-recovered");
  });
}

{
  const session = liveSession();
  await check("maintenance-keeps-connected-call", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    session.state.maintenance = true;
    await fake(page, "providerEvent", "recording-started");
    await hidden(stage(page));
    const call = dock(page);
    await shown(call);
    await call.getByRole("button", { name: "Microphone", exact: true }).click();
    assert.equal(await call.getByRole("button", { name: "Microphone", exact: true }).getAttribute("aria-pressed"), "false");
    assert.equal(await fakeCount(page, "destroy"), 0);
    assert.equal(await page.getByRole("button", { name: /Join session|Start recording/ }).count(), 0, "No new join or capture start during maintenance");
    await screenshot(page, "maintenance-with-dock");
    await call.getByRole("button", { name: "Leave session", exact: true }).click();
    await hidden(call);
    assert.equal(await fakeCount(page, "destroy"), 1);
  });
}

{
  const session = liveSession();
  await check("call-ended-elsewhere-notice", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await openRoutineFromSession(page);
    await shown(dock(page));
    await fake(page, "fatal", "exp-token");
    await hidden(dock(page));
    const ended = page.getByRole("region", { name: "E-Counseling call ended" });
    await shown(ended.getByText(/join link expired/));
    await ended.getByRole("button", { name: "Dismiss", exact: true }).click();
    await hidden(ended);
  });
}

{
  const session = liveSession();
  await check("reload-warns-while-in-call", ePath, { fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    const dialog = page.waitForEvent("dialog");
    await page.close({ runBeforeUnload: true });
    const prompt = await dialog;
    assert.equal(prompt.type(), "beforeunload");
    await prompt.dismiss();
  });
}

for (const device of ["desktop", "laptop", "tablet", "narrowPhone"]) {
  const session = liveSession();
  await check(`dock-layout-${device}`, ePath, { device, fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await openRoutineFromSession(page);
    const call = dock(page);
    await shown(call);
    const box = await call.boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.x >= 0 && box.x + box.width <= viewport.width + 1, "The dock fits the screen");
    await noHorizontalOverflow(page);
    // The page can scroll its last action clear of the dock.
    const save = page.getByRole("button", { name: "Save evaluation", exact: true });
    await save.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    const saveBox = await save.boundingBox();
    const dockBox = await call.boundingBox();
    assert.ok(saveBox.y + saveBox.height <= dockBox.y || saveBox.x + saveBox.width <= dockBox.x, "The dock does not cover the form's save action");
    await screenshot(page, `dock-${device}`);
  });
}

await finish();
