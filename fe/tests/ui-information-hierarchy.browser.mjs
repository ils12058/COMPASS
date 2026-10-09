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
  assert.equal(await download.locator("span").isVisible(), true, "Touch control has a visible name without hover");
  const box = await download.boundingBox();
  assert.ok(box.height >= 44 && box.width >= 44);
  await noHorizontalOverflow(page);
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

await finish();
