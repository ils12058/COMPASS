// CW-3c temporary coverage journeys against the worktree's pages with synthetic canonical responses.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { casesFixture, casePath, counselor, detail, ids } from "./support/counseling-cases-fixtures.mjs";
import { continuityAccount, continuityAPI, head, receiver } from "./support/counseling-continuity-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("counseling-coverage");
const coverageId = "c3c00000-0000-4000-8000-000000000001";
const coveragePath = `/portal/counseling/coverages/${coverageId}`;
const preparePath = `/portal/counseling/cases/${ids.case}/coverage`;

function philippineInput(offsetDays) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(Date.now() + offsetDays * 86_400_000)).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function coverageFixture({ account = continuityAccount(), item = {}, stale = false } = {}) {
  const caseData = detail();
  const caseIdentity = Object.fromEntries(["id", "reference_code", "student", "primary_counselor", "status", "version"].map(key => [key, caseData[key]]));
  const state = {
    operations: [], stale,
    context: { case: caseIdentity, office_prepared: false, receiver_options: [
      { person: receiver, authorization_route: "INDEPENDENT_HEAD", blocked_reason: null },
      { person: head, authorization_route: "OWNER_TO_HEAD", blocked_reason: null },
    ], tasks: [
      { task_id: ids.action, version: 2, category: "COUNSELING", source_kind: null, due_at: "2099-01-07T02:00:00Z", assignee: counselor, title: "Protected synthetic action", can_delegate: true, blocked_reason: null, record_accessible: true },
      { task_id: ids.successor, version: 1, category: "COUNSELING", source_kind: "COUNSELING_ENCOUNTER", due_at: "2099-01-09T02:00:00Z", assignee: counselor, title: "Session-sourced synthetic action", can_delegate: false, blocked_reason: "Session-sourced actions stay with their author during coverage.", record_accessible: true },
    ] },
    item: { id: coverageId, reference_code: "COV-CASE-2026-000001-001", state: "PREPARED", version: 1, case: caseIdentity, primary_counselor: counselor, receiving_counselor: receiver, prepared_by: counselor, office_prepared: false, office_preparation_reason: null, reason: "PLANNED_ABSENCE", starts_at: "2099-01-05T00:00:00Z", expires_at: "2099-01-12T00:00:00Z", waiting_for: null, review_expires_at: null, independent_authorization: true, authorization_route: null, needs_new_arrangement: false, authorized_by: null, authorized_at: null, decided_by: null, decided_at: null, decision_reason: null, revoked_at: null, revoked_by: null, revocation_reason: null, recovery_required_count: 0, student_communication: "NO", student_informed_at: null, communication_recorded_by: counselor, communication_deferral_reason: null, communication_task_id: null, communication_responsible: null, tasks: [], history: [], ...item },
  };
  function projection() {
    const i = state.item;
    const preparer = account.id === i.prepared_by.id, receiving = account.id === i.receiving_counselor.id, primary = account.id === i.primary_counselor.id;
    const pending = ["PREPARED", "AUTHORIZED"].includes(i.state);
    const reviewer = account.id === head.id && !receiving && !preparer && i.state === "PREPARED" && Boolean(i.waiting_for);
    return { ...i, tasks: i.tasks.map(task => ({ ...task, title: primary ? task.title : null, record_accessible: primary })), review_accessible: receiving && i.state === "AUTHORIZED", can_edit: preparer && pending, can_submit: preparer && i.state === "PREPARED" && !i.waiting_for, can_authorize: reviewer, can_accept: receiving && i.state === "AUTHORIZED", can_decline: reviewer || (receiving && i.state === "AUTHORIZED"), can_cancel: preparer && pending, can_revoke: primary && ["SCHEDULED", "ACTIVE"].includes(i.state), can_arrange_transfer: false, can_open_case: primary };
  }
  const summary = () => { const { tasks: _tasks, history: _history, ...rest } = projection(); return rest; };
  const panel = () => ({ transfers: [], responsibility: [], history: [], can_transfer: true, can_arrange_coverage: true, coverages: state.item.history.length || state.item.state !== "PREPARED" ? [summary()] : [], coverage_history: state.item.history });
  const cases = casesFixture({ account, detail: { ...caseData, continuity: panel() } });
  state.handler = async input => {
    const { pathname, method, request, reply } = input;
    if (!pathname.startsWith(continuityAPI)) { cases.detail = { ...cases.detail, continuity: panel() }; return cases.handler(input); }
    state.operations.push({ pathname, method, ...(method !== "GET" ? { body: JSON.parse(request.postData()) } : {}) });
    if (pathname.endsWith("/coverage-context")) { await reply(state.context); return true; }
    if (method === "GET") { await reply(projection()); return true; }
    const body = JSON.parse(request.postData());
    if (pathname.endsWith("/coverages") || method === "PUT") {
      state.item = { ...state.item, receiving_counselor: body.receiving_counselor_id === head.id ? head : receiver, reason: body.reason, starts_at: body.starts_at, expires_at: body.expires_at, prepared_by: { id: account.id, display_name: account.first_name }, state: "PREPARED", waiting_for: null, student_communication: body.student_communication,
        tasks: body.tasks.map(plan => ({ ...state.context.tasks.find(task => task.task_id === plan.task_id), return_plan: plan.return_plan, assigned_counselor: receiver, returned_at: null, returned_by: null, recovery_required: false })) };
      await reply(projection(), 201); return true;
    }
    if (state.stale) { state.item.version++; state.item.state = "CANCELLED"; state.item.needs_new_arrangement = true; state.item.decision_reason = "REQUEST_WITHDRAWN"; await reply({ error: { code: "case_continuity_changed", message: "Private diagnostic" } }, 409); return true; }
    assert.equal(body.expected_version, state.item.version, "Every decision carries the reviewed version");
    const action = pathname.split("/").at(-1);
    const i = state.item;
    i.version++;
    if (action === "submit") { i.waiting_for = "Head approval"; }
    else if (action === "authorize") { Object.assign(i, { state: "AUTHORIZED", waiting_for: receiver.display_name, authorized_by: head, authorized_at: "2026-11-13T02:00:00Z", authorization_route: "INDEPENDENT_HEAD", review_expires_at: "2099-01-04T00:00:00Z" }); }
    else if (action === "accept") { Object.assign(i, { state: "ACTIVE", waiting_for: null }); }
    else { assert.ok(body.reason, "A declining, cancelling or revoking decision needs a reason"); Object.assign(i, { state: action === "revoke" ? "REVOKED" : action === "decline" ? "DECLINED" : "CANCELLED", decision_reason: body.reason, needs_new_arrangement: action !== "revoke", waiting_for: null }); }
    i.history.push({ id: `event-${i.version}`, coverage_id: coverageId, reference_code: i.reference_code, kind: { submit: "submitted", authorize: "authorized", accept: "accepted", decline: "declined", cancel: "cancelled", revoke: "revoked" }[action], version: i.version, actor: { id: account.id, display_name: account.first_name }, occurred_at: "2026-11-13T02:00:00Z", independent_authorization: true, authorization_route: i.authorization_route });
    await reply(projection()); return true;
  };
  state.projection = projection;
  return state;
}

async function decide(page, action, reason) {
  await page.getByRole("button", { name: action, exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: `${action}?`, exact: true });
  await shown(dialog);
  if (reason) await dialog.getByLabel("Reason for this decision", { exact: true }).selectOption(reason);
  await dialog.getByRole("button", { name: action, exact: true }).click();
  const completed = page.getByRole("alertdialog", { name: `${action} completed`, exact: true });
  await shown(completed.getByRole("button", { name: "Done", exact: true }));
  await completed.getByRole("button", { name: "Done", exact: true }).click();
  await hidden(completed);
  await page.waitForFunction(() => document.activeElement?.id === "coverage-review-heading");
}

async function fillPlan(page, days = 7) {
  await shown(page.getByLabel("Covering counselor", { exact: true }));
  await page.getByLabel("Covering counselor", { exact: true }).selectOption(receiver.id);
  await page.getByLabel("Starts (Philippine Time)", { exact: true }).fill(philippineInput(1));
  await page.getByLabel("Ends (Philippine Time)", { exact: true }).fill(philippineInput(1 + days));
  await page.getByLabel("Protected synthetic action", { exact: true }).check();
  await page.getByLabel("Return plan for Protected synthetic action", { exact: true }).selectOption("REVIEW_WITH_PRIMARY");
}

const panel = coverageFixture();
await check("case-panel-offers-coverage-beside-transfer", casePath, { handler: panel.handler }, async page => {
  const continuity = page.locator('[aria-labelledby="case-continuity-heading"]');
  await shown(continuity);
  await shown(continuity.getByText("No temporary coverage is arranged.", { exact: true }));
  await shown(continuity.getByRole("link", { name: "Transfer case", exact: true }));
  await continuity.getByRole("link", { name: "Arrange coverage", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Arrange temporary coverage", exact: true }));
  assert.match(await page.locator("main").innerText(), /stays the primary Counselor throughout the coverage/);
});

const preparation = coverageFixture();
await check("counselor-delegates-only-selected-actions-and-submits", preparePath, { handler: preparation.handler }, async page => {
  await fillPlan(page);
  assert.equal(await page.getByLabel("Session-sourced synthetic action", { exact: true }).isDisabled(), true, "A non-delegable action cannot be selected");
  await shown(page.getByText("Session-sourced actions stay with their author during coverage.", { exact: true }));
  await page.getByRole("button", { name: "Save coverage plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Coverage review", exact: true }));
  const saved = preparation.operations.find(operation => operation.method === "POST");
  assert.deepEqual(saved.body.tasks, [{ task_id: ids.action, expected_version: 2, return_plan: "REVIEW_WITH_PRIMARY" }]);
  assert.match(await page.locator("main").innerText(), /Review with the primary Counselor before coverage ends/);
  await decide(page, "Submit coverage");
  await shown(page.getByText("Waiting for Head approval", { exact: true }));
});

const tooLong = coverageFixture();
await check("interval-limits-are-explained-before-saving", preparePath, { handler: tooLong.handler }, async page => {
  await fillPlan(page, 31);
  await page.getByRole("button", { name: "Save coverage plan", exact: true }).click();
  await shown(page.getByRole("alert").filter({ hasText: "Coverage can last at most 30 days" }));
  assert.equal(tooLong.operations.filter(operation => operation.method !== "GET").length, 0, "Nothing is sent for an invalid interval");
});

const authorization = coverageFixture({ account: continuityAccount(head), item: { waiting_for: "Head approval", tasks: [{ task_id: ids.action, category: "COUNSELING", source_kind: null, due_at: "2099-01-07T02:00:00Z", title: "Protected synthetic action", return_plan: "RETURN_TO_PRIMARY", assigned_counselor: receiver, returned_at: null, returned_by: null, recovery_required: false }] } });
await check("head-authorizes-without-reading-action-titles", coveragePath, { handler: authorization.handler }, async page => {
  await shown(page.getByText("Counseling action 1", { exact: true }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
  await decide(page, "Authorize coverage");
  await shown(page.getByText(`Waiting for ${receiver.display_name} to accept`, { exact: true }).first());
});

const acceptance = coverageFixture({ account: continuityAccount(receiver), item: { state: "AUTHORIZED", waiting_for: receiver.display_name, authorization_route: "INDEPENDENT_HEAD", authorized_by: head, authorized_at: "2026-11-13T02:00:00Z", review_expires_at: "2099-01-04T00:00:00Z" } });
await check("receiver-accepts-and-primary-stays-responsible", coveragePath, { handler: acceptance.handler }, async page => {
  await shown(page.getByRole("button", { name: "Decline coverage", exact: true }));
  assert.match(await page.locator("main").innerText(), /Synthetic CW-1 Counselor \(stays responsible\)/);
  await decide(page, "Accept coverage");
  await shown(page.getByText(/^Covering counselor: Synthetic Receiving Counselor until/).first());
});

const staleAccept = coverageFixture({ account: continuityAccount(receiver), stale: true, item: { state: "AUTHORIZED", waiting_for: receiver.display_name, authorization_route: "INDEPENDENT_HEAD", review_expires_at: "2099-01-04T00:00:00Z" } });
await check("stale-acceptance-shows-latest-and-changes-nothing", coveragePath, { handler: staleAccept.handler }, async page => {
  await page.getByRole("button", { name: "Accept coverage", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Accept coverage?", exact: true });
  await dialog.getByRole("button", { name: "Accept coverage", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "This arrangement changed." }));
  await shown(page.getByText("Cancelled — another arrangement is needed", { exact: true }).first());
  assert.equal(await page.getByRole("button", { name: "Accept coverage", exact: true }).count(), 0);
});

const revocation = coverageFixture({ item: { state: "ACTIVE", authorization_route: "INDEPENDENT_HEAD" } });
await check("primary-ends-active-coverage-with-a-reason", coveragePath, { handler: revocation.handler }, async page => {
  await decide(page, "End coverage now", "ARRANGEMENT_NOT_SUITABLE");
  await shown(page.getByText("Revoked — the primary Counselor keeps the work", { exact: true }).first());
  const revoke = revocation.operations.find(operation => operation.pathname.endsWith("/revoke"));
  assert.equal(revoke.body.reason, "ARRANGEMENT_NOT_SUITABLE");
});

for (const width of [320, 390]) {
  const phone = coverageFixture();
  await check(`phone-${width}-coverage-preparation-and-review`, preparePath, { handler: phone.handler, viewport: { width, height: 844 }, timezoneId: "America/New_York" }, async page => {
    await fillPlan(page);
    await noHorizontalOverflow(page);
    await page.getByRole("button", { name: "Save coverage plan", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Coverage review", exact: true }));
    await noHorizontalOverflow(page);
    await screenshot(page, `coverage-phone-${width}`);
  });
}
await finish();
