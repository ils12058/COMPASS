// Actual portal UI, with synthetic accounts and HTTP responses only.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("guidance-followups");
const id = "11111111-1111-4111-8111-111111111111";
const studentId = "22222222-2222-4222-8222-222222222222";
const sourceId = "33333333-3333-4333-8333-333333333333";
function world(role = "COUNSELOR", { source = false, recoverable = false } = {}) {
  const staff = { ...user(role), capabilities: [...user(role).capabilities, "guidance_followups.view", "guidance_followups.manage"] };
  let item = { id, student_id: studentId, student_name: "Synthetic Student", assigned_to_id: staff.id,
    assigned_to_name: "Synthetic Counselor", category: source ? "COUNSELING" : "ADMINISTRATIVE",
    visibility: source ? "COUNSELOR_CONFIDENTIAL" : "OPERATIONAL", due_at: "2099-01-01T02:00:00Z",
    status: "PENDING", overdue: false, version: 1, created_at: "2026-10-17T00:00:00Z", updated_at: "2026-10-17T00:00:00Z",
    description: "Protected synthetic description", outcome: null, source: source ? { kind: "COUNSELING_ENCOUNTER", id: sourceId } : null,
    source_unavailable: false, completed_at: null, completed_by_name: null, cancelled_at: null, cancelled_by_name: null, events: [], events_has_next: false };
  let recovery = recoverable;
  let uncertainCreate = true;
  let conflictEdit = true;
  const writes = [];
  const page = items => ({ items, page: 1, page_size: 20, has_next: false });
  const handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(staff)); return true; }
    if (!pathname.startsWith("/api/v1/guidance-followups")) return false;
    if (pathname.endsWith("/eligible-students")) { await reply(page([{ id: studentId, display_name: "Synthetic Student", institutional_id: "TEST-2026" }])); return true; }
    if (pathname.endsWith("/eligible-assignees")) { await reply(page([{ id: staff.id, display_name: "Synthetic Counselor" }])); return true; }
    if (pathname.endsWith("/context")) { await reply({ source_kind: "COUNSELING_ENCOUNTER", source_id: sourceId, student_id: studentId, student_name: "Synthetic Student", category: "COUNSELING", visibility: "COUNSELOR_CONFIDENTIAL", can_create: true }); return true; }
    if (pathname.endsWith("/recoverable")) { await reply({ ...page(recovery ? [{ ...item, assigned_to_id: "inactive-staff", assigned_to_name: "Inactive Staff" }] : []), ordering: "EARLIEST_DUE" }); return true; }
    if (pathname.endsWith("/report")) { await reply({ pending: 1, completed: 0, cancelled: 0, overdue: 0, due_soon: 0, completed_in_period: 0, period_start: "2026-09-17T00:00:00Z", period_end: "2026-10-17T00:00:00Z", generated_at: "2026-10-17T00:00:00Z", horizon_days: 7, categories: [{ category: "ADMINISTRATIVE", count: 1 }] }); return true; }
    if (method === "GET") { await reply(pathname === "/api/v1/guidance-followups" ? { ...page([item]), ordering: "EARLIEST_DUE" } : item); return true; }
    const body = JSON.parse(request.postData() ?? "{}");
    writes.push({ pathname, method, body, key: request.headers()["idempotency-key"] });
    if (pathname === "/api/v1/guidance-followups") {
      item = { ...item, ...body, id, student_name: "Synthetic Student", assigned_to_name: "Synthetic Counselor" };
      if (uncertainCreate) { uncertainCreate = false; await reply({ error: { code: "unavailable", message: "Synthetic uncertain response" } }, 503); }
      else await reply(item, 201);
      return true;
    }
    if (method === "PATCH" && conflictEdit) { conflictEdit = false; item = { ...item, version: item.version + 1 }; await reply({ error: { code: "followup_conflict", message: "Changed" } }, 409); return true; }
    item = { ...item, version: item.version + 1 };
    if (method === "PATCH") item = { ...item, ...body };
    if (pathname.endsWith("/activities")) item.events.push({ id: sourceId, kind: "ACTIVITY_RECORDED", revision: item.version, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: item.created_at, old_assignee_id: null, new_assignee_id: null, old_due_at: null, new_due_at: null, remarks: body.remarks });
    if (pathname.endsWith("/complete")) item = { ...item, status: "COMPLETED", outcome: body.outcome, completed_at: item.created_at, completed_by_name: "Synthetic Counselor" };
    if (pathname.endsWith("/reassign")) recovery = false;
    await reply(item); return true;
  };
  return { handler, writes };
}
for (const mobile of [false, true]) {
  const fixture = world();
  await check(`Create freezes an unconfirmed submission and retries one key ${mobile ? "phone" : "desktop"}`, "/portal/follow-ups/new", { handler: fixture.handler, mobile }, async page => {
    await page.getByLabel("Student", { exact: true }).selectOption(studentId);
    await page.getByLabel("Responsible staff member", { exact: true }).selectOption(user("COUNSELOR").id);
    await page.getByLabel("Due date and time (Philippine Time)", { exact: true }).fill("2099-01-01T10:00");
    await page.getByLabel("Follow-up description (optional)", { exact: true }).fill("Synthetic follow-up content");
    await page.getByRole("button", { name: "Create follow-up", exact: true }).click();
    await shown(page.locator("form").getByRole("alert"));
    assert.equal(await page.getByLabel("Follow-up description (optional)", { exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "Retry the same follow-up", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Guidance follow-up", exact: true }));
    assert.equal(fixture.writes.length, 2); assert.deepEqual(fixture.writes[0], fixture.writes[1]); assert.ok(fixture.writes[0].key);
    await noHorizontalOverflow(page); await screenshot(page, mobile ? "detail-phone" : "detail-desktop");
  });
}
{
  const fixture = world();
  await check("Edit conflict preserves input and requires deliberate review, then completes independently", `/portal/follow-ups/${id}`, { handler: fixture.handler }, async page => {
    await page.getByRole("button", { name: "Edit follow-up", exact: true }).click();
    await page.getByRole("textbox", { name: "Description", exact: true }).fill("Retained synthetic edit");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await shown(page.getByRole("button", { name: "I reviewed the latest details", exact: true }));
    assert.equal(await page.getByRole("textbox", { name: "Description", exact: true }).inputValue(), "Retained synthetic edit");
    assert.equal(await page.getByRole("button", { name: "Save changes", exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "I reviewed the latest details", exact: true }).click();
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await shown(page.getByRole("button", { name: "Complete follow-up", exact: true }));
    await page.getByRole("button", { name: "Complete follow-up", exact: true }).click();
    await page.getByLabel("Completion outcome", { exact: true }).fill("Synthetic completion outcome");
    await page.getByRole("button", { name: "Review complete follow-up", exact: true }).click();
    const dialog = page.getByRole("alertdialog"); await shown(dialog);
    assert.equal(fixture.writes.length, 2);
    await dialog.getByRole("button", { name: "Complete follow-up", exact: true }).click();
    await shown(page.getByText("Synthetic completion outcome", { exact: true }));
    assert.equal(fixture.writes.length, 3); assert.ok(fixture.writes.every(row => row.key)); await noHorizontalOverflow(page);
  });
}
{
  const fixture = world("COUNSELOR", { source: true });
  await check("Counseling context uses only its canonical Encounter and locks classification", `/portal/follow-ups/new?source_kind=COUNSELING_ENCOUNTER&source_id=${sourceId}`, { handler: fixture.handler }, async (page, { requests }) => {
    await shown(page.getByText(/Counselor-confidential/));
    assert.equal(await page.getByLabel("Category", { exact: true }).isDisabled(), true);
    assert.equal(requests.some(row => row.pathname.endsWith("/eligible-students")), false);
    await noHorizontalOverflow(page);
  });
}
{
  const fixture = world("GUIDANCE_SERVICES_STAFF", { recoverable: true });
  await check("Operational recovery exposes only the summary and explicit reassignment", "/portal/follow-ups/reassignment", { handler: fixture.handler, mobile: true }, async page => {
    await page.getByRole("button", { name: "Reassign Synthetic Student", exact: true }).click();
    await page.getByLabel("Responsible staff member", { exact: true }).selectOption(user("GUIDANCE_SERVICES_STAFF").id);
    await page.getByRole("button", { name: "Reassign follow-up", exact: true }).click();
    await shown(page.getByText("No operational follow-ups need reassignment in your current scope.", { exact: true }));
    assert.equal(fixture.writes.length, 1); await hidden(page.getByText("Protected synthetic description", { exact: true }));
    await noHorizontalOverflow(page);
  });
}
for (const role of ["STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  const fixture = world(role);
  await check(`${role} has no Follow-Up workspace even with capability strings`, `/portal/follow-ups/${id}`, { handler: fixture.handler }, async (page, { requests }) => {
    await shown(page.getByText("Your account does not have access to Guidance Follow-Ups.", { exact: false }));
    assert.equal(requests.some(row => row.pathname.startsWith("/api/v1/guidance-followups")), false);
  });
}
await finish();
