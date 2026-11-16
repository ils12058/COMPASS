// Intercepted synthetic data only; covers the document gate and College-filtered editor.
import assert from 'node:assert/strict';
import { createBrowserHarness } from './support/browser-harness.mjs';
import { inventoryFixture } from './support/inventory-guide-fixture.mjs';
import { receiptItem } from './support/good-moral-receipt-fixtures.mjs';
import { counselor, requestId } from './support/good-moral-print-fixtures.mjs';
const h = await createBrowserHarness('gm-inventory-academic-basis');
const college = { id: 'synthetic-college', code: 'TEST', name: 'Synthetic College' };
const other = { id: 'other-college', code: 'OTHER', name: 'Other College' };
const program = (id, college) => ({ id, code: id, name: `Bachelor ${id}`, college, is_active: true, academic_classification: 'BACHELORS', applicable_year_levels: [1,2,3,4] });
for (const savedMismatch of [false, true]) {
  const f = inventoryFixture({ currentCollege: college, programs: [program('HOME', college), program('OTHER', other)], savedProgram: savedMismatch ? { id: 'OTHER', code: 'OTHER', name: 'Bachelor OTHER', college_id: other.id } : null });
  await h.check(`Inventory choices match College; saved mismatch ${savedMismatch}`, '/portal/inventory/current', { handler: f.handler, mobile: savedMismatch }, async page => {
    if (savedMismatch) await page.locator('#inventory-section-select').selectOption('education');
    else await page.getByRole('button', { name: 'Educational background', exact: true }).click();
    const select = page.locator('#inventory-program');
    await h.shown(select);
    const options = await select.locator('option').allTextContents();
    assert.ok(options.some(text => text.includes('HOME')));
    assert.equal(options.filter(text => text.includes('OTHER')).length, savedMismatch ? 1 : 0);
    if (savedMismatch) { assert.ok(options.some(text => text.includes('saved value; another College'))); await h.shown(page.getByText('Choose a Program from your College. If your College has changed, ask the Guidance Office.', { exact: true })); }
    await select.selectOption('HOME');
    await h.noHorizontalOverflow(page);
    await h.screenshot(page, `inventory-college-options-${savedMismatch ? 'saved-mismatch-phone' : 'desktop'}`);
  });
}
for (const registrar of [false, true]) {
  const item = { ...receiptItem('VERIFIED'), variant: 'GRADUATE', graduation_basis: registrar ? 'REGISTRAR_RECORD' : 'DOCUMENT_CHECK', graduated_college: registrar ? college : null, graduation_verification_source: registrar ? 'Synthetic Registrar list' : null, graduation_verified_at: registrar ? '2026-07-01T00:00:00Z' : null, document_checked_at: null, document_checked_by_id: null };
  const bodies = [];
  await h.check(`Graduate staff basis and Prepare gate ${registrar ? 'Registrar' : 'documents'}`, `/portal/good-moral/${requestId}`, {
    overrides: { '/api/v1/auth/session': { user: { ...counselor, capabilities: [...counselor.capabilities, 'good_moral.prepare'] }, session: { id: 'synthetic', expires_at: '2099-01-01T00:00:00Z', is_current: true } } },
    handler: async ({ pathname, method, request, reply }) => {
      if (pathname === `/api/v1/good-moral/requests/${requestId}/prepare` && method === 'POST') { bodies.push(JSON.parse(request.postData())); item.status = 'READY_FOR_ISSUANCE'; item.actions.can_prepare = false; await reply(item); return true; }
      if (pathname === `/api/v1/good-moral/requests/${requestId}`) { await reply(item); return true; }
      return false;
    },
  }, async page => {
    await h.shown(page.getByText(registrar ? "Confirmed from the Registrar's record" : "Not in the Registrar's record. Check the diploma or TOR before preparing.", { exact: true }));
    if (registrar) await h.shown(page.getByText('Synthetic Registrar list', { exact: true }));
    await page.getByRole('button', { name: 'Mark ready for issuance', exact: true }).click();
    const dialog = page.getByRole('alertdialog');
    const button = dialog.getByRole('button', { name: 'Mark ready', exact: true });
    const checkbox = dialog.getByRole('checkbox', { name: 'I checked the diploma or TOR', exact: true });
    if (registrar) assert.equal(await checkbox.count(), 0);
    else { assert.equal(await button.isDisabled(), true); await checkbox.check(); assert.equal(await button.isDisabled(), false); }
    await h.screenshot(page, registrar ? 'registrar-prepare' : 'document-check-prepare');
    await button.click();
    await h.shown(dialog.getByRole('heading', { name: 'Ready for issuance', exact: true }));
    assert.equal(bodies[0].diploma_tor_checked, !registrar);
  });
}
await h.finish();
