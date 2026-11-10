// Before/after evidence against a locally built app. All responses are synthetic.
import { join } from 'node:path';
import { createBrowserHarness } from './browser-harness.mjs';
import { navigationWorld, profiles } from './f2-navigation-fixtures.mjs';
const h = await createBrowserHarness('f2-navigation-capture');
for (const [name, profile] of Object.entries(profiles)) for (const width of [1440, 390]) {
  const state = navigationWorld(profile);
  await h.check(`${name}-${width}`, '/portal', state.options({ viewport: {width, height: width === 390 ? 844 : 1000}, mobile: width === 390 }), async page => {
    await h.shown(page.locator('main h1'));
    await h.settleFetches(page);
    await h.screenshot(page, `${name}-${width}-home`);
    if (width === 390) await page.getByRole('button', { name: 'Open portal navigation' }).click();
    const nav = page.getByRole('navigation', { name: 'Portal navigation' });
    await h.shown(nav);
    if (width === 390) await page.getByRole('dialog', { name: 'Portal navigation' }).evaluate(element=>Promise.all(element.getAnimations({subtree:true}).map(animation=>animation.finished.catch(()=>{}))));
    await page.screenshot({path:join(h.artifacts, `${name}-${width}-menu.png`)});
    const more = nav.getByRole('button', { name: /^(More|Administration)/ });
    if (await more.count()) {
      await more.click();
      await page.screenshot({path:join(h.artifacts, `${name}-${width}-more.png`)});
    }
    await h.noHorizontalOverflow(page);
  });
}
await h.finish();
