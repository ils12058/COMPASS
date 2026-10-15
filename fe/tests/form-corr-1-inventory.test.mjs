// FORM-CORR-1 PR 2: Individual Inventory correction targets in the frontend. The backend owns the
// catalog and validates every request; these checks keep the frontend map exhaustive, prove each
// code leads to a rendered control, and keep targets advisory. Every record here is synthetic.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { InventoryCorrectionTargetChooser } from "../src/features/inventory/counselor/inventory-correction-target-chooser.tsx";
import { BackgroundSection } from "../src/features/inventory/editor/background-section.tsx";
import { EducationSection } from "../src/features/inventory/editor/education-section.tsx";
import { FamilySection } from "../src/features/inventory/editor/family-section.tsx";
import { HealthSection } from "../src/features/inventory/editor/health-section.tsx";
import { InterestsSection } from "../src/features/inventory/editor/interests-section.tsx";
import { InventoryEditor } from "../src/features/inventory/editor/inventory-editor.tsx";
import { InventoryReviewProvider } from "../src/features/inventory/editor/inventory-review-context.tsx";
import { OrganizationsSection } from "../src/features/inventory/editor/organizations-section.tsx";
import { PersonalSection } from "../src/features/inventory/editor/personal-section.tsx";
import { PlansSection } from "../src/features/inventory/editor/plans-section.tsx";
import { InventoryCorrectionNotice } from "../src/features/inventory/inventory-correction-notice.tsx";
import {
  emptyInventoryReviewHints,
  INVENTORY_SECTION_REVIEW_ID,
  INVENTORY_SECTION_START_ID,
  inventoryCorrectionFocusOrder,
  inventoryCorrectionTargetLabel,
  inventoryCorrectionTargetOrder,
  inventoryCorrectionTargets,
  inventoryReviewHintId,
  inventoryReviewHints,
  MAX_INVENTORY_CORRECTION_TARGETS,
  readInventoryCorrectionTargets,
  sortInventoryCorrectionTargets,
} from "../src/features/inventory/inventory-correction-targets.ts";
import { getInventoryDraftIssues, getInventorySubmissionIssues, normalizeInventoryPayload, toInventoryPayload } from "../src/features/inventory/inventory-payload.ts";
import { inventorySections } from "../src/features/inventory/inventory-presentation.ts";

function render(element, user = { capabilities: [] }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element))),
  ));
  client.clear();
  return html;
}

const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function openingTag(html, id) {
  return html.match(new RegExp(`<[a-z]+[^>]*\\sid="${escape(id)}"[^>]*>`))?.[0];
}
function describedBy(tag) {
  return (tag?.match(/aria-describedby="([^"]*)"/)?.[1] ?? "").split(" ").filter(Boolean);
}
function ids(html) {
  return [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
}

const codes = Object.keys(inventoryCorrectionTargets);
const editorSections = inventorySections.filter((section) => section.id !== "review").map((section) => section.id);
const sectionComponents = {
  personal: PersonalSection,
  family: FamilySection,
  background: BackgroundSection,
  health: HealthSection,
  education: EducationSection,
  interests: InterestsSection,
  organizations: OrganizationsSection,
  plans: PlansSection,
};

// Every conditional answer rendered.
const fullDraft = {
  living_arrangement: "BOARDING_HOUSE",
  family_members: [{ kind: "FATHER" }, { kind: "MOTHER" }, { kind: "SPOUSE" }],
  geographic_locations: [{ kind: "CURRENT", not_specified: true }, { kind: "PERMANENT", not_specified: true }],
  siblings: [{ sort_order: 0, name: "Synthetic Sibling" }],
  organization_memberships: [
    { scope: "INSIDE_SCHOOL", sort_order: 0, organization_name: "Synthetic Club" },
    { scope: "OUTSIDE_SCHOOL", sort_order: 0, organization_name: "Synthetic League" },
  ],
  transportation_entries: ["TRICYCLE", "BUS", "JEEPNEY", "VAN", "BOAT"].map((mode) => ({ mode })),
};
// Every conditional answer hidden.
const emptyDraft = { living_arrangement: "OWN_HOUSE", family_members: [], geographic_locations: [], siblings: [], organization_memberships: [], transportation_entries: [] };

function renderSection(section, draft, targets) {
  return render(h(InventoryReviewProvider, { value: inventoryReviewHints(targets, draft) }, h(sectionComponents[section], { draft, onChange() {} })));
}

// --- Catalog parity with the backend ------------------------------------------------------------

function backendCatalog() {
  const source = readFileSync(new URL("../../be/compass/inventory/correction_targets.py", import.meta.url), "utf8");
  const body = source.slice(source.indexOf("class InventoryCorrectionTarget(StrEnum):"), source.indexOf("_T = InventoryCorrectionTarget"));
  return [...body.matchAll(/^\s+[A-Z0-9_]+ = "([^"]+)"$/gm)].map((match) => match[1]);
}

test("the frontend map names exactly the backend catalog, in catalog order, keyed by enum value", () => {
  const backend = backendCatalog();
  assert.equal(backend.length, 148);
  assert.deepEqual([...codes].sort(), [...backend].sort(), "Every backend code has a frontend definition and nothing else does");
  assert.deepEqual([...inventoryCorrectionTargetOrder], backend, "Catalog order follows the backend enum");
  assert.ok(codes.every((code) => code.includes(".")), "Keys are the dotted enum values, not the generated object keys");
  const limit = readFileSync(new URL("../../be/compass/inventory/correction_targets.py", import.meta.url), "utf8").match(/MAX_CORRECTION_TARGETS = (\d+)/)?.[1];
  assert.equal(MAX_INVENTORY_CORRECTION_TARGETS, Number(limit));
});

test("every code has a plain label and a real editor section, and never a stored row position", () => {
  const labels = new Set();
  for (const code of codes) {
    const definition = inventoryCorrectionTargets[code];
    assert.ok(editorSections.includes(definition.section), `${code} belongs to an editor section`);
    assert.ok(definition.label.trim(), `${code} has a label`);
    assert.doesNotMatch(definition.label, /[._]/, `${code} label reads as words, not a code`);
    const full = inventoryCorrectionTargetLabel(code);
    assert.ok(!labels.has(full), `${code} label is unique`);
    labels.add(full);
    if (definition.scope === "list") {
      assert.ok(definition.condition?.fallback.endsWith("-add"), `${code} falls back to the list's Add button when it has no rows`);
      assert.ok(!definition.condition.hint, `${code} keeps its list-level hint instead of a fallback hint`);
    }
  }
  // Sections are whole-section targets only; siblings and organizations are lists, never rows.
  assert.equal(codes.filter((code) => inventoryCorrectionTargets[code].scope === "section").length, 8);
  assert.deepEqual(
    codes.filter((code) => inventoryCorrectionTargets[code].scope === "list"),
    ["background.siblings", "organizations.inside_school", "organizations.outside_school"],
  );
  assert.equal(inventoryCorrectionTargetLabel("personal.contact_number"), "Contact number — Personal & contact");
  assert.equal(inventoryCorrectionTargetLabel("family.father.occupation"), "Father's occupation — Family & student support");
  assert.equal(inventoryCorrectionTargetLabel("section.education"), "Whole section — Educational background");
});

// --- Every anchor, fallback and hint is a rendered control ----------------------------------------

test("every answer target's anchor is rendered, described by its hint, and never marked invalid", () => {
  for (const section of editorSections) {
    const targets = codes.filter((code) => inventoryCorrectionTargets[code].section === section && inventoryCorrectionTargets[code].scope !== "section");
    const html = renderSection(section, fullDraft, targets);
    assert.doesNotMatch(html, /aria-invalid/, `${section}: review targets never mark answers invalid`);
    for (const code of targets) {
      const definition = inventoryCorrectionTargets[code];
      const anchor = openingTag(html, definition.anchor);
      assert.ok(anchor, `${code}: anchor #${definition.anchor} is rendered`);
      const hintId = inventoryReviewHintId(definition.hintHost ?? definition.anchor);
      assert.ok(openingTag(html, hintId), `${code}: hint #${hintId} is rendered`);
      assert.ok(describedBy(anchor).includes(hintId), `${code}: #${definition.anchor} is described by its hint`);
    }
    for (const hint of html.matchAll(/<p id="[^"]+-review"[^>]*>([^<]*)<\/p>/g)) {
      assert.doesNotMatch(hint[0], /text-danger|role="alert"/, "A review hint is never styled or announced as an error");
      assert.doesNotMatch(hint[1], /incorrect|invalid|wrong|error/i);
    }
  }
});

test("hidden conditional answers lead to a rendered parent control with an explanation", () => {
  for (const section of editorSections) {
    const conditional = codes.filter((code) => inventoryCorrectionTargets[code].section === section && inventoryCorrectionTargets[code].condition);
    if (!conditional.length) continue;
    const html = renderSection(section, emptyDraft, conditional);
    for (const code of conditional) {
      const { anchor, condition, hintHost } = inventoryCorrectionTargets[code];
      assert.equal(openingTag(html, anchor), undefined, `${code}: #${anchor} is hidden in the empty draft`);
      const fallback = openingTag(html, condition.fallback);
      assert.ok(fallback, `${code}: fallback #${condition.fallback} is rendered`);
      const hintId = inventoryReviewHintId(condition.hint ? condition.fallback : hintHost);
      assert.ok(describedBy(fallback).includes(hintId), `${code}: the fallback is described by #${hintId}`);
      assert.ok(openingTag(html, hintId), `${code}: #${hintId} is rendered`);
      assert.deepEqual(inventoryCorrectionFocusOrder(code, emptyDraft), [condition.fallback, INVENTORY_SECTION_START_ID]);
    }
  }
});

test("the nine previously missing controls have unique ids, and ids stay unique in every section", () => {
  const added = {
    "inventory-parent-statuses": "family",
    "inventory-boarding-exclusive": "health",
    "inventory-immunizations": "health",
    "inventory-schedule-satisfied": "education",
    "inventory-course-first-choice": "interests",
    "inventory-course-choice-reasons": "interests",
    "inventory-interests": "interests",
    "inventory-transport-modes": "organizations",
    "inventory-prior-counseling": "plans",
  };
  for (const [id, section] of Object.entries(added)) {
    const tag = openingTag(render(h(sectionComponents[section], { draft: fullDraft, onChange() {} })), id);
    assert.ok(tag, `#${id} is rendered`);
    assert.match(tag, /^<(fieldset|div)/, `#${id} identifies the whole group of choices`);
  }
  for (const section of editorSections) {
    for (const draft of [fullDraft, emptyDraft]) {
      const all = codes.filter((code) => inventoryCorrectionTargets[code].section === section);
      const rendered = ids(renderSection(section, draft, all));
      assert.deepEqual(rendered.filter((id, index) => rendered.indexOf(id) !== index), [], `${section}: ids are unique`);
    }
  }
  // Radio groups keep one name per question now that they have ids.
  const plans = render(h(PlansSection, { draft: {}, onChange() {} }));
  assert.equal([...plans.matchAll(/name="inventory-prior-counseling"/g)].length, 3);
});

// --- Hints ----------------------------------------------------------------------------------------

test("a correction without targets marks nothing", () => {
  assert.equal(inventoryReviewHints([], fullDraft), emptyInventoryReviewHints);
  const html = render(h(FamilySection, { draft: fullDraft, onChange() {} }));
  assert.doesNotMatch(html, /-review"/);
  assert.doesNotMatch(html, /<details[^>]*open/);
});

test("family details open only for the member whose details were named", () => {
  const hints = inventoryReviewHints(["family.father.email_address", "family.mother.name"], fullDraft);
  assert.deepEqual([...hints.openDetails], ["inventory-family-father-details"]);
  // A Spouse detail hidden until Spouse details are added opens nothing yet.
  assert.deepEqual([...inventoryReviewHints(["family.spouse.email_address"], emptyDraft).openDetails], []);
  // The details open on the client (see form-corr-1-inventory.browser.mjs); each one is addressable.
  const html = renderSection("family", fullDraft, ["family.father.email_address"]);
  for (const member of ["father", "mother", "spouse"]) assert.ok(openingTag(html, `inventory-family-${member}-details`));
});

test("conditional hints combine at a shared parent and clear when the answer reappears", () => {
  const targets = ["health.living_arrangement", "health.boarding_landlord_name", "health.boarding_address"];
  const hidden = inventoryReviewHints(targets, emptyDraft);
  assert.equal(
    hidden.hints.get("inventory-living-arrangement"),
    "You were asked to review this answer. You were asked to review boarding-house details. They appear when you choose Boarding house.",
  );
  assert.equal(hidden.describedBy.get("inventory-living-arrangement"), "inventory-living-arrangement-review");
  assert.equal(hidden.hints.get("inventory-boarding-landlord"), undefined);

  const shown = inventoryReviewHints(targets, fullDraft);
  assert.equal(shown.hints.get("inventory-living-arrangement"), "You were asked to review this answer.");
  assert.equal(shown.hints.get("inventory-boarding-landlord"), "You were asked to review this answer.");
  assert.equal(shown.describedBy.get("inventory-boarding-address"), "inventory-boarding-address-review");
});

test("lists are reviewed as a whole, whichever row exists", () => {
  const withRows = inventoryReviewHints(["background.siblings", "organizations.inside_school"], fullDraft);
  assert.equal(withRows.hints.get("inventory-siblings"), "You were asked to review this list.");
  assert.equal(withRows.describedBy.get("inventory-sibling-0-name"), "inventory-siblings-review");
  assert.equal(withRows.describedBy.get("inventory-membership-inside_school-0-organization"), "inventory-membership-inside_school-review");
  // No second row or index is ever named.
  assert.ok(![...withRows.describedBy.keys()].some((id) => /-[1-9]\d*-/.test(id)));

  const empty = inventoryReviewHints(["background.siblings"], emptyDraft);
  assert.equal(empty.describedBy.get("inventory-sibling-add"), "inventory-siblings-review");
  assert.deepEqual(inventoryCorrectionFocusOrder("background.siblings", fullDraft), ["inventory-sibling-0-name", "inventory-sibling-add", INVENTORY_SECTION_START_ID]);
});

test("whole-section targets lead to the section note, and the editor shows it only in that section", () => {
  assert.deepEqual(inventoryCorrectionFocusOrder("section.health", fullDraft), [INVENTORY_SECTION_REVIEW_ID, INVENTORY_SECTION_START_ID]);
  assert.deepEqual([...inventoryReviewHints(["section.health", "section.plans"], fullDraft).sections], ["health", "plans"]);
  assert.deepEqual(inventoryCorrectionFocusOrder("personal.sex", fullDraft), ["inventory-sex", INVENTORY_SECTION_START_ID]);
});

// --- Reading targets ------------------------------------------------------------------------------

test("received targets are named in catalog order; unknown codes are counted, never shown", () => {
  assert.deepEqual(readInventoryCorrectionTargets(undefined), { targets: [], unknown: 0 });
  assert.deepEqual(
    readInventoryCorrectionTargets(["plans.current_fears", "personal.sex", "personal.sex", "personal.future_code"]),
    { targets: ["personal.sex", "plans.current_fears"], unknown: 1 },
  );
  assert.deepEqual(sortInventoryCorrectionTargets(["section.plans", "family.guardian_name", "section.personal"]), ["section.personal", "family.guardian_name", "section.plans"]);
});

const requestedAt = "2026-10-16T01:00:00Z";

test("a legacy reason-only correction looks exactly as before", () => {
  const html = render(h(InventoryCorrectionNotice, { correction: { message: "Update your contact details.", requested_at: requestedAt, targets: [] }, onSelectTarget() {} }));
  assert.match(html, /Correction requested/);
  assert.match(html, /Update your contact details\./);
  assert.match(html, /Requested /);
  assert.doesNotMatch(html, /Answers to review|<button/);
  // A response from before the field existed.
  const older = render(h(InventoryCorrectionNotice, { correction: { message: "Synthetic.", requested_at: requestedAt } }));
  assert.doesNotMatch(older, /Answers to review/);
});

test("Students see plain labels: actionable in the editor, plain text everywhere else", () => {
  const correction = {
    message: "Please check these answers.",
    requested_at: requestedAt,
    targets: ["personal.contact_number", "family.father.occupation", "education.history.senior_high", "section.plans", "personal.not_released"],
  };
  const plain = render(h(InventoryCorrectionNotice, { correction }));
  for (const label of ["Contact number — Personal &amp; contact", "Father&#x27;s occupation — Family &amp; student support", "Educational history: Senior high — Educational background", "Whole section — Plans &amp; counseling context"]) {
    assert.ok(plain.includes(label), `shows ${label}`);
  }
  assert.match(plain, /Answers to review/);
  assert.match(plain, /1 more part of the form/);
  assert.doesNotMatch(plain, /<button/, "A record that cannot be edited never offers navigation");
  for (const code of correction.targets) assert.ok(!plain.includes(code), `never shows ${code}`);
  assert.ok(plain.indexOf("Please check these answers.") < plain.indexOf("Answers to review"), "The list follows the instructions");

  const editable = render(h(InventoryCorrectionNotice, { correction, onSelectTarget() {} }));
  assert.equal([...editable.matchAll(/<button type="button"/g)].length, 4);
  assert.match(editable, /Select an answer to go to it in the form\./);
  for (const code of correction.targets) assert.ok(!editable.includes(code), `never shows ${code}`);
});

// --- Editor ---------------------------------------------------------------------------------------

const student = { role: "STUDENT", capabilities: ["inventory.view_self", "inventory.manage_self"], student_lifecycle_status: "CURRENT" };
const revision = { id: "f5", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" };
function inventory(overrides = {}) {
  return {
    id: "inventory-corr", academic_year: { id: "year", label: "2026-2027" }, status: "DRAFT", program: null, form_revision: revision,
    submitted_at: null, first_submitted_at: "2026-10-01T00:00:00Z", last_submitted_at: "2026-10-01T00:00:00Z",
    correction_pending: true,
    latest_correction: { message: "Synthetic instructions.", requested_at: requestedAt, targets: ["section.personal", "personal.sex"] },
    ...overrides,
  };
}

test("the editor lists targets as buttons and marks the targeted section and answer", () => {
  const html = render(h(InventoryEditor, { inventory: inventory() }), student);
  assert.match(html, /Answers to review/);
  assert.ok(html.includes(">Whole section — Personal &amp; contact</button>"));
  assert.ok(html.includes(">Sex — Personal &amp; contact</button>"));
  assert.match(openingTag(html, INVENTORY_SECTION_REVIEW_ID), /tabindex="-1"/);
  assert.match(html, /You were asked to review this section\./);
  assert.ok(describedBy(openingTag(html, "inventory-sex")).includes("inventory-sex-review"));
  assert.match(openingTag(html, INVENTORY_SECTION_START_ID), /tabindex="-1"/);
});

test("a correction that is no longer pending shows no targets", () => {
  const html = render(h(InventoryEditor, { inventory: inventory({ correction_pending: false }) }), student);
  assert.doesNotMatch(html, /Correction requested|Answers to review|-review"/);
  assert.equal(openingTag(html, INVENTORY_SECTION_REVIEW_ID), undefined);
});

// --- Payload and lifecycle ------------------------------------------------------------------------

test("toInventoryPayload drops the nested correction, so saving never sends targets", () => {
  const response = {
    ...inventory(),
    full_name: "Synthetic Student",
    sex: "FEMALE",
    family_members: [{ kind: "FATHER", occupation_category: "FARMER", annual_income_status: "NONE" }],
  };
  const payload = toInventoryPayload(response);
  for (const key of ["latest_correction", "correction_pending", "id", "status", "form_revision", "academic_year"]) {
    assert.ok(!(key in payload), `${key} stays out of the update payload`);
  }
  const body = JSON.stringify(normalizeInventoryPayload(payload));
  assert.doesNotMatch(body, /targets|section\.personal|personal\.sex|Synthetic instructions/);
  assert.equal(payload.full_name, "Synthetic Student");
  // A round trip of the saved answers is stable.
  assert.deepEqual(toInventoryPayload({ ...response, ...payload }), payload);
});

test("targets never add a save or submission issue", () => {
  const draft = toInventoryPayload(inventory({ latest_correction: { message: "x", requested_at: requestedAt, targets: [...inventoryCorrectionTargetOrder] } }));
  const withoutTargets = toInventoryPayload(inventory({ latest_correction: null, correction_pending: false }));
  assert.deepEqual(getInventoryDraftIssues(draft), getInventoryDraftIssues(withoutTargets));
  assert.deepEqual(getInventorySubmissionIssues(draft, undefined), getInventorySubmissionIssues(withoutTargets, undefined));
});

// --- Reviewer chooser -----------------------------------------------------------------------------

test("the chooser offers every catalog code, grouped by section, with nothing selected or open", () => {
  const html = render(h(InventoryCorrectionTargetChooser, { value: [], onChange() {} }));
  assert.match(html, /<legend[^>]*>Answers to review \(optional\)<\/legend>/);
  assert.match(html, /Choose the parts of the form the Student should look at again\. They will see these with your instructions\./);
  assert.equal([...html.matchAll(/type="checkbox"/g)].length, 148);
  assert.doesNotMatch(html, /checked=""/, "No target is selected by default");
  assert.doesNotMatch(html, /<details[^>]*open/, "Sections start collapsed");
  assert.equal([...html.matchAll(/<details/g)].length, 8);
  assert.match(html, /None\. The Student will see only your instructions\./);
  assert.match(html, /0 of 30 selected/);
});

test("the chooser lists the selection with Remove buttons and stops at 30", () => {
  const some = render(h(InventoryCorrectionTargetChooser, { value: ["section.family", "personal.contact_number"], onChange() {} }));
  assert.match(some, /aria-label="Remove Contact number — Personal &amp; contact"/);
  assert.match(some, /aria-label="Remove Whole section — Family &amp; student support"/);
  assert.match(some, /Clear selection/);
  assert.match(some, /Family &amp; student support<span[^>]*>1 selected<\/span>/);
  assert.equal([...some.matchAll(/checked=""/g)].length, 2);

  const thirty = inventoryCorrectionTargetOrder.slice(0, 30);
  const full = render(h(InventoryCorrectionTargetChooser, { value: thirty, onChange() {} }));
  assert.match(full, /30 of 30 selected\. Remove one to choose another\./);
  assert.equal([...full.matchAll(/<input type="checkbox"[^>]*checked=""[^>]*>/g)].length, 30);
  const unchecked = [...full.matchAll(/<input type="checkbox"[^>]*>/g)].map((match) => match[0]).filter((tag) => !tag.includes('checked=""'));
  assert.equal(unchecked.length, 118);
  assert.ok(unchecked.every((tag) => tag.includes('disabled=""')), "Nothing more can be chosen at the limit");
  assert.ok(MAX_INVENTORY_CORRECTION_TARGETS === 30);
});

test("a pending reopen disables the whole chooser", () => {
  const html = render(h(InventoryCorrectionTargetChooser, { value: ["personal.sex"], onChange() {}, disabled: true }));
  assert.match(html, /^<fieldset disabled=""/);
});
