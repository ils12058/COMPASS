import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { messagesAccount, sessionFor } from './support/guidance-messages-fixtures.mjs';
const h = await createBrowserHarness('simplify-3b-public-shell');
for (const audience of ['public', 'account']) for (const width of [320, 390, 768, 1024, 1440]) for (const enlarged of [false, true]) {
  const account = messagesAccount('STUDENT', { first_name: 'Alex', last_name: 'Example' });
  const handler = async ({ pathname, reply }) => {
    if (pathname === '/api/v1/auth/session') { await reply(audience === 'public' ? { authenticated: false } : sessionFor(account)); return true; }
    if (pathname === '/api/v1/privacy/public-notices') { await reply({ items: [], page: 1, page_size: 10, has_next: false }); return true; }
    return false;
  };
  await h.check(`${audience}-${width}-${enlarged ? '200' : '100'}`, '/privacy', { handler, viewport: { width, height: 900 } }, async page => {
    await h.shown(page.getByRole('heading', { name: 'Privacy', exact: true }));
    if (audience === 'account') await h.shown(page.getByRole('button', { name: /Open user menu/ }));
    if (enlarged) await page.addStyleTag({ content: 'html { font-size: 200%; }' });
    await h.noHorizontalOverflow(page);
    if (audience === 'account') {
      const accountMenu = page.getByRole('button', { name: /Open user menu/ });
      await accountMenu.click();
      await h.shown(page.getByRole('menu').getByRole('menuitem', { name: 'Open COMPASS' }));
      await page.keyboard.press('Escape');
      await page.waitForFunction(el => document.activeElement === el, await accountMenu.elementHandle());
    }
    const accessibility = page.getByRole('button', { name: 'Accessibility settings' });
    await accessibility.click();
    await h.shown(page.getByRole('dialog', { name: 'Accessibility' }));
    await page.keyboard.press('Escape');
    await page.waitForFunction(el => document.activeElement === el, await accessibility.elementHandle());
    const brand = page.getByRole('link', { name: 'COMPASS home' });
    await h.shown(brand);
    const menu = page.getByRole('button', { name: 'Open navigation menu' });
    if (await menu.isVisible()) {
      await menu.focus();
      await page.keyboard.press('Enter');
      const nav = page.getByRole('navigation', { name: 'Mobile public navigation' });
      await h.shown(nav);
      const r = await nav.boundingBox();
      assert.ok(r.x >= -1 && r.x + r.width <= width + 1, 'Open menu fits viewport');
      await page.keyboard.press('Escape');
      await page.waitForFunction(el => document.activeElement === el, await menu.elementHandle());
    } else {
      await h.shown(page.getByRole('navigation', { name: 'Public navigation' }));
    }
    await h.screenshot(page, `${audience}-${width}-${enlarged ? '200' : '100'}`);
  });
}
await h.check('public-maintenance-accessibility', '/privacy', { viewport: { width: 320, height: 900 }, overrides: {
  '/api/v1/platform/status': { status: 'maintenance_active', message: null, starts_at: null, ends_at: null },
} }, async page => {
  await h.shown(page.getByRole('heading', { name: 'COMPASS is temporarily unavailable' }));
  await page.addStyleTag({ content: 'html { font-size: 200%; }' });
  await h.noHorizontalOverflow(page);
  await page.getByRole('button', { name: 'Accessibility settings' }).click();
  await h.shown(page.getByRole('dialog', { name: 'Accessibility' }));
  await page.keyboard.press('Escape');
});
await h.finish();
