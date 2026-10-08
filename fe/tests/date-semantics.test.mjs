import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { ProfilePage } from "../src/features/account/profile/profile-page.tsx";
import { unavailabilityRangeError } from "../src/features/availability/unavailability-section.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { GoodMoralCorrectionForm } from "../src/features/good-moral/good-moral-correction-form.tsx";
import { GoodMoralRequestPage } from "../src/features/good-moral/good-moral-request-page.tsx";
import { FamilySection } from "../src/features/inventory/editor/family-section.tsx";
import { PersonalSection } from "../src/features/inventory/editor/personal-section.tsx";
import { getInventoryDraftIssues, getInventorySubmissionIssues } from "../src/features/inventory/inventory-payload.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { RetentionRuleEditor } from "../src/features/privacy-governance/retention/retention-rule-editor.tsx";
import { getExitInterviewsGetMyStatusQueryKey } from "../src/lib/api/generated/exit-interviews/exit-interviews.ts";
import { getPrivacyGovernanceGetRetentionRuleQueryKey, getPrivacyGovernanceRetentionCategoriesQueryKey } from "../src/lib/api/generated/privacy-governance/privacy-governance.ts";
import { getProfileGetMyProfileQueryKey } from "../src/lib/api/generated/profile/profile.ts";
import {
  institutionalDateInputValue,
  institutionalDateTimeInputValue,
  isFutureInstitutionalDateInput,
  isPastInstitutionalDateInput,
} from "../src/lib/institutional-time.ts";

const ok = (data) => ({ data, status: 200, headers: {} });

function render(element, { user = { capabilities: [] }, records = [], params = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  for (const [key, data] of records) client.setQueryData(key, ok(data));
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element))),
    { params },
  ));
  client.clear();
  return html;
}

function inputTag(html, id) {
  const tag = html.match(new RegExp(`<input[^>]*id="${id}"[^>]*>`))?.[0];
  assert.ok(tag, `missing input #${id}`);
  return tag;
}

function addDays(dateInput, days) {
  const date = new Date(`${dateInput}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

// --- Institutional calendar ------------------------------------------------------------------

test("picker bounds follow the Philippine calendar day, not the UTC day", () => {
  // 15:59 UTC is still 23:59 on 8 October in Manila; 16:00 UTC is already 9 October.
  assert.equal(institutionalDateInputValue(new Date("2026-10-08T15:59:00Z")), "2026-10-08");
  assert.equal(institutionalDateInputValue(new Date("2026-10-08T16:00:00Z")), "2026-10-09");
  assert.equal(institutionalDateTimeInputValue(new Date("2026-10-08T16:30:00Z")), "2026-10-09T00:30");

  const afterManilaMidnight = new Date("2026-10-08T16:30:00Z");
  assert.equal(isFutureInstitutionalDateInput("2026-10-09", afterManilaMidnight), false);
  assert.equal(isFutureInstitutionalDateInput("2026-10-10", afterManilaMidnight), true);
  assert.equal(isPastInstitutionalDateInput("2026-10-08", afterManilaMidnight), true);
  assert.equal(isPastInstitutionalDateInput("2026-10-09", afterManilaMidnight), false);
  assert.equal(isPastInstitutionalDateInput("not-a-date", afterManilaMidnight), false);
});

// --- Birth dates and other facts that already happened --------------------------------------

const inventoryDraft = {
  date_of_birth: "2004-05-01",
  family_members: [
    { kind: "FATHER", date_of_birth: "1970-01-02" },
    { kind: "MOTHER", date_of_birth: null },
  ],
  geographic_locations: [],
  transportation_entries: [],
};

test("Inventory birth dates offer no future date and a future one blocks saving the draft", () => {
  const today = institutionalDateInputValue();
  const personal = render(h(PersonalSection, { draft: inventoryDraft, onChange() {} }));
  assert.match(inputTag(personal, "inventory-date-of-birth"), new RegExp(`max="${today}"`));
  const family = render(h(FamilySection, { draft: inventoryDraft, onChange() {} }));
  assert.match(inputTag(family, "inventory-family-father-date-of-birth"), new RegExp(`max="${today}"`));

  assert.deepEqual(getInventoryDraftIssues(inventoryDraft), []);
  assert.deepEqual(getInventoryDraftIssues({ ...inventoryDraft, date_of_birth: today }), []);
  const future = addDays(today, 1);
  const issues = getInventoryDraftIssues({
    ...inventoryDraft,
    date_of_birth: future,
    family_members: [{ kind: "MOTHER", date_of_birth: future }],
  });
  assert.deepEqual(issues.map((issue) => [issue.targetId, issue.message]), [
    ["inventory-date-of-birth", "Date of birth cannot be in the future."],
    ["inventory-family-mother-date-of-birth", "Mother's date of birth cannot be in the future."],
  ]);
  const submission = getInventorySubmissionIssues({ ...inventoryDraft, date_of_birth: future }, undefined);
  assert.ok(submission.some((issue) => issue.message === "Date of birth cannot be in the future."));
});

test("a Family birth date that needs attention is shown beside its field", () => {
  const html = render(h(FamilySection, {
    draft: inventoryDraft,
    onChange() {},
    validationIssues: [{ section: "family", targetId: "inventory-family-father-date-of-birth", message: "Father's date of birth cannot be in the future." }],
  }));
  assert.match(html, /id="inventory-family-father-date-of-birth-error"[^>]*>Father&#x27;s date of birth cannot be in the future\./);
});

test("Profile date of birth offers dates up to the institutional today", () => {
  const profile = {
    user_id: "u1", first_name: "Ana", middle_name: "", last_name: "Cruz", suffix: "", full_name: "Ana Cruz",
    email: "ana.cruz@example.edu", institutional_id: "2023-0001", role: "STUDENT",
    date_of_birth: "2004-05-01", civil_status: "Single", contact_number: "", current_address: "", permanent_address: "",
    profile_photo_url: null, profile_photo_updated_at: null,
  };
  const user = { id: "u1", first_name: "Ana", last_name: "Cruz", email: "ana.cruz@example.edu", role: "STUDENT", capabilities: [] };
  const html = render(h(ProfilePage), { user, records: [[getProfileGetMyProfileQueryKey(), profile]] });
  assert.match(inputTag(html, "date-of-birth"), new RegExp(`max="${institutionalDateInputValue()}"`));
});

test("Good Moral graduation and receipt dates offer no future date", () => {
  const today = institutionalDateInputValue();
  const graduate = {
    id: "student", role: "STUDENT", student_lifecycle_status: "GRADUATED", designations: [], first_name: "Graduate",
    last_name: "Example", email: "graduate@example.test", capabilities: ["good_moral.view_self", "good_moral.request_self"],
    exit_interview_workspace_available: false,
  };
  const status = { academic_year: null, opportunity: null, current_record: null, has_records: false, inventory_submitted: false, can_start: false, can_edit_current: false, graduation_good_moral_blocked: false };
  const request = render(h(GoodMoralRequestPage), { user: graduate, records: [[getExitInterviewsGetMyStatusQueryKey(), status]] });
  assert.match(inputTag(request, "good-moral-graduation-date"), new RegExp(`max="${today}"`));

  const item = {
    id: "request", variant: "GRADUATE", status: "REQUESTED", applicant_name: "Graduate Example",
    student: { id: "student", display_name: "Graduate Example" }, student_institutional_id: "2020-1",
    inventory_id: null, academic_year: null, year_level: "", course: "", college: "", semester: "", major: "",
    degree: "BS Psychology", graduation_date: "2024-06-30", official_receipt_number: "", official_receipt_date: null,
    official_receipt_amount: null, form_revision: null, document_template_key: null, document_template_version: null,
    issued_by: null, issued_by_name_snapshot: "", issued_at: null, cancelled_at: null, cancellation: null,
    prepared_by: null, prepared_at: null, created_at: "2026-10-05T00:00:00Z", updated_at: "2026-10-05T00:00:00Z",
    actions: {
      request_version: "2026-10-05T00:00:00+00:00", preparation_version: null, can_correct: true, can_prepare: true,
      can_issue: false, can_cancel: false, can_download: false,
      correction_fields: ["applicant_name", "degree", "major", "graduation_date", "official_receipt_number", "official_receipt_date", "official_receipt_amount"],
    },
  };
  const correction = render(h(GoodMoralCorrectionForm, { item, open: true, onClose() {}, onRefresh: async () => item }));
  assert.match(inputTag(correction, "good-moral-correction-graduation-date"), new RegExp(`max="${today}"`));
  assert.match(inputTag(correction, "good-moral-correction-receipt-date"), new RegExp(`max="${today}"`));
});

// --- Future-facing operations ----------------------------------------------------------------

test("booking and rescheduling start their date picker at the institutional today", () => {
  const booking = readFileSync(new URL("../src/features/appointments/appointment-booking-page.tsx", import.meta.url), "utf8");
  assert.match(booking, /id="booking-date" type="date" min=\{institutionalDateInputValue\(\)\}/);
  const detail = readFileSync(new URL("../src/features/appointments/appointment-detail-page.tsx", import.meta.url), "utf8");
  assert.match(detail, /id="reschedule-date"\s+type="date"\s+min=\{institutionalDateInputValue\(\)\}/);
});

test("a new unavailability may already have started but must not have ended", () => {
  // 10:00 on 8 October in Manila.
  const now = new Date("2026-10-08T02:00:00Z");
  assert.equal(unavailabilityRangeError("2026-10-08T08:00", "2026-10-08T17:00", now), null);
  assert.equal(unavailabilityRangeError("2026-10-09T08:00", "2026-10-09T17:00", now), null);
  const ended = "The unavailability must still be active or upcoming. The end date and time must be in the future.";
  assert.equal(unavailabilityRangeError("2026-10-07T08:00", "2026-10-07T17:00", now), ended);
  assert.equal(unavailabilityRangeError("2026-10-08T08:00", "2026-10-08T10:00", now), ended);
  assert.equal(unavailabilityRangeError("2026-10-09T17:00", "2026-10-09T08:00", now), "The start date/time must be earlier than the end date/time.");
  assert.equal(unavailabilityRangeError("", "2026-10-09T08:00", now), "Enter a valid start and end date/time.");
});

test("a published Announcement's expiry picker starts now; a draft's is unconstrained", () => {
  const source = readFileSync(new URL("../src/features/announcements/announcement-form.tsx", import.meta.url), "utf8");
  assert.match(source, /min=\{isPublished \? institutionalDateTimeInputValue\(\) : undefined\}/);
});

// --- Policy metadata -------------------------------------------------------------------------

test("a past retention effective date is allowed and explains its immediate effect", () => {
  const ruleId = "84176b7a-7337-4123-a8f0-f084d7a0b970";
  const category = { category: "GRADUATE_TRACER", label: "Graduate Tracer", trigger: "SUBMITTED_AT", action: "ANONYMIZE", contract_version: 1 };
  const rule = (effective_on) => ({
    id: ruleId, code: "GTS-5Y", label: "Graduate Tracer five years", category: "GRADUATE_TRACER", contract_version: 1,
    trigger: "SUBMITTED_AT", action: "ANONYMIZE", duration_days: 1825, policy_reference: "Board Resolution 12",
    effective_on, status: "DRAFT", revision: 1, activated_at: null, retired_at: null,
    created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  });
  const user = { capabilities: ["privacy_governance.retention.view", "privacy_governance.retention.manage"] };
  const editor = (effective_on) => render(h(RetentionRuleEditor), {
    user,
    params: { ruleId },
    records: [
      [getPrivacyGovernanceGetRetentionRuleQueryKey(ruleId), rule(effective_on)],
      [getPrivacyGovernanceRetentionCategoriesQueryKey(), [category]],
    ],
  });

  const historical = editor("2021-07-01");
  const effective = inputTag(historical, "rule-effective");
  assert.doesNotMatch(effective, /\bmin=|\bmax=/);
  assert.match(effective, /aria-describedby="rule-effective-warning"/);
  assert.match(historical, /This effective date is in the past\. When activated, this rule may immediately apply to records whose retention period has already elapsed\./);

  const upcoming = editor(addDays(institutionalDateInputValue(), 30));
  assert.doesNotMatch(upcoming, /This effective date is in the past/);
});
