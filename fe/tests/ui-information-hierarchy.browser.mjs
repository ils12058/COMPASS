// Run against a local Next server. Every API read/write uses synthetic fixtures; no account,
// Daily room, credential, recording, notification or institutional record is touched.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";
import { appointmentId, serviceId, appointment, service, workspace, consents, user, slip } from "./support/ui-hierarchy-fixtures.mjs";

const baseURL = process.env.COMPASS_UI_BASE_URL ?? "http://localhost:3107";
assert.ok(["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname), "Use a local Next server");
const artifacts = process.env.COMPASS_UI_ARTIFACTS ?? join(tmpdir(), "compass-ui-information-hierarchy");
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.COMPASS_UI_BROWSER_CHANNEL ? { channel: process.env.COMPASS_UI_BROWSER_CHANNEL } : {}) });
const emptyPage = { items: [], page: 1, page_size: 20, has_next: false };
const failures = [];
const results = [];

async function openPage(path, { role = "COUNSELOR", mobile = false, tablet = false, studentContext = false, mediaStatus = "NOT_STARTED", decision = "APPROVED", disabledVideo = false, overrides = {} } = {}) {
  const context = await browser.newContext(mobile
    ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }
    : { viewport: { width: tablet ? 1024 : 1440, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(12_000);
  const errors = [];
  const requests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route(/\/api\/v1(?:\/|\?)/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();
    requests.push({ pathname, method, search: url.search, body: request.postData() });
    const reply = (body, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { date: new Date().toUTCString() }, body: JSON.stringify(body) });
    const override = overrides[`${method} ${pathname}`] ?? overrides[pathname];
    if (override) {
      if (typeof override === "function") return override({ route, reply, request, url });
      return reply(override);
    }
    if (pathname === "/api/v1/auth/session") return reply({ user: user(role), session: { id: "test-session", expires_at: "2099-10-07T00:00:00Z", is_current: true } });
    if (pathname === "/api/v1/auth/csrf") return reply({ csrf_token: "synthetic-csrf-token" });
    if (pathname === "/api/v1/me/profile") return reply({ full_name: "Example User", photo: null });
    if (pathname === "/api/v1/platform/status") return reply({ status: "operational", starts_at: null, ends_at: null, message: null });
    if (pathname === "/api/v1/notifications/unread-count") return reply({ unread_count: 0 });
    if (pathname === "/api/v1/notifications/push/config") return reply({ enabled: false, vapid_public_key: null });
    if (pathname === "/api/v1/privacy/my-notices") return reply(emptyPage);
    if (/\/e-counseling\/(?:me\/)?appointments\/[^/]+\/consents$/.test(pathname)) return reply({ items: consents(decision) });
    if (/\/e-counseling\/(?:me\/)?appointments\/[^/]+$/.test(pathname)) {
      const data = workspace(mediaStatus);
      data.counseling_context_available = studentContext;
      if (disabledVideo) data.provider_readiness = { ...data.provider_readiness, daily_enabled: false, join_allowed: false, join_state: "PROVIDER_DISABLED" };
      return reply(data);
    }
    if (pathname === `/api/v1/appointments/${appointmentId}`) return reply(appointment);
    if (pathname === `/api/v1/appointments/${appointmentId}/history`) return reply({ items: [] });
    if (pathname === `/api/v1/appointments/${appointmentId}/reassignment-candidates`) return reply({ items: [{ id: "other-counselor", display_name: "Ana Cruz" }] });
    if (pathname === `/api/v1/appointments/${appointmentId}/reschedule-slots`) return reply({ items: [{ starts_at: `${url.searchParams.get("date")}T04:00:00Z`, ends_at: `${url.searchParams.get("date")}T05:00:00Z` }], timezone: "Asia/Manila" });
    if (pathname === "/api/v1/appointments") return reply({ ...emptyPage, items: [appointment], ordering: url.searchParams.get("ordering") ?? "EARLIEST_START" });
    if (pathname === "/api/v1/appointments/booking/services") return reply({ items: [service] });
    if (pathname === "/api/v1/appointments/booking/counselors") return reply({ items: [appointment.provider] });
    if (pathname === `/api/v1/services/${serviceId}`) return reply(service);
    if (pathname === `/api/v1/services/${serviceId}/providers`) return reply({ provider_coverage: "ALL_COUNSELORS", counselors: [{ ...appointment.provider, is_active: true }] });
    if (pathname === "/api/v1/services" || pathname === "/api/v1/services/provider-candidates") return reply({ ...emptyPage, items: pathname.endsWith("provider-candidates") ? [appointment.provider] : [service] });
    if (pathname === `/api/v1/counseling/context/APPOINTMENT/${appointmentId}`) return reply({
      source_type: "APPOINTMENT", source_id: appointmentId, entry_mode: "APPOINTMENT", delivery_mode: "ONLINE",
      valid_from: "2026-01-01T00:00:00Z", valid_until: "2099-01-01T00:00:00Z",
      student: { ...appointment.student, campus: null, college: null, program: null, year_level: 4 },
      matching_encounter: null, routine_interview: null, available_sections: ["OVERVIEW"],
    });
    if (pathname === "/api/v1/institutional-forms") return reply({ items: [{ id: "family", key: "CALL_SLIP", title: "Call Slip", revision_required: true, configuration_state: "MISSING_REQUIRED_REVISION" }] });
    if (/\/institutional-forms\/[^/]+\/revisions$/.test(pathname)) return reply({ items: [{ id: "revision", family_key: "CALL_SLIP", internal_schema_version: 1, official_code: "TEST-CS", official_revision: "1", status: "ACTIVE", supported: false }] });
    if (pathname.startsWith("/api/v1/organization/")) return reply(emptyPage);
    if (pathname === `/api/v1/call-slips/${slip.id}` || pathname === `/api/v1/call-slips/me/${slip.id}`) return reply({ ...slip, updated_at: slip.created_at });
    if (pathname === "/api/v1/platform/health") return reply({ status: "ok", summary: "Dependencies checked", timestamp: new Date().toISOString(), checks: [{ code: "database", label: "Database", status: "ok", summary: "Database is reachable" }] });
    if (method !== "GET") return reply({ error: { code: "synthetic_failure", message: "Synthetic mutation rejected" } }, 500);
    return reply({ error: { code: "synthetic_unavailable", message: "No fixture for this optional read" } }, 404);
  });
  await page.goto(`${baseURL}${path}`, { waitUntil: "domcontentloaded" });
  return { page, context, errors, requests };
}

async function check(name, path, options, run) {
  if (process.env.COMPASS_UI_CHECK && !new RegExp(process.env.COMPASS_UI_CHECK).test(name)) return;
  let fixture;
  try {
    fixture = await openPage(path, options);
    await run(fixture.page, fixture);
    assert.deepEqual(fixture.errors, [], "No browser runtime errors");
    results.push({ name, passed: true });
    console.log(`PASS ${name}`);
  } catch (error) {
    failures.push(name);
    results.push({ name, passed: false, message: error.message });
    console.error(`FAIL ${name}: ${error.message}`);
    await fixture?.page.screenshot({ path: join(artifacts, `${name}-failure.png`), fullPage: true }).catch(() => {});
  } finally {
    await fixture?.context.close();
  }
}

async function shown(locator) { await locator.waitFor({ state: "visible" }); }
async function hidden(locator) { await locator.waitFor({ state: "hidden" }); }
async function screenshot(page, name) { await page.screenshot({ path: join(artifacts, `${name}.png`), fullPage: true }); }
async function noHorizontalOverflow(page) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, "Page fits its viewport");
}

const ePath = `/portal/e-counseling/${appointmentId}`;
await check("help-keyboard-focus", ePath, {}, async (page) => {
  const help = page.getByRole("button", { name: "Help: About E-Counseling", exact: true });
  await shown(help);
  await help.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "About E-Counseling", exact: true });
  await shown(dialog);
  for (const name of ["Media consent", "Recording", "Transcription", "Transcript storage", "Encounter records"]) await shown(dialog.getByRole("heading", { name, exact: true }));
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true);
  await page.keyboard.press("Tab");
  assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, "Focus stays in Help");
  await page.keyboard.press("Escape");
  await hidden(dialog);
  await page.waitForFunction((element) => element === document.activeElement, await help.elementHandle());
});

await check("active-media-state", ePath, { mediaStatus: "ACTIVE", studentContext: true }, async (page) => {
  await shown(page.getByRole("heading", { name: "Media controls", exact: true }));
  const status = page.locator('[aria-live="polite"]').filter({ hasText: "Recording" }).first();
  assert.match(await status.innerText(), /Recording[\s\S]*Active[\s\S]*Transcription[\s\S]*Active/);
  await shown(page.getByRole("button", { name: "Stop recording", exact: true }));
  await shown(page.getByRole("button", { name: "Stop transcription", exact: true }));
  await shown(page.getByRole("tab", { name: "Overview", exact: true }));
  await shown(page.getByText("Available until", { exact: true }));
  await screenshot(page, "e-counseling-counselor");
});

await check("visible-video-blocker", ePath, { disabledVideo: true }, async (page) => {
  await shown(page.getByText(/^Video sessions are off/));
  await hidden(page.getByRole("button", { name: "Start recording", exact: true }));
  await hidden(page.getByRole("dialog"));
});

await check("recording-consequence", ePath, {}, async (page) => {
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Start audio/video recording?" });
  await shown(dialog);
  assert.match(await dialog.innerText(), /captures audio and video/);
  assert.match(await dialog.innerText(), /student has approved recording/);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
});

await check("transcription-consequence", ePath, {}, async (page) => {
  await page.getByRole("button", { name: "Start transcription", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Start session transcription?" });
  await shown(dialog);
  assert.match(await dialog.innerText(), /Speech will be processed as text/);
  assert.match(await dialog.innerText(), /Transcript storage is off/);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
});

await check("student-consent-meaning", ePath, { role: "STUDENT", decision: "PENDING" }, async (page) => {
  await shown(page.getByRole("heading", { name: "Media permissions", exact: true }));
  assert.match(await page.locator("main").innerText(), /does not affect your ability to receive Counseling/);
  await shown(page.getByText(/audio and video from this Counseling session to be recorded/));
  await shown(page.getByText(/speech from this session to be processed as text/));
  await shown(page.getByText(/stored by the video service/));
  assert.equal(await page.getByRole("button", { name: /^Allow / }).count(), 2);
  assert.equal(await page.getByRole("button", { name: /^Decline / }).count(), 2);
  await page.getByRole("button", { name: "Allow audio/video recording", exact: true }).click();
  const review = page.getByRole("alertdialog");
  await shown(review);
  assert.match(await review.innerText(), /audio and video/);
  await review.getByRole("button", { name: "Cancel", exact: true }).click();
  await screenshot(page, "e-counseling-student");
});

await check("encounter-draft-focus", ePath, {}, async (page) => {
  const trigger = page.getByRole("button", { name: "Record encounter", exact: true });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Record encounter", exact: true });
  await dialog.getByLabel("Actual start", { exact: true }).fill("2026-01-06T09:00");
  await dialog.getByLabel("Actual end", { exact: true }).fill("2026-01-06T10:00");
  await page.keyboard.press("Escape");
  await hidden(dialog);
  assert.equal(await trigger.evaluate((element) => element === document.activeElement), true);
  await trigger.click();
  assert.equal(await dialog.getByLabel("Actual start", { exact: true }).inputValue(), "2026-01-06T09:00");
  assert.equal(await dialog.getByLabel("Actual end", { exact: true }).inputValue(), "2026-01-06T10:00");
});

let finishEncounter;
const encounterPending = new Promise((resolve) => { finishEncounter = resolve; });
await check("encounter-save-dismissal", ePath, { overrides: {
  "POST /api/v1/counseling/encounters": async ({ reply }) => { await encounterPending; await reply({ error: { code: "test_uncertain", message: "Synthetic uncertain result" } }, 500); },
} }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Record encounter", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Record encounter", exact: true });
  await dialog.getByLabel("Actual start", { exact: true }).fill("2026-01-06T09:00");
  await dialog.getByLabel("Actual end", { exact: true }).fill("2026-01-06T10:00");
  await dialog.getByRole("button", { name: "Record counseling encounter", exact: true }).click();
  await shown(dialog.getByRole("button", { name: "Recording…", exact: true }));
  await page.keyboard.press("Escape");
  await shown(dialog);
  await hidden(dialog.getByRole("button", { name: "Close dialog", exact: true }));
  assert.equal(await dialog.getByRole("button", { name: "Recording…", exact: true }).isDisabled(), true);
  finishEncounter();
  await shown(dialog.getByText(/Check your encounters before trying again/));
  await page.keyboard.press("Escape");
  await shown(dialog);
  await shown(dialog.getByRole("link", { name: "View encounters", exact: true }));
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/counseling/encounters")).length, 1);
});
finishEncounter();

const appointmentPath = `/portal/appointments/${appointmentId}`;
await check("appointment-dialogs", appointmentPath, {}, async (page) => {
  await hidden(page.getByLabel("New date", { exact: true }));
  const reschedule = page.getByRole("button", { name: "Reschedule", exact: true });
  await reschedule.click();
  const dialog = page.getByRole("dialog", { name: "Reschedule appointment", exact: true });
  await dialog.getByLabel("New date", { exact: true }).fill("2026-10-09");
  await dialog.getByLabel("Reason (optional)", { exact: true }).fill("Schedule adjustment");
  await dialog.getByRole("group", { name: "Available replacement times" }).getByRole("button").first().click();
  await shown(dialog.getByRole("heading", { name: "Review reschedule", exact: true }));
  assert.match(await dialog.innerText(), /Current time[\s\S]*New time/);
  await page.keyboard.press("Escape");
  await hidden(dialog);
  assert.equal(await reschedule.evaluate((element) => element === document.activeElement), true);
  await reschedule.click();
  assert.equal(await dialog.getByLabel("Reason (optional)", { exact: true }).inputValue(), "Schedule adjustment");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Reassign", exact: true }).click();
  const reassign = page.getByRole("dialog", { name: "Reassign counselor", exact: true });
  await reassign.getByLabel("New counselor", { exact: true }).selectOption("other-counselor");
  await reassign.getByLabel("Reason", { exact: true }).fill("Coverage adjustment");
  await shown(reassign.getByRole("heading", { name: "Review reassignment", exact: true }));
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Reassign", exact: true }).click();
  assert.equal(await reassign.getByLabel("Reason", { exact: true }).inputValue(), "Coverage adjustment");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "More actions", exact: true }).click();
  await page.getByRole("menuitem", { name: "Cancel appointment", exact: true }).click();
  await shown(page.getByRole("alertdialog", { name: `Cancel Appointment ${appointment.reference_code}?`, exact: true }));
  await page.getByRole("alertdialog").getByRole("button", { name: "Keep appointment", exact: true }).click();
  await screenshot(page, "appointment-detail");
});

await check("counseling-workspace", `/portal/counseling/workspace/appointment/${appointmentId}`, {}, async (page) => {
  await shown(page.getByRole("heading", { name: "Counseling workspace", exact: true }));
  await shown(page.getByRole("button", { name: "Record encounter", exact: true }));
  await page.getByRole("button", { name: "Help: About Counseling", exact: true }).click();
  await shown(page.getByRole("dialog", { name: "About Counseling", exact: true }));
  await page.keyboard.press("Escape");
  await screenshot(page, "counseling-workspace");
});

let finishReassignment;
const reassignmentPending = new Promise((resolve) => { finishReassignment = resolve; });
await check("reassignment-save-dismissal", appointmentPath, { overrides: {
  [`POST /api/v1/appointments/${appointmentId}/reassign`]: async ({ reply }) => { await reassignmentPending; await reply({ error: { code: "synthetic_failure", message: "Synthetic reassignment failure" } }, 500); },
} }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Reassign", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Reassign counselor", exact: true });
  await dialog.getByLabel("New counselor", { exact: true }).selectOption("other-counselor");
  await dialog.getByLabel("Reason", { exact: true }).fill("Coverage adjustment");
  await dialog.getByRole("button", { name: "Reassign counselor", exact: true }).click();
  await shown(dialog.getByRole("button", { name: "Reassigning…", exact: true }));
  await page.keyboard.press("Escape");
  await shown(dialog);
  assert.equal(await dialog.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
  assert.equal(await dialog.getByLabel("Reason", { exact: true }).isDisabled(), true);
  finishReassignment();
  await shown(dialog.getByRole("alert"));
  assert.equal(await dialog.getByLabel("Reason", { exact: true }).inputValue(), "Coverage adjustment");
  assert.equal(requests.filter((request) => request.method === "POST" && request.pathname.endsWith("/reassign")).length, 1);
});
finishReassignment();

await check("service-editor-help", `/portal/services/${serviceId}/edit`, {}, async (page) => {
  await shown(page.getByText("Online counseling on. Appointment booking is available.", { exact: true }));
  const online = page.getByLabel("Online counseling", { exact: true });
  await online.uncheck();
  await shown(page.getByText(/Existing Appointments keep their saved mode/));
  await page.getByRole("button", { name: "Help: About Service configuration", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About Service configuration", exact: true });
  assert.match(await dialog.innerText(), /existing Appointments keep their saved settings/);
  assert.match(await dialog.innerText(), /separate video-service settings/);
  await page.keyboard.press("Escape");
  await screenshot(page, "service-editor");
});

await check("service-detail-help", `/portal/services/${serviceId}`, {}, async (page) => {
  await shown(page.getByRole("link", { name: "Edit", exact: true }));
  await shown(page.getByText("Available for scheduling", { exact: true }));
  await shown(page.getByRole("button", { name: "Help: About Service configuration", exact: true }));
  await screenshot(page, "service-detail");
});

await check("responsibilities-help", "/portal/organization/responsibilities", {}, async (page) => {
  await page.getByRole("button", { name: "Help: About Responsibilities", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About Responsibilities", exact: true });
  assert.match(await dialog.innerText(), /exactly one active Head Guidance Counselor/);
  assert.match(await dialog.innerText(), /does not automatically grant blanket access/);
  assert.match(await dialog.innerText(), /Guidance Services Staff inherit/);
  await page.keyboard.press("Escape");
  await screenshot(page, "organization-responsibilities");
});

await check("institutional-forms-warning-help", "/portal/institutional-forms", {}, async (page) => {
  await shown(page.getByRole("alert").filter({ hasText: "A current supported revision is required" }));
  await page.getByRole("button", { name: "Help: About Institutional Forms", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About Institutional Forms", exact: true });
  assert.match(await dialog.innerText(), /does not grant institutional approval/);
  assert.match(await dialog.innerText(), /CNSC\/GTA/);
  await page.keyboard.press("Escape");
  await screenshot(page, "institutional-forms");
});

await check("student-call-slip-instruction", `/portal/call-slips/${slip.id}`, { role: "STUDENT" }, async (page) => {
  await shown(page.getByText(/Show this Call Slip to your instructor and report to Guidance Office/));
  await shown(page.getByRole("button", { name: "Download Call Slip", exact: true }));
  await screenshot(page, "call-slip-student");
});

await check("icon-tooltip-interaction", `/portal/call-slips/${slip.id}`, {}, async (page) => {
  await page.getByLabel("Interview ended", { exact: true }).fill("2026-01-06T10:00");
  await page.getByRole("button", { name: "Review interview end", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Record interview end?", exact: true });
  assert.match(await dialog.innerText(), /cannot be changed once saved/);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await hidden(dialog);
  const review = page.getByRole("button", { name: "Review interview end", exact: true });
  await page.waitForFunction((element) => element === document.activeElement, await review.elementHandle());
  const download = page.getByRole("button", { name: "Download Call Slip", exact: true });
  await shown(download);
  assert.equal(await download.locator("span").isVisible(), false, "Desktop action has an independent accessible name");
  await download.focus();
  await shown(page.getByRole("tooltip", { name: "Download Call Slip", exact: true }));
  await page.keyboard.press("Escape");
  await hidden(page.getByRole("tooltip"));
  await page.getByRole("heading", { name: "Call Slip / Interview Permit", exact: true }).click();
  await download.hover();
  await shown(page.getByRole("tooltip", { name: "Download Call Slip", exact: true }));
  await screenshot(page, "call-slip-detail");
});

await check("platform-help", "/portal/platform/health", {}, async (page) => {
  await shown(page.getByRole("heading", { name: "Diagnostic checks", exact: true }));
  await shown(page.getByRole("button", { name: "Check worker", exact: true }));
  await page.getByRole("button", { name: "Help: About Platform diagnostics", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About Platform diagnostics", exact: true });
  assert.match(await dialog.innerText(), /does not establish worker, scheduler, Daily.co, or Turnstile/);
  await page.keyboard.press("Escape");
  await screenshot(page, "platform-health");
});

await check("adr090-sortable-header", "/portal/appointments/manage", {}, async (page, { requests }) => {
  await shown(page.getByLabel("Sort", { exact: true }));
  await page.getByLabel("Sort", { exact: true }).selectOption("LATEST_START");
  await page.waitForURL(/ordering=LATEST_START/);
  await shown(page.locator('th[aria-sort="descending"]'));
  await page.getByRole("button", { name: /Date and time.*Sort earliest start first/ }).click();
  await page.waitForURL(/ordering=EARLIEST_START/);
  await shown(page.locator('th[aria-sort="ascending"]'));
  assert.ok(requests.some((request) => request.pathname === "/api/v1/appointments" && request.search.includes("ordering=LATEST_START")));
});

await check("mobile-help-actions", ePath, { mobile: true, role: "STUDENT", decision: "PENDING" }, async (page) => {
  const help = page.getByRole("button", { name: "Help: About E-Counseling", exact: true });
  await shown(help);
  assert.ok((await help.boundingBox()).height >= 44);
  await help.tap();
  const dialog = page.getByRole("dialog", { name: "About E-Counseling", exact: true });
  await shown(dialog);
  await dialog.getByRole("heading", { name: "Encounter records", exact: true }).scrollIntoViewIfNeeded();
  await dialog.getByRole("button", { name: "Close Help", exact: true }).tap();
  await hidden(dialog);
  await shown(page.getByRole("button", { name: /^Allow / }).first());
  await noHorizontalOverflow(page);
  await screenshot(page, "mobile-e-counseling-student");
});

await check("mobile-sort-and-dialog", "/portal/appointments/manage", { mobile: true }, async (page) => {
  await page.getByLabel("Sort", { exact: true }).selectOption("LATEST_START");
  await page.waitForURL(/ordering=LATEST_START/);
  await noHorizontalOverflow(page);
  await page.goto(`${baseURL}${appointmentPath}`);
  await page.getByRole("button", { name: "Reschedule", exact: true }).tap();
  const dialog = page.getByRole("dialog", { name: "Reschedule appointment", exact: true });
  await dialog.getByLabel("New date", { exact: true }).fill("2026-10-09");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).tap();
  await hidden(dialog);
  await noHorizontalOverflow(page);
});

await check("tablet-help-layout", ePath, { tablet: true, role: "STUDENT", decision: "PENDING" }, async (page) => {
  await page.getByRole("button", { name: "Help: About E-Counseling", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About E-Counseling", exact: true });
  await shown(dialog.getByRole("heading", { name: "Transcript storage", exact: true }));
  await noHorizontalOverflow(page);
  await page.keyboard.press("Escape");
  await hidden(dialog);
  await shown(page.getByRole("button", { name: "Allow audio/video recording", exact: true }));
  await noHorizontalOverflow(page);
});

await check("mobile-icon-action-label", `/portal/call-slips/${slip.id}`, { mobile: true, role: "STUDENT" }, async (page) => {
  const download = page.getByRole("button", { name: "Download Call Slip", exact: true });
  await shown(download);
  assert.equal(await download.locator("span").isVisible(), true, "Touch control has a visible name without hover");
  const box = await download.boundingBox();
  assert.ok(box.height >= 44 && box.width >= 44);
  await noHorizontalOverflow(page);
});

const v2Workspace = (state = "NOT_STARTED", artifact = null) => {
  const data = workspace(state);
  data.media.media_policy_version = 2;
  for (const value of [data.media.recording, data.media.transcription]) {
    value.artifact_status = artifact;
    value.artifact_available = artifact === "STORED";
  }
  return data;
};
const v2Consents = (decision = "PENDING") => ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"].map((scope, index) => ({ ...consents(decision)[0], id: `v2-consent-${index}`, scope }));
const v2Overrides = (data, decision = "PENDING", student = false) => ({
  [`/api/v1/e-counseling/${student ? "me/" : ""}appointments/${appointmentId}`]: data,
  [`/api/v1/e-counseling/${student ? "me/" : ""}appointments/${appointmentId}/consents`]: { items: v2Consents(decision) },
});

await check("v2-student-consent-mobile", ePath, { mobile: true, role: "STUDENT", overrides: v2Overrides(v2Workspace(), "PENDING", true) }, async (page) => {
  await shown(page.getByRole("heading", { name: "Recording & live transcription", exact: true }));
  assert.equal(await page.getByRole("button", { name: /^Allow / }).count(), 2);
  await hidden(page.getByRole("button", { name: "Allow audio/video recording", exact: true }));
  assert.match(await page.locator("main").innerText(), /Approval alone does not start/);
  assert.match(await page.locator("main").innerText(), /does not affect your ability to receive Counseling/);
  await page.getByRole("button", { name: "Allow recording & live transcription", exact: true }).click();
  await shown(page.getByRole("alertdialog"));
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel", exact: true }).click();
  await noHorizontalOverflow(page);
  await screenshot(page, "v2-student-mobile");
});

await check("v2-counselor-preparation", ePath, { overrides: v2Overrides(v2Workspace("READY", "PROCESSING"), "APPROVED") }, async (page) => {
  await shown(page.getByText("Preparing recording…", { exact: true }));
  await shown(page.getByText("Preparing transcript…", { exact: true }));
  await hidden(page.getByRole("button", { name: "Download recording", exact: true }));
  await page.getByRole("button", { name: "Help: About E-Counseling", exact: true }).click();
  await shown(page.getByRole("dialog").getByRole("heading", { name: "Private files", exact: true }));
});

let signedRequests = 0;
await check("v2-fresh-download-per-click", ePath, { overrides: {
  ...v2Overrides(v2Workspace("READY", "STORED"), "APPROVED"),
  [`/api/v1/e-counseling/appointments/${appointmentId}/media/RECORDING/access`]: ({ reply }) => reply({ url: `${baseURL}/synthetic-media-download?token=${++signedRequests}`, expires_at: "2099-10-08T00:00:00Z" }),
} }, async (page, { context }) => {
  await context.route("**/synthetic-media-download?*", (route) => route.fulfill({ status: 200, contentType: "video/mp4", headers: { "Content-Disposition": 'attachment; filename="synthetic.mp4"' }, body: "synthetic" }));
  const button = page.getByRole("button", { name: "Download recording", exact: true });
  await shown(button);
  for (let count = 1; count <= 2; count++) {
    const download = page.waitForEvent("download");
    await button.click();
    const result = await download;
    assert.equal(result.suggestedFilename(), "synthetic.mp4");
    await result.delete();
    await shown(button);
    assert.equal(signedRequests, count);
  }
  assert.doesNotMatch(await page.locator("main").innerText(), /token=|synthetic-media-download/);
  await screenshot(page, "v2-counselor-downloads");
});

await check("v2-download-error", ePath, { overrides: {
  ...v2Overrides(v2Workspace("READY", "STORED"), "APPROVED"),
  [`/api/v1/e-counseling/appointments/${appointmentId}/media/RECORDING/access`]: ({ reply }) => reply({ error: { code: "ecounseling_artifact_unavailable", message: "File unavailable" } }, 503),
} }, async (page) => {
  await page.getByRole("button", { name: "Download recording", exact: true }).click();
  await shown(page.getByRole("alert").filter({ hasText: "file" }));
});

const retentionAuth = {
  "/api/v1/auth/session": { user: { ...user("INSTITUTIONAL_OFFICER"), capabilities: ["privacy_governance.retention.view", "privacy_governance.retention.manage", "privacy_governance.retention.approve"] }, session: { id: "synthetic", expires_at: "2099-10-07T00:00:00Z", is_current: true } },
};
const versionedCategories = [1, 2].flatMap((contract_version) => ["ECOUNSELING_RECORDING", "ECOUNSELING_TRANSCRIPT"].map((category) => ({ category, contract_version, label: category.endsWith("RECORDING") ? "E-Counseling recordings" : "E-Counseling stored transcripts", trigger: "MEDIA_READY_AT", action: contract_version === 2 ? "DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE" : "DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE" })));
await check("v2-retention-rule-contract", "/portal/privacy/retention/rules/new", { role: "INSTITUTIONAL_OFFICER", overrides: {
  ...retentionAuth,
  "/api/v1/privacy/retention/categories": versionedCategories,
} }, async (page, { requests }) => {
  await page.getByLabel("Rule code", { exact: true }).fill("SYNTHETIC-V2");
  await page.getByLabel("Administrative label", { exact: true }).fill("Synthetic media policy");
  await page.getByLabel("Data category", { exact: true }).selectOption("ECOUNSELING_RECORDING");
  await page.getByLabel("Governance contract", { exact: true }).selectOption("2");
  await shown(page.getByText("Delete COMPASS media and remaining provider copy, keep evidence", { exact: true }));
  await page.getByLabel("Whole elapsed days", { exact: true }).fill("30");
  await page.getByLabel("Effective date", { exact: true }).fill("2026-10-08");
  await page.getByLabel("Policy / basis reference", { exact: true }).fill("Synthetic test reference");
  await page.getByRole("button", { name: "Create draft rule", exact: true }).click();
  await shown(page.getByText("The retention draft could not be saved.", { exact: true }));
  const request = requests.find((item) => item.method === "POST" && item.pathname.endsWith("/retention/rules"));
  assert.ok(request);
  const payload = JSON.parse(request.body);
  assert.equal(payload.contract_version, 2);
  assert.equal(payload.action, "DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE");
  await screenshot(page, "v2-retention-rule-contract");
});

await browser.close();
await writeFile(join(artifacts, "results.json"), `${JSON.stringify({ baseURL, results }, null, 2)}\n`);
console.log(`${results.length - failures.length}/${results.length} browser checks passed; artifacts: ${artifacts}`);
if (failures.length) process.exitCode = 1;
