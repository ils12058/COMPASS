import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { PrivacyGovernanceNavigation } from "../src/features/privacy-governance/privacy-governance-navigation.tsx";
import { canViewRetention, canManageRetention, canApproveDisposition, hasPrivacyGovernanceWorkspace } from "../src/features/privacy-governance/privacy-governance-access.ts";
import { RetentionPage } from "../src/features/privacy-governance/retention/retention-page.tsx";
import { RetentionRuleEditor } from "../src/features/privacy-governance/retention/retention-rule-editor.tsx";
import { DispositionCasePage } from "../src/features/privacy-governance/retention/disposition-case-page.tsx";
import { canConfirmDispositionReview, dispositionConsequence } from "../src/features/privacy-governance/retention/retention-shared.tsx";
import { getPrivacyGovernanceGetDispositionCaseQueryKey, getPrivacyGovernanceRetentionCategoriesQueryKey, getPrivacyGovernanceRetentionSummaryQueryKey, getPrivacyGovernanceListDispositionCasesQueryKey } from "../src/lib/api/generated/privacy-governance/privacy-governance.ts";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { withNextRouter } from "./support/next-router.mjs";

const view = "privacy_governance.retention.view";
const manage = "privacy_governance.retention.manage";
const approve = "privacy_governance.retention.approve";
const caseId = "dd93953c-e82b-4d07-b3cf-79b204cdb0f3";
const ruleId = "84176b7a-7337-4123-a8f0-f084d7a0b970";
const reviewed = { id: caseId, rule_id: ruleId, rule_code: "TEST", rule_revision: 2, category: "GRADUATE_TRACER", action: "ANONYMIZE", affected_count: 1, eligible_at: "2026-09-01T00:00:00Z", state: "READY", blocker: null, revision: 1, approved_at: null, started_at: null, completed_at: null, attempts: 0, manual_retries: 0, holds: [] };
const category = { category: "GRADUATE_TRACER", label: "Graduate Tracer", trigger: "SUBMITTED_AT", action: "ANONYMIZE" };

function render(component, { capabilities = [view], records = [], errors = [], pathname = "/portal/privacy/retention", params = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const [key, data] of records) client.setQueryData(key, { data, status: 200, headers: {} });
  for (const [key, error] of errors) client.getQueryCache().find({ queryKey: key }).setState({ status: "error", error });
  const element = createElement(QueryClientProvider, { client }, createElement(PortalSessionProvider, { value: { user: { capabilities } } }, createElement(UnsavedChangesProvider, null, component)));
  const html = renderToStaticMarkup(withNextRouter(element, { pathname, params }));
  client.clear();
  return html;
}

test("retention authority is separate from notice authority and each action is capability-based", () => {
  assert.equal(canViewRetention({ capabilities: [view] }), true);
  assert.equal(canManageRetention({ capabilities: [view] }), false);
  assert.equal(canApproveDisposition({ capabilities: [view, manage] }), false);
  assert.equal(canApproveDisposition({ capabilities: [view, approve] }), true);
  assert.equal(hasPrivacyGovernanceWorkspace({ capabilities: [view] }), true);
  assert.equal(hasPrivacyGovernanceWorkspace({ capabilities: [] }), false);
});

test("navigation includes only authorized destinations, with a named current link", () => {
  const retentionOnly = render(createElement(PrivacyGovernanceNavigation));
  assert.match(retentionOnly, /Retention &amp; Disposition/);
  assert.doesNotMatch(retentionOnly, /Privacy Notices|Privacy &amp; Security Activity/);
  assert.match(retentionOnly, /aria-current="page"/);
  const noticesOnly = render(createElement(PrivacyGovernanceNavigation), { capabilities: ["privacy_governance.view"] });
  assert.match(noticesOnly, /Privacy Notices/);
  assert.doesNotMatch(noticesOnly, /Retention &amp; Disposition/);
});

test("a view-only case is read-only and never renders injected protected source details", () => {
  const html = render(createElement(DispositionCasePage), { params: { caseId }, records: [[getPrivacyGovernanceGetDispositionCaseQueryKey(caseId), { ...reviewed, student_name: "SECRET PERSON", email: "secret@example.edu", survey_answers: "SECRET ANSWERS", transcript: "SECRET CONTENT" }]] });
  assert.match(html, /Needs review|Reviewed case/);
  assert.doesNotMatch(html, /Approve disposition|Place hold|SECRET|secret@example/);
  assert.match(html, /Retention boundary/);
});

test("approval explains irreversible identity removal and provider deletion without showing source data", () => {
  assert.match(dispositionConsequence({ category: "GRADUATE_TRACER" }), /aggregate survey information will remain/i);
  assert.match(dispositionConsequence({ category: "GRADUATE_TRACER" }), /cannot be restored/i);
  assert.match(dispositionConsequence({ category: "ECOUNSELING_TRANSCRIPT" }), /Consent decisions.*remain/);
  const html = render(createElement(DispositionCasePage), { capabilities: [view, approve], params: { caseId }, records: [[getPrivacyGovernanceGetDispositionCaseQueryKey(caseId), reviewed]] });
  assert.match(html, /Approve disposition/);
  assert.doesNotMatch(html, /Place hold/);
});

test("stale or unconfirmed state disables approval and requires review again", () => {
  assert.equal(canConfirmDispositionReview(4, 4, true), true);
  assert.equal(canConfirmDispositionReview(4, 5, true), false);
  assert.equal(canConfirmDispositionReview(4, 4, false), false);
});

test("queued processing is shown truthfully and cannot be approved again", () => {
  const html = render(createElement(DispositionCasePage), { capabilities: [view, approve], params: { caseId }, records: [[getPrivacyGovernanceGetDispositionCaseQueryKey(caseId), { ...reviewed, state: "QUEUED", approved_at: "2026-10-04T00:00:00Z" }]] });
  assert.match(html, /Queued/);
  assert.doesNotMatch(html, /Verified completion|Approve disposition|COMPLETED/);
});

test("hold status and history are visible without an approval path", () => {
  const html = render(createElement(DispositionCasePage), { capabilities: [view, manage, approve], params: { caseId }, records: [[getPrivacyGovernanceGetDispositionCaseQueryKey(caseId), { ...reviewed, state: "ON_HOLD", holds: [{ id: caseId, reason: "Institutional review reference", placed_at: "2026-10-04T00:00:00Z", released_at: null }] }]] });
  assert.match(html, /On hold|Release hold|Hold history/);
  assert.match(html, /does not approve disposition/);
  assert.doesNotMatch(html, /Approve disposition/);
});

test("rule creation uses backend-supported categories and starts with an empty duration", () => {
  const html = render(createElement(RetentionRuleEditor, { creating: true }), { capabilities: [view, manage], records: [[getPrivacyGovernanceRetentionCategoriesQueryKey(), [category]]] });
  assert.match(html, /Graduate Tracer/);
  assert.doesNotMatch(html, /Individual Inventory|Routine Interview|Exit Interview/);
  assert.match(html, /id="rule-duration"[^>]*value=""/);
  assert.match(html, /Policy \/ basis reference/);
  assert.match(html, /label[^>]*for="rule-category"/);
});

test("loading and empty collections have distinct accessible states and responsive comparison tables", () => {
  const loading = render(createElement(RetentionPage));
  assert.match(loading, /Loading disposition cases/);
  assert.doesNotMatch(loading, /No disposition cases/);
  const records = [[getPrivacyGovernanceRetentionSummaryQueryKey(), { needs_review: 0, on_hold: 0, processing: 0, recently_completed: 0, categories: [] }], [getPrivacyGovernanceListDispositionCasesQueryKey({ page: 1, page_size: 20 }), { items: [], page: 1, page_size: 20, has_next: false }]];
  const empty = render(createElement(RetentionPage), { records });
  assert.match(empty, /No disposition cases/);
  const table = render(createElement(RetentionPage), { records: [records[0], [records[1][0], { items: [reviewed], page: 1, page_size: 20, has_next: false }]] });
  assert.match(table, /overflow-x-auto/);
  assert.match(table, /<table|<th/);
  assert.match(table, /for="case-category"/);
});


for (const status of [403, 503]) test(`case refresh ${status} hides lost authority or disables stale approval`, () => {
  const key = getPrivacyGovernanceGetDispositionCaseQueryKey(caseId);
  const error = new CompassApiError({ status, body: { error: { code: status === 403 ? "permission_denied" : "unavailable", message: "Safe failure" } }, headers: {}, method: "GET", url: "/api/v1/privacy/retention/cases/" + caseId });
  const html = render(createElement(DispositionCasePage), { capabilities: [view, approve], params: { caseId }, records: [[key, reviewed]], errors: [[key, error]] });
  if (status === 403) {
    assert.doesNotMatch(html, /Reviewed case|Approve disposition/);
    assert.match(html, /Retry|Safe failure|cannot/);
  } else {
    assert.match(html, /Reviewed case/);
    assert.match(html, /disabled=""[^>]*>Approve disposition/);
    assert.match(html, /Retry/);
  }
});
