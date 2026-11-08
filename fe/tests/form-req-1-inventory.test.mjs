// FORM-REQ-1: the editor mirrors the backend's F5 submission rules. Drafts stay incomplete,
// "Prefer not to specify" is gone, and a pending correction only answers for
// the fields it named. Every record here is a synthetic fixture.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { BackgroundSection } from "../src/features/inventory/editor/background-section.tsx";
import { FamilySection } from "../src/features/inventory/editor/family-section.tsx";
import { HealthSection } from "../src/features/inventory/editor/health-section.tsx";
import { OrganizationsSection } from "../src/features/inventory/editor/organizations-section.tsx";
import { PersonalSection } from "../src/features/inventory/editor/personal-section.tsx";
import { PlansSection } from "../src/features/inventory/editor/plans-section.tsx";
import { inventoryCorrectionIssueAllowed, readInventoryCorrectionTargets } from "../src/features/inventory/inventory-correction-targets.ts";
import { getInventoryDraftIssues, getInventorySubmissionIssues } from "../src/features/inventory/inventory-payload.ts";
import {
  annualIncomeOptions,
  civilStatusOptions,
  enumLabel,
  fourPsOptions,
  indigenousOptions,
  occupationOptions,
  parentLifeOptions,
  pwdOptions,
  religionOptions,
  transportationFrequencyOptions,
} from "../src/features/inventory/inventory-presentation.ts";

function render(element, user = { capabilities: [] }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element))),
  ));
  client.clear();
  return html;
}

function tag(html, id) {
  const found = html.match(new RegExp(`<[a-z]+[^>]*\\sid="${id}"[^>]*>`))?.[0];
  assert.ok(found, `missing #${id}`);
  return found;
}

const programIds = new Set(["program-1"]);

function parent(kind, overrides = {}) {
  const label = kind === "FATHER" ? "Father" : kind === "MOTHER" ? "Mother" : "Spouse";
  return {
    kind,
    name: `Synthetic ${label}`,
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
    ...overrides,
  };
}

const supportProfile = {
  four_ps_status: "NOT_BENEFICIARY",
  indigenous_peoples_status: "NOT_MEMBER",
  mother_life_status: "LIVING",
  father_life_status: "LIVING",
};

// Every blank on the F5 form, answered truthfully. Used as the baseline each rule test departs from.
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
    support_profile: { ...supportProfile },
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
      { level: "ELEMENTARY", school_attended_address: "Synthetic Elementary, Synthetic City", inclusive_years: "2012–2018" },
      { level: "JUNIOR_HIGH", school_attended_address: "Synthetic Junior High, Synthetic City", inclusive_years: "2018–2022" },
      { level: "SENIOR_HIGH", school_attended_address: "Synthetic Senior High, Synthetic City", inclusive_years: "2022–2024" },
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

const withFather = (patch) => completeDraft({
  family_members: completeDraft().family_members.map((member) => member.kind === "FATHER" ? { ...member, ...patch } : member),
});
const issuesIn = (draft, section) =>
  getInventorySubmissionIssues(draft, programIds).filter((issue) => issue.section === section);
const targetsIn = (draft, section) => issuesIn(draft, section).map((issue) => [issue.targetId, issue.message]);

// --- A complete form ---------------------------------------------------------------

test("a complete F5 form has nothing left to answer", () => {
  assert.deepEqual(getInventorySubmissionIssues(completeDraft(), programIds), []);
});

// --- "Prefer not to specify" is gone -------------------------------------------------

test("the truthful replacements are accepted at submission", () => {
  const truthful = completeDraft({
    family_members: completeDraft().family_members.filter((member) => member.kind !== "FATHER"),
    support_profile: {
      four_ps_status: "NOT_SURE",
      indigenous_peoples_status: "NOT_MEMBER",
      mother_life_status: "LIVING",
      father_life_status: "UNKNOWN",
    },
  });
  assert.deepEqual(getInventorySubmissionIssues(truthful, programIds), []);

  const unknownIncome = withFather({ annual_income_status: "UNKNOWN", annual_income_previous_year: null });
  assert.deepEqual(getInventorySubmissionIssues(unknownIncome, programIds), []);
});

test("the form never offers Prefer not to specify and keeps truthful unknown answers", () => {
  for (const options of [
    civilStatusOptions,
    religionOptions,
    occupationOptions,
    transportationFrequencyOptions,
    annualIncomeOptions,
    parentLifeOptions,
    fourPsOptions,
    indigenousOptions,
    pwdOptions,
  ]) {
    assert.ok(!options.some(([, label]) => label === "Prefer not to specify"));
  }
  assert.deepEqual(fourPsOptions.map(([value]) => value), ["BENEFICIARY", "NOT_BENEFICIARY", "NOT_SURE"]);
  assert.deepEqual(indigenousOptions.map(([value]) => value), ["MEMBER", "NOT_MEMBER"]);
  assert.deepEqual(pwdOptions.map(([value]) => value), ["PWD", "NON_PWD"]);
  assert.deepEqual(parentLifeOptions.map(([, label]) => label), ["Living", "Deceased", "Unknown"]);
  assert.deepEqual(annualIncomeOptions.map(([, label]) => label), ["Reported", "None", "Unknown"]);
  assert.equal(enumLabel("NOT_SURE"), "Not sure");
  assert.equal(enumLabel("UNKNOWN"), "Unknown");
});

// --- Conditions -------------------------------------------------------------------

test("a spouse is required only when the Student is married", () => {
  assert.deepEqual(issuesIn(completeDraft({ civil_status_category: "MARRIED" }), "family"), [
    { section: "family", targetId: "inventory-spouse-add", message: "Add your spouse's details." },
  ]);
  const blankSpouse = completeDraft({
    civil_status_category: "MARRIED",
    family_members: [...completeDraft().family_members, { kind: "SPOUSE" }],
  });
  assert.ok(targetsIn(blankSpouse, "family").some(([targetId]) => targetId === "inventory-family-spouse-name"));

  const married = completeDraft({
    civil_status_category: "MARRIED",
    family_members: [...completeDraft().family_members, parent("SPOUSE")],
  });
  assert.deepEqual(getInventorySubmissionIssues(married, programIds), []);
});

test("boarding-house details are required only for boarding-house residents", () => {
  assert.deepEqual(targetsIn(completeDraft({ living_arrangement: "BOARDING_HOUSE" }), "health"), [
    ["inventory-boarding-exclusive", "Answer whether your boarding room is exclusive to you."],
    ["inventory-boarding-landlord", "Add your boarding-house landlord's name."],
    ["inventory-boarding-address", "Add your boarding-house address."],
  ]);
  const boarding = completeDraft({
    living_arrangement: "BOARDING_HOUSE",
    boarding_exclusive: true,
    boarding_landlord_name: "Synthetic Landlord",
    boarding_address: "Synthetic Boarding House",
  });
  assert.deepEqual(getInventorySubmissionIssues(boarding, programIds), []);
});

test("a deceased or unknown parent's details are not required", () => {
  for (const status of ["DECEASED", "UNKNOWN"]) {
    const draft = completeDraft({
      family_members: completeDraft().family_members.filter((member) => member.kind !== "FATHER"),
      support_profile: { ...supportProfile, father_life_status: status },
    });
    assert.deepEqual(getInventorySubmissionIssues(draft, programIds), [], status);
  }
  // The living parent's details are still required.
  const living = completeDraft({
    family_members: completeDraft().family_members.filter((member) => member.kind !== "MOTHER"),
  });
  assert.ok(targetsIn(living, "family").some(([targetId]) => targetId === "inventory-family-mother-name"));
});

test("previous counseling details are required only when the Student had counseling", () => {
  assert.deepEqual(targetsIn(completeDraft({ prior_counseling_experience: true }), "plans"), [
    ["inventory-prior-counselor", "Add your previous counselor's name."],
    ["inventory-prior-counseling-when", "Add when you had previous counseling."],
    ["inventory-prior-counseling-where", "Add where you had previous counseling."],
  ]);
  const described = completeDraft({
    prior_counseling_experience: true,
    prior_counselor_name: "Synthetic Counselor",
    prior_counseling_when: "2025",
    prior_counseling_where: "Synthetic Guidance Office",
  });
  assert.deepEqual(getInventorySubmissionIssues(described, programIds), []);
  assert.deepEqual(getInventorySubmissionIssues(completeDraft({ prior_counseling_experience: false }), programIds), []);
});

test("an unsatisfied schedule needs its reason", () => {
  assert.deepEqual(targetsIn(completeDraft({ schedule_satisfied: false }), "education"), [
    ["inventory-schedule-reason", "Explain why you are not satisfied with your present schedule."],
  ]);
  assert.deepEqual(
    getInventorySubmissionIssues(
      completeDraft({ schedule_satisfied: false, schedule_satisfaction_reason: "Synthetic conflict." }),
      programIds,
    ),
    [],
  );
});

test("None is a complete accident and operation answer; anything else needs its effect", () => {
  assert.deepEqual(getInventorySubmissionIssues(completeDraft({ accidents_experienced: "none" }), programIds), []);
  assert.deepEqual(targetsIn(completeDraft({ accidents_experienced: "Fell from stairs" }), "health"), [
    ["inventory-accidents-effect", "Describe the effect of the accidents you experienced."],
  ]);
  assert.deepEqual(
    getInventorySubmissionIssues(
      completeDraft({ operations_experienced: "None", operations_effect: "" }),
      programIds,
    ),
    [],
  );
  assert.deepEqual(targetsIn(completeDraft({ operations_experienced: "Appendix" }), "health"), [
    ["inventory-operations-effect", "Describe the effect of the operations you experienced."],
  ]);
});

// --- Educational history and remaining requirements ---------------------------------

test("elementary, junior high, and senior high school are the required levels", () => {
  assert.deepEqual(getInventorySubmissionIssues(completeDraft({ education_entries: [] }), programIds), [
    { section: "education", targetId: "inventory-education-elementary-school", message: "Add the school you attended for elementary and its address." },
    { section: "education", targetId: "inventory-education-elementary-years", message: "Add the inclusive years you attended elementary." },
    { section: "education", targetId: "inventory-education-junior_high-school", message: "Add the school you attended for junior high school and its address." },
    { section: "education", targetId: "inventory-education-junior_high-years", message: "Add the inclusive years you attended junior high school." },
    { section: "education", targetId: "inventory-education-senior_high-school", message: "Add the school you attended for senior high school and its address." },
    { section: "education", targetId: "inventory-education-senior_high-years", message: "Add the inclusive years you attended senior high school." },
  ]);
  // Preparatory, technical/vocational, and collegiate stay optional.
  assert.deepEqual(getInventorySubmissionIssues(completeDraft(), programIds), []);
});

test("the current Program is required and every selected transportation mode needs its frequency", () => {
  assert.deepEqual(targetsIn(completeDraft({ program_id: null }), "education"), [
    ["inventory-program", "Choose a currently active program."],
  ]);
  const bus = completeDraft({ transportation_entries: [{ mode: "BUS" }] });
  assert.deepEqual(targetsIn(bus, "organizations"), [
    ["inventory-transport-bus-frequency-category", "Choose how often you use the bus."],
  ]);
  assert.deepEqual(getInventoryDraftIssues(bus), []);
});

// --- Required markers ---------------------------------------------------------------

test("required answers are marked in the editor, including a living parent's details", () => {
  const personal = render(h(PersonalSection, { draft: completeDraft(), onChange() {} }));
  for (const id of [
    "inventory-full-name",
    "inventory-nickname",
    "inventory-student-number",
    "inventory-place-of-birth",
    "inventory-nationality",
    "inventory-birth-order",
    "inventory-contact-number",
    "inventory-email",
    "inventory-languages-home",
    "inventory-languages-fluent",
    "inventory-religion-birth",
    "inventory-current-region",
    "inventory-current-city",
  ]) {
    assert.match(tag(personal, id), /aria-required="true"/, id);
  }

  const family = render(h(FamilySection, { draft: completeDraft(), onChange() {} }));
  for (const id of [
    "inventory-family-father-name",
    "inventory-family-father-occupation-category",
    "inventory-family-father-income-status",
    "inventory-family-mother-contact",
    "inventory-parent-statuses",
    "inventory-guardian-name",
    "inventory-emergency-number",
  ]) {
    assert.match(tag(family, id), /aria-required="true"/, id);
  }

  const deceased = completeDraft({ support_profile: { ...supportProfile, father_life_status: "DECEASED" } });
  const fatherless = render(h(FamilySection, { draft: deceased, onChange() {} }));
  assert.doesNotMatch(tag(fatherless, "inventory-family-father-name"), /aria-required/);

  const background = render(h(BackgroundSection, { draft: completeDraft(), onChange() {} }));
  assert.match(tag(background, "inventory-sibling-0-name"), /aria-required="true"/);
  assert.match(tag(background, "inventory-characteristics"), /aria-required="true"/);

  const boarding = render(h(HealthSection, { draft: completeDraft({ living_arrangement: "BOARDING_HOUSE" }), onChange() {} }));
  assert.match(tag(boarding, "inventory-boarding-exclusive"), /aria-required="true"/);
  assert.match(tag(boarding, "inventory-physical-disadvantage"), /aria-required="true"/);

  const plans = render(h(PlansSection, { draft: completeDraft(), onChange() {} }));
  assert.match(tag(plans, "inventory-prior-counseling"), /aria-required="true"/);
  assert.doesNotMatch(plans, /id="inventory-prior-counselor"/);
  const prior = render(h(PlansSection, { draft: completeDraft({ prior_counseling_experience: true }), onChange() {} }));
  assert.match(tag(prior, "inventory-prior-counselor"), /aria-required="true"/);

  const organizations = render(h(OrganizationsSection, { draft: completeDraft({ transportation_entries: [{ mode: "BUS" }] }), onChange() {} }));
  assert.match(tag(organizations, "inventory-transport-bus-frequency-category"), /aria-required="true"/);
});

// --- Corrections ---------------------------------------------------------------------

test("a pending correction only lets the answers it named block resubmission", () => {
  const { targets } = readInventoryCorrectionTargets([
    "personal.civil_status",
    "family.father.annual_income",
    "background.siblings",
    "section.education",
  ]);
  const allowed = (section, targetId) => inventoryCorrectionIssueAllowed(targets, { section, targetId });
  assert.ok(allowed("personal", "inventory-civil-status"));
  assert.ok(allowed("personal", "inventory-civil-status-other"));
  assert.ok(!allowed("personal", "inventory-nickname"));
  assert.ok(allowed("family", "inventory-family-father-income-status"));
  assert.ok(allowed("family", "inventory-family-father-income-amount"));
  assert.ok(!allowed("family", "inventory-family-mother-name"));
  assert.ok(allowed("background", "inventory-siblings"));
  assert.ok(allowed("background", "inventory-sibling-2-age"));
  assert.ok(allowed("education", "inventory-program"), "a whole-section target covers its section");
  assert.ok(!allowed("health", "inventory-height"));
  assert.ok(
    !inventoryCorrectionIssueAllowed([], { section: "personal", targetId: "inventory-nickname" }),
    "a reason-only correction names no field",
  );
});
