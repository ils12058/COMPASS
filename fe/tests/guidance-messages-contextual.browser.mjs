// Contextual Guidance Messages (ADR-103) in a real browser: the Appointment's one Counseling thread
// opened beside Appointment, Counseling and E-Counseling pages. Every API call is answered by the
// synthetic backends in support/, the call uses the fake Call Object, and realtime is a Playwright
// WebSocket route. No account, record, key, Message or Daily room is real.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import {
  appointmentId,
  appointmentPath,
  contextualRoutes,
  counselingPath,
  ecounselingPath,
  routineCounselingPath,
} from "./support/guidance-contextual-fixtures.mjs";
import {
  COUNSELOR,
  createMessagesBackend,
  messagesAccount,
  sessionFor,
  STUDENT,
  threadIds,
} from "./support/guidance-messages-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow } = await createBrowserHarness("guidance-messages-contextual");

const SOCKET_URL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
const enableRealtime = `window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(SOCKET_URL)} };`;
const THREAD = threadIds.counseling;

async function eventually(condition, message, timeout = 10_000) {
  const started = Date.now();
  while (!(await condition())) {
    if (Date.now() - started > timeout) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

const trigger = (page) => page.getByRole("button", { name: /^Messages/ });
const panel = (page) => page.getByRole("complementary", { name: "Messages" });
const drawer = (page) => page.getByRole("dialog", { name: "Messages" });
const composer = (scope) => scope.getByRole("textbox", { name: /^Message to/ });
const history = (scope) => scope.getByRole("region", { name: "Conversation history" });
const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const stage = (page) => page.getByRole("region", { name: "Video call" });
const tray = (page) => page.getByRole("group", { name: "Call controls" });

/** A Messages backend for the viewer, with the Appointment's thread already started or not. */
function backendFor(role, { started = true, status = "OPEN", startable = true } = {}) {
  const viewerId = role === "STUDENT" ? STUDENT.id : role === "GUIDANCE_SERVICES_STAFF" ? "gss" : COUNSELOR.id;
  const backend = createMessagesBackend({ viewerId, viewerRole: role });
  if (!startable) backend.state.startable.clear();
  if (started) {
    backend.addThread({ id: THREAD, kind: "COUNSELING", status, counselor: COUNSELOR, appointment: appointmentId });
    backend.addMessage(THREAD, COUNSELOR, "Good afternoon, Maria.", { at: backend.minutesAgo(30) });
    backend.addMessage(THREAD, STUDENT, "Thank you po.", { at: backend.minutesAgo(20) });
    backend.state.reads.set(THREAD, 2);
    backend.state.startable.clear();
  }
  return backend;
}

/** One world: a signed-in account, its Messages backend, the Appointment records and a socket. */
function contextualWorld(role, backend, { serviceCode, validUntil, account } = {}) {
  const world = { account: account ?? messagesAccount(role, role === "GUIDANCE_SERVICES_STAFF" ? { id: "gss" } : {}), backend, sockets: [], joins: { count: 0 } };
  const routes = contextualRoutes({ serviceCode, validUntil, joins: world.joins });
  world.handler = async (args) => (await backend.handler(args)) || (await routes(args));
  world.overrides = {
    "/api/v1/auth/session": ({ reply }) => reply(sessionFor(world.account)),
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: `${world.account.first_name} ${world.account.last_name}`, photo: null }),
    "POST /api/v1/realtime/tickets": ({ reply }) => reply({ ticket: `ticket-${world.account.id}-${world.sockets.length}`, expires_in_seconds: 30, user_id: world.account.id }),
  };
  world.beforeNavigate = async ({ context }) => {
    await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
      const socket = { route, serverFrames: [], closed: null };
      world.sockets.push(socket);
      route.onMessage((message) => {
        if (JSON.parse(String(message)).type === "authenticate") world.send(socket, { v: 1, type: "ready" });
      });
      route.onClose(() => { socket.closed = true; });
    });
  };
  world.send = (socket, frame) => { socket.serverFrames.push(frame); socket.route.send(JSON.stringify(frame)); };
  world.changed = (threadId) => world.sockets.filter((socket) => !socket.closed).forEach((socket) => world.send(socket, { v: 1, type: "messages.thread_changed", thread_id: threadId }));
  world.ready = () => eventually(() => world.sockets.some((socket) => socket.serverFrames.length > 0), "Socket ready");
  world.options = (extra = {}) => ({ handler: world.handler, overrides: world.overrides, beforeNavigate: world.beforeNavigate, ...extra });
  return world;
}

// ── Appointment detail ────────────────────────────────────────────────────────────────────────

for (const role of ["STUDENT", "COUNSELOR"]) {
  const world = contextualWorld(role, backendFor(role));
  await check(`Appointment (${role.toLowerCase()}): Messages docks beside the page with the canonical thread`, appointmentPath, world.options(), async (page) => {
    await shown(trigger(page));
    assert.equal(await trigger(page).getAttribute("aria-expanded"), "false");
    assert.equal(world.backend.requests((request) => request.pathname.includes("/messages")).length, 0, "No history before opening");
    await trigger(page).click();
    await shown(panel(page));
    assert.equal(await trigger(page).getAttribute("aria-expanded"), "true");
    await shown(history(panel(page)).getByText("Good afternoon, Maria."));
    await shown(panel(page).getByText(role === "STUDENT" ? "Ana Cruz · Counseling" : "Maria Santos · Counseling"));
    const link = panel(page).getByRole("link", { name: "Open full conversation" });
    assert.equal(await link.getAttribute("href"), `/portal/messages/${THREAD}`);
    assert.equal(await page.getByRole("dialog").count(), 0, "Docked, not modal");
    await shown(page.getByRole("heading", { name: "Appointment", level: 1 }));
    assert.equal(await page.locator("[inert], [aria-hidden=true] #main-content").count(), 0, "The page stays usable beside the panel");
    assert.equal(await panel(page).getByRole("button", { name: /Resolve conversation/ }).count(), role === "COUNSELOR" ? 1 : 0, "Only staff can resolve");
    await noHorizontalOverflow(page);
    await panel(page).getByRole("button", { name: "Close Messages" }).click();
    await hidden(panel(page));
    assert.equal(await trigger(page).evaluate((node) => document.activeElement === node), true, "Focus returns to Messages");
  });
}

{
  const world = contextualWorld("STUDENT", backendFor("STUDENT"), { serviceCode: "GM-OTHER" });
  await check("a non-Counseling Appointment offers no Messages and asks nothing", appointmentPath, world.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Appointment", level: 1 }));
    await page.waitForTimeout(1_500);
    assert.equal(await trigger(page).count(), 0);
    assert.equal(world.backend.contexts().length, 0);
  });
}

for (const [label, role] of [["concealed context", "STUDENT"], ["GSS", "GUIDANCE_SERVICES_STAFF"]]) {
  const backend = backendFor(role, { started: label === "GSS", startable: false });
  const world = contextualWorld(role, backend);
  await check(`${label}: no Messages action and no content`, appointmentPath, world.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Appointment", level: 1 }));
    await eventually(() => world.backend.contexts().length > 0, "The context is asked once");
    await page.waitForTimeout(800);
    assert.equal(await trigger(page).count(), 0);
    assert.equal(await page.getByText("Good afternoon, Maria.").count(), 0);
  });
}

{
  const backend = backendFor("STUDENT", { started: false });
  const world = contextualWorld("STUDENT", backend);
  await check("first Message: no thread until the first send, then the same panel shows it", appointmentPath, world.options(), async (page) => {
    await trigger(page).click();
    await shown(panel(page).getByText("No conversation has started for this counseling appointment yet."));
    assert.equal(await history(panel(page)).count(), 0, "No fake bubbles");
    assert.equal(await panel(page).getByRole("link", { name: "Open full conversation" }).count(), 0);
    assert.equal(backend.state.threads.size, 0, "Opening creates nothing");
    await composer(panel(page)).fill("First contextual message");
    await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(panel(page)).getByText("First contextual message"));
    const [opened] = backend.opens();
    assert.equal(opened.pathname, `/api/v1/guidance-messages/appointments/${appointmentId}/counseling-thread`);
    assert.deepEqual(Object.keys(opened.body).sort(), ["body", "client_message_id"]);
    assert.match(page.url(), new RegExp(`${appointmentPath}$`), "Stays on the Appointment");
    const created = [...backend.state.threads.keys()][0];
    const link = panel(page).getByRole("link", { name: "Open full conversation" });
    await shown(link);
    assert.equal(await link.getAttribute("href"), `/portal/messages/${created}`);
    await composer(panel(page)).fill("A second one");
    await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(panel(page)).getByText("A second one"));
    assert.equal(backend.state.threads.size, 1, "Still one thread");
    await link.click();
    await page.waitForURL(new RegExp(`/portal/messages/${created}$`));
    await shown(page.getByRole("region", { name: "Conversation history" }).getByText("First contextual message"));
  });
}

{
  const backend = backendFor("STUDENT", { started: false });
  let attempts = 0;
  backend.state.onSend = () => (attempts++ === 0 ? "commit-then-network" : undefined);
  const world = contextualWorld("STUDENT", backend);
  await check("an unconfirmed first Message retries with the same ID after the thread appears", appointmentPath, world.options(), async (page) => {
    await trigger(page).click();
    await composer(panel(page)).fill("Did my first message arrive?");
    await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    await shown(panel(page).getByRole("button", { name: "Retry sending" }));
    await panel(page).getByRole("button", { name: "Retry sending" }).click();
    await shown(history(panel(page)).getByText("Did my first message arrive?"));
    const [first, retry] = backend.opens();
    assert.equal(retry.body.client_message_id, first.body.client_message_id);
    assert.equal(retry.body.body, first.body.body);
    await page.waitForTimeout(500);
    assert.equal(await history(panel(page)).getByText("Did my first message arrive?", { exact: true }).count(), 1);
    assert.equal(backend.state.threads.size, 1);
  });
}

{
  const world = contextualWorld("STUDENT", backendFor("STUDENT"));
  await check("a draft survives closing and reopening the panel, and guards navigation", appointmentPath, world.options(), async (page) => {
    const dialogs = [];
    page.on("dialog", async (dialog) => { dialogs.push(dialog.message()); await dialog.dismiss(); });
    await trigger(page).click();
    await composer(panel(page)).fill("Half-written thought");
    await panel(page).getByRole("button", { name: "Close Messages" }).click();
    await hidden(panel(page));
    await trigger(page).click();
    assert.equal(await composer(panel(page)).inputValue(), "Half-written thought");
    await panel(page).getByRole("button", { name: "Close Messages" }).click();
    await page.getByRole("navigation").getByRole("link", { name: "Messages", exact: true }).first().click();
    await eventually(() => dialogs.length === 1, "Leaving asks first");
    assert.equal(dialogs[0], "Discard your unsent message?");
    assert.match(page.url(), new RegExp(`${appointmentPath}$`));
  });
}

for (const role of ["STUDENT", "COUNSELOR"]) {
  const backend = backendFor(role, { status: "RESOLVED" });
  const world = contextualWorld(role, backend);
  await check(`a resolved thread stays readable (${role.toLowerCase()})`, appointmentPath, world.options(), async (page) => {
    await trigger(page).click();
    await shown(history(panel(page)).getByText("Good afternoon, Maria."));
    await shown(panel(page).getByText("This conversation is resolved.", { exact: true }));
    assert.ok(await panel(page).getByRole("button", { name: "Send", exact: true }).isDisabled());
    if (role === "STUDENT") {
      assert.equal(await panel(page).getByRole("button", { name: /Reopen/ }).count(), 0);
    } else {
      await panel(page).getByRole("button", { name: "Reopen conversation" }).click();
      await eventually(async () => !(await panel(page).getByRole("button", { name: "Send", exact: true }).isDisabled()), "Reopen restores sending");
      assert.equal(backend.state.threads.size, 1, "No second thread");
    }
  });
}

{
  const world = contextualWorld("STUDENT", backendFor("STUDENT"));
  await check("narrow: Messages is a full-width drawer; Escape closes it and focus returns", appointmentPath, world.options({ device: "phone" }), async (page) => {
    await trigger(page).click();
    await shown(drawer(page));
    await shown(history(drawer(page)).getByText("Good afternoon, Maria."));
    await eventually(() => page.evaluate(() => document.activeElement?.textContent === "Messages" && document.activeElement.tagName === "H2"), "Focus moves to the drawer's heading");
    const box = await drawer(page).boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.x <= 0.5 && box.width >= viewport.width - 1, "Full width");
    const send = await drawer(page).getByRole("button", { name: "Send", exact: true }).boundingBox();
    assert.ok(send.y + send.height <= viewport.height, "Composer in reach");
    await noHorizontalOverflow(page);
    await page.keyboard.press("Escape");
    await hidden(drawer(page));
    // Radix restores focus as the drawer unmounts, just after it disappears.
    await eventually(() => trigger(page).evaluate((node) => document.activeElement === node), "Focus returns to Messages");
  });
}

{
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"));
  await check("no horizontal overflow with Messages open from 320px to 1440px", appointmentPath, world.options(), async (page) => {
    for (const width of [320, 375, 390, 430, 768, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto(`${baseURL}${appointmentPath}`);
      await trigger(page).click();
      await shown(width >= 1100 ? panel(page) : drawer(page));
      await shown(page.getByText("Good afternoon, Maria."));
      await noHorizontalOverflow(page);
    }
  });
}

// ── Counseling workspace ──────────────────────────────────────────────────────────────────────

{
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"));
  await check("Counseling workspace (Appointment anchor) opens the same thread", counselingPath, world.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Counseling workspace" }));
    await trigger(page).click();
    await shown(history(panel(page)).getByText("Thank you po."));
    assert.equal(await panel(page).getByRole("link", { name: "Open full conversation" }).getAttribute("href"), `/portal/messages/${THREAD}`);
    await composer(panel(page)).fill("Reply from the Counseling workspace");
    await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(panel(page)).getByText("Reply from the Counseling workspace"));
    assert.equal(world.backend.state.messages.get(THREAD).length, 3);
  });
}

{
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"));
  await check("a Routine Interview Counseling context offers no contextual Messages", routineCounselingPath, world.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Counseling workspace" }));
    await page.waitForTimeout(1_500);
    assert.equal(await trigger(page).count(), 0);
    assert.equal(world.backend.contexts().length, 0);
  });
}

{
  const validUntil = new Date(Date.now() + 25_000).toISOString();
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"), { validUntil });
  await check("Counseling context expiry keeps the Messages panel, its draft and the thread", counselingPath, world.options(), async (page) => {
    await trigger(page).click();
    await shown(history(panel(page)).getByText("Thank you po."));
    await composer(panel(page)).fill("Written before the context ended");
    await page.getByRole("heading", { name: "Counseling information unavailable" }).waitFor({ timeout: 40_000 });
    await shown(panel(page));
    assert.equal(await composer(panel(page)).inputValue(), "Written before the context ended");
    await shown(history(panel(page)).getByText("Thank you po."));
    assert.equal(world.backend.state.threads.size, 1, "The thread is untouched");
    await page.goto(`${baseURL}/portal/messages/${THREAD}`);
    await shown(page.getByRole("region", { name: "Conversation history" }).getByText("Thank you po."));
  });
}

// ── E-Counseling ──────────────────────────────────────────────────────────────────────────────

for (const role of ["STUDENT", "COUNSELOR"]) {
  const world = contextualWorld(role, backendFor(role));
  await check(`E-Counseling (${role.toLowerCase()}): Messages opens and closes without touching the call`, ecounselingPath, world.options({ fakeDaily: true }), async (page) => {
    await page.getByRole("button", { name: "Join session", exact: true }).click();
    await shown(stage(page).getByText(/^Waiting for /).first());
    await fake(page, "remoteJoin", { userId: role === "STUDENT" ? "counselor" : "student", name: "Remote" });
    await shown(stage(page).getByText("Connected", { exact: true }));
    const microphone = tray(page).getByRole("button", { name: "Microphone", exact: true });
    await microphone.click();
    assert.equal(await microphone.getAttribute("aria-pressed"), "false");
    const before = await page.evaluate(() => ({ instances: window.__COMPASS_FAKE_DAILY__.instances.length, audio: document.querySelector("audio") }));
    const counts = async () => ({
      created: await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.instances.length),
      joins: await fakeCount(page, "join"),
      leaves: await fakeCount(page, "leave"),
      destroys: await fakeCount(page, "destroy"),
      recordings: await fakeCount(page, "startRecording") + await fakeCount(page, "stopRecording"),
      transcriptions: await fakeCount(page, "startTranscription") + await fakeCount(page, "stopTranscription"),
    });
    const initial = await counts();

    await trigger(page).click();
    const surface = page.getByRole("complementary", { name: "Messages" });
    await shown(history(surface).getByText("Good afternoon, Maria."));
    await composer(surface).fill(`Sent during the call by ${role.toLowerCase()}`);
    await surface.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(surface).getByText(`Sent during the call by ${role.toLowerCase()}`));
    await shown(stage(page).getByText("Connected", { exact: true }));
    await surface.getByRole("button", { name: "Close Messages" }).click();
    await hidden(surface);

    assert.deepEqual(await counts(), initial, "No call created, joined, left, destroyed or captured");
    assert.equal(before.instances, 1);
    assert.equal(world.joins.count, 1, "No second credential request");
    assert.equal(await microphone.getAttribute("aria-pressed"), "false", "Local media state is kept");
    assert.equal(await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.instances.filter((call) => !call.isDestroyed()).length), 1);
    await shown(stage(page).getByText("Connected", { exact: true }));
    assert.equal(await page.evaluate(() => document.querySelectorAll("audio").length), 1, "One remote audio element");
  });
}

{
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"));
  await check("E-Counseling Counselor: the layout preset survives Messages", ecounselingPath, world.options({ fakeDaily: true }), async (page) => {
    await page.getByRole("button", { name: "Compact", exact: true }).click();
    await trigger(page).click();
    await shown(page.getByRole("complementary", { name: "Messages" }));
    await noHorizontalOverflow(page);
    await page.getByRole("button", { name: "Close Messages" }).click();
    await shown(page.getByRole("button", { name: "Compact", exact: true }));
    assert.equal(await page.getByRole("button", { name: "Compact", exact: true }).getAttribute("aria-pressed"), "true");
  });
}

{
  const world = contextualWorld("STUDENT", backendFor("STUDENT"));
  await check("E-Counseling on a phone: the drawer covers the call without ending it", ecounselingPath, world.options({ fakeDaily: true, device: "phone" }), async (page) => {
    await page.getByRole("button", { name: "Join session", exact: true }).click();
    await shown(stage(page).getByText(/^Waiting for /).first());
    await fake(page, "remoteJoin", { userId: "counselor", name: "Ana" });
    await shown(stage(page).getByText("Connected", { exact: true }));
    await trigger(page).click();
    await shown(history(drawer(page)).getByText("Good afternoon, Maria."));
    await noHorizontalOverflow(page);
    await page.keyboard.press("Escape");
    await hidden(drawer(page));
    await shown(stage(page).getByText("Connected", { exact: true }));
    assert.equal(await fakeCount(page, "leave"), 0);
    assert.equal(world.joins.count, 1);
  });
}

// ── One thread everywhere, realtime and accounts ──────────────────────────────────────────────

{
  const world = contextualWorld("COUNSELOR", backendFor("COUNSELOR"));
  await check("Appointment, Counseling, E-Counseling and the full workspace share one thread", appointmentPath, world.options({ fakeDaily: true }), async (page) => {
    const hrefs = [];
    for (const path of [appointmentPath, counselingPath, ecounselingPath]) {
      if (path !== appointmentPath) await page.goto(`${baseURL}${path}`);
      await trigger(page).click();
      const link = page.getByRole("link", { name: "Open full conversation" });
      await shown(link);
      hrefs.push(await link.getAttribute("href"));
    }
    assert.deepEqual(hrefs, Array(3).fill(`/portal/messages/${THREAD}`));
    await page.getByRole("link", { name: "Open full conversation" }).click();
    await page.waitForURL(new RegExp(`/portal/messages/${THREAD}$`));
    await shown(page.getByRole("region", { name: "Conversation history" }).getByText("Thank you po."));
    assert.equal(world.backend.state.threads.size, 1);
    assert.equal(world.backend.opens().length, 0, "No surface created a thread");
  });
}

{
  const world = contextualWorld("STUDENT", backendFor("STUDENT"));
  await check("cross-tab: the panel and the full workspace reconcile each other over HTTP", appointmentPath, world.options({ initScripts: [enableRealtime] }), async (page, { context }) => {
    await trigger(page).click();
    await shown(history(panel(page)).getByText("Thank you po."));
    const full = await context.newPage();
    await full.addInitScript({ content: enableRealtime });
    await full.goto(`${baseURL}/portal/messages/${THREAD}`);
    await shown(full.getByRole("region", { name: "Conversation history" }).getByText("Thank you po."));
    await eventually(() => world.sockets.length === 2 && world.sockets.every((socket) => socket.serverFrames.length > 0), "One ready socket per tab");
    await composer(panel(page)).fill("From the Appointment panel");
    await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(panel(page)).getByText("From the Appointment panel"));
    world.changed(THREAD);
    await shown(full.getByRole("region", { name: "Conversation history" }).getByText("From the Appointment panel"));
    await full.getByRole("textbox", { name: /^Message to/ }).fill("From the full workspace");
    await full.getByRole("button", { name: "Send", exact: true }).click();
    world.changed(THREAD);
    await shown(history(panel(page)).getByText("From the full workspace"));
    assert.equal(world.sockets.length, 2, "No socket beyond one per tab");
    const wire = world.sockets.flatMap((socket) => socket.serverFrames).filter((frame) => frame.type !== "ready");
    assert.ok(wire.every((frame) => Object.keys(frame).sort().join() === "thread_id,type,v"), "Hints carry no content");
  });
}

{
  const backend = backendFor("STUDENT", { started: false });
  const world = contextualWorld("STUDENT", backend);
  await check("an open panel without a thread discovers one another tab started", appointmentPath, world.options({ initScripts: [enableRealtime] }), async (page) => {
    await trigger(page).click();
    await shown(panel(page).getByText("No conversation has started for this counseling appointment yet."));
    await world.ready();
    backend.addThread({ id: THREAD, kind: "COUNSELING", counselor: COUNSELOR, appointment: appointmentId });
    backend.addMessage(THREAD, STUDENT, "Started in another tab");
    backend.state.startable.clear();
    world.changed(THREAD);
    await shown(history(panel(page)).getByText("Started in another tab"));
    await shown(panel(page).getByRole("link", { name: "Open full conversation" }));
  });
}

{
  const backend = backendFor("STUDENT");
  backend.addMessage(THREAD, COUNSELOR, "Unread reply", { at: backend.minutesAgo(1) });
  const world = contextualWorld("STUDENT", backend);
  await check("reads follow the open panel only; no read receipt", appointmentPath, world.options(), async (page) => {
    await shown(trigger(page).getByText("1 unread"));
    await page.waitForTimeout(1_000);
    assert.equal(backend.reads().length, 0, "The button and resolver mark nothing read");
    await trigger(page).click();
    await eventually(() => backend.reads().some((request) => request.body.sequence === 3), "Read once visible in the panel");
    await panel(page).getByRole("button", { name: "Close Messages" }).click();
    await hidden(trigger(page).getByText("1 unread"));
    assert.equal(await page.getByText(/seen|read by/i).count(), 0);
  });
}

{
  const backend = backendFor("STUDENT");
  const accountA = messagesAccount("STUDENT", { first_name: "Account", last_name: "Alpha" });
  const accountB = messagesAccount("STUDENT", { id: "student-b", first_name: "Account", last_name: "Bravo" });
  const world = contextualWorld("STUDENT", backend, { account: accountA });
  await check("another account never sees the previous account's panel, history or draft", appointmentPath, world.options({
    beforeNavigate: async (fixture) => { await world.beforeNavigate(fixture); await fixture.page.clock.install(); },
  }), async (page) => {
    await trigger(page).click();
    await shown(history(panel(page)).getByText("Good afternoon, Maria."));
    await composer(panel(page)).fill("Account A draft");
    world.account = accountB;
    backend.state.viewerId = accountB.id;
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("Account Bravo").first());
    await page.waitForTimeout(800);
    assert.equal(await page.getByText("Good afternoon, Maria.").count(), 0);
    assert.equal(await page.getByText("Account A draft").count(), 0);
    assert.equal(await panel(page).count(), 0, "The panel closed with the account");
    assert.equal(await trigger(page).count(), 0, "Re-resolved for Account B, who has no thread here");
  });
}

await finish();
