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
// Backdrop photographs follow the headline rotation and its single Pause control.
const photoState = page => page.evaluate(() => [...document.querySelectorAll('[data-hero-photo]')]
  .map(img => ({ id: img.dataset.heroPhoto, opacity: getComputedStyle(img).opacity, priority: img.getAttribute('fetchpriority'), loading: img.getAttribute('loading'), src: img.getAttribute('src') })));
await h.check('hero-backdrop-crossfade-desktop', '/', { viewport: { width: 1440, height: 900 } }, async page => {
  await page.waitForLoadState('load');
  const [first] = await photoState(page);
  assert.equal(first.id, '0');
  assert.equal(first.priority, 'high', 'The first photo is the preloaded largest paint');
  assert.notEqual(first.loading, 'lazy');
  assert.match(first.src, /hero-gym-seminar\.webp/);
  assert.equal(await page.locator('link[rel="preload"][as="image"][imagesrcset*="hero-gym-seminar"]').count(), 1, 'The first photo is preloaded');
  // The second photo shows with the quote, only once it has loaded.
  await page.waitForFunction(() => {
    const second = document.querySelector('[data-hero-photo="1"]');
    return second && second.complete && getComputedStyle(second).opacity === '1';
  }, null, { timeout: 15000 });
  assert.equal(await page.locator('p.font-script').evaluate(el => getComputedStyle(el).opacity), '1');
  assert.match((await photoState(page))[1].src, /hero-classroom\.webp/);
  // Pause holds both the headline and the photo.
  await page.getByRole('button', { name: 'Pause headline animation' }).click();
  await page.mouse.move(5, 890);
  await page.waitForTimeout(8000);
  assert.equal((await photoState(page))[1].opacity, '1', 'Paused: the photo stays');
  assert.equal(await page.locator('p.font-script').evaluate(el => getComputedStyle(el).opacity), '1', 'Paused: the headline stays');
  await h.noHorizontalOverflow(page);
});
await h.check('hero-backdrop-single-photo-phone', '/', { viewport: { width: 390, height: 844 } }, async page => {
  await page.waitForLoadState('load');
  await page.waitForTimeout(1500);
  const photos = await photoState(page);
  assert.equal(photos.length, 1, 'Phones load one photo only');
  assert.equal(photos[0].opacity, '1');
});
await h.check('hero-backdrop-reduced-motion', '/', {
  viewport: { width: 1440, height: 900 },
  beforeNavigate: async ({ page }) => { await page.emulateMedia({ reducedMotion: 'reduce' }); },
}, async page => {
  await page.waitForLoadState('load');
  await page.waitForTimeout(9000);
  const photos = await photoState(page);
  assert.equal(photos[0].opacity, '1', 'Reduced motion keeps the first photo');
  assert.ok(photos.length === 1 || photos[1].opacity === '0', 'Reduced motion never fades to the second photo');
});
await h.finish();
