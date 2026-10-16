import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { withNextRouter } from './support/next-router.mjs';
import { PortalSessionProvider } from '../src/features/portal/components/portal-session.tsx';
import { GoodMoralWorkspacePage } from '../src/features/good-moral/good-moral-page.tsx';
import { GoodMoralDetailPage } from '../src/features/good-moral/good-moral-detail-page.tsx';
import { GoodMoralAssistedRequestPage } from '../src/features/good-moral/good-moral-assisted-request-page.tsx';
import { getGoodMoralAccess } from '../src/features/good-moral/good-moral-access.ts';
import { goodMoralInitiationLabel } from '../src/features/good-moral/good-moral-shared.tsx';
import { assistedCreationError } from '../src/features/good-moral/good-moral-assisted-request.ts';
import { CompassApiError } from '../src/lib/api/errors.ts';
import { getGoodMoralGetMyRequestQueryKey, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey, getGoodMoralListMyRequestsQueryKey } from '../src/lib/api/generated/good-moral/good-moral.ts';
import { certificate } from './support/good-moral-print-fixtures.mjs';
const account = (role, capabilities = ['good_moral.view', 'good_moral.initiate']) => ({ id: 'actor', role, first_name: 'Synthetic', last_name: 'Staff', capabilities, designations: [], student_lifecycle_status: role === 'STUDENT' ? 'CURRENT' : null });
const filters = { search: '', formRevisionId: '', variant: '', status: '', page: 1 };
const item = { ...certificate('REQUESTED'), initiation_origin: 'GCO_ASSISTED', initiated_by: { id: 'actor', display_name: 'Operational Initiator' }, actions: { ...certificate('REQUESTED').actions, can_issue: false, can_prepare: false } };
function render(element, user) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const ok = data => ({ data, status: 200, headers: {} });
  client.setQueryData(getGoodMoralListRequestsQueryKey({ page: 1 }), ok({ items: [item], page: 1, page_size: 20, has_next: false, filter_options: { form_revisions: [] } }));
  client.setQueryData(getGoodMoralListMyRequestsQueryKey(), ok({ items: [item] }));
  client.setQueryData(getGoodMoralGetMyRequestQueryKey(item.id), ok(item));
  client.setQueryData(getGoodMoralGetRequestQueryKey(item.id), ok(item));
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, element))));
  client.clear(); return html;
}
for (const role of ['COUNSELOR', 'GUIDANCE_SERVICES_STAFF']) test(`${role} initiation access and queue entry point`, () => {
  const user = account(role);
  assert.equal(getGoodMoralAccess(user).canInitiate, true);
  assert.match(render(h(GoodMoralWorkspacePage, { filters }), user), /\/portal\/good-moral\/start/);
  const detail = render(h(GoodMoralDetailPage, { requestId: item.id }), user);
  assert.match(detail, /Operational Initiator/); assert.doesNotMatch(detail, /Issue certificate/);
});
for (const role of ['STUDENT', 'IT_ADMIN', 'INSTITUTIONAL_OFFICER']) test(`${role} cannot initiate even with capabilities`, () => {
  const user = account(role); assert.equal(getGoodMoralAccess(user).canInitiate, false);
  const html = render(h(GoodMoralAssistedRequestPage), user);
  assert.match(html, /Request initiation unavailable/); assert.doesNotMatch(html, /eligible-student-search/);
});
test('revoked capability hides the entry point', () => {
  for (const capabilities of [['good_moral.view'], ['good_moral.initiate']]) assert.equal(getGoodMoralAccess(account('COUNSELOR', capabilities)).canInitiate, false);
});
test('Student history and detail distinguish provenance and preserve cancellation', () => {
  const user = account('STUDENT', ['good_moral.view_self', 'good_moral.request_self']);
  const detail = render(h(GoodMoralDetailPage, { requestId: item.id }), user);
  for (const html of [render(h(GoodMoralWorkspacePage, { filters }), user), detail]) {
    assert.match(html, /Started by the Guidance and Counseling Office/); assert.doesNotMatch(html, /Operational Initiator/);
  }
  assert.match(detail, /Cancel request/);
  assert.equal(goodMoralInitiationLabel('STUDENT_SELF'), 'Requested by Student');
  assert.equal(goodMoralInitiationLabel('LEGACY_UNSPECIFIED'), 'Initiator not recorded');
});
test('prerequisite and uncertain errors remain safe and actionable', () => {
  for (const code of ['good_moral_inventory_required', 'good_moral_exit_interview_required', 'good_moral_not_found', 'permission_denied']) {
    assert.doesNotMatch(assistedCreationError(new CompassApiError({ status: 409, body: { error: { code, message: 'PRIVATE INTERNAL DIAGNOSTIC' } }, headers: {}, method: 'POST', url: '/synthetic' })), /PRIVATE/);
  }
  assert.match(assistedCreationError(new Error('network')), /Retry the same request/);
});
