import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { withNextRouter } from './support/next-router.mjs';
import { GoodMoralDetailPage } from '../src/features/good-moral/good-moral-detail-page.tsx';
import { PortalSessionProvider } from '../src/features/portal/components/portal-session.tsx';
import { getGoodMoralGetRequestQueryKey, getGoodMoralGetMyRequestQueryKey } from '../src/lib/api/generated/good-moral/good-moral.ts';
import { openGoodMoralPrintPreview } from '../src/features/good-moral/good-moral-print-preview.ts';
import { certificate, counselor, requestId } from './support/good-moral-print-fixtures.mjs';

function render(item, account = counselor) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const key = account.role === 'STUDENT' ? getGoodMoralGetMyRequestQueryKey(requestId) : getGoodMoralGetRequestQueryKey(requestId);
  client.setQueryData(key, { data: item, status: 200, headers: {} });
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user: account } }, h(GoodMoralDetailPage, { requestId })))));
  client.clear();
  return html;
}
for (const variant of ['CURRENT_STUDENT', 'GRADUATE']) {
  test(`${variant}: only issued authorized records offer print/download with frozen metadata`, () => {
    const html = render(certificate('ISSUED', variant));
    assert.match(html, /Print certificate/);
    assert.match(html, /Download certificate/);
    assert.match(html, /Frozen Issuer Name/);
    assert.match(html, variant === 'CURRENT_STUDENT' ? /UCN-OP-GCO-01F4/ : /UCN-OP-GCO-01F6/);
    assert.match(html, /physical signature and dry seal/);
    assert.doesNotMatch(html, /Issue certificate|printed successfully/);
    for (const status of ['REQUESTED', 'READY_FOR_ISSUANCE', 'CANCELLED']) assert.doesNotMatch(render(certificate(status, variant)), /Print certificate|Finalized certificate PDF/);
    const blocked = certificate('ISSUED', variant);
    blocked.actions.can_download = false;
    assert.doesNotMatch(render(blocked), /Print certificate|Download certificate/);
  });
}
test('Student download stays self-service with no new printing or automatic PDF retrieval', () => {
  const student = { ...counselor, role: 'STUDENT', student_lifecycle_status: 'CURRENT', capabilities: ['good_moral.view_self'] };
  const html = render(certificate('ISSUED'), student);
  assert.match(html, /Download certificate|physical signature and dry seal/);
  assert.doesNotMatch(html, /Print certificate|Preparing certificate PDF|Finalized certificate PDF/);
});

for (const result of ['opened', 'blocked', 'throws']) {
  test(`print preview ${result}: direct open and independent URL lifetime`, () => {
    const previousWindow = globalThis.window;
    const create = URL.createObjectURL;
    const revoke = URL.revokeObjectURL;
    const released = [];
    const calls = [];
    const blob = new Blob(['%PDF-synthetic'], { type: 'application/pdf' });
    const preview = { closed: false, opener: 'parent' };
    let interval;
    try {
      URL.createObjectURL = value => { assert.equal(value, blob); return 'blob:synthetic'; };
      URL.revokeObjectURL = value => released.push(value);
      globalThis.window = {
        open: (...args) => { calls.push(args); if (result === 'throws') throw new Error('blocked'); return result === 'blocked' ? null : preview; },
        setInterval: callback => { interval = callback; return 42; },
        clearInterval: id => assert.equal(id, 42),
      };
      assert.equal(openGoodMoralPrintPreview(blob), result === 'opened');
      assert.deepEqual(calls, [['blob:synthetic', '_blank']]);
      if (result === 'opened') {
        assert.equal(preview.opener, null);
        interval();
        assert.deepEqual(released, [], 'Keep the PDF alive through loading and print cancellation');
        preview.closed = true;
        interval();
      } else assert.equal(interval, undefined);
      assert.deepEqual(released, ['blob:synthetic']);
    } finally {
      globalThis.window = previousWindow;
      URL.createObjectURL = create;
      URL.revokeObjectURL = revoke;
    }
  });
}
