import assert from 'node:assert/strict';
import test from 'node:test';
import { graduateBasisMessage, inventoryCollegeMismatchStaffMessage } from '../src/features/good-moral/good-moral-graduation-presentation.ts';
import { goodMoralErrorMessage } from '../src/features/good-moral/good-moral-shared.tsx';
import { assistedCreationError } from '../src/features/good-moral/good-moral-assisted-request.ts';
import { inventoryErrorMessage } from '../src/features/inventory/inventory-shared.tsx';
import { CompassApiError } from '../src/lib/api/errors.ts';
const error = code => new CompassApiError({ status: 409, body: { error: { code, message: 'PRIVATE-DIAGNOSTIC-SENTINEL' } }, headers: {}, method: 'POST', url: '/api/v1/synthetic' });
test('Registrar and document basis tell each reader their next action', () => {
  assert.equal(graduateBasisMessage('REGISTRAR_RECORD'), "Confirmed from the Registrar's record");
  assert.equal(graduateBasisMessage('DOCUMENT_CHECK'), 'Bring your diploma or TOR when you present your Official Receipt.');
  assert.equal(graduateBasisMessage('DOCUMENT_CHECK', true), "Not in the Registrar's record. Check the diploma or TOR before preparing.");
});
test('Inventory mismatch maps to a bounded Student message', () => {
  assert.equal(inventoryErrorMessage(error('inventory_program_college_mismatch'), 'fallback'), 'Choose a Program from your College. If your College has changed, ask the Guidance Office.');
  assert.equal(inventoryErrorMessage(error('unknown_private_code'), 'fallback'), 'fallback');
});
test('Good Moral mismatch gives Students and staff the appropriate correction route', () => {
  assert.equal(goodMoralErrorMessage(error('good_moral_inventory_college_mismatch'), 'fallback'), "Your Inventory's College doesn't match your current College. Ask the Guidance Office to correct it.");
  assert.equal(assistedCreationError(error('good_moral_inventory_college_mismatch')), inventoryCollegeMismatchStaffMessage);
});
test('Prepare document gate never displays an unbounded backend diagnosis', () => {
  assert.equal(goodMoralErrorMessage(error('good_moral_graduate_document_check_required'), 'fallback'), 'Check the diploma or TOR and confirm it before preparing.');
});
