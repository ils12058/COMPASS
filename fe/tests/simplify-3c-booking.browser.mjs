import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { featureWorld } from './support/simplify-2c-feature-fixtures.mjs';

const h = await createBrowserHarness('simplify-3c-booking');
const phase = process.env.COMPASS_BOOKING_PHASE ?? 'after';
for (const width of [320, 390, 768, 1024, 1440]) {
  await h.check(`${phase}-${width}`, '/portal/appointments/book', featureWorld('booking').options({ viewport: { width, height: 1000 } }), async (page, { requests }) => {
    await h.shown(page.getByRole('heading', { name: 'Ways to get support' }));
    await h.shown(page.getByRole('heading', { name: '1. Choose a Service' }));
    await h.noHorizontalOverflow(page);
    await h.screenshot(page, `${phase}-${width}`);
    assert.equal(requests.filter(r => r.method !== 'GET').length, 0);
    if (phase === 'after') {
      const serviceHeading = page.getByRole('heading', { name: '1. Choose a Service' });
      const box = await serviceHeading.boundingBox();
      assert.ok(box.y < (width < 390 ? 700 : width < 1024 ? 600 : 500), `Service selection should appear early; y=${box.y}`);
      const art = page.locator('main img[src*="service-catalog-3d"]');
      assert.equal(await art.getAttribute('alt'), '');
      if (width < 768) assert.equal(await art.isVisible(), false);
      await page.getByRole('button', { name: /Counseling/ }).click();
      await h.shown(page.getByRole('heading', { name: '2. Choose delivery mode' }));
      assert.equal(await art.count(), 0, 'Artwork leaves the active booking steps');
      await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active', colorScheme: 'dark' });
      await page.addStyleTag({ content: 'html { font-size: 200%; }' });
      await h.noHorizontalOverflow(page);
    }
  });
}
await h.finish();
