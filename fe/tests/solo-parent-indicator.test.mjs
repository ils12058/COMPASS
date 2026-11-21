// ADR-121: separate "solo parent" from civil status in the Inventory editor, read-only view,
// and Student Profiling report. Every record here is a synthetic fixture.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { FamilySection } from "../src/features/inventory/editor/family-section.tsx";
import { PersonalSection } from "../src/features/inventory/editor/personal-section.tsx";
import { InventoryReadOnly } from "../src/features/inventory/read-only/inventory-read-only.tsx";
import {
  getInventorySubmissionIssues,
  toInventoryPayload,
} from "../src/features/inventory/inventory-payload.ts";
import {
  civilStatusOptions,
  enumLabel,
  soloParentOptions,
} from "../src/features/inventory/inventory-presentation.ts";
import { StudentProfileReportContent } from "../src/features/reports/student-profile-report-content.tsx";

function render(element, user = { capabilities: [] }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
  });
  const html = renderToStaticMarkup(
    withNextRouter(
      h(
        QueryClientProvider,
        { client },
        h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element)),
      ),
    ),
  );
  client.clear();
  return html;
}

const programIds = new Set(["program-1"]);

function parent(kind) {
  return {
    kind,
    name: `Synthetic ${kind}`,
    date_of_birth: "1975-01-01",
    place_of_birth: "Synthetic City",
    current_address: "Synthetic Street",
    permanent_address: "Synthetic Street",
    contact_number: "0917 000 0001",
    email_address: "None",
    educational_attainment: "College",
    occupation_category: "FARMER",
    annual_income_status: "NONE",
    annual_income_previous_year: null,
    business_address: "None",
    business_telephone: "None",
    languages_spoken: "Filipino",
    religion_raised_with: "Roman Catholic",
    current_religion: "Roman Catholic",
  };
}

function completeDraft(overrides = {}) {
  return {
    full_name: "Synthetic Student",
    nickname: "Syn",
    student_number: "2026-00001",
    date_of_birth: "2006-01-01",
    place_of_birth: "Synthetic City",
    nationality: "Filipino",
    sex: "FEMALE",
    birth_order_among_siblings: "First",
    civil_status_category: "SINGLE",
    current_address: "Synthetic Street",
    permanent_address: "Synthetic Street",
    contact_number: "0917 000 0000",
    email_address: "synthetic@example.test",
    languages_spoken_at_home: "Filipino",
    languages_most_fluent: "Filipino, English",
    religion_from_birth: "Roman Catholic",
    current_religion_category: "ROMAN_CATHOLIC",
    geographic_locations: [
      { kind: "CURRENT", region_psgc_code: "010000000", city_municipality_psgc_code: "0100101000" },
    ],
    family_members: [parent("FATHER"), parent("MOTHER")],
    parent_statuses: ["MARRIED_ANNULLED_LEGALLY_SEPARATED"],
    guardian_name: "Synthetic Guardian",
    guardian_relationship: "Aunt",
    guardian_address: "Synthetic Street",
    guardian_contact_number: "0917 000 0002",
    emergency_contact_name: "Synthetic Contact",
    emergency_contact_number: "0917 000 0003",
    support_profile: {
      four_ps_status: "NOT_BENEFICIARY",
      indigenous_peoples_status: "NOT_MEMBER",
      mother_life_status: "LIVING",
      father_life_status: "LIVING",
      solo_parent_status: "NO",
    },
    siblings: [{ sort_order: 0, name: "Synthetic Student", sex: "FEMALE", age: 18, is_self: true }],
    friends_in_school: "None",
    friends_outside_school: "None",
    special_interest: "None",
    special_skills_talents: "None",
    hobbies_recreation: "None",
    ambition_goal: "None",
    characteristics: "None",
    living_arrangement: "OWN_HOUSE",
    present_place_people_count: 4,
    room_sharing_people_count: 2,
    accidents_experienced: "None",
    operations_experienced: "None",
    height: "160 cm",
    weight: "55 kg",
    physical_disadvantage: "None",
    pwd_status: "NON_PWD",
    illness_this_year: "None",
    previous_illness: "None",
    immunizations: [],
    education_entries: [
      { level: "ELEMENTARY", school_attended_address: "Synthetic Elementary", inclusive_years: "2012–2018" },
      { level: "JUNIOR_HIGH", school_attended_address: "Synthetic Junior High", inclusive_years: "2018–2022" },
      { level: "SENIOR_HIGH", school_attended_address: "Synthetic Senior High", inclusive_years: "2022–2024" },
    ],
    program_id: "program-1",
    year_level: 1,
    schedule_satisfied: true,
    course_first_choice: true,
    course_choice_reasons: ["INTEREST_APTITUDE"],
    lowest_subjects_grades: "Math — 85",
    highest_subjects_grades: "English — 95",
    inclination_performing_arts: "None",
    inclination_sports: "None",
    inclination_leadership: "None",
    interests: ["PAINTING"],
    other_skills_hobbies: "None",
    desired_extracurricular_activities: "None",
    reading_preferences: "None",
    handedness: "RIGHT",
    daily_hours_class: "6",
    daily_hours_library: "1",
    daily_hours_studying: "2",
    daily_hours_rest: "8",
    daily_hours_recreation: "2",
    daily_hours_other: "1",
    ideal_monthly_allowance: "FROM_500_TO_1000",
    intended_work_field: "PROFESSIONAL",
    prior_counseling_experience: false,
    current_concerns: "None",
    current_fears: "None",
    organization_memberships: [],
    transportation_entries: [],
    ...overrides,
  };
}

test("civil status choices list the six real statuses and omit Solo Parent", () => {
  assert.deepEqual(civilStatusOptions, [
    ["SINGLE", "Single"],
    ["MARRIED", "Married"],
    ["WIDOWED", "Widowed"],
    ["SEPARATED", "Separated"],
    ["ANNULLED", "Annulled"],
    ["OTHER", "Other"],
  ]);
  assert.deepEqual(soloParentOptions, [
    ["YES", "Yes"],
    ["NO", "No"],
  ]);

  const html = render(h(PersonalSection, { draft: completeDraft(), onChange() {} }));
  for (const label of ["Single", "Married", "Widowed", "Separated", "Annulled", "Other"]) {
    assert.ok(html.includes(`>${label}</option>`), `renders ${label}`);
  }
  assert.ok(!html.includes("SOLO_PARENT"));
  assert.ok(!html.includes("Solo Parent"));
});

test("family section renders the separate required solo-parent question with RA 11861 help text", () => {
  const html = render(h(FamilySection, { draft: completeDraft(), onChange() {} }));
  assert.ok(html.includes("Are you a solo parent?"));
  assert.ok(
    html.includes(
      "A solo parent is raising a child alone, for example because of a partner&#x27;s death, separation, abandonment, or work abroad (Republic Act No. 11861).",
    ),
  );
  const selectTag = html.match(/<select[^>]*\sid="inventory-solo-parent"[^>]*>/)?.[0];
  assert.ok(selectTag, "renders #inventory-solo-parent");
  assert.match(selectTag, /aria-required="true"/);
});

test("submission requires solo-parent status and supports Widowed/Separated/Annulled without spouse", () => {
  const missingSolo = completeDraft({
    support_profile: {
      four_ps_status: "NOT_BENEFICIARY",
      indigenous_peoples_status: "NOT_MEMBER",
      mother_life_status: "LIVING",
      father_life_status: "LIVING",
      solo_parent_status: null,
    },
  });
  assert.deepEqual(getInventorySubmissionIssues(missingSolo, programIds), [
    {
      section: "family",
      targetId: "inventory-solo-parent",
      message: "Answer whether you are a solo parent.",
    },
  ]);

  for (const status of ["WIDOWED", "SEPARATED", "ANNULLED"]) {
    const draft = completeDraft({
      civil_status_category: status,
      support_profile: {
        four_ps_status: "NOT_BENEFICIARY",
        indigenous_peoples_status: "NOT_MEMBER",
        mother_life_status: "LIVING",
        father_life_status: "LIVING",
        solo_parent_status: "YES",
      },
    });
    assert.deepEqual(getInventorySubmissionIssues(draft, programIds), [], status);
  }
});

test("toInventoryPayload clears legacy SOLO_PARENT draft civil status while keeping solo_parent_status", () => {
  const legacyDraftResponse = {
    id: "inv-legacy-draft",
    academic_year: { id: "year", label: "2026-2027" },
    status: "DRAFT",
    program: null,
    form_revision: {
      id: "rev",
      family_key: "individual_inventory",
      internal_schema_version: 1,
      official_code: "UCN-OP-GCO-01F5",
      official_revision: "1",
    },
    correction_pending: false,
    latest_correction: null,
    civil_status_category: "SOLO_PARENT",
    civil_status: "Solo Parent",
    support_profile: {
      four_ps_status: "NOT_BENEFICIARY",
      indigenous_peoples_status: "NOT_MEMBER",
      mother_life_status: "LIVING",
      father_life_status: "LIVING",
      solo_parent_status: "YES",
    },
  };
  const payload = toInventoryPayload(legacyDraftResponse);
  assert.equal(payload.civil_status_category, null);
  assert.equal(payload.civil_status, "");
  assert.equal(payload.support_profile.solo_parent_status, "YES");
});

test("read-only view displays solo parent status and plain legacy civil status label", () => {
  assert.equal(enumLabel("SOLO_PARENT"), "Solo parent (recorded before the update)");
  const legacySubmitted = {
    ...completeDraft({
      civil_status_category: "SOLO_PARENT",
      civil_status: "Solo Parent",
      support_profile: {
        four_ps_status: "NOT_BENEFICIARY",
        indigenous_peoples_status: "NOT_MEMBER",
        mother_life_status: "LIVING",
        father_life_status: "LIVING",
        solo_parent_status: "YES",
      },
    }),
    id: "inv-legacy-sub",
    academic_year: { id: "year", label: "2026-2027" },
    status: "SUBMITTED",
    submitted_at: "2026-08-30T04:00:00Z",
    program: { id: "program-1", code: "BSIS", name: "BS Information Systems" },
    form_revision: {
      id: "rev",
      family_key: "individual_inventory",
      internal_schema_version: 1,
      official_code: "UCN-OP-GCO-01F5",
      official_revision: "1",
    },
    correction_pending: false,
    latest_correction: null,
  };
  const html = render(h(InventoryReadOnly, { inventory: legacySubmitted }));
  assert.ok(html.includes("Solo parent"));
  assert.ok(html.includes(">Yes<"));
  assert.ok(html.includes("Solo parent (recorded before the update)"));
  assert.ok(!html.includes("SOLO_PARENT"));
});

test("student profile report renders Solo Parent Status right after PWD Status", () => {
  const programColumns = [
    {
      key: "program:p1",
      program_id: "p1",
      code: "BSIS",
      name: "BS Information Systems",
      submitted_inventory_count: 2,
      college: { id: "c1", code: "CCMS", name: "College of Computing" },
      campus: { id: "camp1", code: "MAIN", name: "Main Campus" },
    },
  ];
  const makeSection = (key, label, rows) => ({
    key,
    label,
    denominator: 2,
    rows: rows.map(([rowKey, rowLabel, count]) => ({
      key: rowKey,
      label: rowLabel,
      total_count: count,
      percentage: count === 0 ? "0.00" : count === 1 ? "50.00" : "100.00",
      program_counts: [{ program_key: "program:p1", count }],
    })),
  });
  const report = {
    report_context: {
      academic_year: { id: "ay1", label: "2026-2027", is_current: true },
      campus: null,
      college: null,
      program: null,
      year_level: null,
      year_level_label: null,
      submitted_inventory_count: 2,
      reporting_scope: { is_global: true, colleges: [] },
      generated_at: "2026-10-11T07:00:00Z",
    },
    methodology: {
      profile_population_note: "Profile population note.",
      coverage_note: "Coverage note.",
      access_scope_note: "Report coverage: all Campuses and Colleges.",
      historical_coverage_note: null,
      parent_income_bracket_basis: "PIDS",
      parent_family_status_note: "Students may tick more than one.",
    },
    disclosure_warnings: [],
    program_columns: programColumns,
    inventory_coverage: {
      mode: "CURRENT",
      eligible_student_count: 2,
      submitted_count: 2,
      draft_count: 0,
      missing_count: 0,
      applied_filters: [],
      ignored_filters: [],
      scope_note: "Coverage scope note.",
      reconciliation: {
        profile_submitted_count: 2,
        coverage_submitted_count: 2,
        in_both_count: 2,
        profile_only_count: 0,
        coverage_only_count: 0,
      },
      academic_alignment: {
        current_student_count: 2,
        current_with_placement_count: 2,
        current_without_placement_count: 0,
        submitted_inventory_count: 2,
        submitted_with_program_count: 2,
        submitted_without_program_count: 0,
        placement_program_match_count: 2,
        placement_program_mismatch_count: 0,
        precedence_note: "Precedence note.",
      },
    },
    sections: {
      sex: makeSection("sex", "Distribution of Students based on Sex", [["FEMALE", "Female", 2]]),
      age: makeSection("age", "Distribution of Students based on Age", [["20", "20", 2]]),
      civil_status: makeSection("civil_status", "Distribution of Students based on Civil Status", [
        ["SINGLE", "Single", 1],
        ["WIDOWED", "Widowed", 1],
      ]),
      physical_disadvantage: makeSection(
        "physical_disadvantage",
        "Distribution of Students based on PWD Status",
        [
          ["PWD", "PWD", 0],
          ["NON_PWD", "Non-PWD", 2],
        ],
      ),
      solo_parent_status: makeSection(
        "solo_parent_status",
        "Distribution of Students based on Solo Parent Status",
        [
          ["YES", "Yes", 1],
          ["NO", "No", 1],
        ],
      ),
      current_religion: makeSection(
        "current_religion",
        "Distribution of Students based on Current Religion",
        [["ROMAN_CATHOLIC", "Roman Catholic", 2]],
      ),
      mother_life_status: makeSection(
        "mother_life_status",
        "Distribution of Students based on Mother Life Status",
        [["LIVING", "Living", 2]],
      ),
      father_life_status: makeSection(
        "father_life_status",
        "Distribution of Students based on Father Life Status",
        [["LIVING", "Living", 2]],
      ),
      parent_family_status: makeSection(
        "parent_family_status",
        "Distribution of Students based on Parent Family Status",
        [["MARRIED_ANNULLED_LEGALLY_SEPARATED", "Married / Annulled / Legally Separated", 2]],
      ),
      city_municipality: {
        key: "city_municipality",
        label: "Distribution of Students based on City / Municipality",
        denominator: 2,
        rows: [],
      },
      parent_annual_income: makeSection(
        "parent_annual_income",
        "Distribution of Students based on Parent Annual Income",
        [["NONE", "None", 2]],
      ),
      mother_occupation: makeSection(
        "mother_occupation",
        "Distribution of Students based on Mother Occupation",
        [["FARMER", "Farmer", 2]],
      ),
      father_occupation: makeSection(
        "father_occupation",
        "Distribution of Students based on Father Occupation",
        [["FARMER", "Farmer", 2]],
      ),
      living_condition: makeSection(
        "living_condition",
        "Distribution of Students based on Living Condition",
        [["OWN_HOUSE", "Own House", 2]],
      ),
    },
  };

  const html = render(
    h(StudentProfileReportContent, { report, isGlobal: true, isFetching: false }),
  );
  const pwdPos = html.indexOf("Distribution of Students based on PWD Status");
  const soloPos = html.indexOf("Distribution of Students based on Solo Parent Status");
  const religionPos = html.indexOf("Distribution of Students based on Current Religion");
  assert.ok(pwdPos > -1, "renders PWD Status section");
  assert.ok(soloPos > -1, "renders Solo Parent Status section");
  assert.ok(religionPos > -1, "renders Current Religion section");
  assert.ok(pwdPos < soloPos && soloPos < religionPos, "Solo Parent Status follows PWD Status");
});
