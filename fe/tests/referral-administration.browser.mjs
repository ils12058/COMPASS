// Synthetic FAC-4 state, policy, stale/uncertain and accessibility fixtures.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
const { check, finish, shown, artifacts } = await createBrowserHarness("referral-administration");
const id = "f4000000-0000-4000-8000-000000000001";
const source = "/api/v1/referrals/" + id;
const path = "/portal/referrals/" + id;
const facultyPath = "/portal/faculty/referrals";
const actor = { id: "f4000000-0000-4000-8000-000000000002", display_name: "Synthetic GCO actor" };
const faculty = { ...user("STUDENT"), role: "FACULTY", capabilities: ["referrals.submit_self", "referrals.view_submitted_self"], designations: [], faculty_affiliation: { active: true, college_name: "CAS", campus_name: "Main", resource_version: 1 } };
const gco = { ...user(), capabilities: [...user().capabilities, "referrals.view", "referrals.manage"] };
const ref = { id, reference_code: "REF-2026-000004", submission_channel: "FACULTY_PORTAL", submitted_at: "2026-11-01T01:00:00Z", administrative_state: "SUBMITTED", student: { id: actor.id, display_name: "Synthetic Student", institutional_id: "SYNTHETIC-1" }, student_name_snapshot: "Synthetic Student", course_year_block_snapshot: "BSIS", form_revision: { id: actor.id, official_code: "UCN-OP-GCO-01F3", official_revision: "1", internal_schema_version: 1 }, referred_on: "2026-11-01", received_at: null, created_at: "2026-11-01T01:00:00Z", recorded_by: null, referrer_name: "Synthetic Faculty", reason: "Synthetic confidential GCO source", status_note: "", voided_at: null, voided_by: null, void_reason: "", actions: [] };
const stages = ["SUBMITTED", "RECEIVED_BY_GCO", "ADMINISTRATIVELY_CLOSED"];
function fixture(options = {}) {
  const state = { version: 1, writes: 0, unavailable: false, ...options };
  const facts = () => ({ referral_id: id, version: state.version, state: stages[state.version-1], submitted_at: ref.submitted_at, submitted_by: { ...actor, display_name: "Synthetic Faculty" }, faculty_home_college: "CAS", student_college_at_submission: "CCMS", received_at: state.version >= 2 ? "2026-11-01T02:00:00Z" : null, acknowledged_by: state.version >= 2 ? actor : null, closed_at: state.version === 3 ? "2026-11-01T03:00:00Z" : null, closed_by: state.version === 3 ? actor : null, can_acknowledge: !state.unavailable && state.version === 1, can_close: !state.unavailable && state.version === 2, valid_until: "2099-01-01T00:00:00Z" });
  const own = () => ({ id, reference_code: ref.reference_code, submitted_at: ref.submitted_at, student: { display_name: ref.student_name_snapshot }, state: stages[state.version-1], received_at: facts().received_at, closed_at: facts().closed_at });
  return { state, handler: async ({ pathname, reply, route, request }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(state.faculty ? faculty : gco)); return true; }
    if (pathname === source + "/administration") {
      if (state.readError) { await reply({ error: { code: "referral_not_found", message: "Synthetic" } }, state.readError); return true; }
      if (state.delay) await new Promise(r => setTimeout(r, 500));
      await reply(facts()); return true;
    }
    if (pathname === source + "/acknowledgment" || pathname === source + "/administrative-closure") {
      state.writes++;
      const body = request.postDataJSON();
      assert.equal(body.expected_version, state.version);
      if (pathname.endsWith("administrative-closure")) assert.equal(body.obligations_reviewed, true);
      state.version++;
      if (state.writeError === "lost") { await route.abort("failed"); return true; }
      if (state.writeError) { await reply({ error: { code: "referral_administration_conflict", message: "Synthetic" } }, state.writeError); return true; }
      await reply(facts()); return true;
    }
    if (pathname === source) { await reply({ ...ref, received_at: facts().received_at, administrative_state: facts().state }); return true; }
    if (pathname === "/api/v1/referrals") { await reply({ items: [ref], page: 1, page_size: 20, has_next: false, ordering: "REFERRED_DESC", filter_options: { form_revisions: [] } }); return true; }
    if (pathname === "/api/v1/faculty/referrals/availability") { await reply({ can_confirm_student: true, can_submit_referral: true, can_view_submissions: true, valid_until: "2099-01-01T00:00:00Z" }); return true; }
    if (pathname === "/api/v1/faculty/referrals/" + id) { await reply(own()); return true; }
    if (pathname === "/api/v1/faculty/referrals") { await reply({ items: [own()], page: 1, page_size: 20, has_next: false }); return true; }
    return false;
  } };
}
const dialog = page => page.getByRole("alertdialog");
const confirm = (page,name) => dialog(page).getByRole("button", { name, exact: true });
for (const width of [320, 390, 768, 1024, 1440]) for (const scale of [100, 200]) {
  const f = fixture({ version: 2 });
  await check(`gco-review-${width}-${scale}`, path, { handler: f.handler, viewport: { width, height: 1000 } }, async page => {
    await page.emulateMedia({ colorScheme: scale === 200 ? "dark" : "light", reducedMotion: "reduce" });
    await page.evaluate(scale => { document.documentElement.style.fontSize = `${scale}%`; }, scale);
    await page.getByRole("button", { name: "Close administratively", exact: true }).click();
    await shown(dialog(page));
    assert.equal(await confirm(page,"Close administratively").isDisabled(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1), false);
    await page.screenshot({ path: join(artifacts, `closure-review-${width}-${scale}.png`), fullPage: false });
    await page.getByLabel("I reviewed the required obligations").check();
    await confirm(page,"Close administratively").click();
    await shown(page.getByText("Referral closed administratively.", { exact: true }));
    assert.equal(f.state.writes,1);
  });
}
for (const version of [1,2,3]) for (const entry of ["/portal",facultyPath,`${facultyPath}/${id}`]) for (const width of [320,390,768,1024,1440]) for (const scale of [100,200]) {
  const f=fixture({faculty:true,version});
  await check(`faculty-stage-${version}-${entry.split("/").at(-1)}-${width}-${scale}`,entry,{handler:f.handler,viewport:{width,height:1000}},async(page,observed)=>{
    await page.emulateMedia({ colorScheme: scale === 200 ? "dark" : "light", reducedMotion: "reduce" });
    await page.evaluate(scale => { document.documentElement.style.fontSize = `${scale}%`; }, scale);
    const labels=["Submitted","Received by GCO","Administratively Closed"];
    await shown(page.getByText(labels[version-1],{exact:true}).last());
    assert.equal(await page.getByText("Synthetic GCO actor",{exact:true}).count(),0);
    assert.equal(observed.requests.some(r=>r.pathname.startsWith("/api/v1/referrals")),false);
    if(entry.endsWith(id)) {
      assert.equal(await page.getByText("Received by GCO · Philippine Time",{exact:true}).count(),version>=2?1:0);
      assert.equal(await page.getByText("Administratively closed · Philippine Time",{exact:true}).count(),version===3?1:0);
      if(version===3) { await page.getByRole("button",{name:/Help/}).click(); await shown(page.getByText(/does not establish that Counseling/)); }
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1),false);
    if ([320,1440].includes(width) && scale === 200) await page.screenshot({path:join(artifacts,`faculty-${version}-${entry.split("/").at(-1)}-${width}-${scale}.png`),fullPage:true});
  });
}
for (const version of [1,2]) {
  await check(`policy-unavailable-${version}`,path,{handler:fixture({unavailable:true,version}).handler},async page=>{
    await shown(page.getByText("Administrative action is unavailable. Current policy and record eligibility must be confirmed.",{exact:true}));
    assert.equal(await page.getByRole("button",{name:/^(Acknowledge receipt|Close administratively)$/}).count(),0);
  });
}
for (const error of [409,403,"lost"]) {
  const f=fixture({writeError:error});
  await check(`mutation-reconcile-${error}`,path,{handler:f.handler},async page=>{
    await page.getByRole("button",{name:"Acknowledge receipt",exact:true}).click();
    await confirm(page,"Acknowledge receipt").click();
    await shown(dialog(page).getByRole("alert"));
    assert.equal(await confirm(page,"Acknowledge receipt").isDisabled(),true);
    assert.equal(f.state.writes,1);
    await dialog(page).getByRole("button",{name:"Cancel",exact:true}).click();
    await shown(page.getByText("Received by GCO",{exact:true}));
    assert.equal(await page.getByText("Receipt acknowledged.",{exact:true}).count(),0);
    await page.getByRole("button",{name:"Refresh intake record",exact:true}).click();
    await shown(page.getByRole("button",{name:"Close administratively",exact:true}));
    assert.equal(f.state.writes,1);
  });
}
await check("intake-error-disables-actions",path,{handler:fixture({readError:403}).handler},async page=>{
  await shown(page.getByText("Intake details could not be refreshed. Actions are unavailable.",{exact:true}));
  assert.equal(await page.getByRole("button",{name:"Acknowledge receipt",exact:true}).count(),0);
});
await check("keyboard-explicit-review-cancel",path,{handler:fixture().handler},async page=>{
  const button=page.getByRole("button",{name:"Acknowledge receipt",exact:true});
  await shown(button); await button.focus(); await page.keyboard.press("Enter"); await shown(dialog(page));
  assert.equal(await page.locator('[role="alertdialog"]').getAttribute("aria-describedby") !== null,true);
  await page.keyboard.press("Escape"); await button.waitFor({state:"visible"});
  assert.equal(await button.evaluate(e=>e===document.activeElement),true);
});
await check("origin-filter-is-server-side", "/portal/referrals?submission_channel=FACULTY_PORTAL", { handler: fixture().handler }, async(page,observed)=>{
  await shown(page.getByRole("link",{name:ref.reference_code,exact:true}).last());
  assert.ok(observed.requests.some(r=>r.pathname==="/api/v1/referrals" && new URLSearchParams(r.search).get("submission_channel")==="FACULTY_PORTAL"));
});
await finish();
