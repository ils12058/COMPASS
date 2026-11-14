import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { counselor } from "./support/counseling-cases-fixtures.mjs";
import { continuityFixture, continuityAccount, transferPath, head, office, receiver, handoffSections } from "./support/counseling-continuity-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish, settleFetches } = await createBrowserHarness("counseling-handoffs");
const handoffPath = `${transferPath}/handoff`;
function fixture(person = counselor, overrides = {}) {
  return continuityFixture({ account: continuityAccount(person, person.id === office.id ? "GUIDANCE_OFFICE_ASSISTANT" : "COUNSELOR"), item: { state: "AUTHORIZED", waiting_for: receiver.display_name, review_expires_at: "2099-01-15T00:00:00Z", authorization_route: "INDEPENDENT_HEAD", ...overrides } });
}
async function completion(page, action, title) {
  await page.getByRole("button", { name: action, exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: `${action}?`, exact: true });
  await shown(dialog);
  await dialog.getByRole("button", { name: action, exact: true }).click();
  const result = page.getByRole("alertdialog", { name: title, exact: true });
  await shown(result.getByRole("button", {name:"Done",exact:true}));
  await result.getByRole("button", {name:"Done",exact:true}).click();
  await hidden(result);
}

const draft = fixture(counselor, { state: "PREPARED", handoff: null });
await check("draft-submission-is-separate-from-transfer-and-immutable", handoffPath, { handler: draft.handler }, async page => {
  await page.getByLabel("Current concern and handoff purpose", {exact:true}).fill("Synthetic draft continuation");
  await page.getByLabel("What the receiver should review or do next", {exact:true}).fill("Review assigned work");
  assert.equal(await page.getByRole("button", {name:"Submit handoff",exact:true}).isDisabled(), true);
  await page.getByRole("button", {name:"Save handoff draft",exact:true}).click();
  await shown(page.getByText("Handoff draft saved.", {exact:true}));
  await completion(page, "Submit handoff", "Handoff submitted");
  await shown(page.getByRole("heading", {name:"Submitted handoff",exact:true}));
  await page.waitForFunction(() => document.activeElement?.id === "case-handoff-page-heading");
  assert.equal(draft.item.state, "PREPARED");
  assert.equal(draft.item.case.primary_counselor.id, counselor.id);
  assert.equal(await page.getByLabel("Current concern and handoff purpose", {exact:true}).count(),0);
  assert.equal(await page.getByRole("button",{name:"Accept transfer",exact:true}).count(),0);
  await screenshot(page,"submitted-immutable-handoff");
});

const receiving = fixture(receiver);
await check("receiver-opens-with-receipt-and-no-case-management-or-source-content", transferPath, {handler:receiving.handler}, async page => {
  await page.getByRole("link",{name:"Open handoff",exact:true}).click();
  await shown(page.getByText(handoffSections.context_and_purpose,{exact:true}));
  assert.ok(receiving.item.handoff.received_at);
  assert.equal(receiving.item.case.primary_counselor.id,counselor.id);
  assert.equal(await page.getByRole("button",{name:"Save handoff draft",exact:true}).count(),0);
  assert.equal(await page.getByRole("button",{name:"Add addendum",exact:true}).count(),0);
  assert.doesNotMatch(await page.locator("main").innerText(),/Protected synthetic action/);
});
const headOnly = fixture(head, {state:"PREPARED",waiting_for:"Head approval"});
await check("head-authorizes-without-handoff-narrative",transferPath,{handler:headOnly.handler},async page=>{
  await shown(page.getByRole("button",{name:"Authorize transfer",exact:true}));
  assert.equal(await page.getByRole("link",{name:"Open handoff",exact:true}).count(),0);
  assert.doesNotMatch(await page.locator("main").innerText(),/Synthetic confidential context|Protected synthetic action/);
});
const missing = fixture(receiver,{handoff:null,handoff_exception:{reason:"OWNER_UNAVAILABLE",recorded_by:head,recorded_at:"2026-11-13T02:00:00Z"}});
await check("receiver-sees-unavailable-warning-and-can-explicitly-accept",transferPath,{handler:missing.handler},async page=>{
  await shown(page.getByText(/No handoff is available\./));
  await shown(page.getByRole("button",{name:"Accept transfer",exact:true}));
  assert.equal(await page.getByRole("link",{name:"Open handoff",exact:true}).count(),0);
});
const officeRequest = fixture(head,{state:"PREPARED",waiting_for:null,handoff:null,prepared_by:office,office_prepared:true});
await check("head-records-unavailable-exception-before-office-submission",transferPath,{handler:officeRequest.handler},async page=>{
  await shown(page.getByRole("button",{name:"Record handoff unavailable",exact:true}));
  assert.equal(await page.getByRole("button",{name:"Authorize transfer",exact:true}).count(),0);
  await page.getByRole("button",{name:"Record handoff unavailable",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Record handoff unavailable?",exact:true});
  await dialog.getByLabel("Why is the handoff unavailable?",{exact:true}).selectOption("OWNER_UNAVAILABLE");
  await dialog.getByRole("button",{name:"Record exception",exact:true}).click();
  await shown(page.getByRole("alertdialog",{name:"Handoff exception recorded",exact:true}));
  await page.getByRole("button",{name:"Done",exact:true}).click();
  await page.waitForFunction(() => document.activeElement?.id === "transfer-handoff-heading");
  assert.equal(officeRequest.item.handoff_exception.recorded_by.id,head.id);
  assert.equal(officeRequest.item.case.primary_counselor.id,counselor.id);
});
const expired=fixture(receiver,{state:"EXPIRED",needs_new_arrangement:true});
await check("expired-review-never-requests-the-narrative",handoffPath,{handler:expired.handler},async page=>{
  await shown(page.getByText(/This protected handoff is unavailable/));
  assert.equal(expired.operations.filter(operation=>operation.pathname.includes("/handoffs/")).length,0);
});
const protectedText=fixture(receiver);
await check("offline-clears-body-and-requires-explicit-recheck",handoffPath,{handler:protectedText.handler},async page=>{
  await shown(page.getByText(handoffSections.context_and_purpose,{exact:true}));
  await page.evaluate(()=>window.dispatchEvent(new Event("offline")));
  await shown(page.getByRole("button",{name:"Check handoff access",exact:true}));
  await hidden(page.getByText(handoffSections.context_and_purpose,{exact:true}));
  await page.getByRole("button",{name:"Check handoff access",exact:true}).click();
  await shown(page.getByText(handoffSections.context_and_purpose,{exact:true}));
});
const staleDraft=fixture(counselor,{state:"PREPARED",handoff:{id:"c3000000-0000-4000-8000-000000000010",version:1,state:"DRAFT",author:counselor,submitted_at:null,received_at:null}});
staleDraft.handoffBody.state="DRAFT";
await check("draft-conflict-keeps-input-and-requires-current-version-review",handoffPath,{handler:staleDraft.handler},async page=>{
  const field=page.getByLabel("Current concern and handoff purpose",{exact:true});
  await shown(field); await field.fill("Unsaved protected draft");
  staleDraft.item.version++;
  await page.getByRole("button",{name:"Save handoff draft",exact:true}).click();
  await shown(page.getByRole("button",{name:"Use current saved version",exact:true}));
  assert.equal(await field.inputValue(),"Unsaved protected draft");
  assert.equal(await page.getByRole("button",{name:"Save handoff draft",exact:true}).isDisabled(),true);
  await page.getByRole("button",{name:"Use current saved version",exact:true}).click();
  await settleFetches(page);
  assert.equal(await field.inputValue(),"Unsaved protected draft");
});
const accepted=fixture(receiver,{state:"ACCEPTED"});
accepted.item.case.primary_counselor=receiver;
await check("accepted-owner-adds-attributed-information-without-editing-snapshot",handoffPath,{handler:accepted.handler},async page=>{
  await shown(page.getByLabel("Attributed addendum",{exact:true}));
  await page.getByLabel("Attributed addendum",{exact:true}).fill("Synthetic accepted-owner update");
  await page.getByRole("button",{name:"Add addendum",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Add handoff addendum?",exact:true});
  await dialog.getByRole("button",{name:"Add addendum",exact:true}).click();
  await shown(page.getByRole("alertdialog",{name:"Handoff addendum recorded",exact:true}));
  await page.getByRole("button",{name:"Done",exact:true}).click();
  await shown(page.getByText("Synthetic accepted-owner update",{exact:true}));
  assert.equal(accepted.handoffBody.sections.context_and_purpose,handoffSections.context_and_purpose);
  assert.equal(accepted.handoffBody.addenda[0].author.id,receiver.id);
  assert.equal(accepted.item.state,"ACCEPTED");
});
const phone=fixture(receiver);
await check("phone-320-handoff-and-readonly-work",handoffPath,{handler:phone.handler,viewport:{width:320,height:844},timezoneId:"America/New_York"},async page=>{
  await shown(page.getByText(handoffSections.context_and_purpose,{exact:true}));
  await noHorizontalOverflow(page); await screenshot(page,"handoff-phone-320");
});
await finish();
