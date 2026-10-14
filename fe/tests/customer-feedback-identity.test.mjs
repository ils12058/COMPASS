import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { CustomerFeedbackForm } from "../src/features/feedback/customer-feedback-form.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getFeedbackGetMyOpportunityQueryKey } from "../src/lib/api/generated/feedback/feedback.ts";
import { getProfileGetMyProfileQueryKey } from "../src/lib/api/generated/profile/profile.ts";

const opportunityId = "bb111111-1111-4111-8111-111111111111";
const user = { id: "synthetic-student", role: "STUDENT", first_name: "Account", last_name: "Identity", capabilities: ["feedback.submit_customer_feedback"] };
const ok = (data) => ({ data, status: 200, headers: {} });

for (const cachedProfile of [false, true]) test(`optional identity starts blank with ${cachedProfile ? "populated" : "no"} cached profile`, () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(getFeedbackGetMyOpportunityQueryKey(opportunityId), ok({
    id: opportunityId, service_kind: "COUNSELING", service_label: "Counseling",
    can_submit_customer_feedback: true, customer_feedback_submitted: false,
  }));
  if (cachedProfile) client.setQueryData(getProfileGetMyProfileQueryKey(), ok({
    full_name: "Account Identity", current_address: "Account Current Address",
    permanent_address: "Account Permanent Address", contact_number: "Account Phone",
  }));
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } },
      h(UnsavedChangesProvider, null, h(CustomerFeedbackForm)))),
    { pathname: "/portal/feedback/customer-feedback", search: `opportunity=${opportunityId}` },
  ));
  for (const id of ["feedback-respondent-name", "feedback-address", "feedback-mobile"]) {
    const input = html.match(new RegExp(`<input[^>]*id="${id}"[^>]*>`))?.[0];
    assert.ok(input);
    assert.match(input, /value=""/);
    assert.doesNotMatch(input, /required=/);
  }
  assert.match(html, /id="feedback-course-year"[^>]*required=""/);
  assert.doesNotMatch(html, /Account Identity|Account Current Address|Account Permanent Address|Account Phone/);
  assert.match(html, /Providing your name, address, and mobile number is optional/);
  assert.match(html, /Submission activity is recorded separately for security and accountability/);
  if (!cachedProfile) assert.equal(client.getQueryCache().find({ queryKey: getProfileGetMyProfileQueryKey() }), undefined);
  client.clear();
});
