// Guidance Messages workspace in a real browser (ADR-102). Every API call is answered by the
// synthetic Messages backend in support/guidance-messages-fixtures.mjs, and realtime is a Playwright
// WebSocket route enabled through the development-only seam. No account, record, key or Message is real.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import {
  appointmentId,
  COUNSELOR,
  createMessagesBackend,
  messagesAccount,
  OTHER_STUDENT,
  sessionFor,
  staffWorld,
  STUDENT,
  studentWorld,
  threadIds,
} from "./support/guidance-messages-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow } = await createBrowserHarness("guidance-messages");

const SOCKET_URL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
const enableRealtime = `window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(SOCKET_URL)} };`;
// Lets a test hide and show the document the way a background tab would.
const controllableVisibility = (initial = "visible") => `(() => {
  let state = ${JSON.stringify(initial)};
  Object.defineProperty(Document.prototype, "visibilityState", { configurable: true, get: () => state });
  Object.defineProperty(Document.prototype, "hidden", { configurable: true, get: () => state === "hidden" });
  window.__setVisibility = (next) => { state = next; document.dispatchEvent(new Event("visibilitychange")); };
})();`;

const threadPath = (id) => `/portal/messages/${id}`;
const isThreadsList = (request) => request.method === "GET" && request.pathname === "/api/v1/guidance-messages/threads";
const isDetail = (id) => (request) => request.method === "GET" && request.pathname === `/api/v1/guidance-messages/threads/${id}`;
const isHistory = (id) => (request) => request.method === "GET" && request.pathname === `/api/v1/guidance-messages/threads/${id}/messages`;

async function eventually(condition, message, timeout = 10_000) {
  const started = Date.now();
  while (!(await condition())) {
    if (Date.now() - started > timeout) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

function composer(page) {
  return page.getByRole("textbox", { name: /^Message/ });
}

function row(page, id) {
  return page.locator(`nav[aria-label="Conversations"] a[data-thread-id="${id}"]`);
}

function history(page) {
  return page.getByRole("region", { name: "Conversation history" });
}

/** A signed-in account the test can replace, plus the fake realtime server for it. */
function messagesWorld(backend, account) {
  const world = { account, backend, sockets: [], tickets: [] };
  world.overrides = {
    "/api/v1/auth/session": ({ reply }) => reply(sessionFor(world.account)),
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: `${world.account.first_name} ${world.account.last_name}`, photo: null }),
    "POST /api/v1/realtime/tickets": ({ reply }) => {
      const ticket = `ticket-${world.account.id}-${world.tickets.length}`;
      world.tickets.push(ticket);
      return reply({ ticket, expires_in_seconds: 30, user_id: world.account.id });
    },
  };
  world.beforeNavigate = async ({ context }) => {
    await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
      const socket = { route, frames: [], serverFrames: [], closed: null };
      world.sockets.push(socket);
      route.onMessage((message) => {
        socket.frames.push(String(message));
        if (JSON.parse(String(message)).type === "authenticate") world.send(socket, { v: 1, type: "ready" });
      });
      route.onClose((code) => { socket.closed = code ?? 1005; });
    });
  };
  world.send = (socket, frame) => {
    socket.serverFrames.push(frame);
    socket.route.send(JSON.stringify(frame));
  };
  world.open = () => world.sockets.filter((socket) => socket.closed === null);
  world.changed = (threadId) => world.open().forEach((socket) => world.send(socket, { v: 1, type: "messages.thread_changed", thread_id: threadId }));
  world.ready = () => eventually(() => world.open().some((socket) => socket.serverFrames.length > 0), "The socket is ready");
  world.options = (extra = {}) => ({ handler: backend.handler, overrides: world.overrides, beforeNavigate: world.beforeNavigate, ...extra });
  return world;
}

// ── Navigation and access ─────────────────────────────────────────────────────────────────────

for (const [role, label] of [["STUDENT", "Student with view_self"], ["GUIDANCE_SERVICES_STAFF", "Guidance staff with view"]]) {
  const world = messagesWorld(role === "STUDENT" ? studentWorld() : staffWorld(), messagesAccount(role));
  await check(`${label} sees the Messages destination`, "/portal", world.options(), async (page) => {
    await shown(page.getByRole("link", { name: "Messages", exact: true }).first());
  });
}

for (const [label, account] of [
  ["IT Admin", messagesAccount("IT_ADMIN")],
  ["DPO designation", messagesAccount("IT_ADMIN", { designations: ["DPO"] })],
  ["Head designation without the capability", messagesAccount("COUNSELOR", { designations: ["HEAD_GUIDANCE_COUNSELOR"], capabilities: ["appointments.view_self"] })],
]) {
  const world = messagesWorld(staffWorld(), account);
  await check(`${label} has no Messages destination or content`, "/portal", world.options(), async (page) => {
    await shown(page.getByRole("link", { name: "Overview" }).first());
    assert.equal(await page.getByRole("link", { name: "Messages", exact: true }).count(), 0);
    await page.goto(`${baseURL}/portal/messages`);
    await shown(page.getByRole("heading", { name: "Messages unavailable" }));
    assert.equal(world.backend.requests().length, 0, "No Messages request is made");
  });
}

// ── Directory and conversation presentation ───────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("Student desktop split: directory labels, no previews, current thread, chronological chat", threadPath(threadIds.office), world.options(), async (page) => {
    const directory = page.getByRole("navigation", { name: "Conversations" });
    await shown(row(page, threadIds.office));
    await shown(page.getByRole("heading", { name: "Guidance Office", level: 2 }));
    assert.equal(await row(page, threadIds.office).getAttribute("aria-current"), "page");
    assert.equal(await row(page, threadIds.counseling).getAttribute("aria-current"), null);
    const directoryText = await directory.innerText();
    assert.match(await row(page, threadIds.counseling).innerText(), /Ana Cruz\s+.*\s*Counseling/s);
    assert.match(await row(page, threadIds.resolved).innerText(), /Guidance Office[\s\S]*Resolved/);
    for (const hiddenText of ["Bring your ID", "Good afternoon", "Thank you po", threadIds.office, "OFFICE", "COUNSELING", "RESOLVED"]) {
      assert.ok(!directoryText.includes(hiddenText), `The directory never shows ${hiddenText}`);
    }
    await shown(page.getByText("Guidance and Counseling Office", { exact: true }));
    const items = history(page).locator("ol > li");
    await eventually(async () => (await items.count()) === 3, "Three Messages render");
    const texts = await items.allInnerTexts();
    assert.match(texts[0], /You[\s\S]*Good afternoon po/);
    assert.match(texts[1], /Ana Cruz[\s\S]*Good afternoon, Maria\.\nYes, you can come on Monday\./);
    const [own, other] = await Promise.all([items.nth(0), items.nth(1)].map((item) => item.evaluate((node) => getComputedStyle(node).alignItems)));
    assert.equal(own, "flex-end", "Own Messages align to the end");
    assert.equal(other, "flex-start", "Other Messages align to the start");
    assert.equal(await page.getByText(/seen|read by/i).count(), 0, "No read receipt");
    assert.equal(await page.getByRole("button", { name: /Resolve|Reopen/ }).count(), 0, "Students never resolve or reopen");
  });
}

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("staff directory: Student, kind, College and handler; Counseling for Counseling", "/portal/messages", world.options(), async (page) => {
    await shown(row(page, threadIds.office));
    const office = await row(page, threadIds.office).innerText();
    assert.match(office, /Maria Santos[\s\S]*Guidance Office · College of Computing[\s\S]*Assigned to Lea Ramos[\s\S]*1 unread/);
    assert.match(await row(page, threadIds.counseling).innerText(), /John Reyes[\s\S]*Counseling/);
    assert.ok(!office.includes("Good afternoon"), "No Message preview");
    await shown(page.getByText("Choose a conversation, or start a new message."));
    await page.waitForTimeout(1_500);
    assert.equal(backend.reads().length, 0, "Loading the directory marks nothing read");
  });
}

// ── Read state ────────────────────────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("opening a visible thread marks it read once through the latest loaded sequence", "/portal/messages", world.options(), async (page) => {
    await shown(row(page, threadIds.office).getByText("2 unread"));
    await page.waitForTimeout(1_000);
    assert.equal(backend.reads().length, 0, "The directory alone marks nothing read");
    // Keyboard activation: Safari does not focus links on click.
    await row(page, threadIds.office).focus();
    await page.keyboard.press("Enter");
    await eventually(() => backend.reads().length === 1, "One read update");
    assert.deepEqual(backend.reads()[0].body, { sequence: 3 });
    assert.equal(backend.reads()[0].pathname, `/api/v1/guidance-messages/threads/${threadIds.office}/read`);
    await hidden(row(page, threadIds.office).getByText("2 unread"));
    await page.waitForTimeout(2_000);
    assert.equal(backend.reads().length, 1, "An unchanged cursor is not sent again");
    assert.equal(await row(page, threadIds.office).evaluate((node) => document.activeElement === node), true, "Desktop keeps focus on the chosen row");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a hidden tab does not mark read; becoming visible does", threadPath(threadIds.office), world.options({ initScripts: [controllableVisibility("hidden")] }), async (page) => {
    await eventually(async () => (await history(page).locator("ol > li").count()) === 3, "History loads while hidden");
    await page.waitForTimeout(1_500);
    assert.equal(backend.reads().length, 0, "Nothing is marked read while hidden");
    await page.evaluate(() => window.__setVisibility("visible"));
    await eventually(() => backend.reads().length === 1, "Becoming visible marks it read");
  });
}

{
  const backend = createMessagesBackend({ viewerId: COUNSELOR.id });
  backend.addThread({ id: threadIds.office });
  backend.addMessage(threadIds.office, STUDENT, "Please reply when you can.");
  const world = messagesWorld(backend, messagesAccount("GUIDANCE_SERVICES_STAFF", { capabilities: ["guidance_messages.view"] }));
  await check("view-only staff can read but not write, start, or mark read", threadPath(threadIds.office), world.options(), async (page) => {
    await shown(page.getByText("Please reply when you can."));
    await shown(page.getByText("You can read this conversation, but your account cannot send messages."));
    assert.equal(await composer(page).count(), 0);
    assert.equal(await page.getByRole("link", { name: "New message" }).count(), 0);
    assert.equal(await page.getByRole("button", { name: /Resolve conversation/ }).count(), 0);
    await page.waitForTimeout(1_500);
    assert.equal(backend.reads().length, 0);
  });
}

// ── History pagination, scrolling and containment ─────────────────────────────────────────────

function longWorld() {
  const backend = createMessagesBackend({ viewerId: STUDENT.id });
  backend.addThread({ id: threadIds.long });
  for (let index = 1; index <= 120; index += 1) {
    backend.addMessage(threadIds.long, index % 3 ? COUNSELOR : STUDENT, `Message number ${index}`, { at: new Date(Date.now() - (121 - index) * 60_000).toISOString() });
  }
  return backend;
}

{
  const backend = longWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("opens at the newest Message; Load older keeps the reader's place", threadPath(threadIds.long), world.options(), async (page) => {
    const scroller = history(page);
    await shown(page.getByText("Message number 120", { exact: true }));
    const atEnd = () => scroller.evaluate((node) => node.scrollHeight - node.scrollTop - node.clientHeight <= 2);
    await eventually(atEnd, "Opens scrolled to the newest Message");
    assert.equal(await scroller.locator("ol > li").count(), 50, "Only the newest page is loaded");
    await scroller.evaluate((node) => { node.scrollTop = 0; });
    // Development mounts twice, so compare newest-page reads from here on.
    const newestReads = () => backend.requests(isHistory(threadIds.long)).filter((request) => !request.search.includes("before_sequence")).length;
    const newestBefore = newestReads();
    const anchor = page.getByText("Message number 71", { exact: true });
    const before = await anchor.evaluate((node) => node.getBoundingClientRect().top);
    await page.getByRole("button", { name: "Load older messages" }).click();
    await shown(page.getByText("Message number 21", { exact: true }));
    const after = await anchor.evaluate((node) => node.getBoundingClientRect().top);
    assert.ok(Math.abs(after - before) <= 2, `The reader's place is kept (${before} → ${after})`);
    const older = backend.requests(isHistory(threadIds.long)).filter((request) => request.search.includes("before_sequence"));
    assert.equal(older.length, 1);
    assert.match(older[0].search, /before_sequence=71/);
    assert.match(older[0].search, /page_size=50/);
    await page.getByRole("button", { name: "Load older messages" }).click();
    await shown(page.getByText("Start of conversation"));
    assert.equal(await scroller.locator("ol > li").count(), 120);
    assert.equal(newestReads(), newestBefore, "Older pages never re-read the newest page");
  });
}

{
  const backend = createMessagesBackend({ viewerId: STUDENT.id });
  backend.addThread({ id: threadIds.long });
  const token = "x".repeat(900);
  backend.addMessage(threadIds.long, COUNSELOR, `${"Long body ".repeat(300)}${token}`.slice(0, 4000));
  backend.addMessage(threadIds.long, COUNSELOR, "Line one\n\nLine three\n   indented");
  backend.addMessage(threadIds.long, COUNSELOR, "<b>not bold</b> **not markdown** https://example.test");
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  for (const width of [320, 1440]) {
    await check(`plain-text bodies stay contained at ${width}px`, threadPath(threadIds.long), world.options({ viewport: { width, height: 800 }, ...(width < 768 ? { device: "narrowPhone" } : {}) }), async (page) => {
      await shown(page.getByText("<b>not bold</b> **not markdown** https://example.test", { exact: true }));
      assert.equal(await history(page).locator("b, strong, a").count(), 0, "Nothing is interpreted as HTML, Markdown or links");
      const multiline = await page.getByText(/^Line one/).innerText();
      assert.equal(multiline, "Line one\n\nLine three\n   indented");
      const overflow = await history(page).evaluate((node) => node.scrollWidth - node.clientWidth);
      assert.ok(overflow <= 1, `The history does not scroll sideways (${overflow}px)`);
      await noHorizontalOverflow(page);
    });
  }
}

// ── Sending and idempotency ───────────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("one Send: one client_message_id, cleared after canonical success, focus kept", threadPath(threadIds.office), world.options(), async (page) => {
    const box = composer(page);
    await shown(box);
    await box.click();
    await page.keyboard.type("First line");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Second line");
    assert.equal(await box.inputValue(), "First line\nSecond line", "Enter adds a line");
    assert.equal(backend.sends().length, 0, "Enter never sends");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("First line\nSecond line"));
    assert.equal(backend.sends().length, 1);
    const [sent] = backend.sends();
    assert.deepEqual(Object.keys(sent.body).sort(), ["body", "client_message_id"]);
    assert.equal(sent.body.body, "First line\nSecond line");
    assert.match(sent.body.client_message_id, /^[0-9a-f-]{36}$/);
    await eventually(async () => (await box.inputValue()) === "", "The composer clears after success");
    assert.equal(await box.evaluate((node) => document.activeElement === node), true, "Focus stays in the composer");
    await eventually(() => history(page).evaluate((node) => node.scrollHeight - node.scrollTop - node.clientHeight <= 2), "Scrolled to the sent Message");

    await page.keyboard.type("Sent with the shortcut");
    await page.keyboard.press(process.platform === "darwin" ? "Meta+Enter" : "Control+Enter");
    await shown(history(page).getByText("Sent with the shortcut"));
    assert.equal(backend.sends().length, 2);
    assert.notEqual(backend.sends()[1].body.client_message_id, sent.body.client_message_id, "The next Message has a new ID");
    assert.ok(!page.url().includes("line"), "No Message text in the URL");
  });
}

{
  const backend = studentWorld();
  let attempts = 0;
  backend.state.onSend = () => (attempts++ === 0 ? "commit-then-network" : undefined);
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("an unconfirmed send retries with the same ID and body and shows one Message", threadPath(threadIds.office), world.options(), async (page) => {
    const box = composer(page);
    await box.fill("Did this arrive?");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByText("Your message could not be confirmed because the connection to COMPASS failed."));
    assert.equal(await box.inputValue(), "Did this arrive?", "The draft is kept");
    assert.equal(await box.getAttribute("readonly"), "", "The unconfirmed text cannot be edited silently");
    await page.getByRole("button", { name: "Retry sending" }).click();
    await shown(history(page).getByText("Did this arrive?"));
    const [first, retry] = backend.sends();
    assert.equal(backend.sends().length, 2);
    assert.equal(retry.body.client_message_id, first.body.client_message_id, "The retry reuses the ID");
    assert.equal(retry.body.body, first.body.body, "The retry reuses the body");
    await page.waitForTimeout(500);
    assert.equal(await history(page).getByText("Did this arrive?", { exact: true }).count(), 1, "One canonical Message");
    await eventually(async () => (await box.inputValue()) === "", "Cleared after the confirmed retry");
    await box.fill("A different message");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("A different message"));
    assert.notEqual(backend.sends()[2].body.client_message_id, first.body.client_message_id, "A new intended Message gets a new ID");
  });
}

{
  const backend = studentWorld();
  backend.state.onSend = () => "network";
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("editing after an unconfirmed send is explicit and uses a new ID", threadPath(threadIds.office), world.options(), async (page) => {
    const box = composer(page);
    await box.fill("First wording");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByRole("button", { name: "Edit message" }));
    backend.state.onSend = null;
    await page.getByRole("button", { name: "Edit message" }).click();
    await shown(page.getByText(/Your edited text will be sent as a new message/));
    assert.equal(await box.evaluate((node) => document.activeElement === node), true);
    await box.fill("Second wording");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("Second wording"));
    const [first, second] = backend.sends();
    assert.notEqual(second.body.client_message_id, first.body.client_message_id);
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a rapid double click sends one intended Message", threadPath(threadIds.office), world.options(), async (page) => {
    const release = backend.holdNextSend();
    await composer(page).fill("Only once");
    await page.getByRole("button", { name: "Send", exact: true }).evaluate((button) => { button.click(); button.click(); });
    await page.getByRole("button", { name: "Sending…" }).dblclick({ force: true }).catch(() => {});
    await page.waitForTimeout(500);
    release();
    await shown(history(page).getByText("Only once"));
    assert.equal(backend.sends().length, 1);
  });
}

{
  const backend = studentWorld();
  backend.state.onSend = (_payload, thread) => {
    thread.status = "RESOLVED";
    return { status: 409, body: { error: { code: "guidance_messages_conflict", message: "This Guidance thread is resolved." } } };
  };
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a send refused because the thread was resolved keeps the draft", threadPath(threadIds.office), world.options(), async (page) => {
    const box = composer(page);
    await box.fill("Keep this text");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByText("This conversation is resolved, so your message was not sent. Your text is still here."));
    await shown(page.getByText("This conversation is resolved.", { exact: true }));
    assert.equal(await box.inputValue(), "Keep this text");
    assert.ok(await page.getByRole("button", { name: "Send", exact: true }).isDisabled());
    await shown(page.getByRole("link", { name: "start a new message" }));
    await page.waitForTimeout(500);
    assert.equal(backend.sends().length, 1, "No automatic resend");
  });
}

// ── Resolve and reopen ────────────────────────────────────────────────────────────────────────

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("staff resolve disables the composer; reopen restores it", threadPath(threadIds.office), world.options(), async (page) => {
    await shown(composer(page));
    // Keyboard activation, so the control has focus to return to in every engine.
    await page.getByRole("button", { name: "Resolve conversation" }).focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("alertdialog", { name: "Resolve this conversation?" });
    await shown(dialog.getByText(/Maria Santos will not be able to send messages here/));
    await dialog.getByRole("button", { name: "Resolve conversation" }).click();
    await hidden(dialog);
    await shown(page.getByText("This conversation is resolved.", { exact: true }));
    await shown(page.getByText("Conversation resolved."));
    assert.equal(await composer(page).getAttribute("readonly"), "");
    const reopen = page.getByRole("button", { name: "Reopen conversation" });
    await shown(reopen);
    assert.equal(await reopen.evaluate((node) => document.activeElement === node), true, "Focus stays on the status control");
    await shown(row(page, threadIds.office).getByText("Resolved"));
    await shown(history(page).getByText("Good afternoon po."));
    await reopen.click();
    await shown(page.getByRole("button", { name: "Resolve conversation" }));
    assert.equal(await composer(page).getAttribute("readonly"), null);
    assert.ok(backend.requests((request) => request.pathname.endsWith("/resolve")).length === 1);
    assert.ok(backend.requests((request) => request.pathname.endsWith("/reopen")).length === 1);
  });
}

{
  const backend = staffWorld();
  backend.addThread({ id: threadIds.resolved, status: "RESOLVED" });
  backend.addMessage(threadIds.resolved, STUDENT, "An earlier concern.", { at: backend.minutesAgo(600) });
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("reopening while another Office conversation is open shows the conflict", threadPath(threadIds.resolved), world.options(), async (page) => {
    await page.getByRole("button", { name: "Reopen conversation" }).click();
    await shown(page.getByText("This conversation cannot be reopened because the Student already has an open Guidance Office conversation."));
    await shown(page.getByText("This conversation is resolved.", { exact: true }));
  });
}

// ── Concealment and privacy ───────────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  backend.addThread({ id: threadIds.hidden });
  backend.addMessage(threadIds.hidden, COUNSELOR, "SECRET OTHER THREAD");
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a guessed or malformed thread URL shows only an unavailable state", threadPath(threadIds.hidden), world.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Conversation unavailable" }));
    assert.equal(await page.getByText("SECRET OTHER THREAD").count(), 0);
    await page.goto(`${baseURL}/portal/messages/not-a-thread`);
    await shown(page.getByRole("heading", { name: "Conversation unavailable" }));
    assert.equal(backend.requests((request) => request.pathname.includes("not-a-thread")).length, 0, "A malformed ID is never requested");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  const MARKER = "CONFIDENTIAL-MARKER-7731";
  await check("Message bodies never reach the URL, history state or browser storage", threadPath(threadIds.office), world.options(), async (page) => {
    await composer(page).fill(`${MARKER} draft`);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText(`${MARKER} draft`));
    await composer(page).fill(`${MARKER} unsent`);
    const stored = await page.evaluate(async () => {
      const dump = (storage) => Object.keys(storage).map((key) => `${key}=${storage.getItem(key)}`).join("\n");
      const databases = typeof indexedDB.databases === "function" ? (await indexedDB.databases()).map((db) => db.name).join(",") : "";
      return { url: location.href, state: JSON.stringify(history.state), local: dump(localStorage), session: dump(sessionStorage), databases };
    });
    for (const [where, value] of Object.entries(stored)) assert.ok(!value.includes(MARKER), `No Message text in ${where}`);
  });
}

{
  const backend = studentWorld();
  const accountA = messagesAccount("STUDENT", { first_name: "Account", last_name: "Alpha" });
  const accountB = messagesAccount("STUDENT", { id: "student-b", first_name: "Account", last_name: "Bravo" });
  const world = messagesWorld(backend, accountA);
  const overlap = `(() => {
    window.__overlap = false;
    new MutationObserver(() => {
      const text = document.body?.innerText ?? "";
      if (text.includes("Account Bravo") && text.includes("Bring your ID")) window.__overlap = true;
    }).observe(document, { subtree: true, childList: true, characterData: true });
  })();`;
  await check("another account never sees the previous account's conversation", threadPath(threadIds.office), world.options({
    initScripts: [overlap],
    beforeNavigate: async (fixture) => { await world.beforeNavigate(fixture); await fixture.page.clock.install(); },
  }), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    await composer(page).fill("Account A draft");
    world.account = accountB;
    backend.state.viewerId = accountB.id;
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("Account Bravo").first());
    await shown(page.getByRole("heading", { name: "Conversation unavailable" }));
    assert.equal(await page.getByText("Bring your ID.").count(), 0, "A's Messages are gone");
    assert.equal(await page.getByText("Account A draft").count(), 0, "A's draft is gone");
    assert.equal(await page.evaluate(() => window.__overlap), false, "A's content never shared the screen with B");
  });
}

{
  const backend = studentWorld();
  const accountA = messagesAccount("STUDENT", { first_name: "Account", last_name: "Alpha" });
  const accountB = messagesAccount("STUDENT", { id: "student-b", first_name: "Account", last_name: "Bravo" });
  const world = messagesWorld(backend, accountA);
  await check("a send that completes after the account changed cannot reach the new account", threadPath(threadIds.office), world.options({
    beforeNavigate: async (fixture) => { await world.beforeNavigate(fixture); await fixture.page.clock.install(); },
  }), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    const release = backend.holdNextSend();
    await composer(page).fill("Late success for A");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByRole("button", { name: "Sending…" }));
    world.account = accountB;
    backend.state.viewerId = accountB.id;
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("Account Bravo").first());
    release();
    await page.waitForTimeout(1_500);
    assert.equal(await page.getByText("Late success for A").count(), 0, "A's confirmed Message never renders for B");
    assert.equal(await page.getByText("Bring your ID.").count(), 0);
  });
}

// ── Realtime, readiness and fallback ──────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("hints reconcile over HTTP: the open thread fully, another thread only in the directory", threadPath(threadIds.office), world.options({ initScripts: [enableRealtime] }), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    await world.ready();
    await eventually(() => backend.reads().length === 1, "Initial read");
    await page.waitForTimeout(500);
    backend.addMessage(threadIds.office, COUNSELOR, "Realtime reply via HTTP");
    const before = { list: backend.requests(isThreadsList).length, detail: backend.requests(isDetail(threadIds.office)).length, history: backend.requests(isHistory(threadIds.office)).length };
    world.changed(threadIds.office);
    await shown(history(page).getByText("Realtime reply via HTTP"));
    await eventually(() => backend.reads().some((request) => request.body.sequence === 4), "The visible new Message is marked read after it loaded");
    assert.ok(backend.requests(isThreadsList).length > before.list);
    assert.ok(backend.requests(isDetail(threadIds.office)).length > before.detail);
    assert.ok(backend.requests(isHistory(threadIds.office)).length > before.history);
    await shown(page.getByText("New message received.", { exact: true }));

    await page.waitForTimeout(500);
    const active = backend.requests(isHistory(threadIds.office)).length;
    const list = backend.requests(isThreadsList).length;
    backend.addMessage(threadIds.counseling, COUNSELOR, "Elsewhere");
    world.changed(threadIds.counseling);
    await shown(row(page, threadIds.counseling).getByText("1 unread"));
    assert.ok(backend.requests(isThreadsList).length > list, "The directory reconciles");
    assert.equal(backend.requests(isHistory(threadIds.office)).length, active, "The open thread's history is not re-read");
    assert.equal(backend.requests(isHistory(threadIds.counseling)).length, 0, "Another thread's Messages are not fetched");
    assert.ok(!backend.reads().some((request) => request.pathname.includes(threadIds.counseling)), "The other thread stays unread");
    assert.equal(world.sockets.length, 1, "Messages adds no WebSocket");
    const wire = world.sockets[0].serverFrames.filter((frame) => frame.type !== "ready");
    assert.ok(wire.every((frame) => Object.keys(frame).sort().join() === "thread_id,type,v"), "Hints carry no content");
  });
}

{
  const backend = longWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a new Message while reading older history offers New messages without moving the reader", threadPath(threadIds.long), world.options({ initScripts: [enableRealtime] }), async (page) => {
    await shown(page.getByText("Message number 120", { exact: true }));
    await world.ready();
    await history(page).evaluate((node) => { node.scrollTop = 0; node.dispatchEvent(new Event("scroll")); });
    const before = await history(page).evaluate((node) => node.scrollTop);
    const reads = backend.reads().length;
    backend.addMessage(threadIds.long, COUNSELOR, "Arrived while reading");
    world.changed(threadIds.long);
    const jump = page.getByRole("button", { name: "New messages" });
    await shown(jump);
    assert.equal(await history(page).evaluate((node) => node.scrollTop), before, "The reader is not moved");
    await page.waitForTimeout(500);
    assert.equal(backend.reads().length, reads, "Unseen Messages are not marked read");
    await jump.click();
    await eventually(() => history(page).evaluate((node) => node.scrollHeight - node.scrollTop - node.clientHeight <= 2), "Jumps to the newest Message");
    await eventually(() => backend.reads().some((request) => request.body.sequence === 121), "Read once it is in view");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a fresh ready reconciles the directory, the open thread and its newest page", threadPath(threadIds.office), world.options({ initScripts: [enableRealtime] }), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    await world.ready();
    await page.waitForTimeout(500);
    backend.addMessage(threadIds.office, COUNSELOR, "Missed while disconnected");
    await world.sockets[0].route.close({ code: 4000, reason: "lifetime_expired" });
    await eventually(() => world.sockets.length === 2 && world.sockets[1].serverFrames.length > 0, "Reconnected and ready");
    await shown(history(page).getByText("Missed while disconnected"));
    assert.ok(world.sockets.every((socket) => socket.serverFrames.every((frame) => frame.type === "ready")), "Healed without a hint");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a burst of hints collapses into a bounded reconciliation", "/portal/messages", world.options({ initScripts: [enableRealtime] }), async (page) => {
    await shown(row(page, threadIds.office));
    await world.ready();
    await page.waitForTimeout(800);
    const before = backend.requests(isThreadsList).length;
    for (let index = 0; index < 25; index += 1) world.changed(threadIds.counseling);
    await page.waitForTimeout(2_000);
    const after = backend.requests(isThreadsList).length - before;
    assert.ok(after >= 1 && after <= 3, `25 hints caused ${after} directory reads`);
  });
}

for (const mode of ["disabled", "unavailable"]) {
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  if (mode === "unavailable") {
    world.overrides["POST /api/v1/realtime/tickets"] = ({ reply }) => reply({ error: { code: "realtime_unavailable", message: "Synthetic" } }, 503);
  }
  await check(`realtime ${mode}: Messages poll about every 8 seconds and pause while hidden`, threadPath(threadIds.office), world.options({
    initScripts: [controllableVisibility(), ...(mode === "unavailable" ? [enableRealtime] : [])],
    beforeNavigate: async (fixture) => { await world.beforeNavigate(fixture); await fixture.page.clock.install(); },
  }), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    await page.waitForTimeout(500);
    backend.addMessage(threadIds.office, COUNSELOR, "Arrived by polling");
    await page.clock.fastForward(8_100);
    await shown(history(page).getByText("Arrived by polling"));
    await page.evaluate(() => window.__setVisibility("hidden"));
    await page.waitForTimeout(300);
    const hiddenBefore = backend.requests().length;
    await page.clock.fastForward(40_000);
    await page.waitForTimeout(500);
    assert.equal(backend.requests().length, hiddenBefore, "A hidden tab does not poll");
    await page.evaluate(() => window.__setVisibility("visible"));
    await eventually(() => backend.requests(isThreadsList).length > 0 && backend.requests().length > hiddenBefore, "Becoming visible reconciles promptly");
    assert.equal(world.sockets.length, 0, "No socket");
    assert.equal(await page.locator("#main-content [role=alert]").count(), 0, "No transport error is shown");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a live socket keeps only a 60-second safety poll", "/portal/messages", world.options({
    initScripts: [enableRealtime],
    beforeNavigate: async (fixture) => { await world.beforeNavigate(fixture); await fixture.page.clock.install(); },
  }), async (page) => {
    await shown(row(page, threadIds.office));
    await world.ready();
    await page.waitForTimeout(800);
    const before = backend.requests(isThreadsList).length;
    await page.clock.fastForward(20_000);
    await page.waitForTimeout(500);
    assert.equal(backend.requests(isThreadsList).length, before, "No 8-second poll while live");
    await page.clock.fastForward(41_000);
    await eventually(() => backend.requests(isThreadsList).length > before, "The safety poll runs");
  });
}

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("two tabs of one account: a send reaches the other tab over HTTP; reads stay private", threadPath(threadIds.office), world.options({ initScripts: [enableRealtime] }), async (page, { context }) => {
    await shown(history(page).getByText("Bring your ID."));
    const second = await context.newPage();
    await second.addInitScript({ content: enableRealtime });
    await second.goto(`${baseURL}${threadPath(threadIds.office)}`);
    await shown(history(second).getByText("Bring your ID."));
    await eventually(() => world.sockets.length === 2 && world.sockets.every((socket) => socket.serverFrames.length > 0), "One ready socket per tab");
    await composer(page).fill("Sent from tab A");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("Sent from tab A"));
    world.changed(threadIds.office);
    await shown(history(second).getByText("Sent from tab A"));
    assert.equal(world.sockets.length, 2, "Exactly one socket per tab");
    assert.equal(await page.getByText(/seen|read by/i).count(), 0, "No read receipt in tab A");
    assert.equal(await second.getByText(/seen|read by/i).count(), 0);
  });
}

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("two tabs of one staff account: resolving in one closes the composer in the other", threadPath(threadIds.office), world.options({ initScripts: [enableRealtime] }), async (page, { context }) => {
    await shown(composer(page));
    const second = await context.newPage();
    await second.addInitScript({ content: enableRealtime });
    await second.goto(`${baseURL}${threadPath(threadIds.office)}`);
    await shown(composer(second));
    await eventually(() => world.sockets.length === 2 && world.sockets.every((socket) => socket.serverFrames.length > 0), "One ready socket per tab");
    await page.getByRole("button", { name: "Resolve conversation" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Resolve conversation" }).click();
    await shown(page.getByText("This conversation is resolved.", { exact: true }));
    world.changed(threadIds.office);
    await shown(second.getByText("This conversation is resolved.", { exact: true }));
  });
}

// ── Responsive layout and focus ───────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("phone: directory, then conversation with Back to Messages; focus follows", "/portal/messages", world.options({ device: "phone" }), async (page) => {
    await shown(row(page, threadIds.office));
    assert.equal(await composer(page).count(), 0, "Only the directory on the directory route");
    await row(page, threadIds.office).click();
    await page.waitForURL(new RegExp(`${threadIds.office}$`));
    await shown(composer(page));
    await hidden(row(page, threadIds.office));
    await eventually(() => page.evaluate(() => document.activeElement?.id === "guidance-conversation-heading"), "Focus moves to the conversation heading");
    const box = await composer(page).boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box && box.y + box.height <= viewport.height, "The composer is on screen");
    await page.getByRole("link", { name: "Back to Messages" }).click();
    await page.waitForURL(/\/portal\/messages$/);
    await shown(row(page, threadIds.office));
    await eventually(() => row(page, threadIds.office).evaluate((node) => document.activeElement === node), "Focus returns to the conversation's row");
  });
}

for (const device of ["desktop", "phone"]) {
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check(`an E-Counseling call dock keeps the composer in reach (${device})`, threadPath(threadIds.office), world.options({ device }), async (page) => {
    await shown(composer(page));
    // The portal call dock publishes its height and floats at the bottom; stand in for it.
    await page.evaluate(() => {
      const dock = document.createElement("div");
      dock.setAttribute("data-call-dock", "");
      dock.style.cssText = "position:fixed;left:0;right:0;bottom:16px;height:72px;";
      document.body.append(dock);
      document.documentElement.style.setProperty("--call-dock-height", "72px");
    });
    await page.waitForTimeout(200);
    const box = await page.getByRole("button", { name: "Send", exact: true }).boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.y + box.height <= viewport.height - 72 - 16, `Send stays above the dock (${box.y + box.height} of ${viewport.height})`);
    await noHorizontalOverflow(page);
  });
}

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("no horizontal overflow from 320px to 1440px", "/portal/messages", world.options(), async (page) => {
    for (const width of [320, 375, 390, 393, 430, 768, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      for (const path of ["/portal/messages", threadPath(threadIds.office), "/portal/messages/new"]) {
        await page.goto(`${baseURL}${path}`);
        await shown(page.getByRole("heading", { name: path.endsWith("/new") ? "New message" : path.endsWith("messages") ? "Messages" : "Maria Santos" }).first());
        await noHorizontalOverflow(page);
      }
      const split = await page.evaluate(() => getComputedStyle(document.getElementById("guidance-messages-heading").closest(".flex-col")).display !== "none");
      assert.equal(split, width >= 768, `${width}px ${width >= 768 ? "shows" : "hides"} the directory beside a conversation`);
    }
  });
}

// ── New conversations ─────────────────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  backend.state.threads.get(threadIds.office).status = "RESOLVED";
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("Student: a first Message to the Guidance Office, then to a Counseling relationship", "/portal/messages", world.options(), async (page) => {
    await page.getByRole("link", { name: "New message" }).first().click();
    await shown(page.getByRole("radio", { name: /Guidance Office/ }));
    assert.ok(await page.getByRole("radio", { name: /Guidance Office/ }).isChecked(), "The Guidance Office is offered first");
    await shown(page.getByRole("radio", { name: /Ana Cruz/ }));
    await composer(page).fill("Hello Guidance Office");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.waitForURL(/\/portal\/messages\/a0000000-0000-4000-8000-000000000100$/);
    await shown(history(page).getByText("Hello Guidance Office"));
    const [office] = backend.requests((request) => request.method === "POST" && request.pathname === "/api/v1/guidance-messages/office-thread");
    assert.deepEqual(Object.keys(office.body).sort(), ["body", "client_message_id"], "No Counselor, College or handler is sent");

    await page.getByRole("link", { name: "New message" }).first().click();
    await page.getByRole("radio", { name: /Ana Cruz/ }).check();
    await composer(page).fill("Hello Counselor");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.waitForURL(new RegExp(`${threadIds.counseling}$`));
    await shown(history(page).getByText("Hello Counselor"));
    const [counseling] = backend.requests((request) => request.method === "POST" && request.pathname.endsWith("/counseling-thread"));
    assert.equal(counseling.pathname, `/api/v1/guidance-messages/appointments/${appointmentId}/counseling-thread`);
    assert.equal(backend.requests((request) => request.pathname.startsWith("/api/v1/accounts")).length, 0);
  });
}

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("staff: explicit Student search, first Office Message, reply in the returned thread", "/portal/messages/new", world.options(), async (page, { requests }) => {
    await shown(page.getByRole("radio", { name: /John Reyes/ }));
    const searches = () => backend.requests((request) => request.pathname.endsWith("/eligible-students"));
    const initial = searches().length;
    await page.getByLabel("Search eligible Students").fill("John");
    await page.waitForTimeout(800);
    assert.equal(searches().length, initial, "Typing alone does not search");
    await page.getByLabel("Search eligible Students").press("Enter");
    await eventually(() => searches().some((request) => request.search.includes("search=John")), "Search runs on Enter");
    assert.match(searches().at(-1).search, /page=1/);
    await page.getByRole("radio", { name: /John Reyes/ }).check();
    await composer(page).fill("Hello John");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.waitForURL(/\/portal\/messages\/a0000000-0000-4000-8000-000000000100$/);
    await shown(history(page).getByText("Hello John"));
    const [opened] = backend.requests((request) => request.method === "POST" && request.pathname.endsWith("/office-thread"));
    assert.equal(opened.pathname, `/api/v1/guidance-messages/students/${OTHER_STUDENT.id}/office-thread`);
    await composer(page).fill("A follow-up reply");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("A follow-up reply"));
    assert.equal(requests.filter((request) => request.pathname.startsWith("/api/v1/accounts")).length, 0, "Never the Accounts directory");
    assert.equal(backend.requests((request) => request.pathname.endsWith("/recipient-options")).length, 0, "No Counselor directory");
  });
}

{
  const backend = staffWorld();
  const world = messagesWorld(backend, messagesAccount("COUNSELOR"));
  await check("staff: a Student with an open Office conversation continues in it", "/portal/messages/new", world.options(), async (page) => {
    await page.getByRole("radio", { name: /Maria Santos/ }).check();
    await composer(page).fill("Continuing the open conversation");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.waitForURL(new RegExp(`${threadIds.office}$`));
    await shown(history(page).getByText("Continuing the open conversation"));
    await shown(history(page).getByText("Good afternoon po."));
  });
}

// ── Unsaved drafts ────────────────────────────────────────────────────────────────────────────

{
  const backend = studentWorld();
  const world = messagesWorld(backend, messagesAccount("STUDENT"));
  await check("a nonblank draft asks before leaving; an empty one does not", threadPath(threadIds.office), world.options(), async (page) => {
    const dialogs = [];
    page.on("dialog", async (dialog) => { dialogs.push(dialog.message()); await dialog.dismiss(); });
    await composer(page).fill("Unsent words");
    await row(page, threadIds.counseling).click();
    await eventually(() => dialogs.length === 1, "Leaving asks first");
    assert.equal(dialogs[0], "Discard your unsent message?");
    assert.match(page.url(), new RegExp(`${threadIds.office}$`));
    assert.equal(await composer(page).inputValue(), "Unsent words");
    await composer(page).fill("");
    await row(page, threadIds.counseling).click();
    await page.waitForURL(new RegExp(`${threadIds.counseling}$`));
    assert.equal(dialogs.length, 1, "An empty composer leaves without asking");
  });
}

await finish();
