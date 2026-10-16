import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { PrivacyGovernanceNavigation } from "../src/features/privacy-governance/privacy-governance-navigation.tsx";
import { PrivacyLanding } from "../src/features/privacy-governance/privacy-landing.tsx";
import * as access from "../src/features/privacy-governance/privacy-governance-access.ts";
import { NOT_ADOPTED_COPY, RetentionPoliciesPage } from "../src/features/privacy-governance/retention/retention-policies-page.tsx";
import { getPrivacyGovernanceListRetentionPoliciesQueryKey } from "../src/lib/api/generated/privacy-governance/privacy-governance.ts";
import { RetentionAdoptionStatus } from "../src/lib/api/generated/model/index.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { withNextRouter } from "./support/next-router.mjs";

const view = "privacy_governance.retention.view";
const key = getPrivacyGovernanceListRetentionPoliciesQueryKey();
const entry = (category_code, category_label, values = {}) => ({ category_code, category_label, adoption_status: "NOT_ADOPTED", retention_period: null, policy_reference: null, effective_date: null, ...values });
const register = { items: [entry("GRADUATE_TRACER", "Graduate Tracer responses"), entry("ECOUNSELING_RECORDING", "E-Counseling recordings"), entry("ECOUNSELING_TRANSCRIPT", "E-Counseling transcripts")] };
const retired = /Create|Edit|Activate|Retire|Approve|Retry|Place hold|Release hold|Disposition cases|Needs review|Retention &amp; Disposition|Retention rules|0 days|N\/A/;

function render(component, { capabilities = [view], data, error, pathname = "/portal/privacy/retention" } = {}) {
  // An errored query with no data refetches on mount unless retryOnMount is off.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false, staleTime: Infinity } } });
  if (data) client.setQueryData(key, { data, status: 200, headers: {} });
  if (error) client.getQueryCache().build(client, { queryKey: key }).setState({ status: "error", error, data: undefined });
  const element = createElement(QueryClientProvider, { client }, createElement(PortalSessionProvider, { value: { user: { capabilities } } }, component));
  const html = renderToStaticMarkup(withNextRouter(element, { pathname }));
  client.clear();
  return html;
}

test("retention authority is read-only and separate from notice authority", () => {
  assert.equal(access.canViewRetention({ capabilities: [view] }), true);
  assert.equal(access.canViewRetention({ capabilities: ["privacy_governance.view"] }), false);
  assert.equal(access.hasPrivacyGovernanceWorkspace({ capabilities: [view] }), true);
  assert.equal(access.hasPrivacyGovernanceWorkspace({ capabilities: [] }), false);
  assert.equal("canManageRetention" in access, false);
  assert.equal("canApproveDisposition" in access, false);
  assert.deepEqual(Object.values(RetentionAdoptionStatus), ["NOT_ADOPTED", "ADOPTED"]);
});

test("navigation and landing name the oversight page Retention Policies", () => {
  const nav = render(createElement(PrivacyGovernanceNavigation));
  assert.match(nav, /Retention Policies/);
  assert.match(nav, /aria-current="page"/);
  assert.doesNotMatch(nav, /Retention &amp; Disposition|Privacy Notices/);
  const noticesOnly = render(createElement(PrivacyGovernanceNavigation), { capabilities: ["privacy_governance.view"] });
  assert.doesNotMatch(noticesOnly, /Retention/);
  const landing = render(createElement(PrivacyLanding), { pathname: "/portal/privacy" });
  assert.match(landing, /Retention Policies/);
  assert.match(landing, /Retention policy status recorded in COMPASS\./);
  assert.doesNotMatch(landing, /disposition cases|holds/i);
});

test("each category is read-only and states that no policy is recorded without implying deletion", () => {
  const html = render(createElement(RetentionPoliciesPage), { data: { items: register.items.map((item) => ({ ...item, source_id: "SECRET-SOURCE", student_name: "SECRET PERSON" })) } });
  assert.match(html, /<h1[^>]*>Retention Policies<\/h1>/);
  assert.match(html, /View the retention policy status recorded in COMPASS\. Policy changes are governed through institutional approval and reviewed system updates\./);
  for (const label of ["Graduate Tracer responses", "E-Counseling recordings", "E-Counseling transcripts"]) assert.match(html, new RegExp(`<h3[^>]*>${label}</h3>`));
  assert.equal(html.split(">Not adopted<").length - 1, 3);
  assert.equal(html.split(NOT_ADOPTED_COPY).length - 1, 3);
  assert.match(html, /COMPASS doesn’t delete or anonymize records under these policies\. Records disposition goes through the University’s authorized process outside COMPASS\./);
  assert.doesNotMatch(html, /Retention period|Policy reference|Effective date/);
  assert.doesNotMatch(html, retired);
  assert.doesNotMatch(html, /SECRET/);
  assert.doesNotMatch(html, /<form|<input|<select|<textarea/);
  const buttons = html.match(/<button[^>]*>[\s\S]*?<\/button>/g) ?? [];
  assert.deepEqual(buttons.map((button) => button.replace(/<[^>]+>/g, "").trim()), ["Help"]);
});

test("an adopted entry shows its recorded terms verbatim with an institutional date", () => {
  const adopted = entry("GRADUATE_TRACER", "Graduate Tracer responses", { adoption_status: "ADOPTED", retention_period: "SYNTHETIC WORDING", policy_reference: "SYNTHETIC-REF", effective_date: "2030-01-02" });
  const html = render(createElement(RetentionPoliciesPage), { data: { items: [adopted, register.items[1]] } });
  assert.match(html, />Adopted</);
  assert.match(html, /Retention period[\s\S]*SYNTHETIC WORDING/);
  assert.match(html, /Policy reference[\s\S]*SYNTHETIC-REF/);
  assert.match(html, /Effective date[\s\S]*January 2, 2030/);
  assert.equal(html.split(">Not adopted<").length - 1, 1);
});

test("loading, unauthorized and unavailable states fail safely", () => {
  const loading = render(createElement(RetentionPoliciesPage));
  assert.match(loading, /Loading retention policies…/);
  assert.doesNotMatch(loading, /Not adopted/);
  const unavailable = render(createElement(RetentionPoliciesPage), { capabilities: ["privacy_governance.view"] });
  assert.match(unavailable, /Retention Policies unavailable/);
  assert.doesNotMatch(unavailable, /Record categories/);
  for (const status of [403, 503]) {
    const error = new CompassApiError({ status, body: { error: { code: status === 403 ? "permission_denied" : "unavailable", message: "PRIVATE DIAGNOSTIC" } }, headers: {}, method: "GET", url: "/api/v1/privacy/retention/policies" });
    const html = render(createElement(RetentionPoliciesPage), { error });
    assert.match(html, /role="alert"/);
    assert.match(html, />Retry</);
    assert.match(html, status === 403 ? /You can&#x27;t perform this privacy action\.|You can't perform this privacy action\./ : /Retention policies could not be loaded\./);
    assert.doesNotMatch(html, /PRIVATE DIAGNOSTIC|Not adopted/);
  }
});

test("retired rule and case routes have no page implementation or redirect", () => {
  const root = new URL("../src/app/(portal)/portal/privacy/retention/", import.meta.url);
  const files = readdirSync(root, { recursive: true }).filter((name) => name.endsWith(".tsx")).sort();
  assert.deepEqual(files, ["page.tsx"]);
  const feature = readdirSync(new URL("../src/features/privacy-governance/retention/", import.meta.url)).sort();
  assert.deepEqual(feature, ["retention-help.tsx", "retention-policies-page.tsx"]);
});
