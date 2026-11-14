// Synthetic identity and constrained-viewport regressions; no institutional API is contacted.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import {
  COUNSELOR, LONG_STAFF, STUDENT, messagesAccount, relationshipOption, sessionFor,
  studentWorld, staffWorld, threadIds,
} from "./support/guidance-messages-fixtures.mjs";

const { check, shown, screenshot, finish, noHorizontalOverflow, settleFetches, navigate } = await createBrowserHarness("guidance-messages-layout");
const REMINDER = "Share only the details needed for your concern. Never send passwords, verification codes, or payment card details.";
const box = (page) => page.getByRole("textbox", { name: /^Message/ });
const history = (page) => page.getByRole("region", { name: "Conversation history" });
const row = (page, id) => page.locator(`[data-thread-id="${id}"]`);
const path = (id) => `/portal/messages/${id}`;
function options(backend, role = "STUDENT", extra = {}) {
  return { handler: backend.handler, overrides: { "/api/v1/auth/session": sessionFor(messagesAccount(role)) }, ...extra };
}
async function reachable(page, control) {
  await control.scrollIntoViewIfNeeded();
  const bounds = await control.boundingBox();
  const viewport = page.viewportSize();
  assert.ok(bounds && bounds.y >= -1 && bounds.y + bounds.height <= viewport.height + 1, "Control can be scrolled fully into the viewport");
  assert.ok(await control.evaluate((node) => {
    const r = node.getBoundingClientRect();
    return node.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
  }), "Control is not covered by another element");
}
async function layout(page) {
  await shown(box(page));
  await reachable(page, box(page));
  await reachable(page, page.getByRole("button", { name: "Send", exact: true }));
  const form = box(page).locator("xpath=ancestor::form");
  const reminder = form.getByText(REMINDER, { exact: true });
  await shown(reminder);
  assert.ok(await reminder.evaluate((node) => {
    const style = getComputedStyle(node);
    return parseFloat(style.fontSize) >= parseFloat(getComputedStyle(document.documentElement).fontSize) * .875 && node.scrollWidth <= node.clientWidth + 1;
  }), "Reminder has readable secondary text and wraps");
  const regions = await Promise.all([history(page).boundingBox(), form.boundingBox()]);
  assert.ok(regions[0].height >= 95, "History retains a usable scroll region");
  assert.ok(regions[0].y + regions[0].height <= regions[1].y + 1, "History does not overlap the composer");
  await noHorizontalOverflow(page);
}

{
  const backend = studentWorld();
  backend.state.threads.get(threadIds.counseling).counselor = LONG_STAFF;
  // CW-6: two conversations with one Counselor are told apart by their own Appointments.
  backend.addThread({ id: threadIds.long, kind: "COUNSELING", counselor: LONG_STAFF, created: 1200, appointment: "b0000000-0000-4000-8000-000000000002", summary: { reference_code: "APT-2026-0002", starts_at: "2026-10-12T03:00:00Z", ends_at: "2026-10-12T04:00:00Z" } });
  backend.addMessage(threadIds.long, LONG_STAFF, "Synthetic second conversation.");
  await check("desktop identity and distinct conversation Appointments", path(threadIds.counseling), options(backend), async (page, fixture) => {
    await shown(page.getByRole("heading", { name: LONG_STAFF.display_name, exact: true }));
    for (const id of [threadIds.counseling, threadIds.long]) {
      assert.match(await row(page, id).innerText(), /MC[\s\S]*Appointment /);
      assert.ok((await row(page, id).innerText()).includes(LONG_STAFF.display_name));
    }
    assert.notEqual((await row(page, threadIds.counseling).innerText()).split("Appointment ")[1], (await row(page, threadIds.long).innerText()).split("Appointment ")[1]);
    assert.equal(await row(page, threadIds.office).locator("svg.lucide-building2").count(), 1);
    assert.ok(!(await row(page, threadIds.office).innerText()).includes(COUNSELOR.display_name));
    assert.equal(await page.locator("header").filter({ has: page.getByRole("heading", { name: LONG_STAFF.display_name }) }).getByText("MC", { exact: true }).count(), 1);
    assert.equal(await page.getByText(/Counseling Appointment ·/).count(), 0, "No fabricated appointment date in a thread");
    await layout(page);
    await settleFetches(page);
    const guidanceReads = fixture.requests.filter((r) => r.method === "GET" && r.pathname.startsWith("/api/v1/guidance-messages/"));
    assert.ok(guidanceReads.every((r) => r.pathname.endsWith("/threads") || r.pathname.endsWith(`/threads/${threadIds.counseling}`) || r.pathname.endsWith("/messages") || r.pathname.endsWith("/unread-count")), "Only existing workspace reads");
    assert.equal(backend.sends().length, 0);
    await screenshot(page, "desktop-completed");
  });
}

for (const [name, viewport, enlarged] of [
  ["short desktop", { width: 1100, height: 430 }, false],
  ["narrow", { width: 390, height: 640 }, false],
  ["enlarged text", { width: 390, height: 640 }, true],
  ["reduced viewport", { width: 320, height: 350 }, true],
  ["CSS zoom simulation", { width: 780, height: 700 }, "zoom"],
]) {
  const backend = studentWorld();
  backend.state.threads.get(threadIds.counseling).counselor = LONG_STAFF;
  await check(`${name}: composer and reminder remain reachable`, path(threadIds.counseling), options(backend, "STUDENT", { viewport }), async (page) => {
    await shown(box(page));
    const original = await box(page).elementHandle();
    await box(page).fill("Synthetic draft\n".repeat(10));
    if (enlarged === "zoom") await page.evaluate(() => { document.body.style.zoom = "2"; });
    else if (enlarged) await page.evaluate(() => { document.documentElement.style.fontSize = "32px"; });
    await layout(page);
    assert.equal(await box(page).inputValue(), "Synthetic draft\n".repeat(10));
    assert.ok(await original.evaluate((node) => node.isConnected), "Layout keeps the original textarea mounted");
    assert.equal(backend.sends().length, 0, "Layout never sends");
    if (name === "narrow") await screenshot(page, "narrow-completed");
  });
}

{
  const backend = studentWorld();
  backend.state.relationships = [
    relationshipOption({ counselor: LONG_STAFF, starts_at: "2026-11-12T02:00:00Z" }),
    relationshipOption({ counselor: LONG_STAFF, id: "b0000000-0000-4000-8000-000000000002", reference_code: "APT-2026-0002", starts_at: "2026-11-13T03:00:00Z" }),
  ];
  await check("recipient identity, supplied dates, keyboard focus and existing draft behavior", "/portal/messages/new", options(backend, "STUDENT", { viewport: { width: 390, height: 640 } }), async (page) => {
    const choices = page.getByRole("radio");
    await shown(choices.nth(1));
    await choices.first().focus();
    await page.keyboard.press("ArrowDown");
    assert.equal(await choices.nth(1).isChecked(), true);
    const label = choices.nth(1).locator("xpath=parent::label");
    assert.equal(await label.getByText("MC", { exact: true }).count(), 1);
    assert.match(await label.innerText(), /Nov 12, 2026/);
    assert.match(await choices.nth(2).locator("xpath=parent::label").innerText(), /Nov 13, 2026/);
    assert.ok(await label.evaluate((node) => getComputedStyle(node).boxShadow !== "none"), "Keyboard focus is visible on the choice");
    await box(page).fill("Draft for first appointment");
    await choices.nth(2).focus();
    await page.keyboard.press("Space");
    assert.equal(await box(page).inputValue(), "Draft for first appointment", "Existing new-message behavior keeps editable text when choosing another recipient");
    await noHorizontalOverflow(page);
    assert.equal(backend.sends().length, 0);
    await screenshot(page, "narrow-recipients");
  });
}

{
  const backend = studentWorld();
  let attempts = 0;
  backend.state.onSend = () => attempts++ === 0 ? "commit-then-network" : undefined;
  await check("resize preserves uncertain Retry and duplicate protection", path(threadIds.office), options(backend), async (page) => {
    const text = "Synthetic uncertain send.";
    await box(page).fill(text);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const retry = page.getByRole("button", { name: "Retry sending" });
    await shown(retry);
    await page.setViewportSize({ width: 320, height: 380 });
    await page.evaluate(() => { document.documentElement.style.fontSize = "24px"; });
    await reachable(page, retry);
    assert.equal(await box(page).inputValue(), text);
    assert.equal(backend.sends().length, 1, "Resizing never replays a send");
    const release = backend.holdNextSend();
    await retry.click();
    await shown(page.getByRole("button", { name: "Sending…" }));
    await box(page).press("Control+Enter");
    assert.equal(backend.sends().length, 2, "Pending retry cannot send twice");
    release();
    await shown(history(page).getByText(text, { exact: true }));
    assert.deepEqual(backend.sends()[0].body, backend.sends()[1].body, "Original ID and exact text reused");
    assert.equal(await history(page).getByText(text, { exact: true }).count(), 1);
    await noHorizontalOverflow(page);
  });
}

{
  const backend = staffWorld();
  backend.state.eligibleStudents[0].display_name = LONG_STAFF.display_name;
  await check("Guidance staff student choices use initials and wrap", "/portal/messages/new", options(backend, "GUIDANCE_OFFICE_ASSISTANT", { viewport: { width: 320, height: 500 } }), async (page) => {
    const choice = page.getByRole("radio").first();
    await shown(choice);
    await choice.focus();
    await page.keyboard.press("Space");
    assert.match(await choice.locator("xpath=parent::label").innerText(), /MC/);
    await noHorizontalOverflow(page);
    await reachable(page, box(page));
    assert.equal(backend.sends().length, 0);
  });
}

{
  const backend = staffWorld();
  backend.state.threads.get(threadIds.counseling).student = { ...STUDENT, display_name: LONG_STAFF.display_name };
  await check("staff long-name header wraps actions without squeezing identity", path(threadIds.counseling), options(backend, "COUNSELOR", { viewport: { width: 320, height: 480 } }), async (page) => {
    await shown(page.getByRole("heading", { name: LONG_STAFF.display_name, exact: true }));
    const heading = await page.getByRole("heading", { name: LONG_STAFF.display_name, exact: true }).boundingBox();
    const close = await page.getByRole("button", { name: "Close conversation", exact: true }).boundingBox();
    assert.ok(close.y >= heading.y + heading.height, "Actions move below the full name at a narrow width");
    await layout(page);
    assert.equal(backend.sends().length, 0);
  });
}

for (const [role, kind, title, office] of [
  ["FACULTY", "FACULTY_INQUIRY", "Guidance Office", true],
  ["FACULTY", "REFERRAL_COORDINATION", "Guidance Office", true],
  ["COUNSELOR", "COUNSELOR_DIRECT", LONG_STAFF.display_name, false],
  ["COUNSELOR", "COUNSELOR_CASE_COORDINATION", LONG_STAFF.display_name, false],
]) {
  const account = messagesAccount(role, { capabilities: [
    "guidance_messages.inquiry_view_self", "guidance_messages.inquiry_manage_self",
    "guidance_messages.referral_view_self", "guidance_messages.referral_manage_self",
    "guidance_messages.view", "guidance_messages.counselor_direct.view", "guidance_messages.counselor_direct.manage",
    "guidance_messages.case_coordination.view", "guidance_messages.case_coordination.manage",
  ] });
  const thread = {
    id: threadIds.long, kind, status: "OPEN", student: null, counselor: null, requester: { id: account.id, display_name: "Synthetic Faculty" },
    direct_first_user: { id: account.id, display_name: "Synthetic Counselor" }, direct_second_user: LONG_STAFF,
    student_subject: LONG_STAFF, routing_college: null, assigned_to: null,
    relationship_appointment_id: null, relationship_referral_id: kind === "REFERRAL_COORDINATION" ? "referral" : null,
    relationship_referral_reference: kind === "REFERRAL_COORDINATION" ? "REF-SYNTHETIC" : null, relationship_referral_voided: false,
    relationship_case_grant_id: null, created_at: "2026-11-01T02:00:00Z", last_message_at: null,
    last_sequence: 0, own_last_read_sequence: 0, unread_count: 0, seen_sequence: null, seen_scope: null,
  };
  await check(`${kind}: authorized conversation identity`, path(thread.id), {
    overrides: { "/api/v1/auth/session": sessionFor(account) },
    handler: async ({ pathname, reply }) => {
      if (pathname === "/api/v1/guidance-messages/threads") { await reply({ items: [thread], page: 1, page_size: 20, has_next: false }); return true; }
      if (pathname === `/api/v1/guidance-messages/threads/${thread.id}`) { await reply(thread); return true; }
      if (pathname === `/api/v1/guidance-messages/threads/${thread.id}/messages`) { await reply({ items: [], has_older: false }); return true; }
      return false;
    },
  }, async (page) => {
    await shown(page.getByRole("heading", { name: title, exact: true }));
    assert.equal(await row(page, thread.id).locator("svg.lucide-building2").count(), office ? 1 : 0);
    if (!office) assert.equal(await row(page, thread.id).getByText("MC", { exact: true }).count(), 1);
    if (kind === "REFERRAL_COORDINATION") await shown(page.getByText("Referral REF-SYNTHETIC", { exact: true }).last());
    await noHorizontalOverflow(page);
  });
}

{
  const backend = studentWorld();
  await check("deliberate conversation navigation resets the existing composer", path(threadIds.office), options(backend), async (page) => {
    await box(page).fill("Synthetic draft to discard deliberately.");
    page.once("dialog", (dialog) => dialog.accept());
    await row(page, threadIds.counseling).click();
    await page.waitForURL(new RegExp(`${threadIds.counseling}$`));
    await shown(box(page));
    assert.equal(await box(page).inputValue(), "");
    assert.equal(backend.sends().length, 0);
  });
}

{
  const backend = studentWorld();
  await check("empty, load error and concealed states retain their meaning", "/portal/messages", options(backend, "STUDENT", {
    handler: async (args) => {
      if (args.pathname === "/api/v1/guidance-messages/threads") {
        await args.reply({ items: [], page: 1, page_size: 20, has_next: false }); return true;
      }
      if (args.pathname === `/api/v1/guidance-messages/threads/${threadIds.long}` || args.pathname === `/api/v1/guidance-messages/threads/${threadIds.long}/messages`) {
        await args.reply({ error: { code: "synthetic_unavailable" } }, 503); return true;
      }
      return backend.handler(args);
    },
  }), async (page) => {
    await shown(page.getByText("No messages yet.", { exact: true }));
    await navigate(page, path(threadIds.long));
    await shown(page.getByRole("heading", { name: "Conversation not loaded" }));
    assert.equal(await box(page).count(), 0);
    await navigate(page, path(threadIds.hidden));
    await shown(page.getByText("This conversation does not exist, or your account no longer has access to it."));
    assert.equal(await box(page).count(), 0);
    assert.equal(await history(page).count(), 0);
  });
}

{
  const backend = studentWorld();
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await check("loading keeps identity concealed until the thread response arrives", path(threadIds.counseling), options(backend, "STUDENT", {
    handler: async (args) => {
      if (args.pathname === `/api/v1/guidance-messages/threads/${threadIds.counseling}`) await held;
      return backend.handler(args);
    },
  }), async (page) => {
    await shown(page.getByRole("heading", { name: "Loading conversation…" }));
    assert.equal(await box(page).count(), 0);
    release();
    await shown(box(page));
    await layout(page);
  });
}

{
  const backend = studentWorld();
  let failure = null;
  const marker = "Synthetic cached message for a refresh check.";
  backend.addMessage(threadIds.office, COUNSELOR, marker);
  await check("stale refresh keeps confirmed content and access loss conceals it", path(threadIds.office), options(backend, "STUDENT", {
    handler: async (args) => {
      if (failure && (args.pathname === `/api/v1/guidance-messages/threads/${threadIds.office}` || args.pathname === `/api/v1/guidance-messages/threads/${threadIds.office}/messages`)) {
        await args.reply({ error: { code: failure === 403 ? "forbidden" : "synthetic_unavailable" } }, failure); return true;
      }
      return backend.handler(args);
    },
  }), async (page) => {
    await shown(history(page).getByText(marker));
    await box(page).fill("Draft survives a transient refresh.");
    failure = 503;
    await page.getByText("Couldn't refresh messages. Showing the messages already loaded.", { exact: true }).waitFor({ timeout: 25_000 });
    await shown(history(page).getByText(marker));
    assert.equal(await box(page).inputValue(), "Draft survives a transient refresh.");
    await layout(page);
    failure = 403;
    await page.getByText("This conversation does not exist, or your account no longer has access to it.", { exact: true }).waitFor({ timeout: 25_000 });
    assert.equal(await page.getByText(marker, { exact: true }).count(), 0);
    assert.equal(await box(page).count(), 0);
    assert.equal(backend.sends().length, 0);
  });
}

await finish();
