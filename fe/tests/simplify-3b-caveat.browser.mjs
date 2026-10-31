import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { homeWorld } from './support/ux15-home-fixtures.mjs';
const h = await createBrowserHarness('simplify-3b-caveat');
const phase = process.env.COMPASS_3B_PHASE ?? 'after';
for (const role of ['STUDENT', 'COUNSELOR', 'GUIDANCE_SERVICES_STAFF']) {
  for (const width of role === 'STUDENT' ? [320, 390, 768, 1024, 1440] : [390, 1440]) {
    const world = homeWorld({ role });
    await h.check(`${phase}-${role}-${width}`, '/portal', world.options({ viewport: { width, height: 900 } }), async page => {
      const title = page.getByRole('heading', { level: 1 });
      await h.shown(title);
      await page.evaluate(() => document.fonts.ready);
      assert.match(await title.innerText(), role === 'GUIDANCE_SERVICES_STAFF' ? /Guidance Services Home/ : /Good (?:morning|afternoon|evening), Alex/);
      if (phase === 'after') {
        const face = await title.locator(role === 'STUDENT' ? 'span' : ':scope').first().evaluate(el => getComputedStyle(el).fontFamily);
        if (role === 'STUDENT') assert.match(face, /Caveat/i);
        else assert.doesNotMatch(face, /Caveat/i);
      }
      await h.noHorizontalOverflow(page);
      await h.screenshot(page, `${phase}-${role}-${width}`);
      await page.addStyleTag({ content: 'html { font-size: 200%; }' });
      await h.noHorizontalOverflow(page);
    });
  }
}
const long = homeWorld();
long.account.first_name = 'A'.repeat(48);
await h.check(`${phase}-long-name-320`, '/portal', long.options({ viewport: { width: 320, height: 900 } }), async page => {
  await h.shown(page.getByRole('heading', { level: 1 }));
  await h.noHorizontalOverflow(page);
  await page.addStyleTag({ content: 'html { font-size: 200%; }' });
  await h.noHorizontalOverflow(page);
});
await h.finish();
