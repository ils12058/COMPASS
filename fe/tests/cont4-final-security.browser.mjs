// Integrated confidentiality and keyboard checks against local synthetic HTTP fixtures.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { coverageFixture, ids, path, recommendation } from './support/case-coverage-fixtures.mjs';

const { check, finish, shown, hidden } = await createBrowserHarness('cont4-final-security');

for (const change of ['role', 'capability', 'student-affiliation', 'grant-revocation']) {
  const state = coverageFixture({ handoff: {} });
  await check(`${change}-clears-selected-and-handoff`, path, { handler: state.handler }, async page => {
    await page.getByRole('button', { name: new RegExp(`Review record ${ids.routine}`) }).click();
    await shown(page.getByText(recommendation, { exact: true }));
    await page.getByRole('button', { name: 'Open handoff', exact: true }).click();
    await shown(page.getByText('SYNTHETIC CONFIDENTIAL HANDOFF', { exact: true }));
    const currentUser = state.currentUser;
    if (change === 'role') state.currentUser = () => ({ ...currentUser(), role: 'GUIDANCE_SERVICES_STAFF' });
    if (change === 'capability') state.currentUser = () => ({ ...currentUser(), capabilities: currentUser().capabilities.filter(c => !c.startsWith('counseling.continuity') && !c.startsWith('counseling.handoff')) });
    state.denied = true;
    state.deniedStatus = ['role', 'capability'].includes(change) ? 403 : 404;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await page.getByText(recommendation, { exact: true }).waitFor({ state: 'hidden', timeout: 22000 });
    await hidden(page.getByText('SYNTHETIC CONFIDENTIAL HANDOFF', { exact: true }));
    const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
    assert.equal(storage.includes(recommendation) || storage.includes('SYNTHETIC CONFIDENTIAL HANDOFF'), false);
  });
}

await check('independent-approval-dialog-keyboard-focus-trap', path, {
  handler: coverageFixture({ identity: 'head', grant: { decision: 'REQUESTED', effective_status: 'PENDING' } }).handler,
}, async page => {
  const trigger = page.getByRole('button', { name: 'Approve coverage', exact: true });
  await trigger.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('alertdialog');
  await shown(dialog);
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press(key);
      assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true);
    }
  }
  await page.keyboard.press('Escape');
  await hidden(dialog);
  await page.waitForFunction(() => document.activeElement?.textContent?.trim() === 'Approve coverage');
});

await check('two-real-tabs-content-free-invalidation', path, { handler: coverageFixture().handler }, async (page, fixture) => {
  const second = await fixture.context.newPage();
  await second.goto(new URL('/portal/counseling/coverage', page.url()).href);
  await page.bringToFront();
  await page.getByRole('button', { name: new RegExp(`Review record ${ids.routine}`) }).click();
  await shown(page.getByText(recommendation, { exact: true }));
  await page.evaluate(() => {
    window.cont4Hint = null;
    window.cont4Channel = new BroadcastChannel('compass-case-coverage');
    window.cont4Channel.onmessage = event => { window.cont4Hint = event.data; };
  });
  await second.evaluate(id => {
    const channel = new BroadcastChannel('compass-case-coverage');
    channel.postMessage({ grant_id: id });
    channel.close();
  }, ids.grant);
  await page.getByText(recommendation, { exact: true }).waitFor({ state: 'hidden', timeout: 12000 });
  assert.deepEqual(await page.evaluate(() => window.cont4Hint), { grant_id: ids.grant });
  await shown(page.getByText('Protected content is closed', { exact: true }));
  await second.close();
});

await finish();
