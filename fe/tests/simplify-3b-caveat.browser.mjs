import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { homeWorld } from './support/ux15-home-fixtures.mjs';
const h = await createBrowserHarness('simplify-3b-caveat');
// FINAL-UI-1: every role's Home shares one header — a Caveat greeting h1, the "Home" context and
// the office date in the description. The fixture clock fixes the greeting at "Good morning, Alex".
const roles = [
  { role: 'STUDENT' },
  { role: 'COUNSELOR' },
  { role: 'COUNSELOR', designations: ['HEAD_GUIDANCE_COUNSELOR'], label: 'HEAD_GUIDANCE_COUNSELOR' },
  { role: 'GUIDANCE_OFFICE_ASSISTANT' },
  { role: 'IT_ADMIN' },
  { role: 'INSTITUTIONAL_OFFICER' },
  { role: 'FACULTY' },
];
const facultyAvailability = { can_confirm_student: false, can_submit_referral: false, can_view_submissions: false, valid_until: null };
for (const { role, designations = [], label = role } of roles) {
  for (const width of role === 'STUDENT' ? [320, 390, 768, 1024, 1440] : [390, 1440]) {
    const world = homeWorld({ role, designations });
    await h.check(`${label}-${width}`, '/portal', world.options({
      viewport: { width, height: 900 },
      ...(role === 'FACULTY' ? { overrides: { '/api/v1/faculty/referrals/availability': facultyAvailability } } : {}),
    }), async page => {
      const title = page.getByRole('heading', { level: 1 });
      await h.shown(title);
      await page.evaluate(() => document.fonts.ready);
      assert.match(await title.innerText(), /Good (?:morning|afternoon|evening), Alex/);
      assert.equal(await title.getAttribute('id'), role === 'FACULTY' ? 'faculty-home-heading' : 'portal-overview-heading');
      const face = await title.locator('span').first().evaluate(el => getComputedStyle(el).fontFamily);
      assert.match(face, /Caveat/i);
      const header = page.locator('[data-page-header]');
      await h.shown(header.getByText('Home', { exact: true }));
      assert.match(await header.locator('p').nth(1).innerText(), /Thursday, October 22/);
      if (label === 'HEAD_GUIDANCE_COUNSELOR') assert.match(await header.locator('p').nth(1).innerText(), /Counselor · Head Guidance Counselor/);
      await h.noHorizontalOverflow(page);
      await h.screenshot(page, `${label}-${width}`);
      await page.addStyleTag({ content: 'html { font-size: 200%; }' });
      await h.noHorizontalOverflow(page);
    });
  }
}
const long = homeWorld();
long.account.first_name = 'A'.repeat(48);
await h.check('long-name-320', '/portal', long.options({ viewport: { width: 320, height: 900 } }), async page => {
  await h.shown(page.getByRole('heading', { level: 1 }));
  await h.noHorizontalOverflow(page);
  await page.addStyleTag({ content: 'html { font-size: 200%; }' });
  await h.noHorizontalOverflow(page);
});
await h.finish();