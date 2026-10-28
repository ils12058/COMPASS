import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { homeWorld } from './support/ux15-home-fixtures.mjs';
const h = await createBrowserHarness('simplify-3b-caveat-accessibility');
for (const role of ['STUDENT', 'COUNSELOR']) {
  const world = homeWorld({ role });
  await h.check(`${role}-forced-colors`, '/portal', world.options({ viewport: { width: 390, height: 844 }, beforeNavigate: async ({ page }) => page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' }) }), async page => {
    const heading = page.getByRole('heading', { level: 1 });
    await h.shown(heading);
    await page.addStyleTag({ content: 'html { font-size: 200%; }' });
    await h.noHorizontalOverflow(page);
    assert.equal(await page.evaluate(() => matchMedia('(forced-colors: active)').matches && matchMedia('(prefers-reduced-motion: reduce)').matches), true);
    assert.ok((await heading.innerText()).length > 0);
  });
}
await h.check('hero-reduced-motion', '/', { viewport: { width: 390, height: 844 }, beforeNavigate: async ({ page }) => page.emulateMedia({ reducedMotion: 'reduce' }) }, async page => {
  await h.shown(page.getByRole('button', { name: 'Play headline animation' }));
  const quote = page.getByText('A place to talk and find support.', { exact: true });
  assert.equal(await quote.evaluate(el => getComputedStyle(el).opacity), '0');
});
await h.finish();
