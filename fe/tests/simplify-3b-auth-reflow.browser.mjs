// Synthetic signed-out render audit; this does not establish real authentication or UAT.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';

const h = await createBrowserHarness('simplify-3b-auth-reflow');
const signedOut = async ({ pathname, reply }) => {
  if (pathname === '/api/v1/auth/session') {
    await reply({ error: { code: 'not_authenticated', message: 'Sign in required.' } }, 401);
    return true;
  }
  return false;
};
for (const route of ['/login', '/password']) {
  for (const width of [320, 390, 768, 1024, 1440]) {
    for (const scale of [100, 200]) {
      await h.check(`${route} ${width}px ${scale}%`, route, {
        viewport: { width, height: 844 }, handler: signedOut,
      }, async page => {
        await h.shown(page.getByRole('heading', { level: 1 }));
        await page.evaluate(size => { document.documentElement.style.fontSize = `${size}%`; }, scale);
        await h.noHorizontalOverflow(page);
        const problems = await page.locator('main input, main button, main a').evaluateAll(elements => elements.filter(el => {
          const r = el.getBoundingClientRect();
          return r.width && (r.left < -1 || r.right > document.documentElement.clientWidth + 1);
        }).map(el => ({ text: el.textContent, name: el.getAttribute('aria-label') })));
        assert.deepEqual(problems, [], 'interactive controls fit the viewport');
        const clippedText = await page.locator('main h1, main a[aria-label="COMPASS public site"]').evaluateAll(elements => {
          const outside = [];
          for (const element of elements) {
            const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
              const range = document.createRange();
              range.selectNodeContents(walker.currentNode);
              for (const rect of range.getClientRects()) {
                if (rect.width && (rect.left < -1 || rect.right > document.documentElement.clientWidth + 1)) outside.push(walker.currentNode.textContent);
              }
            }
          }
          return outside;
        });
        assert.deepEqual(clippedText, [], 'heading and brand text fit the viewport');
        const accessibility = page.getByRole('button', { name: 'Accessibility settings' });
        await accessibility.click();
        await h.shown(page.getByRole('dialog', { name: 'Accessibility' }));
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Accessibility settings');
        if (width === 320 || width === 1440) await h.screenshot(page, `${route.slice(1)}-${width}-${scale}`);
      });
    }
  }
}
await h.check('mandatory setup QR at 320px 200%', '/login', {
  viewport: { width: 320, height: 844 },
  handler: async ({ pathname, method, reply }) => {
    if (pathname === '/api/v1/auth/login' && method === 'POST') {
      await reply({ error: { code: 'mfa_setup_required', message: 'Authenticator setup required.' } }, 403);
      return true;
    }
    if (pathname === '/api/v1/auth/mfa/totp/bootstrap/setup' && method === 'POST') {
      await reply({ provisioning_uri: 'otpauth://totp/Synthetic?secret=JBSWY3DPEHPK3PXP&issuer=Synthetic' });
      return true;
    }
    return signedOut({ pathname, reply });
  },
}, async page => {
  await h.shown(page.getByRole('heading', { name: 'Sign in' }));
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await page.getByLabel('Email', { exact: true }).fill('synthetic@example.test');
  await page.getByLabel('Password', { exact: true }).fill('synthetic-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await h.shown(page.getByRole('heading', { name: 'Set up an authenticator app' }));
  await page.getByRole('button', { name: 'Start authenticator setup' }).click();
  await h.shown(page.getByLabel('Authenticator code', { exact: true }));
  await h.noHorizontalOverflow(page);
  const qr = await page.locator('svg[role="img"]').boundingBox();
  assert.ok(qr && qr.x >= 0 && qr.x + qr.width <= 321, 'setup QR fits the viewport');
});
await h.finish();
