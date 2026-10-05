import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { GoodMoralDetailPage } from "../src/features/good-moral/good-moral-detail-page.tsx";
import { GoodMoralCorrectionForm } from "../src/features/good-moral/good-moral-correction-form.tsx";
import { GoodMoralWorkspacePage } from "../src/features/good-moral/good-moral-page.tsx";
import { getGoodMoralAccess } from "../src/features/good-moral/good-moral-access.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { getOverviewMetrics } from "../src/features/portal/home/overview-presentation.ts";
import { getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "../src/lib/api/generated/good-moral/good-moral.ts";

const staff = {
  id: "staff", role: "GUIDANCE_SERVICES_STAFF", first_name: "Guidance", last_name: "Staff",
  email: "staff@example.test", student_lifecycle_status: null, designations: [],
  capabilities: ["good_moral.view", "good_moral.prepare", "academic_years.view", "institutional_forms.view"],
};
const clerical = ["year_level", "course", "major", "semester", "official_receipt_number", "official_receipt_date", "official_receipt_amount"];
const actions = { request_version: "2026-10-05T00:00:00.123456+00:00", preparation_version: null, can_correct: true, can_prepare: true, can_issue: false, can_cancel: false, can_download: false, correction_fields: clerical };
const item = {
  id: "request", variant: "CURRENT_STUDENT", status: "REQUESTED", applicant_name: "Student Example",
  student: { id: "student", display_name: "Student Example" }, student_institutional_id: "2026-1",
  inventory_id: "inventory", academic_year: { id: "year", label: "2026-2027" }, year_level: "Fourth",
  course: "BS Computing", college: "College of Computing", semester: "First", major: "Software",
  degree: "", graduation_date: null, official_receipt_number: "", official_receipt_date: null,
  official_receipt_amount: null, form_revision: null, document_template_key: null, document_template_version: null,
  issued_by: null, issued_by_name_snapshot: "", issued_at: null, cancelled_at: null, cancellation: null,
  prepared_by: null, prepared_at: null, created_at: "2026-10-05T00:00:00Z", updated_at: "2026-10-05T00:00:00Z", actions,
};
const filters = { search: "", formRevisionId: "", variant: "", status: "", page: 1 };
const ok = (data) => ({ data, status: 200, headers: {} });

function render(element, user = staff, request = item) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  client.setQueryData(getGoodMoralGetRequestQueryKey(item.id), ok(request));
  client.setQueryData(getGoodMoralListRequestsQueryKey({ page: 1 }), ok({ items: [request], page: 1, page_size: 20, has_next: false, filter_options: { form_revisions: [] } }));
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, element))));
  client.clear();
  return html;
}

test("GSS gets Good Moral and references while professional destinations stay absent", () => {
  const hrefs = portalWorkspaceGroups(staff).flatMap((group) => group.links.map((link) => link.href));
  assert.ok(hrefs.includes("/portal/good-moral"));
  for (const path of ["/portal/counseling", "/portal/inventory", "/portal/routine-interviews", "/portal/exit-interviews", "/portal/reports"]) assert.ok(!hrefs.includes(path));
  const revoked = { ...staff, capabilities: ["good_moral.view"] };
  assert.equal(getGoodMoralAccess(revoked).canPrepare, false);
  assert.equal(getGoodMoralAccess(revoked).hasOperationalWorkspace, true);
  assert.equal(getGoodMoralAccess({ ...staff, capabilities: [] }).hasOperationalWorkspace, false);
  assert.equal(getGoodMoralAccess({ ...staff, capabilities: [...staff.capabilities, "good_moral.issue"] }).canIssue, false);
});

test("GSS queue shows year, preparation state, and useful status filters", () => {
  const html = render(h(GoodMoralWorkspacePage, { filters }));
  assert.match(html, /Student Example/);
  assert.match(html, /2026-2027/);
  assert.match(html, /Needs preparation/);
  assert.match(html, /Ready for issuance/);
  assert.doesNotMatch(html, /Issue certificate/);
});

test("GSS direct detail can correct and mark ready but cannot cancel or issue", () => {
  const html = render(h(GoodMoralDetailPage, { requestId: item.id }));
  assert.match(html, /Correct certificate details/);
  assert.match(html, /Mark ready for issuance/);
  assert.doesNotMatch(html, /Issue certificate|Cancel request/);
});

test("view-only GSS sees the record without preparation controls", () => {
  const user = { ...staff, capabilities: ["good_moral.view"] };
  const request = { ...item, actions: { ...actions, can_prepare: false, can_correct: false, correction_fields: [] } };
  const html = render(h(GoodMoralDetailPage, { requestId: item.id }), user, request);
  assert.match(html, /Student Example/);
  assert.doesNotMatch(html, /Mark ready for issuance|Correct certificate details|Issue certificate/);
});

test("clerical editor excludes protected identity and graduation facts", () => {
  const html = render(h(GoodMoralCorrectionForm, { item, open: true, onRefresh: async () => item, onClose() {} }));
  assert.match(html, /good-moral-correction-course/);
  assert.match(html, /good-moral-correction-receipt-number/);
  assert.doesNotMatch(html, /good-moral-correction-applicant-name|good-moral-correction-college/);
  const graduate = { ...item, variant: "GRADUATE", actions: { ...actions, correction_fields: clerical.filter((key) => !["year_level", "course", "semester"].includes(key)) } };
  const gradHtml = render(h(GoodMoralCorrectionForm, { item: graduate, open: true, onRefresh: async () => graduate, onClose() {} }));
  assert.doesNotMatch(gradHtml, /good-moral-correction-degree|good-moral-correction-graduation-date/);
  assert.match(gradHtml, /good-moral-correction-major/);
});

test("Counselor sees actual preparation provenance and can issue ready requests", () => {
  const counselor = { ...staff, role: "COUNSELOR", capabilities: [...staff.capabilities, "good_moral.manage", "good_moral.issue"] };
  const ready = { ...item, status: "READY_FOR_ISSUANCE", prepared_by: { id: "staff", display_name: "Guidance Staff" }, prepared_at: "2026-10-05T01:00:00Z", actions: { ...actions, can_prepare: false, can_issue: true, can_cancel: true, preparation_version: "2026-10-05T01:00:00.123456+00:00" } };
  const html = render(h(GoodMoralDetailPage, { requestId: item.id }), counselor, ready);
  assert.match(html, /Prepared by/);
  assert.match(html, /Guidance Staff/);
  assert.match(html, /Issue certificate/);
  assert.match(html, /Ready for issuance/);
  assert.doesNotMatch(render(h(GoodMoralDetailPage, { requestId: item.id }), staff, { ...ready, actions: { ...ready.actions, can_issue: false, can_cancel: false } }), /Issue certificate/);
});

test("issued GSS detail offers certificate download and preserves the issuing Counselor", () => {
  const issued = { ...item, status: "ISSUED", issued_at: "2026-10-05T01:00:00Z", issued_by: { id: "counselor", display_name: "Actual Counselor" }, issued_by_name_snapshot: "Actual Counselor", actions: { ...actions, can_prepare: false, can_correct: false, can_download: true, correction_fields: [] } };
  const html = render(h(GoodMoralDetailPage, { requestId: item.id }), staff, issued);
  assert.match(html, /Actual Counselor/);
  assert.match(html, /Download/);
  assert.doesNotMatch(html, /Issue certificate|Mark ready for issuance/);
});

test("GSS Overview links only the exact preparation and readiness counts", () => {
  const summary = { student: null, platform: null, guidance: {
    upcoming_self_appointments_count: null, upcoming_managed_appointments_count: null,
    routine_evaluation_pending_count: null, active_call_slip_count: null,
    good_moral_requested_count: 2, good_moral_ready_count: 3,
  } };
  const metrics = getOverviewMetrics(summary, staff);
  assert.equal(metrics.length, 2);
  assert.deepEqual(metrics.map((metric) => metric.href), ["/portal/good-moral?status=REQUESTED", "/portal/good-moral?status=READY_FOR_ISSUANCE"]);
});
