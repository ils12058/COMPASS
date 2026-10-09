// Account changes, failed refreshes, and unsaved drafts in a real browser (frontend audit
// FE-001 to FE-004). Every API read and write is a synthetic fixture; no account, record, or
// external service is touched.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { service, serviceId, user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, finish } = await createBrowserHarness("draft-and-session-safety");

const MARKER = "UNSAVED DRAFT MARKER";
const servicePath = `/portal/services/${serviceId}`;
const academicYear = { id: "year-2026", label: "2026-2027" };

const withCapabilities = (role, capabilities, fields = {}) => {
  const base = user(role);
  return { ...base, ...fields, capabilities: [...base.capabilities, ...capabilities] };
};
const sessionFor = (account) => ({
  authenticated: true,
  user: account,
  session: { id: `session-${account.id}`, expires_at: "2099-10-07T00:00:00Z", is_current: true },
});
const failure = (status, code = "synthetic_failure") => [{ error: { code, message: `Synthetic ${code}` } }, status];

async function eventually(condition, message, timeout = 10_000) {
  const started = Date.now();
  while (!(await condition())) {
    if (Date.now() - started > timeout) throw new Error(message);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

// Makes cached reads stale and reconnects, which refetches the page's queries as a real
// reconnection would.
const clocks = new WeakSet();
async function refreshStaleQueries(page) {
  if (!clocks.has(page)) {
    await page.clock.install();
    clocks.add(page);
  }
  await page.clock.fastForward(31_000);
  await page.evaluate(() => {
    window.dispatchEvent(new Event("offline"));
    window.dispatchEvent(new Event("online"));
  });
}

// Records each browser dialog (navigation confirmations and beforeunload) and answers it.
function answerDialogs(page) {
  const seen = [];
  let accept = false;
  page.on("dialog", async (dialog) => {
    seen.push({ type: dialog.type(), message: dialog.message() });
    if (accept) await dialog.accept();
    else await dialog.dismiss();
  });
  return {
    seen,
    acceptNext(value) {
      accept = value;
    },
  };
}

const inventoryRevision = { id: "inventory-revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "TEST-INV", official_revision: "1" };
const inventoryRecordFor = (account) => ({
  id: `inventory-${account.toLowerCase()}`, academic_year: academicYear, status: "DRAFT", program: null, form_revision: inventoryRevision,
  submitted_at: null, first_submitted_at: null, last_submitted_at: null, correction_pending: false, latest_correction: null,
  full_name: "Maria Santos",
});
const inventoryRecord = inventoryRecordFor("draft-test");
const inventoryStatus = {
  academic_year: academicYear, status: "DRAFT", form_revision: inventoryRevision, correction_pending: false, latest_correction: null,
  submitted_at: null, first_submitted_at: null, last_submitted_at: null,
};

// ── FE-001: protected client state belongs to one confirmed account ───────────────────────────

const accountUser = (account) => ({ ...user("COUNSELOR"), id: `account-${account.toLowerCase()}`, first_name: `Account ${account}`, last_name: "User" });
const menuButton = (page, name) => page.getByRole("button", { name: `Open user menu for ${name}`, exact: true });

function accountWorld() {
  const state = { account: "A", sessionStatus: 200, unreadStatus: null, holdProfile: false, held: [], sessionsServed: [], profilesServed: [] };
  const overrides = {
    "GET /api/v1/auth/session": ({ reply }) => {
      state.sessionsServed.push(state.sessionStatus === 200 ? state.account : state.sessionStatus);
      if (state.sessionStatus !== 200) return reply(...failure(state.sessionStatus, state.sessionStatus === 401 ? "not_authenticated" : "temporarily_unavailable"));
      return reply(sessionFor(accountUser(state.account)));
    },
    "GET /api/v1/me/profile": ({ reply }) => {
      const account = state.account;
      state.profilesServed.push(account);
      const body = { full_name: `PROFILE ACCOUNT ${account}`, photo: null };
      // A held response completes only when the test releases it, after the account changed.
      if (state.holdProfile) return new Promise((resolve) => state.held.push(() => resolve(reply(body).catch(() => "aborted"))));
      return reply(body);
    },
    // A refused read is how the portal learns to check the session again.
    "GET /api/v1/notifications/unread-count": ({ reply }) => {
      if (state.unreadStatus) {
        const status = state.unreadStatus;
        state.unreadStatus = null;
        return reply(...failure(status, status === 401 ? "not_authenticated" : "permission_denied"));
      }
      return reply({ unread_count: 0 });
    },
  };
  return { state, overrides };
}

async function recordMenuNames(page) {
  await page.evaluate(() => {
    const names = [];
    window.__accountMenuNames = names;
    const record = () => {
      const name = document.querySelector('button[aria-label^="Open user menu for "]')?.getAttribute("aria-label");
      if (name && names.at(-1) !== name) names.push(name);
    };
    record();
    new MutationObserver(record).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-label"] });
  });
}
const menuNames = (page) => page.evaluate(() => window.__accountMenuNames);

async function revalidateSession(page, state, status = 403) {
  state.unreadStatus = status;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
}

{
  const { state, overrides } = accountWorld();
  await check("account-change-discards-previous-account-cache", servicePath, { overrides }, async (page) => {
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    await recordMenuNames(page);
    // Development renders read twice on mount, so compare reads from this point on.
    const readsBefore = state.profilesServed.length;
    state.account = "B";
    await revalidateSession(page, state);
    await shown(menuButton(page, "PROFILE ACCOUNT B"));
    const names = await menuNames(page);
    const firstB = names.findIndex((name) => /Account B|ACCOUNT B/.test(name));
    assert.ok(firstB > 0, `The menu moved from Account A to Account B: ${names.join(" → ")}`);
    assert.ok(!names.slice(firstB).some((name) => name.includes("ACCOUNT A")), `Account A's profile never returns under Account B: ${names.join(" → ")}`);
    const readsAfter = state.profilesServed.slice(readsBefore);
    assert.ok(readsAfter.length > 0 && readsAfter.every((account) => account === "B"), `Account B's profile is fetched for Account B: ${readsAfter}`);
  });
}

{
  const { state, overrides } = accountWorld();
  state.holdProfile = true;
  await check("late-previous-account-response-is-discarded", servicePath, { overrides }, async (page) => {
    await shown(menuButton(page, "Account A User"));
    await eventually(() => state.held.length > 0, "Account A's profile request started");
    await recordMenuNames(page);
    state.holdProfile = false;
    state.account = "B";
    await revalidateSession(page, state);
    await shown(menuButton(page, "PROFILE ACCOUNT B"));
    // Complete the request Account A started, after Account B became the confirmed account.
    for (const release of state.held.splice(0)) await release();
    await page.waitForTimeout(750);
    await shown(menuButton(page, "PROFILE ACCOUNT B"));
    const names = await menuNames(page);
    assert.ok(!names.some((name) => name.includes("PROFILE ACCOUNT A")), `Account A's late profile never appears: ${names.join(" → ")}`);
  });
}

// A response to a save Account A started arrives after Account B is confirmed. Its success handling
// would write Account A's Individual Inventory into the account-relative "my current" record.
{
  const state = { account: "A", unreadStatus: null, held: [], saves: 0 };
  const student = (account) => withCapabilities("STUDENT", ["inventory.view_self", "inventory.manage_self"], { id: `student-${account.toLowerCase()}`, first_name: `Student ${account}` });
  const record = (account, fullName = `Student ${account}`) => ({ ...inventoryRecordFor(account), full_name: fullName });
  await check("late-previous-account-save-cannot-fill-next-account-record", "/portal/inventory/current", {
    overrides: {
      "GET /api/v1/auth/session": ({ reply }) => reply(sessionFor(student(state.account))),
      "GET /api/v1/inventory/me/status": inventoryStatus,
      "GET /api/v1/inventory/me/current": ({ reply }) => reply(record(state.account)),
      "PUT /api/v1/inventory/me/current": ({ reply }) => {
        state.saves += 1;
        return new Promise((resolve) => state.held.push(() => resolve(reply(record("A", "Student A saved")).catch(() => "aborted"))));
      },
      "GET /api/v1/notifications/unread-count": ({ reply }) => {
        if (state.unreadStatus) {
          state.unreadStatus = null;
          return reply(...failure(403, "permission_denied"));
        }
        return reply({ unread_count: 0 });
      },
    },
  }, async (page) => {
    const fullName = page.getByLabel("Full name", { exact: true });
    await fullName.fill("Student A edited");
    await page.getByRole("button", { name: "Save progress", exact: true }).click();
    await eventually(() => state.held.length > 0, "Account A's save started");
    state.account = "B";
    state.unreadStatus = 403;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await eventually(async () => (await fullName.inputValue().catch(() => "")) === "Student B", "Account B's own record is shown");
    // Complete the save Account A started, after Account B became the confirmed account.
    for (const release of state.held.splice(0)) await release();
    await page.waitForTimeout(750);
    assert.equal(await fullName.inputValue(), "Student B", "Account B still sees only its own record");
    assert.equal(await page.getByText(/Student A/).count(), 0, "Nothing from Account A's save is shown");
  });
}

{
  const { state, overrides } = accountWorld();
  await check("same-account-revalidation-keeps-cache-and-draft", `${servicePath}/edit`, { overrides }, async (page) => {
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    await page.getByLabel("Name", { exact: true }).fill(MARKER);
    const sessionsBefore = state.sessionsServed.length;
    const readsBefore = state.profilesServed.length;
    await revalidateSession(page, state);
    await eventually(() => state.sessionsServed.length > sessionsBefore, "The session was checked again");
    await page.waitForTimeout(500);
    assert.equal(state.profilesServed.length, readsBefore, "The same account keeps its cached profile");
    assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), MARKER, "The draft is not remounted");
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
  });
}

{
  const { state, overrides } = accountWorld();
  await check("failed-session-check-keeps-confirmed-account", servicePath, { overrides }, async (page) => {
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    const readsBefore = state.profilesServed.length;
    state.sessionStatus = 503;
    await revalidateSession(page, state);
    await shown(page.getByText("We could not verify your session.", { exact: true }));
    state.sessionStatus = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    assert.equal(state.profilesServed.length, readsBefore, "A failed check is not an account change: the cache is kept");
  });
}

{
  const { state, overrides } = accountWorld();
  await check("confirmed-sign-out-clears-protected-cache", servicePath, { overrides }, async (page) => {
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    state.sessionStatus = 401;
    await revalidateSession(page, state, 401);
    await page.waitForURL(/\/login/);
    const readsBefore = state.profilesServed.length;
    // Sign in again in this tab without reloading: the portal must fetch the profile again.
    state.sessionStatus = 200;
    await page.evaluate((path) => window.next.router.push(path), servicePath);
    await shown(menuButton(page, "PROFILE ACCOUNT A"));
    assert.ok(state.profilesServed.length > readsBefore, "Signing out cleared the cached profile, so it is read again");
  });
}

// ── FE-002: a failed refresh keeps the draft; a refusal removes the record ─────────────────────

function serviceWorld() {
  const state = { read: 200, name: service.name, patches: [] };
  const overrides = {
    [`GET /api/v1/services/${serviceId}`]: ({ reply }) =>
      state.read === 200 ? reply({ ...service, name: state.name }) : reply(...failure(state.read, state.read === 403 ? "permission_denied" : "temporarily_unavailable")),
    [`PATCH /api/v1/services/${serviceId}`]: ({ reply, request }) => {
      const changes = request.postDataJSON();
      state.patches.push(changes);
      if (changes.name) state.name = changes.name;
      return reply({ ...service, name: state.name });
    },
  };
  return { state, overrides };
}

{
  const { state, overrides } = serviceWorld();
  await check("service-draft-survives-transient-refresh-failure", `${servicePath}/edit`, { overrides }, async (page) => {
    const name = page.getByLabel("Name", { exact: true });
    await name.fill(MARKER);
    state.read = 503;
    await refreshStaleQueries(page);
    const notice = page.getByText(/^The latest Service details could not be refreshed\./);
    await shown(notice);
    assert.equal(await name.inputValue(), MARKER, "The unsaved name is kept");
    assert.equal(await page.getByRole("button", { name: "Save changes", exact: true }).isDisabled(), true, "Saving waits for confirmed details");
    state.read = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await hidden(notice);
    assert.equal(await name.inputValue(), MARKER, "Retrying keeps the unsaved name");
    assert.equal(await page.getByRole("button", { name: "Save changes", exact: true }).isEnabled(), true);
  });
}

{
  const { state, overrides } = serviceWorld();
  await check("service-editor-removed-on-confirmed-refusal", `${servicePath}/edit`, { overrides }, async (page) => {
    await page.getByLabel("Name", { exact: true }).fill(MARKER);
    state.read = 403;
    await refreshStaleQueries(page);
    await hidden(page.getByLabel("Name", { exact: true }));
    assert.equal(await page.getByText(MARKER).count(), 0, "Nothing from the refused record or draft stays on screen");
  });
}

{
  const state = { read: 200 };
  const student = withCapabilities("STUDENT", ["inventory.view_self", "inventory.manage_self"]);
  await check("inventory-draft-survives-transient-refresh-failure", "/portal/inventory/current", {
    overrides: {
      "GET /api/v1/auth/session": sessionFor(student),
      "GET /api/v1/inventory/me/status": inventoryStatus,
      "GET /api/v1/inventory/me/current": ({ reply }) => (state.read === 200 ? reply(inventoryRecord) : reply(...failure(state.read))),
    },
  }, async (page) => {
    const fullName = page.getByLabel("Full name", { exact: true });
    await fullName.fill(MARKER);
    state.read = 503;
    await refreshStaleQueries(page);
    const notice = page.getByText(/^The latest Individual Inventory could not be refreshed\./);
    await shown(notice);
    assert.equal(await fullName.inputValue(), MARKER, "The unsaved answer is kept");
    state.read = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await hidden(notice);
    assert.equal(await fullName.inputValue(), MARKER, "Retrying keeps the unsaved answer");
    await shown(page.getByText("Unsaved changes", { exact: true }));
  });
}

const exitInterviewId = "exit-draft-test";
const exitDetail = {
  id: exitInterviewId, academic_year: academicYear, can_edit: true, status: "DRAFT", inventory_id: "inventory-draft-test",
  student: { id: "student", display_name: "Maria Santos", institutional_id: "TEST-01" }, student_name: "Maria Santos",
  self_assessment_ratings: [], college_feedback_ratings: [], reopen_events: [],
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z", first_submitted_at: null, last_submitted_at: null,
};

function exitInterviewOverrides(state) {
  const student = withCapabilities("STUDENT", ["exit_interviews.view_self", "exit_interviews.manage_self"], { exit_interview_workspace_available: true });
  return {
    "GET /api/v1/auth/session": sessionFor(student),
    [`GET /api/v1/exit-interviews/me/${exitInterviewId}`]: ({ reply }) =>
      state.read === 200 ? reply(exitDetail) : reply(...failure(state.read, state.read === 404 ? "exit_interview_not_found" : "temporarily_unavailable")),
  };
}

{
  const state = { read: 200 };
  await check("exit-interview-draft-survives-transient-refresh-failure", `/portal/exit-interviews/${exitInterviewId}`, { overrides: exitInterviewOverrides(state) }, async (page) => {
    const studentName = page.getByLabel("Student name", { exact: true });
    await studentName.fill(MARKER);
    state.read = 503;
    await refreshStaleQueries(page);
    const notice = page.getByText(/^The latest Exit Interview status could not be confirmed\./);
    await shown(notice);
    assert.equal(await studentName.inputValue(), MARKER, "The unsaved answer is kept");
    assert.equal(await page.getByRole("button", { name: "Save draft", exact: true }).isDisabled(), true, "Saving waits for a confirmed status");
    state.read = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await hidden(notice);
    assert.equal(await studentName.inputValue(), MARKER, "Retrying keeps the unsaved answer");
    assert.equal(await page.getByRole("button", { name: "Save draft", exact: true }).isEnabled(), true);
  });
}

{
  const state = { read: 200 };
  await check("exit-interview-editor-removed-when-record-disappears", `/portal/exit-interviews/${exitInterviewId}`, { overrides: exitInterviewOverrides(state) }, async (page) => {
    await page.getByLabel("Student name", { exact: true }).fill(MARKER);
    state.read = 404;
    await refreshStaleQueries(page);
    await shown(page.getByRole("heading", { name: "Exit Interview not found" }));
    assert.equal(await page.getByLabel("Student name", { exact: true }).count(), 0, "The editor is removed with the record");
  });
}

// ── FE-002 and FE-003: the Referral status note ───────────────────────────────────────────────

const referralId = "referral-draft-test";
function referralWorld() {
  const state = { read: 200, note: "Existing note", updatedAt: "2026-10-07T00:00:00Z", reads: 0, saves: [] };
  const detail = () => ({
    id: referralId, reference_code: "REF-TEST-01", actions: [],
    student: { id: "student", display_name: "Maria Santos", institutional_id: "TEST-01" },
    form_revision: { official_code: "TEST-REF", official_revision: "1" },
    student_name_snapshot: "Maria Santos", course_year_block_snapshot: "BSIT / 4", referred_on: "2026-10-07",
    received_at: null, created_at: "2026-10-07T00:00:00Z", updated_at: state.updatedAt, recorded_by: null,
    referrer_name: "Synthetic Referrer", reason: "Synthetic referral", status_note: state.note,
    voided_at: null, void_reason: "", voided_by: null,
  });
  const counselor = withCapabilities("COUNSELOR", ["referrals.view", "referrals.manage"]);
  const overrides = {
    "GET /api/v1/auth/session": sessionFor(counselor),
    [`GET /api/v1/referrals/${referralId}`]: ({ reply }) => {
      state.reads += 1;
      return state.read === 200 ? reply(detail()) : reply(...failure(state.read));
    },
    [`PATCH /api/v1/referrals/${referralId}/status`]: ({ reply, request }) => {
      const { status_note: note } = request.postDataJSON();
      state.saves.push(note);
      state.note = note;
      state.updatedAt = "2026-10-09T00:00:00Z";
      return reply(detail());
    },
    "GET /api/v1/call-slips": { items: [], page: 1, page_size: 1, has_next: false },
  };
  return { state, overrides };
}
const referralPath = `/portal/referrals/${referralId}`;
const noteField = (page) => page.getByRole("textbox", { name: "Status note", exact: true });

async function openNoteEditor(page) {
  await page.getByRole("button", { name: "Update status note", exact: true }).click();
  await shown(noteField(page));
}

async function refreshReferral(page, state) {
  const before = state.reads;
  await refreshStaleQueries(page);
  await eventually(() => state.reads > before, "The Referral was read again");
  await page.waitForTimeout(300);
}

{
  const { state, overrides } = referralWorld();
  await check("referral-note-survives-transient-refresh-failure", referralPath, { overrides }, async (page) => {
    await openNoteEditor(page);
    await noteField(page).fill(MARKER);
    state.read = 503;
    await refreshStaleQueries(page);
    const notice = page.getByText(/^The latest Referral details could not be refreshed\./);
    await shown(notice);
    assert.equal(await noteField(page).inputValue(), MARKER, "The unsaved note is kept");
    assert.equal(await page.getByRole("button", { name: "Save status note", exact: true }).isDisabled(), true);
    state.read = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await hidden(notice);
    assert.equal(await noteField(page).inputValue(), MARKER, "Retrying keeps the unsaved note");
    assert.equal(await page.getByRole("button", { name: "Save status note", exact: true }).isEnabled(), true);
  });
}

{
  const { state, overrides } = referralWorld();
  await check("referral-timestamp-refresh-keeps-note-draft", referralPath, { overrides }, async (page) => {
    await openNoteEditor(page);
    await noteField(page).fill(MARKER);
    state.updatedAt = "2026-10-08T00:00:00Z";
    await refreshReferral(page, state);
    assert.equal(await noteField(page).inputValue(), MARKER, "A reload that changed only the timestamp keeps the editor and text");
    assert.equal(await page.getByText(/The saved status note changed/).count(), 0, "An unrelated change is not reported as a note change");
  });
}

{
  const { state, overrides } = referralWorld();
  await check("referral-note-change-never-overwrites-unsaved-text", referralPath, { overrides }, async (page) => {
    await openNoteEditor(page);
    await noteField(page).fill(MARKER);
    state.note = "Changed elsewhere";
    state.updatedAt = "2026-10-08T00:00:00Z";
    await refreshReferral(page, state);
    await shown(page.getByText(/The saved status note changed while you were editing/));
    assert.equal(await noteField(page).inputValue(), MARKER, "The unsaved text is kept");
    const save = page.getByRole("button", { name: "Save status note", exact: true });
    assert.equal(await save.isDisabled(), true, "Saving waits for a deliberate review");
    await page.getByRole("button", { name: "Keep my text", exact: true }).click();
    assert.equal(await save.isEnabled(), true);
    await save.click();
    await shown(page.getByText("Status note updated.", { exact: true }));
    assert.deepEqual(state.saves, [MARKER], "The person's text replaces the newer note only after review");
  });
}

{
  const { state, overrides } = referralWorld();
  await check("referral-unchanged-note-editor-follows-saved-note", referralPath, { overrides }, async (page) => {
    await openNoteEditor(page);
    state.note = "Changed elsewhere";
    state.updatedAt = "2026-10-08T00:00:00Z";
    await refreshReferral(page, state);
    assert.equal(await noteField(page).inputValue(), "Changed elsewhere", "Unchanged text follows the newer saved note");
    assert.equal(await page.getByText(/The saved status note changed/).count(), 0);
  });
}

{
  const { state, overrides } = referralWorld();
  await check("referral-note-cancel-and-save-set-the-baseline", referralPath, { overrides }, async (page) => {
    await openNoteEditor(page);
    await noteField(page).fill(MARKER);
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await hidden(noteField(page));
    await openNoteEditor(page);
    assert.equal(await noteField(page).inputValue(), "Existing note", "Cancel restores the saved note");
    await noteField(page).fill("Saved from this page");
    await page.getByRole("button", { name: "Save status note", exact: true }).click();
    await shown(page.getByText("Status note updated.", { exact: true }));
    await hidden(noteField(page));
    await refreshReferral(page, state);
    await openNoteEditor(page);
    assert.equal(await noteField(page).inputValue(), "Saved from this page", "The saved note is the new baseline");
    assert.equal(await page.getByText(/The saved status note changed/).count(), 0, "The editor's own save is not a concurrent change");
  });
}

// ── FE-004: unsaved configuration asks before navigation ──────────────────────────────────────

{
  const { overrides } = serviceWorld();
  await check("service-draft-asks-before-navigation", `${servicePath}/edit`, { overrides }, async (page) => {
    const dialogs = answerDialogs(page);
    await page.getByLabel("Name", { exact: true }).fill(MARKER);
    const back = page.getByRole("link", { name: /Service detail/ });
    await back.click();
    await eventually(() => dialogs.seen.length === 1, "Leaving asks first");
    assert.equal(dialogs.seen[0].message, "Discard your unsaved Service changes?");
    await page.waitForTimeout(300);
    assert.match(page.url(), /\/edit$/, "Cancelling keeps the editor open");
    assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), MARKER);
    dialogs.acceptNext(true);
    await back.click();
    await page.waitForURL(`**${servicePath}`);
    assert.equal(dialogs.seen.length, 2, "One question per navigation");
    // The guard leaves with the editor: later navigation does not ask.
    await page.getByRole("link", { name: /Services/ }).first().click();
    await page.waitForURL("**/portal/services");
    assert.equal(dialogs.seen.length, 2, "No question after the editor is gone");
  });
}

{
  const { overrides } = serviceWorld();
  await check("service-draft-asks-before-back-and-unload", servicePath, { overrides }, async (page) => {
    const dialogs = answerDialogs(page);
    await page.getByRole("link", { name: "Edit", exact: true }).click();
    await page.waitForURL(`**${servicePath}/edit`);
    await page.getByLabel("Name", { exact: true }).fill(MARKER);
    // The browser's own Back; a cancelled Back never finishes navigating.
    const back = page.goBack({ timeout: 5_000 }).catch(() => null);
    await eventually(() => dialogs.seen.length === 1, "Browser Back asks first");
    assert.equal(dialogs.seen[0].message, "Discard your unsaved Service changes?");
    await back;
    assert.match(page.url(), /\/edit$/, "Cancelling Back keeps the editor");
    assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), MARKER);
    // Closing or reloading asks too; declining keeps the page.
    await page.close({ runBeforeUnload: true });
    await eventually(() => dialogs.seen.length === 2, "Closing or reloading asks first");
    assert.equal(dialogs.seen[1].type, "beforeunload");
    assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), MARKER);
    // Accepting Back leaves with one question, not a second one from popstate.
    dialogs.acceptNext(true);
    await page.goBack();
    await page.waitForURL(`**${servicePath}`);
    await page.waitForTimeout(300);
    assert.equal(dialogs.seen.length, 3, "One question per Back");
    // The guard left with the editor, so closing no longer asks.
    await page.close({ runBeforeUnload: true });
    await page.waitForEvent("close");
    assert.equal(dialogs.seen.length, 3, "No question after the editor is gone");
  });
}

{
  const { state, overrides } = serviceWorld();
  await check("service-save-clears-navigation-question", `${servicePath}/edit`, { overrides }, async (page) => {
    const dialogs = answerDialogs(page);
    await page.getByLabel("Name", { exact: true }).fill("Counseling (renamed)");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await page.waitForURL(new RegExp(`${servicePath}\\?updated=true$`));
    assert.deepEqual(state.patches, [{ name: "Counseling (renamed)" }]);
    await page.getByRole("link", { name: /Services/ }).first().click();
    await page.waitForURL("**/portal/services");
    assert.equal(dialogs.seen.length, 0, "A saved Service never asks before navigation");
  });
}

{
  const state = {
    windows: [{ id: "window-monday", weekday: "MONDAY", start_time: "08:00:00", end_time: "12:00:00", mode_scope: "ALL" }],
    saves: 0,
  };
  const counselor = withCapabilities("COUNSELOR", ["availability.view", "availability.manage_self", "availability.manage"]);
  await check("weekly-schedule-asks-before-navigation-until-saved", "/portal/availability/me", {
    overrides: {
      "GET /api/v1/auth/session": sessionFor(counselor),
      "GET /api/v1/availability/me/weekly": ({ reply }) => reply({ provider_id: counselor.id, windows: state.windows }),
      "GET /api/v1/availability/me/exceptions": { provider_id: counselor.id, items: [] },
      "PUT /api/v1/availability/me/weekly": ({ reply, request }) => {
        state.saves += 1;
        state.windows = request.postDataJSON().windows.map((window, index) => ({
          id: `saved-${state.saves}-${index}`, ...window, start_time: `${window.start_time}:00`, end_time: `${window.end_time}:00`,
        }));
        return reply({ provider_id: counselor.id, windows: state.windows });
      },
    },
  }, async (page) => {
    const dialogs = answerDialogs(page);
    const save = page.getByRole("button", { name: "Save weekly schedule", exact: true });
    const office = page.getByRole("link", { name: "Office", exact: true });
    await page.getByRole("button", { name: "Add time on Tuesday", exact: true }).click();
    await office.click();
    await eventually(() => dialogs.seen.length === 1, "Leaving with unsaved hours asks first");
    assert.equal(dialogs.seen[0].message, "Discard your unsaved weekly schedule changes?");
    await page.waitForTimeout(300);
    assert.match(page.url(), /\/availability\/me$/, "Cancelling keeps the schedule open");
    // Removing the added hours returns to the saved schedule, which is not an unsaved change.
    await page.getByRole("button", { name: /^Remove .* on Tuesday$/ }).click();
    assert.equal(await save.isDisabled(), true, "Unsaved state compares with the saved schedule");
    await page.getByRole("button", { name: "Add time on Tuesday", exact: true }).click();
    await save.click();
    await shown(page.getByText("Weekly schedule saved.", { exact: true }));
    assert.equal(state.saves, 1);
    await office.click();
    await page.waitForURL("**/portal/availability/office");
    assert.equal(dialogs.seen.length, 1, "Saved hours never ask, and each navigation asked at most once");
  });
}

await finish();
