import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  captureStatusLabel,
  consentProjectionLabels,
  consentStatusLabel,
  ecounselingErrorMessage,
} from "../src/features/ecounseling/ecounseling-shared.ts";
import { StudentConsentPanel } from "../src/features/ecounseling/student-consent-panel.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { getECounselingListMyConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import {
  ECounselingCaptureStatus,
  ECounselingConsentStatus,
} from "../src/lib/api/generated/model/index.ts";

// Words that describe how COMPASS is built rather than what a reader is doing.
const IMPLEMENTATION_TERMS = /\b(provider|canonical|projection|reconcil\w*|payload|capture state)\b/i;

test("Students see presentation labels, never backend enum values or implementation terms", () => {
  for (const status of Object.values(ECounselingCaptureStatus)) {
    const label = captureStatusLabel(status);
    assert.notEqual(label, status);
    assert.doesNotMatch(label, /_/);
    assert.doesNotMatch(label, IMPLEMENTATION_TERMS);
  }
  for (const status of Object.values(ECounselingConsentStatus)) {
    const label = consentProjectionLabels[status];
    assert.notEqual(label, status);
    assert.doesNotMatch(label, /_/);
  }
  assert.equal(consentStatusLabel({ decision: "APPROVED", effective: true, withdrawn_at: "2026-10-04T02:00:00Z" }), "Withdrawn");
});

test("E-Counseling errors explain what happened without implementation terms", () => {
  const codes = [
    "ecounseling_consent_conflict",
    "ecounseling_media_conflict",
    "ecounseling_media_stop_pending",
    "ecounseling_provider_disabled",
    "ecounseling_provider_unavailable",
    "ecounseling_invalid_provider_response",
  ];
  for (const code of codes) {
    const message = ecounselingErrorMessage(new CompassApiError({ status: 409, body: { error: { code, message: "raw" } }, headers: {}, method: "POST", url: "/api/v1/e-counseling" }), "fallback");
    assert.notEqual(message, "fallback", code);
    assert.doesNotMatch(message, IMPLEMENTATION_TERMS, code);
  }
});

const APPOINTMENT = "60000000-0000-4000-8000-000000000001";
const consents = [
  { id: "c1", scope: "AUDIO_VIDEO_RECORDING", decision: "APPROVED", effective: true, requested_at: "2026-10-04T02:00:00Z", decided_at: "2026-10-04T02:01:00Z", withdrawn_at: null },
  { id: "c2", scope: "LIVE_TRANSCRIPTION", decision: "PENDING", effective: false, requested_at: "2026-10-04T02:02:00Z", decided_at: null, withdrawn_at: null },
];

function renderConsent() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(getECounselingListMyConsentsQueryKey(APPOINTMENT), { data: { items: consents }, status: 200, headers: {} });
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(StudentConsentPanel, {
        appointmentId: APPOINTMENT,
        access: { canConsentSelf: true },
        media: {
          recording: { capture_status: "NOT_STARTED", consent_status: "APPROVED" },
          transcription: { capture_status: "NOT_STARTED", consent_status: "PENDING", storage_consent_status: "NOT_REQUESTED", storage_enabled: false },
        },
      }),
    ),
  );
}

test("media consent still says it does not affect Counseling, where Students decide", () => {
  const html = renderConsent();
  assert.match(html, /Your media-consent choice does not affect your ability to receive Counseling\./);
  // Each scope keeps its meaning beside its status and the decisions available now.
  assert.match(html, /Allows audio and video from this Counseling session to be recorded\./);
  assert.match(html, /Allows speech from this session to be processed as text while transcription is active\./);
  assert.match(html, /Allows the transcript of this session to be stored by the video service\./);
  assert.match(html, />Approve</);
  assert.match(html, />Decline</);
  assert.match(html, />Withdraw consent</);
  assert.doesNotMatch(html, IMPLEMENTATION_TERMS);
  // Capture activity lives on the session stage, not repeated in the consent list.
  assert.doesNotMatch(html, /Session media activity/);
});

test("a Privacy Notice still says acknowledging it is not consent", async () => {
  const { AccountPrivacyPage } = await import("../src/features/account/privacy/account-privacy-page.tsx");
  const { getPrivacyGovernanceListMyNoticesQueryKey } = await import("../src/lib/api/generated/privacy-governance/privacy-governance.ts");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const notice = {
    acknowledged: false,
    acknowledged_at: null,
    audiences: ["STUDENT"],
    body: "Notice body as written by the Data Protection Officer.",
    code: "PN-1",
    effective_on: "2026-09-01",
    name: "Student Privacy Notice",
    notice_id: "n1",
    requires_acknowledgment: true,
    revision_id: "r1",
    revision_number: 1,
    summary: "How COMPASS handles Student records.",
    title: "Student Privacy Notice",
  };
  client.setQueryData(getPrivacyGovernanceListMyNoticesQueryKey({ page: 1, page_size: 20 }), {
    data: { items: [notice], page: 1, page_size: 20, has_next: false },
    status: 200,
    headers: {},
  });
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(AccountPrivacyPage)));
  assert.match(html, /Acknowledgment records that you have seen this notice\. It is not consent to all data processing\./);
  // The notice text itself is shown as written.
  assert.match(html, /Notice body as written by the Data Protection Officer\./);
});
