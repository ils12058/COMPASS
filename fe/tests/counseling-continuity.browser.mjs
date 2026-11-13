// CW-3 role journeys use the worktree's actual pages and synthetic canonical responses.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { counselor, casePath } from "./support/counseling-cases-fixtures.mjs";
import { continuityAccount, continuityFixture, head, office, preparePath, receiver, transferPath } from "./support/counseling-continuity-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, settleFetches, finish } = await createBrowserHarness("counseling-continuity");
const tabs = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
async function tabTo(page, locator) {
  await shown(locator);
  const element = await locator.elementHandle();
  for (let index = 0; index < 100; index++) {
    if (await page.evaluate(target => document.activeElement === target, element)) return;
    await page.keyboard.press(tabs);
  }
  throw new Error("The action is not keyboard reachable");
}
async function confirm(page, action, reason) {
  await page.getByRole("button", { name: action, exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: `${action}?`, exact: true });
  await shown(dialog);
  if (reason) await dialog.getByLabel("Reason for this decision", { exact: true }).selectOption(reason);
  await dialog.getByRole("button", { name: action, exact: true }).click();
  const completed = page.getByRole("alertdialog", { name: `${action} completed`, exact: true });
  await shown(completed.getByRole("button", { name: "Done", exact: true }));
  assert.equal(await completed.getByRole("button").count(), 1, "A confirmed action has only Done");
  await completed.getByRole("button", { name: "Done", exact: true }).click();
  await hidden(completed);
  await page.waitForFunction(() => document.activeElement?.id === "transfer-review-heading");
}
async function submitHandoff(page) {
  await page.getByRole("link", { name: "Open handoff", exact: true }).click();
  await shown(page.getByRole("button", {name:"Submit handoff",exact:true}));
  await page.getByRole("button", {name:"Submit handoff",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Submit handoff?",exact:true});
  await dialog.getByRole("button",{name:"Submit handoff",exact:true}).click();
  await shown(page.getByRole("alertdialog",{name:"Handoff submitted",exact:true}));
  await page.getByRole("button",{name:"Done",exact:true}).click();
  await page.getByRole("link",{name:"Back to transfer review",exact:true}).click();
  await shown(page.getByRole("heading",{name:"Transfer review",exact:true}));
}
async function fillPreparation(page, chosen = receiver) {
  await shown(page.getByLabel("Receiving counselor", { exact: true }));
  await page.getByLabel("Receiving counselor", { exact: true }).selectOption(chosen.id);
  await page.getByLabel("Plan for action 1", { exact: true }).selectOption("TRANSFER");
  await page.getByLabel("Plan for APT-CW3-0001", { exact: true }).selectOption("RETAIN_WITH_PROVIDER");
  await page.getByLabel(`Why retain ${counselor.display_name}?`, { exact: true }).selectOption("CONTINUING_SUPPORT");
  if (await page.getByLabel("Current concern and handoff purpose", {exact:true}).count()) {
    await page.getByLabel("Current concern and handoff purpose", {exact:true}).fill("Synthetic continuation context");
    await page.getByLabel("What the receiver should review or do next", {exact:true}).fill("Review the specified work");
  }
}
function reviewFixture(person, state = "AUTHORIZED", changes = {}) {
  const fixture = continuityFixture({ account: continuityAccount(person), item: { state, waiting_for: state === "AUTHORIZED" ? receiver.display_name : "Head approval", authorization_route: state === "AUTHORIZED" ? "INDEPENDENT_HEAD" : null, review_expires_at: state === "AUTHORIZED" ? "2099-01-15T00:00:00Z" : null, ...changes } });
  fixture.item.tasks = fixture.context.tasks.map(task => ({ ...task, title: "Protected synthetic action", disposition: "TRANSFER", successor_due_at: null, successor_title: null }));
  fixture.item.appointments = fixture.context.appointments.map(appointment => ({ ...appointment, disposition: "RETAIN_WITH_PROVIDER", retention_reason: "CONTINUING_SUPPORT" }));
  return fixture;
}

const owner = continuityFixture();
await check("case-panel-names-owner-and-starts-transfer", casePath, { handler: owner.handler }, async page => {
  const panel = page.locator('[aria-labelledby="case-continuity-heading"]');
  await shown(panel);
  assert.match(await panel.innerText(), /Primary counselor: Synthetic CW-1 Counselor/);
  const transfer = panel.getByRole("link", { name: "Transfer case", exact: true });
  await tabTo(page, transfer); await page.keyboard.press("Enter");
  await shown(page.getByRole("heading", { name: "Transfer case", exact: true }));
  await shown(page.getByLabel("Receiving counselor", { exact: true }));
});

const preparation = continuityFixture();
await check("counselor-prepares-all-work-and-deferred-communication", preparePath, { handler: preparation.handler }, async page => {
  await fillPreparation(page);
  assert.deepEqual(await page.getByRole("heading", { name: /^[1-6]\. / }).allTextContents(), ["1. Receiver and reason", "2. Pending actions", "3. Upcoming appointments", "4. Handoff", "5. Student communication", "6. Review and save"]);
  await page.getByLabel("Has the Student been informed?", { exact: true }).selectOption("DEFERRED");
  await page.getByLabel("Why informing is deferred", { exact: true }).selectOption("CONTACT_PENDING");
  await page.getByLabel("Next action to inform the Student", { exact: true }).fill("Contact Student about new Counselor");
  await page.getByLabel("Communication deadline (Philippine Time)", { exact: true }).fill("2099-01-07T10:00");
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
  const write = preparation.operations.find(operation => operation.method === "POST");
  assert.equal(write.body.communication_due_at, "2099-01-07T02:00:00.000Z");
  assert.equal(write.body.tasks[0].disposition, "TRANSFER");
  assert.equal(write.body.appointments[0].disposition, "RETAIN_WITH_PROVIDER");
  assert.equal(preparation.item.case.primary_counselor.id, counselor.id);
  await submitHandoff(page);
  await confirm(page, "Submit transfer");
  await shown(page.getByText("Waiting for Head approval", { exact: true }));
  assert.equal(preparation.item.case.primary_counselor.id, counselor.id);
  await screenshot(page, "counselor-submitted-transfer");
});

const missing = continuityFixture();
await check("every-task-and-appointment-plan-is-required", preparePath, { handler: missing.handler }, async page => {
  await page.getByLabel("Receiving counselor", { exact: true }).selectOption(receiver.id);
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  assert.equal(missing.operations.filter(operation => operation.method === "POST").length, 0);
});

const edited = reviewFixture(counselor, "PREPARED", { reason: "PLANNED_ABSENCE", waiting_for: null });
await check("editing-keeps-the-saved-reason-and-reviewed-work", `${preparePath}?edit=${edited.item.id}`, { handler: edited.handler }, async page => {
  await shown(page.getByLabel("Receiving counselor", { exact: true }));
  await settleFetches(page);
  assert.equal(await page.getByLabel("Neutral reason", { exact: true }).inputValue(), "PLANNED_ABSENCE");
  assert.equal(await page.getByLabel("Plan for action 1", { exact: true }).inputValue(), "TRANSFER");
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
  const write = edited.operations.find(operation => operation.method === "PUT");
  assert.equal(write.body.reason, "PLANNED_ABSENCE");
  assert.equal(write.body.tasks[0].disposition, "TRANSFER");
});

const reasonChange = continuityFixture();
reasonChange.context.tasks[0].allowed_dispositions.push("RETAIN");
await check("changing-reason-preserves-input-and-refreshes-dispositions", preparePath, { handler: reasonChange.handler }, async page => {
  await fillPreparation(page);
  await page.getByLabel("Neutral reason", { exact: true }).selectOption("PLANNED_ABSENCE");
  await settleFetches(page);
  assert.equal(await page.getByLabel("Receiving counselor", { exact: true }).inputValue(), receiver.id);
  assert.equal(await page.getByLabel("Plan for action 1", { exact: true }).inputValue(), "TRANSFER");
  await page.getByLabel("Plan for action 1", { exact: true }).selectOption("RETAIN");
  await page.getByLabel("Neutral reason", { exact: true }).selectOption("IMPARTIALITY_CONCERN");
  await shown(page.getByText("This disposition is no longer available for the selected reason.", { exact: true }));
  assert.equal(await page.getByLabel("Receiving counselor", { exact: true }).inputValue(), receiver.id);
});

const headReview = reviewFixture(head, "PREPARED");
await check("head-authorizes-only-metadata-and-keeps-current-owner", transferPath, { handler: headReview.handler }, async page => {
  await shown(page.getByRole("button", { name: "Authorize transfer", exact: true }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
  assert.equal(await page.getByRole("link", { name: "Open action", exact: true }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Accept transfer", exact: true }).count(), 0);
  await confirm(page, "Authorize transfer");
  assert.equal(headReview.item.case.primary_counselor.id, counselor.id);
  await shown(page.getByText(`Waiting for ${receiver.display_name} to accept`, { exact: true }));
});

const accepting = reviewFixture(receiver);
await check("receiver-accepts-scoped-review-and-focuses-confirmed-result", transferPath, { handler: accepting.handler }, async page => {
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
  const button = page.getByRole("button", { name: "Accept transfer", exact: true });
  await tabTo(page, button); await page.keyboard.press("Enter");
  const dialog = page.getByRole("alertdialog", { name: "Accept transfer?", exact: true });
  await shown(dialog); await page.keyboard.press("Escape"); await hidden(dialog);
  await confirm(page, "Accept transfer");
  assert.equal(accepting.item.case.primary_counselor.id, receiver.id);
  assert.equal(await page.getByRole("button", { name: "Accept transfer", exact: true }).count(), 0);
  await shown(page.getByRole("link", { name: "Open case CASE-2026-000001", exact: true }));
  assert.equal(await page.getByRole("heading", { name: "Pending actions", exact: true }).count(), 0, "The terminal review package has ended");
});

const declining = reviewFixture(receiver);
await check("receiver-declines-with-bounded-reason-and-owner-stays", transferPath, { handler: declining.handler }, async page => {
  await confirm(page, "Decline transfer", "NO_CAPACITY");
  assert.equal(declining.item.case.primary_counselor.id, counselor.id);
  assert.equal(declining.item.decision_reason, "NO_CAPACITY");
  await shown(page.getByText(/another arrangement is needed\./));
});

const toHead = continuityFixture();
await check("personal-request-to-only-head-needs-explicit-acceptance", preparePath, { handler: toHead.handler }, async page => {
  await fillPreparation(page, head);
  await shown(page.getByText(/Personally requested.*no independent Head authorization\./));
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
  await submitHandoff(page);
  await confirm(page, "Submit transfer");
  assert.equal(toHead.item.state, "AUTHORIZED");
  assert.equal(toHead.item.independent_authorization, false);
  assert.equal(toHead.item.case.primary_counselor.id, counselor.id);
});
const incomingHead = reviewFixture(head, "AUTHORIZED", { receiving_counselor: head, authorization_route: "OWNER_TO_HEAD", independent_authorization: false });
await check("receiving-head-cannot-authorize-her-own-incoming-case", transferPath, { handler: incomingHead.handler }, async page => {
  await shown(page.getByRole("button", { name: "Accept transfer", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Authorize transfer", exact: true }).count(), 0);
  await confirm(page, "Accept transfer");
  assert.equal(incomingHead.item.case.primary_counselor.id, head.id);
});

const blockedOffice = continuityFixture({ account: continuityAccount(office, "GUIDANCE_OFFICE_ASSISTANT") });
await check("office-lookup-hides-content-and-incoming-head-route-is-blocked", "/portal/counseling/continuity", { handler: blockedOffice.handler }, async page => {
  await shown(page.getByRole("link", { name: "Transfer case CASE-2026-000001", exact: true }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
  await page.getByRole("link", { name: "Transfer case CASE-2026-000001", exact: true }).click();
  await page.getByLabel("Receiving counselor", { exact: true }).selectOption(head.id);
  await shown(page.getByText(/No independent approver is available\./));
  assert.equal(await page.getByRole("button", { name: "Save transfer plan", exact: true }).isDisabled(), true);
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
  assert.equal(await page.getByLabel("Plan for action 1", { exact: true }).locator("option").count(), 3);
});
const officePreparation = continuityFixture({ account: continuityAccount(office, "GUIDANCE_OFFICE_ASSISTANT") });
await check("office-prepares-with-attributed-operational-reason", preparePath, { handler: officePreparation.handler }, async page => {
  await fillPreparation(page);
  await page.getByLabel("Why is the office preparing this?", { exact: true }).selectOption("OWNER_UNAVAILABLE");
  await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
  assert.equal(await page.getByRole("button", {name:"Submit transfer",exact:true}).count(),0,"Office preparation needs the Head exception first");
  assert.equal(officePreparation.operations.find(operation=>operation.method==="POST").body.handoff_sections,undefined);
  assert.equal(officePreparation.item.prepared_by.id, office.id);
  assert.equal(officePreparation.item.state, "PREPARED");
  assert.doesNotMatch(await page.locator("main").innerText(), /Protected synthetic action/);
});

const stale = reviewFixture(receiver); stale.stale = true;
await check("stale-acceptance-hides-package-and-applies-nothing", transferPath, { handler: stale.handler }, async page => {
  await page.getByRole("button", { name: "Accept transfer", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Accept transfer?", exact: true });
  await dialog.getByRole("button", { name: "Accept transfer", exact: true }).click();
  await hidden(dialog);
  await shown(page.getByText(/This arrangement changed\. The latest details are now shown/));
  assert.equal(stale.item.case.primary_counselor.id, counselor.id);
  assert.equal(await page.getByRole("button", { name: "Accept transfer", exact: true }).count(), 0);
  assert.doesNotMatch(await page.locator("main").innerText(), /Private diagnostic/);
});
const expired = reviewFixture(receiver, "EXPIRED", { needs_new_arrangement: true, decision_reason: "REVIEW_WINDOW_ENDED" });
await check("expired-review-conceals-plans-and-offers-no-acceptance", transferPath, { handler: expired.handler }, async page => {
  await shown(page.getByText(/Expired — another arrangement is needed/));
  assert.equal(await page.getByRole("heading", { name: "Pending actions", exact: true }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Accept transfer", exact: true }).count(), 0);
});
const denied = reviewFixture(receiver); denied.denied = true;
await check("denied-review-has-safe-error-and-retry", transferPath, { handler: denied.handler }, async page => {
  await shown(page.locator("main").getByRole("alert").filter({ hasText: "This arrangement isn't available to your account." }));
  assert.doesNotMatch(await page.locator("main").innerText(), /Private diagnostic|Protected synthetic/);
  denied.denied = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByRole("button", { name: "Accept transfer", exact: true }));
});
for (const width of [320, 390]) {
  const phone = continuityFixture();
  await check(`phone-${width}-preparation-and-review`, preparePath, { handler: phone.handler, viewport: { width, height: 844 }, timezoneId: "America/New_York" }, async page => {
    await fillPreparation(page);
    await noHorizontalOverflow(page);
    await page.getByRole("button", { name: "Save transfer plan", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Transfer review", exact: true }));
    await noHorizontalOverflow(page);
    await screenshot(page, `transfer-phone-${width}`);
  });
}
await finish();
