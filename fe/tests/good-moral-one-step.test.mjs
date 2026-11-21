import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { GoodMoralOneStepPreparation } from "../src/features/good-moral/good-moral-one-step-preparation.tsx";
import { GoodMoralOperationalList } from "../src/features/good-moral/good-moral-operational-list.tsx";
import { AssistedAcademicPrefill } from "../src/features/good-moral/good-moral-assisted-academic.tsx";
import { getGoodMoralAccess } from "../src/features/good-moral/good-moral-access.ts";
import { getGoodMoralListRequestsQueryKey } from "../src/lib/api/generated/good-moral/good-moral.ts";
import { institutionalDateInputValue } from "../src/lib/institutional-time.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const filters = { search: "", formRevisionId: "", variant: "", status: "", page: 1 };
const counselor = {
  id: "counselor", role: "COUNSELOR", first_name: "Actual", last_name: "Counselor",
  email: "counselor@example.test", student_lifecycle_status: null, designations: [],
  capabilities: ["good_moral.view", "good_moral.prepare", "good_moral.issue", "good_moral.manage", "academic_years.view", "institutional_forms.view"],
};
const goa = { ...counselor, id: "staff", role: "GUIDANCE_OFFICE_ASSISTANT", capabilities: ["good_moral.view", "good_moral.prepare", "academic_years.view", "institutional_forms.view"] };

const actions = { request_version: "2026-10-05T00:00:00.123456+00:00", preparation_version: null, can_correct: true, can_prepare: true, can_issue: false, can_cancel: false, can_download: false, correction_fields: [] };
const oneStepItem = {
  id: "request", variant: "CURRENT_STUDENT", status: "REQUESTED", applicant_name: "Student Example",
  graduation_basis: null, official_receipt_number: "", official_receipt_date: null, official_receipt_amount: null,
  receipt_fee: { expected_amount: "80.00", currency: "PHP" }, receipt_identity: null, receipt_inspection: null, actions,
};

function renderOneStep(request) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(GoodMoralOneStepPreparation, { item: request, confirmed: true, onRefresh: async () => request })));
  client.clear();
  return html;
}

function renderList(user, rows) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  client.setQueryData(getGoodMoralListRequestsQueryKey({ page: 1 }), ok({ items: rows, page: 1, page_size: 20, has_next: false, ordering: "OLDEST_FIRST", filter_options: { form_revisions: [] } }));
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(GoodMoralOperationalList, { filters })))));
  client.clear();
  return html;
}

const row = (status) => ({
  id: `row-${status}`, applicant_name: "Ready Student", variant: "CURRENT_STUDENT", status,
  academic_year: { id: "year", label: "2026-2027" }, created_at: "2026-10-05T00:00:00Z", issued_at: null,
  official_receipt_number: "OR-1", student_institutional_id: "2026-1", updated_at: "2026-10-05T01:00:00Z",
  prepared_at: "2026-10-05T01:00:00Z", cancelled_at: null, initiation_origin: "GCO_ASSISTED",
});

test("one-step panel fills the receipt date with today and the amount with the expected fee", () => {
  const html = renderOneStep(oneStepItem);
  const today = institutionalDateInputValue();
  assert.match(html, /Save and mark ready/);
  assert.ok(html.includes('id="good-moral-one-step-receipt-number"'));
  assert.ok(html.includes('id="good-moral-one-step-attestation"'));
  assert.ok(html.includes(`value="${today}"`), "receipt date defaults to institutional today");
  assert.ok(html.includes('value="80.00"'), "receipt amount defaults to the expected fee");
  // A current Student needs no graduate document check.
  assert.doesNotMatch(html, /good-moral-one-step-document-check/);
});

test("one-step panel keeps existing receipt values and requires the graduate document check only when needed", () => {
  const recorded = { ...oneStepItem, official_receipt_number: "OR-9", official_receipt_date: "2026-01-15", official_receipt_amount: "80.00" };
  const html = renderOneStep(recorded);
  assert.ok(html.includes('value="OR-9"'));
  assert.ok(html.includes('value="2026-01-15"'));
  const graduate = { ...oneStepItem, variant: "GRADUATE", graduation_basis: "DIPLOMA_TOR" };
  assert.match(renderOneStep(graduate), /good-moral-one-step-document-check/);
  const registrar = { ...oneStepItem, variant: "GRADUATE", graduation_basis: "REGISTRAR_RECORD" };
  assert.doesNotMatch(renderOneStep(registrar), /good-moral-one-step-document-check/);
});

test("one-step panel does not offer issuance or cancellation", () => {
  const html = renderOneStep(oneStepItem);
  assert.doesNotMatch(html, /Issue certificate|Cancel request/);
});

test("Counselor gets Issue directly on ready rows; GOA and non-ready rows do not", () => {
  assert.equal(getGoodMoralAccess(counselor).canIssue, true);
  assert.equal(getGoodMoralAccess(goa).canIssue, false);
  const readyHtml = renderList(counselor, [row("READY_FOR_ISSUANCE")]);
  assert.match(readyHtml, /Actions/);
  assert.ok(readyHtml.includes(">Issue</button>"), "ready row offers Issue");
  // The row action is not the detail's full button label.
  assert.doesNotMatch(readyHtml, /Issue certificate/);
  assert.doesNotMatch(renderList(goa, [row("READY_FOR_ISSUANCE")]), /Actions|>Issue<\/button>/);
  assert.doesNotMatch(renderList(counselor, [row("REQUESTED")]), />Issue<\/button>/);
  assert.doesNotMatch(renderList(counselor, [row("ISSUED")]), />Issue<\/button>/);
});

test("assisted current Student prefill shows recorded academic details and leaves gaps blank", () => {
  const context = { year_level: "4th Year", college: "College of Computing", course: "BS Computing", major: "Software", academic_year: "2026-2027" };
  const html = renderToStaticMarkup(h(AssistedAcademicPrefill, { context }));
  assert.ok(html.includes('id="assisted-college"'));
  assert.ok(html.includes('value="College of Computing"'));
  assert.ok(html.includes('value="BS Computing"'));
  assert.ok(html.includes('value="Software"'));
  assert.ok(html.includes('value="2026-2027"'));
  const empty = renderToStaticMarkup(h(AssistedAcademicPrefill, { context: { year_level: null, college: null, course: null, major: null, academic_year: null } }));
  assert.ok(empty.includes('placeholder="Not recorded"'));
  assert.doesNotMatch(empty, /value="College of Computing"/);
  const missing = renderToStaticMarkup(h(AssistedAcademicPrefill, {}));
  assert.ok(missing.includes('placeholder="Not recorded"'));
});