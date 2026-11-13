// Synthetic contract/error fixtures only. The companion live suite uses a disposable real backend.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { civilDays, manilaDay, reportedTimingFixture } from "./support/referral-timing-fixtures.mjs";

const { check, finish, shown, artifacts, navigate } = await createBrowserHarness("faculty-referrals");
const root = "/portal/faculty/referrals";
const api = "/api/v1/faculty/referrals";
const tabKey = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
const recordId = "f3000000-0000-4000-8000-000000000001";
const faculty = { ...user("STUDENT"), role: "FACULTY", student_lifecycle_status: null, designations: [], capabilities: ["referrals.submit_self", "referrals.view_submitted_self"], faculty_affiliation: { active: true, college_name: "College of Arts and Sciences", campus_name: "Main Campus", resource_version: 1 } };
const longName = "Synthetic Student " + "LongInstitutionalName".repeat(5);
const record = { id: recordId, reference_code: "REF-2026-000001", submitted_at: "2026-11-01T01:30:00Z", state: "SUBMITTED", student: { display_name: longName }, received_at: null, closed_at: null, timing_status: "NOT_PROVIDED" };
const approved = { can_confirm_student: true, can_submit_referral: true, can_view_submissions: true, valid_until: "2099-01-01T00:00:00Z" };
const unavailable = { can_confirm_student: false, can_submit_referral: false, can_view_submissions: false, valid_until: null };

function fixture(options = {}) {
  const calls = [];
  const state = { available: true, confirmations: 0, submissions: 0, statement: null, ...options };
  const detail = () => ({ ...record, timing_status: state.statement?.answer_kind ?? "NOT_PROVIDED", scheduling_statement: state.statement });
  const summary = () => { const { scheduling_statement, ...item } = detail(); void scheduling_statement; return item; };
  return { state, calls, handler: async ({ pathname, method, request, reply, route, url }) => {
    if (pathname === "/api/v1/auth/session") { await reply(state.sessionEnded ? { error: { code: "session_unavailable", message: "Synthetic session ended" } } : sessionFor(state.account ?? faculty), state.sessionEnded ? 401 : 200); return true; }
    if (pathname === api + "/availability") { await reply(state.available ? (state.availability ?? approved) : unavailable); return true; }
    if (pathname === api + "/student-confirmation") {
      state.confirmations++;
      if (state.confirmError) {
        await route.fulfill({ status: state.confirmError, contentType: "application/json", headers: { "Retry-After": "2" }, body: JSON.stringify({ error: { code: state.confirmError === 429 ? "faculty_referral_rate_limited" : "faculty_referral_confirmation_unavailable", message: "Synthetic denial" } }) }); return true;
      }
      await reply(state.negative ? { confirmed: false, student: null, confirmation: null, expires_at: null } : { confirmed: true, student: record.student, confirmation: `synthetic-component-memory-${state.confirmations}`, expires_at: new Date(Date.now() + (state.expiring && state.confirmations === 1 ? 1300 : 300000)).toISOString() }); return true;
    }
    if (pathname === api && method === "POST") {
      state.submissions++;
      calls.push({ key: request.headers()["idempotency-key"], body: request.postData() });
      if (state.beforeSubmit) await state.beforeSubmit();
      if (state.uncertain && state.submissions === 1) { await route.abort("failed"); return true; }
      if (state.timingError) { await reply({ error: { code: "referral_timing_invalid", message: "Check the timing information.", details: [{ loc: ["body", "scheduling_statement", "windows", "0", "end_time"], message: "End time must be after start time." }] } }, 422); return true; }
      if (state.submitError) {
        if (state.submitError === 401) state.sessionEnded = true;
        if (state.changeRole) state.account = user("STUDENT");
        if (state.submitError === 403) state.available = false;
        await reply({ error: { code: state.submitError === 403 ? "faculty_referral_ineligible" : "referral_creation_conflict", message: "Synthetic denial" } }, state.submitError); return true;
      }
      const statement = request.postDataJSON().scheduling_statement;
      state.statement = statement ? reportedTimingFixture({ ...statement, windows: statement.windows.map(window => ({ ...window, expired: false })), created_at: new Date().toISOString() }) : null;
      await reply(detail(), state.uncertain ? 200 : 201); return true;
    }
    if (pathname === api && method === "GET") {
      if (state.beforeList) await state.beforeList();
      const page = Number(url.searchParams.get("page") ?? 1);
      if (state.listError) { await reply({ error: { code: "permission_denied", message: "Synthetic read denial" } }, state.listError); return true; }
      await reply({ items: page > 1 || state.empty ? [] : [summary()], page, page_size: Number(url.searchParams.get("page_size") ?? 20), has_next: !!state.pages && page === 1 }); return true;
    }
    if (pathname === `${api}/${recordId}`) {
      await reply(state.detailError ? { error: { code: "referral_not_found", message: "Synthetic unavailable" } } : detail(), state.detailError ?? 200); return true;
    }
    return false;
  } };
}

async function fill(page, reason = "Synthetic confidential concern", answer = "UNKNOWN") {
  await page.getByLabel("Student institutional ID", { exact: true }).fill("SYNTHETIC-EXACT-ID");
  await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
  await shown(page.getByText(longName, { exact: true }));
  await page.getByLabel("Course/Year/Block", { exact: true }).fill("CCMS course declared by CAS Faculty");
  await page.getByLabel("Referral reason", { exact: true }).fill(reason);
  if (answer) await page.getByRole("radio", { name: answer === "UNKNOWN" ? "Unknown / needs confirmation" : "Known times", exact: true }).check();
}
async function review(page) {
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Review Referral", exact: true }));
  await page.waitForFunction(() => document.activeElement?.id === "faculty-review-heading");
}
const facultyWrites = (requests) => requests.filter(r => r.pathname.startsWith(api) && r.method === "POST");

for (const width of [320, 390, 768, 1024, 1440]) for (const scale of [100, 200]) {
  const f = fixture();
  await check(`responsive-${width}-${scale}`, root + "/new", { handler: f.handler, viewport: { width, height: 1000 } }, async (page, observed) => {
    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: scale === 200 ? "dark" : "light" });
    await shown(page.getByRole("heading", { name: "Submit Referral", exact: true }));
    await page.evaluate(value => { document.documentElement.style.fontSize = `${value}%`; }, scale);
    await fill(page, "Synthetic confidential concern " + "LongWord".repeat(50));
    assert.equal(await page.getByLabel("Student institutional ID").getAttribute("autocomplete"), "off");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, "Form fits enlarged text");
    if ([320, 1440].includes(width)) await page.screenshot({ path: join(artifacts, `form-${width}-${scale}.png`), fullPage: true });
    await review(page);
    assert.equal(await page.locator("#faculty-review-heading").evaluate(e => e === document.activeElement), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, "Review fits enlarged text");
    if ((width === 1440 && scale === 100) || (width === 320 && scale === 200)) await page.screenshot({ path: join(artifacts, `review-${width}-${scale}.png`), fullPage: true });
    await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
    await shown(page.getByText("Your Referral has been submitted to the Guidance Office.", { exact: true }));
    assert.equal(f.calls.length, 1);
    assert.ok(f.calls[0].key);
    assert.deepEqual(JSON.parse(f.calls[0].body).scheduling_statement, { answer_kind: "UNKNOWN", windows: [], note: "" });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, "Confirmation fits enlarged text");
    const storage = await page.evaluate(() => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), location.href]));
    assert.ok(!/SYNTHETIC-EXACT-ID|synthetic-component-memory|Synthetic confidential concern/.test(storage), "No sensitive form data in URL or storage");
    await page.getByRole("link", { name: "View Referral details", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Referral details", exact: true }));
    await shown(page.getByText("Unknown / needs confirmation", { exact: true }));
    assert.equal(await page.getByRole("heading", { name: "Verified availability", exact: true }).count(), 0);
    assert.equal(await page.getByText(/Synthetic confidential concern/).count(), 0);
    assert.equal(observed.requests.some(r => /\/api\/v1\/(?:referrals|accounts|counseling|guidance-followups)(?:\/|$)/.test(r.pathname)), false);
    if ([320, 1440].includes(width)) await page.screenshot({ path: join(artifacts, `detail-${width}-${scale}.png`), fullPage: true });
  });
}

await check("default-unavailable-home-and-direct-submission", "/portal", { handler: fixture({ available: false }).handler }, async (page, observed) => {
  await shown(page.getByRole("heading", { name: "Faculty Home", exact: true }));
  await shown(page.getByText("Digital Student Referrals are not available yet.", { exact: true }));
  assert.equal(await page.locator(`a[href="${root}/new"]`).count(), 0);
  await page.screenshot({ path: join(artifacts, "home-unavailable.png"), fullPage: true });
  await navigate(page, root + "/new");
  await shown(page.getByText("You can't submit digital Referrals right now.", { exact: true }));
  assert.equal(await page.getByLabel("Student institutional ID").count(), 0);
  assert.equal(facultyWrites(observed.requests).length, 0);
});
await check("own-list-alone-never-enables-submission", "/portal", { handler: fixture({ availability: { ...approved, can_confirm_student: false, can_submit_referral: false } }).handler }, async page => {
  await shown(page.getByRole("heading", { name: "Recent referrals" }));
  assert.equal(await page.locator(`a[href="${root}/new"]`).count(), 0);
  await page.screenshot({ path: join(artifacts, "home-own-read-only.png"), fullPage: true });
});
await check("approved-home-uses-actual-own-records-and-primary-action", "/portal", { handler: fixture().handler }, async page => {
  await shown(page.getByRole("heading", { name: "Recent referrals" }));
  await shown(page.locator("[data-page-header-actions]").getByRole("link", { name: "Submit Referral", exact: true }));
  await shown(page.getByText("Main Campus · College of Arts and Sciences", { exact: true }));
  await page.screenshot({ path: join(artifacts, "home-approved.png"), fullPage: true });
});
await check("form-errors-focus-original-fields-and-preserve-input", root + "/new", { handler: fixture().handler }, async page => {
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await shown(page.getByText("Enter the exact institutional ID.", { exact: true }));
  assert.equal(await page.getByLabel("Student institutional ID").getAttribute("aria-invalid"), "true");
  assert.equal(await page.getByLabel("Student institutional ID").evaluate(e => e === document.activeElement), true);
  await page.getByLabel("Referral reason").fill("Preserved synthetic input");
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "Preserved synthetic input");
});
const uncertainFixture = fixture({ uncertain: true });
await check("uncertain-result-retains-exact-key-body-and-never-auto-retries", root + "/new", { handler: uncertainFixture.handler }, async (page, observed) => {
  const f = uncertainFixture;
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
  await shown(page.getByRole("button", { name: "Retry same submission", exact: true }));
  assert.equal(f.calls.length, 1);
  assert.equal(await page.getByRole("button", { name: "Edit Referral information" }).isDisabled(), true);
  await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
  assert.equal(f.calls.length, 2);
  assert.ok(f.calls[0].key === f.calls[1].key && f.calls[0].body === f.calls[1].body, "Exact intended submission is retained");
  assert.equal(facultyWrites(observed.requests).filter(r => r.pathname === api).length, 2);
});

for (const status of [403, 409]) {
  const f = fixture({ submitError: status });
  await check(`submission-refusal-${status}-is-not-success`, root + "/new", { handler: f.handler }, async page => {
    await fill(page); await review(page); await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
    await shown(page.getByRole("alert").first());
    assert.equal(await page.getByRole("heading", { name: "Referral submitted" }).count(), 0);
    assert.equal(f.calls.length, 1);
    await shown(page.getByText("Synthetic confidential concern", { exact: true }));
    if (status === 403) await shown(page.getByRole("button", { name: "Check Availability" }));
  });
}
for (const status of [429, 503]) {
  const f = fixture({ confirmError: status });
  await check(`confirmation-refusal-${status}-preserves-exact-input`, root + "/new", { handler: f.handler }, async page => {
    await page.getByLabel("Student institutional ID").fill("SYNTHETIC-EXACT-ID");
    await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
    await shown(page.getByRole("alert").first());
    assert.equal(await page.getByLabel("Student institutional ID").inputValue(), "SYNTHETIC-EXACT-ID");
    assert.equal(f.state.submissions, 0);
    if (status === 429) assert.equal(await page.getByRole("button", { name: "Confirm Student", exact: true }).isDisabled(), true);
  });
}
await check("expired-confirmation-requires-deliberate-reconfirmation", root + "/new", { handler: fixture({ expiring: true }).handler }, async page => {
  await fill(page);
  await shown(page.getByText("Confirmation expired.", { exact: true }));
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Review Referral", exact: true }).count(), 0);
  await page.getByRole("button", { name: "Confirm Student again", exact: true }).click();
  await shown(page.getByText(/Confirmation expires /));
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "Synthetic confidential concern");
  await review(page);
});
await check("pagination-keeps-previous-on-empty-later-page", root, { handler: fixture({ pages: true }).handler }, async page => {
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await shown(page.getByText("No Referrals on this page. Go back to the previous page.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Previous", exact: true }).isDisabled(), false);
  await page.getByRole("button", { name: "Previous", exact: true }).click();
  await shown(page.getByRole("link", { name: `View Referral ${record.reference_code}` }));
});
await check("safe-own-detail-404-never-probes-internal-record", `${root}/${recordId}`, { handler: fixture({ detailError: 404 }).handler }, async (page, observed) => {
  await shown(page.getByText("This Referral is not available. Return to My Referrals.", { exact: true }));
  assert.equal(observed.requests.some(r => r.pathname.startsWith("/api/v1/referrals")), false);
});
await check("keyboard-only-confirm-review-submit", root + "/new", { handler: fixture().handler }, async page => {
  const input = page.getByLabel("Student institutional ID");
  await input.focus();
  await page.keyboard.type("SYNTHETIC-EXACT-ID");
  await page.keyboard.press(tabKey);
  await page.keyboard.press("Enter");
  await shown(page.getByText(longName, { exact: true }));
  await page.keyboard.press(tabKey);
  assert.equal(await page.getByLabel("Course/Year/Block").evaluate(e => e === document.activeElement), true);
  await page.keyboard.type("Synthetic course");
  await page.keyboard.press(tabKey);
  await page.keyboard.type("Synthetic relevant observations");
  await page.keyboard.press(tabKey);
  assert.equal(await page.getByRole("radio", { name: "Known times", exact: true }).evaluate(e => e === document.activeElement), true);
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.getByRole("radio", { name: "Unknown / needs confirmation", exact: true }).isChecked(), true);
  await page.keyboard.press(tabKey);
  assert.equal(await page.getByRole("button", { name: "Review Referral", exact: true }).evaluate(e => e === document.activeElement), true);
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.id === "faculty-review-heading");
  await page.keyboard.press(tabKey);
  await page.keyboard.press("Enter");
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
});
await check("own-list-policy-denial-hides-protected-results", root, { handler: fixture({ listError: 403 }).handler }, async page => {
  await shown(page.getByText("You don't have access to your submitted Referrals.", { exact: true }));
  assert.equal(await page.getByText(longName, { exact: true }).count(), 0);
});
await check("empty-own-list-is-not-a-fabricated-total", root, { handler: fixture({ empty: true }).handler }, async page => {
  await shown(page.getByText("You have no submitted Referrals.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Next", exact: true }).count(), 0);
});
await check("uniform-negative-confirmation-never-advances-to-review", root + "/new", { handler: fixture({ negative: true }).handler }, async page => {
  await page.getByLabel("Student institutional ID").fill("SYNTHETIC-NONCONFIRMED");
  await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
  await shown(page.getByText(/Couldn't confirm the Student/));
  assert.equal(await page.getByText(longName, { exact: true }).count(), 0);
});
let releaseSubmit;
const pendingSubmission = new Promise(resolve => { releaseSubmit = resolve; });
const pendingFixture = fixture({ beforeSubmit: () => pendingSubmission });
await check("pending-submit-prevents-duplicates", root + "/new", { handler: pendingFixture.handler }, async page => {
  try {
    await fill(page); await review(page);
    await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
    await shown(page.getByRole("button", { name: "Submitting…", exact: true }));
    assert.equal(await page.getByRole("button", { name: "Submitting…", exact: true }).isDisabled(), true);
    assert.equal(pendingFixture.calls.length, 1);
  } finally { releaseSubmit(); }
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
});
await check("discard-is-deliberate-and-cancel-preserves-draft", root + "/new", { handler: fixture().handler }, async page => {
  await fill(page);
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "Discard draft", exact: true }).click();
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "Synthetic confidential concern");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Discard draft", exact: true }).click();
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "");
  assert.equal(await page.getByLabel("Student institutional ID").inputValue(), "");
});
let releaseList;
const pendingList = new Promise(resolve => { releaseList = resolve; });
const retryFixture = fixture({ beforeList: () => pendingList, listError: 503 });
await check("initial-loading-then-retry-never-claims-empty", root, { handler: retryFixture.handler }, async page => {
  try {
    await shown(page.getByText("Loading Faculty Referrals…", { exact: true }));
    assert.equal(await page.getByText("You have no submitted Referrals.", { exact: true }).count(), 0);
  } finally { releaseList(); }
  await shown(page.getByRole("button", { name: "Retry", exact: true }));
  retryFixture.state.listError = null;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByRole("link", { name: `View Referral ${record.reference_code}` }));
});
const roleChange = fixture({ submitError: 403, changeRole: true });
await check("stale-role-revalidation-unmounts-faculty-form-without-replay", root + "/new", { handler: roleChange.handler }, async page => {
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Workspace access" }));
  assert.equal(await page.getByText("Synthetic confidential concern", { exact: true }).count(), 0);
  assert.equal(roleChange.calls.length, 1);
});
const endedSession = fixture({ submitError: 401 });
await check("ended-session-uses-existing-sign-in-boundary-without-replay", root + "/new", { handler: endedSession.handler }, async page => {
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
  await page.waitForURL(url => url.pathname === "/login");
  await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
  // Finish the destination render before closing the context. Aborting its first optimized
  // logo request leaves later WebKit sign-in captures waiting on that same in-flight image.
  await page.waitForFunction(() => [...document.images].every(image => image.complete && image.naturalWidth > 0));
  assert.equal(endedSession.calls.length, 1);
  assert.equal(await page.getByText("Synthetic confidential concern", { exact: true }).count(), 0);
});
for (const role of ["STUDENT", "COUNSELOR", "IT_ADMIN"]) {
  await check(`non-faculty-${role}-direct-route`, root + "/new", { handler: fixture({ account: { ...user(role), capabilities: [...user(role).capabilities, ...faculty.capabilities] } }).handler }, async (page, observed) => {
    await shown(page.getByRole("heading", { name: "Workspace access" }));
    assert.equal(observed.requests.some(r => r.pathname.startsWith(api)), false);
  });
}
await check("faculty-gco-route-denies-before-protected-components-mount", "/portal/referrals/new", { handler: fixture().handler }, async (page, observed) => {
  await shown(page.getByRole("heading", { name: "Workspace access" }));
  assert.equal(observed.requests.some(r => r.pathname.startsWith("/api/v1/referrals")), false);
});

async function specificWindow(page) {
  await page.getByRole("button", { name: "Add window", exact: true }).click();
  const row = page.getByRole("group", { name: "Window 1 of 1", exact: true });
  await row.getByLabel("Date · Philippine Time", { exact: true }).fill(civilDays(manilaDay(), 2));
  await row.getByLabel("Start time · Philippine Time", { exact: true }).fill("10:00");
  await row.getByLabel("End time · Philippine Time", { exact: true }).fill("11:00");
  return row;
}

for (const width of [320, 390, 1440]) {
  const f = fixture();
  await check(`mixed-windows-own-detail-and-marker-only-${width}`, root + "/new", { handler: f.handler, viewport: { width, height: 1000 }, timezoneId: "America/Los_Angeles" }, async (page, observed) => {
    await fill(page, "Synthetic confidential concern", "KNOWN");
    await specificWindow(page);
    await page.getByRole("button", { name: "Add window", exact: true }).click();
    const second = page.getByRole("group", { name: "Window 2 of 2", exact: true });
    await second.getByLabel("Information type", { exact: true }).selectOption("CLASS_RELEASE");
    await second.getByLabel("Pattern", { exact: true }).selectOption("RECURRING_WEEKDAY");
    await second.getByLabel("Weekday", { exact: true }).selectOption("SATURDAY");
    await second.getByLabel("Valid until · Philippine Time", { exact: true }).fill(civilDays(manilaDay(), 7));
    await second.getByLabel("Start time · Philippine Time", { exact: true }).fill("13:00");
    await second.getByLabel("End time · Philippine Time", { exact: true }).fill("14:00");
    await page.getByLabel("Scheduling constraints note (optional)", { exact: true }).fill("Synthetic timetable constraint only");
    if (width === 320) await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    await page.screenshot({ path: join(artifacts, `mixed-editor-${width}.png`), fullPage: true });
    await review(page);
    await shown(page.getByText("The student is usually free", { exact: true }));
    await shown(page.getByText("The student may leave the referrer’s class", { exact: true }));
    await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
    const submitted = JSON.parse(f.calls[0].body).scheduling_statement;
    assert.equal(submitted.answer_kind, "KNOWN");
    assert.equal(submitted.windows.length, 2);
    assert.equal(submitted.windows[1].information_type, "CLASS_RELEASE");
    assert.equal(submitted.windows[1].date, null);
    await page.getByRole("link", { name: "View Referral details", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Reported by the referrer", exact: true }));
    await shown(page.getByText(/Synthetic timetable constraint only/));
    assert.equal(await page.getByRole("heading", { name: "Verified availability", exact: true }).count(), 0);
    assert.equal(await page.getByText("Student confirmed", { exact: true }).count(), 0);
    assert.equal(observed.requests.some(request => request.pathname.startsWith("/api/v1/referrals")), false);
    await page.getByRole("link", { name: "Back to My Referrals", exact: true }).click();
    await shown(page.getByText("Timing: Known", { exact: true }));
    assert.equal(await page.getByText(/Synthetic timetable constraint only/).count(), 0);
  });
}

await check("timing-errors-use-field-order-and-retain-partial-windows", root + "/new", { handler: fixture().handler, viewport: { width: 390, height: 844 } }, async page => {
  await fill(page, "Synthetic concern", null);
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-answer_kind");
  await page.getByRole("radio", { name: "Known times", exact: true }).check();
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-add-window");
  await page.getByRole("button", { name: "Add window", exact: true }).click();
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-window-1-date");
  const row = page.getByRole("group", { name: "Window 1 of 1", exact: true });
  assert.equal(await row.getByLabel("Date · Philippine Time", { exact: true }).getAttribute("aria-invalid"), "true");
  await row.getByLabel("Date · Philippine Time", { exact: true }).fill(manilaDay());
  await row.getByLabel("Start time · Philippine Time", { exact: true }).fill("11:00");
  await row.getByLabel("End time · Philippine Time", { exact: true }).fill("10:00");
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-window-1-end_time");
  await shown(page.getByText("End time must be after start time.", { exact: true }));
  await row.getByLabel("End time · Philippine Time", { exact: true }).fill("12:00");
  await page.getByLabel("Scheduling constraints note (optional)", { exact: true }).fill("🌱".repeat(501));
  await page.getByRole("button", { name: "Review Referral", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-note");
  assert.equal(await page.getByLabel("Scheduling constraints note (optional)").inputValue(), "🌱".repeat(501));
  await page.getByRole("radio", { name: "Unknown / needs confirmation", exact: true }).check();
  await page.getByRole("radio", { name: "Known times", exact: true }).check();
  assert.equal(await row.getByLabel("Start time · Philippine Time", { exact: true }).inputValue(), "11:00");
});

await check("five-window-limit-remove-renumbers-and-restores-focus", root + "/new", { handler: fixture().handler }, async page => {
  await page.getByRole("radio", { name: "Known times", exact: true }).check();
  for (let i = 0; i < 5; i++) await page.getByRole("button", { name: "Add window", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Add window", exact: true }).isDisabled(), true);
  await shown(page.getByRole("group", { name: "Window 5 of 5", exact: true }));
  await page.getByRole("button", { name: "Remove Window 2", exact: true }).click();
  await shown(page.getByRole("group", { name: "Window 4 of 4", exact: true }));
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-add-window");
  assert.equal(await page.getByRole("button", { name: "Add window", exact: true }).isEnabled(), true);
});

const timingFailure = fixture({ timingError: true });
await check("backend-window-refusal-returns-to-preserved-field-with-focus", root + "/new", { handler: timingFailure.handler }, async page => {
  await fill(page, "Synthetic concern", "KNOWN");
  await specificWindow(page); await review(page);
  await page.getByRole("button", { name: "Submit Referral", exact: true }).click();
  await shown(page.getByText("End time must be after start time.", { exact: true }));
  await page.waitForFunction(() => document.activeElement?.id === "faculty-timing-window-1-end_time");
  assert.equal(await page.getByLabel("Start time · Philippine Time", { exact: true }).inputValue(), "10:00");
  assert.equal(timingFailure.calls.length, 1);
  assert.equal(await page.getByRole("heading", { name: "Referral submitted", exact: true }).count(), 0);
});

await check("partial-timing-draft-navigation-warns-and-cancel-keeps-input", root + "/new", { handler: fixture().handler }, async page => {
  await page.getByRole("radio", { name: "Known times", exact: true }).check();
  await page.getByRole("button", { name: "Add window", exact: true }).click();
  await page.getByLabel("Start time · Philippine Time", { exact: true }).fill("09:30");
  let warned = 0;
  page.once("dialog", async dialog => { warned++; assert.match(dialog.message(), /unsaved Referral/); await dialog.dismiss(); });
  await page.locator('a[href="/portal"]').first().click();
  assert.equal(warned, 1);
  assert.equal(new URL(page.url()).pathname, root + "/new");
  assert.equal(await page.getByLabel("Start time · Philippine Time", { exact: true }).inputValue(), "09:30");
  page.once("dialog", dialog => dialog.accept());
  await page.locator('a[href="/portal"]').first().click();
  await shown(page.getByRole("heading", { name: "Faculty Home", exact: true }));
});

await check("own-historical-statement-is-read-only-and-keeps-expired-windows", `${root}/${recordId}`, { handler: fixture({ statement: reportedTimingFixture() }).handler }, async (page, observed) => {
  await shown(page.getByText("This time has passed", { exact: true }));
  await shown(page.getByText(/^No longer valid after /));
  assert.equal(await page.getByRole("heading", { name: "Verified availability", exact: true }).count(), 0);
  assert.equal(await page.getByRole("radio").count(), 0);
  assert.equal(observed.requests.some(request => request.pathname.startsWith("/api/v1/referrals")), false);
});
await finish();
