// Run against a local Next server. Every API read/write uses synthetic fixtures; no account,
// Daily room, credential, recording, notification or institutional record is touched.
// E-Counseling sessions have their own suite: ecounseling-call.browser.mjs.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointmentId, serviceId, appointment, user, slip } from "./support/ui-hierarchy-fixtures.mjs";

const { baseURL, check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("ui-information-hierarchy");

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
  await shown(page.getByRole("link", { name: "Edit Service", exact: true }));
  await shown(page.getByText("Available for scheduling", { exact: true }));
  await shown(page.getByRole("button", { name: "Help: About Service configuration", exact: true }));
  await screenshot(page, "service-detail");
});

await check("responsibilities-help", "/portal/organization/responsibilities", {}, async (page) => {
  await page.getByRole("button", { name: "Help: About Responsibilities", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "About Responsibilities", exact: true });
  assert.match(await dialog.innerText(), /exactly one active Head Guidance Counselor/);
  assert.match(await dialog.innerText(), /does not automatically grant blanket access/);
  assert.match(await dialog.innerText(), /Guidance Services Staff handle/);
  assert.match(await dialog.innerText(), /Staff do not inherit Head oversight authority/);
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

await check("page-action-label-and-confirmation-focus", `/portal/call-slips/${slip.id}`, {}, async (page) => {
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
  await shown(download.locator("[data-page-action-label]"));
  assert.equal(await download.locator("[data-page-action-label]").innerText(), "Download Call Slip", "Desktop command keeps its visible name");
  await download.focus();
  assert.equal(await download.evaluate((element) => element === document.activeElement), true);
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

await check("mobile-icon-action-label", `/portal/call-slips/${slip.id}`, { mobile: true, role: "STUDENT" }, async (page) => {
  const download = page.getByRole("button", { name: "Download Call Slip", exact: true });
  await shown(download);
  assert.equal(await download.locator("[data-page-action-label]").isVisible(), true, "Touch control has a visible name without hover");
  const box = await download.boundingBox();
  assert.ok(box.height >= 44 && box.width >= 44);
  await noHorizontalOverflow(page);
});

const retentionAuth = {
  "/api/v1/auth/session": { user: { ...user("INSTITUTIONAL_OFFICER"), designations: ["DPO"], capabilities: ["privacy_governance.view", "privacy_governance.manage", "privacy_governance.activity.export", "privacy_governance.retention.view"] }, session: { id: "synthetic", expires_at: "2099-10-07T00:00:00Z", is_current: true } },
  "/api/v1/privacy/retention/policies": { items: [
    ["GRADUATE_TRACER", "Graduate Tracer responses"],
    ["ECOUNSELING_RECORDING", "E-Counseling recordings"],
    ["ECOUNSELING_TRANSCRIPT", "E-Counseling transcripts"],
  ].map(([category_code, category_label]) => ({ category_code, category_label, adoption_status: "NOT_ADOPTED", retention_period: null, policy_reference: null, effective_date: null })) },
};
for (const device of ["desktop", "phone"]) {
  await check(`retention-policies-read-only-${device}`, "/portal/privacy/retention", { role: "INSTITUTIONAL_OFFICER", device, overrides: retentionAuth }, async (page, { requests }) => {
    await shown(page.getByRole("heading", { level: 1, name: "Retention Policies", exact: true }));
    await shown(page.getByRole("link", { name: "Retention Policies", exact: true }));
    for (const name of ["Graduate Tracer responses", "E-Counseling recordings", "E-Counseling transcripts"]) await shown(page.getByRole("heading", { name, exact: true }));
    assert.equal(await page.getByText("Not adopted", { exact: true }).count(), 3);
    assert.equal(await page.getByText("No adopted retention policy has been recorded in COMPASS for this category.", { exact: true }).count(), 3);
    const main = await page.locator("main").innerText();
    assert.doesNotMatch(main, /Retention & Disposition|Create|Edit|Activate|Approve|Retry|Place hold|Release hold|Disposition cases|Needs review|0 days|N\/A/);
    const buttons = await page.locator("main").getByRole("button").allInnerTexts();
    assert.deepEqual(buttons.map((text) => text.trim()), ["Help"]);
    await page.getByRole("button", { name: "Help: About Retention Policies", exact: true }).click();
    const help = page.getByRole("dialog", { name: "About Retention Policies", exact: true });
    assert.match(await help.innerText(), /version-controlled COMPASS code[\s\S]*can’t be created or edited in COMPASS[\s\S]*outside COMPASS/);
    await page.keyboard.press("Escape");
    await hidden(help);
    const privacy = requests.filter((item) => item.pathname.startsWith("/api/v1/privacy/"));
    assert.ok(privacy.length > 0 && privacy.every((item) => item.method === "GET"), "the oversight page never mutates");
    assert.ok(!requests.some((item) => /\/retention\/(rules|cases|summary|categories)/.test(item.pathname)));
    await noHorizontalOverflow(page);
    await screenshot(page, `retention-policies-${device}`);
  });
}
for (const legacy of ["/portal/privacy/retention/rules", "/portal/privacy/retention/rules/new", "/portal/privacy/retention/cases/dd93953c-e82b-4d07-b3cf-79b204cdb0f3"]) {
  await check(`retention-legacy-bookmark-${legacy.split("/").slice(4).join("-")}`, legacy, { role: "INSTITUTIONAL_OFFICER", overrides: retentionAuth }, async (page) => {
    await page.waitForURL((url) => url.pathname === "/portal/privacy/retention");
    await shown(page.getByRole("heading", { level: 1, name: "Retention Policies", exact: true }));
    await hidden(page.getByRole("button", { name: /Create draft rule|Approve disposition|Place hold/ }));
  });
}

await finish();
