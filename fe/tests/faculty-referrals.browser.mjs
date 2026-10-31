// Synthetic contract/error fixtures only. The companion live suite uses a disposable real backend.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, finish, shown, artifacts, navigate } = await createBrowserHarness("faculty-referrals");
const root = "/portal/faculty/referrals";
const api = "/api/v1/faculty/referrals";
const tabKey = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
const recordId = "f3000000-0000-4000-8000-000000000001";
const faculty = { ...user("STUDENT"), role: "FACULTY", student_lifecycle_status: null, designations: [], capabilities: ["referrals.submit_self", "referrals.view_submitted_self"], faculty_affiliation: { active: true, college_name: "College of Arts and Sciences", campus_name: "Main Campus", resource_version: 1 } };
const longName = "Synthetic Student " + "LongInstitutionalName".repeat(5);
const record = { id: recordId, reference_code: "REF-2026-000001", submitted_at: "2026-11-01T01:30:00Z", state: "SUBMITTED", student: { display_name: longName } };
const approved = { can_confirm_student: true, can_submit_referral: true, can_view_submissions: true, valid_until: "2099-01-01T00:00:00Z" };
const unavailable = { can_confirm_student: false, can_submit_referral: false, can_view_submissions: false, valid_until: null };

function fixture(options = {}) {
  const calls = [];
  const state = { available: true, confirmations: 0, submissions: 0, ...options };
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
      if (state.submitError) {
        if (state.submitError === 401) state.sessionEnded = true;
        if (state.changeRole) state.account = user("STUDENT");
        if (state.submitError === 403) state.available = false;
        await reply({ error: { code: state.submitError === 403 ? "faculty_referral_submission_policy_unconfirmed" : "referral_creation_conflict", message: "Synthetic denial" } }, state.submitError); return true;
      }
      await reply(record, state.uncertain ? 200 : 201); return true;
    }
    if (pathname === api && method === "GET") {
      if (state.beforeList) await state.beforeList();
      const page = Number(url.searchParams.get("page") ?? 1);
      if (state.listError) { await reply({ error: { code: "faculty_referral_policy_unconfirmed", message: "Synthetic read denial" } }, state.listError); return true; }
      await reply({ items: page > 1 || state.empty ? [] : [record], page, page_size: Number(url.searchParams.get("page_size") ?? 20), has_next: !!state.pages && page === 1 }); return true;
    }
    if (pathname === `${api}/${recordId}`) {
      await reply(state.detailError ? { error: { code: "referral_not_found", message: "Synthetic unavailable" } } : record, state.detailError ?? 200); return true;
    }
    return false;
  } };
}

async function fill(page, reason = "Synthetic confidential concern") {
  await page.getByLabel("Student institutional ID", { exact: true }).fill("SYNTHETIC-EXACT-ID");
  await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
  await shown(page.getByText(longName, { exact: true }));
  await page.getByLabel("Course/Year/Block", { exact: true }).fill("CCMS course declared by CAS Faculty");
  await page.getByLabel("Referral reason", { exact: true }).fill(reason);
}
async function review(page) {
  await page.getByRole("button", { name: "Review referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Review referral", exact: true }));
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
    await page.getByRole("button", { name: "Submit referral", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
    await shown(page.getByText("Your referral has been submitted to the Guidance and Counseling Office.", { exact: true }));
    assert.equal(f.calls.length, 1);
    assert.ok(f.calls[0].key);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, "Confirmation fits enlarged text");
    const storage = await page.evaluate(() => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), location.href]));
    assert.ok(!/SYNTHETIC-EXACT-ID|synthetic-component-memory|Synthetic confidential concern/.test(storage), "No sensitive form data in URL or storage");
    await page.getByRole("link", { name: "View referral details", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Referral details", exact: true }));
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
  await shown(page.getByText("Digital Referrals are not available yet.", { exact: true }));
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
  await page.getByRole("button", { name: "Review referral", exact: true }).click();
  await shown(page.getByText("Enter the exact institutional ID.", { exact: true }));
  assert.equal(await page.getByLabel("Student institutional ID").getAttribute("aria-invalid"), "true");
  assert.equal(await page.getByLabel("Student institutional ID").evaluate(e => e === document.activeElement), true);
  await page.getByLabel("Referral reason").fill("Preserved synthetic input");
  await page.getByRole("button", { name: "Review referral", exact: true }).click();
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "Preserved synthetic input");
});
const uncertainFixture = fixture({ uncertain: true });
await check("uncertain-result-retains-exact-key-body-and-never-auto-retries", root + "/new", { handler: uncertainFixture.handler }, async (page, observed) => {
  const f = uncertainFixture;
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit referral", exact: true }).click();
  await shown(page.getByRole("button", { name: "Retry same submission", exact: true }));
  assert.equal(f.calls.length, 1);
  assert.equal(await page.getByRole("button", { name: "Edit referral information" }).isDisabled(), true);
  await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
  assert.equal(f.calls.length, 2);
  assert.ok(f.calls[0].key === f.calls[1].key && f.calls[0].body === f.calls[1].body, "Exact intended submission is retained");
  assert.equal(facultyWrites(observed.requests).filter(r => r.pathname === api).length, 2);
});

for (const status of [403, 409]) {
  const f = fixture({ submitError: status });
  await check(`submission-refusal-${status}-is-not-success`, root + "/new", { handler: f.handler }, async page => {
    await fill(page); await review(page); await page.getByRole("button", { name: "Submit referral", exact: true }).click();
    await shown(page.getByRole("alert").first());
    assert.equal(await page.getByRole("heading", { name: "Referral submitted" }).count(), 0);
    assert.equal(f.calls.length, 1);
    await shown(page.getByText("Synthetic confidential concern", { exact: true }));
    if (status === 403) await shown(page.getByRole("button", { name: "Check availability" }));
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
  await page.getByRole("button", { name: "Review referral", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Review referral", exact: true }).count(), 0);
  await page.getByRole("button", { name: "Confirm Student again", exact: true }).click();
  await shown(page.getByText(/Confirmation expires /));
  assert.equal(await page.getByLabel("Referral reason").inputValue(), "Synthetic confidential concern");
  await review(page);
});
await check("pagination-keeps-previous-on-empty-later-page", root, { handler: fixture({ pages: true }).handler }, async page => {
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await shown(page.getByText("No referrals on this page. Go back to the previous page.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Previous", exact: true }).isDisabled(), false);
  await page.getByRole("button", { name: "Previous", exact: true }).click();
  await shown(page.getByRole("link", { name: `View referral ${record.reference_code}` }));
});
await check("safe-own-detail-404-never-probes-internal-record", `${root}/${recordId}`, { handler: fixture({ detailError: 404 }).handler }, async (page, observed) => {
  await shown(page.getByText("This referral is not available. Return to My Referrals.", { exact: true }));
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
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.id === "faculty-review-heading");
  await page.keyboard.press(tabKey);
  await page.keyboard.press("Enter");
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
});
await check("own-list-policy-denial-hides-protected-results", root, { handler: fixture({ listError: 403 }).handler }, async page => {
  await shown(page.getByText("Your submitted referrals are not available for this account right now.", { exact: true }));
  assert.equal(await page.getByText(longName, { exact: true }).count(), 0);
});
await check("empty-own-list-is-not-a-fabricated-total", root, { handler: fixture({ empty: true }).handler }, async page => {
  await shown(page.getByText("You have no submitted referrals.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Next", exact: true }).count(), 0);
});
await check("uniform-negative-confirmation-never-advances-to-review", root + "/new", { handler: fixture({ negative: true }).handler }, async page => {
  await page.getByLabel("Student institutional ID").fill("SYNTHETIC-NONCONFIRMED");
  await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
  await shown(page.getByText(/The Student could not be confirmed/));
  assert.equal(await page.getByText(longName, { exact: true }).count(), 0);
});
let releaseSubmit;
const pendingSubmission = new Promise(resolve => { releaseSubmit = resolve; });
const pendingFixture = fixture({ beforeSubmit: () => pendingSubmission });
await check("pending-submit-prevents-duplicates", root + "/new", { handler: pendingFixture.handler }, async page => {
  try {
    await fill(page); await review(page);
    await page.getByRole("button", { name: "Submit referral", exact: true }).click();
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
    assert.equal(await page.getByText("You have no submitted referrals.", { exact: true }).count(), 0);
  } finally { releaseList(); }
  await shown(page.getByRole("button", { name: "Retry", exact: true }));
  retryFixture.state.listError = null;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByRole("link", { name: `View referral ${record.reference_code}` }));
});
const roleChange = fixture({ submitError: 403, changeRole: true });
await check("stale-role-revalidation-unmounts-faculty-form-without-replay", root + "/new", { handler: roleChange.handler }, async page => {
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Workspace unavailable" }));
  assert.equal(await page.getByText("Synthetic confidential concern", { exact: true }).count(), 0);
  assert.equal(roleChange.calls.length, 1);
});
const endedSession = fixture({ submitError: 401 });
await check("ended-session-uses-existing-sign-in-boundary-without-replay", root + "/new", { handler: endedSession.handler }, async page => {
  await fill(page); await review(page);
  await page.getByRole("button", { name: "Submit referral", exact: true }).click();
  await page.waitForURL(url => url.pathname === "/login");
  assert.equal(endedSession.calls.length, 1);
  assert.equal(await page.getByText("Synthetic confidential concern", { exact: true }).count(), 0);
});
for (const role of ["STUDENT", "COUNSELOR", "IT_ADMIN"]) {
  await check(`non-faculty-${role}-direct-route`, root + "/new", { handler: fixture({ account: { ...user(role), capabilities: [...user(role).capabilities, ...faculty.capabilities] } }).handler }, async (page, observed) => {
    await shown(page.getByRole("heading", { name: "Workspace unavailable" }));
    assert.equal(observed.requests.some(r => r.pathname.startsWith(api)), false);
  });
}
await check("faculty-gco-route-denies-before-protected-components-mount", "/portal/referrals/new", { handler: fixture().handler }, async (page, observed) => {
  await shown(page.getByRole("heading", { name: "Workspace unavailable" }));
  assert.equal(observed.requests.some(r => r.pathname.startsWith("/api/v1/referrals")), false);
});
await finish();
