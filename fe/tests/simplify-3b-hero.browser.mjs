import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
const h = await createBrowserHarness('simplify-3b-hero');
for (const width of [320, 390, 768, 1024, 1440]) {
  await h.check(`hero-${width}`, '/', {
    viewport: { width, height: 900 },
  }, async page => {
    const quote = page.getByText('A place to talk and find support.', { exact: true });
    await page.waitForLoadState('load');
    await page.waitForFunction(() => {
      const element = document.querySelector('p.font-script');
      return element && getComputedStyle(element).opacity === '1';
    }, null, { timeout: 15000 });
    assert.equal(await quote.count(), 1);
    assert.equal(await quote.evaluate(el => getComputedStyle(el).opacity), '1');
    assert.match(await quote.evaluate(el => getComputedStyle(el).fontFamily), /Caveat/i);
    await h.screenshot(page, `hero-${width}`, page.locator("section.public-hero"));
    await page.addStyleTag({ content: 'html { font-size: 200%; }' });
    const fits = await quote.evaluate(el => {
      const rect = el.getBoundingClientRect();
      return rect.left >= -1 && rect.right <= document.documentElement.clientWidth + 1 && el.scrollWidth <= el.clientWidth + 1;
    });
    assert.ok(fits, 'Hero quote remains within the viewport at enlarged text');
  });
}
await h.finish();
