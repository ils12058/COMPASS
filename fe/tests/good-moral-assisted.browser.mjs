// Local, intercepted synthetic APIs only; no real Students or mail transport.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { counselor, certificate, requestId } from './support/good-moral-print-fixtures.mjs';
const engine = process.env.COMPASS_UI_BROWSER ?? 'chromium';
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`good-moral-assisted-${engine}`);
const start = '/portal/good-moral/start';
const current = { id: '11111111-1111-4111-8111-111111111111', display_name: 'Current Synthetic', institutional_id: 'SYNTHETIC-1', college: { id: 'college', code: 'TEST', name: 'Synthetic College' }, variant: 'CURRENT_STUDENT' };
const graduate = { ...current, id: '22222222-2222-4222-8222-222222222222', display_name: 'Graduate Synthetic', institutional_id: 'SYNTHETIC-2', variant: 'GRADUATE' };
const empty = { items: [], page: 1, page_size: 10, has_next: false, filter_options: { form_revisions: [] } };
function fixture({ role = 'COUNSELOR', errorCode, hold = false, authorized = true } = {}) {
  let calls = 0, release, began;
  const started = new Promise(resolve => { began = resolve; });
  const gate = hold ? new Promise(resolve => { release = resolve; }) : Promise.resolve();
  const state = { bodies: [], keys: [], searches: [], currentStudent: current };
  const account = { ...counselor, role, capabilities: authorized ? [...counselor.capabilities.filter(c => c !== 'good_moral.issue' || role === 'COUNSELOR'), 'good_moral.initiate', 'good_moral.prepare'] : ['good_moral.view'], designations: [] };
  const item = { ...certificate('REQUESTED'), initiation_origin: 'GCO_ASSISTED', initiated_by: { id: account.id, display_name: 'Synthetic Initiator' } };
  return { state, started, release: () => release?.(), options: {
    overrides: { '/api/v1/auth/session': { user: account, session: { id: 'synthetic', expires_at: '2099-01-01T00:00:00Z', is_current: true } }, '/api/v1/good-moral/requests': empty, [`/api/v1/good-moral/requests/${requestId}`]: item },
    handler: async ({ pathname, method, url, request, reply }) => {
      if (pathname === '/api/v1/good-moral/student-options') {
        state.searches.push(url.search);
        const page = Number(url.searchParams.get('page') || 1), term = url.searchParams.get('search') ?? '';
        await reply({ ...empty, items: term.includes('Graduate') || page === 2 ? [graduate] : [state.currentStudent], page, has_next: !term && page === 1 }); return true;
      }
      if (method === 'POST' && /^\/api\/v1\/good-moral\/requests\/(current-student|graduate)$/.test(pathname)) {
        calls++; state.bodies.push(JSON.parse(request.postData())); state.keys.push(request.headers()['idempotency-key']);
        began(); await gate;
        if (errorCode && calls === 1) await reply({ error: { code: errorCode, message: 'PRIVATE INTERNAL DIAGNOSTIC' } }, errorCode === 'internal_error' ? 503 : 409);
        else await reply(item, 201);
        return true;
      }
      return false;
    },
  } };
}
async function chooseCurrent(page) {
  await page.getByRole('radio', { name: /Current Synthetic/ }).check();
  await page.getByLabel('Year level').selectOption('4th Year');
  await page.getByLabel('Semester', { exact: false }).selectOption('First Semester');
  await page.getByRole('button', { name: 'Review request', exact: true }).click();
  const dialog = page.getByRole('alertdialog');
  await shown(dialog.getByText(/Current Synthetic/));
  await shown(dialog.getByText(/Student will receive a COMPASS notification and email/));
  return dialog;
}
for (const role of ['COUNSELOR', 'GUIDANCE_SERVICES_STAFF']) {
  const f = fixture({ role, hold: true });
  await check(`${role} confirmation, double submit and operational navigation`, start, f.options, async page => {
    const dialog = await chooseCurrent(page);
    await dialog.getByRole('button', { name: 'Start Good Moral request', exact: true }).click();
    await f.started;
    assert.equal(await dialog.getByRole('button', { name: 'Starting request…', exact: true }).isDisabled(), true);
    assert.equal(f.state.bodies.length, 1); f.release();
    await shown(dialog.getByRole('heading', { name: 'Good Moral request started', exact: true }));
    await dialog.getByRole('button', { name: 'Open request', exact: true }).click();
    await page.waitForURL(`**/portal/good-moral/${requestId}`);
    await shown(page.getByText('Synthetic Initiator', { exact: true }));
    assert.deepEqual(f.state.bodies[0], { student_id: current.id, year_level: '4th Year', semester: 'First Semester' });
    assert.equal(f.state.keys[0].length, 36);
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
  });
}
{
  const f = fixture();
  await check('Graduate search, pagination, historical date and review', start, f.options, async page => {
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await shown(page.getByRole('radio', { name: /Graduate Synthetic/ }));
    await page.getByLabel('Search eligible Students').fill('Graduate');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.getByRole('radio', { name: /Graduate Synthetic/ }).check();
    await hidden(page.getByLabel('Year level'));
    await page.getByLabel('Degree', { exact: false }).fill('Bachelor of Science');
    await page.getByLabel('Major (optional)').fill('Computing');
    await page.getByLabel('Graduation date', { exact: false }).fill('2020-06-01');
    await page.getByRole('button', { name: 'Review request', exact: true }).click();
    const dialog = page.getByRole('alertdialog');
    await shown(dialog.getByText(/Bachelor of Science · Computing/));
    await dialog.getByRole('button', { name: 'Start Good Moral request', exact: true }).click();
    await shown(dialog.getByRole('heading', { name: 'Good Moral request started' }));
    assert.equal(f.state.bodies[0].student_id, graduate.id);
    assert.equal(f.state.bodies[0].graduation_date, '2020-06-01');
    assert.ok(f.state.searches.some(search => search.includes('search=Graduate') && search.includes('page=1')));
  });
}
for (const errorCode of ['good_moral_inventory_required', 'good_moral_exit_interview_required', 'good_moral_not_found', 'good_moral_conflict']) {
  const f = fixture({ errorCode });
  await check(`${errorCode} stays on review without false success`, start, f.options, async page => {
    const dialog = await chooseCurrent(page);
    await dialog.getByRole('button', { name: 'Start Good Moral request', exact: true }).click();
    await shown(dialog.getByRole('alert')); assert.doesNotMatch(await dialog.textContent(), /PRIVATE/);
    assert.equal(new URL(page.url()).pathname, start);
    await hidden(dialog.getByRole('heading', { name: 'Good Moral request started', exact: true }));
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.waitForFunction(() => document.activeElement?.textContent === 'Review request');
  });
}
{
  const f = fixture({ errorCode: 'internal_error' });
  await check('uncertain result locks details and retries original identity', start, f.options, async page => {
    const dialog = await chooseCurrent(page);
    await dialog.getByRole('button', { name: 'Start Good Moral request', exact: true }).click();
    await shown(dialog.getByText(/result could not be confirmed/));
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    assert.equal(await page.getByLabel('Year level').isDisabled(), true);
    await page.getByRole('button', { name: 'Retry same request', exact: true }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Retry same request', exact: true }).click();
    await shown(page.getByRole('heading', { name: 'Good Moral request started', exact: true }));
    assert.equal(f.state.keys.length, 2); assert.equal(f.state.keys[0], f.state.keys[1]);
    assert.deepEqual(f.state.bodies[0], f.state.bodies[1]);
  });
}
{
  const f = fixture({ authorized: false });
  await check('view-only account has no action or picker', '/portal/good-moral', f.options, async page => {
    await hidden(page.getByRole('link', { name: /Start request/ }));
    await page.goto(new URL(start, page.url()).href);
    await shown(page.getByRole('heading', { name: 'Request initiation unavailable' }));
    await hidden(page.getByLabel('Search eligible Students'));
  });
}
{
  const f = fixture({ errorCode: 'current_student_required' });
  await check('changed lifecycle refreshes same search and requires explicit reselection', start, f.options, async page => {
    const dialog = await chooseCurrent(page);
    await dialog.getByRole('button', { name: 'Start Good Moral request', exact: true }).click();
    await shown(dialog.getByText(/lifecycle has changed/));
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    f.state.currentStudent = { ...current, variant: 'GRADUATE' };
    const previousSearches = f.state.searches.length;
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.getByRole('radio', { name: /Current Synthetic/ }).check();
    assert.ok(f.state.searches.length > previousSearches);
    await shown(page.getByLabel('Degree', { exact: false }));
    await hidden(page.getByLabel('Year level'));
  });
}
for (const device of ['phone', 'tablet']) {
  const f = fixture({ role: 'GUIDANCE_SERVICES_STAFF' });
  await check(`${device} layout and keyboard review`, start, { ...f.options, device }, async page => {
    await chooseCurrent(page); await noHorizontalOverflow(page);
    await page.getByRole('alertdialog').getByRole('button', { name: 'Cancel', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.activeElement?.textContent === 'Review request');
    await noHorizontalOverflow(page); await screenshot(page, `${device}-assisted-request`);
  });
}
await finish();
