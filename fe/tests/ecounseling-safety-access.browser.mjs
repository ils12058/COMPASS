// Slice 1A behavior in the real workspace/runtime. Every request and call uses synthetic fixtures.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { workspace, consents } from "./support/ui-hierarchy-fixtures.mjs";
import { appointmentId, counselingOverview } from "./support/guidance-contextual-fixtures.mjs";
import { COUNSELOR, STUDENT, createMessagesBackend, messagesAccount, sessionFor, threadIds } from "./support/guidance-messages-fixtures.mjs";

const { check, shown, hidden, finish, screenshot } = await createBrowserHarness("ecounseling-safety-access");
const ePath = `/portal/e-counseling/${appointmentId}`;
const ROUTINE = "routine-slice1a";
const THREAD = threadIds.counseling;
const privateMessage = "Private synthetic counseling message";
const stage = (page) => page.getByRole("region", { name: "Video call" });
const dock = (page) => page.getByRole("region", { name: "Active E-Counseling call" });
const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
const count = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const leaveDialog = (page) => page.getByRole("alertdialog", { name: "Leave this session?", exact: true });

async function eventually(condition, message) {
  const deadline = Date.now() + 12_000;
  while (!(await condition())) {
    if (Date.now() > deadline) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
}

function world(role = "COUNSELOR", states = {}) {
  const student = role === "STUDENT";
  const state = { recording: "NOT_STARTED", transcription: "NOT_STARTED", artifact: null, workspaceStatus: 200, contextStatus: 200, sessionStatus: 200, linkStatus: 200, joins: 0, logouts: 0, holdContext: false, heldContext: [], holdCredential: false, heldCredentials: [], holdLink: false, heldLinks: [], ...states };
  const account = messagesAccount(role, { id: student ? STUDENT.id : COUNSELOR.id });
  account.capabilities.push(...(student ? ["routine_interviews.view_self", "routine_interviews.manage_self"] : ["routine_interviews.view_assigned", "routine_interviews.manage_assigned"]));
  const backend = createMessagesBackend({ viewerId: account.id, viewerRole: role });
  backend.addThread({ id: THREAD, kind: "COUNSELING", counselor: COUNSELOR, appointment: appointmentId });
  backend.addMessage(THREAD, COUNSELOR, privateMessage);
  const prefix = `/api/v1/e-counseling/${student ? "me/" : ""}appointments/${appointmentId}`;
  const data = () => {
    const value = workspace(); value.appointment.id = appointmentId;
    value.student.display_name = "Protected Student Fixture";
    value.counselor.display_name = "Protected Counselor Fixture";
    value.media.media_policy_version = 2;
    value.media.recording.capture_status = state.recording;
    value.media.transcription.capture_status = state.transcription;
    value.media.recording.artifact_status = state.artifact;
    value.media.recording.artifact_available = state.artifact === "STORED";
    value.counseling_context_available = true;
    value.routine_interview = { id: ROUTINE, intake_status: student ? "DRAFT" : "SUBMITTED", evaluation_status: "DRAFT" };
    return value;
  };
  const failure = (reply, status) => reply({ error: { code: status === 401 ? "authentication_required" : "permission_denied", message: "Private synthetic refusal detail" } }, status);
  const handler = async (args) => {
    const { pathname, method, reply, route } = args;
    if (pathname === "/api/v1/auth/session") { await (state.sessionStatus === 200 ? reply(sessionFor(account)) : failure(reply, state.sessionStatus)); return true; }
    if (pathname === prefix) {
      if (state.workspaceStatus === "timeout") await route.abort("timedout");
      else await (state.workspaceStatus === 200 ? reply(data()) : failure(reply, state.workspaceStatus));
      return true;
    }
    if (pathname === `${prefix}/consents`) { await reply({ items: [{ ...consents("APPROVED")[0], scope: "SESSION_MEDIA_CAPTURE" }] }); return true; }
    if (pathname === `/api/v1/e-counseling/appointments/${appointmentId}/join`) {
      state.joins++;
      const credential = { appointment_id: appointmentId, workspace_id: "synthetic", provider: "DAILY", room_url: "https://synthetic.daily.co/room", meeting_token: "synthetic-credential", token_expires_at: new Date(Date.now() + 900_000).toISOString() };
      if (state.holdCredential) await new Promise((resolve) => state.heldCredentials.push(() => resolve(reply(credential).catch(() => {}))));
      else await reply(credential);
      return true;
    }
    if (pathname === `/api/v1/counseling/context/APPOINTMENT/${appointmentId}`) {
      if (state.contextStatus !== 200) { await failure(reply, state.contextStatus); return true; }
      const context = counselingOverview({ anchorId: appointmentId }); context.student.display_name = "Protected Context Fixture";
      if (state.holdContext) await new Promise((resolve) => state.heldContext.push(() => resolve(reply(context).catch(() => {}))));
      else await reply(context);
      return true;
    }
    if (pathname === `/api/v1/e-counseling/appointments/${appointmentId}/media/RECORDING/access`) {
      if (state.linkStatus !== 200) await failure(reply, state.linkStatus);
      else if (state.holdLink) await new Promise((resolve) => state.heldLinks.push(() => resolve(reply({ url: "http://127.0.0.1:3114/synthetic-blocked-artifact" }).catch(() => {}))));
      else await reply({ url: "http://127.0.0.1:3114/synthetic-blocked-artifact" });
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${ROUTINE}`) {
      await reply({ id: ROUTINE, appointment: { id: appointmentId, reference_code: "SYNTHETIC-PRIVATE", starts_at: "2026-10-13T02:00:00Z", ends_at: "2026-10-13T03:00:00Z" }, student: { id: STUDENT.id, display_name: "Protected Routine Fixture" }, workflow_state: "ACTIVE", intake_status: "SUBMITTED", intake: {}, evaluation_status: "DRAFT", evaluation: {}, counseling_context_available: false, delivery_mode: "ONLINE", entry_mode: "APPOINTMENT", created_at: "2026-10-13T00:00:00Z", form_revision: null, counseling_encounter: null });
      return true;
    }
    if (method === "POST" && pathname === "/api/v1/auth/logout") { state.logouts++; await reply({}); return true; }
    return backend.handler(args);
  };
  return { state, options: { role, fakeDaily: true, handler }, backend };
}

async function join(page, role = "COUNSELOR") {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for Protected ${role === "STUDENT" ? "Counselor" : "Student"} Fixture…`, { exact: true }).first());
}
async function refresh(page) { await fake(page, "providerEvent", "recording-stopped"); }
async function signOutMenu(page) {
  await page.getByRole("button", { name: /Open user menu/ }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
}
async function assertNoProviderCommands(page, requests) {
  for (const method of ["startRecording", "stopRecording", "startTranscription", "stopTranscription"]) assert.equal(await count(page, method), 0);
  assert.equal(requests.filter((request) => /\/(recording|transcription)\/(start|stop)$/.test(request.pathname)).length, 0, "Cleanup never issues backend capture commands");
}

for (const role of ["COUNSELOR", "STUDENT"]) for (const kind of ["recording", "transcription"]) for (const status of ["ACTIVE", "START_REQUESTED", "STOP_REQUESTED", "ERROR"]) {
  const w = world(role, { [kind]: status });
  await check(`${role}-${kind}-${status}-leave-safety`, ePath, w.options, async (page, { requests }) => {
    await join(page, role);
    const indicator = stage(page).getByRole("list", { name: "Session capture" });
    await shown(indicator);
    assert.match((await indicator.innerText()).toLowerCase(), new RegExp(kind));
    if (status === "ERROR") assert.match(await indicator.innerText(), /status uncertain/);
    if (status === "START_REQUESTED") assert.match(await indicator.innerText(), /starting/);
    if (status === "STOP_REQUESTED") assert.match(await indicator.innerText(), /stopping/);
    await stage(page).getByRole("button", { name: "Leave session", exact: true }).click();
    const dialog = leaveDialog(page); await shown(dialog);
    const text = await dialog.innerText();
    assert.match(text.toLowerCase(), new RegExp(`${kind} has not been confirmed as stopped`));
    assert.match(text, /Leaving the call may not stop/);
    assert.doesNotMatch(text, /START_REQUESTED|STOP_REQUESTED|HTTP|webhook|provider|still active/);
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click(); await hidden(dialog);
    assert.equal(await count(page, "destroy"), 0, "Cancel preserves the call");
    await stage(page).getByRole("button", { name: "Leave session", exact: true }).click();
    await leaveDialog(page).getByRole("button", { name: "Leave session", exact: true }).click();
    await eventually(async () => await count(page, "destroy") === 1, "Existing cleanup destroys the local call");
    assert.equal(w.state[kind], status, "Local Leave does not establish capture cessation");
    await assertNoProviderCommands(page, requests);
  });
}

for (const role of ["COUNSELOR", "STUDENT"]) {
  const w = world(role, { recording: "STOP_REQUESTED", transcription: "ERROR" });
  await check(`${role}-both-unresolved-sign-out`, ePath, w.options, async (page, { requests }) => {
    await join(page, role); await signOutMenu(page);
    const dialog = page.getByRole("alertdialog", { name: "Sign out and end this call?" });
    await shown(dialog);
    assert.match(await dialog.innerText(), /Recording and transcription have not been confirmed as stopped/);
    assert.match(await dialog.innerText(), /Signing out may not stop recording or transcription/);
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    assert.equal(await count(page, "destroy"), 0);
    await signOutMenu(page); await page.getByRole("alertdialog").getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL((url) => url.pathname === "/");
    assert.equal(await count(page, "destroy"), 1); assert.equal(w.state.logouts, 1);
    await assertNoProviderCommands(page, requests);
  });
}

for (const role of ["COUNSELOR", "STUDENT"]) for (const status of ["NOT_STARTED", "READY"]) {
  const w = world(role, { recording: status, transcription: status });
  await check(`${role}-${status}-leave-without-warning`, ePath, w.options, async (page) => {
    await join(page, role); await stage(page).getByRole("button", { name: "Leave session", exact: true }).click();
    await eventually(async () => await count(page, "destroy") === 1, "Terminal capture uses ordinary cleanup");
    assert.equal(await leaveDialog(page).count(), 0);
  });
}

for (const role of ["COUNSELOR", "STUDENT"]) {
  const w = world(role, { transcription: "STOPPED" });
  await check(`${role}-legacy-transcription-stop-is-uncertain`, ePath, w.options, async (page) => {
    await join(page, role); await shown(stage(page).getByText("Transcription stop not confirmed", { exact: true }));
    await stage(page).getByRole("button", { name: "Leave session", exact: true }).click();
    await shown(leaveDialog(page)); assert.match(await leaveDialog(page).innerText(), /Transcription has not been confirmed as stopped/);
  });
}

for (const role of ["COUNSELOR", "STUDENT"]) for (const failure of [503, "timeout"]) {
  const w = world(role, { recording: "STOP_REQUESTED" });
  await check(`${role}-${failure}-preserves-call-and-warning`, ePath, w.options, async (page) => {
    await join(page, role); w.state.workspaceStatus = failure; await refresh(page);
    await shown(page.getByText("Latest information could not be refreshed. Showing the last confirmed result.", { exact: true }));
    await shown(stage(page).getByText("Recording stopping…", { exact: true }));
    assert.equal(await count(page, "destroy"), 0);
    await stage(page).getByRole("button", { name: "Microphone", exact: true }).click();
    assert.equal(await stage(page).getByRole("button", { name: "Microphone", exact: true }).getAttribute("aria-pressed"), "false");
    await stage(page).getByRole("button", { name: "Leave session", exact: true }).click(); await shown(leaveDialog(page));
    assert.match(await leaveDialog(page).innerText(), /Recording has not been confirmed as stopped/);
    await leaveDialog(page).getByRole("button", { name: "Cancel", exact: true }).click();
    w.state.workspaceStatus = 200; await page.getByRole("button", { name: "Retry", exact: true }).first().click();
    await hidden(page.getByText("Latest information could not be refreshed. Showing the last confirmed result.", { exact: true }));
    assert.equal(await count(page, "join"), 1);
  });
}

for (const role of ["COUNSELOR", "STUDENT"]) {
  const w = world(role, { recording: "STOP_REQUESTED", transcription: "ERROR" });
  await check(`${role}-403-conceals-dependent-views-and-allows-fresh-recovery`, ePath, w.options, async (page, { requests }) => {
    await join(page, role); await fake(page, "remoteJoin", { userId: "synthetic-remote", name: "Fixture" });
    await page.getByRole("button", { name: /^Messages/ }).click();
    await shown(page.getByText(privateMessage, { exact: true }));
    w.state.workspaceStatus = 403; await refresh(page);
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    await eventually(async () => await count(page, "destroy") === 1, "403 destroys the local Daily object");
    for (const name of ["Protected Student Fixture", "Protected Counselor Fixture", "Protected Context Fixture", privateMessage]) assert.equal(await page.getByText(name, { exact: true }).count(), 0, name);
    assert.equal(await page.getByRole("button", { name: /Join session|Start recording|Record encounter|Send/ }).count(), 0);
    assert.equal(await dock(page).count(), 0);
    await page.waitForFunction(() => [...document.querySelectorAll("video,audio")].every((element) => element.srcObject === null));
    assert.equal(await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.liveListenerCount()), 0);
    assert.equal(w.state.sessionStatus, 200, "Account remains authenticated");
    assert.equal(w.state.joins, 1, "No new credential after denial");
    await shown(page.getByText(/Recording and transcription have not been confirmed as stopped/));
    await assertNoProviderCommands(page, requests);
    await screenshot(page, `${role.toLowerCase()}-resource-unavailable`);
    w.state.workspaceStatus = 503; await page.getByRole("button", { name: "Retry", exact: true }).first().click();
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    assert.equal(await page.getByText(privateMessage, { exact: true }).count(), 0, "A transient retry cannot resurrect content");
    w.state.workspaceStatus = 200; await page.getByRole("button", { name: "Retry", exact: true }).first().click();
    await shown(page.getByRole("heading", { name: role === "STUDENT" ? "Protected Counselor Fixture" : "Protected Student Fixture", exact: true }));
    assert.equal(await count(page, "join"), 1, "Recovery never rejoins automatically");
    await join(page, role); assert.equal(w.state.joins, 2, "Deliberate authorized rejoin gets a fresh credential");
  });
}

{
  const w = world("COUNSELOR", { recording: "ERROR" });
  await check("off-route-denial-removes-Routine-and-dock-context", ePath, w.options, async (page, { requests }) => {
    await join(page); await page.getByRole("button", { name: /^Session details/ }).click();
    await page.getByRole("link", { name: "Open Routine Interview", exact: true }).click();
    await shown(page.getByText("Protected Routine Fixture", { exact: true })); await shown(dock(page));
    w.state.workspaceStatus = 403; await refresh(page);
    await eventually(async () => await count(page, "destroy") === 1, "Off-route resource denial cleans up");
    assert.equal(await page.getByText("Protected Routine Fixture", { exact: true }).count(), 0);
    assert.equal(await dock(page).count(), 0);
    assert.equal(await page.getByLabel("Recommendations", { exact: true }).count(), 0);
    await shown(page.getByText(/Recording has not been confirmed as stopped/));
    await assertNoProviderCommands(page, requests);
    await page.getByRole("region", { name: "E-Counseling call ended" }).getByRole("link", { name: "Return to session", exact: true }).click();
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    assert.equal(w.state.joins, 1);
  });
}

{
  const w = world("COUNSELOR", { holdContext: true });
  await check("delayed-Student-information-cannot-resurrect-denied-workspace", ePath, w.options, async (page) => {
    await join(page); await eventually(() => w.state.heldContext.length > 0, "Context request is pending");
    w.state.workspaceStatus = 403; await refresh(page);
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    for (const release of w.state.heldContext.splice(0)) await release();
    await page.waitForTimeout(200);
    assert.equal(await page.getByText("Protected Context Fixture", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("region", { name: "Student Counseling context" }).count(), 0);
    assert.equal(await count(page, "destroy"), 1);
  });
}

{
  const w = world("COUNSELOR", { holdCredential: true });
  await check("denial-during-credential-fetch-drops-late-credential", ePath, w.options, async (page, { requests }) => {
    await page.getByRole("button", { name: "Join session", exact: true }).click();
    await eventually(() => w.state.heldCredentials.length > 0, "Credential request is pending");
    w.state.workspaceStatus = 403;
    // The runtime's existing poll reads the canonical workspace while the credential is pending.
    await eventually(() => requests.filter((request) => request.pathname === `/api/v1/e-counseling/appointments/${appointmentId}`).length > 1, "Runtime rereads the canonical workspace");
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    for (const release of w.state.heldCredentials.splice(0)) await release();
    await page.waitForTimeout(200);
    assert.equal(await count(page, "createCallObject"), 0); assert.equal(await count(page, "join"), 0);
    assert.equal(w.state.joins, 1);
  });
}

{
  const w = world();
  await check("401-uses-confirmed-session-loss-cleanup", ePath, w.options, async (page) => {
    await join(page); w.state.workspaceStatus = 401; w.state.sessionStatus = 401; await refresh(page);
    await page.waitForURL(/\/login/); assert.equal(await count(page, "destroy"), 1);
    assert.equal(await page.getByText("Protected Student Fixture", { exact: true }).count(), 0);
  });
}

{
  const w = world();
  await check("Student-information-403-hides-cached-context-without-revoking-independent-call", ePath, w.options, async (page) => {
    await page.clock.install();
    await join(page);
    const disclosure = page.getByRole("button", { name: /^Student information/ });
    if (await disclosure.getAttribute("aria-expanded") === "false") await disclosure.click();
    await shown(page.getByText("Protected Context Fixture", { exact: true }));
    w.state.contextStatus = 403;
    await page.clock.fastForward(31_000);
    // A normal portal navigation remounts the information query and rechecks its stale result.
    await page.evaluate(() => window.next.router.push("/portal/appointments"));
    await shown(dock(page));
    await dock(page).getByRole("link", { name: "Return to session", exact: true }).click();
    const reloadedDisclosure = page.getByRole("button", { name: /^Student information/ });
    if (await reloadedDisclosure.getAttribute("aria-expanded") === "false") await reloadedDisclosure.click();
    await shown(page.getByText("Student information couldn’t be loaded. Try again.", { exact: true }));
    assert.equal(await page.getByText("Protected Context Fixture", { exact: true }).count(), 0);
    assert.equal(await count(page, "destroy"), 0, "Context denial alone does not revoke the independently authorized call");
  });
}

{
  const w = world("COUNSELOR", { recording: "READY", artifact: "STORED", linkStatus: 403 });
  await check("imperative-file-link-403-conceals-workspace-and-closes-call", ePath, w.options, async (page) => {
    await join(page);
    const files = page.getByRole("button", { name: /^Session files/ });
    if (await files.getAttribute("aria-expanded") === "false") await files.click();
    await page.getByRole("button", { name: "Download recording", exact: true }).click();
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    await eventually(async () => await count(page, "destroy") === 1, "File access denial closes the local call");
    assert.equal(await page.getByRole("button", { name: "Download recording", exact: true }).count(), 0);
  });
}

{
  const w = world("COUNSELOR", { recording: "READY", artifact: "STORED", linkStatus: 401 });
  await check("imperative-file-link-401-follows-session-loss-flow", ePath, w.options, async (page) => {
    await join(page); w.state.sessionStatus = 401;
    const files = page.getByRole("button", { name: /^Session files/ });
    if (await files.getAttribute("aria-expanded") === "false") await files.click();
    await page.getByRole("button", { name: "Download recording", exact: true }).click();
    await page.waitForURL(/\/login/);
    assert.equal(await count(page, "destroy"), 1);
    assert.equal(await page.getByText("Protected Student Fixture", { exact: true }).count(), 0);
  });
}

{
  const w = world("COUNSELOR", { recording: "READY", artifact: "STORED", holdLink: true });
  let openedLinks = 0;
  w.options.beforeNavigate = async ({ context }) => {
    await context.route(/\/synthetic-blocked-artifact$/, (route) => { openedLinks++; return route.abort(); });
  };
  await check("late-file-link-is-never-opened-after-denial", ePath, w.options, async (page, { context }) => {
    await join(page);
    const files = page.getByRole("button", { name: /^Session files/ });
    if (await files.getAttribute("aria-expanded") === "false") await files.click();
    await page.getByRole("button", { name: "Download recording", exact: true }).click();
    await eventually(() => w.state.heldLinks.length > 0, "File-link request is pending");
    w.state.workspaceStatus = 403; await refresh(page);
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    for (const release of w.state.heldLinks.splice(0)) await release();
    await page.waitForTimeout(200);
    assert.equal(openedLinks, 0); assert.equal(context.pages().length, 1, "No new protected file surface");
  });
}

await finish();
