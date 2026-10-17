// RT-1B uses only synthetic HTTP/socket/provider fixtures on a loopback Next server.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { baseURL, check, openPage, shown, hidden, finish } = await createBrowserHarness("ecounseling-media-realtime");
const ID = "b0000000-0000-4000-8000-000000000001";
const OTHER = "b0000000-0000-4000-8000-000000000002";
const CONSENT = "d0000000-0000-4000-8000-000000000001";
const PATH = `/portal/e-counseling/${ID}`;
const enable = `window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(`${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`)} };`;
const stage = (page) => page.getByRole("region", { name: "Video call" });
const dock = (page) => page.getByRole("region", { name: "Active E-Counseling call" });

async function eventually(condition, message) {
  const deadline = Date.now() + 12_000;
  while (!(await condition())) {
    if (Date.now() > deadline) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
}

function world({ recording = "NOT_STARTED", transcription = "NOT_STARTED", realtime = true, outage = false, startFailure = false, stopFailure = false } = {}) {
  const state = { recording, transcription, artifact: null, available: false, disposed: false, withdrawn: false, failure: false, denied: false, hold: false, holdConsent: false, held: [], heldConsent: [], sockets: [], reads: [], commands: [] };
  const row = () => ({ id: CONSENT, scope: "SESSION_MEDIA_CAPTURE", decision: "APPROVED", effective: !state.withdrawn, requested_at: "2026-10-14T00:00:00Z", decided_at: "2026-10-14T00:01:00Z", withdrawn_at: state.withdrawn ? "2026-10-14T00:02:00Z" : null });
  const send = (id = ID, type = "ecounseling.media.changed") => {
    for (const socket of state.sockets.filter((socket) => !socket.closed)) socket.route.send(JSON.stringify({ v: 1, type, appointment_id: id }));
  };
  const release = () => { state.hold = false; state.holdConsent = false; for (const complete of [...state.held.splice(0), ...state.heldConsent.splice(0)]) complete(); };
  const options = (role) => ({
    role, fakeDaily: true, initScripts: realtime ? [enable] : [],
    beforeNavigate: async ({ context }) => {
      await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
        const socket = { role, route, closed: false }; state.sockets.push(socket);
        route.onMessage((message) => {
          assert.equal(JSON.parse(String(message)).type, "authenticate");
          if (outage) route.close({ code: 1013, reason: "synthetic outage" });
          else route.send('{"v":1,"type":"ready"}');
        });
        route.onClose(() => { socket.closed = true; });
      });
    },
    handler: async ({ method, pathname, reply }) => {
      const own = `/api/v1/e-counseling/${role === "STUDENT" ? "me/" : ""}appointments/${ID}`;
      if (pathname === "/api/v1/realtime/tickets") { await reply({ ticket: "synthetic-ticket", expires_in_seconds: 30, user_id: user(role).id }); return true; }
      if (method === "GET" && pathname === own) {
        state.reads.push({ role, kind: "workspace" });
        const value = workspace(); value.appointment = { ...value.appointment, id: ID };
        value.student.display_name = "Media Test Student"; value.counselor.display_name = "Media Test Counselor";
        value.media.media_policy_version = 2;
        value.media.recording.consent_status = state.withdrawn ? "WITHDRAWN" : "APPROVED";
        value.media.transcription.consent_status = state.withdrawn ? "WITHDRAWN" : "APPROVED";
        value.media.recording.capture_status = state.recording; value.media.transcription.capture_status = state.transcription;
        value.media.recording.artifact_status = state.artifact; value.media.recording.artifact_available = state.available;
        value.media.recording.artifact_disposed_at = state.disposed ? "2026-10-14T00:03:00Z" : null;
        if (state.hold && role === "COUNSELOR") await new Promise((resolve) => state.held.push(resolve));
        if (state.denied && role === "COUNSELOR") await reply({ error: { code: "ecounseling_not_permitted", message: "Synthetic refusal" } }, 403);
        else if (state.failure && role === "COUNSELOR") await reply({ error: { code: "synthetic_unavailable", message: "Synthetic read failure" } }, 503);
        else await reply(value);
        return true;
      }
      if (method === "GET" && pathname === `${own}/consents`) {
        state.reads.push({ role, kind: "consents" });
        const value = row();
        if (state.holdConsent && role === "COUNSELOR") await new Promise((resolve) => state.heldConsent.push(resolve));
        await reply({ items: [value] }); return true;
      }
      if (method === "POST" && pathname.endsWith(`/${ID}/join`)) {
        await reply({ appointment_id: ID, workspace_id: "synthetic", provider: "DAILY", room_url: "https://synthetic.daily.co/room", meeting_token: "synthetic", token_expires_at: new Date(Date.now()+900_000).toISOString() }); return true;
      }
      if (method === "POST" && /\/(recording|transcription)\/(start|stop)$/.test(pathname)) {
        state.commands.push(pathname);
        const kind = pathname.includes("/recording/") ? "recording" : "transcription";
        const starting = pathname.endsWith("/start");
        const next = starting ? (startFailure ? "ERROR" : "START_REQUESTED") : "STOP_REQUESTED";
        const changed = state[kind] !== next; state[kind] = next;
        if (changed) send();
        if (starting ? startFailure : stopFailure) await reply({ error: { code: "ecounseling_provider_unavailable", message: "Synthetic provider uncertainty" } }, 503);
        else await reply({ id: "synthetic-capture", status: state[kind] });
        return true;
      }
      return false;
    },
  });
  return { state, send, release, options };
}

async function join(page, role = "COUNSELOR") {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for Media Test ${role === "COUNSELOR" ? "Student" : "Counselor"}…`, { exact: true }));
}
async function startRecording(page) {
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await page.getByRole("alertdialog", { name: "Start recording?", exact: true }).getByRole("button", { name: "Start recording", exact: true }).click();
}
async function openSection(page, label) {
  const button = page.getByRole("button", { name: new RegExp(`^${label}`) });
  if ((await button.getAttribute("aria-expanded")) === "false") await button.click();
}

{
  const w = world();
  await check("in-flight old workspace cannot reopen Start before a trailing authoritative media read", PATH, w.options("COUNSELOR"), async (page) => {
    try {
      await join(page); w.state.hold = true; w.send();
      await eventually(() => w.state.held.length > 0, "Canonical workspace read held");
      w.state.recording = "ACTIVE"; w.send();
      assert.equal(await page.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true);
      w.release(); await shown(stage(page).getByText("Recording", { exact: true }));
      assert.equal(await page.getByRole("button", { name: "Stop recording", exact: true }).isEnabled(), true);
      assert.equal(w.state.commands.length, 0);
    } finally { w.release(); }
  });
}

{
  const w = world();
  await check("two sessions observe Start, Active, Stop, Completed and verified institutional availability", PATH, w.options("COUNSELOR"), async (counselor) => {
    const student = await openPage(PATH, w.options("STUDENT"));
    try {
      await join(counselor); await join(student.page, "STUDENT");
      assert.equal(w.state.commands.length, 0, "Approval never starts capture");
      await startRecording(counselor);
      await shown(stage(student.page).getByText("Recording starting…", { exact: true }));
      assert.equal(w.state.recording, "START_REQUESTED", "Accepted Start cannot invent ACTIVE");
      w.state.recording = "ACTIVE"; w.send();
      await shown(stage(student.page).getByText("Recording", { exact: true }));
      await counselor.getByRole("button", { name: "Stop recording", exact: true }).click();
      await shown(stage(student.page).getByText("Recording stopping…", { exact: true }));
      assert.equal(w.state.recording, "STOP_REQUESTED");
      w.state.recording = "READY"; w.state.artifact = "PENDING"; w.send();
      await openSection(student.page, "Session details");
      await shown(student.page.getByRole("region", { name: /Session details/ }).getByText("Completed", { exact: true }));
      await openSection(counselor, "Session files");
      await shown(counselor.getByText("Preparing file…", { exact: true }));
      await hidden(counselor.getByRole("button", { name: "Download recording", exact: true }));
      w.state.artifact = "PROCESSING"; w.send();
      await shown(counselor.getByText("Preparing file…", { exact: true }));
      w.state.artifact = "STORED"; w.state.available = true; w.send();
      await shown(counselor.getByRole("button", { name: "Download recording", exact: true }));
      assert.equal(await student.page.getByRole("button", { name: "Download recording", exact: true }).count(), 0);
      assert.equal(w.state.commands.length, 2, "Only the explicit Start and Stop reached HTTP");
      for (const role of ["STUDENT", "COUNSELOR"]) assert.equal(w.state.sockets.filter((socket) => socket.role === role && !socket.closed).length, 1);
      assert.deepEqual(student.errors, []);
    } finally { w.release(); await student.context.close(); }
  });
}

{
  const w = world({ startFailure: true });
  await check("committed Start failure becomes uncertain without a false Active indication", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); await startRecording(page);
    await shown(stage(page).getByText("Recording status uncertain", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "Recording status uncertain", exact: true }).isDisabled(), true);
    assert.equal(w.state.commands.length, 1);
  });
}

{
  const w = world({ recording: "ACTIVE", stopFailure: true });
  await check("provider Stop failure is shown as not confirmed, keeps Stop intent and never claims completion", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); await page.getByRole("button", { name: "Stop recording", exact: true }).click();
    await shown(stage(page).getByText("Recording stopping…", { exact: true }));
    // The failed request is not presented as progress: the control says so and can be sent again.
    const retry = page.getByRole("button", { name: "Recording stop not confirmed. Stop recording again", exact: true });
    await shown(retry);
    assert.equal(await retry.isDisabled(), false);
    assert.equal(await stage(page).getByRole("button", { name: "Stopping…", exact: true }).count(), 0);
    assert.equal(w.state.commands.length, 1, "A failed Stop is never repeated automatically");
    // The dock's own Stop has sent nothing, so it shows only COMPASS's recorded Stop intent.
    await page.getByRole("link", { name: "Services", exact: true }).first().click();
    await shown(dock(page));
    assert.equal(await dock(page).getByRole("button", { name: "Stopping…", exact: true }).isDisabled(), true);
    assert.equal(w.state.recording, "STOP_REQUESTED");
    assert.equal(await page.getByText("Recording stopped", { exact: true }).count(), 0);
  });
}

{
  const w = world({ transcription: "ACTIVE" });
  await check("media hint closes stale Start confirmation and failed workspace read cannot authorize Start", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); await page.getByRole("button", { name: "Start recording", exact: true }).click();
    const dialog = page.getByRole("alertdialog", { name: "Start recording?", exact: true }); await shown(dialog);
    w.state.failure = true; w.send(); await hidden(dialog);
    await eventually(() => page.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), "Start stays unavailable");
    await eventually(() => page.getByRole("button", { name: "Stop transcription", exact: true }).isEnabled(), "Consent/workspace uncertainty cannot remove Stop");
    assert.equal(w.state.commands.length, 0);
  });
}

{
  const w = world();
  await check("media hint cannot bypass a pending consent reconciliation or restore withdrawal", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); w.state.holdConsent = true; w.send(ID, "ecounseling.consent.changed");
    await eventually(() => w.state.heldConsent.length > 0, "Consent reconciliation is pending");
    w.state.withdrawn = true; w.send();
    assert.equal(await page.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true);
    w.release(); w.send(ID, "ecounseling.consent.changed");
    await shown(page.getByRole("list", { name: "Media permission", exact: true }).getByText("Media permission withdrawn", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true);
    assert.equal(w.state.commands.length, 0);
  });
}

for (const boundary of ["hidden", "offline"]) {
  const w = world();
  await check(`${boundary} media hints wait for foreground recovery without background HTTP`, PATH, w.options("STUDENT"), async (page) => {
    await join(page, "STUDENT"); await page.waitForTimeout(100);
    await page.evaluate((boundary) => {
      if (boundary === "hidden") { Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" }); document.dispatchEvent(new Event("visibilitychange")); }
      else { Object.defineProperty(navigator, "onLine", { configurable: true, value: false }); window.dispatchEvent(new Event("offline")); }
    }, boundary);
    const before = w.state.reads.filter((read) => read.kind === "workspace").length;
    w.state.recording = "ACTIVE"; if (boundary === "hidden") w.send();
    await page.waitForTimeout(150);
    assert.equal(w.state.reads.filter((read) => read.kind === "workspace").length, before);
    await page.evaluate((boundary) => {
      if (boundary === "hidden") { Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" }); document.dispatchEvent(new Event("visibilitychange")); }
      else { Object.defineProperty(navigator, "onLine", { configurable: true, value: true }); window.dispatchEvent(new Event("online")); }
    }, boundary);
    await shown(stage(page).getByText("Recording", { exact: true }));
    assert.equal(w.state.commands.length, 0);
  });
}

for (const mode of ["disabled", "outage"]) {
  const w = world({ realtime: mode !== "disabled", outage: mode === "outage" });
  await check(`${mode} transport heals lost media through bounded workspace polling`, PATH, w.options("STUDENT"), async (page) => {
    await join(page, "STUDENT"); w.state.recording = "ACTIVE";
    await shown(stage(page).getByText("Recording", { exact: true }));
    assert.equal(w.state.commands.length, 0);
    if (mode === "disabled") assert.equal(w.state.sockets.length, 0);
  });
}

{
  const w = world();
  await check("initial ready and reconnect heal media missed between socket generations", PATH, w.options("STUDENT"), async (page) => {
    await join(page, "STUDENT"); await eventually(() => w.state.sockets.length === 1, "Shared socket connected");
    w.state.recording = "ACTIVE"; w.state.sockets[0].route.close({ code: 4000, reason: "synthetic reconnect" });
    await shown(stage(page).getByText("Recording", { exact: true }));
  });
}

{
  const w = world({ recording: "ACTIVE" });
  await check("media burst and page plus call share one workspace read; consent and other appointments untouched", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); await page.waitForTimeout(200);
    const before = w.state.reads.length; w.send(OTHER); await page.waitForTimeout(150);
    assert.equal(w.state.reads.length, before);
    for (let i = 0; i < 20; i++) w.send();
    await eventually(() => w.state.reads.length > before, "Workspace reconciliation runs");
    await page.waitForTimeout(100);
    const reads = w.state.reads.slice(before);
    assert.ok(reads.length <= 2); assert.ok(reads.every((read) => read.kind === "workspace"));
    assert.equal(w.state.sockets.filter((socket) => !socket.closed).length, 1);
  });
}

{
  const w = world({ recording: "ACTIVE" });
  await check("healthy active capture uses slower safety rather than duplicate 7-second page/call polls", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); await page.waitForTimeout(200);
    const before = w.state.reads.filter((read) => read.kind === "workspace").length;
    await page.waitForTimeout(7500);
    assert.equal(w.state.reads.filter((read) => read.kind === "workspace").length, before);
  });
}

{
  const w = world({ recording: "READY" }); w.state.artifact = "PROCESSING";
  await check("artifact failure, verified Stored and approved disposal have distinct download behavior", PATH, w.options("COUNSELOR"), async (page) => {
    await openSection(page, "Session files"); await shown(page.getByText("Preparing file…", { exact: true }));
    w.state.artifact = "FAILED"; w.send();
    await shown(page.getByText("The file isn't available right now. Preparation will be retried.", { exact: true }));
    await hidden(page.getByRole("button", { name: "Download recording", exact: true }));
    w.state.artifact = "STORED"; w.state.available = true; w.send();
    await shown(page.getByRole("button", { name: "Download recording", exact: true }));
    w.state.artifact = "DISPOSED"; w.state.available = false; w.state.disposed = true; w.send();
    await shown(page.getByText("Deleted under an approved retention rule.", { exact: true }));
    await hidden(page.getByRole("button", { name: "Download recording", exact: true }));
    assert.equal(w.state.commands.length, 0);
  });
}

{
  const w = world({ recording: "ACTIVE" });
  await check("persistent off-page call receives media state without another socket or join", PATH, w.options("COUNSELOR"), async (page, { requests }) => {
    await join(page); await page.getByRole("link", { name: "Services", exact: true }).first().click();
    await shown(dock(page)); w.state.recording = "STOP_REQUESTED"; w.send();
    await shown(dock(page).getByText("Recording stopping…", { exact: true }));
    assert.equal(requests.filter((request) => request.pathname.endsWith("/join")).length, 1);
    assert.equal(w.state.sockets.filter((socket) => !socket.closed).length, 1);
  });
}

{
  const w = world({ recording: "ACTIVE" });
  await check("403 canonical read conceals protected workspace and ends the existing call", PATH, w.options("COUNSELOR"), async (page) => {
    await join(page); w.state.denied = true; w.send();
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    assert.equal(await page.getByText("Media Test Student", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "Stop recording", exact: true }).count(), 0);
    await hidden(stage(page));
  });
}

await finish();
