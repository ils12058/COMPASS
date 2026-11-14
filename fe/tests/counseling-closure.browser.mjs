import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { closureFixture, closureNote } from "./support/counseling-closure-fixtures.mjs";
import { casePath, casesAPI, counselor, detail, followup, ids, root, student, summary } from "./support/counseling-cases-fixtures.mjs";
import { continuityAccount, continuityAPI, continuityFixture, head, office, receiver, transferPath, preparePath } from "./support/counseling-continuity-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("counseling-closure");
const closePath = `${casePath}/close`;
const reopenPath = `${casePath}/reopen`;
const reasonLabels = { PLANNED_SUPPORT_CONCLUDED: "Planned support concluded", STUDENT_DISCONTINUED: "Student chose to discontinue", CONTACT_NOT_REESTABLISHED: "Unable to re-establish contact after documented attempts", EXTERNAL_HANDOVER_CONFIRMED: "External service handover confirmed", ELIGIBILITY_ENDED: "Institutional service eligibility ended" };

async function closeDetails(page, reason = "PLANNED_SUPPORT_CONCLUDED") {
  await page.getByRole("button", { name: "Next: closure details", exact: true }).click();
  await shown(page.getByLabel("Closure reason", { exact: true }));
  await page.getByLabel("Closure reason", { exact: true }).selectOption(reason);
  await page.getByLabel("Outcome", { exact: true }).selectOption("NOT_ASSESSED");
  await page.getByLabel(/^Confidential closure note/).fill(closureNote);
  await page.getByRole("button", { name: "Review closure", exact: true }).click();
  return page.getByRole("alertdialog", { name: "3. Close this case?", exact: true });
}
async function confirmClose(page, dialog) {
  await dialog.getByRole("button", { name: "Close case", exact: true }).click();
  const completed = page.getByRole("alertdialog", { name: "Case closed", exact: true });
  await shown(completed.getByRole("button", { name: "Done", exact: true }));
  assert.equal(await completed.getByRole("button", { name: "Done", exact: true }).evaluate(element => element === document.activeElement), true, "Done receives focus after confirmed closure");
  // A focus refetch after closing must not replace the confirmed result: the Active-only review now answers 409.
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await page.waitForTimeout(500);
  assert.equal(await completed.getByRole("button", { name: "Done", exact: true }).isVisible(), true, "The confirmed closure stays visible after a refetch");
  await completed.getByRole("button", { name: "Done", exact: true }).click();
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
}
async function reopen(page) {
  await page.getByRole("link", { name: "Reopen case", exact: true }).click();
  await shown(page.getByText("If this is a different concern, open a new case instead.", { exact: true }));
  const newCase = page.getByRole("link", { name: "Open new case for this Student", exact: true });
  assert.equal(new URL(await newCase.getAttribute("href"), "http://localhost").searchParams.get("student"), ids.student);
  await page.getByRole("button", { name: "Next: reopening reason", exact: true }).click();
  await page.getByLabel("Reopening reason", { exact: true }).selectOption("SAME_CONCERN_RETURNED");
  await page.getByRole("button", { name: "Review reopening", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "3. Reopen this case?", exact: true });
  await dialog.getByRole("button", { name: "Reopen case", exact: true }).click();
  const complete = page.getByRole("alertdialog", { name: "Case reopened", exact: true });
  await shown(complete.getByRole("button", { name: "Done", exact: true }));
  await complete.getByRole("button", { name: "Done", exact: true }).click();
  await shown(page.getByRole("link", { name: "Close case", exact: true }));
}

const blockers = closureFixture({ followups: [followup()], state: { transfers: [{ id: "c3000000-0000-4000-8000-000000000001", reference_code: "TRF-SYNTH-1", state: "PREPARED" }], coverages: [{ id: "c3c00000-0000-4000-8000-000000000001", reference_code: "COV-SYNTH-1", state: "ACTIVE" }], delegated_task_ids: [ids.successor], appointments: [{ id: ids.nextAppointment, reference_code: "APT-SYNTH-1", starts_at: "2099-01-08T01:00:00Z", ends_at: "2099-01-08T02:00:00Z" }] } });
await check("all-blockers-link-to-their-owning-workflows", closePath, { handler: blockers.handler }, async page => {
  for (const label of ["Pending transfer", "Pending or current coverage", "Delegated action awaiting return", "Upcoming linked Appointment", "Pending action without an after-closure plan"]) await shown(page.getByText(label, { exact: true }));
  for (const [label, path] of [["TRF-SYNTH-1 · Review or cancel transfer", "/portal/counseling/transfers/"], ["COV-SYNTH-1 · Review or end coverage", "/portal/counseling/coverages/"], ["Review delegated action", "/portal/follow-ups/"], ["APT-SYNTH-1 · Open Appointment actions", "/portal/appointments/"], ["Complete or cancel action", "/portal/follow-ups/"]]) assert.ok((await page.getByRole("link", { name: label, exact: true }).getAttribute("href")).startsWith(path));
  assert.equal(await page.getByRole("button", { name: "Next: closure details", exact: true }).isDisabled(), true);
  assert.equal(blockers.operations.length, 0, "Reviewing blocked closure never cancels, completes or unlinks anything");
});

const administrative = closureFixture({ followups: [followup()] });
await check("pending-administrative-action-needs-explicit-owner-due-date-and-mark", closePath, { handler: administrative.handler }, async page => {
  await page.getByRole("button", { name: "Keep after closure", exact: true }).click();
  await page.getByRole("checkbox", { name: "This is an administrative action to keep after closure.", exact: true }).check();
  await page.getByLabel("Owner after closure", { exact: true }).selectOption(counselor.id);
  await page.getByLabel("Due (Philippine Time)", { exact: true }).fill("2099-01-08T10:00");
  await page.getByRole("button", { name: "Save after-closure plan", exact: true }).click();
  await shown(page.getByText(/After closure$/));
  const sent = administrative.operations.find(operation => operation.pathname.endsWith("/after-closure"));
  assert.deepEqual(sent.body, { expected_version: 4, expected_task_version: 1, administrative_action: true, assigned_to_id: counselor.id, due_at: "2099-01-08T02:00:00.000Z" });
  await confirmClose(page, await closeDetails(page));
  assert.equal(administrative.cases.followups[0].status, "PENDING", "Closure keeps the deliberately designated action pending");
  await shown(page.locator('[aria-labelledby="case-next-actions-heading"]').getByRole("link", { name: "Check progress with Student", exact: true }));
});

for (const reason of Object.keys(reasonLabels)) {
  const fixture = closureFixture();
  await check(`close-${reason.toLowerCase()}-retains-readonly-case`, closePath, { handler: fixture.handler }, async page => {
    const dialog = await closeDetails(page, reason);
    await confirmClose(page, dialog);
    const record = page.locator('[aria-labelledby="case-details-heading"]');
    await shown(record.getByText(reasonLabels[reason], { exact: true }));
    await shown(record.getByText("Not assessed", { exact: true }));
    await shown(record.getByText(closureNote, { exact: true }));
    assert.doesNotMatch(await page.locator("main").innerText(), /resolved|successful/i);
    for (const action of ["Record session", "Add next action", "Link appointment", "Add recorded session", "Transfer case", "Arrange coverage"]) assert.equal(await page.getByRole("link", { name: action, exact: true }).count() + await page.getByRole("button", { name: action, exact: true }).count(), 0, `${action} is absent from a Closed case`);
    assert.equal(fixture.cases.detail.session_count, 2);
    assert.equal(fixture.cases.detail.sessions.length, 2);
    await shown(page.getByRole("link", { name: "Reopen case", exact: true }));
    if (reason === "CONTACT_NOT_REESTABLISHED") {
      await reopen(page);
      await shown(page.getByText("Case reopened · Same concern returned", { exact: true }));
      assert.equal(fixture.cases.detail.closures.length, 1);
      assert.equal(fixture.cases.detail.closures[0].note, closureNote);
    }
  });
}

const contact = closureFixture();
await check("contact-reason-requires-a-note-before-confirmation", closePath, { handler: contact.handler }, async page => {
  await page.getByRole("button", { name: "Next: closure details", exact: true }).click();
  await page.getByLabel("Closure reason", { exact: true }).selectOption("CONTACT_NOT_REESTABLISHED");
  await page.getByLabel("Confidential closure note (required)", { exact: true }).fill("Short note");
  await page.getByRole("button", { name: "Review closure", exact: true }).click();
  await shown(page.getByRole("alert").filter({ hasText: "at least 20 characters" }));
  assert.equal(contact.operations.length, 0);
});

for (const mode of ["stale", "blocked-race", "failure"]) {
  const fixture = closureFixture({ state: { mode } });
  await check(`${mode}-closure-preserves-input-and-never-replays`, closePath, { handler: fixture.handler }, async page => {
    const dialog = await closeDetails(page, "CONTACT_NOT_REESTABLISHED");
    await dialog.getByRole("button", { name: "Close case", exact: true }).click();
    if (mode === "failure") {
      await shown(dialog.getByRole("alert"));
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(await page.getByLabel("Confidential closure note (required)", { exact: true }).inputValue(), closureNote);
    } else {
      await hidden(dialog);
      await shown(page.getByRole("status").filter({ hasText: mode === "stale" ? "case changed" : "Outstanding work" }));
      if (mode === "blocked-race") await shown(page.getByText("Pending transfer", { exact: true }));
    }
    assert.equal(fixture.operations.length, 1);
    assert.equal(fixture.cases.detail.status, "ACTIVE");
    assert.doesNotMatch(await page.locator("main").innerText(), /Private diagnostic/);
  });
}

const closedRow = summary(detail({ id: ids.otherCase, student: { ...student, display_name: "Closed Synthetic Student" }, status: "CLOSED", closed_at: "2026-11-13T04:00:00Z", closure_reason: "STUDENT_DISCONTINUED" }));
const list = closureFixture();
list.cases.list.push(closedRow);
await check("my-cases-default-active-closed-and-all-filters", root, { handler: list.handler }, async page => {
  await shown(page.getByRole("link", { name: student.display_name, exact: true }));
  assert.equal(await page.getByRole("link", { name: "Closed Synthetic Student", exact: true }).count(), 0);
  await page.getByRole("button", { name: /Filters/ }).click();
  await page.getByLabel("Status", { exact: true }).selectOption("CLOSED");
  await page.getByRole("button", { name: "Apply filters", exact: true }).click();
  await shown(page.getByRole("link", { name: "Closed Synthetic Student", exact: true }));
  await shown(page.getByText("Student chose to discontinue", { exact: true }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Not assessed|Synthetic documented contact/);
  await page.getByRole("button", { name: /Filters/ }).click();
  await page.getByLabel("Status", { exact: true }).selectOption("all");
  await page.getByRole("button", { name: "Apply filters", exact: true }).click();
  await shown(page.getByRole("link", { name: student.display_name, exact: true }));
  await shown(page.getByRole("link", { name: "Closed Synthetic Student", exact: true }));
});

for (const width of [320, 390]) {
  const fixture = closureFixture();
  await check(`phone-${width}-close-and-reopen`, closePath, { handler: fixture.handler, viewport: { width, height: 844 }, timezoneId: "America/New_York" }, async page => {
    await noHorizontalOverflow(page);
    const dialog = await closeDetails(page, "CONTACT_NOT_REESTABLISHED");
    await noHorizontalOverflow(page);
    await confirmClose(page, dialog);
    await noHorizontalOverflow(page);
    await shown(page.getByText(/Nov 13, 2026(?:,| at) 12:00\s*PM/).first());
    await reopen(page);
    await noHorizontalOverflow(page);
    await screenshot(page, `closure-phone-${width}`);
  });
}

function reopeningTransfer(account, changes = {}, stale = false) {
  const identity = Object.fromEntries(["id", "reference_code", "student", "primary_counselor", "status", "version"].map(key => [key, detail({ status: "CLOSED" })[key]]));
  return continuityFixture({ account, item: { purpose: "REOPEN", case: identity, office_prepared: true, prepared_by: office, office_preparation_reason: "OWNER_UNAVAILABLE", handoff: null, handoff_required: false, ...changes }, state: { stale, context: { purpose: "REOPEN", case: identity, office_prepared: true, tasks: [], appointments: [], receiver_options: [{ person: receiver, authorization_route: "INDEPENDENT_HEAD", blocked_reason: null }, { person: head, authorization_route: null, blocked_reason: "No independent approver is available." }] } } });
}
async function transferDecision(page, action) {
  await page.getByRole("button", { name: action, exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: `${action}?`, exact: true });
  await dialog.getByRole("button", { name: action, exact: true }).click();
  const completed = page.getByRole("alertdialog", { name: `${action} completed`, exact: true });
  await shown(completed.getByRole("button", { name: "Done", exact: true }));
  await completed.getByRole("button", { name: "Done", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "transfer-review-heading");
}
const officeReopen = reopeningTransfer(continuityAccount(office, "GUIDANCE_OFFICE_ASSISTANT"));
await check("office-prepares-closed-case-reopening-with-independent-head-rule", "/portal/counseling/continuity?status=CLOSED", { handler: officeReopen.handler }, async page => {
  await page.getByRole("link", { name: /Transfer to reopen/ }).click();
  await shown(page.getByRole("heading", { name: "Transfer to reopen case", exact: true }));
  await page.getByLabel("Receiving counselor", { exact: true }).selectOption(head.id);
  await shown(page.getByRole("alert").filter({ hasText: "No independent approver" }));
  await page.getByLabel("Receiving counselor", { exact: true }).selectOption(receiver.id);
  await page.getByLabel("Why is the office preparing this?", { exact: true }).selectOption("OWNER_UNAVAILABLE");
  assert.equal(await page.getByRole("heading", { name: "4. Handoff", exact: true }).count(), 0);
  assert.equal(await page.getByRole("option", { name: "Deferred", exact: true }).count(), 0);
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
  const prepared = officeReopen.operations.find(operation => operation.method === "POST");
  assert.equal(prepared.body.purpose, "REOPEN");
  assert.deepEqual(prepared.body.tasks, []);
  assert.deepEqual(prepared.body.appointments, []);
  assert.equal(prepared.body.handoff_sections, undefined);
  await transferDecision(page, "Submit transfer");
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action|Synthetic documented contact|Not assessed/);
});
const headReopen = reopeningTransfer(continuityAccount(head), { waiting_for: "Head approval" });
await check("independent-head-authorizes-reopening-transfer-without-case-narrative", transferPath, { handler: headReopen.handler }, async page => {
  await transferDecision(page, "Authorize transfer");
  assert.equal(headReopen.item.case.status, "CLOSED");
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action|Synthetic documented contact|Not assessed/);
});
const receiverReopen = reopeningTransfer(continuityAccount(receiver), { state: "AUTHORIZED", waiting_for: receiver.display_name, review_expires_at: "2099-01-01T00:00:00Z", authorization_route: "INDEPENDENT_HEAD" });
await check("receiver-explicitly-accepts-and-reopens-closed-case", transferPath, { handler: receiverReopen.handler }, async page => {
  await shown(page.getByText(/Acceptance reopens it with reason/));
  await transferDecision(page, "Accept and reopen case");
  assert.equal(receiverReopen.item.case.status, "ACTIVE");
  assert.equal(receiverReopen.item.case.primary_counselor.id, receiver.id);
  await shown(page.getByText(/The case is Active again/));
});
const staleReopen = reopeningTransfer(continuityAccount(receiver), { state: "AUTHORIZED", waiting_for: receiver.display_name, review_expires_at: "2099-01-01T00:00:00Z", authorization_route: "INDEPENDENT_HEAD" }, true);
// The backend refuses acceptance after the owner reopened the case with this exact code.
staleReopen.staleCode = "case_continuity_case_not_closed";
await check("stale-reopening-transfer-keeps-case-closed", transferPath, { handler: staleReopen.handler }, async page => {
  await page.getByRole("button", { name: "Accept and reopen case", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Accept and reopen case?", exact: true });
  await dialog.getByRole("button", { name: "Accept and reopen case", exact: true }).click();
  await hidden(dialog);
  await shown(page.getByText("This case is no longer Closed, so this reopening transfer can't be accepted.", { exact: true }));
  assert.equal(staleReopen.item.case.status, "CLOSED");
  assert.equal(staleReopen.item.case.primary_counselor.id, counselor.id);
});

const privacyRow = { id: "c4000000-0000-4000-8000-000000000001", reason: "CONTACT_NOT_REESTABLISHED", outcome: "NOT_ASSESSED", note: closureNote, closed_at: "2026-11-13T04:00:00Z", closed_by: counselor, reopened_at: null, reopened_by: null, reopen_reason: null };
const privateCase = closureFixture({ detail: { status: "CLOSED", can_reopen: true, closure: privacyRow, closures: [privacyRow] } });
let heldRead = null;
await check("owner-note-clears-offline-and-rejects-a-late-case-read", casePath, { handler: async input => { if (input.pathname === `${casesAPI}/${ids.case}` && input.method === "GET" && heldRead) await heldRead; return privateCase.handler(input); } }, async (page, fixture) => {
  await shown(page.getByText(closureNote, { exact: true }));
  await fixture.context.setOffline(true);
  await shown(page.getByRole("button", { name: "Retry", exact: true }));
  assert.equal(await page.getByText(closureNote, { exact: true }).count(), 0);
  await fixture.context.setOffline(false);
  let release;
  heldRead = new Promise(resolve => { release = resolve; });
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "Loading" }).first());
  await fixture.context.setOffline(true);
  heldRead = null;
  release();
  await shown(page.getByRole("button", { name: "Retry", exact: true }));
  assert.equal(await page.getByText(closureNote, { exact: true }).count(), 0, "A late response cannot repopulate the cleared note");
  await fixture.context.setOffline(false);
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByText(closureNote, { exact: true }));
});

const keyboardCase = closureFixture();
await check("keyboard-close-review-input-confirmation-and-focus", closePath, { handler: keyboardCase.handler }, async page => {
  const tabKey = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
  async function tabTo(locator) {
    await shown(locator);
    const handle = await locator.elementHandle();
    for (let index = 0; index < 100; index++) {
      if (await page.evaluate(element => element === document.activeElement, handle)) return;
      await page.keyboard.press(tabKey);
    }
    throw new Error("The named case control is not reachable with Tab");
  }
  await tabTo(page.getByRole("button", { name: "Next: closure details", exact: true }));
  await page.keyboard.press("Enter");
  await tabTo(page.getByLabel("Closure reason", { exact: true }));
  // Type-ahead changes a closed native select in every engine; arrow keys open the macOS popup instead.
  await page.keyboard.type("Contact");
  assert.equal(await page.getByLabel("Closure reason", { exact: true }).inputValue(), "CONTACT_NOT_REESTABLISHED");
  const note = page.getByLabel("Confidential closure note (required)", { exact: true });
  await tabTo(note);
  // Linux WebKit in CI dropped every key after the first word of a per-key type() (the field held
  // only "Synthetic", so Review stayed blocked). This check is about reaching, confirming and
  // returning focus by keyboard; insertText still enters the note through the focused field.
  await page.keyboard.insertText(closureNote);
  assert.equal(await note.inputValue(), closureNote, "The keyboard-entered note is complete");
  await tabTo(page.getByRole("button", { name: "Review closure", exact: true }));
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("alertdialog", { name: "3. Close this case?", exact: true });
  await tabTo(dialog.getByRole("button", { name: "Close case", exact: true }));
  await page.keyboard.press("Enter");
  const done = page.getByRole("alertdialog", { name: "Case closed", exact: true }).getByRole("button", { name: "Done", exact: true });
  await shown(done);
  await page.waitForFunction(element => document.activeElement === element, await done.elementHandle());
  await page.keyboard.press("Enter");
  await shown(page.getByRole("link", { name: "Reopen case", exact: true }));
});

const hiddenCase = closureFixture({ detail: { status: "CLOSED", can_reopen: true, closure: privacyRow, closures: [privacyRow] } });
await check("owner-note-clears-when-tab-is-hidden-until-authority-rechecked", casePath, { handler: hiddenCase.handler }, async page => {
  await shown(page.getByText(closureNote, { exact: true }));
  await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" }); document.dispatchEvent(new Event("visibilitychange")); });
  await shown(page.getByRole("button", { name: "Retry", exact: true }));
  assert.equal(await page.getByText(closureNote, { exact: true }).count(), 0);
  await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" }); document.dispatchEvent(new Event("visibilitychange")); });
  assert.equal(await page.getByText(closureNote, { exact: true }).count(), 0, "Visible again does not grant access or restore the old note");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByText(closureNote, { exact: true }));
});

await finish();
