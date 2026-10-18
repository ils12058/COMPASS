// Local synthetic API only. Native print dialogs and physical paper cannot be asserted headlessly.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { certificate, counselor, requestId, preparedVersion, pdfBytes } from './support/good-moral-print-fixtures.mjs';

const engine = process.env.COMPASS_UI_BROWSER ?? 'chromium';
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`good-moral-print-${engine}`);
const path = `/api/v1/good-moral/requests/${requestId}`;
const route = `/portal/good-moral/${requestId}`;
const diagnostic = 'PRIVATE-PRINT-DIAGNOSTIC';
const session = account => ({ user: account, session: { id: 'synthetic-session', expires_at: '2099-01-01T00:00:00Z', is_current: true } });
const instrument = `
  window.pdfResources = { created: [], revoked: [], opened: [], previews: [] };
  const originalCreate = URL.createObjectURL.bind(URL);
  const originalRevoke = URL.revokeObjectURL.bind(URL);
  URL.createObjectURL = blob => { const url = originalCreate(blob); window.pdfResources.created.push(url); return url; };
  URL.revokeObjectURL = url => { window.pdfResources.revoked.push(url); originalRevoke(url); };
`;
const fakePreview = `${instrument}
  window.open = (url, target) => {
    window.pdfResources.opened.push({ url, target, active: navigator.userActivation.isActive });
    const preview = { closed: false, opener: window };
    window.pdfResources.previews.push(preview);
    return preview;
  };
`;
function fixture({ status = 'READY_FOR_ISSUANCE', variant = 'CURRENT_STUDENT', issueCode, commit = true, pdfFailures = 0, pdfStatus = 503, refreshFailures = 0, holdIssue = false, holdVerify = false, holdPdf = false, account = counselor } = {}) {
  let item = certificate(status, variant);
  let attempts = 0;
  let issuedAttempt = false;
  let releaseIssue;
  let issueBegan;
  const issueStarted = new Promise(resolve => { issueBegan = resolve; });
  let releaseVerify;
  let verificationBegan;
  const verificationStarted = new Promise(resolve => { verificationBegan = resolve; });
  const issueGate = holdIssue ? new Promise(resolve => { releaseIssue = resolve; }) : Promise.resolve();
  const verifyGate = holdVerify ? new Promise(resolve => { releaseVerify = resolve; }) : Promise.resolve();
  let releasePdf;
  let pdfBegan;
  const pdfStarted = new Promise(resolve => { pdfBegan = resolve; });
  const pdfGate = holdPdf ? new Promise(resolve => { releasePdf = resolve; }) : Promise.resolve();
  const state = { issueBodies: [], pdfReads: 0, prematurePdfReads: 0, verificationReads: 0, refreshFailures, pdfFailures };
  return {
    state,
    issueStarted,
    verificationStarted,
    pdfStarted,
    releasePdf: () => releasePdf?.(),
    setDownloadAllowed: allowed => { item.actions.can_download = allowed; },
    releaseIssue: () => releaseIssue?.(),
    releaseVerify: () => releaseVerify?.(),
    options: {
      overrides: { '/api/v1/auth/session': session(account), '/api/v1/good-moral/requests': { items: [], page: 1, page_size: 20, has_next: false, filter_options: { form_revisions: [] } } },
      handler: async ({ pathname, method, request, reply, route: apiRoute }) => {
        if (pathname === path && method === 'GET') {
          if (issuedAttempt) {
            state.verificationReads++;
            verificationBegan();
            await verifyGate;
            if (state.refreshFailures-- > 0) { await reply({ error: { code: 'internal_error', message: diagnostic } }, 503); return true; }
          }
          await reply(item); return true;
        }
        if (pathname === `${path}/issue` && method === 'POST') {
          state.issueBodies.push(JSON.parse(request.postData()));
          issueBegan();
          await issueGate;
          issuedAttempt = true;
          if (!issueCode || commit) item = certificate('ISSUED', variant);
          if (issueCode === 'good_moral_preparation_changed') item.actions.preparation_version = '2026-10-16T01:00:00.987654+00:00';
          await reply(issueCode ? { error: { code: issueCode, message: diagnostic } } : item, issueCode ? issueCode === 'internal_error' ? 500 : 409 : 200);
          return true;
        }
        if (pathname === `${path}/pdf`) {
          state.pdfReads++;
          if (item.status !== 'ISSUED') state.prematurePdfReads++;
          attempts++;
          pdfBegan();
          await pdfGate;
          if (attempts <= state.pdfFailures) await reply({ error: { code: pdfStatus === 403 ? 'permission_denied' : 'release_audit_unavailable', message: diagnostic } }, pdfStatus);
          else await apiRoute.fulfill({ status: 200, contentType: 'application/pdf', headers: { 'content-disposition': 'attachment; filename="COMPASS-synthetic-certificate.pdf"' }, body: pdfBytes });
          return true;
        }
        return false;
      },
    },
  };
}
async function issue(page) {
  await page.getByRole('button', { name: 'Issue certificate', exact: true }).click();
  const dialog = page.getByRole('alertdialog');
  await shown(dialog);
  await shown(dialog.getByRole('heading', { name: 'Issue Good Moral certificate?' }));
  await dialog.getByRole('button', { name: 'Issue certificate', exact: true }).click();
}
async function prepared(page) {
  await page.waitForFunction(() => {
    const frame = document.querySelector('iframe[title="Finalized certificate PDF"]');
    return frame?.src.startsWith('blob:') && frame.dataset.previewReady === 'true';
  });
  assert.equal(await page.getByRole('button', { name: 'Print certificate', exact: true }).isEnabled(), true);
  await shown(page.getByText('The certificate has been issued. You can print or download the finalized PDF.', { exact: true }));
  await shown(page.getByText(/physical signature and dry seal/));
}
async function setFramePrint(page, mode) {
  await page.evaluate(mode => {
    const frame = document.querySelector('iframe[title="Finalized certificate PDF"]');
    if (!frame) throw new Error('Finalized PDF preview is missing');
    const print = mode === 'direct'
      ? () => window.__gmNativePrintCalls.push({ active: navigator.userActivation.isActive })
      : mode === 'throws'
        ? () => { throw new Error('Native PDF print is unavailable'); }
        : undefined;
    window.__gmNativePrintCalls ??= [];
    Object.defineProperty(frame, 'contentWindow', { configurable: true, value: print ? { print } : {} });
  }, mode);
}
async function downloaded(page) {
  // A headless PDF popup may also emit an unnamed download. Match this explicit fallback.
  const event = page.waitForEvent('download', { predicate: item => item.suggestedFilename() === 'COMPASS-synthetic-certificate.pdf' });
  await page.getByRole('button', { name: 'Download certificate', exact: true }).click();
  const download = await event;
  assert.equal(download.suggestedFilename(), 'COMPASS-synthetic-certificate.pdf');
  assert.deepEqual(await readFile(await download.path()), pdfBytes);
}
async function safe(page, data) {
  assert.equal(data.state.prematurePdfReads, 0);
  assert.ok(!(await page.locator('body').innerText()).includes(diagnostic));
  assert.doesNotMatch(await page.locator('body').innerText(), /printed successfully|printing completed|certificate printed/i);
  await noHorizontalOverflow(page);
}

for (const variant of ['CURRENT_STUDENT', 'GRADUATE']) for (const width of [320, 1440]) {
  const data = fixture({ variant, holdIssue: true, holdVerify: true });
  await check(`issue-confirm-verify-preview-download-reprint-${variant}-${width}`, route, { ...data.options, viewport: { width, height: 1000 }, initScripts: [fakePreview] }, async page => {
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(data.state.pdfReads, 0);
    await issue(page);
    await data.issueStarted;
    await shown(page.getByRole('button', { name: 'Issuing certificate…', exact: true }));
    assert.equal(await page.getByRole('button', { name: 'Issuing certificate…', exact: true }).isDisabled(), true);
    await page.keyboard.press('Enter');
    await page.keyboard.press('Escape');
    await shown(page.getByRole('alertdialog'));
    assert.equal(data.state.issueBodies.length, 1);
    assert.deepEqual(data.state.issueBodies[0], { expected_preparation_version: preparedVersion });
    assert.equal(data.state.pdfReads, 0);
    data.releaseIssue();
    await data.verificationStarted;
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(data.state.pdfReads, 0, 'Successful mutation alone cannot expose PDF before official refresh');
    data.releaseVerify();
    await prepared(page);
    assert.ok(data.state.verificationReads > 0);
    await hidden(page.getByRole('alertdialog'));
    await hidden(page.getByRole('button', { name: 'Issue certificate', exact: true }));
    await shown(page.getByText(variant === 'CURRENT_STUDENT' ? 'UCN-OP-GCO-01F4' : 'UCN-OP-GCO-01F6', { exact: true }));
    await downloaded(page);
    await setFramePrint(page, 'direct');
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    let resources = await page.evaluate(() => ({ calls: window.__gmNativePrintCalls, opened: window.pdfResources.opened, revoked: window.pdfResources.revoked }));
    assert.equal(resources.calls.length, 1);
    assert.equal(resources.calls[0].active, true, 'Native print is requested within the direct user gesture');
    assert.equal(resources.opened.length, 0, 'Supported direct print does not open an extra tab');
    assert.match(await page.getByRole('status').last().innerText(), /print request was sent/i);
    // A cancelled/no-op browser print leaves the issued view and all actions available.
    await prepared(page);
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    resources = await page.evaluate(() => ({ calls: window.__gmNativePrintCalls, opened: window.pdfResources.opened }));
    assert.equal(resources.calls.length, 2);
    assert.equal(resources.opened.length, 0);
    assert.equal(data.state.issueBodies.length, 1);
    assert.equal(data.state.pdfReads, 1, 'Preview, reprint, and download reuse the finalized Blob');
    await safe(page, data);
    await screenshot(page, `issued-${variant}-${width}`);
    const inline = await page.locator('iframe[title="Finalized certificate PDF"]').getAttribute('src');
    await page.getByRole('link', { name: 'Back to Good Moral queue', exact: true }).click();
    await hidden(page.locator('iframe[title="Finalized certificate PDF"]'));
    await page.waitForFunction(url => window.pdfResources.revoked.includes(url), inline);
    resources = await page.evaluate(() => ({ opened: window.pdfResources.opened, revoked: window.pdfResources.revoked }));
    assert.equal(resources.opened.length, 0);
    assert.ok(resources.revoked.includes(inline), 'Leaving the record revokes its inline PDF URL');
  });
}

{
  const data = fixture({ status: 'ISSUED' });
  await check('native-print-unavailable-opens-authorized-pdf-preview', route, { ...data.options, initScripts: [fakePreview] }, async page => {
    await prepared(page);
    await setFramePrint(page, 'throws');
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    await shown(page.getByRole('status').filter({ hasText: 'The finalized PDF preview opened in a new tab.' }));
    const resources = await page.evaluate(() => ({ opened: window.pdfResources.opened, previews: window.pdfResources.previews }));
    assert.equal(resources.opened.length, 1);
    assert.equal(resources.opened[0].active, true, 'Fallback preview opens within the direct user gesture');
    assert.equal(resources.previews[0].opener, null);
    assert.ok(resources.opened[0].url.startsWith('blob:'));
    assert.equal(await page.evaluate(async url => (await (await fetch(url)).arrayBuffer()).byteLength, resources.opened[0].url), pdfBytes.length);
    await downloaded(page);
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
    await page.getByRole('link', { name: 'Back to Good Moral queue', exact: true }).click();
    await page.evaluate(() => window.pdfResources.previews.forEach(p => { p.closed = true; }));
    await page.waitForFunction(() => window.pdfResources.opened.every(p => window.pdfResources.revoked.includes(p.url)));
  });
}

for (const mode of ['blocked', 'throws']) {
  const data = fixture({ status: 'ISSUED' });
  await check(`popup-${mode}-download-fallback`, route, { ...data.options, initScripts: [`${instrument} window.open = () => { ${mode === 'throws' ? 'throw new Error("blocked");' : 'return null;'} };`] }, async page => {
    await prepared(page);
    await setFramePrint(page, 'unsupported');
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    await shown(page.getByRole('alert').filter({ hasText: 'The print request and a new PDF preview could not be opened.' }));
    assert.equal(await page.evaluate(() => window.pdfResources.revoked.includes(window.pdfResources.created.at(-1))), true);
    await downloaded(page);
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
  });
}

{
  const data = fixture({ pdfFailures: 1 });
  await check('issued-then-pdf-failure-and-retry-without-reissue', route, data.options, async page => {
    await issue(page);
    await shown(page.getByRole('alert').filter({ hasText: 'The certificate is issued, but its PDF could not be prepared.' }));
    assert.equal(await page.getByRole('button', { name: 'Print certificate', exact: true }).isDisabled(), true);
    await hidden(page.getByRole('button', { name: 'Issue certificate', exact: true }));
    await page.getByRole('button', { name: 'Retry PDF', exact: true }).click();
    await prepared(page);
    assert.equal(data.state.pdfReads, 2);
    assert.equal(data.state.issueBodies.length, 1);
    await downloaded(page);
    await safe(page, data);
  });
}
{
  const data = fixture({ status: 'ISSUED', pdfFailures: 100, pdfStatus: 403 });
  await check('unauthorized-pdf-has-no-preview-and-retry-never-issues', route, data.options, async page => {
    await shown(page.getByRole('alert').filter({ hasText: 'its PDF could not be prepared' }));
    await hidden(page.locator('iframe[title="Finalized certificate PDF"]'));
    assert.equal(await page.getByRole('button', { name: 'Print certificate', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Download certificate', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('button') && ![...document.querySelectorAll('button')].some(b => b.textContent === 'Download certificate' && b.disabled));
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
  });
}
for (const commit of [true, false]) {
  const data = fixture({ issueCode: 'internal_error', commit });
  await check(`uncertain-issuance-verified-${commit ? 'issued' : 'ready'}`, route, data.options, async page => {
    await issue(page);
    if (commit) await prepared(page);
    else {
      await shown(page.getByRole('alert').filter({ hasText: 'Issuance could not be confirmed. The request is still ready for issuance' }));
      await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
      assert.equal(data.state.pdfReads, 0);
    }
    assert.equal(data.state.issueBodies.length, 1);
    await safe(page, data);
  });
}
for (const issueCode of [undefined, 'internal_error']) {
  const data = fixture({ issueCode, refreshFailures: 100 });
  await check(`issuance-${issueCode ? 'uncertain' : 'successful'}-refresh-fails-no-print-until-verified`, route, data.options, async page => {
    await issue(page);
    await shown(page.getByText(/Latest information could not be refreshed|could not be checked/i).first());
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(data.state.pdfReads, 0);
    data.state.refreshFailures = 0;
    await page.getByRole('button', { name: 'Retry', exact: true }).first().click();
    await prepared(page);
    assert.equal(data.state.issueBodies.length, 1);
    await safe(page, data);
  });
}
for (const code of ['good_moral_preparation_changed', 'current_student_required']) {
  const data = fixture({ issueCode: code, commit: false });
  await check(`issuance-rejection-${code}`, route, data.options, async page => {
    await issue(page);
    await shown(page.getByRole('alert').filter({ hasText: code === 'good_moral_preparation_changed' ? 'This request changed.' : 'no longer a current student' }));
    await hidden(page.getByRole('alertdialog'));
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(data.state.pdfReads, 0);
    assert.equal(data.state.issueBodies.length, 1);
    if (code === 'good_moral_preparation_changed') {
      await page.getByRole('button', { name: 'Issue certificate', exact: true }).click();
      await page.getByRole('alertdialog').getByRole('button', { name: 'Issue certificate', exact: true }).click();
      await shown(page.getByRole('alert').filter({ hasText: 'This request changed.' }));
      assert.equal(data.state.issueBodies[1].expected_preparation_version, '2026-10-16T01:00:00.987654+00:00');
    }
    await safe(page, data);
  });
}
for (const status of ['REQUESTED', 'READY_FOR_ISSUANCE', 'CANCELLED']) {
  const data = fixture({ status });
  await check(`unissued-${status}-has-no-print-flow`, route, data.options, async page => {
    await shown(page.getByRole('heading', { name: 'Good Moral request', exact: true }));
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(data.state.pdfReads, 0);
    await safe(page, data);
  });
}
{
  const data = fixture({ status: 'ISSUED', holdPdf: true });
  await check('permission-loss-during-pdf-read-discards-response-before-authorized-remount', route, {
    ...data.options,
    beforeNavigate: async ({ page }) => page.clock.install(),
  }, async page => {
    await data.pdfStarted;
    data.setDownloadAllowed(false);
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event('offline')); window.dispatchEvent(new Event('online')); });
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    const completed = page.waitForResponse(response => response.url().endsWith(`${path}/pdf`));
    data.releasePdf();
    await completed;
    await page.clock.runFor(10);
    await hidden(page.locator('iframe[title="Finalized certificate PDF"]'));
    data.setDownloadAllowed(true);
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event('offline')); window.dispatchEvent(new Event('online')); });
    await prepared(page);
    assert.equal(data.state.pdfReads, 2, 'A newly authorized mount fetches again after the unobserved response was discarded');
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
  });
}
{
  const account = { ...counselor, role: 'GUIDANCE_SERVICES_STAFF', capabilities: ['good_moral.view', 'good_moral.prepare'] };
  const data = fixture({ status: 'ISSUED', account });
  await check('existing-authorized-gss-can-reprint-without-issue-authority', route, { ...data.options, initScripts: [fakePreview] }, async page => {
    await prepared(page);
    await hidden(page.getByRole('button', { name: 'Issue certificate', exact: true }));
    await setFramePrint(page, 'direct');
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    assert.equal(await page.evaluate(() => window.__gmNativePrintCalls.length), 1);
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
  });
}
{
  const account = { ...counselor, role: 'STUDENT', student_lifecycle_status: 'CURRENT', capabilities: ['good_moral.view_self'] };
  await check('student-original-download-remains-unchanged', route, { overrides: { '/api/v1/auth/session': session(account), [`/api/v1/good-moral/me/${requestId}`]: certificate('ISSUED'), [`/api/v1/good-moral/me/${requestId}/pdf`]: ({ route: apiRoute }) => apiRoute.fulfill({ status: 200, contentType: 'application/pdf', headers: { 'content-disposition': 'attachment; filename="COMPASS-synthetic-certificate.pdf"' }, body: pdfBytes }) } }, async (page, { requests }) => {
    await shown(page.getByRole('button', { name: 'Download certificate', exact: true }));
    await hidden(page.getByRole('button', { name: 'Print certificate', exact: true }));
    assert.equal(requests.filter(r => r.pathname.endsWith('/pdf')).length, 0);
    await downloaded(page);
    assert.equal(requests.filter(r => r.method === 'POST').length, 0);
    assert.equal(requests.filter(r => r.pathname.startsWith('/api/v1/good-moral/requests/')).length, 0);
  });
}
{
  const data = fixture({ status: 'ISSUED' });
  await check('direct-print-requests-browser-print-from-finalized-pdf-click', route, { ...data.options, initScripts: [instrument] }, async (page, { context }) => {
    await prepared(page);
    await setFramePrint(page, 'direct');
    await page.getByRole('button', { name: 'Print certificate', exact: true }).click();
    // The handler is stubbed so browser automation never opens a real native print dialog.
    assert.equal(await page.evaluate(() => window.__gmNativePrintCalls.length), 1);
    assert.equal(context.pages().length, 1);
    await downloaded(page);
    assert.match(await page.getByRole('status').last().innerText(), /print request was sent/i);
    assert.equal(data.state.issueBodies.length, 0);
    await safe(page, data);
  });
}
await finish();
