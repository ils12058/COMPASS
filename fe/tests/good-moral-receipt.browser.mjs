// Local mocked API contracts. These simulations do not prove PostgreSQL authorization or inspect a physical OR.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { pdfBytes } from './support/good-moral-print-fixtures.mjs';
import { receiptItem, requestId, revisionId, nextRevisionId, verificationId, inspectorId, inspector, session, version, nextVersion } from './support/good-moral-receipt-fixtures.mjs';

const engine = process.env.COMPASS_UI_BROWSER ?? 'chromium';
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`good-moral-receipt-${engine}`);
const path = `/api/v1/good-moral/requests/${requestId}`;
const route = `/portal/good-moral/${requestId}`;
const diagnosis = 'PRIVATE-RECEIPT-DIAGNOSTIC';
function fixture({ item = receiptItem(), account = inspector, behavior = 'success', hold = false, refreshFailures = 0 } = {}) {
  const state = { item, account, posts: [], patches: [], prepares: 0, issues: 0, gets: 0, refreshFailures };
  let release, started;
  const begun = new Promise(resolve => { started = resolve; });
  const gate = hold ? new Promise(resolve => { release = resolve; }) : Promise.resolve();
  const verified = (actor = inspectorId) => {
    state.item = { ...state.item, actions: { ...state.item.actions, request_version: nextVersion, can_prepare: true },
      receipt_inspection: { ...state.item.receipt_inspection, status: 'VERIFIED', can_verify: false, blocker: null, verification_id: verificationId, verified_by_id: actor, verified_at: '2026-10-24T01:01:00Z', method: 'PHYSICAL_OR_INSPECTION' } };
  };
  const replace = () => {
    state.item = { ...state.item, official_receipt_number: 'OR-OTHER-STAFF', actions: { ...state.item.actions, request_version: nextVersion, can_prepare: false, can_issue: false }, receipt_identity: { ...state.item.receipt_identity, revision_id: nextRevisionId }, receipt_inspection: { ...receiptItem().receipt_inspection } };
  };
  return { state, begun, release: () => release?.(), verified, replace,
    options: { handler: async ({ pathname, method, request, reply, route: api }) => {
      if (pathname === '/api/v1/auth/session') { await reply({ ...session(state.account), session: { ...session(state.account).session, id: state.sessionId ?? session(state.account).session.id } }); return true; }
      if (pathname === path && method === 'GET') {
        state.gets++;
        if ((state.posts.length || state.patches.length) && state.refreshFailures-- > 0) { await reply({ error: { code: 'internal_error', message: diagnosis } }, 503); return true; }
        if (behavior === 'deactivated' && state.posts.length) { await reply({ error: { code: 'permission_denied', message: diagnosis } }, 403); return true; }
        await reply(state.item); return true;
      }
      if (pathname === `${path}/receipt/verify` && method === 'POST') {
        const body = JSON.parse(request.postData()); state.posts.push(body); started(); await gate;
        if (behavior === 'stale') { replace(); await reply({ error: { code: 'good_moral_receipt_changed', message: diagnosis } }, 409); return true; }
        if (['prepared-elsewhere', 'issued-elsewhere', 'session-changed'].includes(behavior)) {
          if (behavior === 'session-changed') { state.sessionId = 'replacement-session'; await reply({ error: { code: 'not_authenticated', message: diagnosis } }, 401); return true; }
          verified('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'); state.item.status = behavior === 'issued-elsewhere' ? 'ISSUED' : 'READY_FOR_ISSUANCE'; state.item.actions.can_correct = behavior !== 'issued-elsewhere'; state.item.actions.can_prepare = false; state.item.actions.can_issue = behavior !== 'issued-elsewhere'; state.item.actions.can_download = behavior === 'issued-elsewhere';
          await reply({ error: { code: 'good_moral_conflict', message: diagnosis } }, 409); return true;
        }
        if (behavior === 'already') { verified('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'); await reply({ error: { code: 'good_moral_receipt_already_verified', message: diagnosis } }, 409); return true; }
        if (['conflict', 'policy', 'fenced', 'cancelled', 'revoked', 'deactivated', 'account-changed'].includes(behavior)) {
          let code = 'permission_denied'; let status = 403;
          if (behavior === 'conflict') code = 'good_moral_receipt_conflict';
          if (behavior === 'policy') { code = 'good_moral_receipt_policy_unresolved'; state.item.receipt_inspection = { ...state.item.receipt_inspection, status: 'POLICY_UNAVAILABLE', can_verify: false, expected_amount: null, currency: null, blocker: code }; }
          if (behavior === 'fenced') { code = 'good_moral_receipt_cutover_required'; state.item.receipt_identity.ledger_mode = 'FENCED'; state.item.receipt_inspection.can_verify = false; state.item.receipt_inspection.blocker = code; }
          if (behavior === 'cancelled') { code = 'good_moral_conflict'; state.item.status = 'CANCELLED'; state.item.receipt_inspection.can_verify = false; state.item.actions.can_correct = false; state.item.actions.can_prepare = false; }
          if (!['revoked', 'deactivated', 'account-changed'].includes(behavior)) status = 409;
          else state.item.receipt_inspection.can_verify = false;
          if (behavior === 'account-changed') { status = 401; state.account = { ...inspector, id: 'new-account', first_name: 'Other' }; state.item.applicant_name = 'New account record'; }
          await reply({ error: { code, message: diagnosis } }, status); return true;
        }
        if (behavior === 'abort-before' && state.posts.length === 1) { await api.abort('failed'); return true; }
        verified();
        state.item.receipt_verification_result = { operation_id: body.operation_id, verification_id: verificationId, assignment_id: revisionId, invalidated_at: null };
        const response = structuredClone(state.item);
        if (behavior === 'late-invalidated') { replace(); response.receipt_verification_result.invalidated_at = '2026-10-24T01:02:00Z'; }
        if (behavior === 'abort-after') await api.abort('failed');
        else await reply(response);
        return true;
      }
      if (pathname === path && method === 'PATCH') {
        const body = JSON.parse(request.postData()); state.patches.push(body);
        const receiptChanged = Object.keys(body).some(k => k.startsWith('official_receipt_'));
        state.item = { ...state.item, ...Object.fromEntries(Object.entries(body).filter(([key]) => key.startsWith("official_receipt_"))), degree: body.degree ?? state.item.degree, major: body.major ?? state.item.major, status: 'REQUESTED', prepared_by: null, prepared_at: null, actions: { ...state.item.actions, request_version: nextVersion, can_prepare: !receiptChanged && state.item.receipt_inspection.status === 'VERIFIED', can_issue: false } };
        if (receiptChanged) { state.item.receipt_identity.revision_id = nextRevisionId; state.item.receipt_inspection = { ...receiptItem().receipt_inspection }; }
        if (behavior === 'patch-uncertain-refresh') { state.refreshFailures = 1; await reply({ error: { code: 'internal_error', message: diagnosis } }, 503); }
        else await reply(state.item);
        return true;
      }
      if (pathname === `${path}/prepare`) {
        state.prepares++; state.item.status = 'READY_FOR_ISSUANCE'; state.item.prepared_at = nextVersion; state.item.prepared_by = { id: inspectorId, display_name: 'Synthetic Inspector' }; state.item.actions = { ...state.item.actions, request_version: nextVersion, preparation_version: nextVersion, can_prepare: false, can_issue: true };
        await reply(state.item); return true;
      }
      if (pathname === `${path}/issue`) {
        state.issues++; state.item.status = 'ISSUED'; state.item.issued_at = nextVersion; state.item.issued_by_name_snapshot = 'Synthetic Counselor'; state.item.actions.can_issue = false; state.item.actions.can_correct = false; state.item.actions.can_download = true;
        await reply(state.item); return true;
      }
      if (pathname === `${path}/pdf`) { await api.fulfill({ status: 200, contentType: 'application/pdf', body: pdfBytes }); return true; }
      if (pathname === '/api/v1/good-moral/requests') { await reply({ items: [], page: 1, page_size: 20, has_next: false, ordering: 'OLDEST_FIRST', filter_options: { form_revisions: [] } }); return true; }
      return false;
    } },
  };
}
async function openInspection(page, name = 'Verify receipt') {
  await page.getByRole('button', { name, exact: true }).click();
  const dialog = page.getByRole('alertdialog'); await shown(dialog);
  return dialog;
}
async function submitInspection(page, name) {
  const dialog = await openInspection(page, name);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Verify receipt', exact: true }).click();
}

for (const [state, label] of [['MISSING', 'Missing receipt'], ['INCOMPLETE', 'Receipt incomplete'], ['POLICY_UNAVAILABLE', 'Fee policy unavailable'], ['LEGACY_CONFLICT', 'Receipt needs GCO review'], ['DISPUTED', 'Receipt disputed']]) {
  const item = receiptItem(state); const f = fixture({ item });
  await check(`blocker-${state}`, route, f.options, async page => {
    await shown(page.getByText(label, { exact: true }));
    await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
    await hidden(page.getByRole('button', { name: 'Mark ready for issuance', exact: true }));
    assert.equal(f.state.posts.length, 0);
  });
}
for (const mode of ['DORMANT', 'FENCED']) {
  const f = fixture({ item: receiptItem('LEGACY_UNKNOWN', mode) });
  await check(`availability-${mode}`, route, f.options, async page => {
    await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
    await shown(page.getByText(mode === 'DORMANT' ? /inspection is not enabled/ : /processing is temporarily paused/).first());
    if (mode === 'FENCED') { await hidden(page.getByRole('button', { name: 'Correct certificate details' })); await hidden(page.getByRole('button', { name: 'Mark ready for issuance' })); }
    else await shown(page.getByRole('button', { name: 'Mark ready for issuance' }));
  });
}
{
  const item = receiptItem('INCOMPLETE'); item.official_receipt_amount = '75.00'; item.receipt_inspection.blocker = 'good_moral_receipt_fee_mismatch';
  const f = fixture({ item }); await check('fee-mismatch-keeps-actual-and-approved-expected', route, f.options, async page => {
    await shown(page.getByText(/keep the amount printed/)); const region = page.getByRole('region', { name: 'Official Receipt', exact: true });
    assert.ok((await region.innerText()).includes('75.00'));
    await shown(page.getByText('Approved expected amount', { exact: true })); await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
  });
}
{
  const item = receiptItem(); item.receipt_inspection.can_verify = false;
  const f = fixture({ item }); await check('backend-refusal-hides-verification-despite-capability', route, f.options, async page => { await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true })); });
}
{
  const f = fixture({ account: { ...inspector, role: 'GUIDANCE_SERVICES_STAFF' } });
  await check('gss-intentional-inspection-pins-payload-and-refreshes-provenance', route, f.options, async page => {
    const dialog = await openInspection(page); const checkbox = dialog.getByRole('checkbox');
    assert.equal(await checkbox.isChecked(), false); assert.equal(await dialog.getByRole('button', { name: 'Verify receipt', exact: true }).isDisabled(), true);
    await shown(dialog.getByText(requestId, { exact: true })); await shown(dialog.getByText('OR-SYNTHETIC-000125', { exact: true }));
    await checkbox.check(); await dialog.getByRole('button', { name: 'Verify receipt', exact: true }).click();
    await shown(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    assert.equal(f.state.posts.length, 1);
    assert.deepEqual(Object.keys(f.state.posts[0]).sort(), ['assignment_id', 'expected_resource_version', 'method', 'operation_id']);
    assert.equal(f.state.posts[0].assignment_id, revisionId); assert.equal(f.state.posts[0].expected_resource_version, version);
    assert.equal(f.state.posts[0].method, 'PHYSICAL_OR_INSPECTION');
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.waitForFunction(() => document.activeElement?.id === 'good-moral-receipt-heading');
    await shown(page.getByText('Receipt verified', { exact: true })); await shown(page.getByText('Inspector account reference', { exact: true }));
    await shown(page.getByRole('button', { name: 'Mark ready for issuance', exact: true }));
    await hidden(page.getByRole('button', { name: 'Issue certificate', exact: true }));
  });
}
for (const behavior of ['stale', 'already', 'conflict', 'policy', 'fenced', 'cancelled', 'revoked', 'deactivated', 'account-changed', 'late-invalidated']) {
  const f = fixture({ behavior });
  await check(`inspection-recovery-${behavior}`, route, f.options, async page => {
    await submitInspection(page); await f.begun;
    await hidden(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    if (behavior === 'already') { await shown(page.getByText('Receipt verified', { exact: true })); await shown(page.getByText('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', { exact: true })); }
    else if (behavior === 'account-changed') { await shown(page.getByText('New account record', { exact: true }).first()); }
    else if (behavior === 'deactivated') { await shown(page.getByRole('alert').filter({ hasText: /could not be loaded|can't perform/ }).first()); }
    else { await shown(page.getByRole('alert').filter({ hasText: /receipt|inspection|action|paused/i }).first()); }
    assert.equal(f.state.posts.length, 1); assert.doesNotMatch(await page.locator('body').innerText(), /PRIVATE-RECEIPT-DIAGNOSTIC/);
    if (['policy', 'fenced', 'cancelled', 'revoked', 'deactivated'].includes(behavior)) await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
  });
}
{
  const f = fixture({ behavior: 'abort-before' });
  await check('uncertain-before-commit-retries-same-operation-after-new-review', route, f.options, async page => {
    await submitInspection(page); await shown(page.getByRole('button', { name: 'Review inspection retry', exact: true }));
    const original = f.state.posts[0]; const dialog = await openInspection(page, 'Review inspection retry');
    assert.equal(await dialog.getByRole('checkbox').isChecked(), false);
    await dialog.getByRole('checkbox').check(); await dialog.getByRole('button', { name: 'Verify receipt', exact: true }).click();
    await shown(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    assert.deepEqual(f.state.posts, [original, original]);
  });
}
{
  const f = fixture({ behavior: 'abort-after' });
  await check('uncertain-after-commit-refreshes-without-replay', route, f.options, async page => {
    await submitInspection(page); await shown(page.getByText('Receipt verified', { exact: true }));
    await hidden(page.getByRole('alertdialog')); assert.equal(f.state.posts.length, 1); await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
  });
}
{
  const f = fixture({ refreshFailures: 1 });
  await check('failed-refresh-blocks-other-mutations-until-current-outcome-checked', route, f.options, async page => {
    await submitInspection(page); await shown(page.getByText(/Latest information could not be refreshed/));
    await hidden(page.getByRole('button', { name: 'Correct certificate details', exact: true }));
    await hidden(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    await page.getByRole('button', { name: 'Check current request', exact: true }).click(); await shown(page.getByText('Receipt verified', { exact: true })); assert.equal(f.state.posts.length, 1);
  });
}
{
  const f = fixture({ hold: true });
  await check('pending-dialog-traps-keyboard-and-rejects-dismissal-or-double-submit', route, f.options, async page => {
    await submitInspection(page); await f.begun;
    const dialog = page.getByRole('alertdialog'); await shown(dialog.getByRole('button', { name: 'Recording inspection…', exact: true }));
    await page.keyboard.press('Escape'); await shown(dialog); assert.equal(await dialog.getByRole('button', { name: 'Cancel', exact: true }).isDisabled(), true);
    await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="alertdialog"]'))), true, await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 250)));
    assert.equal(f.state.posts.length, 1); f.release(); await shown(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
  });
}
for (const receiptChange of [true, false]) {
  const item = receiptItem('VERIFIED'); item.status = 'READY_FOR_ISSUANCE'; item.prepared_at = version; item.prepared_by = { id: inspectorId, display_name: 'Synthetic Staff' }; item.actions.can_prepare = false; item.actions.can_issue = true;
  const f = fixture({ item });
  await check(receiptChange ? 'receipt-correction-needs-reinspection-and-preparation' : 'unrelated-correction-retains-inspection-and-resets-preparation', route, f.options, async page => {
    await page.getByRole('button', { name: 'Correct certificate details', exact: true }).click();
    await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
    await page.getByLabel(receiptChange ? 'Receipt number' : 'Major', { exact: true }).fill(receiptChange ? 'OR-CORRECTED' : 'New major');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await shown(page.getByRole('button', { name: 'Correct certificate details', exact: true }));
    if (receiptChange) { await shown(page.getByText('Receipt needs verification', { exact: true })); await shown(page.getByRole('button', { name: 'Verify receipt', exact: true })); }
    else { await shown(page.getByText('Receipt verified', { exact: true })); await shown(page.getByRole('button', { name: 'Mark ready for issuance', exact: true })); }
    await hidden(page.getByRole('button', { name: 'Issue certificate', exact: true })); assert.equal(f.state.posts.length, 0);
  });
}
{
  const f = fixture();
  await check('counselor-verifies-prepares-and-issues-without-printing-on-inspection', route, f.options, async page => {
    await submitInspection(page); await shown(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    assert.equal(f.state.issues, 0); await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Mark ready for issuance', exact: true }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Mark ready', exact: true }).click();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Issue certificate', exact: true }).click();
    await shown(page.getByRole('alertdialog').getByText(/Receipt verified/));
    await page.getByRole('alertdialog').getByRole('button', { name: 'Issue certificate', exact: true }).click();
    await shown(page.getByRole('heading', { name: 'Certificate issuance', exact: true })); assert.equal(f.state.issues, 1);
  });
}
for (const width of [320, 768, 1440]) {
  const item = receiptItem(); item.applicant_name = 'Synthetic Long Applicant Name '.repeat(8).slice(0, 200); item.official_receipt_number = 'OR-'.padEnd(96, '9'); item.official_receipt_amount = '9999999999.99'; item.receipt_inspection.expected_amount = item.official_receipt_amount;
  const f = fixture({ item });
  await check(`receipt-keyboard-responsive-${width}`, route, { ...f.options, viewport: { width, height: 900 } }, async page => {
    if (width === 768) await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    const dialog = await openInspection(page); await noHorizontalOverflow(page);
    const checkBox = dialog.getByRole('checkbox'); await checkBox.focus(); await page.keyboard.press('Space'); assert.equal(await checkBox.isChecked(), true);
    await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="alertdialog"]'))), true);
    await screenshot(page, `receipt-${width}`); await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await hidden(dialog);
    await page.waitForFunction(() => document.activeElement?.id === 'good-moral-verify-trigger');
    assert.equal(f.state.posts.length, 0);
  });
}
for (const behavior of ['prepared-elsewhere', 'issued-elsewhere', 'session-changed']) {
  const f = fixture({ behavior });
  await check(`concurrent-request-${behavior}`, route, f.options, async page => {
    await submitInspection(page);
    if (behavior === 'session-changed') await shown(page.getByRole('button', { name: 'Verify receipt', exact: true }));
    else await shown(page.getByText('Receipt verified', { exact: true }));
    await hidden(page.getByRole('heading', { name: 'Receipt inspection recorded', exact: true }));
    assert.equal(f.state.posts.length, 1);
  });
}
{
  const f = fixture({ behavior: 'patch-uncertain-refresh' });
  await check('uncertain-correction-with-failed-refresh-keeps-unsaved-draft', route, f.options, async page => {
    await page.getByRole('button', { name: 'Correct certificate details', exact: true }).click();
    await page.getByLabel('Receipt number', { exact: true }).fill('OR-KEPT-DRAFT');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await shown(page.getByText(/Latest information could not be refreshed/));
    assert.equal(await page.getByLabel('Receipt number', { exact: true }).inputValue(), 'OR-KEPT-DRAFT');
    assert.equal(await page.getByRole('button', { name: 'Save changes', exact: true }).isDisabled(), true);
    assert.equal(f.state.patches.length, 1); assert.equal(f.state.posts.length, 0);
  });
}
for (const variant of ['CURRENT_STUDENT', 'GRADUATE']) {
  const item = receiptItem('MISSING', 'DORMANT'); item.variant = variant;
  const studentItem = structuredClone(item);
  for (const field of ['actions', 'receipt_identity', 'receipt_inspection', 'receipt_mutation_result', 'receipt_verification_result', 'initiated_by', 'student_institutional_id', 'cancellation', 'prepared_by', 'prepared_at']) delete studentItem[field];
  const account = { ...inspector, role: 'STUDENT', student_lifecycle_status: variant === 'CURRENT_STUDENT' ? 'CURRENT' : 'GRADUATED', capabilities: ['good_moral.request_self', 'good_moral.view_self', 'exit_interviews.view_self'] };
  const posts = [];
  await check(`student-${variant}-requests-without-receipt-and-sees-next-steps`, '/portal/good-moral/request', { handler: async ({ pathname, method, request, reply }) => {
    if (pathname === '/api/v1/auth/session') { await reply(session(account)); return true; }
    if (pathname === '/api/v1/good-moral/me/academic-context') { await reply({ status: 'ELIGIBLE', academic_classification: 'BACHELORS', year_level: 4 }); return true; }
    if (pathname === '/api/v1/exit-interviews/me/status') { await reply({ graduation_good_moral_blocked: false }); return true; }
    if (pathname === '/api/v1/good-moral/degree-options') { await reply({ items: ['Bachelor of Science'] }); return true; }
    if (pathname === `/api/v1/good-moral/me/${requestId}`) { await reply(studentItem); return true; }
    if (method === 'POST' && pathname === `/api/v1/good-moral/me/requests/${variant === 'CURRENT_STUDENT' ? 'current-student' : 'graduate'}`) { posts.push(JSON.parse(request.postData())); await reply(studentItem, 201); return true; }
    return false;
  } }, async page => {
    if (variant === 'CURRENT_STUDENT') await page.getByLabel('Semester', { exact: false }).selectOption('First Semester');
    else { await page.getByLabel('Degree').fill('Bachelor of Science'); await page.getByLabel('Graduation date').fill('2020-06-30'); }
    await page.getByRole('button', { name: 'Submit request', exact: true }).click();
    await page.waitForURL(`**/portal/good-moral/${requestId}`);
    await shown(page.getByRole('heading', { name: 'Next steps', exact: true }));
    await shown(page.getByText(/Pay the applicable certificate fee at UCN Cashier/));
    assert.equal(posts.length, 1); assert.ok(Object.keys(posts[0]).every(k => !/receipt|payment|verification/.test(k)));
    await hidden(page.getByRole('button', { name: 'Verify receipt', exact: true }));
    assert.doesNotMatch(await page.locator('body').innerText(), /Inspector account reference|Receipt change history|DORMANT|ACTIVE|Fee policy|₱80/);
  });
}
{
  const f = fixture({ item: receiptItem('VERIFIED') });
  await check('own-request-history-is-labeled-metadata-with-no-global-lookup', route, f.options, async (page, browserFixture) => {
    const disclosure = page.locator('details').filter({ hasText: 'Receipt change history' });
    assert.equal(await disclosure.getAttribute('open'), null);
    await disclosure.locator('summary').click();
    await shown(disclosure.getByText(/Earlier receipt contents/)); await shown(disclosure.getByText(/Recorder account reference/));
    assert.equal(browserFixture.requests.filter(r => /accounts|receipt.*search/.test(r.pathname)).length, 0);
  });
}
await finish();
