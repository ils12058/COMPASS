// FORM-INPUT-1C: input limits, save-time rules, numeric controls, and field guidance that follow the
// existing server contracts. Every record here is a synthetic fixture.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { BackgroundSection } from "../src/features/inventory/editor/background-section.tsx";
import { EducationSection } from "../src/features/inventory/editor/education-section.tsx";
import { FamilySection } from "../src/features/inventory/editor/family-section.tsx";
import { HealthSection } from "../src/features/inventory/editor/health-section.tsx";
import { InterestsSection } from "../src/features/inventory/editor/interests-section.tsx";
import { OrganizationsSection } from "../src/features/inventory/editor/organizations-section.tsx";
import { PersonalSection } from "../src/features/inventory/editor/personal-section.tsx";
import { PlansSection } from "../src/features/inventory/editor/plans-section.tsx";
import { ReviewSection } from "../src/features/inventory/editor/review-section.tsx";
import {
  educationTextLimits,
  familyMemberTextLimits,
  inventoryTextLimits,
  organizationTextLimits,
  siblingTextLimits,
  transportationTextLimits,
} from "../src/features/inventory/inventory-field-limits.ts";
import {
  getInventoryDraftIssues,
  getInventorySubmissionIssues,
  normalizeInventoryPayload,
} from "../src/features/inventory/inventory-payload.ts";
import { exitInterviewFormFromDetail } from "../src/features/exit-interviews/exit-interview-presentation.ts";
import { ExitInterviewFormSections } from "../src/features/exit-interviews/exit-interview-form-sections.tsx";
import { ReferralCreatePage } from "../src/features/referrals/referral-create-page.tsx";
import { institutionalDateInputValue } from "../src/lib/institutional-time.ts";
import { YEAR_LEVELS, yearLevelLabel } from "../src/lib/year-level.ts";

function render(element, user = { capabilities: [] }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element))),
  ));
  client.clear();
  return html;
}

function tag(html, id, element = "input") {
  const found = html.match(new RegExp(`<${element}[^>]*id="${id}"[^>]*>`))?.[0];
  assert.ok(found, `missing ${element} #${id}`);
  return found;
}

const section = (Component, draft, validationIssues = []) => render(h(Component, { draft, onChange() {}, validationIssues }));
const issueTargets = (issues) => issues.map((issue) => [issue.section, issue.targetId, issue.message]);

// --- X-1: limits mirror the server ----------------------------------------------------------

// Reads the private answer limits COMPASS enforces (be/compass/inventory/confidential_content.py).
function serverLimits() {
  const source = readFileSync(new URL("../../be/compass/inventory/confidential_content.py", import.meta.url), "utf8");
  const fields = source.slice(source.indexOf("FIELDS = {"), source.indexOf("BINDINGS = {"));
  const families = {};
  for (const match of fields.matchAll(/"(\w+)": \{([^}]*)\}/g)) {
    families[match[1]] = Object.fromEntries(
      [...match[2].matchAll(/"(\w+)": (\d+|None)/g)].map(([, key, limit]) => [key, limit === "None" ? null : Number(limit)]),
    );
  }
  return families;
}

function modelMaxLength(field) {
  const source = readFileSync(new URL("../../be/compass/inventory/models.py", import.meta.url), "utf8");
  const limit = source.match(new RegExp(`\\n    ${field} = models\\.CharField\\(max_length=(\\d+)`))?.[1];
  assert.ok(limit, `missing model field ${field}`);
  return Number(limit);
}

test("Inventory text limits are the server's limits, and unbounded answers stay unbounded", () => {
  const server = serverLimits();
  const pairs = [
    [inventoryTextLimits, "StudentInventory"],
    [familyMemberTextLimits, "InventoryFamilyMember"],
    [siblingTextLimits, "InventorySibling"],
    [educationTextLimits, "InventoryEducationEntry"],
    [organizationTextLimits, "InventoryOrganizationMembership"],
    [transportationTextLimits, "InventoryTransportationEntry"],
  ];
  const modelColumns = { full_name: "full_name_snapshot", major: "major" };
  for (const [limits, family] of pairs) {
    for (const [field, limit] of Object.entries(limits)) {
      const expected = family === "StudentInventory" && field in modelColumns
        ? modelMaxLength(modelColumns[field])
        : server[family][field];
      assert.equal(limit, expected, `${family}.${field}`);
    }
    // Every bounded text answer the Student types is covered (sibling sex is a select).
    for (const [field, limit] of Object.entries(server[family])) {
      if (limit === null || (family === "InventorySibling" && field === "sex")) continue;
      assert.ok(field in limits, `${family}.${field} has a server limit but no editor limit`);
    }
  }
  for (const field of ["current_address", "permanent_address", "current_concerns", "current_fears", "characteristics"]) {
    assert.equal(server.StudentInventory[field], null);
    assert.ok(!(field in inventoryTextLimits), `${field} stays unbounded`);
  }
});

const nickname100 = "N".repeat(100);
const personalDraft = { full_name: "Maria Santos", nickname: "Mia", geographic_locations: [] };

test("bounded Inventory fields expose their limit; unbounded fields do not", () => {
  const personal = section(PersonalSection, personalDraft);
  assert.match(tag(personal, "inventory-nickname"), /maxLength="100"/i);
  assert.match(tag(personal, "inventory-full-name"), /maxLength="200"/i);
  assert.match(tag(personal, "inventory-contact-number"), /maxLength="64"/i);
  assert.doesNotMatch(tag(personal, "inventory-current-address", "textarea"), /maxlength/i);

  const family = section(FamilySection, { family_members: [{ kind: "FATHER" }] });
  assert.match(tag(family, "inventory-family-father-name"), /maxLength="160"/i);
  assert.match(tag(family, "inventory-guardian-relationship"), /maxLength="120"/i);
  assert.doesNotMatch(tag(family, "inventory-guardian-address", "textarea"), /maxlength/i);

  const background = section(BackgroundSection, { siblings: [{ sort_order: 0 }] });
  assert.match(tag(background, "inventory-sibling-0-name"), /maxLength="160"/i);
  const education = section(EducationSection, { education_entries: [] });
  assert.match(tag(education, "inventory-education-elementary-years"), /maxLength="100"/i);
  assert.match(tag(education, "inventory-major"), /maxLength="180"/i);
  const plans = section(PlansSection, { prior_counseling_experience: true });
  assert.match(tag(plans, "inventory-prior-counseling-where"), /maxLength="200"/i);
  assert.doesNotMatch(tag(plans, "inventory-current-concerns", "textarea"), /maxlength/i);
  const organizations = section(OrganizationsSection, {
    organization_memberships: [{ scope: "INSIDE_SCHOOL", sort_order: 0 }],
    transportation_entries: [{ mode: "BUS", frequency_category: "OTHER", frequency: "" }],
  });
  assert.match(tag(organizations, "inventory-membership-inside_school-0-organization"), /maxLength="180"/i);
  assert.match(tag(organizations, "inventory-transport-bus-frequency-other"), /maxLength="100"/i);
});

test("an answer at its limit says so and is described by that message; a shorter one is not", () => {
  const atLimit = section(PersonalSection, { ...personalDraft, nickname: nickname100 });
  const input = tag(atLimit, "inventory-nickname");
  assert.match(input, /aria-describedby="inventory-nickname-limit"/);
  assert.match(atLimit, /id="inventory-nickname-limit" aria-live="polite"[^>]*>This field allows up to 100 characters\.</);

  const below = section(PersonalSection, { ...personalDraft, nickname: "N".repeat(99) });
  assert.doesNotMatch(tag(below, "inventory-nickname"), /aria-describedby="[^"]*inventory-nickname-limit/);
  assert.match(below, /id="inventory-nickname-limit" aria-live="polite" class="sr-only"><\/p>/);
  // A saved value is shown in full; the editor never shortens it.
  const longer = section(PersonalSection, { ...personalDraft, nickname: `${nickname100}X` });
  assert.match(tag(longer, "inventory-nickname"), new RegExp(`value="${nickname100}X"`));
});

// --- X-2: transportation frequency ----------------------------------------------------------

const baseDraft = {
  family_members: [],
  geographic_locations: [],
  transportation_entries: [],
  siblings: [],
};

test("a transportation row without a frequency blocks submission with a field-level issue", () => {
  const missing = getInventorySubmissionIssues({ ...baseDraft, transportation_entries: [{ mode: "BUS" }] }, undefined);
  assert.deepEqual(
    issueTargets(missing.filter((issue) => issue.section === "organizations")),
    [["organizations", "inventory-transport-bus-frequency-category", "Choose how often you use the bus."]],
  );
  // Saving a draft without a frequency is still allowed, as on the server.
  assert.deepEqual(getInventoryDraftIssues({ ...baseDraft, transportation_entries: [{ mode: "BUS" }] }), []);

  const chosen = getInventorySubmissionIssues({ ...baseDraft, transportation_entries: [{ mode: "BUS", frequency_category: "DAILY" }] }, undefined);
  assert.equal(chosen.filter((issue) => issue.section === "organizations").length, 0);

  const html = section(OrganizationsSection, { transportation_entries: [{ mode: "BUS" }] }, missing.filter((issue) => issue.section === "organizations"));
  assert.match(tag(html, "inventory-transport-bus-frequency-category", "select"), /aria-invalid="true"/);
  assert.match(html, /id="inventory-transport-bus-frequency-category-error"[^>]*>Choose how often you use the bus\./);
});

test("Other frequency keeps its detail field, and an empty detail blocks saving as the server does", () => {
  const other = { ...baseDraft, transportation_entries: [{ mode: "JEEPNEY", frequency_category: "OTHER", frequency: " " }] };
  assert.deepEqual(issueTargets(getInventoryDraftIssues(other)), [
    ["organizations", "inventory-transport-jeepney-frequency-other", "Describe how often you use the jeepney."],
  ]);
  const described = { ...baseDraft, transportation_entries: [{ mode: "JEEPNEY", frequency_category: "OTHER", frequency: "Twice monthly" }] };
  assert.deepEqual(getInventoryDraftIssues(described), []);
  assert.equal(normalizeInventoryPayload(described).transportation_entries[0].frequency, "Twice monthly");
  // Choosing a fixed frequency still clears the detail before saving.
  assert.equal(normalizeInventoryPayload({ ...baseDraft, transportation_entries: [{ mode: "JEEPNEY", frequency_category: "DAILY", frequency: "old" }] }).transportation_entries[0].frequency, "");
  const html = section(OrganizationsSection, other);
  assert.match(tag(html, "inventory-transport-jeepney-frequency-other"), /aria-required="true"/);
});

// --- X-3: reported parent income ------------------------------------------------------------

const income = (kind, annual_income_status, annual_income_previous_year) => ({ kind, annual_income_status, annual_income_previous_year });

test("a Reported income must be greater than ₱0 before saving or submitting", () => {
  const zero = { ...baseDraft, family_members: [income("FATHER", "REPORTED", "0")] };
  assert.deepEqual(issueTargets(getInventoryDraftIssues(zero)), [
    ["family", "inventory-family-father-income-amount", "Enter an amount greater than ₱0 for father's income."],
  ]);
  assert.deepEqual(
    issueTargets(getInventoryDraftIssues({ ...baseDraft, family_members: [income("MOTHER", "REPORTED", "-5")] })),
    [["family", "inventory-family-mother-income-amount", "Enter an amount greater than ₱0 for mother's income."]],
  );
  assert.deepEqual(
    issueTargets(getInventoryDraftIssues({ ...baseDraft, family_members: [income("SPOUSE", "REPORTED", "0.00")] })),
    [["family", "inventory-family-spouse-income-amount", "Enter an amount greater than ₱0 for spouse's income."]],
  );
  assert.deepEqual(
    issueTargets(getInventoryDraftIssues({ ...baseDraft, family_members: [income("FATHER", "REPORTED", null)] })),
    [["family", "inventory-family-father-income-amount", "Enter the reported previous-year income for father."]],
  );
  const submission = getInventorySubmissionIssues(zero, undefined);
  assert.ok(submission.some((issue) => issue.targetId === "inventory-family-father-income-amount"));

  assert.deepEqual(getInventoryDraftIssues({ ...baseDraft, family_members: [income("FATHER", "REPORTED", "150000.50")] }), []);
});

test("None and Not specified stay distinct from zero and from a missing answer", () => {
  const draft = {
    ...baseDraft,
    family_members: [income("FATHER", "NONE", "0.00"), income("MOTHER", "NOT_SPECIFIED", null), income("SPOUSE", "REPORTED", "98000")],
  };
  assert.deepEqual(getInventoryDraftIssues(draft), []);
  const normalized = normalizeInventoryPayload(draft).family_members;
  assert.deepEqual(normalized.map((member) => [member.kind, member.annual_income_status, member.annual_income_previous_year]), [
    ["FATHER", "NONE", null],
    ["MOTHER", "NOT_SPECIFIED", null],
    ["SPOUSE", "REPORTED", "98000"],
  ]);
  const missing = getInventorySubmissionIssues({ ...baseDraft, family_members: [{ kind: "FATHER", occupation_category: "FARMER" }] }, undefined);
  assert.ok(missing.some((issue) => issue.targetId === "inventory-family-father-income-status"));
});

test("the income amount shows the annual-period guidance, a centavo step, and its issue", () => {
  const html = section(FamilySection, { family_members: [income("FATHER", "REPORTED", "0")] }, [
    { section: "family", targetId: "inventory-family-father-income-amount", message: "Enter an amount greater than ₱0 for father's income." },
  ]);
  const amount = tag(html, "inventory-family-father-income-amount");
  assert.match(amount, /step="0.01"/);
  assert.match(amount, /aria-required="true"/);
  assert.match(amount, /aria-describedby="inventory-family-father-income-amount-hint inventory-family-father-income-amount-error"/);
  assert.match(html, /Total for the whole previous year, in pesos \(₱\)\./);
  assert.match(html, /id="inventory-family-father-income-amount-error"[^>]*>Enter an amount greater than ₱0 for father&#x27;s income\./);
});

// --- Numeric controls -----------------------------------------------------------------------

test("exact peso amounts keep two decimal places and are never rewritten", () => {
  const fare = (value) => ({ ...baseDraft, transportation_entries: [{ mode: "TRICYCLE", frequency_category: "DAILY", fare: value }] });
  assert.deepEqual(getInventoryDraftIssues(fare("0")), []);
  assert.deepEqual(getInventoryDraftIssues(fare("37.50")), []);
  assert.deepEqual(issueTargets(getInventoryDraftIssues(fare("12.345"))), [
    ["organizations", "inventory-transport-tricycle-fare", "Use up to two decimal places for the tricycle fare."],
  ]);
  assert.deepEqual(issueTargets(getInventoryDraftIssues(fare("-1"))), [
    ["organizations", "inventory-transport-tricycle-fare", "Enter the tricycle fare as ₱0 or more."],
  ]);
  assert.deepEqual(issueTargets(getInventoryDraftIssues(fare("123456789"))), [
    ["organizations", "inventory-transport-tricycle-fare", "Enter a smaller tricycle fare."],
  ]);
  assert.equal(normalizeInventoryPayload(fare("37.50")).transportation_entries[0].fare, "37.50");
  assert.deepEqual(
    issueTargets(getInventoryDraftIssues({ ...baseDraft, family_members: [income("FATHER", "REPORTED", "1000.001")] })),
    [["family", "inventory-family-father-income-amount", "Use up to two decimal places for father's income."]],
  );

  const html = section(OrganizationsSection, fare("20.00"));
  const input = tag(html, "inventory-transport-tricycle-fare");
  assert.match(input, /step="0.01"/);
  assert.match(input, /value="20.00"/);
  assert.match(html, /In pesos \(₱\)\./);
  assert.doesNotMatch(html, /one-way|round trip|per ride/i);
});

test("daily hours accept two decimals from 0 to 24", () => {
  const hours = (daily_hours_class) => ({ ...baseDraft, daily_hours_class });
  for (const ok of ["0", "7.25", "7.3", "24", 4, "4.00", null, ""]) assert.deepEqual(getInventoryDraftIssues(hours(ok)), [], String(ok));
  assert.deepEqual(issueTargets(getInventoryDraftIssues(hours("7.255"))), [
    ["interests", "inventory-daily-hours-class", "Use up to two decimal places for class hours."],
  ]);
  for (const bad of ["24.5", "-1", "100"]) {
    assert.deepEqual(issueTargets(getInventoryDraftIssues(hours(bad))), [
      ["interests", "inventory-daily-hours-class", "Enter class hours from 0 to 24."],
    ], bad);
  }
  const html = section(InterestsSection, hours("7.25"));
  assert.match(tag(html, "inventory-daily-hours-class"), /step="0.01"/);
  assert.match(html, /0 to 24 hours, up to two decimal places\./);
});

test("counts and ages are whole numbers of zero or more", () => {
  assert.deepEqual(getInventoryDraftIssues({ ...baseDraft, siblings: [{ sort_order: 0, age: 12 }, { sort_order: 1, age: null }] }), []);
  assert.deepEqual(issueTargets(getInventoryDraftIssues({ ...baseDraft, siblings: [{ sort_order: 0, age: 9 }, { sort_order: 1, age: 2.5 }] })), [
    ["background", "inventory-sibling-1-age", "Enter sibling 2's age as a whole number."],
  ]);
  assert.deepEqual(issueTargets(getInventoryDraftIssues({ ...baseDraft, present_place_people_count: -1, room_sharing_people_count: 1.5 })), [
    ["health", "inventory-present-place-people", "Enter a whole number for the people in your present living place."],
    ["health", "inventory-room-sharing-people", "Enter a whole number for the people sharing your room."],
  ]);
  assert.deepEqual(getInventoryDraftIssues({ ...baseDraft, present_place_people_count: 0, room_sharing_people_count: 3 }), []);

  const background = section(BackgroundSection, { siblings: [{ sort_order: 0, age: 2.5 }] }, [
    { section: "background", targetId: "inventory-sibling-0-age", message: "Enter sibling 1's age as a whole number." },
  ]);
  const age = tag(background, "inventory-sibling-0-age");
  assert.match(age, /min="0"/);
  assert.match(age, /step="1"/);
  assert.match(background, /id="inventory-sibling-0-age-error"[^>]*>Enter sibling 1&#x27;s age as a whole number\./);
  const health = section(HealthSection, {});
  assert.match(tag(health, "inventory-present-place-people"), /step="1"/);
  assert.match(tag(health, "inventory-room-sharing-people"), /step="1"/);
});

test("submission lists save-time and submit-time issues in section order", () => {
  const issues = getInventorySubmissionIssues({
    ...baseDraft,
    transportation_entries: [{ mode: "BOAT", fare: "1.234" }],
    family_members: [income("FATHER", "REPORTED", "0")],
  }, undefined);
  const sections = issues.map((issue) => issue.section);
  const order = ["personal", "family", "background", "health", "education", "interests", "organizations", "plans", "review"];
  assert.deepEqual(sections, [...sections].sort((a, b) => order.indexOf(a) - order.indexOf(b)));
  assert.deepEqual(issueTargets(issues.filter((issue) => issue.section === "organizations")), [
    ["organizations", "inventory-transport-boat-frequency-category", "Choose how often you use the boat."],
    ["organizations", "inventory-transport-boat-fare", "Use up to two decimal places for the boat fare."],
  ]);
});

// --- Field guidance -------------------------------------------------------------------------

test("contact, height, weight, and attendance years show examples without new rules", () => {
  const personal = section(PersonalSection, personalDraft);
  assert.match(tag(personal, "inventory-contact-number"), /aria-describedby="inventory-contact-number-hint"/);
  assert.match(personal, /id="inventory-contact-number-hint"[^>]*>For example, 0917 123 4567\./);
  assert.doesNotMatch(tag(personal, "inventory-contact-number"), /pattern=/);

  const family = section(FamilySection, { family_members: [{ kind: "MOTHER" }] });
  for (const id of ["inventory-guardian-contact", "inventory-emergency-number", "inventory-family-mother-contact"]) {
    assert.match(family, new RegExp(`id="${id}-hint"[^>]*>For example, 0917 123 4567\\.`), id);
  }
  assert.match(family, /id="inventory-family-mother-business-telephone-hint"[^>]*>Include the area code for a landline\./);

  const health = section(HealthSection, { height: "5 ft 2 in", weight: "" });
  assert.match(health, /id="inventory-height-hint"[^>]*>For example, 160 cm\./);
  assert.match(health, /id="inventory-weight-hint"[^>]*>For example, 52 kg\./);
  assert.match(tag(health, "inventory-height"), /type="text"[^>]*value="5 ft 2 in"|value="5 ft 2 in"[^>]*type="text"/);

  assert.match(section(EducationSection, { education_entries: [] }), /years attended for each level, such as 2016–2022\./);
});

const exitRecord = {
  id: "interview", student: { id: "student", display_name: "Student Example", institutional_id: "2026-1" }, student_name: "Student Example",
  academic_year: { id: "year", label: "2026-2027" }, status: "DRAFT", first_submitted_at: null, last_submitted_at: null,
  created_at: "2026-10-05T00:00:00Z", updated_at: "2026-10-05T00:00:00Z", contact_number: "0917 123 4567; (054) 440 1234",
  college_feedback_item_codes: [], self_assessment_ratings: [], college_feedback_ratings: [], delay_reasons: [],
  significant_learning_experiences: [], career_modes: [], work_choices: [], study_choices: [],
};

test("Exit Interview contact number shows the same example and keeps multiple numbers", () => {
  const form = exitInterviewFormFromDetail(exitRecord);
  const props = { disabled: false, onTextChange() {}, onProgramCompletionChange() {}, onToggleDelayReason() {},
    onToggleLearning() {}, onToggleCareerMode() {}, onToggleWorkChoice() {}, onToggleStudyChoice() {}, onRatingChange() {} };
  const html = renderToStaticMarkup(h(ExitInterviewFormSections, { ...props, form }));
  const input = tag(html, "exit-contact-number");
  assert.match(input, /aria-describedby="exit-contact-number-hint"/);
  assert.match(input, /value="0917 123 4567; \(054\) 440 1234"/);
  assert.doesNotMatch(input, /pattern=/i);
  assert.match(input, /maxLength="64"/i);
  assert.match(html, /id="exit-contact-number-hint"[^>]*>For example, 0917 123 4567\./);
});

test("Date referred offers dates up to the institutional today", () => {
  const counselor = { id: "counselor", role: "COUNSELOR", designations: [], first_name: "Ana", last_name: "Cruz", email: "ana@example.test", capabilities: ["referrals.view", "referrals.manage"] };
  const html = render(h(ReferralCreatePage), counselor);
  assert.match(tag(html, "referral-referred-on"), new RegExp(`max="${institutionalDateInputValue()}"`));
});

// --- Year Level labels ----------------------------------------------------------------------

test("Year Level labels are display text for the stored numbers 1 through 10", () => {
  assert.deepEqual(YEAR_LEVELS, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  assert.deepEqual(YEAR_LEVELS.map(yearLevelLabel), [
    "1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "6th Year", "7th Year", "8th Year", "9th Year", "10th Year",
  ]);
  assert.equal(yearLevelLabel(11), "11th Year");
  assert.equal(yearLevelLabel(22), "22nd Year");

  const education = section(EducationSection, { education_entries: [], year_level: 3 });
  const options = [...education.matchAll(/<option value="(\d+)"[^>]*>([^<]+)<\/option>/g)].map(([, value, label]) => [value, label]);
  assert.deepEqual(options, YEAR_LEVELS.map((level) => [String(level), yearLevelLabel(level)]));
  assert.match(education, /<option value="3" selected="">3rd Year<\/option>/);

  const review = render(h(ReviewSection, {
    draft: { year_level: 4, geographic_locations: [] }, academicYear: "2026-2027", formRevision: "UCN-OP-GCO-01F5 · Revision 1",
    issues: [], programLookupReady: true, onSelectIssue() {},
  }));
  assert.match(review, />4th Year</);
});

test("frontend CI runs the Inventory input checks in both engines on a compiled route", () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.match(pkg.scripts["test:ui:forms"], /node tests\/form-input-standardization\.browser\.mjs/);
  assert.match(pkg.scripts["test:ui:forms"], /COMPASS_UI_BROWSER=webkit node tests\/form-input-standardization\.browser\.mjs/);
  assert.match(pkg.scripts["test:ui:regressions"], /pnpm test:ui:forms/);
  const workflow = readFileSync(new URL("../../.github/workflows/frontend-targeted.yml", import.meta.url), "utf8");
  assert.match(workflow, /\/portal\/inventory\/current/);
  assert.match(workflow, /pnpm test:ui:regressions/);
});
