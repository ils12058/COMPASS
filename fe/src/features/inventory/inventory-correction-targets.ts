import {
  FamilyMemberKindValue,
  GeographicLocationKindValue,
  InventoryCorrectionTarget,
  LivingArrangementValue,
  OrganizationScopeValue,
  TransportationModeValue,
  type InventoryPayload,
} from "@/lib/api/generated/model";
import { inventorySections, transportationModes, type InventorySectionId } from "@/features/inventory/inventory-presentation";

// FORM-CORR-1: what each backend Individual Inventory correction-target code means in the editor.
// The backend owns the codes (be/compass/inventory/correction_targets.py), validates every request
// and returns them in catalog order. This map only names a code for people and says where the
// Student finds it. It is keyed by the enum *values*: the generated object keys drop the dots.
//
// A target asks the Student to look at an answer again. It is not a validation error: it never marks
// a control invalid, blocks saving or resubmission, or requires the answer to change.
//
// Anchors are DOM ids of rendered editor controls. They never become stored codes, and they never
// name a sibling or organization row by position: those rows are recreated on every save and
// renumbered by the editor, so they are targeted only as whole lists.

export type InventoryEditorSectionId = Exclude<InventorySectionId, "review">;

// section: every answer in an editor section. answer: one question, with any detail it reveals.
// answers: a keyed row or block of related inputs. list: a repeating list as a whole.
export type InventoryCorrectionScope = "section" | "answer" | "answers" | "list";

export type InventoryCorrectionCondition = {
  // Whether the anchor is rendered for this draft.
  visible: (draft: InventoryPayload) => boolean;
  // The control the Student is taken to while the anchor is not rendered.
  fallback: string;
  // Shown at the fallback while the anchor is hidden. Omitted when the target's own hint stays
  // rendered either way, as for a list without rows.
  hint?: string;
};

export type InventoryCorrectionTargetDefinition = {
  section: InventoryEditorSectionId;
  // The editor field group the answer sits in; it organizes the reviewer's choices.
  group: string;
  label: string;
  scope: InventoryCorrectionScope;
  // The control that receives focus while it is rendered.
  anchor: string;
  // The element that shows the hint (as `${hintHost}-review`), when it is not the anchor itself.
  hintHost?: string;
  condition?: InventoryCorrectionCondition;
  // The collapsed <details> that contains the anchor.
  details?: string;
};

// Focus lands here for a whole-section target, and as the last resort for any target whose
// control cannot take focus (for example while the form is saving).
export const INVENTORY_SECTION_REVIEW_ID = "inventory-section-review";
export const INVENTORY_SECTION_START_ID = "inventory-section-start";

export const inventoryReviewHintText: Record<InventoryCorrectionScope, string> = {
  section: "You were asked to review this section.",
  answer: "You were asked to review this answer.",
  answers: "You were asked to review these answers.",
  list: "You were asked to review this list.",
};

export function inventoryReviewHintId(host: string): string {
  return `${host}-review`;
}

type Definition = InventoryCorrectionTargetDefinition;

const sectionTarget = (section: InventoryEditorSectionId): Definition => ({
  section,
  group: "Whole section",
  label: "Whole section",
  scope: "section",
  anchor: INVENTORY_SECTION_REVIEW_ID,
});

const answer = (
  section: InventoryEditorSectionId,
  group: string,
  label: string,
  anchor: string,
  extra: Partial<Pick<Definition, "condition" | "details" | "hintHost" | "scope">> = {},
): Definition => ({ section, group, label, scope: "answer", anchor, ...extra });

// --- Conditions -------------------------------------------------------------------------------

const boardingHouse: InventoryCorrectionCondition = {
  visible: (draft) => draft.living_arrangement === LivingArrangementValue.BOARDING_HOUSE,
  fallback: "inventory-living-arrangement",
  hint: "You were asked to review boarding-house details. They appear when you choose Boarding house.",
};

const spouseAdded: InventoryCorrectionCondition = {
  visible: (draft) => (draft.family_members ?? []).some((member) => member.kind === FamilyMemberKindValue.SPOUSE),
  fallback: "inventory-spouse-add",
  hint: "You were asked to review Spouse information. It appears after you choose Add optional Spouse details.",
};

const permanentLocationAdded: InventoryCorrectionCondition = {
  visible: (draft) =>
    (draft.geographic_locations ?? []).some((location) => location.kind === GeographicLocationKindValue.PERMANENT),
  fallback: "inventory-permanent-location-add",
};

const siblingsListed: InventoryCorrectionCondition = {
  visible: (draft) => (draft.siblings ?? []).length > 0,
  fallback: "inventory-sibling-add",
};

function membershipsListed(scope: OrganizationScopeValue): InventoryCorrectionCondition {
  return {
    visible: (draft) => (draft.organization_memberships ?? []).some((row) => row.scope === scope),
    fallback: `inventory-membership-${scope.toLowerCase()}-add`,
  };
}

const transportationLabels = new Map<string, string>(transportationModes);

function transportationSelected(mode: TransportationModeValue): InventoryCorrectionCondition {
  const label = transportationLabels.get(mode) ?? mode;
  return {
    visible: (draft) => (draft.transportation_entries ?? []).some((entry) => entry.mode === mode),
    fallback: "inventory-transport-modes",
    hint: `You were asked to review your ${label} details. They appear when you select ${label}.`,
  };
}

// --- Keyed rows ---------------------------------------------------------------------------------

type FamilyKey = "father" | "mother" | "spouse";
type FamilyQuestion =
  | "name"
  | "occupation"
  | "annual_income"
  | "date_of_birth"
  | "place_of_birth"
  | "current_address"
  | "permanent_address"
  | "contact_number"
  | "email_address"
  | "educational_attainment"
  | "business_address"
  | "business_telephone"
  | "languages_spoken"
  | "religion_raised_with"
  | "current_religion";

// [question, label, control id suffix, inside the "Additional … information" details]
const familyQuestions: readonly (readonly [FamilyQuestion, string, string, boolean])[] = [
  ["name", "name", "name", false],
  ["occupation", "occupation", "occupation-category", false],
  ["annual_income", "annual income from previous year", "income-status", false],
  ["date_of_birth", "date of birth", "date-of-birth", true],
  ["place_of_birth", "place of birth", "place-of-birth", true],
  ["current_address", "current address", "current-address", true],
  ["permanent_address", "permanent address", "permanent-address", true],
  ["contact_number", "contact number", "contact", true],
  ["email_address", "email address", "email", true],
  ["educational_attainment", "educational attainment", "education", true],
  ["business_address", "business address", "business-address", true],
  ["business_telephone", "business telephone", "business-telephone", true],
  ["languages_spoken", "languages spoken", "languages", true],
  ["religion_raised_with", "religion raised with", "religion-raised", true],
  ["current_religion", "current religion", "current-religion", true],
];

function familyTargets<K extends FamilyKey>(key: K, person: string): Record<`family.${K}.${FamilyQuestion}`, Definition> {
  const prefix = `inventory-family-${key}`;
  const condition = key === "spouse" ? spouseAdded : undefined;
  return Object.fromEntries(
    familyQuestions.map(([question, label, suffix, inDetails]) => [
      `family.${key}.${question}`,
      answer("family", person, `${person}'s ${label}`, `${prefix}-${suffix}`, {
        ...(condition ? { condition } : {}),
        ...(inDetails ? { details: `${prefix}-details` } : {}),
      }),
    ]),
  ) as Record<`family.${K}.${FamilyQuestion}`, Definition>;
}

type EducationKey = "preparatory" | "elementary" | "junior_high" | "senior_high" | "technical_vocational" | "collegiate";

function educationTarget(level: EducationKey, label: string): Definition {
  return answer("education", "Educational history", `Educational history: ${label}`, `inventory-education-${level}-school`, {
    scope: "answers",
    hintHost: `inventory-education-${level}`,
  });
}

function transportationTarget(mode: TransportationModeValue): Definition {
  const key = mode.toLowerCase();
  const label = transportationLabels.get(mode) ?? mode;
  return answer("organizations", "Transportation", `${label}: frequency and fare`, `inventory-transport-${key}-frequency-category`, {
    scope: "answers",
    hintHost: `inventory-transport-${key}`,
    condition: transportationSelected(mode),
  });
}

function membershipTarget(scope: OrganizationScopeValue, label: string): Definition {
  const key = scope.toLowerCase();
  return answer("organizations", "Membership in organizations", label, `inventory-membership-${key}-0-organization`, {
    scope: "list",
    hintHost: `inventory-membership-${key}`,
    condition: membershipsListed(scope),
  });
}

// --- Catalog ------------------------------------------------------------------------------------

const personal = "personal";
const family = "family";
const background = "background";
const health = "health";
const education = "education";
const interests = "interests";
const organizations = "organizations";
const plans = "plans";

export const inventoryCorrectionTargets = {
  "section.personal": sectionTarget(personal),
  "personal.full_name": answer(personal, "Personal data", "Full name", "inventory-full-name"),
  "personal.nickname": answer(personal, "Personal data", "Nickname", "inventory-nickname"),
  "personal.date_of_birth": answer(personal, "Personal data", "Date of birth", "inventory-date-of-birth"),
  "personal.place_of_birth": answer(personal, "Personal data", "Place of birth", "inventory-place-of-birth"),
  "personal.nationality": answer(personal, "Personal data", "Nationality", "inventory-nationality"),
  "personal.sex": answer(personal, "Personal data", "Sex", "inventory-sex"),
  "personal.birth_order": answer(personal, "Personal data", "Birth order among siblings", "inventory-birth-order"),
  "personal.civil_status": answer(personal, "Personal data", "Civil status", "inventory-civil-status"),
  "personal.current_address": answer(personal, "Contact and addresses", "Current address", "inventory-current-address"),
  "personal.permanent_address": answer(personal, "Contact and addresses", "Permanent address", "inventory-permanent-address"),
  "personal.contact_number": answer(personal, "Contact and addresses", "Contact number", "inventory-contact-number"),
  "personal.email_address": answer(personal, "Contact and addresses", "Email address", "inventory-email"),
  "personal.languages_spoken_at_home": answer(personal, "Contact and addresses", "Languages spoken at home", "inventory-languages-home"),
  "personal.languages_most_fluent": answer(personal, "Contact and addresses", "Languages most fluent in", "inventory-languages-fluent"),
  "personal.religion_from_birth": answer(personal, "Contact and addresses", "Religion from birth", "inventory-religion-birth"),
  "personal.current_religion": answer(personal, "Contact and addresses", "Current religion", "inventory-current-religion-category"),
  "personal.current_location": answer(personal, "Location details", "Current location details", "inventory-current-location-choice", {
    scope: "answers",
    hintHost: "inventory-current-location",
  }),
  "personal.permanent_location": answer(personal, "Location details", "Permanent location details", "inventory-permanent-location-choice", {
    scope: "answers",
    hintHost: "inventory-permanent-location",
    condition: permanentLocationAdded,
  }),

  "section.family": sectionTarget(family),
  ...familyTargets("father", "Father"),
  ...familyTargets("mother", "Mother"),
  ...familyTargets("spouse", "Spouse"),
  "family.parent_status_category": answer(family, "Parent status", "Current parent-status category", "inventory-parent-status-category"),
  "family.parent_statuses": answer(family, "Parent status", "Additional parent circumstances", "inventory-parent-statuses"),
  "family.guardian_name": answer(family, "Guardian and emergency contact", "Guardian name", "inventory-guardian-name"),
  "family.guardian_relationship": answer(family, "Guardian and emergency contact", "Relationship with guardian", "inventory-guardian-relationship"),
  "family.guardian_address": answer(family, "Guardian and emergency contact", "Guardian address", "inventory-guardian-address"),
  "family.guardian_contact_number": answer(family, "Guardian and emergency contact", "Guardian contact number", "inventory-guardian-contact"),
  "family.emergency_contact_name": answer(family, "Guardian and emergency contact", "Emergency contact name", "inventory-emergency-name"),
  "family.emergency_contact_number": answer(family, "Guardian and emergency contact", "Emergency contact number", "inventory-emergency-number"),
  "family.four_ps_status": answer(family, "Student support information", "4Ps status", "inventory-four-ps"),
  "family.indigenous_peoples_status": answer(family, "Student support information", "Indigenous Peoples status", "inventory-indigenous-peoples"),
  "family.mother_life_status": answer(family, "Student support information", "Mother's life status", "inventory-mother-life-status"),
  "family.father_life_status": answer(family, "Student support information", "Father's life status", "inventory-father-life-status"),

  "section.background": sectionTarget(background),
  "background.siblings": answer(background, "Siblings", "Siblings", "inventory-sibling-0-name", {
    scope: "list",
    hintHost: "inventory-siblings",
    condition: siblingsListed,
  }),
  "background.friends_in_school": answer(background, "Personal background and unique features", "Friends in school", "inventory-friends-in-school"),
  "background.friends_outside_school": answer(background, "Personal background and unique features", "Friends outside school", "inventory-friends-outside-school"),
  "background.special_interest": answer(background, "Personal background and unique features", "Special interest", "inventory-special-interest"),
  "background.special_skills_talents": answer(background, "Personal background and unique features", "Special skills and talents", "inventory-special-skills"),
  "background.hobbies_recreation": answer(background, "Personal background and unique features", "Hobbies and recreation activities", "inventory-hobbies"),
  "background.ambition_goal": answer(background, "Personal background and unique features", "Ambition or goal", "inventory-ambition"),
  "background.characteristics": answer(background, "Personal background and unique features", "Characteristics that describe you best", "inventory-characteristics"),

  "section.health": sectionTarget(health),
  "health.living_arrangement": answer(health, "Living conditions", "Where do you live now?", "inventory-living-arrangement"),
  "health.present_place_people_count": answer(health, "Living conditions", "People in your present living place", "inventory-present-place-people"),
  "health.room_sharing_people_count": answer(health, "Living conditions", "People sharing your room", "inventory-room-sharing-people"),
  "health.boarding_exclusive": answer(health, "Living conditions", "Is the boarding house exclusive to one sex?", "inventory-boarding-exclusive", { condition: boardingHouse }),
  "health.boarding_landlord_name": answer(health, "Living conditions", "Landlord or landlady name", "inventory-boarding-landlord", { condition: boardingHouse }),
  "health.boarding_address": answer(health, "Living conditions", "Boarding-house address", "inventory-boarding-address", { condition: boardingHouse }),
  "health.accidents_experienced": answer(health, "Health conditions", "Accidents experienced", "inventory-accidents"),
  "health.accidents_effect": answer(health, "Health conditions", "Effect of accidents", "inventory-accidents-effect"),
  "health.operations_experienced": answer(health, "Health conditions", "Operations experienced", "inventory-operations"),
  "health.operations_effect": answer(health, "Health conditions", "Effect of operations", "inventory-operations-effect"),
  "health.immunizations": answer(health, "Health conditions", "Immunizations you have had", "inventory-immunizations"),
  "health.height": answer(health, "Health conditions", "Height", "inventory-height"),
  "health.weight": answer(health, "Health conditions", "Weight", "inventory-weight"),
  "health.pwd_status": answer(health, "Health conditions", "Disability status", "inventory-pwd-status"),
  "health.illness_this_year": answer(health, "Health conditions", "Illness this year", "inventory-illness-this-year"),
  "health.previous_illness": answer(health, "Health conditions", "Previous illness", "inventory-previous-illness"),

  "section.education": sectionTarget(education),
  "education.history.preparatory": educationTarget("preparatory", "Preparatory"),
  "education.history.elementary": educationTarget("elementary", "Elementary"),
  "education.history.junior_high": educationTarget("junior_high", "Junior high"),
  "education.history.senior_high": educationTarget("senior_high", "Senior high"),
  "education.history.technical_vocational": educationTarget("technical_vocational", "Technical / vocational"),
  "education.history.collegiate": educationTarget("collegiate", "Collegiate"),
  "education.program": answer(education, "Current Program and course choices", "Current Program", "inventory-program"),
  "education.year_level": answer(education, "Current Program and course choices", "Year Level", "inventory-year-level"),
  "education.major": answer(education, "Current Program and course choices", "Major", "inventory-major"),
  "education.schedule_satisfaction": answer(education, "Current Program and course choices", "Satisfaction with your present schedule", "inventory-schedule-satisfied"),

  "section.interests": sectionTarget(interests),
  "interests.course_first_choice": answer(interests, "Course choice and educational perception", "Was your enrolled course your first choice?", "inventory-course-first-choice"),
  "interests.course_choice_reasons": answer(interests, "Course choice and educational perception", "Reasons for your course choice", "inventory-course-choice-reasons"),
  "interests.lowest_subjects_grades": answer(interests, "Course choice and educational perception", "Subjects with lowest grades", "inventory-lowest-subjects"),
  "interests.highest_subjects_grades": answer(interests, "Course choice and educational perception", "Subjects with highest grades", "inventory-highest-subjects"),
  "interests.inclination_performing_arts": answer(interests, "Course choice and educational perception", "Inclinations: performing arts", "inventory-inclination-performing-arts"),
  "interests.inclination_sports": answer(interests, "Course choice and educational perception", "Inclinations: sports", "inventory-inclination-sports"),
  "interests.inclination_leadership": answer(interests, "Course choice and educational perception", "Inclinations: leadership", "inventory-inclination-leadership"),
  "interests.interests": answer(interests, "Interests and daily routine", "Interests", "inventory-interests"),
  "interests.other_skills_hobbies": answer(interests, "Interests and daily routine", "Other skills and hobbies", "inventory-other-skills-hobbies"),
  "interests.desired_extracurricular_activities": answer(interests, "Interests and daily routine", "Extracurricular activities you would like to join", "inventory-desired-extracurricular"),
  "interests.reading_preferences": answer(interests, "Interests and daily routine", "Books and magazines you enjoy reading", "inventory-reading-preferences"),
  "interests.handedness": answer(interests, "Interests and daily routine", "Handedness", "inventory-handedness"),
  "interests.daily_hours_class": answer(interests, "Interests and daily routine", "Hours devoted daily: class", "inventory-daily-hours-class"),
  "interests.daily_hours_library": answer(interests, "Interests and daily routine", "Hours devoted daily: library work", "inventory-daily-hours-library"),
  "interests.daily_hours_studying": answer(interests, "Interests and daily routine", "Hours devoted daily: studying lessons", "inventory-daily-hours-studying"),
  "interests.daily_hours_rest": answer(interests, "Interests and daily routine", "Hours devoted daily: rest", "inventory-daily-hours-rest"),
  "interests.daily_hours_recreation": answer(interests, "Interests and daily routine", "Hours devoted daily: recreation", "inventory-daily-hours-recreation"),
  "interests.daily_hours_other": answer(interests, "Interests and daily routine", "Hours devoted daily: other activities", "inventory-daily-hours-other"),

  "section.organizations": sectionTarget(organizations),
  "organizations.inside_school": membershipTarget(OrganizationScopeValue.INSIDE_SCHOOL, "Organizations inside the university"),
  "organizations.outside_school": membershipTarget(OrganizationScopeValue.OUTSIDE_SCHOOL, "Organizations outside the university"),
  "organizations.transportation_modes": answer(organizations, "Transportation", "Ways you travel to the university", "inventory-transport-modes"),
  "organizations.transportation.tricycle": transportationTarget(TransportationModeValue.TRICYCLE),
  "organizations.transportation.bus": transportationTarget(TransportationModeValue.BUS),
  "organizations.transportation.jeepney": transportationTarget(TransportationModeValue.JEEPNEY),
  "organizations.transportation.van": transportationTarget(TransportationModeValue.VAN),
  "organizations.transportation.boat": transportationTarget(TransportationModeValue.BOAT),

  "section.plans": sectionTarget(plans),
  "plans.ideal_monthly_allowance": answer(plans, "Plans after graduation", "Ideal monthly allowance", "inventory-ideal-allowance"),
  "plans.intended_work_field": answer(plans, "Plans after graduation", "Field you intend to work in after graduation", "inventory-intended-work-field"),
  "plans.prior_counseling": answer(plans, "Prior counseling experience", "Prior counseling experience", "inventory-prior-counseling"),
  "plans.current_concerns": answer(plans, "Current concerns and fears", "Current concerns", "inventory-current-concerns"),
  "plans.current_fears": answer(plans, "Current concerns and fears", "Current fears", "inventory-current-fears"),
} satisfies Record<InventoryCorrectionTarget, Definition>;

// Catalog order, which the backend also stores and returns.
export const inventoryCorrectionTargetOrder: readonly InventoryCorrectionTarget[] = Object.values(InventoryCorrectionTarget);

// The backend's request limit (MAX_CORRECTION_TARGETS). The backend still enforces it.
export const MAX_INVENTORY_CORRECTION_TARGETS = 30;

const sectionLabels = new Map<string, string>(inventorySections.map((item) => [item.id, item.label]));

export function inventorySectionLabel(section: InventoryEditorSectionId): string {
  return sectionLabels.get(section) ?? section;
}

export function isInventoryCorrectionTarget(value: string): value is InventoryCorrectionTarget {
  return Object.hasOwn(inventoryCorrectionTargets, value);
}

export function inventoryCorrectionTarget(code: InventoryCorrectionTarget): Definition {
  return inventoryCorrectionTargets[code];
}

// "Contact number — Personal & contact". Never the code itself.
export function inventoryCorrectionTargetLabel(code: InventoryCorrectionTarget): string {
  const definition = inventoryCorrectionTargets[code];
  return `${definition.label} — ${inventorySectionLabel(definition.section)}`;
}

// Codes this build can name, in catalog order without repeats, and how many it could not. A build
// older than the backend may receive a newer code; it is never shown raw.
export function readInventoryCorrectionTargets(values: readonly string[] | null | undefined): {
  targets: InventoryCorrectionTarget[];
  unknown: number;
} {
  const known = new Set<InventoryCorrectionTarget>();
  let unknown = 0;
  for (const value of values ?? []) {
    if (isInventoryCorrectionTarget(value)) known.add(value);
    else unknown += 1;
  }
  return { targets: inventoryCorrectionTargetOrder.filter((code) => known.has(code)), unknown };
}

export function sortInventoryCorrectionTargets(values: Iterable<InventoryCorrectionTarget>): InventoryCorrectionTarget[] {
  const selected = new Set(values);
  return inventoryCorrectionTargetOrder.filter((code) => selected.has(code));
}

// --- Editor hints -------------------------------------------------------------------------------

export type InventoryReviewHints = {
  // Hint text per host, rendered by that host as `${host}-review`.
  hints: ReadonlyMap<string, string>;
  // The hint ids each control adds to its aria-describedby.
  describedBy: ReadonlyMap<string, string>;
  sections: ReadonlySet<InventoryEditorSectionId>;
  // Collapsed details that contain a targeted answer start open.
  openDetails: ReadonlySet<string>;
};

export const emptyInventoryReviewHints: InventoryReviewHints = {
  hints: new Map(),
  describedBy: new Map(),
  sections: new Set(),
  openDetails: new Set(),
};

function isAnchorVisible(definition: Definition, draft: InventoryPayload): boolean {
  return definition.condition ? definition.condition.visible(draft) : true;
}

// Where each requested review shows in the editor for the current draft. A conditional answer that
// is hidden by its parent answer is pointed out at the parent control instead.
export function inventoryReviewHints(
  targets: readonly InventoryCorrectionTarget[],
  draft: InventoryPayload,
): InventoryReviewHints {
  if (!targets.length) return emptyInventoryReviewHints;
  const hints = new Map<string, string[]>();
  const describedBy = new Map<string, string[]>();
  const sections = new Set<InventoryEditorSectionId>();
  const openDetails = new Set<string>();
  const add = <T>(map: Map<string, T[]>, key: string, value: T) => {
    const values = map.get(key) ?? [];
    if (!values.includes(value)) values.push(value);
    map.set(key, values);
  };

  for (const code of sortInventoryCorrectionTargets(targets)) {
    const definition = inventoryCorrectionTargets[code];
    if (definition.scope === "section") {
      sections.add(definition.section);
      continue;
    }
    const visible = isAnchorVisible(definition, draft);
    const condition = definition.condition;
    if (visible || !condition?.hint) {
      const host = definition.hintHost ?? definition.anchor;
      add(hints, host, inventoryReviewHintText[definition.scope]);
      add(describedBy, visible ? definition.anchor : condition!.fallback, inventoryReviewHintId(host));
      if (visible && definition.details) openDetails.add(definition.details);
    } else {
      add(hints, condition.fallback, condition.hint);
      add(describedBy, condition.fallback, inventoryReviewHintId(condition.fallback));
    }
  }

  return {
    hints: new Map([...hints].map(([host, texts]) => [host, texts.join(" ")])),
    describedBy: new Map([...describedBy].map(([id, hintIds]) => [id, hintIds.join(" ")])),
    sections,
    openDetails,
  };
}

// --- Navigation ---------------------------------------------------------------------------------

// Element ids to try, best first. The last is the section's own start, so a target always leads
// somewhere even if its control cannot take focus.
export function inventoryCorrectionFocusOrder(code: InventoryCorrectionTarget, draft: InventoryPayload): string[] {
  const definition = inventoryCorrectionTargets[code];
  if (definition.scope === "section") return [INVENTORY_SECTION_REVIEW_ID, INVENTORY_SECTION_START_ID];
  const order = isAnchorVisible(definition, draft)
    ? [definition.anchor, ...(definition.condition ? [definition.condition.fallback] : [])]
    : [definition.condition!.fallback];
  return [...order, INVENTORY_SECTION_START_ID];
}

const focusableSelector = "input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(:disabled)";

function focusTargetWithin(element: HTMLElement): HTMLElement | null {
  if (element.matches("input, select, textarea, button, [tabindex]")) return element;
  // A radio group is entered at its checked choice, as the Tab key would.
  return element.querySelector<HTMLElement>('input[type="radio"]:checked:not(:disabled)')
    ?? element.querySelector<HTMLElement>(focusableSelector);
}

// Opens the details that holds the target, scrolls it into view and moves focus to it. Returns the
// id that received focus.
export function focusInventoryCorrectionTarget(ids: readonly string[], root: Document = document): string | null {
  let scrolled = false;
  for (const id of ids) {
    const element = root.getElementById(id);
    if (!element) continue;
    const details = element.closest("details");
    if (details && !details.open) details.open = true;
    const target = focusTargetWithin(element);
    if (!scrolled) {
      element.scrollIntoView({ block: "center" });
      scrolled = true;
    }
    target?.focus({ preventScroll: true });
    if (target && root.activeElement === target) return id;
  }
  return null;
}
