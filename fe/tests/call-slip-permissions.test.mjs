import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CallSlipDetailPage } from "../src/features/call-slips/call-slip-detail-page.tsx";
import CallSlipListRoute from "../src/app/(portal)/portal/call-slips/page.tsx";
import { ReferralCallSlipSection } from "../src/features/referrals/referral-call-slip-section.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getCallSlipsGetQueryKey, getCallSlipsGetMyQueryKey, getCallSlipsListQueryKey } from "../src/lib/api/generated/call-slips/call-slips.ts";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user, slip } from "./support/ui-hierarchy-fixtures.mjs";

function render(role, capabilities, state = "ACTIVE", { error = null, referralAccess = false } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const item = { ...slip, state, updated_at: slip.created_at, void_reason: "Recorded in error", referral: { id: "referral-test", reference_code: "REF-TEST" } };
  const key = role === "STUDENT" ? getCallSlipsGetMyQueryKey(slip.id) : getCallSlipsGetQueryKey(slip.id);
  client.setQueryData(key, { data: item, status: 200, headers: {} });
  if (error) client.getQueryCache().find({ queryKey: key }).setState({ status: "error", error });
  const account = { ...user(role), capabilities: [...capabilities, ...(referralAccess ? ["referrals.view"] : [])] };
  try {
    return renderToStaticMarkup(h(QueryClientProvider, { client }, h(PortalSessionProvider,
      { value: sessionFor(account) }, h(CallSlipDetailPage, { callSlipId: slip.id }))));
  } finally { client.clear(); }
}
function assertReadable(html) {
  for (const text of ["Maria Santos", "BSIT / 4", "Guidance Office", "Date and time to report", "Maria Reyes", "TEST-CS", "Revision 1", "data-page-action-label"]) assert.ok(html.includes(text), text);
  assert.match(html, /data-page-action-label=""[^>]*>Download<span class="sr-only"> Call Slip<\/span>/);
}
function assertNoManagement(html) {
  assert.doesNotMatch(html, /Staff actions|Record interview end|Review interview end|Void Call Slip|call-slip-interview-ended|call-slip-void-reason|role="alertdialog"/);
}
for (const role of ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"]) {
  for (const state of ["ACTIVE", "COMPLETED", "VOIDED"]) {
    test(`${role} with explicit view-only capabilities keeps ${state} details and PDF without management`, () => {
      const html = render(role, ["call_slips.view"], state);
      assertReadable(html); assertNoManagement(html);
      assert.match(html, /You don(?:&#x27;|')t have access to the linked Referral reference/);
      assert.doesNotMatch(html, /REF-TEST/);
    });
    test(`${role} manager respects ${state} lifecycle restrictions`, () => {
      const html = render(role, ["call_slips.view", "call_slips.manage"], state);
      assertReadable(html);
      if (state === "ACTIVE") {
        assert.match(html, /Record interview end/); assert.match(html, /Void Call Slip/);
      } else assertNoManagement(html);
    });
  }
  test(`${role} management capability never implies viewing`, () => {
    const html = render(role, ["call_slips.manage"]);
    assertNoManagement(html); assert.doesNotMatch(html, /Maria Santos|data-page-action-layout="call-slip"|TEST-CS/);
  });
  test(`${role} failed refresh retains readable data and suppresses lifecycle actions`, () => {
    const html = render(role, ["call_slips.view", "call_slips.manage"], "ACTIVE", { error: new TypeError("Synthetic offline") });
    assertReadable(html); assertNoManagement(html);
    assert.match(html, /Latest information could not be refreshed/);
  });
}
for (const state of ["ACTIVE", "COMPLETED", "VOIDED"]) {
  test(`Student owner keeps ${state} self details and PDF without operational controls`, () => {
    const html = render("STUDENT", ["call_slips.view_self", "call_slips.view", "call_slips.manage"], state);
    assertReadable(html); assertNoManagement(html);
    assert.doesNotMatch(html, /Linked Referral|REF-TEST|Recorded by/);
    if (state === "VOIDED") assert.match(html, /Withdrawn|This Call Slip is no longer active/);
  });
}
for (const role of ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  test(`${role} without applicable viewing authority cannot render seeded protected detail`, () => {
    const capabilities = ["unrelated.view", ...(role === "IT_ADMIN" || role === "INSTITUTIONAL_OFFICER" ? ["call_slips.view", "call_slips.manage", "call_slips.view_self"] : [])];
    const html = render(role, capabilities);
    assertNoManagement(html); assert.doesNotMatch(html, /Maria Santos|data-page-action-layout="call-slip"|TEST-CS/);
  });
}
test("authorized linked Referral remains available to a view-only Counselor", () => {
  const html = render("COUNSELOR", ["call_slips.view"], "ACTIVE", { referralAccess: true });
  assert.match(html, /Open Referral<span class="sr-only"> REF-TEST<\/span>/); assertNoManagement(html);
});

test("Call Slip route keeps lifecycle state without the removed void toggle", async () => {
  const element = await CallSlipListRoute({ searchParams: Promise.resolve({ state: "VOIDED", page: "2" }) });
  const filters = element.props.children.props.operationalFilters;
  assert.equal(filters.state, "VOIDED");
  assert.equal(filters.page, 2);
  assert.equal(Object.hasOwn(filters, "includeVoided"), false);
});

for (const hasCurrent of [false, true]) {
  test(`Referral linked history queries voided slips while current slip is ${hasCurrent ? "present" : "absent"}`, () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
    const referral = { id: "referral-history", voided_at: null, actions: [] };
    const voided = { ...slip, id: "voided-history-slip", state: "VOIDED" };
    client.setQueryData(getCallSlipsListQueryKey({ referral_id: referral.id, state: "VOIDED", page: 1, page_size: 20 }), {
      data: { items: [voided], page: 1, page_size: 20, has_next: false }, status: 200, headers: {},
    });
    try {
      const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(ReferralCallSlipSection, {
        referral, canManageReferral: false, canViewCallSlips: true, canManageCallSlips: true,
        currentItems: hasCurrent ? [slip] : [], currentPending: false, currentError: null,
        retryCurrent: () => {}, onRefresh: async () => referral,
      })));
      assert.match(html, /Linked Call Slip history/);
      assert.match(html, /voided-history-slip/);
      assert.doesNotMatch(html, /Loading linked Call Slip history/);
      if (hasCurrent) {
        assert.match(html, /slip-density-test/);
        assert.doesNotMatch(html, /Issue another linked Call Slip/);
      } else {
        assert.match(html, /No current linked Call Slip/);
        assert.match(html, /Issue another linked Call Slip/);
      }
    } finally { client.clear(); }
  });
}
