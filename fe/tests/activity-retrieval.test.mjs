import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { ActivityPage } from "../src/features/account/activity/activity-page.tsx";
import { PlatformActivityPage } from "../src/features/platform/activity/platform-activity-page.tsx";
import { PrivacyActivityPage } from "../src/features/privacy-governance/activity/privacy-activity-page.tsx";
import { ActivityFilterTools, activityUrl, enumValue } from "../src/features/activity/activity-filters.tsx";
import { activityErrorMessage } from "../src/features/activity/activity-errors.ts";
import { getMeListActivityQueryKey, getMeListSecurityActivityQueryKey, getMeListSupervisedStaffQueryKey, getMeListSupervisedStaffActivityQueryKey } from "../src/lib/api/generated/activity/activity.ts";
import { getPlatformOperationsListActivityQueryKey } from "../src/lib/api/generated/platform-operations/platform-operations.ts";
import { getPrivacyGovernanceListActivityQueryKey, getPrivacyGovernanceExportActivityUrl } from "../src/lib/api/generated/privacy-governance/privacy-governance.ts";
import { SupervisedActivityType, TechnicalActivityType, PrivacyActivityType } from "../src/lib/api/generated/model/index.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { withNextRouter } from "./support/next-router.mjs";

const supervise = "activity.supervised_staff.view";
const browse = "privacy_governance.view";
const exportCapability = "privacy_governance.activity.export";
const staff = { id: "00000000-0000-4000-8000-000000000001", display_name: "José Staff" };
const ok = (data) => ({ data, status: 200, headers: {} });
const page = (items, number = 1, next = false) => ({ items, page: number, page_size: 20, has_next: next });
const event = { id: "e1", type: "referral.created", title: "Referral recorded", description: "A referral was recorded.", occurred_at: "2026-10-04T00:00:00Z", staff };
const privacyEvent = { id: "p1", category: "PRIVACY_GOVERNANCE", type: "privacy.disposition.completed", title: "Disposition completed", description: "The domain executor verified the approved treatment.", occurred_at: event.occurred_at, actor_display_name: "DPO Operator", artifact_type: null, artifact_format: null, scope: null, resource_reference: "case-opaque" };
const platformEvent = { id: "t1", type: "platform.maintenance.enabled", title: "Maintenance Mode enabled", description: "Manual Maintenance Mode was enabled.", occurred_at: event.occurred_at, actor_display_name: "IT Operator", actor_type: "USER" };

function render(component, { capabilities = [], records = [], errors = [], pathname = "/portal/account/activity", search = "" } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const [key, data] of records) client.setQueryData(key, data);
  for (const [key, error] of errors) client.getQueryCache().find({ queryKey: key }).setState({ status: "error", error });
  const html = renderToStaticMarkup(withNextRouter(createElement(QueryClientProvider, { client }, createElement(PortalSessionProvider, { value: { user: { capabilities } } }, component)), { pathname, search }));
  const requested = client.getQueryCache().getAll().map((query) => query.queryKey);
  client.clear();
  return { html, requested };
}
function apiError(status, code = "permission_denied", message = "Refused") {
  return new CompassApiError({ status, body: { error: { code, message } }, headers: {}, method: "GET", url: "/api/v1/privacy/activity" });
}
const scopeRecords = (items = [staff]) => [[getMeListSupervisedStaffQueryKey({ page_size: 50 }), { pages: [ok(page(items))], pageParams: [1] }]];

test("self Activity stays simple, self-only, and has the original view controls", () => {
  for (const capabilities of [[], [supervise]]) {
    const { html } = render(createElement(ActivityPage), { capabilities, records: [...scopeRecords([]), [getMeListActivityQueryKey({ page: 1, page_size: 20 }), ok(page([{ ...event, type: "auth.login", title: "Signed in to COMPASS" }]))]] });
    assert.match(html, /My activity|Security activity|Signed in to COMPASS/);
    assert.doesNotMatch(html, /role="search"|Export CSV|Supervised staff|José/);
  }
});

test("the supervised tab requires both effective authority and confirmed nonempty scope", () => {
  assert.match(render(createElement(ActivityPage), { capabilities: [supervise], records: scopeRecords() }).html, /Supervised staff/);
  for (const options of [{ capabilities: [], records: scopeRecords() }, { capabilities: [supervise], records: scopeRecords([]) }, { capabilities: [supervise] }]) {
    assert.doesNotMatch(render(createElement(ActivityPage), options).html, />Supervised staff<|José/);
  }
});

test("a revoked scope hides the third tab and cached staff names", () => {
  const key = getMeListSupervisedStaffQueryKey({ page_size: 50 });
  const { html } = render(createElement(ActivityPage), { capabilities: [supervise], records: scopeRecords(), errors: [[key, apiError(403)]] });
  assert.doesNotMatch(html, />Supervised staff<|José/);
});

test("security Activity has no search/filter/export controls", () => {
  const { html } = render(createElement(ActivityPage), { search: "view=security", records: [[getMeListSecurityActivityQueryKey({ page: 1, page_size: 20 }), ok(page([{ ...event, title: "Authenticator app enabled" }]))]] });
  assert.match(html, /Authenticator app enabled/);
  assert.doesNotMatch(html, /role="search"|Export CSV|name="event_type"/);
});

test("supervised criteria come from URL and generated types, with safe names/text", () => {
  const params = { search: "José", staff_id: staff.id, event_type: event.type, date_from: "2026-10-01", date_to: "2026-10-04", page: 2, page_size: 20 };
  const { html, requested } = render(createElement(ActivityPage), { capabilities: [supervise], search: new URLSearchParams({ view: "supervised", ...params }).toString(), records: [...scopeRecords(), [getMeListSupervisedStaffActivityQueryKey(params), ok(page([{ ...event, metadata: "PRIVATE-METADATA", student_name: "PRIVATE-STUDENT", target_id: "PRIVATE-TARGET" }], 2, true))]] });
  assert.ok(requested.some((key) => key[0] === "/api/v1/me/supervised-staff-activity" && key[1].page === 2 && key[1].staff_id === staff.id));
  for (const label of ["Staff member", "Activity type", "Date from", "Date to", "José Staff", "Referral recorded", "Clear filters"]) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /Export CSV|PRIVATE/);
  assert.match(html, /name="search"[^>]*value="José"/);
  assert.match(html, /Page 2/);
});

test("supervised filtered empty state differs from no activity", () => {
  const params = { search: "missing", page: 1, page_size: 20 };
  const { html } = render(createElement(ActivityPage), { capabilities: [supervise], search: "view=supervised&search=missing", records: [...scopeRecords(), [getMeListSupervisedStaffActivityQueryKey(params), ok(page([]))]] });
  assert.match(html, /No matching activity\.|Clear filters/);
});

test("platform filters compose and preserve the curated list without export", () => {
  const params = { search: "manual", event_type: platformEvent.type, operator: "IT", date_from: "2026-10-01", date_to: "2026-10-04", page: 2, page_size: 20 };
  const { html, requested } = render(createElement(PlatformActivityPage), { pathname: "/portal/platform/activity", search: new URLSearchParams(params).toString(), records: [[getPlatformOperationsListActivityQueryKey(params), ok(page([platformEvent], 2, true))]] });
  assert.ok(requested.some((key) => key[0] === "/api/v1/platform/activity" && key[1].operator === "IT" && key[1].page === 2));
  assert.match(html, /Technical activity|Event type|Operator|Date from|Date to|Maintenance Mode enabled/);
  assert.doesNotMatch(html, /Export CSV|metadata|PRIVATE/);
});

test("privacy criteria and retention presentation survive URL reload", () => {
  const params = { search: "verified", category: "PRIVACY_GOVERNANCE", event_type: privacyEvent.type, actor: "DPO", date_from: "2026-10-01", date_to: "2026-10-04", page: 2, page_size: 20 };
  const { html, requested } = render(createElement(PrivacyActivityPage), { capabilities: [browse, exportCapability], pathname: "/portal/privacy/activity", search: new URLSearchParams(params).toString(), records: [[getPrivacyGovernanceListActivityQueryKey(params), ok(page([{ ...privacyEvent, provider_id: "PRIVATE-PROVIDER", raw_metadata: "PRIVATE-METADATA" }], 2, true))]] });
  assert.ok(requested.some((key) => key[0] === "/api/v1/privacy/activity" && key[1].category === "PRIVACY_GOVERNANCE" && key[1].actor === "DPO"));
  assert.match(html, /Export CSV|Disposition completed|Category|Event type|Actor|Date from|Date to/);
  assert.doesNotMatch(html, /PRIVATE/);
});

test("browse-only Privacy Activity has no export action", () => {
  const { html } = render(createElement(PrivacyActivityPage), { capabilities: [browse], pathname: "/portal/privacy/activity", records: [[getPrivacyGovernanceListActivityQueryKey({ page: 1, page_size: 20 }), ok(page([privacyEvent]))]] });
  assert.doesNotMatch(html, /Export CSV/);
});

test("CSV request uses every active criterion and omits page selection", () => {
  const criteria = { search: "draft", category: "PRIVACY_GOVERNANCE", event_type: "privacy.retention.rule.updated", actor: "José", date_from: "2026-10-01", date_to: "2026-10-04" };
  const url = new URL(getPrivacyGovernanceExportActivityUrl(criteria), "https://example.edu");
  for (const [key, value] of Object.entries(criteria)) assert.equal(url.searchParams.get(key), value);
  assert.equal(url.searchParams.has("page"), false);
  assert.equal(url.searchParams.has("page_size"), false);
});

test("URL changes reset pages and pagination preserves all active criteria", () => {
  const before = "view=supervised&search=referral&staff_id=abc&event_type=referral.created&date_from=2026-10-01&page=4";
  const changed = new URL(activityUrl("/portal/account/activity", before, { search: "call", event_type: "call_slip.created" }), "https://example.edu");
  assert.equal(changed.searchParams.has("page"), false);
  assert.equal(changed.searchParams.get("view"), "supervised");
  assert.equal(changed.searchParams.get("staff_id"), "abc");
  const paged = new URL(activityUrl("/portal/account/activity", before, { page: "5" }, false), "https://example.edu");
  assert.equal(paged.searchParams.get("page"), "5");
  assert.equal(paged.searchParams.get("search"), "referral");
  assert.equal(paged.searchParams.get("date_from"), "2026-10-01");
  assert.equal(new URL(activityUrl("/portal/account/activity", before, { search: null, staff_id: null, event_type: null, date_from: null }), "https://example.edu").searchParams.toString(), "view=supervised");
});

test("event-type choices are the generated closed vocabularies", () => {
  assert.equal(Object.values(SupervisedActivityType).length, 22);
  assert.equal(enumValue("auth.login", Object.values(SupervisedActivityType)), undefined);
  assert.equal(enumValue("privacy.disposition.completed", Object.values(PrivacyActivityType)), "privacy.disposition.completed");
  assert.equal(enumValue("privacy.disposition.completed", Object.values(TechnicalActivityType)), undefined);
});

test("filter form has named controls and a shared dialog with explicit apply/clear", () => {
  const { html } = render(createElement(ActivityFilterTools, { applied: { search: "record", date_from: "2026-10-05", date_to: "2026-10-04" }, fields: [{ name: "date_from", label: "Date from", type: "date" }, { name: "date_to", label: "Date to", type: "date" }], onApply() {} }));
  assert.match(html, /role="search" aria-label="Find activity"/);
  assert.match(html, /<dialog|aria-expanded="false"|Apply filters|Clear filters/);
  assert.match(html, /Date from must not be after Date to/);
  assert.match(html, /aria-invalid="true"/);
});

test("refresh failure retains confirmed data but authority failure hides it", () => {
  const key = getPrivacyGovernanceListActivityQueryKey({ page: 1, page_size: 20 });
  for (const status of [503, 403]) {
    const { html } = render(createElement(PrivacyActivityPage), { capabilities: [browse, exportCapability], pathname: "/portal/privacy/activity", records: [[key, ok(page([privacyEvent]))]], errors: [[key, apiError(status)]] });
    if (status === 503) assert.match(html, /Disposition completed|Retry/);
    else assert.doesNotMatch(html, /Disposition completed/);
    assert.match(html, /<button[^>]*disabled=""[^>]*>Export CSV/);
  }
});

test("typed export failure reports the backend bound and audit failure without raw errors", () => {
  assert.match(activityErrorMessage(apiError(422, "privacy_activity_export_too_large", "More than 10,000 events match. Narrow the filters."), "fallback"), /10,000/);
  assert.match(activityErrorMessage(apiError(503, "release_audit_unavailable", "The required export audit could not be recorded."), "fallback"), /export audit/);
  assert.equal(activityErrorMessage(apiError(500, "unknown", "PRIVATE TRACE"), "CSV could not be exported."), "CSV could not be exported.");
});
