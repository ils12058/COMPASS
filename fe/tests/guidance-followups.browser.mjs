// Actual portal UI, with synthetic accounts and HTTP responses only.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("guidance-followups");
const id = "11111111-1111-4111-8111-111111111111";
const studentId = "22222222-2222-4222-8222-222222222222";
const sourceId = "33333333-3333-4333-8333-333333333333";
function world(role = "COUNSELOR", { source = false, sourceKind = "COUNSELING_ENCOUNTER", recoverable = false, empty = "none" } = {}) {
  const staff = { ...user(role), capabilities: [...user(role).capabilities, "guidance_followups.view", "guidance_followups.manage"] };
  const confidential = source && sourceKind !== "REFERRAL";
  const category = source ? sourceKind === "REFERRAL" ? "REFERRAL_ACTION" : "COUNSELING" : "ADMINISTRATIVE";
  let item = { id, student_id: studentId, student_name: "Synthetic Student", assigned_to_id: staff.id,
    assigned_to_name: "Synthetic Counselor", category,
    visibility: confidential ? "COUNSELOR_CONFIDENTIAL" : "OPERATIONAL", due_at: "2026-10-20T02:00:00Z",
    status: "PENDING", overdue: false, version: 1, created_at: "2026-10-17T00:00:00Z", updated_at: "2026-10-17T00:00:00Z",
    description: "Protected synthetic description", outcome: null, source: source ? { kind: sourceKind, id: sourceId } : null,
    source_unavailable: false, completed_at: null, completed_by_name: null, cancelled_at: null, cancelled_by_name: null,
    events: [
      { id: "created-event", kind: "CREATED", revision: 1, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: "2026-10-14T00:00:00Z", old_assignee_id: null, new_assignee_id: staff.id, old_due_at: null, new_due_at: "2026-10-19T02:00:00Z", remarks: null },
      { id: "due-change-event", kind: "UPDATED", revision: 2, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: "2026-10-15T00:00:00Z", old_assignee_id: null, new_assignee_id: null, old_due_at: "2026-10-19T02:00:00Z", new_due_at: "2026-10-20T02:00:00Z", remarks: null },
    ], events_has_next: false };
  let recovery = recoverable;
  let uncertainCreate = true;
  let conflictEdit = true;
  const writes = [];
  const page = items => ({ items, page: 1, page_size: 20, has_next: false });
  const handler = async ({ pathname, method, request, reply, url }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(staff)); return true; }
    if (!pathname.startsWith("/api/v1/guidance-followups")) return false;
    if (pathname.endsWith("/eligible-students")) { await reply(page([{ id: studentId, display_name: "Synthetic Student", institutional_id: "TEST-2026" }])); return true; }
    if (pathname.endsWith("/eligible-assignees")) { await reply(page([{ id: staff.id, display_name: "Synthetic Counselor" }])); return true; }
    if (pathname.endsWith("/context")) { await reply({ source_kind: sourceKind, source_id: sourceId, student_id: studentId, student_name: "Synthetic Student", category, visibility: confidential ? "COUNSELOR_CONFIDENTIAL" : "OPERATIONAL", can_create: true }); return true; }
    if (pathname.endsWith("/recoverable")) { await reply({ ...page(recovery ? [{ ...item, assigned_to_id: "inactive-staff", assigned_to_name: "Inactive Staff" }] : []), ordering: "EARLIEST_DUE" }); return true; }
    if (pathname.endsWith("/report")) {
      const counts = empty === "no-assigned" ? { pending: 0, completed: 0, cancelled: 0, overdue: 0, due_soon: 0 }
        : empty === "no-pending" ? { pending: 0, completed: 1, cancelled: 0, overdue: 0, due_soon: 0 }
          : { pending: 3, completed: 0, cancelled: 0, overdue: 1, due_soon: 2 };
      await reply({ ...counts, completed_in_period: 0, period_start: "2026-09-17T00:00:00Z", period_end: "2026-10-17T00:00:00Z", generated_at: "2026-10-18T00:00:00Z", horizon_days: 7, categories: [{ category, count: counts.pending + counts.completed }] }); return true;
    }
    if (method === "GET") {
      if (pathname === "/api/v1/guidance-followups") {
        const requestedPage = Number(url.searchParams.get("page") ?? 1);
        const requestedStatus = url.searchParams.get("status");
        const matchesStatus = !requestedStatus || requestedStatus === item.status;
        const overdueItem = { ...item, id: "overdue-synthetic", student_id: "overdue-student", student_name: "Synthetic Overdue Student", due_at: "2026-10-17T00:00:00Z", overdue: true };
        await reply({
          ...page(matchesStatus && empty === "none" ? [item, overdueItem] : []),
          page: requestedPage,
          has_next: matchesStatus && empty === "none" && requestedPage === 1,
          ordering: url.searchParams.get("ordering") ?? "EARLIEST_DUE",
        });
      } else await reply(item);
      return true;
    }
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
    if (pathname.endsWith("/activities")) item.events.push({ id: `activity-${item.version}`, kind: "ACTIVITY_RECORDED", revision: item.version, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: "2026-10-18T01:00:00Z", old_assignee_id: null, new_assignee_id: null, old_due_at: null, new_due_at: null, remarks: body.remarks });
    if (pathname.endsWith("/complete")) { item = { ...item, status: "COMPLETED", outcome: body.outcome, completed_at: "2026-10-18T02:00:00Z", completed_by_name: "Synthetic Counselor" }; item.events.push({ id: `completed-${item.version}`, kind: "COMPLETED", revision: item.version, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: "2026-10-18T02:00:00Z", old_assignee_id: null, new_assignee_id: null, old_due_at: null, new_due_at: null, remarks: null }); }
    if (pathname.endsWith("/cancel")) { item = { ...item, status: "CANCELLED", cancelled_at: "2026-10-18T02:00:00Z", cancelled_by_name: "Synthetic Counselor" }; item.events.push({ id: `cancelled-${item.version}`, kind: "CANCELLED", revision: item.version, actor_id: staff.id, actor_name: "Synthetic Counselor", created_at: "2026-10-18T02:00:00Z", old_assignee_id: null, new_assignee_id: null, old_due_at: null, new_due_at: null, remarks: body.reason }); }
    if (pathname.endsWith("/reassign")) recovery = false;
    await reply(item); return true;
  };
  return { handler, writes };
}
{
  const fixture = world();
  await check("Follow-Up toolbar groups filters, counts defaults and active status, and preserves query behavior", "/portal/follow-ups", {
    handler: fixture.handler,
    viewport: { width: 1440, height: 1000 },
  }, async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Follow-Ups", exact: true }));
    await shown(page.getByRole("link", { name: "Synthetic Student", exact: true }));
    assert.match(await page.locator('[data-page-header=""]').textContent(), /after counseling, referrals, or other Guidance Office activities/i);
    await shown(page.getByRole("heading", { name: "Workload overview", exact: true }));
    await shown(page.getByText("Counts include only follow-ups you can currently access. Due soon means the next 7 days.", { exact: true }));
    const overview = page.locator('section[aria-labelledby="followup-workload-heading"] dl');
    assert.equal(await overview.getByText("3", { exact: true }).count(), 1, "Pending is the authorized report total");
    assert.equal(await overview.getByText("1", { exact: true }).count(), 1, "Overdue is counted separately");
    assert.equal(await overview.getByText("2", { exact: true }).count(), 1, "Due soon excludes overdue work");
    const reportRequest = requests.find(request => request.pathname.endsWith("/report"));
    assert.equal(new URLSearchParams(reportRequest?.search ?? "").get("horizon_days"), "7");
    await shown(page.locator("tbody").getByText("Due soon", { exact: true }));
    await shown(page.locator("tbody").getByText("Overdue", { exact: true }));
    await hidden(page.getByText("Protected synthetic description", { exact: true }));
    await hidden(page.getByText("Protected synthetic outcome", { exact: true }));
    await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
    const filterButton = () => page.getByRole("button", { name: "Filters", exact: true });
    const filterTrigger = () => page.locator('[data-floating-list-tools] button[aria-haspopup="dialog"]');
    const queryFor = (key, value) => page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/v1/guidance-followups" && url.searchParams.get(key) === value;
    });
    const latestQuery = () => new URLSearchParams(
      [...requests].reverse().find((request) => request.pathname === "/api/v1/guidance-followups")?.search ?? "",
    );

    assert.equal(await page.getByLabel("Status", { exact: true }).inputValue(), "PENDING");
    assert.equal(await filterButton().count(), 1, "default Pending is not counted as an active non-default filter");
    const defaultQuery = latestQuery();
    assert.equal(defaultQuery.get("status"), "PENDING");
    await screenshot(page, "followups-default-1440");

    const nextPageRequest = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/v1/guidance-followups" && url.searchParams.get("page") === "2";
    });
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await nextPageRequest;
    assert.equal(latestQuery().get("page"), "2");

    let completedRequest = queryFor("status", "COMPLETED");
    await page.getByLabel("Status", { exact: true }).selectOption("COMPLETED");
    await completedRequest;
    assert.equal(latestQuery().get("page"), "1", "changing status resets pagination");
    assert.equal(latestQuery().has("due_window"), false);
    assert.match(await page.locator("#followup-status-description").textContent(), /status filter is active/i);
    await shown(page.getByRole("button", { name: /Filters.*1 in use/ }));

    await page.getByRole("button", { name: /Filters.*1 in use/ }).click();
    const dialog = page.getByRole("dialog", { name: "Filters", exact: true });
    await shown(dialog);
    await shown(dialog.getByRole("group", { name: "Progress & timing", exact: true }));
    await shown(dialog.getByRole("group", { name: "Responsibility", exact: true }));
    await shown(dialog.getByRole("group", { name: "Display order", exact: true }));
    await shown(dialog.getByRole("button", { name: "Clear filters", exact: true }));
    await dialog.getByRole("button", { name: "Clear filters", exact: true }).click();
    assert.equal(await page.getByLabel("Status", { exact: true }).inputValue(), "PENDING");
    assert.equal(await dialog.getByLabel("Due date", { exact: true }).inputValue(), "");
    assert.equal(await dialog.getByLabel("Assignee", { exact: true }).inputValue(), "");
    assert.equal(await filterButton().count(), 1);
    assert.equal(await dialog.getByRole("button", { name: "Clear filters", exact: true }).count(), 0);
    await shown(filterButton());
    await page.getByRole("button", { name: "Show results", exact: true }).click();
    assert.equal(await filterButton().evaluate((element) => element === document.activeElement), true, "closing restores focus to Filters");
    await hidden(dialog);

    await filterButton().click();
    const openDialog = page.getByRole("dialog", { name: "Filters", exact: true });
    await shown(openDialog);
    assert.equal(await openDialog.getByLabel("Due date", { exact: true }).getAttribute("aria-describedby"), "followup-due-filter-hint");
    const upcomingRequest = queryFor("due_window", "UPCOMING");
    await openDialog.getByLabel("Due date", { exact: true }).selectOption("UPCOMING");
    await upcomingRequest;
    const assigneeRequest = queryFor("assigned_to_id", user("COUNSELOR").id);
    await openDialog.getByLabel("Assignee", { exact: true }).selectOption(user("COUNSELOR").id);
    await assigneeRequest;
    const latestOrderRequest = queryFor("ordering", "LATEST_DUE");
    await openDialog.getByLabel("Sort by", { exact: true }).selectOption("LATEST_DUE");
    await latestOrderRequest;
    assert.equal(latestQuery().get("status"), "PENDING");
    assert.equal(latestQuery().get("due_window"), "UPCOMING");
    assert.equal(latestQuery().get("assigned_to_id"), user("COUNSELOR").id);
    assert.equal(latestQuery().get("ordering"), "LATEST_DUE");
    assert.equal(latestQuery().get("page"), "1");
    await shown(page.getByRole("button", { name: /Filters.*2 in use/ }));
    await screenshot(page, "followups-filter-dialog-1440");
    await page.getByRole("button", { name: "Show results", exact: true }).click();
    await hidden(openDialog);
    assert.equal(await filterTrigger().evaluate((element) => element === document.activeElement), true, "Show results returns focus to Filters");
    await screenshot(page, "followups-applied-1440");

    completedRequest = queryFor("status", "COMPLETED");
    await page.getByLabel("Status", { exact: true }).selectOption("COMPLETED");
    await completedRequest;
    assert.equal(latestQuery().get("status"), "COMPLETED");
    assert.equal(latestQuery().has("due_window"), false, "due-window is cleared because it applies to Pending records only");
    assert.equal(latestQuery().get("assigned_to_id"), user("COUNSELOR").id, "changing status keeps the independent assignee filter");
    assert.equal(latestQuery().get("ordering"), "LATEST_DUE", "changing status keeps sort order");

    await page.getByRole("button", { name: /Filters.*2 in use/ }).click();
    const activeDialog = page.getByRole("dialog", { name: "Filters", exact: true });
    const clearRequest = queryFor("status", "PENDING");
    await activeDialog.getByRole("button", { name: "Clear filters", exact: true }).click();
    await clearRequest;
    assert.equal(latestQuery().has("due_window"), false);
    assert.equal(latestQuery().has("assigned_to_id"), false);
    assert.equal(latestQuery().get("ordering"), "LATEST_DUE", "Clear filters preserves the user's display order");
    await shown(filterButton());
    assert.equal(await activeDialog.getByRole("button", { name: "Clear filters", exact: true }).count(), 0, "sorting alone does not expose Clear filters");
    await page.getByRole("button", { name: "Show results", exact: true }).click();
    await hidden(activeDialog);
  });
}
{
  const fixture = world();
  await check("Follow-Up toolbar, filters dialog, focus and touch targets fit responsive workspaces", "/portal/follow-ups", {
    handler: fixture.handler,
  }, async (page) => {
    await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
    for (const width of [320, 375, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: width < 400 ? 844 : 1000 });
      await noHorizontalOverflow(page);
      const status = page.getByLabel("Status", { exact: true });
      const filters = page.getByRole("button", { name: "Filters", exact: true });
      await shown(status);
      await shown(filters);
      const statusBounds = await status.boundingBox();
      const toolbar = await page.locator("[data-floating-list-tools] > div").boundingBox();
      assert.ok(toolbar && toolbar.x >= 0 && toolbar.x + toolbar.width <= width + 1, `${width}px toolbar stays in the viewport`);
      if (width === 1024) {
        const workspace = await page.locator('[data-dock] > div.min-w-0.flex-1').boundingBox();
        assert.ok(workspace && workspace.width < width, "the expanded navigation dock narrows the 1024px workspace");
        assert.ok(toolbar && toolbar.x >= workspace.x && toolbar.x + toolbar.width <= workspace.x + workspace.width + 1, "the toolbar stays centered in the narrowed workspace");
      }
      assert.ok(statusBounds?.height >= 40, `${width}px Status remains a usable touch target (height ${statusBounds?.height}px)`);
      assert.ok((await filters.boundingBox())?.height >= 40, `${width}px Filters remains a usable touch target`);
      if (width === 320 || width === 375 || width === 1024 || width === 1440) {
        await screenshot(page, `followups-default-${width}`);
      }
      await filters.click();
      const dialog = page.getByRole("dialog", { name: "Filters", exact: true });
      await shown(dialog);
      const bounds = await dialog.boundingBox();
      assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= width + 1, `${width}px dialog stays within the viewport`);
      await shown(dialog.getByRole("button", { name: "Show results", exact: true }));
      await noHorizontalOverflow(page);
      if (width === 320) await screenshot(page, "followups-filter-dialog-320");
      if (width === 375) await screenshot(page, "followups-filter-dialog-375");
      if (width === 1440) {
        for (let step = 0; step < 6; step += 1) {
          await page.keyboard.press("Tab");
          assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, "Tab stays inside the modal dialog");
        }
        await dialog.getByLabel("Due date", { exact: true }).focus();
        await page.keyboard.press("Shift+Tab");
        assert.equal(await dialog.evaluate((element) => element.contains(document.activeElement)), true, "Shift+Tab stays inside the modal dialog");
        assert.equal(await dialog.getByRole("button", { name: "Close filters", exact: true }).evaluate((element) => element === document.activeElement), true, "Shift+Tab from the first control reaches the last control");
        await page.keyboard.press("Escape");
        await hidden(dialog);
        assert.equal(await filters.evaluate((element) => element === document.activeElement), true, "Escape restores focus to Filters");
      } else {
        await page.getByRole("button", { name: "Show results", exact: true }).click();
        await hidden(dialog);
      }
    }
  });
}
for (const mobile of [false, true]) {
  const fixture = world();
  await check(`Create freezes an unconfirmed submission and retries one key ${mobile ? "phone" : "desktop"}`, "/portal/follow-ups/new", { handler: fixture.handler, mobile }, async page => {
    await shown(page.getByRole("heading", { name: "What needs to be done?", exact: true }));
    await shown(page.getByRole("heading", { name: "Student", exact: true }));
    await shown(page.getByRole("heading", { name: "Responsible staff member", exact: true }));
    await shown(page.getByRole("heading", { name: "Due date and time", exact: true }));
    await shown(page.getByText(/For a counseling follow-up, open the Student’s authorized Counseling Encounter or Routine Interview/));
    await shown(page.getByText("Creating one does not contact the Student or send a Student notification."));
    await noHorizontalOverflow(page);
    await screenshot(page, mobile ? "create-standalone-phone" : "create-standalone-desktop");
    await page.locator("#followup-student").selectOption(studentId);
    await page.locator("#followup-assignee").selectOption(user("COUNSELOR").id);
    await page.getByLabel("Due date and time (Philippine Time)", { exact: true }).fill("2099-01-01T10:00");
    await page.getByLabel("Task description (optional)", { exact: true }).fill("Synthetic follow-up content");
    await page.getByRole("button", { name: "Create follow-up", exact: true }).click();
    await shown(page.locator("form").getByRole("alert"));
    assert.equal(await page.getByLabel("Task description (optional)", { exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "Retry the same follow-up", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Follow-Up", exact: true }));
    assert.equal(fixture.writes.length, 2); assert.deepEqual(fixture.writes[0], fixture.writes[1]); assert.ok(fixture.writes[0].key);
    await noHorizontalOverflow(page); await screenshot(page, mobile ? "detail-phone" : "detail-desktop");
  });
}
for (const [empty, title, description] of [
  ["no-assigned", "No follow-ups assigned", "Follow-ups appear here when a next action is assigned to you."],
  ["no-pending", "No Pending follow-ups", "Choose another Status to review completed or cancelled work."],
]) {
  const fixture = world("COUNSELOR", { empty });
  await check(`Follow-Up empty state explains ${empty}`, "/portal/follow-ups", { handler: fixture.handler }, async page => {
    const message = page.locator('[data-density="compact"] p');
    await shown(message);
    assert.match(await message.textContent(), new RegExp(title));
    assert.match(await message.textContent(), new RegExp(description));
    await noHorizontalOverflow(page);
    await screenshot(page, empty === "no-assigned" ? "followups-empty-unassigned" : "followups-empty-pending");
  });
}
{
  const fixture = world("COUNSELOR", { empty: "no-assigned" });
  await check("Follow-Up empty state distinguishes an active filter from no assigned work", "/portal/follow-ups", { handler: fixture.handler }, async page => {
    await page.getByLabel("Status", { exact: true }).selectOption("COMPLETED");
    const message = page.locator('[data-density="compact"] p');
    await shown(message);
    assert.match(await message.textContent(), /No matching follow-ups/);
    assert.match(await message.textContent(), /Change Status or open Filters/);
  });
}
{
  const fixture = world();
  await check("Primary actions, secondary actions, task hierarchy, chronological history and conflict review remain clear", `/portal/follow-ups/${id}`, { handler: fixture.handler }, async page => {
    await shown(page.getByRole("heading", { name: "What needs to be done?", exact: true }));
    await shown(page.getByRole("heading", { name: "Current status and due date", exact: true }));
    await shown(page.getByRole("heading", { name: "Responsible staff member", exact: true }));
    await noHorizontalOverflow(page); await screenshot(page, "detail-pending-desktop");
    await shown(page.getByRole("button", { name: "Record activity", exact: true }));
    await shown(page.getByRole("button", { name: "Mark complete", exact: true }));
    const moreActions = page.getByRole("button", { name: "More actions", exact: true });
    await moreActions.focus(); await page.keyboard.press("Enter");
    const menu = page.getByRole("menu"); await shown(menu);
    assert.equal(await page.getByRole("menuitem", { name: "Edit task details", exact: true }).evaluate(element => element === document.activeElement), true, "keyboard opening moves focus into More actions");
    await page.keyboard.press("Escape");
    await page.waitForFunction(element => element === document.activeElement, await moreActions.elementHandle());
    assert.equal(await moreActions.evaluate(element => element === document.activeElement), true, "closing More actions restores focus");
    await moreActions.click();
    for (const label of ["Edit task details", "Change due date", "Reassign", "Cancel follow-up"]) await shown(menu.getByRole("menuitem", { name: label, exact: true }));
    await menu.getByRole("menuitem", { name: "Edit task details", exact: true }).click();
    await page.getByRole("textbox", { name: "Task description", exact: true }).fill("Retained synthetic edit");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await shown(page.getByRole("button", { name: "I reviewed the latest details", exact: true }));
    assert.equal(await page.getByRole("textbox", { name: "Task description", exact: true }).inputValue(), "Retained synthetic edit");
    assert.equal(await page.getByRole("button", { name: "Save changes", exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "I reviewed the latest details", exact: true }).click();
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await page.getByRole("button", { name: "Mark complete", exact: true }).click();
    await page.getByLabel("Completion outcome", { exact: true }).fill("Synthetic completion outcome");
    await page.getByRole("button", { name: "Review mark complete", exact: true }).click();
    const dialog = page.getByRole("alertdialog"); await shown(dialog);
    assert.equal(fixture.writes.length, 2);
    await screenshot(page, "complete-confirmation-desktop");
    await dialog.getByRole("button", { name: "Mark complete", exact: true }).click();
    await shown(page.getByText("Synthetic completion outcome", { exact: true }));
    await shown(page.getByRole("heading", { name: "Completion outcome", exact: true }));
    await shown(page.getByText("Due date changed", { exact: false }));
    await shown(page.getByText("Completed · Synthetic Counselor", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "More actions", exact: true }).count(), 0, "terminal records have no mutation menu");
    await noHorizontalOverflow(page); await screenshot(page, "detail-completed-desktop");
    assert.equal(fixture.writes.length, 3); assert.ok(fixture.writes.every(row => row.key));
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
  const fixture = world();
  await check("Recording activity logs progress, leaves the follow-up Pending, and restores focus", `/portal/follow-ups/${id}`, { handler: fixture.handler }, async page => {
    await page.getByRole("button", { name: "Record activity", exact: true }).click();
    await shown(page.getByText("Record an action or update. This follow-up will remain Pending.", { exact: true }));
    await page.getByLabel("Activity or update", { exact: true }).fill("Attempted Student contact; no answer.");
    await noHorizontalOverflow(page); await screenshot(page, "record-activity-desktop");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await shown(page.getByText("Activity recorded · Synthetic Counselor", { exact: true }));
    await shown(page.getByText("Attempted Student contact; no answer.", { exact: true }));
    assert.equal(await page.locator('[data-page-header=""]').getByText("Pending", { exact: true }).count(), 1);
    assert.equal(fixture.writes.length, 1);
    assert.match(fixture.writes[0].pathname, /\/activities$/);
    assert.equal(await page.getByRole("button", { name: "Record activity", exact: true }).evaluate(element => element === document.activeElement), true, "completed activity returns focus to its action");
    await noHorizontalOverflow(page);
  });
}
{
  const fixture = world();
  await check("Cancellation requires confirmation and leaves a readable terminal record", `/portal/follow-ups/${id}`, { handler: fixture.handler }, async page => {
    await page.getByRole("button", { name: "More actions", exact: true }).click();
    await page.getByRole("menuitem", { name: "Cancel follow-up", exact: true }).click();
    await page.getByLabel("Cancellation reason", { exact: true }).fill("The next action is no longer needed.");
    await page.getByRole("button", { name: "Review cancel follow-up", exact: true }).click();
    const dialog = page.getByRole("alertdialog"); await shown(dialog);
    assert.equal(fixture.writes.length, 0, "the request waits for explicit confirmation");
    await screenshot(page, "cancel-confirmation-desktop");
    await dialog.getByRole("button", { name: "Cancel follow-up", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Cancellation details", exact: true }));
    await shown(page.getByText("The next action is no longer needed.", { exact: true }).first());
    await shown(page.getByText("Cancelled · Synthetic Counselor", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "More actions", exact: true }).count(), 0);
    assert.equal(fixture.writes.length, 1); await noHorizontalOverflow(page); await screenshot(page, "detail-cancelled-desktop");
  });
}
for (const [sourceKind, category, visibility] of [
  ["COUNSELING_ENCOUNTER", "COUNSELING", "COUNSELOR_CONFIDENTIAL"],
  ["ROUTINE_INTERVIEW", "COUNSELING", "COUNSELOR_CONFIDENTIAL"],
  ["REFERRAL", "REFERRAL_ACTION", "OPERATIONAL"],
]) {
  const fixture = world("COUNSELOR", { source: true, sourceKind });
  await check(`${sourceKind} creation keeps the authorized source, category and assignment scope`, `/portal/follow-ups/new?source_kind=${sourceKind}&source_id=${sourceId}`, { handler: fixture.handler }, async (page, { requests }) => {
    await shown(page.getByText("Synthetic Student", { exact: true }));
    assert.equal(await page.getByLabel("Category", { exact: true }).inputValue(), category);
    assert.equal(await page.getByLabel("Category", { exact: true }).isDisabled(), true);
    assert.equal(requests.some(row => row.pathname.endsWith("/eligible-students")), false);
    const assigneeRequest = requests.find(row => row.pathname.endsWith("/eligible-assignees"));
    const parameters = new URLSearchParams(assigneeRequest?.search ?? "");
    assert.equal(parameters.get("student_id"), studentId);
    assert.equal(parameters.get("category"), category);
    assert.equal(parameters.get("source_kind"), sourceKind);
    assert.equal(parameters.get("source_id"), sourceId);
    if (visibility === "COUNSELOR_CONFIDENTIAL") await shown(page.getByText("Only the authorized Counselor for this record can be assigned.", { exact: true }));
    else await shown(page.getByText(/Operational coordination.*Created from the authorized related record/));
    await noHorizontalOverflow(page);
    if (sourceKind === "COUNSELING_ENCOUNTER") await screenshot(page, "create-counseling-linked-desktop");
  });
}
{
  const fixture = world("GUIDANCE_SERVICES_STAFF", { recoverable: true });
  await check("Operational recovery exposes only the summary and scoped assignment restoration", "/portal/follow-ups/reassignment", { handler: fixture.handler, mobile: true }, async page => {
    await shown(page.getByRole("heading", { name: "Recover assignments", exact: true }));
    await page.getByRole("button", { name: "Recover assignment for Synthetic Student", exact: true }).click();
    await page.getByLabel("Responsible staff member", { exact: true }).selectOption(user("GUIDANCE_SERVICES_STAFF").id);
    await page.getByRole("button", { name: "Recover assignment", exact: true }).click();
    await shown(page.getByText("No operational follow-ups need recovery in your current scope.", { exact: true }));
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
