import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { counselorWorld, counselorAppointment, workItem } from "./support/ux15-counselor-home-fixtures.mjs";
import { gssWorld } from "./support/ux15-gss-home-fixtures.mjs";
const h = await createBrowserHarness("home-composition");
const cases = [
  ["one-work-many-appointments", () => counselorWorld({ work: [workItem("ROUTINE_EVALUATION", 1)], appointments: [1,2,3,4,5].map(n => counselorAppointment(n)) })],
  ["many-work-empty-agenda", () => counselorWorld({ work: [1,2,3,4,5].map(n => workItem("ROUTINE_EVALUATION", n)), appointments: [] })],
  ["empty-work-and-agenda", () => counselorWorld({ work: [], appointments: [] })],
  ["absent-summary-and-announcements", () => { const w=counselorWorld(); w.summary.guidance=null; w.announcements=[]; return w; }],
  ["gss-single-work", () => gssWorld({ work: [workItem("GUIDANCE_MESSAGE_REPLY", 1)] })],
  ["student-empty", () => { const w=homeWorld({ items: [] }); w.announcements=[]; return w; }],
  ["head-without-oversight", () => counselorWorld({ head: true, capabilities: ["appointments.view_self"] })],
  ["unavailable-work", () => { const w=counselorWorld(); w.workStatus=503; return w; }],
];
for (const [name, makeWorld] of cases) for (const width of [320,1440]) {
  const state=makeWorld();
  await h.check(`${name}-${width}`, "/portal", state.options({ viewport:{width,height:1000} }), async page=>{
    await h.shown(page.locator("#overview-announcements-heading"));
    const work=page.locator('section[aria-labelledby="counselor-work-heading"]');
    if (await work.count()) {
      if (name==="unavailable-work") await h.shown(work.getByRole("alert"));
      else if (name==="empty-work-and-agenda") await h.shown(work.getByText("No items currently need attention in My work.", {exact:true}));
      else await h.shown(work.locator("li h3").first());
      const agenda=page.locator('section[aria-labelledby="counselor-agenda-heading"]');
      if (await agenda.count()) {
        const a=await work.boundingBox();const b=await agenda.boundingBox();
        assert.ok(a && b && b.y-a.y-a.height < 32, "Agenda follows work without a content-sized blank row");
      }
      for (const row of await work.locator("li").all()) {
        assert.ok(await row.locator("a").count() <= 1, "A task has one navigation action");
        assert.equal(await row.locator("a button, a a").count(), 0, "No nested interactive controls");
      }
    }
    if(name==="absent-summary-and-announcements") {
      assert.equal(await page.locator("#overview-summary-heading").count(),0);
      await h.shown(page.getByText("No current announcements.",{exact:true}));
    }
    if(name==="head-without-oversight") assert.equal(await page.locator("#head-guidance-oversight-heading").count(),0);
    await h.noHorizontalOverflow(page);
    await h.screenshot(page,name+"-"+width);
  });
}
if (process.env.COMPASS_UI_BROWSER !== "webkit") {
  await h.check("system-high-contrast-focus", "/portal", homeWorld().options(), async page => {
    await page.emulateMedia({ forcedColors: "active" });
    const link=page.getByRole("link", { name: "View all actions", exact: true });
    await h.shown(link); await page.keyboard.press("Tab"); await link.focus();
    const focus=await link.evaluate(node=>({ active:node===document.activeElement, style:getComputedStyle(node).outlineStyle, width:getComputedStyle(node).outlineWidth }));
    assert.equal(focus.active,true);assert.equal(focus.style,"solid");assert.equal(focus.width,"2px");
    await h.screenshot(page,"system-high-contrast-focus");
  });
}
await h.finish();
