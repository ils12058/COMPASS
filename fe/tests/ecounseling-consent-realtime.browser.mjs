// RT-1A: synthetic HTTP, shared portal socket and isolated Student/Counselor browser sessions.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { baseURL, check, openPage, shown, hidden, screenshot, finish } = await createBrowserHarness("ecounseling-consent-realtime");
const ID = "b0000000-0000-4000-8000-000000000001";
const OTHER = "b0000000-0000-4000-8000-000000000002";
const CONSENT = "d0000000-0000-4000-8000-000000000001";
const PATH = `/portal/e-counseling/${ID}`;
const enable = `window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(`${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`)} };`;
const subject = "recording & live transcription";

async function eventually(condition, message) {
  const deadline = Date.now() + 12_000;
  while (!(await condition())) {
    if (Date.now() > deadline) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
}

function world({ approved = false, recording = "NOT_STARTED", transcription = "NOT_STARTED", realtime = true, outage = false, withdrawalFailure = false } = {}) {
  const state = { row: approved ? row("APPROVED") : null, recording, transcription, failure: false, denied: false, hold: false, held: [], sockets: [], reads: [], commands: [] };
  function row(decision) { return { id: CONSENT, scope: "SESSION_MEDIA_CAPTURE", decision, effective: decision === "APPROVED", requested_at: "2026-10-14T00:00:00Z", decided_at: decision === "PENDING" ? null : "2026-10-14T00:01:00Z", withdrawn_at: null }; }
  const send = (id = ID) => {
    for (const socket of state.sockets.filter((socket) => !socket.closed)) socket.route.send(JSON.stringify({ v: 1, type: "ecounseling.consent.changed", appointment_id: id }));
  };
  const release = () => { state.hold = false; for (const complete of state.held.splice(0)) complete(); };
  const options = (role) => ({
    role, fakeDaily: true, initScripts: realtime ? [enable] : [],
    beforeNavigate: async ({ context }) => {
      await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
        const socket = { role, route, closed: false, ready: false }; state.sockets.push(socket);
        route.onMessage((message) => {
          assert.equal(JSON.parse(String(message)).type, "authenticate");
          if (outage) route.close({ code: 1013, reason: "synthetic outage" });
          else { socket.ready = true; route.send('{"v":1,"type":"ready"}'); }
        });
        route.onClose(() => { socket.closed = true; });
      });
    },
    handler: async ({ method, pathname, request, reply }) => {
      const own = `/api/v1/e-counseling/${role === "STUDENT" ? "me/" : ""}appointments/${ID}`;
      if (pathname === "/api/v1/realtime/tickets") {
        await reply({ ticket: "synthetic-ticket", expires_in_seconds: 30, user_id: user(role).id }); return true;
      }
      if (method === "GET" && pathname === own) {
        state.reads.push({ role, kind: "workspace" });
        if (state.denied && role === "COUNSELOR") { await reply({ error: { code: "ecounseling_not_permitted", message: "Synthetic refusal" } }, 403); return true; }
        const value = workspace(); value.appointment = { ...value.appointment, id: ID };
        value.student.display_name = "Consent Test Student"; value.counselor.display_name = "Consent Test Counselor";
        value.media.media_policy_version = 2;
        const consent = state.row?.withdrawn_at ? "WITHDRAWN" : state.row?.decision ?? "NOT_REQUESTED";
        value.media.recording.consent_status = consent; value.media.transcription.consent_status = consent;
        value.media.recording.capture_status = state.recording; value.media.transcription.capture_status = state.transcription;
        await reply(value); return true;
      }
      if (method === "GET" && pathname === `${own}/consents`) {
        state.reads.push({ role, kind: "consents" });
        if (state.hold && role === "COUNSELOR") await new Promise((resolve) => state.held.push(resolve));
        if (state.failure && role === "COUNSELOR") await reply({ error: { code: "synthetic_unavailable", message: "Synthetic read failure" } }, 503);
        else await reply({ items: state.row ? [state.row] : [] });
        return true;
      }
      if (method === "POST" && pathname === `/api/v1/e-counseling/appointments/${ID}/consents`) {
        state.row = row("PENDING"); send(); await reply({ items: [state.row] }); return true;
      }
      if (method === "POST" && pathname === `${own}/consents/${CONSENT}/decision`) {
        state.row = row(request.postDataJSON().decision); send(); await reply(state.row); return true;
      }
      if (method === "POST" && pathname === `${own}/consents/${CONSENT}/withdraw`) {
        state.row = { ...state.row, effective: false, withdrawn_at: "2026-10-14T00:02:00Z" };
        send();
        await (withdrawalFailure ? reply({ error: { code: "ecounseling_provider_unavailable", message: "Synthetic Stop timeout after committed withdrawal" } }, 503) : reply(state.row));
        return true;
      }
      if (method === "POST" && pathname === `/api/v1/e-counseling/appointments/${ID}/join`) {
        await reply({ appointment_id: ID, workspace_id: "synthetic", provider: "DAILY", room_url: "https://synthetic.daily.co/room", meeting_token: "synthetic", token_expires_at: new Date(Date.now() + 900_000).toISOString() }); return true;
      }
      if (method === "POST" && /\/(recording|transcription)\/(start|stop)$/.test(pathname)) {
        state.commands.push(pathname);
        if (pathname.endsWith("/transcription/stop")) state.transcription = "STOP_REQUESTED";
        await reply({ id: "synthetic-capture", status: "STOP_REQUESTED" }); return true;
      }
      return false;
    },
  });
  return { state, send, release, options, request: () => { state.row = row("PENDING"); } };
}

const permission = (page, text) => page.getByRole("list", { name: "Media permission", exact: true }).getByText(text, { exact: true });
async function join(page) {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(page.getByRole("region", { name: "Video call" }).getByText("Waiting for Consent Test Student…", { exact: true }));
}
async function withdraw(student) {
  await student.getByRole("button", { name: "Withdraw recording and live transcription permission", exact: true }).click();
  await student.getByRole("alertdialog").getByRole("button", { name: "Withdraw permission", exact: true }).click();
}

{
  const w = world();
  await check("two isolated sessions request-approve-withdraw before any Daily call", PATH, w.options("COUNSELOR"), async (counselor, { requests }) => {
    const student = await openPage(PATH, w.options("STUDENT"));
    try {
      await shown(permission(counselor, "Media permission · Not requested"));
      await screenshot(counselor, "counselor-permission-request-available");
      await counselor.getByRole("button", { name: "Request media permission", exact: true }).click();
      await shown(permission(counselor, "Media permission · Waiting for Student"));
      await screenshot(counselor, "counselor-permission-pending");
      await shown(student.page.getByRole("button", { name: `Allow ${subject}`, exact: true }));
      await screenshot(student.page, "student-consent-pending");
      await student.page.getByRole("button", { name: `Allow ${subject}`, exact: true }).click();
      await student.page.getByRole("alertdialog").getByRole("button", { name: "Allow", exact: true }).click();
      await shown(permission(counselor, "Media permission · Approved"));
      await shown(student.page.getByText("Allowed", { exact: true }));
      await screenshot(student.page, "student-consent-approved");
      await screenshot(counselor, "counselor-permission-approved");
      await withdraw(student.page);
      await shown(permission(counselor, "Media permission · Withdrawn"));
      await shown(student.page.getByText("Withdrawn", { exact: true }).first());
      await screenshot(student.page, "student-consent-withdrawn");
      assert.equal(w.state.commands.length, 0, "Consent never auto-starts or invents a Stop");
      assert.equal(requests.filter((request) => request.pathname.endsWith("/join")).length, 0);
      assert.deepEqual(student.errors, []);
      for (const role of ["STUDENT", "COUNSELOR"]) assert.equal(w.state.sockets.filter((socket) => socket.role === role && !socket.closed).length, 1);
      assert.equal(student.requests.filter((request) => request.pathname === `/api/v1/e-counseling/appointments/${ID}/consents`).length, 0, "Student never reads assigned consent API");
    } finally { await student.context.close(); }
  });
}

{
  const w = world({ approved: true });
  await check("active-call withdrawal closes an open Start confirmation before a delayed consent response", PATH, w.options("COUNSELOR"), async (counselor) => {
    const student = await openPage(PATH, w.options("STUDENT"));
    try {
      await shown(permission(counselor, "Media permission · Approved")); await join(counselor);
      await counselor.getByRole("button", { name: "Start recording", exact: true }).click();
      const dialog = counselor.getByRole("alertdialog", { name: "Start recording?", exact: true }); await shown(dialog);
      w.state.hold = true; await withdraw(student.page);
      await hidden(dialog);
      await eventually(() => w.state.held.length > 0, "Consent HTTP refresh starts");
      assert.equal(await counselor.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true);
      w.release(); await shown(permission(counselor, "Media permission · Withdrawn"));
      assert.equal(w.state.commands.length, 0);
      assert.deepEqual(student.errors, []);
    } finally { w.release(); await student.context.close(); }
  });
}

{
  const w = world({ approved: true, transcription: "ACTIVE" });
  await check("failed consent refresh blocks Start but keeps a legitimate Stop and uncertainty", PATH, w.options("COUNSELOR"), async (page) => {
    await shown(permission(page, "Media permission · Approved")); await join(page);
    w.state.failure = true; w.send();
    await shown(page.getByText("Media permission couldn’t be loaded. Recording and transcription can’t start until it loads.", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "Start recording", exact: true }).isDisabled(), true);
    const stop = page.getByRole("button", { name: "Stop transcription", exact: true });
    assert.equal(await stop.isEnabled(), true); await stop.click();
    await eventually(() => w.state.commands.length === 1, "Only the explicit Stop reaches HTTP");
    assert.ok(w.state.commands[0].endsWith("/transcription/stop"));
    assert.equal(await page.getByText("Recording stopped", { exact: true }).count(), 0);
  });
}

{
  const w = world({ approved: true, recording: "ACTIVE", withdrawalFailure: true });
  await check("provider failure after withdrawal still refreshes permission without claiming recording stopped", PATH, w.options("COUNSELOR"), async (counselor) => {
    const student = await openPage(PATH, w.options("STUDENT"));
    try {
      await shown(permission(counselor, "Media permission · Approved"));
      await withdraw(student.page);
      await shown(permission(counselor, "Media permission · Withdrawn"));
      assert.equal(await counselor.getByRole("button", { name: "Stop recording", exact: true }).isEnabled(), true);
      assert.equal(await counselor.getByText("Recording stopped", { exact: true }).count(), 0);
      assert.equal(w.state.recording, "ACTIVE", "Consent cannot invent physical provider cessation");
      assert.deepEqual(student.errors, []);
    } finally { await student.context.close(); }
  });
}

for (const boundary of ["hidden", "offline"]) {
  const w = world();
  await check(`${boundary} tab returns to canonical consent without a manual reload`, PATH, w.options("STUDENT"), async (page) => {
    await shown(page.getByRole("heading", { name: "Recording & live transcription", exact: true }));
    await eventually(() => w.state.reads.some((read) => read.kind === "workspace") && w.state.reads.some((read) => read.kind === "consents"), "Initial workspace and consent reads completed");
    await eventually(() => w.state.sockets.length === 1 && w.state.sockets[0].ready, "Realtime connection is ready before the foreground transition");
    const before = w.state.reads.filter((read) => read.kind === "consents").length;
    await page.evaluate((value) => {
      if (value === "hidden") {
        Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
        document.dispatchEvent(new Event("visibilitychange"));
      } else {
        Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
        window.dispatchEvent(new Event("offline"));
      }
    }, boundary);
    w.request();
    if (boundary === "hidden") w.send();
    await page.waitForTimeout(150);
    assert.equal(w.state.reads.filter((read) => read.kind === "consents").length, before);
    await page.evaluate((value) => {
      if (value === "hidden") {
        Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
        document.dispatchEvent(new Event("visibilitychange"));
      } else {
        Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
        window.dispatchEvent(new Event("online"));
      }
    }, boundary);
    await shown(page.getByRole("button", { name: `Allow ${subject}`, exact: true }));
    assert.equal(w.state.commands.length, 0);
  });
}

for (const mode of ["disabled", "outage"]) {
  const w = world({ realtime: mode !== "disabled", outage: mode === "outage" });
  await check(`${mode} transport heals a pre-call request by bounded polling`, PATH, w.options("STUDENT"), async (page) => {
    await shown(page.getByRole("heading", { name: "Recording & live transcription", exact: true }));
    w.request();
    await shown(page.getByRole("button", { name: `Allow ${subject}`, exact: true }));
    assert.equal(w.state.commands.length, 0);
    if (mode === "disabled") assert.equal(w.state.sockets.length, 0);
  });
}

{
  const w = world();
  await check("initial socket ready and reconnect heal a missed pre-call request", PATH, w.options("STUDENT"), async (page) => {
    await eventually(() => w.state.sockets.length === 1, "One shared socket connects");
    w.request();
    w.state.sockets[0].route.close({ code: 4000, reason: "synthetic reconnect" });
    await shown(page.getByRole("button", { name: `Allow ${subject}`, exact: true }));
    assert.equal(w.state.commands.length, 0);
  });
}

{
  const w = world({ approved: true });
  await check("unrelated appointment hint does not refetch current consent; page plus active call share refresh", PATH, w.options("COUNSELOR"), async (page) => {
    await shown(permission(page, "Media permission · Approved")); await join(page);
    // Wait for the join's canonical refresh; then isolate the consent-specific event counts.
    await eventually(() => w.state.reads.filter((read) => read.kind === "consents").length >= 1, "Consent read completed");
    const before = w.state.reads.filter((read) => read.kind === "consents").length;
    w.send(OTHER);
    await page.waitForTimeout(150);
    assert.equal(w.state.reads.filter((read) => read.kind === "consents").length, before);
    for (let i = 0; i < 10; i++) w.send();
    await eventually(() => w.state.reads.filter((read) => read.kind === "consents").length > before, "Current appointment reconciles");
    assert.ok(w.state.reads.filter((read) => read.kind === "consents").length - before <= 2, "One fetch with at most one trailing read");
    assert.equal(w.state.sockets.filter((socket) => !socket.closed).length, 1);
  });
}

{
  const w = world({ approved: true });
  await check("lost workspace access conceals protected consent state", PATH, w.options("COUNSELOR"), async (page) => {
    await shown(permission(page, "Media permission · Approved"));
    w.state.denied = true; w.send();
    await shown(page.getByRole("heading", { name: "E-Counseling unavailable", exact: true }));
    assert.equal(await page.getByText("Consent Test Student", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("list", { name: "Media permission", exact: true }).count(), 0);
  });
}

await finish();
