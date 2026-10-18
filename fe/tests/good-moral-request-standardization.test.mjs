import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { GoodMoralRequestPage } from "../src/features/good-moral/good-moral-request-page.tsx";
import { GoodMoralCorrectionForm } from "../src/features/good-moral/good-moral-correction-form.tsx";
import {
  GOOD_MORAL_SEMESTERS,
  GOOD_MORAL_YEAR_LEVELS,
  isCanonicalSemester,
  isCanonicalYearLevel,
} from "../src/features/good-moral/good-moral-shared.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getExitInterviewsGetMyStatusQueryKey } from "../src/lib/api/generated/exit-interviews/exit-interviews.ts";
import { getGoodMoralGetMyF4AcademicContextQueryKey, getGoodMoralListDegreeOptionsQueryKey } from "../src/lib/api/generated/good-moral/good-moral.ts";

const student = {
  id: "student-1",
  role: "STUDENT",
  first_name: "Juan",
  last_name: "Dela Cruz",
  email: "juan@example.edu",
  student_lifecycle_status: "CURRENT",
  designations: [],
  capabilities: ["good_moral.request_self", "good_moral.view_self", "exit_interviews.view_self"],
};

const graduateStudent = {
  ...student,
  student_lifecycle_status: "GRADUATED",
};

const staffUser = {
  id: "staff-1",
  role: "GUIDANCE_SERVICES_STAFF",
  first_name: "Guidance",
  last_name: "Staff",
  email: "staff@example.edu",
  student_lifecycle_status: null,
  designations: [],
  capabilities: ["good_moral.view", "good_moral.prepare"],
};

const clericalFields = [
  "year_level",
  "course",
  "major",
  "semester",
  "official_receipt_number",
  "official_receipt_date",
  "official_receipt_amount",
];

const canonicalItem = {
  id: "gm-req-1",
  variant: "CURRENT_STUDENT",
  status: "REQUESTED",
  applicant_name: "Juan Dela Cruz",
  student: { id: "student-1", display_name: "Juan Dela Cruz" },
  student_institutional_id: "2026-0001",
  inventory_id: "inv-1",
  academic_year: { id: "ay-1", label: "2026-2027" },
  year_level: "3rd Year",
  course: "BS Information Systems",
  college: "College of Computing and Multimedia Studies",
  semester: "First Semester",
  major: "Systems Development",
  degree: "",
  graduation_date: null,
  official_receipt_number: "",
  official_receipt_date: null,
  official_receipt_amount: null,
  form_revision: null,
  document_template_key: null,
  document_template_version: null,
  issued_by: null,
  issued_by_name_snapshot: "",
  issued_at: null,
  cancelled_at: null,
  cancellation: null,
  prepared_by: null,
  prepared_at: null,
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
  actions: {
    request_version: "2026-10-15T00:00:00.000000+00:00",
    preparation_version: null,
    can_correct: true,
    can_prepare: true,
    can_issue: false,
    can_cancel: false,
    can_download: false,
    correction_fields: clericalFields,
  },
};

const legacyItem = {
  ...canonicalItem,
  id: "gm-req-legacy",
  year_level: "Fourth",
  semester: "1st semester",
};

function renderComponent(element, user = student, querySetup = () => {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
  });
  client.setQueryData(getExitInterviewsGetMyStatusQueryKey(), {
    data: { graduation_good_moral_blocked: false },
    status: 200,
    headers: {},
  });
  client.setQueryData(getGoodMoralGetMyF4AcademicContextQueryKey(), {
    data: { status: "ELIGIBLE", academic_classification: "BACHELORS", year_level: 3 },
    status: 200,
    headers: {},
  });
  client.setQueryData(getGoodMoralListDegreeOptionsQueryKey(), {
    data: { items: ["Bachelor of Science in Information Systems"] },
    status: 200,
    headers: {},
  });
  querySetup(client);
  const html = renderToStaticMarkup(
    withNextRouter(
      h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, element)),
    ),
  );
  client.clear();
  return html;
}

test("GM-UX-2: Shared constants and type guards match approved undergraduate domain", () => {
  assert.deepEqual(GOOD_MORAL_YEAR_LEVELS, [
    "1st Year",
    "2nd Year",
    "3rd Year",
    "4th Year",
  ]);
  assert.deepEqual(GOOD_MORAL_SEMESTERS, [
    "First Semester",
    "Second Semester",
  ]);

  for (const level of GOOD_MORAL_YEAR_LEVELS) {
    assert.equal(isCanonicalYearLevel(level), true);
  }
  assert.equal(isCanonicalYearLevel("Fourth"), false);
  assert.equal(isCanonicalYearLevel("11th Year"), false);
  assert.equal(isCanonicalYearLevel(""), false);
  assert.equal(isCanonicalYearLevel(null), false);

  for (const sem of GOOD_MORAL_SEMESTERS) {
    assert.equal(isCanonicalSemester(sem), true);
  }
  assert.equal(isCanonicalSemester("Summer"), false);
  assert.equal(isCanonicalSemester("Midyear"), false);
  assert.equal(isCanonicalSemester("First"), false);
  assert.equal(isCanonicalSemester(""), false);
  assert.equal(isCanonicalSemester(null), false);
});

test("GM-UX-2: Student F4 shows Inventory-derived Year Level and Semester selection", () => {
  const html = renderComponent(h(GoodMoralRequestPage));

  assert.match(html, /<input[^>]*id="good-moral-year-level"[^>]*readOnly=""[^>]*value="3rd Year"/);
  assert.match(html, /Taken from your submitted Individual Inventory/);
  assert.doesNotMatch(html, /5th Year|6th Year|7th Year|8th Year|9th Year|10th Year/);

  // Semester select control exists and is required
  assert.match(html, /<select[^>]*id="good-moral-semester"[^>]*required=""/);
  // Default placeholder is present and unselected initially
  assert.match(html, /<option value=""[^>]*>Select your Semester<\/option>/);
  // Exactly the two approved Semester choices are present
  for (const sem of GOOD_MORAL_SEMESTERS) {
    assert.match(html, new RegExp(`<option value="${sem}"[^>]*>${sem}</option>`));
  }
  // Excluded terms must not be in the dropdown
  assert.doesNotMatch(html, /Summer/);
  assert.doesNotMatch(html, /Midyear/);
  assert.doesNotMatch(html, /Third Semester/);

  // Obsolete character count hints removed
  assert.doesNotMatch(html, /Up to 64 characters/);
  assert.doesNotMatch(html, /Up to 80 characters/);
});

test("GM-UX-2: Operational correction form offers only 1st–4th Year values", () => {
  const html = renderComponent(
    h(GoodMoralCorrectionForm, {
      item: canonicalItem,
      open: true,
      onRefresh: async () => canonicalItem,
      onClose() {},
    }),
    staffUser,
  );

  // Year Level select exists
  assert.match(html, /<select[^>]*id="good-moral-correction-year-level"/);
  // Canonical value 3rd Year is selected
  assert.match(html, /<option value="3rd Year" selected="">3rd Year<\/option>/);
  assert.doesNotMatch(html, /<option value="[5-9]th Year">|<option value="10th Year">/);

  // Semester select exists
  assert.match(html, /<select[^>]*id="good-moral-correction-semester"/);
  // Canonical value First Semester is selected
  assert.match(html, /<option value="First Semester" selected="">First Semester<\/option>/);

  // No historical value warning for canonical record
  assert.doesNotMatch(html, /Historical value as entered/);
});

test("GM-UX-2: Operational correction form displays and preserves historical non-canonical values", () => {
  const html = renderComponent(
    h(GoodMoralCorrectionForm, {
      item: legacyItem,
      open: true,
      onRefresh: async () => legacyItem,
      onClose() {},
    }),
    staffUser,
  );

  // Year Level select contains the legacy value clearly labeled
  assert.match(
    html,
    /<option value="Fourth" selected="">Fourth \(Current value as entered\)<\/option>/,
  );
  // Explanatory guidance for legacy Year Level
  assert.match(
    html,
    /Historical value as entered: “Fourth”\. Select a standardized Year Level to update it\./,
  );

  // Semester select contains the legacy value clearly labeled
  assert.match(
    html,
    /<option value="1st semester" selected="">1st semester \(Current value as entered\)<\/option>/,
  );
  // Explanatory guidance for legacy Semester
  assert.match(
    html,
    /Historical value as entered: “1st semester”\. Select a standardized Semester to update it\./,
  );

  // The supported Year Levels and both Semesters are available for deliberate replacement
  for (const level of GOOD_MORAL_YEAR_LEVELS) {
    assert.match(html, new RegExp(`<option value="${level}">${level}</option>`));
  }
  for (const sem of GOOD_MORAL_SEMESTERS) {
    assert.match(html, new RegExp(`<option value="${sem}">${sem}</option>`));
  }
});

test("GM-UX-2: F6 suggestions preserve historical fallback and disclose the verification limit", () => {
  const html = renderComponent(h(GoodMoralRequestPage), graduateStudent);

  // Graduate fields are rendered
  assert.match(html, /id="good-moral-degree"/);
  assert.match(html, /list="good-moral-degree-suggestions"/);
  assert.match(html, /Bachelor of Science in Information Systems/);
  assert.match(html, /Choose a current program or enter an older degree name/);
  assert.match(html, /F6 is for a completed UCN/);
  assert.match(html, /id="good-moral-major"/);
  assert.match(html, /id="good-moral-graduation-date"/);

  // Year Level and Semester must NOT be rendered for Graduate
  assert.doesNotMatch(html, /id="good-moral-year-level"/);
  assert.doesNotMatch(html, /id="good-moral-semester"/);
});
