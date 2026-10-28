// Local synthetic fixtures: illustrations never supply authorization or state.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { counselorWorld } from "./support/ux15-counselor-home-fixtures.mjs";
import { appointment } from "./support/ui-hierarchy-fixtures.mjs";
import { gssWorld } from "./support/ux15-gss-home-fixtures.mjs";
const h = await createBrowserHarness("simplify-2c");
const before = process.env.COMPASS_HOME_PHASE === "before";
const cases = [
  ["student", () => homeWorld(), "appointment-calendar-3d"],
  ["counselor", () => counselorWorld(), "guidance-messages-3d"],
  ["head", () => counselorWorld({ head:true }), "guidance-messages-3d"],
  ["gss", () => gssWorld(), "appointment-calendar-3d"],
  ["it", () => homeWorld({role:"IT_ADMIN"}), null],
];
async function checkImages(page, expected) {
  const images = page.locator('main img[src*="illustrations"]');
  assert.equal(await images.count(), before || !expected ? 0 : 1);
  if (before || !expected) return;
  const image = page.locator(`main img[src*="${expected}"]`);
  await h.shown(image);
  await page.waitForFunction(el => el.complete && el.naturalWidth > 0, await image.elementHandle());
  assert.equal(await image.getAttribute("alt"), "");
  assert.equal(await image.evaluate(el => el.tabIndex), -1);
  assert.equal(await image.locator('xpath=ancestor::a | ancestor::button').count(), 0);
  const bounds=await image.boundingBox();
  assert.ok(Math.abs(bounds.width / bounds.height - 1) < .01);
  for (const control of await page.locator("main h1, main h2, main a, main button, main input").all()) {
    if (!await control.isVisible()) continue;
    const box=await control.boundingBox();
    assert.ok(!(bounds.x < box.x+box.width-1 && bounds.x+bounds.width > box.x+1 && bounds.y < box.y+box.height-1 && bounds.y+bounds.height > box.y+1), "Artwork stays clear of headings and controls");
  }
}
for(const [name,makeWorld,asset] of cases) for(const width of [320,390,1024,1440]) {
  await h.check(`${name}-${width}`,"/portal",makeWorld().options({viewport:{width,height:1000}}),async page=>{
    await h.shown(page.locator("#overview-announcements-heading"));
    await checkImages(page,asset);
    const primary=page.locator("main h2").first();
    if(name !== "it") assert.match(await primary.innerText(),/Needs your attention|My work/);
    await h.noHorizontalOverflow(page);
    await h.screenshot(page,`${before?"before":"after"}-${name}-${width}`);
  });
}
for(const width of [320,390,1024,1440]) {
  const world=homeWorld(); const options=world.options({viewport:{width,height:1000}});
  const handler=options.handler;
  options.handler=async args=>args.pathname==="/api/v1/appointments/me"
    ? (await args.reply({items:[],page:1,page_size:20,has_next:false,ordering:"EARLIEST_START"}), true) : handler(args);
  await h.check(`appointments-empty-${width}`,"/portal/appointments/my?status=ALL",options,async page=>{
    await h.shown(page.getByText("No appointments are available.",{exact:true}));
    await checkImages(page,"appointment-calendar-3d");
    await h.noHorizontalOverflow(page);
    await h.screenshot(page,`${before?"before":"after"}-appointments-empty-${width}`);
  });
}
if (!before) {
  for (const [name, makeWorld] of [
    ["student", () => homeWorld({capabilities:["guidance_messages.view_self"]})],
    ["counselor", () => counselorWorld({capabilities:["appointments.view_self"]})],
    ["gss", () => gssWorld({capabilities:["guidance_messages.view"]})],
  ]) await h.check(`no-relevant-destination-${name}`, "/portal", makeWorld().options(), async page => {
    await h.shown(page.locator("#overview-announcements-heading"));
    assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
  });
  for (const mode of ["filtered","error","populated"]) {
    const options=homeWorld().options(); const handler=options.handler;
    options.handler=async args=>args.pathname==="/api/v1/appointments/me"
      ? (await args.reply(mode==="error" ? {error:{code:"synthetic_unavailable",message:"Synthetic"}} : {items:mode==="populated"?[appointment]:[],page:1,page_size:20,has_next:false,ordering:"EARLIEST_START"},mode==="error"?503:200),true):handler(args);
    await h.check(`appointments-${mode}`,`/portal/appointments/my?status=ALL${mode==="filtered"?"&search=no-match":""}`,options,async page=>{
      await h.shown(mode==="error"?page.getByRole("button",{name:"Retry",exact:true}):mode==="filtered"?page.getByText("No appointments match the selected filters.",{exact:true}):page.locator("tbody tr").first());
      assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
    });
  }
  {
    let release; const gate=new Promise(resolve=>{release=resolve;});
    const options=homeWorld().options(); const handler=options.handler;
    options.handler=async args=>args.pathname==="/api/v1/appointments/me" ? (await gate,await args.reply({items:[],page:1,page_size:20,has_next:false,ordering:"EARLIEST_START"}),true):handler(args);
    await h.check("appointments-loading", "/portal/appointments/my?status=ALL",options,async page=>{
      try {
        await h.shown(page.getByText("Loading appointments…",{exact:true}));
        assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
        release();
        await h.shown(page.getByText("No appointments are available.",{exact:true}));
        await checkImages(page,"appointment-calendar-3d");
      } finally {release();}
    });
  }
  await h.check("home-delayed-artwork", "/portal", homeWorld().options({beforeNavigate:async({context})=>{
    await context.route("**/_next/image?**", async route=>{await new Promise(resolve=>setTimeout(resolve,1500));await route.continue();});
  }}),async page=>{
    const primary=page.locator('#overview-attention-heading');await h.shown(primary);
    const title=await primary.boundingBox();
    await checkImages(page,"appointment-calendar-3d");
    const loaded=await primary.boundingBox();
    assert.ok(Math.abs(title.y-loaded.y)<=1,"Artwork loading never shifts primary work");
  });
  for(const width of [320,390,1024,1440]) await h.check(`home-enlarged-${width}`,"/portal",homeWorld().options({viewport:{width,height:1000}}),async page=>{
    await h.shown(page.locator('#student-home-services-heading'));
    await page.addStyleTag({content:"html { font-size:200%; }"});
    await h.noHorizontalOverflow(page);
    await h.shown(page.getByRole("link",{name:"Book appointment",exact:true}));
  });
  await h.check("home-image-failure", "/portal",homeWorld().options({beforeNavigate:async({context})=>{
    await context.route("**/_next/image?**",route=>route.abort("failed"));
  }}),async page=>{
    await h.shown(page.getByRole("link",{name:"Book appointment",exact:true}));
    await h.shown(page.getByRole("link",{name:"View appointments",exact:true}));
    await h.noHorizontalOverflow(page);
  });
}
await h.finish();
