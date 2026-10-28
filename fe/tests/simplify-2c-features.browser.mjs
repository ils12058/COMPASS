import assert from 'node:assert/strict';
import {createBrowserHarness} from './support/browser-harness.mjs';
import {tracerFixture} from './support/ux15-tracer-fixtures.mjs';
import {studentWorld, messagesAccount, sessionFor, threadIds} from './support/guidance-messages-fixtures.mjs';
import {featureCases,featureWorld} from './support/simplify-2c-feature-fixtures.mjs';
const h=await createBrowserHarness('simplify-2c-features');
const before=process.env.COMPASS_HOME_PHASE==='before';
for(const [name,path,text,asset] of featureCases) for(const width of [320,390,1024,1440]) {
  await h.check(`${name}-${width}`,path,featureWorld(name).options({viewport:{width,height:1000}}),async(page,{requests})=>{
    await h.shown(page.getByText(text,{exact:true}).first());
    const images=page.locator('main img[src*="illustrations"]');
    if(!before) await images.first().waitFor({state:'attached'});
    assert.equal(await images.count(),before?0:1);
    if(!before) {
      const image=page.locator(`main img[src*="${asset}"]`);
      assert.equal(await image.getAttribute('alt'),'');
      assert.equal(await image.evaluate(el=>el.tabIndex),-1);
      if(await image.isVisible()) {
        await page.waitForFunction(el=>el.complete&&el.naturalWidth>0,await image.elementHandle());
        const a=await image.boundingBox();
        assert.ok(Math.abs(a.width/a.height-1)<.01);
        for(const control of await page.locator('main h1,main h2,main input,main button,main a').all()) {
          if(!await control.isVisible()) continue;
          const b=await control.boundingBox();
          assert.ok(!(a.x<b.x+b.width-1&&a.x+a.width>b.x+1&&a.y<b.y+b.height-1&&a.y+a.height>b.y+1),'Artwork avoids content and controls');
        }
      }
    }
    await h.noHorizontalOverflow(page);
    assert.equal(requests.filter(r=>r.method!=='GET').length,0,'Introduction creates no records');
    await h.screenshot(page,`${before?'before':'after'}-${name}-${width}`);
    if(!before) {await page.addStyleTag({content:'html { font-size:200%; }'});await h.noHorizontalOverflow(page);}
  });
}
if(!before) {
  for(const [name,path] of featureCases) await h.check(`${name}-error`,path,featureWorld(name,'error').options(),async page=>{
    await h.shown(page.locator('main [role="alert"]').first());
    assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
  });
  for(const name of ['exit','good-moral']) {
    const entry=featureCases.find(row=>row[0]===name);
    await h.check(`${name}-blocked`,entry[1],featureWorld(name,'blocked').options(),async page=>{
      await h.shown(name==='exit'?page.getByRole('link',{name:'Open Individual Inventory',exact:true}):page.getByText("Submit this year's Individual Inventory to request F4.",{exact:true}));
      assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
    });
  }
  const tracer=tracerFixture();
  await h.check('tracer-private-draft','/portal/graduate-tracer',{handler:tracer.handler},async page=>{
    await h.shown(page.getByText('Your response',{exact:true}));
    assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
  });
  const backend=studentWorld();
  await h.check('messages-private-conversation',`/portal/messages/${threadIds.office}`,{
    handler:backend.handler,overrides:{'/api/v1/auth/session':sessionFor(messagesAccount('STUDENT'))},
  },async page=>{
    await h.shown(page.getByRole('textbox',{name:/^Message/}));
    assert.equal(await page.locator('main img[src*="illustrations"]').count(),0);
  });
}
await h.finish();
