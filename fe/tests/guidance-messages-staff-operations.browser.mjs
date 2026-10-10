// Guidance Messages staff operations (ADR-104) in a real browser: Office handler assignment, the
// Message template picker in every staff composer, and the templates page. Every API call is
// answered by the synthetic backends in support/, and E-Counseling uses the fake Call Object. No
// account, record, key, template, Message or Daily room is real.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointmentPath, contextualRoutes, ecounselingPath } from "./support/guidance-contextual-fixtures.mjs";
import {
  LONG_STAFF,
  messagesAccount,
  sessionFor,
  staffWorld,
  studentWorld,
  threadIds,
} from "./support/guidance-messages-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow } = await createBrowserHarness("guidance-messages-staff-operations");

const OFFICE = `/portal/messages/${threadIds.office}`;
const COUNSELING = `/portal/messages/${threadIds.counseling}`;
const TEMPLATES_PAGE = "/portal/messages/templates";
const FOLLOW_UP = "We received your message.\nA Guidance staff member will follow up with you.";
const REMINDER = "Good day. Please visit the Guidance and Counseling Office during office hours.";

async function eventually(condition, message, timeout = 10_000) {
  const started = Date.now();
  while (!(await condition())) {
    if (Date.now() - started > timeout) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

const composer = (scope) => scope.getByRole("textbox", { name: /^Message/ });
const history = (scope) => scope.getByRole("region", { name: "Conversation history" });
const templatesButton = (scope) => scope.getByRole("button", { name: "Templates", exact: true });
const picker = (page) => page.getByRole("dialog", { name: "Templates" });
const assignDialog = (page) => page.getByRole("dialog", { name: "Assign conversation" });
// The open conversation's header; the directory beside it also names each handler.
const conversation = (page) => page.locator("header", { has: page.locator("#guidance-conversation-heading") });

/** A signed-in account the test can replace, with its synthetic Messages backend. */
function world(backend, account, extraHandler = null) {
  const value = { account, backend };
  value.overrides = {
    "/api/v1/auth/session": ({ reply }) => reply(sessionFor(value.account)),
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: `${value.account.first_name} ${value.account.last_name}`, photo: null }),
  };
  value.handler = async (args) => (await backend.handler(args)) || (extraHandler ? await extraHandler(args) : false);
  value.options = (extra = {}) => ({ handler: value.handler, overrides: value.overrides, ...extra });
  return value;
}

function withTemplates(backend) {
  backend.addTemplate({ name: "Office follow-up", body: FOLLOW_UP });
  backend.addTemplate({ name: "Appointment reminder", body: REMINDER });
  backend.addTemplate({ name: "Retired wording", body: "This one is archived.", status: "ARCHIVED" });
  return backend;
}

/** Refetches the session the way a long-lived tab does, after the 30-second staleTime. */
async function refreshSession(page) {
  await page.clock.fastForward(31_000);
  await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
}

const withClock = (value) => ({ beforeNavigate: async ({ page }) => { await page.clock.install(); }, ...value });

async function choose(page, name) {
  await templatesButton(page).click();
  await shown(picker(page).getByRole("button", { name }));
  await picker(page).getByRole("button", { name }).click();
}

// ── Office handler assignment ─────────────────────────────────────────────────────────────────

{
  const backend = staffWorld();
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("Office thread: Assigned to + Change opens the thread's eligible staff, never Accounts", OFFICE, value.options(), async (page, { requests }) => {
    await shown(conversation(page).getByText("Assigned to Lea Ramos"));
    const historyNode = await history(page).elementHandle();
    await page.getByRole("button", { name: "Change assignment" }).click();
    const dialog = assignDialog(page);
    await shown(dialog.getByText("Assignment shows who follows up. It does not change who can read this conversation."));
    await shown(dialog.getByRole("radio", { name: /Lea Ramos/ }));
    assert.match(await dialog.getByText(/Guidance Services Staff · Currently assigned/).first().innerText(), /Currently assigned/);
    // Development mounts twice, so count from what the dialog has already asked.
    const initial = backend.handlerLists().length;
    assert.ok(initial >= 1);
    assert.ok(backend.handlerLists().every((request) => request.pathname === `/api/v1/guidance-messages/threads/${threadIds.office}/eligible-handlers`));
    assert.equal(requests.filter((request) => request.pathname.startsWith("/api/v1/accounts")).length, 0, "The Accounts directory is never asked");

    await dialog.getByRole("searchbox", { name: "Search staff" }).fill("maria");
    await page.waitForTimeout(800);
    assert.equal(backend.handlerLists().length, initial, "Typing alone asks nothing");
    await dialog.getByRole("button", { name: "Search", exact: true }).click();
    await eventually(() => backend.handlerLists().length > initial, "Search asks");
    assert.match(backend.handlerLists().at(-1).search, /search=maria/);
    assert.match(backend.handlerLists().at(-1).search, /page=1/);
    await shown(dialog.getByRole("radio", { name: new RegExp(LONG_STAFF.display_name) }));
    assert.equal(await dialog.getByRole("radio").count(), 1);

    await dialog.getByRole("radio", { name: new RegExp(LONG_STAFF.display_name) }).check();
    await page.waitForTimeout(400);
    assert.equal(backend.assigns().length, 0, "Choosing a row assigns nothing");
    const directoryReads = backend.requests((request) => request.method === "GET" && request.pathname.endsWith("/threads")).length;
    const readsBefore = backend.reads().length;
    await dialog.getByRole("button", { name: "Assign", exact: true }).click();
    await hidden(dialog);
    assert.equal(backend.assigns().length, 1);
    assert.deepEqual(backend.assigns()[0].body, { handler_id: LONG_STAFF.id });
    await shown(conversation(page).getByText(`Assigned to ${LONG_STAFF.display_name}`));
    await shown(page.getByText(`Conversation assigned to ${LONG_STAFF.display_name}.`));
    await eventually(
      () => backend.requests((request) => request.method === "GET" && request.pathname.endsWith("/threads")).length > directoryReads,
      "The directory reconciles",
    );
    assert.equal(await historyNode.evaluate((node) => node.isConnected), true, "The conversation stays mounted");
    assert.equal(await history(page).getByText("Good afternoon po.").count(), 1, "History is unchanged");
    assert.equal(backend.reads().length, readsBefore, "Assignment marks nothing read");
    assert.equal(backend.sends().length, 0, "Assignment sends nothing");
  });
}

{
  const backend = staffWorld();
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("choosing the current assignee keeps Assign disabled; Cancel changes nothing", OFFICE, value.options(), async (page) => {
    await page.getByRole("button", { name: "Change assignment" }).click();
    const dialog = assignDialog(page);
    await dialog.getByRole("radio", { name: /Lea Ramos/ }).check();
    assert.equal(await dialog.getByRole("button", { name: "Assign", exact: true }).isDisabled(), true);
    await dialog.getByRole("radio", { name: /Ana Cruz/ }).check();
    assert.equal(await dialog.getByRole("button", { name: "Assign", exact: true }).isDisabled(), false);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await hidden(dialog);
    assert.equal(backend.assigns().length, 0);
    assert.equal(await page.getByRole("button", { name: "Change assignment" }).evaluate((node) => document.activeElement === node), true, "Focus returns to Change");
  });
}

{
  const backend = staffWorld();
  backend.state.onAssign = (body) => {
    backend.state.handlers = backend.state.handlers.filter((item) => item.id !== body.handler_id);
    return { status: 422, body: { error: { code: "invalid_guidance_message_input", message: "Choose an eligible Guidance handler." } } };
  };
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("a stale candidate is refused, the list refreshes and nothing is retried", OFFICE, value.options(), async (page) => {
    await page.getByRole("button", { name: "Change assignment" }).click();
    const dialog = assignDialog(page);
    await dialog.getByRole("radio", { name: new RegExp(LONG_STAFF.display_name) }).check();
    const listed = backend.handlerLists().length;
    await dialog.getByRole("button", { name: "Assign", exact: true }).click();
    await shown(dialog.getByText(/can no longer be assigned this conversation\. The list was refreshed/));
    await eventually(() => backend.handlerLists().length > listed, "The eligible list is read again");
    await hidden(dialog.getByRole("radio", { name: new RegExp(LONG_STAFF.display_name) }));
    await page.waitForTimeout(600);
    assert.equal(backend.assigns().length, 1, "No automatic retry");
    assert.equal(await dialog.getByRole("button", { name: "Assign", exact: true }).isDisabled(), true);
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await shown(conversation(page).getByText("Assigned to Lea Ramos"));
  });
}

{
  const backend = staffWorld();
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("Counseling threads have no assignment control", COUNSELING, value.options(), async (page) => {
    await shown(history(page).getByText("Thank you for today."));
    assert.equal(await page.getByRole("button", { name: /Change assignment|Assign conversation/ }).count(), 0);
    assert.equal(await conversation(page).getByText(/Assigned to/).count(), 0);
    assert.equal(backend.handlerLists().length, 0);
  });
}

{
  const backend = studentWorld();
  const value = world(backend, messagesAccount("STUDENT"));
  await check("Students see no assignment, no Templates and make no template request", OFFICE, value.options(), async (page) => {
    await shown(history(page).getByText("Bring your ID."));
    assert.equal(await conversation(page).getByText(/Assigned to/).count(), 0);
    assert.equal(await page.getByRole("button", { name: /Change assignment/ }).count(), 0);
    assert.equal(await templatesButton(page).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Templates" }).count(), 0);
    await page.goto(`${baseURL}/portal/messages/new`);
    await shown(page.getByRole("heading", { name: "New message" }));
    assert.equal(await templatesButton(page).count(), 0);
    await page.goto(`${baseURL}${TEMPLATES_PAGE}`);
    await shown(page.getByRole("heading", { name: "Message templates unavailable" }));
    assert.equal(backend.templateRequests().length, 0, "No template API call");
    assert.equal(backend.handlerLists().length, 0);
  });
}

{
  const backend = staffWorld();
  backend.state.threads.get(threadIds.office).assigned_to = { id: LONG_STAFF.id, display_name: LONG_STAFF.display_name };
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("long staff names wrap in the header and picker from 320px to 1440px", OFFICE, value.options(), async (page) => {
    for (const width of [320, 375, 390, 430, 768, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      await shown(conversation(page).getByText(`Assigned to ${LONG_STAFF.display_name}`));
      await noHorizontalOverflow(page);
      await page.getByRole("button", { name: "Change assignment" }).click();
      await shown(assignDialog(page).getByRole("radio", { name: new RegExp(LONG_STAFF.display_name) }));
      await noHorizontalOverflow(page);
      const box = await assignDialog(page).boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= width, `The dialog fits at ${width}px`);
      await page.keyboard.press("Escape");
      await hidden(assignDialog(page));
    }
  });
}

{
  const backend = staffWorld();
  const account = messagesAccount("COUNSELOR");
  const value = world(backend, account);
  await check("losing Messages manage hides Change and Templates after the session refreshes", OFFICE, value.options(withClock()), async (page) => {
    await shown(page.getByRole("button", { name: "Change assignment" }));
    await shown(templatesButton(page));
    value.account = { ...account, capabilities: account.capabilities.filter((code) => code !== "guidance_messages.manage") };
    await refreshSession(page);
    await hidden(page.getByRole("button", { name: "Change assignment" }));
    await shown(conversation(page).getByText("Assigned to Lea Ramos"));
    assert.equal(await templatesButton(page).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Templates" }).count(), 0);
  });
}

// ── Template picker ───────────────────────────────────────────────────────────────────────────

{
  const backend = withTemplates(staffWorld());
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("Office reply: a template fills a blank draft, appends to text, stays editable and never sends", OFFICE, value.options(), async (page) => {
    const box = composer(page);
    await shown(box);
    await templatesButton(page).click();
    await shown(picker(page).getByRole("button", { name: "Appointment reminder" }));
    assert.deepEqual(
      await picker(page).getByRole("list").getByRole("button").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-labelledby") && document.getElementById(node.getAttribute("aria-labelledby")).textContent)),
      ["Appointment reminder", "Office follow-up"],
      "Active templates only, by name",
    );
    assert.equal(await picker(page).getByText("Retired wording").count(), 0, "Archived templates are not offered");
    await picker(page).getByRole("button", { name: "Office follow-up" }).click();
    await hidden(picker(page));
    assert.equal(await box.inputValue(), FOLLOW_UP, "A blank draft becomes the template");
    await eventually(() => box.evaluate((node) => document.activeElement === node), "Focus returns to the draft");
    assert.equal(await box.evaluate((node) => node.selectionStart === node.value.length), true, "The caret is at the end");
    assert.equal(backend.sends().length, 0, "Nothing is sent");

    await page.keyboard.type(" Thank you.");
    await choose(page, "Appointment reminder");
    await hidden(picker(page));
    const combined = `${FOLLOW_UP} Thank you.\n\n${REMINDER}`;
    assert.equal(await box.inputValue(), combined, "A nonblank draft is kept and the template follows a blank line");
    await box.fill(combined.replace("office hours", "office hours this Friday"));
    assert.equal(backend.sends().length, 0);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const edited = combined.replace("office hours", "office hours this Friday");
    await shown(history(page).getByText("office hours this Friday", { exact: false }));
    assert.equal(backend.sends().length, 1);
    const [sent] = backend.sends();
    assert.deepEqual(Object.keys(sent.body).sort(), ["body", "client_message_id"], "An ordinary send: no template field");
    assert.equal(sent.body.body, edited);
    assert.match(sent.body.client_message_id, /^[0-9a-f-]{36}$/);
    assert.equal(backend.state.messages.get(threadIds.office).at(-1).body, edited, "The stored Message is the edited text");
  });
}

{
  const backend = staffWorld();
  backend.addTemplate({ name: "Long wording", body: "a".repeat(3000) });
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("a template that would pass 4,000 characters is refused and the draft is unchanged", OFFICE, value.options(), async (page) => {
    const draft = "b".repeat(1500);
    await composer(page).fill(draft);
    await choose(page, "Long wording");
    await shown(picker(page).getByRole("alert").getByText("This template would make the message longer than 4,000 characters."));
    await page.keyboard.press("Escape");
    await hidden(picker(page));
    assert.equal(await composer(page).inputValue(), draft, "Not truncated, not replaced");
    assert.equal(await templatesButton(page).evaluate((node) => document.activeElement === node), true, "Cancelling returns focus to Templates");
  });
}

{
  const backend = withTemplates(staffWorld());
  let attempts = 0;
  backend.state.onSend = () => (attempts++ === 0 ? "commit-then-network" : undefined);
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("an unconfirmed send locks Templates; Retry keeps the exact ID and body", OFFICE, value.options(), async (page) => {
    await choose(page, "Office follow-up");
    await hidden(picker(page));
    const release = backend.holdNextSend();
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByRole("button", { name: "Sending…" }));
    assert.equal(await templatesButton(page).isDisabled(), true, "Unavailable while sending");
    release();
    await shown(page.getByRole("button", { name: "Retry sending" }));
    assert.equal(await templatesButton(page).isDisabled(), true, "Unavailable while unconfirmed");
    await page.getByRole("button", { name: "Retry sending" }).click();
    await shown(history(page).getByText("A Guidance staff member will follow up with you.", { exact: false }));
    const [first, retry] = backend.sends();
    assert.equal(retry.body.client_message_id, first.body.client_message_id);
    assert.equal(retry.body.body, FOLLOW_UP);
    assert.equal(backend.state.messages.get(threadIds.office).filter((message) => message.body === FOLLOW_UP).length, 1, "One Message");
    await eventually(async () => !(await templatesButton(page).isDisabled()), "Available again after the confirmed send");
  });
}

{
  const backend = withTemplates(staffWorld());
  backend.state.onSend = () => "network";
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("Edit message sets the unconfirmed intent aside; a template then starts a new Message", OFFICE, value.options(), async (page) => {
    await composer(page).fill("First wording");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByRole("button", { name: "Edit message" }));
    assert.equal(await templatesButton(page).isDisabled(), true);
    backend.state.onSend = null;
    await page.getByRole("button", { name: "Edit message" }).click();
    assert.equal(await templatesButton(page).isDisabled(), false);
    await choose(page, "Appointment reminder");
    await hidden(picker(page));
    assert.equal(await composer(page).inputValue(), `First wording\n\n${REMINDER}`);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText(REMINDER, { exact: false }));
    const [first, second] = backend.sends();
    assert.notEqual(second.body.client_message_id, first.body.client_message_id, "The edited text is a new intended Message");
  });
}

{
  const backend = withTemplates(staffWorld());
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("the exact Counselor's Counseling reply offers the same Templates", COUNSELING, value.options(), async (page) => {
    await choose(page, "Office follow-up");
    await hidden(picker(page));
    assert.equal(await composer(page).inputValue(), FOLLOW_UP);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(page).getByText("A Guidance staff member will follow up with you.", { exact: false }));
    assert.equal(backend.sends()[0].pathname, `/api/v1/guidance-messages/threads/${threadIds.counseling}/messages`);
  });
}

{
  const backend = withTemplates(staffWorld());
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("staff New message: Templates wait for a Student, then fill the first Office Message", "/portal/messages/new", value.options(), async (page) => {
    await shown(page.getByRole("radio", { name: /Maria Santos/ }));
    assert.equal(await templatesButton(page).isDisabled(), true, "No recipient yet");
    await page.getByRole("radio", { name: /John Reyes/ }).check();
    await choose(page, "Office follow-up");
    await hidden(picker(page));
    assert.equal(await composer(page).inputValue(), FOLLOW_UP);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await page.waitForURL(/\/portal\/messages\/a0000000-/);
    const opened = backend.requests((request) => request.method === "POST" && request.pathname.endsWith("/office-thread"));
    assert.equal(opened.length, 1);
    assert.deepEqual(Object.keys(opened[0].body).sort(), ["body", "client_message_id"]);
    assert.equal(opened[0].body.body, FOLLOW_UP);
  });
}

{
  const backend = staffWorld();
  for (let index = 1; index <= 25; index += 1) backend.addTemplate({ name: `Template ${String(index).padStart(2, "0")}`, body: `Generic wording ${index}.` });
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("picker search is explicit, never submits the Message, and loads more on request", OFFICE, value.options(), async (page) => {
    await composer(page).fill("Draft stays");
    await templatesButton(page).click();
    await shown(picker(page).getByRole("button", { name: "Template 01" }));
    const lists = () => backend.templateRequests().filter((request) => request.method === "GET").length;
    const before = lists();
    assert.equal(await picker(page).getByRole("list").getByRole("button").count(), 20);
    await picker(page).getByRole("button", { name: "Show more templates" }).click();
    await shown(picker(page).getByRole("button", { name: "Template 25" }));
    assert.match(backend.templateRequests().at(-1).search, /page=2/);
    await picker(page).getByRole("searchbox", { name: "Search templates" }).fill("Template 1");
    await page.waitForTimeout(600);
    assert.equal(lists(), before + 1, "Typing alone asks nothing");
    await page.keyboard.press("Enter");
    await eventually(() => lists() === before + 2, "Enter searches once");
    assert.match(backend.templateRequests().at(-1).search, /search=Template\+1|search=Template%201/);
    await eventually(async () => (await picker(page).getByRole("list").getByRole("button").count()) === 10, "Template 10 to 19 match");
    assert.equal(backend.sends().length, 0, "The picker's search never sends the Message");
    await picker(page).getByRole("searchbox", { name: "Search templates" }).fill("nothing like this");
    await picker(page).getByRole("button", { name: "Search", exact: true }).click();
    await shown(picker(page).getByText("No templates match this search."));
    await page.keyboard.press("Escape");
    assert.equal(await composer(page).inputValue(), "Draft stays");
  });
}

{
  const backend = staffWorld();
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("an empty picker says so and offers the templates page to managers", OFFICE, value.options(), async (page) => {
    await templatesButton(page).click();
    await shown(picker(page).getByText("No message templates yet."));
    await picker(page).getByRole("link", { name: "Manage templates" }).click();
    await page.waitForURL(new RegExp(`${TEMPLATES_PAGE}$`));
    await shown(page.getByRole("heading", { name: "Message templates", level: 1 }));
  });
}

{
  const backend = withTemplates(staffWorld());
  const accountA = messagesAccount("COUNSELOR", { first_name: "Account", last_name: "Alpha" });
  const accountB = messagesAccount("GUIDANCE_SERVICES_STAFF", { id: "staff-b", first_name: "Account", last_name: "Bravo" });
  const value = world(backend, accountA);
  await check("an account change drops the previous account's templates and template-filled draft", OFFICE, value.options(withClock()), async (page) => {
    await choose(page, "Office follow-up");
    await hidden(picker(page));
    assert.equal(await composer(page).inputValue(), FOLLOW_UP);
    const before = backend.templateRequests().length;
    value.account = accountB;
    backend.state.viewerId = accountB.id;
    await refreshSession(page);
    await shown(page.getByText("Account Bravo").first());
    await eventually(async () => (await composer(page).inputValue()) === "", "A's draft is gone");
    await templatesButton(page).click();
    await shown(picker(page).getByRole("button", { name: "Office follow-up" }));
    assert.ok(backend.templateRequests().length > before, "B's picker asks again; A's cached list was removed");
  });
}

// ── Contextual Counselor composer ─────────────────────────────────────────────────────────────

{
  const backend = withTemplates(staffWorld());
  backend.state.threads.delete(threadIds.counseling);
  const joins = { count: 0 };
  const routes = contextualRoutes({ joins });
  const value = world(backend, messagesAccount("COUNSELOR"), routes);
  const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
  const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
  await check("E-Counseling: a template fills the first contextual Message while the call keeps running", ecounselingPath, value.options({ fakeDaily: true }), async (page) => {
    const stage = page.getByRole("region", { name: "Video call" });
    await page.getByRole("button", { name: "Join session", exact: true }).click();
    await shown(stage.getByText(/^Waiting for /).first());
    await fake(page, "remoteJoin", { userId: "student", name: "Remote" });
    await shown(stage.getByText("Connected", { exact: true }));
    const counts = async () => ({
      created: await page.evaluate(() => window.__COMPASS_FAKE_DAILY__.instances.length),
      joins: await fakeCount(page, "join"),
      leaves: await fakeCount(page, "leave"),
      destroys: await fakeCount(page, "destroy"),
      appMessages: await fakeCount(page, "sendAppMessage"),
      recordings: await fakeCount(page, "startRecording"),
      transcriptions: await fakeCount(page, "startTranscription"),
    });
    const initial = await counts();
    await page.getByRole("button", { name: /^Messages/ }).click();
    const surface = page.getByRole("complementary", { name: "Messages" });
    await shown(surface.getByText("No Messages conversation has started for this Counseling appointment yet."));
    await templatesButton(surface).click();
    await picker(page).getByRole("button", { name: "Appointment reminder" }).click();
    await hidden(picker(page));
    await eventually(() => composer(surface).evaluate((node) => document.activeElement === node), "Focus returns to the panel's draft");
    await page.keyboard.type(" See you soon.");
    await surface.getByRole("button", { name: "Send", exact: true }).click();
    await shown(history(surface).getByText("See you soon.", { exact: false }));
    const [opened] = backend.opens();
    assert.deepEqual(Object.keys(opened.body).sort(), ["body", "client_message_id"]);
    assert.equal(opened.body.body, `${REMINDER} See you soon.`);
    await shown(stage.getByText("Connected", { exact: true }));
    assert.deepEqual(await counts(), initial, "No call created, joined, left, destroyed, messaged or captured");
    assert.equal(joins.count, 1, "No second credential request");
  });
}

{
  const backend = withTemplates(studentWorld());
  const value = world(backend, messagesAccount("STUDENT"), contextualRoutes());
  await check("a Student's contextual panel has no Templates", appointmentPath, value.options(), async (page) => {
    await page.getByRole("button", { name: /^Messages/ }).click();
    const surface = page.getByRole("complementary", { name: "Messages" });
    await shown(composer(surface));
    assert.equal(await templatesButton(surface).count(), 0);
    assert.equal(backend.templateRequests().length, 0);
  });
}

// ── Templates page ────────────────────────────────────────────────────────────────────────────

{
  const backend = staffWorld();
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("managers reach Templates beside New message; empty state; create with validation", "/portal/messages", value.options(), async (page) => {
    const link = page.getByRole("link", { name: "Templates" });
    await shown(link);
    await link.click();
    await page.waitForURL(new RegExp(`${TEMPLATES_PAGE}$`));
    const main = page.getByRole("main");
    await shown(main.getByText("No message templates yet."));
    await main.getByRole("button", { name: "Create template" }).last().click();
    const editor = page.getByRole("dialog", { name: "Create template" });
    await shown(editor.getByText(/never a Student.s name or details/));
    await editor.getByRole("button", { name: "Create template" }).click();
    await shown(editor.getByText("Enter a template name."));
    await shown(editor.getByText("Write the template text."));
    assert.equal(backend.templateRequests().filter((request) => request.method === "POST").length, 0, "Invalid input is not sent");
    await editor.getByRole("textbox", { name: "Name" }).fill("  Office follow-up  ");
    await editor.getByRole("textbox", { name: "Text" }).fill(FOLLOW_UP);
    await editor.getByRole("button", { name: "Create template" }).click();
    await hidden(editor);
    await shown(page.getByText("Office follow-up created."));
    const created = backend.templateRequests().find((request) => request.method === "POST");
    assert.deepEqual(created.body, { name: "Office follow-up", body: FOLLOW_UP });
    await shown(main.getByRole("heading", { name: "Office follow-up", level: 2 }));

    await main.getByRole("button", { name: "Create template" }).first().click();
    const second = page.getByRole("dialog", { name: "Create template" });
    await second.getByRole("textbox", { name: "Name" }).fill("OFFICE FOLLOW-UP");
    await second.getByRole("textbox", { name: "Text" }).fill("Other generic wording.");
    await second.getByRole("button", { name: "Create template" }).click();
    await shown(second.getByText("Another template already uses this name. Choose a different name."));
    assert.equal(await second.getByRole("textbox", { name: "Name" }).evaluate((node) => document.activeElement === node), true);
  });
}

{
  const backend = withTemplates(staffWorld());
  const value = world(backend, messagesAccount("GUIDANCE_SERVICES_STAFF"));
  await check("edit, archive with confirmation, archived view and restore", TEMPLATES_PAGE, value.options(), async (page) => {
    const main = page.getByRole("main");
    await shown(main.getByRole("heading", { name: "Appointment reminder", level: 2 }));
    assert.equal(await main.getByText("Retired wording").count(), 0, "Archived templates stay in Archived");
    await main.getByRole("button", { name: "Edit Office follow-up" }).click();
    const editor = page.getByRole("dialog", { name: "Edit template" });
    assert.equal(await editor.getByRole("textbox", { name: "Text" }).inputValue(), FOLLOW_UP);
    await editor.getByRole("textbox", { name: "Text" }).fill("We received your message. Thank you.");
    await editor.getByRole("button", { name: "Save changes" }).click();
    await hidden(editor);
    await shown(page.getByText("Office follow-up saved."));
    const patch = backend.templateRequests().find((request) => request.method === "PATCH");
    assert.deepEqual(Object.keys(patch.body).sort(), ["body", "expected_updated_at"], "Only the changed field and the opened version");

    await main.getByRole("button", { name: "Archive Office follow-up" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Archive this template?" });
    await shown(confirm.getByText(/Messages already sent and drafts that already include it do not change/));
    await confirm.getByRole("button", { name: "Archive template" }).click();
    await hidden(confirm);
    await shown(page.getByText("Office follow-up archived."));
    await hidden(main.getByRole("heading", { name: "Office follow-up", level: 2 }));
    await main.getByRole("button", { name: "Archived", exact: true }).click();
    assert.equal(await main.getByRole("button", { name: "Archived", exact: true }).getAttribute("aria-pressed"), "true");
    await shown(main.getByRole("heading", { name: "Office follow-up", level: 2 }));
    await shown(main.getByRole("heading", { name: "Retired wording", level: 2 }));
    assert.equal(await main.getByRole("button", { name: /^Edit / }).count(), 0, "Archived templates are restored before editing");
    await main.getByRole("button", { name: "Restore Office follow-up" }).click();
    await shown(page.getByText("Office follow-up restored."));
    await hidden(main.getByRole("heading", { name: "Office follow-up", level: 2 }));
    await main.getByRole("button", { name: "Active", exact: true }).click();
    await shown(main.getByRole("heading", { name: "Office follow-up", level: 2 }));
    assert.equal(backend.templateRequests().filter((request) => request.method === "DELETE").length, 0, "There is no delete");
  });
}

{
  const backend = withTemplates(staffWorld());
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("unsaved template edits ask before closing the editor or leaving the page", "/portal/messages", value.options(), async (page) => {
    const dialogs = [];
    page.on("dialog", async (dialog) => { dialogs.push(dialog.message()); await dialog.dismiss(); });
    await page.getByRole("link", { name: "Templates" }).click();
    await page.waitForURL(new RegExp(`${TEMPLATES_PAGE}$`));
    await page.getByRole("main").getByRole("button", { name: "Create template" }).first().click();
    const editor = page.getByRole("dialog", { name: "Create template" });
    await editor.getByRole("textbox", { name: "Name" }).fill("Half-written");
    await page.keyboard.press("Escape");
    await shown(editor.getByText("Discard your changes to this template?"));
    await editor.getByRole("button", { name: "Keep editing" }).click();
    assert.equal(await editor.getByRole("textbox", { name: "Name" }).inputValue(), "Half-written");
    await page.evaluate(() => history.back());
    await eventually(() => dialogs.length === 1, "Leaving asks first");
    assert.equal(dialogs[0], "Discard your unsaved template changes?");
    assert.match(page.url(), new RegExp(`${TEMPLATES_PAGE}$`));
    await editor.getByRole("button", { name: "Cancel" }).click();
    await editor.getByRole("button", { name: "Discard changes" }).click();
    await hidden(editor);
    assert.equal(backend.templateRequests().filter((request) => request.method === "POST").length, 0);
  });
}

for (const [label, account] of [
  ["IT Admin", messagesAccount("IT_ADMIN")],
  ["DPO designation", messagesAccount("INSTITUTIONAL_OFFICER", { designations: ["DPO"] })],
  ["a Counselor whose template management was revoked", messagesAccount("COUNSELOR", { capabilities: ["guidance_messages.view", "guidance_messages.manage"] })],
]) {
  const backend = withTemplates(staffWorld());
  const value = world(backend, account);
  await check(`${label} cannot open the templates page`, TEMPLATES_PAGE, value.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Message templates unavailable" }));
    assert.equal(backend.templateRequests().length, 0, "No template request");
    if (account.role === "COUNSELOR") {
      await page.goto(`${baseURL}/portal/messages`);
      await shown(page.getByRole("link", { name: "New message" }));
      assert.equal(await page.getByRole("link", { name: "Templates" }).count(), 0, "No management link");
      await page.goto(`${baseURL}${OFFICE}`);
      await shown(templatesButton(page));
    }
  });
}

{
  const backend = staffWorld();
  backend.addTemplate({ name: "A very long template name that keeps going to test wrapping across narrow phone widths ok", body: "x ".repeat(400) });
  backend.addTemplate({ name: "Office follow-up", body: FOLLOW_UP });
  const value = world(backend, messagesAccount("COUNSELOR"));
  await check("templates page and editor have no horizontal overflow from 320px to 1440px", TEMPLATES_PAGE, value.options(), async (page) => {
    for (const width of [320, 375, 390, 430, 768, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      await shown(page.getByRole("heading", { name: "Office follow-up", level: 2 }));
      await noHorizontalOverflow(page);
      await page.getByRole("button", { name: "Edit Office follow-up" }).click();
      const editor = page.getByRole("dialog", { name: "Edit template" });
      await shown(editor.getByRole("textbox", { name: "Text" }));
      await noHorizontalOverflow(page);
      const box = await editor.boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= width, `The editor fits at ${width}px`);
      await page.keyboard.press("Escape");
      await hidden(editor);
    }
  });
}

await finish();
