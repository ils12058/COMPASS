import assert from "node:assert/strict";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { CustomerFeedbackForm } from "../src/features/feedback/customer-feedback-form.tsx";
import { CsmForm } from "../src/features/feedback/csm-form.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { feedbackSectionHeadingId } from "../src/features/feedback/feedback-shared.tsx";
import { getFeedbackGetMyOpportunityQueryKey } from "../src/lib/api/generated/feedback/feedback.ts";

const customerOpportunityId = "bb111111-1111-4111-8111-111111111111";
const csmOpportunityId = "cc111111-1111-4111-8111-111111111111";

function renderFeedbackForm({ Form, opportunityId, capability, pathname }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(getFeedbackGetMyOpportunityQueryKey(opportunityId), {
    data: {
      id: opportunityId,
      service_kind: "COUNSELING",
      service_label: "Counseling",
      service_completed_at: "2026-10-14T00:00:00Z",
      can_submit_customer_feedback: capability === "feedback.submit_customer_feedback",
      can_submit_csm: capability === "feedback.submit_csm",
      customer_feedback_submitted: false,
      csm_submitted: false,
    },
    status: 200,
    headers: {},
  });
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, {
      value: { user: { id: "synthetic-student", role: "STUDENT", capabilities: [capability] } },
    }, h(UnsavedChangesProvider, null, h(Form)))),
    { pathname, search: `opportunity=${opportunityId}` },
  ));
  client.clear();
  return html;
}

test("Customer Feedback section links target the existing nine continuous sections", () => {
  const html = renderFeedbackForm({
    Form: CustomerFeedbackForm,
    opportunityId: customerOpportunityId,
    capability: "feedback.submit_customer_feedback",
    pathname: "/portal/feedback/customer-feedback",
  });
  const titles = [
    "I. Service/s received",
    "II. Guidance Counselor and accommodation",
    "III. Number of office visits",
    "IV. Service personnel experience",
    "V. Office experience",
    "VI. Overall satisfaction",
    "VII. Additional feedback",
    "VIII. Future service improvement",
    "IX. Respondent information",
  ];

  assert.match(html, /aria-label="Customer Feedback sections"/);
  assert.equal((html.match(/aria-current="step"/g) ?? []).length, 0);
  for (const title of titles) {
    const id = feedbackSectionHeadingId(title);
    assert.match(html, new RegExp(`href="#${id}"`));
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /Questions marked \* are required/);
  assert.match(html, /Providing your name, address, and mobile number is optional/);
  assert.doesNotMatch(html, /anonymous response|save progress|autosave/i);
});

test("CSM retains the original continuous four-group layout and all six SQD values", () => {
  const html = renderFeedbackForm({
    Form: CsmForm,
    opportunityId: csmOpportunityId,
    capability: "feedback.submit_csm",
    pathname: "/portal/feedback/csm",
  });
  const groupIds = [
    "feedback-respondent-information",
    "feedback-citizen-s-charter",
    "feedback-service-quality",
    "feedback-suggestions-and-optional-contact",
  ];

  for (const id of groupIds) assert.match(html, new RegExp(`id="${id}"`));
  assert.doesNotMatch(html, /Client Satisfaction Measurement sections/);
  assert.match(html, /0 — Not Applicable|Not Applicable/);
  assert.match(html, /Neither Agree nor Disagree/);
  assert.match(html, /Questions marked \* are required; suggestions and email are optional/);

  for (let index = 0; index <= 8; index += 1) {
    assert.match(html, new RegExp(`SQD${index}\\.`), `SQD${index} is present`);
    const values = [...html.matchAll(new RegExp(`name="csm-sqd${index}" value="([0-5])"`, "g"))].map((match) => Number(match[1]));
    assert.deepEqual(values, [1, 2, 3, 4, 5, 0]);
  }
});
