import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoodMoralReceiptSection } from '../src/features/good-moral/good-moral-receipt-section.tsx';
import { GoodMoralStudentNextSteps } from '../src/features/good-moral/good-moral-student-next-steps.tsx';
import { GoodMoralCorrectionForm } from '../src/features/good-moral/good-moral-correction-form.tsx';
import { receiptStatuses, receiptBlockerMessage, receiptAmount } from '../src/features/good-moral/receipt-presentation.ts';
import { inspectionReview, sameReceiptReview, reviewedInspectionIsCurrent } from '../src/features/good-moral/receipt-review.ts';
import { receiptItem, revisionId, verificationId, inspectorId, version, nextVersion } from './support/good-moral-receipt-fixtures.mjs';
import { withNextRouter } from './support/next-router.mjs';
function render(item, props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(GoodMoralReceiptSection, { item, confirmed: true, editorOpen: false, onRefresh: async () => item, onActivityChange() {}, ...props })));
  client.clear(); return html;
}
for (const status of Object.keys(receiptStatuses)) test(`backend ${status} has accurate text`, () => {
  const item = receiptItem(status); const html = render(item);
  assert.ok(html.includes(receiptStatuses[status].label));
  assert.equal(html.includes('>Verify receipt</button>'), item.receipt_inspection.can_verify);
  if (status !== 'VERIFIED') assert.doesNotMatch(html, />Receipt verified</);
});
for (const mode of ['DORMANT', 'FENCED']) test(`${mode} offers no inspection and no invented approved amount`, () => {
  const html = render(receiptItem('LEGACY_UNKNOWN', mode));
  assert.doesNotMatch(html, />Verify receipt<\/button>|Approved expected amount/);
  assert.match(html, mode === 'DORMANT' ? /not enabled here/ : /temporarily paused/);
});
test('backend can_verify=false wins even for an otherwise complete receipt', () => {
  const item = receiptItem(); item.receipt_inspection.can_verify = false;
  assert.doesNotMatch(render(item), />Verify receipt<\/button>/);
});
for (const props of [{ confirmed: false }, { editorOpen: true }]) test(`inspection blocked for ${JSON.stringify(props)}`, () => assert.doesNotMatch(render(receiptItem(), props), />Verify receipt<\/button>/));
test('provenance retains backend inspector ID and institutional time', () => {
  const html = render(receiptItem('VERIFIED'));
  assert.match(html, /Inspector account reference/); assert.ok(html.includes(inspectorId)); assert.match(html, /Inspected at/);
  assert.doesNotMatch(html, /Cashier confirmed|Payment verified|cleared funds have/);
});
test('metadata history is a disclosure and never invents old receipt contents', () => {
  const html = render(receiptItem()); assert.match(html, /<details/); assert.match(html, /Receipt change history/);
  assert.match(html, /Earlier receipt contents.*not included/); assert.match(html, /Recorder account reference/);
});
test('expected fee is displayed only from the approved backend projection', () => {
  const item = receiptItem('POLICY_UNAVAILABLE'); assert.doesNotMatch(render(item), /Approved expected amount/);
  assert.match(render(receiptItem()), /Approved expected amount/);
  assert.equal(receiptAmount('9999999999.99', 'PHP').replace(/[^0-9.]/g, ''), '9999999999.99');
});
test('fee mismatch gives a review blocker without suggesting editing away the printed amount', () => assert.match(receiptBlockerMessage('good_moral_receipt_fee_mismatch'), /keep the amount printed/));
test('inspection intent contains only the exact generated mutation fields', () => {
  const item = receiptItem(); const review = inspectionReview(item, verificationId);
  assert.deepEqual(review.payload, { expected_resource_version: version, assignment_id: revisionId, operation_id: verificationId, method: 'PHYSICAL_OR_INSPECTION' });
  item.official_receipt_number = 'CHANGED'; assert.equal(review.item.official_receipt_number, 'OR-SYNTHETIC-000125');
});
test('same intent remains stable while a stale resource or revision requires review', () => {
  const item = receiptItem(); const review = inspectionReview(item, verificationId);
  assert.ok(sameReceiptReview(item, review)); item.actions.request_version = nextVersion; assert.equal(sameReceiptReview(item, review), false);
  item.actions.request_version = version; item.receipt_identity.revision_id = verificationId; assert.equal(sameReceiptReview(item, review), false);
});
test('no success for invalidated or replaced inspection evidence', () => {
  const review = inspectionReview(receiptItem(), verificationId); const current = receiptItem('VERIFIED');
  assert.ok(reviewedInspectionIsCurrent(current, review)); current.receipt_inspection.status = 'NEEDS_VERIFICATION'; assert.equal(reviewedInspectionIsCurrent(current, review), false);
  current.receipt_inspection.status = 'VERIFIED'; current.receipt_identity.revision_id = verificationId; assert.equal(reviewedInspectionIsCurrent(current, review), false);
});
test('Student next steps contain no approved amount, inspection authority or online payment', () => {
  const html = renderToStaticMarkup(h(GoodMoralStudentNextSteps)); assert.match(html, /UCN Cashier/); assert.match(html, /physical Official Receipt/); assert.match(html, /Guidance and Counseling Office/);
  assert.doesNotMatch(html, /80|Verify receipt|ledger|policy|<input|<form|upload/);
});
test('active correction avoids an unconditional optional receipt label and never attests to inspection', () => {
  const client = new QueryClient();
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(GoodMoralCorrectionForm, { item: receiptItem(), open: true, onRefresh: async () => receiptItem(), onClose() {} }))));
  assert.doesNotMatch(html, /Official Receipt <span[^>]*>\(optional\)/); assert.match(html, /Saving these details does not record a physical inspection/); client.clear();
});
