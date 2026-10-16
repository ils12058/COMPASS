// The backend owns allowlisting; these safe API fixtures exercise the resulting account UI.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
const engine = process.env.COMPASS_UI_BROWSER ?? 'chromium';
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`security-activity-${engine}`);
const item = (type, title, index) => ({ id: `event-${index}`, type, title, description: 'Synthetic account security activity.', occurred_at: `2026-10-16T00:0${index}:00Z` });
const first = [item('auth.login', 'Signed in to COMPASS', 4), item('auth.logout', 'Signed out of COMPASS', 3), item('auth.mfa.totp.enrolled', 'Authenticator app enabled', 2), item('auth.trusted.session.revoked', 'Trusted browser removed', 1)];
for (const width of [320, 1440]) {
  await check(`security-pagination-and-my-activity-${width}`, '/portal/account/activity?view=security', {
    viewport: { width, height: 1000 },
    overrides: {
      '/api/v1/me/security-activity': ({ url, reply }) => reply({ items: url.searchParams.get('page') === '2' ? [item('auth.login.failed', 'Unsuccessful sign-in attempt', 0)] : first, page: Number(url.searchParams.get('page')), page_size: 20, has_next: url.searchParams.get('page') !== '2' }),
      '/api/v1/me/activity': { items: [item('auth.login', 'Signed in to COMPASS', 4)], page: 1, page_size: 20, has_next: false },
    },
  }, async (page, { requests }) => {
    for (const event of first) await shown(page.getByText(event.title, { exact: true }));
    await hidden(page.getByText('New session created', { exact: true }));
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await shown(page.getByText('Unsuccessful sign-in attempt', { exact: true }));
    assert.equal(await page.getByRole('button', { name: 'Next', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Previous', exact: true }).click();
    await shown(page.getByText('Signed in to COMPASS', { exact: true }));
    await noHorizontalOverflow(page);
    await screenshot(page, `security-${width}`);
    await page.getByRole('button', { name: 'My activity', exact: true }).click();
    await shown(page.getByText('Signed in to COMPASS', { exact: true }));
    await hidden(page.getByText('Authenticator app enabled', { exact: true }));
    assert.ok(requests.some(r => r.pathname === '/api/v1/me/security-activity' && r.search.includes('page=2')));
    assert.equal(requests.filter(r => r.method !== 'GET').length, 0);
  });
}
await finish();
