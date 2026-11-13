// CW-6: Counselor About and Messages context, on the worktree's actual pages with synthetic
// canonical responses. No institutional API, person or photo is contacted.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { continuityFixture, preparePath, receiver } from "./support/counseling-continuity-fixtures.mjs";
import {
  COUNSELOR, messagesAccount, sessionFor, staffWorld, studentWorld, threadIds,
} from "./support/guidance-messages-fixtures.mjs";
import { service, user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, settleFetches, finish } = await createBrowserHarness("counselor-about");

const ABOUT = /^\/api\/v1\/organization\/counselors\/([^/]+)\/about$/;
const counselors = [
  { id: "11111111-1111-4111-8111-111111111111", display_name: "Maria Reyes", is_default: true, profile_photo_url: null, profile_photo_updated_at: null },
  { id: "22222222-2222-4222-8222-222222222222", display_name: "Alexandra Gabriella Delos Santos Villanueva", is_default: false, profile_photo_url: null, profile_photo_updated_at: null },
];
const names = Object.fromEntries([...counselors, COUNSELOR, receiver].map((person) => [person.id, person.display_name]));
const campuses = [{
  id: "d0000000-0000-4000-8000-000000000001", code: "MAIN", name: "Main Campus",
  colleges: [
    { id: "d0000000-0000-4000-8000-000000000011", code: "CCMS", name: "College of Computing and Multimedia Studies", basis: "ASSIGNED" },
    { id: "d0000000-0000-4000-8000-000000000012", code: "CBA", name: "College of Business and Accountancy", basis: "HEAD_FALLBACK" },
  ],
}];

/** Answers only the About read; `failures` maps a Counselor ID to a status, removed to recover. */
function aboutBackend({ failures = {}, assignments = campuses } = {}) {
  const state = { reads: [], failures: { ...failures } };
  async function about({ pathname, method, reply }) {
    const match = ABOUT.exec(pathname);
    if (!match) return false;
    assert.equal(method, "GET", "About is read-only");
    state.reads.push(match[1]);
    const status = state.failures[match[1]];
    if (status) {
      await reply({ error: { code: status === 404 ? "counselor_about_unavailable" : "internal_error", message: "Synthetic backend wording" } }, status);
      return true;
    }
    await reply({
      counselor: { id: match[1], display_name: names[match[1]] ?? "Synthetic Counselor", profile_photo_url: null, profile_photo_updated_at: null },
      campuses: assignments,
      checked_at: new Date().toISOString(),
    });
    return true;
  }
  return { state, about };
}
const chain = (...handlers) => async (args) => {
  for (const handler of handlers) if (await handler(args)) return true;
  return false;
};
const aboutDialog = (page, name) => page.getByRole("dialog", { name, exact: true });
// Radix restores focus just after the close; wait for it rather than sampling once.
const focusReturnsTo = (page, id) => page.waitForFunction((target) => document.activeElement?.getAttribute("data-counselor-about") === target, id, { timeout: 5_000 });

async function expectAssignments(dialog) {
  // The Campus is a small uppercase label; match its words, not the CSS case.
  await shown(dialog.getByText(/^Main Campus$/i));
  await shown(dialog.getByText("College of Computing and Multimedia Studies", { exact: true }));
  await shown(dialog.getByText("College of Business and Accountancy", { exact: true }));
  await shown(dialog.getByText("Covered while no Counselor is assigned", { exact: true }));
  await shown(dialog.getByText("This shows office assignments, not who handles a particular case.", { exact: true }));
}

// ── Booking ─────────────────────────────────────────────────────────────────────────────────

function bookingWorld(about) {
  const posts = [];
  const account = { ...user("STUDENT"), capabilities: ["appointments.view_self", "appointments.manage_self", "services.catalog.view"] };
  const handler = chain(about, async ({ pathname, method, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply({ user: account, session: { id: "synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true } }); return true; }
    if (pathname === "/api/v1/appointments/booking/services") { await reply({ items: [{ ...service, delivery_modes: ["IN_PERSON", "ONLINE"] }], page: 1, page_size: 10, has_next: false }); return true; }
    if (pathname === "/api/v1/appointments/booking/counselors") { await reply({ items: counselors }); return true; }
    if (pathname === "/api/v1/appointments/booking/slots") { await reply({ date: "2099-01-05", timezone: "Asia/Manila", duration_minutes: 60, items: [] }); return true; }
    if (method === "POST" && pathname.startsWith("/api/v1/appointments")) { posts.push(pathname); await reply({ error: { code: "synthetic_failure" } }, 500); return true; }
    return false;
  });
  return { posts, options: { role: "STUDENT", handler } };
}
async function chooseService(page) {
  await shown(page.getByRole("button", { name: /^Counseling/ }));
  await page.getByRole("button", { name: /^Counseling/ }).click();
  await page.getByRole("radio", { name: "In person", exact: true }).check();
  await shown(page.getByRole("radio", { name: /Maria Reyes/ }));
}

{
  const backend = aboutBackend();
  const world = bookingWorld(backend.about);
  await check("booking About shows assignments without selecting or booking", "/portal/appointments/book", { ...world.options, viewport: { width: 390, height: 720 } }, async (page) => {
    await chooseService(page);
    await page.getByRole("radio", { name: /Maria Reyes/ }).check();
    // A modal dialog hides the page from the accessibility tree, so read the inputs directly.
    const first = page.locator(`input[name="booking-counselor"][value="${counselors[0].id}"]`);
    const second = page.locator(`input[name="booking-counselor"][value="${counselors[1].id}"]`);
    const button = page.getByRole("button", { name: `About ${counselors[1].display_name}`, exact: true });
    await button.click();
    const dialog = aboutDialog(page, counselors[1].display_name);
    await expectAssignments(dialog);
    assert.equal(await first.isChecked(), true, "Opening About keeps the selected Counselor");
    assert.equal(await second.isChecked(), false, "Opening About never selects that Counselor");
    await noHorizontalOverflow(page);
    await screenshot(page, "booking-about-phone", dialog);
    await page.keyboard.press("Escape");
    await hidden(dialog);
    await focusReturnsTo(page, counselors[1].id);
    assert.equal(await first.isChecked(), true);
    assert.deepEqual(backend.state.reads, [counselors[1].id]);
    assert.deepEqual(world.posts, [], "About books nothing");
  });
}

{
  const backend = aboutBackend();
  const world = bookingWorld(backend.about);
  await check("About asks again on every opening and keeps no copy", "/portal/appointments/book", world.options, async (page) => {
    await chooseService(page);
    const button = page.getByRole("button", { name: `About ${counselors[0].display_name}`, exact: true });
    for (let opening = 0; opening < 2; opening++) {
      await button.click();
      await expectAssignments(aboutDialog(page, counselors[0].display_name));
      await page.keyboard.press("Escape");
      await hidden(aboutDialog(page, counselors[0].display_name));
    }
    assert.deepEqual(backend.state.reads, [counselors[0].id, counselors[0].id]);
  });
}

{
  const backend = aboutBackend({ assignments: [] });
  const world = bookingWorld(backend.about);
  await check("About states plainly when no assignment is recorded", "/portal/appointments/book", world.options, async (page) => {
    await chooseService(page);
    await page.getByRole("button", { name: `About ${counselors[0].display_name}`, exact: true }).click();
    const dialog = aboutDialog(page, counselors[0].display_name);
    await shown(dialog.getByText("No current College assignment is recorded for this Counselor.", { exact: true }));
    assert.equal(await dialog.getByText("This shows office assignments", { exact: false }).count(), 1);
  });
}

// ── Messages: recipient choice, conversation header and directory ─────────────────────────────

function messagesOptions(backend, about, role = "STUDENT", extra = {}) {
  return { handler: chain(about, backend.handler), overrides: { "/api/v1/auth/session": sessionFor(messagesAccount(role)) }, ...extra };
}

{
  const messages = studentWorld();
  const backend = aboutBackend();
  await check("Student recipient choice names the Appointment and opens About beside it", "/portal/messages/new", messagesOptions(messages, backend.about, "STUDENT", { viewport: { width: 390, height: 720 } }), async (page) => {
    await shown(page.getByRole("radio", { name: /^Guidance Office/ }));
    await shown(page.getByRole("radio", { name: /Ana Cruz/ }));
    // A modal dialog hides the page from the accessibility tree, so read the inputs directly.
    const office = page.locator('input[name="guidance-recipient"]').nth(0);
    const choice = page.locator('input[name="guidance-recipient"]').nth(1);
    assert.equal(await office.isChecked(), true);
    assert.match(await choice.locator("xpath=parent::label").innerText(), /APT-2026-0001 · Oct 5, 2026.* · Scheduled/);
    await page.getByRole("button", { name: "About Ana Cruz", exact: true }).click();
    await expectAssignments(aboutDialog(page, "Ana Cruz"));
    assert.equal(await office.isChecked(), true, "About does not change the recipient");
    assert.equal(await choice.isChecked(), false);
    await noHorizontalOverflow(page);
    await page.keyboard.press("Escape");
    await hidden(aboutDialog(page, "Ana Cruz"));
    await focusReturnsTo(page, COUNSELOR.id);
    assert.equal(messages.state.requests.filter((request) => request.method !== "GET").length, 0, "Nothing is sent");
  });
}

{
  const messages = studentWorld();
  const backend = aboutBackend({ failures: { [COUNSELOR.id]: 404 } });
  await check("an unavailable Counselor is a final, plain refusal", "/portal/messages/new", messagesOptions(messages, backend.about), async (page) => {
    await page.getByRole("button", { name: "About Ana Cruz", exact: true }).click();
    const dialog = aboutDialog(page, "Ana Cruz");
    await shown(dialog.getByText("This Counselor's details aren't available.", { exact: true }));
    assert.equal(await dialog.getByRole("button", { name: "Retry" }).count(), 0);
    assert.equal(await dialog.getByText("Synthetic backend wording").count(), 0, "Backend wording is not shown");
    assert.equal(await dialog.getByText(/^Main Campus$/i).count(), 0);
  });
}

{
  const messages = studentWorld();
  const backend = aboutBackend({ failures: { [COUNSELOR.id]: 500 } });
  await check("a failed About read can be retried in place", `/portal/messages/${threadIds.counseling}`, messagesOptions(messages, backend.about), async (page) => {
    await page.getByRole("button", { name: "About Ana Cruz", exact: true }).click();
    const dialog = aboutDialog(page, "Ana Cruz");
    await shown(dialog.getByText("Couldn't load this Counselor's details. Try again.", { exact: true }));
    delete backend.state.failures[COUNSELOR.id];
    await dialog.getByRole("button", { name: "Retry", exact: true }).click();
    await expectAssignments(dialog);
  });
}

{
  const messages = studentWorld();
  const backend = aboutBackend();
  await check("Student Counseling conversation shows its Appointment and Counselor About", `/portal/messages/${threadIds.counseling}`, messagesOptions(messages, backend.about), async (page) => {
    const header = page.locator("header[data-guide-target=message-identity]");
    await shown(header.getByRole("heading", { name: "Ana Cruz", exact: true }));
    await shown(header.getByText("APT-2026-0001", { exact: true }));
    assert.match(await header.innerText(), /APT-2026-0001 · Oct 5, 2026.* · Scheduled/);
    const row = page.locator(`[data-thread-id="${threadIds.counseling}"]`);
    assert.match(await row.innerText(), /Appointment APT-2026-0001 · Oct 5, 2026.* · Scheduled/);
    // The Office conversation keeps its office identity and has no Appointment line.
    const office = page.locator(`[data-thread-id="${threadIds.office}"]`);
    assert.match(await office.innerText(), /^Guidance Office/);
    assert.doesNotMatch(await office.innerText(), /APT-|Scheduled/);
    await header.getByRole("button", { name: "About Ana Cruz", exact: true }).click();
    await expectAssignments(aboutDialog(page, "Ana Cruz"));
    await page.keyboard.press("Escape");
    await hidden(aboutDialog(page, "Ana Cruz"));
    await shown(page.getByRole("textbox", { name: /^Message/ }));
    await screenshot(page, "student-counseling-header");
  });
}

{
  const messages = staffWorld();
  // The Counselor was reassigned away from the Appointment: the conversation stays, its summary does not.
  messages.state.threads.get(threadIds.counseling).relationship_appointment = null;
  const backend = aboutBackend();
  await check("a reassigned Counselor keeps the conversation without the Appointment", `/portal/messages/${threadIds.counseling}`, messagesOptions(messages, backend.about, "COUNSELOR"), async (page) => {
    const header = page.locator("header[data-guide-target=message-identity]");
    await shown(header.getByRole("heading", { name: "John Reyes", exact: true }));
    await shown(header.getByText("Appointment details aren't available to you.", { exact: true }));
    assert.equal(await header.getByText(/APT-/).count(), 0);
    assert.equal(await page.getByRole("button", { name: /^About / }).count(), 0, "Staff see the Student, not Counselor About");
    await settleFetches(page);
    assert.deepEqual(backend.state.reads, []);
  });
}

// ── Case continuity: receiving Counselor choice ─────────────────────────────────────────────

{
  const fixture = continuityFixture();
  const backend = aboutBackend();
  await check("transfer preparation offers About for the chosen receiver without changing it", preparePath, { handler: chain(backend.about, fixture.handler) }, async (page) => {
    const select = page.getByLabel("Receiving counselor", { exact: true });
    await shown(select);
    assert.equal(await page.getByRole("button", { name: /^About / }).count(), 0, "Nothing to describe before a choice");
    await select.selectOption(receiver.id);
    await page.getByRole("button", { name: `About ${receiver.display_name}`, exact: true }).click();
    await expectAssignments(aboutDialog(page, receiver.display_name));
    await page.keyboard.press("Escape");
    await hidden(aboutDialog(page, receiver.display_name));
    assert.equal(await select.inputValue(), receiver.id, "The receiver stays as chosen");
    assert.equal(fixture.operations.filter((operation) => operation.method !== "GET").length, 0, "About prepares nothing");
  });
}

await finish();
