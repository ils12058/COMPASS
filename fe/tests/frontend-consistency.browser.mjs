// Synthetic APIs only; these checks exercise actual portal routes and CSS in both browser engines.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { worlds, empty } from "./support/ux-hardening-fixtures.mjs";
import { user, slip, serviceId } from "./support/ui-hierarchy-fixtures.mjs";
import { assessmentWorld, recordId } from "./support/assessment-records-fixtures.mjs";
import { operationsAccount, operationsData } from "./support/guidance-operations-fixtures.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness(`frontend-consistency-${engine}`);
const session = (account) => ({ user: account, session: { id: "consistency", expires_at: "2099-01-01T00:00:00Z", is_current: true } });
const staff = { ...user(), capabilities: [...user().capabilities, "referrals.view", "referrals.manage", "routine_interviews.view_assigned", "routine_interviews.manage_assigned", "graduate_tracer.view", "announcements.manage"] };
const graduate = { ...user("STUDENT"), student_lifecycle_status: "GRADUATED", capabilities: ["graduate_tracer.view_self"] };
const tracer = { id: "tracer", status: "SUBMITTED", name: "Synthetic Graduate", student: slip.student, submitted_at: "2026-10-08T00:00:00Z", educational_attainments: [], professional_exams: [], trainings: [] };
const overrides = {
  ...worlds, "/api/v1/auth/session": session(staff),
  "/api/v1/call-slips": { ...empty, filter_options: { form_revisions: [] } },
  "/api/v1/referrals": { ...empty, filter_options: { form_revisions: [] } }, "/api/v1/routine-interviews": { ...empty, filter_options: { form_revisions: [] } },
  "/api/v1/graduate-tracer/responses/tracer": tracer,
};
async function commands(page, labels) {
  const header = page.locator("[data-page-header]").first(); await shown(header);
  for (const label of labels) {
    const command = header.getByRole("button", { name: label, exact: true }).or(header.getByRole("link", { name: label, exact: true }));
    await shown(command);
    const text = command.locator("[data-page-action-label]"); await shown(text);
    assert.ok((await text.innerText()).trim().length > 0);
    assert.ok(await command.evaluate((el) => { const label = el.querySelector("[data-page-action-label]"); const surface = el.querySelector("[data-page-action-surface]"); const l = label.getBoundingClientRect(); const s = surface.getBoundingClientRect(); return l.top >= s.bottom - 1 && getComputedStyle(label).visibility === "visible"; }), "Visible label sits beneath its icon surface");
    await command.focus();
    assert.equal(await command.evaluate((el) => el === document.activeElement), true);
    assert.ok(await command.evaluate((el) => getComputedStyle(el).boxShadow !== "none"), "Keyboard focus has a visible ring");
  }
  // Every rendered command in an ordinary action slot uses the same labeled surface.
  const actionRegion = header.locator("[data-page-header-actions]");
  for (const command of await actionRegion.locator("button, a").all()) assert.equal(await command.locator("[data-page-action-label]").count(), 1);
  await noHorizontalOverflow(page);
}
for (const width of [320, 393, 1440]) {
  const viewport = { width, height: 1000 };
  const cases = [
    ["call-list", "/portal/call-slips", ["Issue Call Slip"]],
    ["call-detail", `/portal/call-slips/${slip.id}`, ["Download Call Slip"]],
    ["referral-list", "/portal/referrals", ["Record referral"]],
    ["referral-detail", "/portal/referrals/long", ["Download Referral Slip"]],
    ["service-list", "/portal/services", ["Create Service"]],
    ["service-detail", `/portal/services/${serviceId}`, ["Edit Service"]],
    ["routine-workspace", "/portal/routine-interviews", ["Start Routine Interview"]],
    ["graduate-detail", "/portal/graduate-tracer/responses/tracer", []],
    ["announcement-detail", "/portal/announcements/long", ["Edit Announcement", "Publish Announcement", "Archive Announcement"]],
  ];
  for (const [name, route, labels] of cases) await check(`${name}-${width}`, route, { viewport, overrides }, async (page) => {
    await shown(page.getByRole("heading", { level: 1 }));
    if (name === "graduate-detail") {
      await shown(page.getByRole("heading", { level: 1, name: tracer.name }));
      assert.equal(await page.locator("[data-page-header-actions]").count(), 0);
      assert.match(await page.locator("[data-page-header]").innerText(), /Submitted/);
      await shown(page.getByRole("link", { name: "Back to Graduate Tracer queue", exact: true }));
    }
    await commands(page, labels);
    if (name.endsWith("list") && name !== "service-list") await shown(page.getByRole("heading", { level: 2, name: "Results", exact: true }));
    if (name === "announcement-detail") {
      await page.getByRole("button", { name: "Publish Announcement", exact: true }).click();
      const dialog = page.getByRole("alertdialog"); await shown(dialog);
      assert.match(await dialog.innerText(), /visible to/); await noHorizontalOverflow(page);
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click(); await hidden(dialog);
    }
    if (width === 393 && ["call-detail", "referral-detail", "service-detail", "graduate-detail", "announcement-detail"].includes(name)) await screenshot(page, `${name}-${width}`);
  });
  const assessment = assessmentWorld();
  for (const [name, route, labels] of [["assessment-list", "/portal/assessment-records", ["Record result assessment", "Manage types assessment"]], ["assessment-detail", `/portal/assessment-records/${recordId}`, ["Edit record assessment"]]]) {
    await check(`${name}-${width}`, route, assessment.options({ viewport }), async (page) => {
      await shown(page.locator("table").or(page.getByText("CONFIDENTIAL-SCORE-88/100", { exact: true })));
      await commands(page, labels);
      if (name === "assessment-list") await shown(page.getByRole("heading", { level: 2, name: "Results", exact: true }));
      if (width === 393) await screenshot(page, `${name}-${width}`);
    });
  }
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) await check(`operations-${role}-${width}`, "/portal/operations", { viewport, overrides: { "/api/v1/auth/session": session(operationsAccount(role)), "/api/v1/guidance-operations": operationsData(role) } }, async (page) => {
    await shown(page.getByRole("heading", { level: 1, name: "Guidance Operations" }));
    await shown(page.getByText("Active Call Slips", { exact: true })); await noHorizontalOverflow(page);
  });
}
await check("student-tracer-metadata", "/portal/graduate-tracer", { mobile: true, overrides: { "/api/v1/auth/session": session(graduate), "/api/v1/graduate-tracer/me": tracer } }, async (page) => {
  await shown(page.getByRole("heading", { level: 1, name: "Graduate Tracer Survey" }));
  await shown(page.locator("[data-page-header]").getByText("Submitted", { exact: true }));
  assert.equal(await page.locator("[data-page-header-actions]").count(), 0); await noHorizontalOverflow(page);
});
for (const role of ["COUNSELOR", "STUDENT"]) {
  let release; let started; let failDownload = false;
  const gate = new Promise((resolve) => { release = resolve; });
  const issued = new Promise((resolve) => { started = resolve; });
  await check(`call-download-pending-failure-retry-${role}`, `/portal/call-slips/${slip.id}`, { role, mobile: role === "STUDENT", handler: async ({ pathname, route }) => {
    if (!pathname.endsWith("/pdf")) return false;
    const expected = role === "STUDENT" ? `/api/v1/call-slips/me/${slip.id}/pdf` : `/api/v1/call-slips/${slip.id}/pdf`;
    assert.equal(pathname, expected); started(); await gate;
    await route.fulfill(failDownload ? { status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "synthetic_failure" } }) } : { status: 200, contentType: "application/pdf", headers: { "content-disposition": 'attachment; filename="Synthetic-Call-Slip.pdf"' }, body: "%PDF-1.4\nsynthetic test" }); return true;
  } }, async (page) => {
    const button = page.getByRole("button", { name: "Download Call Slip", exact: true }); await shown(button);
    await button.click(); await issued;
    await shown(page.getByRole("button", { name: "Preparing Call Slip…", exact: true })); assert.equal(await page.getByRole("button", { name: "Preparing Call Slip…", exact: true }).isDisabled(), true);
    const download = page.waitForEvent("download"); release(); assert.equal((await download).suggestedFilename(), "Synthetic-Call-Slip.pdf");
    await shown(button); failDownload = true; await button.click(); await shown(page.getByRole("alert").filter({ hasText: /could not be released/ }));
    assert.equal(await button.isEnabled(), true); await noHorizontalOverflow(page);
  });
  release();
}
for (const width of [320, 1440]) await check(`privacy-notice-actions-${width}`, "/portal/privacy/notices/notice", { viewport: { width, height: 1000 }, overrides: {
  "/api/v1/auth/session": session({ ...user("INSTITUTIONAL_OFFICER"), capabilities: ["privacy_governance.view", "privacy_governance.manage"] }),
  "/api/v1/privacy/notices/notice": { id: "notice", name: "Synthetic Privacy Notice", code: "NOTICE", is_active: true, updated_at: "2026-10-08T00:00:00Z", current_revision: null, draft_revision: null },
  "/api/v1/privacy/notices/notice/revisions": empty,
} }, async (page) => {
  await shown(page.getByRole("heading", { name: "Synthetic Privacy Notice", level: 1 }));
  await commands(page, ["Rename", "Retire"]);
  assert.equal(await page.getByRole("button", { name: "Retire", exact: true }).locator("[data-page-action-surface=danger]").count(), 1);
  // Keyboard activation preserves a focused opener on browsers that do not focus pointer clicks.
  await page.getByRole("button", { name: "Retire", exact: true }).press("Enter");
  const dialog = page.getByRole("alertdialog", { name: "Retire this privacy notice?" }); await shown(dialog);
  assert.match(await dialog.innerText(), /acknowledgment history will remain preserved/);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click(); await hidden(dialog);
  await page.waitForFunction((el) => el === document.activeElement, await page.getByRole("button", { name: "Retire", exact: true }).elementHandle());
  await noHorizontalOverflow(page);
});
await check("routine-shared-query-error-and-retry", "/portal/routine-interviews/routine", { overrides: { ...overrides, "/api/v1/routine-interviews/routine": ({ reply }) => reply({ error: { code: "synthetic_failure" } }, 503) } }, async (page, { requests }) => {
  const alert = page.getByRole("alert").filter({ hasText: "Routine Interview could not be loaded" }); await shown(alert);
  assert.equal(await alert.evaluate((el) => el.tagName), "DIV", "Domain query error uses the shared Notice surface");
  const count = requests.filter((r) => r.pathname === "/api/v1/routine-interviews/routine").length;
  const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/v1/routine-interviews/routine");
  await alert.getByRole("button", { name: "Retry", exact: true }).click(); await response;
  assert.ok(requests.filter((r) => r.pathname === "/api/v1/routine-interviews/routine").length > count);
  await shown(alert); await noHorizontalOverflow(page);
});
let releaseTracer;
const tracerGate = new Promise((resolve) => { releaseTracer = resolve; });
await check("tracer-shared-loading-status", "/portal/graduate-tracer/responses/tracer", { overrides: { ...overrides, "/api/v1/graduate-tracer/responses/tracer": async ({ reply }) => { await tracerGate; return reply(tracer); } } }, async (page) => {
  try {
    const status = page.getByRole("status", { name: "", exact: true }).filter({ hasText: "Loading Graduate Tracer response…" }); await shown(status);
    assert.equal(await status.locator("..").getAttribute("aria-busy"), "true");
    releaseTracer(); await shown(page.getByRole("heading", { level: 1, name: tracer.name }));
  } finally { releaseTracer(); }
});
releaseTracer();
await finish();
