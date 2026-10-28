// Minimal correction-contract compatibility; synthetic local API only, no inspection/fee UX.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { certificate, counselor, requestId } from './support/good-moral-print-fixtures.mjs';

const { check, shown, finish } = await createBrowserHarness('good-moral-receipt-correction');
const path = `/api/v1/good-moral/requests/${requestId}`;
const route = `/portal/good-moral/${requestId}`;
const originalRevision = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const nextRevision = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const originalVersion = '2026-10-24T01:00:00.000000+00:00';
const nextVersion = '2026-10-24T01:01:00.000000+00:00';
const account = { ...counselor, capabilities: [...counselor.capabilities, 'good_moral.prepare'] };
function fixture(mode = 'ACTIVE', behavior = 'success') {
  let item = { ...certificate('REQUESTED', 'GRADUATE'), prepared_at: null, prepared_by: null };
  item.actions = { ...item.actions, request_version: originalVersion, can_correct: true, can_prepare: true, can_issue: false, correction_fields: ['official_receipt_number', 'official_receipt_date', 'official_receipt_amount', 'major'] };
  item.receipt_identity = { ledger_mode: mode, revision_id: originalRevision, identity_state: mode === 'ACTIVE' ? 'BOUND' : 'DORMANT', history: [] };
  const bodies = [];
  return {
    bodies,
    options: {
      overrides: { '/api/v1/auth/session': { user: account, session: { id: 'synthetic', expires_at: '2099-01-01T00:00:00Z', is_current: true } } },
      handler: async ({ pathname, method, request, reply }) => {
        if (pathname !== path) return false;
        if (method === 'GET') { await reply(item); return true; }
        if (method === 'PATCH') {
          const body = JSON.parse(request.postData()); bodies.push(body);
          if (behavior === 'conflict') { await reply({ error: { code: 'good_moral_receipt_conflict', message: 'PRIVATE-DIAGNOSTIC' } }, 409); return true; }
          if (behavior === 'stale' && bodies.length === 1) {
            item = { ...item, official_receipt_number: 'OR-OTHER-OPERATOR', actions: { ...item.actions, request_version: nextVersion }, receipt_identity: { ...item.receipt_identity, revision_id: nextRevision } };
            await reply({ error: { code: 'good_moral_receipt_changed', message: 'PRIVATE-DIAGNOSTIC' } }, 409); return true;
          }
          item = { ...item, official_receipt_number: body.official_receipt_number, actions: { ...item.actions, request_version: nextVersion }, receipt_identity: { ...item.receipt_identity, revision_id: nextRevision } };
          await reply(behavior === 'uncertain' ? { error: { code: 'internal_error', message: 'PRIVATE-DIAGNOSTIC' } } : item, behavior === 'uncertain' ? 500 : 200);
          return true;
        }
        return false;
      },
    },
  };
}
async function enter(page) {
  await page.getByRole('button', { name: 'Correct certificate details', exact: true }).click();
  await page.getByLabel('Receipt number', { exact: true }).fill('OR-MY-DRAFT');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
}
for (const mode of ['DORMANT', 'ACTIVE']) {
  const f = fixture(mode);
  await check(`${mode} preserves correction contract`, route, f.options, async page => {
    await enter(page);
    await page.getByRole('button', { name: 'Correct certificate details', exact: true }).waitFor();
    assert.equal(f.bodies.length, 1);
    if (mode === 'ACTIVE') {
      assert.equal(f.bodies[0].expected_resource_version, originalVersion);
      assert.equal(f.bodies[0].expected_receipt_revision, originalRevision);
      assert.match(f.bodies[0].receipt_operation_id, /^[0-9a-f-]{36}$/);
    } else assert.deepEqual(f.bodies[0], { official_receipt_number: 'OR-MY-DRAFT' });
  });
}
{
  const f = fixture('ACTIVE', 'stale');
  await check('stale receipt preserves draft and requires deliberate review', route, f.options, async page => {
    await enter(page);
    await shown(page.getByText(/Latest saved receipt: OR-OTHER-OPERATOR/));
    assert.equal(await page.getByLabel('Receipt number', { exact: true }).inputValue(), 'OR-MY-DRAFT');
    assert.equal(await page.getByRole('button', { name: 'Save changes', exact: true }).isDisabled(), true);
    assert.equal(f.bodies.length, 1);
    await page.getByRole('button', { name: 'Continue with my reviewed draft', exact: true }).click();
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('button', { name: 'Correct certificate details', exact: true }).waitFor();
    assert.equal(f.bodies.length, 2);
    assert.equal(f.bodies[1].expected_resource_version, nextVersion);
    assert.equal(f.bodies[1].expected_receipt_revision, nextRevision);
    assert.notEqual(f.bodies[0].receipt_operation_id, f.bodies[1].receipt_operation_id);
    assert.doesNotMatch(await page.locator('body').innerText(), /PRIVATE-DIAGNOSTIC/);
  });
}
{
  const f = fixture('ACTIVE', 'uncertain');
  await check('uncertain committed correction refreshes without automatic replay', route, f.options, async page => {
    await enter(page);
    await shown(page.getByText(/Latest saved receipt: OR-MY-DRAFT/));
    await page.getByRole('button', { name: 'Continue with my reviewed draft', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Save changes', exact: true }).isDisabled(), true);
    assert.equal(f.bodies.length, 1);
  });
}
{
  const f = fixture('ACTIVE', 'conflict');
  await check('duplicate conflict keeps input and displays safe copy', route, f.options, async page => {
    await enter(page);
    await shown(page.getByRole('alert').filter({ hasText: 'Official Receipt number already recorded' }));
    assert.equal(await page.getByLabel('Receipt number', { exact: true }).inputValue(), 'OR-MY-DRAFT');
    assert.doesNotMatch(await page.locator('body').innerText(), /PRIVATE-DIAGNOSTIC/);
  });
}
await finish();
